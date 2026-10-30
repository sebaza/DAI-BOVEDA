"""Cifrado reversible del texto crudo y seudonimización (fase A2).

Por qué existe
--------------
`percepcion_comentario.texto` y `percepcion_publicacion.caption` se guardan CIFRADOS con una
clave que solo tiene el dueño. Cuando los datos pasen al almacén institucional, quien tenga
acceso ahí ve únicamente texto cifrado. Los procesos privilegiados (Curación, derivados,
subtemas, resumen semanal) descifran EN MEMORIA justo después de leer la fila; nada
descifrado se vuelve a escribir en la base.

Formato
-------
    enc:<versión>:<base64url(nonce || texto cifrado + tag)>

* AES-256-GCM, nonce aleatorio de 96 bits por llamada.
* AAD = contexto de la fila (``comentario:<id>`` / ``publicacion:<id>``): un texto cifrado
  copiado a otra fila no descifra (``TextoIlegible``).
* La versión elige la clave: la actual (``PERCEPCION_CLAVE_VERSION``) o una de
  ``PERCEPCION_CLAVES_ANTERIORES`` ("version:clave,version:clave"), para seguir leyendo lo
  cifrado antes de una rotación.
* Un valor que NO tiene el formato ``enc:...`` se devuelve tal cual al descifrar (transición:
  las filas en claro siguen funcionando). Un valor cifrado sin clave NUNCA se devuelve como si
  fuera texto: lanza ``ClaveNoConfigurada``.

Variables de entorno (ver ``app.config``)
-----------------------------------------
``PERCEPCION_CLAVE_TEXTO`` (base64url, 32 bytes), ``PERCEPCION_CLAVE_ID`` (otra clave de 32
bytes, solo para HMAC), ``PERCEPCION_CLAVE_VERSION`` (por defecto "1") y
``PERCEPCION_CLAVES_ANTERIORES``. Los mensajes de error nombran la variable, jamás el valor.
Si se pierde ``PERCEPCION_CLAVE_TEXTO`` los textos cifrados son IRRECUPERABLES.

Seudonimización
---------------
``seudonimo(valor, dominio)`` = HMAC-SHA256(``PERCEPCION_CLAVE_ID``, dominio NUL valor) en hex.
NO se aplica a la base local: cambiaría ``autor_hash`` en una base que sigue al worker. Se usa
en el almacén institucional (fase A3): ``scripts/publicar_warehouse_percepcion.py`` lo aplica a
la carga inicial y ``sincronizacion.py`` a los comentarios nuevos, siempre por ``seudonimo_autor``
(el dominio separa usos: "autor", "etiqueta", ...).
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import os
import re
from functools import lru_cache

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.config import get_settings

PREFIJO = "enc:"
_LARGO_CLAVE = 32
_LARGO_NONCE = 12
_LARGO_TAG = 16
_VERSION_OK = re.compile(r"^[A-Za-z0-9_-]{1,16}$")
# enc:<versión>:<base64url>; el cuerpo mide al menos nonce + tag (28 bytes = 38 caracteres).
_FORMATO = re.compile(r"^enc:([A-Za-z0-9_-]{1,16}):([A-Za-z0-9_-]{38,})\Z")

VAR_CLAVE_TEXTO = "PERCEPCION_CLAVE_TEXTO"
VAR_CLAVE_ID = "PERCEPCION_CLAVE_ID"
VAR_CLAVE_VERSION = "PERCEPCION_CLAVE_VERSION"
VAR_CLAVES_ANTERIORES = "PERCEPCION_CLAVES_ANTERIORES"


class ErrorCripto(Exception):
    """Base de los errores de este módulo. Los mensajes nunca traen claves ni texto."""


class ClaveNoConfigurada(ErrorCripto):
    """Falta una clave necesaria (o no hay clave para la versión del valor cifrado)."""


class ClaveInvalida(ErrorCripto):
    """Una clave configurada no es base64url de 32 bytes."""


class TextoIlegible(ErrorCripto):
    """El valor cifrado no se pudo descifrar: clave equivocada, alterado o de otra fila."""


# ---------------------------------------------------------------------------------------
# Claves
# ---------------------------------------------------------------------------------------
def _decodificar_clave(nombre: str, valor: str) -> bytes:
    limpio = (valor or "").strip()
    try:
        crudo = base64.urlsafe_b64decode(limpio + "=" * (-len(limpio) % 4))
    except (binascii.Error, ValueError):
        raise ClaveInvalida(f"{nombre} no es base64url válido.") from None
    if len(crudo) != _LARGO_CLAVE:
        raise ClaveInvalida(f"{nombre} debe decodificar a exactamente {_LARGO_CLAVE} bytes.")
    return crudo


def _version_actual() -> str:
    version = (get_settings().percepcion_clave_version or "").strip() or "1"
    if not _VERSION_OK.match(version):
        raise ClaveInvalida(f"{VAR_CLAVE_VERSION} solo admite letras, dígitos, '-' y '_' (máx. 16).")
    return version


def _claves_de_texto() -> dict[str, bytes]:
    """{versión: clave}. La actual solo está si PERCEPCION_CLAVE_TEXTO está configurada."""
    s = get_settings()
    claves: dict[str, bytes] = {}
    for par in (s.percepcion_claves_anteriores or "").split(","):
        par = par.strip()
        if not par:
            continue
        version, sep, clave = par.partition(":")
        version = version.strip()
        if not sep or not _VERSION_OK.match(version):
            raise ClaveInvalida(
                f"{VAR_CLAVES_ANTERIORES} debe tener el formato 'version:clave,version:clave'.")
        claves[version] = _decodificar_clave(VAR_CLAVES_ANTERIORES, clave)
    if (s.percepcion_clave_texto or "").strip():
        claves[_version_actual()] = _decodificar_clave(VAR_CLAVE_TEXTO, s.percepcion_clave_texto)
    return claves


def hay_clave() -> bool:
    """¿Hay clave actual para cifrar? (Valida su formato: una clave mal escrita lanza.)"""
    bruta = get_settings().percepcion_clave_texto
    if not (bruta or "").strip():
        return False
    _decodificar_clave(VAR_CLAVE_TEXTO, bruta)
    return True


@lru_cache(maxsize=16)
def _aes(clave: bytes) -> AESGCM:
    return AESGCM(clave)


# ---------------------------------------------------------------------------------------
# Cifrar / descifrar
# ---------------------------------------------------------------------------------------
def es_cifrado(valor: str | None) -> bool:
    """¿Tiene la FORMA de un valor cifrado? Es forjable: un comentario público puede imitarla.

    Para decidir en una ruta de ESCRITURA si algo ya está cifrado usa `es_genuino`.
    """
    return isinstance(valor, str) and _FORMATO.match(valor) is not None


def es_genuino(valor: str | None, contexto: str) -> bool:
    """¿Es un cifrado AUTÉNTICO de esta fila? (descifra de verdad con su AAD y una clave).

    Lo que tiene la forma pero no descifra es texto en claro (alguien lo escribió así) y debe
    cifrarse. Si la versión no tiene clave configurada no se puede verificar: lanza
    `ClaveNoConfigurada` (no se arriesga a cifrar encima de un cifrado legítimo).
    """
    if not es_cifrado(valor):
        return False
    try:
        descifrar(valor, contexto)
    except TextoIlegible:
        return False
    return True


def cifrar(texto: str | None, contexto: str) -> str | None:
    """AES-256-GCM con la clave actual. ``None`` y "" pasan sin cambios."""
    if texto is None or texto == "":
        return texto
    if not hay_clave():
        raise ClaveNoConfigurada(f"{VAR_CLAVE_TEXTO} no está configurada: no se puede cifrar.")
    version = _version_actual()
    clave = _claves_de_texto()[version]
    nonce = os.urandom(_LARGO_NONCE)
    cuerpo = _aes(clave).encrypt(nonce, texto.encode("utf-8"), contexto.encode("utf-8"))
    return f"{PREFIJO}{version}:" + base64.urlsafe_b64encode(nonce + cuerpo).decode("ascii").rstrip("=")


def descifrar(valor: str | None, contexto: str) -> str | None:
    """Inversa de ``cifrar``. Lo que no tiene formato ``enc:...`` se devuelve igual."""
    if valor is None:
        return valor
    m = _FORMATO.match(valor)
    if m is None:
        return valor
    version, cuerpo = m.groups()
    claves = _claves_de_texto()
    if not claves:
        raise ClaveNoConfigurada(
            f"{VAR_CLAVE_TEXTO} no está configurada: no se puede descifrar.")
    clave = claves.get(version)
    if clave is None:
        # Con claves configuradas, una versión desconocida se trata como ilegible y no como
        # falta de configuración: un comentario público con forma "enc:9:..." no debe poder
        # detener todo el proceso. Una clave rotada se mantiene en PERCEPCION_CLAVES_ANTERIORES.
        raise TextoIlegible(
            f"Versión de clave desconocida: si es una clave rotada, agrégala a {VAR_CLAVES_ANTERIORES}.")
    try:
        crudo = base64.urlsafe_b64decode(cuerpo + "=" * (-len(cuerpo) % 4))
        return _aes(clave).decrypt(
            crudo[:_LARGO_NONCE], crudo[_LARGO_NONCE:], contexto.encode("utf-8")).decode("utf-8")
    except (InvalidTag, ValueError, binascii.Error, UnicodeDecodeError):
        raise TextoIlegible(
            "No se pudo descifrar el valor (clave distinta, alterado o de otra fila).") from None


# Ayudas por tabla: el contexto es parte del cifrado, así que se arma en UN solo lugar.
def contexto_comentario(id_: int) -> str:
    return f"comentario:{id_}"


def contexto_publicacion(id_: int) -> str:
    return f"publicacion:{id_}"


def texto_de(id_: int, valor: str | None) -> str | None:
    """``percepcion_comentario.texto`` en claro (descifra si hace falta)."""
    return descifrar(valor, contexto_comentario(id_))


def caption_de(id_: int, valor: str | None) -> str | None:
    """``percepcion_publicacion.caption`` en claro (descifra si hace falta)."""
    return descifrar(valor, contexto_publicacion(id_))


def texto_de_seguro(id_: int, valor: str | None, fallos: list[int] | None = None) -> str | None:
    """Como `texto_de`, pero un valor ilegible (`TextoIlegible`) da "" y anota el id en `fallos`.

    Para lectores por lotes: una fila mala no debe tumbar todo el proceso. Solo ids, nunca
    contenido. `ClaveNoConfigurada` SÍ se propaga: una clave ausente es un error de configuración.
    """
    try:
        return texto_de(id_, valor)
    except TextoIlegible:
        if fallos is not None:
            fallos.append(id_)
        return ""


def caption_de_seguro(id_: int, valor: str | None, fallos: list[int] | None = None) -> str | None:
    try:
        return caption_de(id_, valor)
    except TextoIlegible:
        if fallos is not None:
            fallos.append(id_)
        return ""


def cifrar_texto(id_: int, valor: str | None) -> str | None:
    return cifrar(valor, contexto_comentario(id_))


def cifrar_caption(id_: int, valor: str | None) -> str | None:
    return cifrar(valor, contexto_publicacion(id_))


# ---------------------------------------------------------------------------------------
# Seudonimización (para la exportación al almacén; no se aplica a la base local)
# ---------------------------------------------------------------------------------------
def seudonimo(valor: str, dominio: str) -> str:
    """HMAC-SHA256 hex de ``dominio:valor`` con ``PERCEPCION_CLAVE_ID``. Determinista."""
    bruta = (get_settings().percepcion_clave_id or "").strip()
    if not bruta:
        raise ClaveNoConfigurada(f"{VAR_CLAVE_ID} no está configurada.")
    clave = _decodificar_clave(VAR_CLAVE_ID, bruta)
    if hmac.compare_digest(clave, _decodificar_clave(VAR_CLAVE_TEXTO, get_settings().percepcion_clave_texto)
                           if (get_settings().percepcion_clave_texto or "").strip() else b""):
        raise ClaveInvalida(f"{VAR_CLAVE_ID} no puede ser igual a {VAR_CLAVE_TEXTO}.")
    if "\x00" in dominio:
        raise ValueError("El dominio no puede contener NUL.")
    # Dominio y valor separados por NUL: ("a", "b:c") y ("a:b", "c") dan entradas distintas.
    mensaje = dominio.encode("utf-8") + b"\x00" + valor.encode("utf-8")
    return hmac.new(clave, mensaje, hashlib.sha256).hexdigest()


DOMINIO_AUTOR = "autor"


def seudonimo_autor(valor: str | None) -> str | None:
    """Seudónimo del ``autor_hash`` del worker para el almacén. Vacío/None pasan sin cambios.

    UN solo lugar para la regla, así la carga y la sincronización no pueden divergir.
    Determinista: la misma persona sigue siendo "una" persona (conteos de autores distintos).
    """
    if not valor:
        return valor
    return seudonimo(valor, DOMINIO_AUTOR)


DOMINIO_EXT_COMENTARIO = "comentario_ext"


def seudonimo_ext_comentario(valor: str | None) -> str | None:
    """Seudónimo del ``external_id`` de un comentario (enlaza con su autor público) para el almacén.

    Mismo criterio que `seudonimo_autor` y la misma garantía: un solo lugar, determinista. Hex de
    64 caracteres: cabe en `external_id` (String(80)). Solo para comentarios; el `external_id` de
    publicaciones y el `handle` de cuentas son datos públicos institucionales y no se tocan.
    """
    if not valor:
        return valor
    return seudonimo(valor, DOMINIO_EXT_COMENTARIO)
