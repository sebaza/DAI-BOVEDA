"""Genera las claves del cifrado de texto de Percepción (ver `services/percepcion/cripto.py`).

Imprime DOS claves aleatorias nuevas (base64url, 32 bytes) con el nombre de la variable de
entorno de cada una. No escribe nada en disco: copia los valores a `backend/.env` tú mismo.

⚠️ GUÁRDALAS en un gestor de contraseñas Y en un respaldo aparte. Si se pierde
PERCEPCION_CLAVE_TEXTO los textos cifrados son IRRECUPERABLES (no hay puerta trasera).
No las subas a git ni las pegues en chats o tickets.

Uso:
    backend\\.venv\\Scripts\\python.exe -I scripts/generar_claves_percepcion.py
"""
from __future__ import annotations

import base64
import os

VAR_CLAVE_TEXTO = "PERCEPCION_CLAVE_TEXTO"
VAR_CLAVE_ID = "PERCEPCION_CLAVE_ID"


def _clave_nueva() -> str:
    return base64.urlsafe_b64encode(os.urandom(32)).decode("ascii")


def generar_claves() -> dict[str, str]:
    """{variable: clave} con dos claves independientes. No imprime ni escribe nada."""
    return {VAR_CLAVE_TEXTO: _clave_nueva(), VAR_CLAVE_ID: _clave_nueva()}


def main() -> int:
    claves = generar_claves()
    print("Agrega estas líneas a backend/.env (y NO las compartas):\n")
    for nombre, valor in claves.items():
        print(f"{nombre}={valor}")
    print("\nPERCEPCION_CLAVE_VERSION=1   (opcional; es el valor por defecto)")
    print()
    print("ADVERTENCIA: guarda ambas claves en un gestor de contraseñas Y en un respaldo aparte.")
    print(f"Si pierdes {VAR_CLAVE_TEXTO}, los textos cifrados NO se pueden recuperar.")
    print(f"{VAR_CLAVE_ID} solo sirve para seudonimizar (HMAC) en la exportación al almacén.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
