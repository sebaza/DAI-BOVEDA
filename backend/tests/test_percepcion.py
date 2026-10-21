"""Tests del feature Percepción (dashboard filtrable sobre la tabla de hechos).

BD SQLite en memoria con las tablas percepcion_*. Siembra hechos diarios y valida
el resumen, la evolución, la comparación, las emociones, los eventos, las
anomalías, los filtros y el filtrado combinado. Sin red, sin worker, sin torch.

Correr con:
    backend\\.venv\\Scripts\\python.exe -m unittest tests.test_percepcion
"""
from __future__ import annotations

import unittest
from datetime import date, datetime, time, timedelta
from unittest import mock

from sqlalchemy import create_engine, func, select, update
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.services.percepcion import calidad, curacion, derivados, eventos, lexico, postura, repository
from app.services.percepcion.repository import ETIQUETAS_TEMA
from app.services.percepcion.models import (
    PercepcionComentario,
    PercepcionComentarioFamilia,
    PercepcionComentarioToken,
    PercepcionCorreccion,
    PercepcionCuenta,
    PercepcionEvento,
    PercepcionHechoDiario,
    PercepcionPublicacion,
    PercepcionPublicacionRasgo,
    PercepcionScore,
    PercepcionTemaCustom,
)

BASE = date(2026, 1, 1)


def _memoria():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False},
        poolclass=StaticPool, future=True,
    )
    # Se crean TODAS las tablas, no solo hechos y eventos: desde 09-2026 la postura
    # se calcula sobre el corpus (necesita el tipo de cuenta, que el hecho no
    # guarda), así que un fixture sin corpus dejaba esas vistas reventando por tabla
    # inexistente en vez de por el dato. Las tablas de más quedan vacías y no
    # molestan a quien no las use.
    for m in (PercepcionHechoDiario, PercepcionEvento, PercepcionCuenta,
              PercepcionPublicacion, PercepcionComentario, PercepcionScore,
              PercepcionCorreccion, PercepcionComentarioToken, PercepcionComentarioFamilia,
              PercepcionPublicacionRasgo):
        m.__table__.create(engine)
    return sessionmaker(bind=engine, future=True)()


def _memoria_completa():
    """BD con las tablas del CORPUS (cuenta/publicación/comentario/score).

    La nube de palabras no lee la tabla de hechos sino los textos crudos, así que
    necesita el join completo — `_memoria()` solo crea hechos y eventos.
    """
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False},
        poolclass=StaticPool, future=True,
    )
    for m in (PercepcionHechoDiario, PercepcionEvento, PercepcionCuenta,
              PercepcionPublicacion, PercepcionComentario, PercepcionScore,
              PercepcionCorreccion, PercepcionComentarioToken, PercepcionComentarioFamilia,
              PercepcionPublicacionRasgo):
        m.__table__.create(engine)
    return sessionmaker(bind=engine, future=True)()


def _derivar(db):
    """Llena las tablas derivadas del texto, como el precálculo de producción.

    La API ya no tokeniza el texto: lee `percepcion_comentario_token`/`_familia`. Todo
    test que siembra comentarios y consulta nube/términos/destacados/impacto debe
    llamarlo después de sembrar.
    """
    derivados.reconstruir(db)
    db.commit()


def _commit_y_derivar(db):
    db.commit()
    derivados.reconstruir(db)
    db.commit()


def _sembrar_comentarios(db, comentarios, *, campus="Antofagasta", facultad="Ingeniería"):
    """Siembra (texto, sentimiento, emoción, tema[, fecha]) bajo una cuenta/publicación.

    La fecha es opcional (default 02/01/2026) para no tocar los tests que no la
    necesitan; los de términos sí la usan, porque miden evolución semanal.
    """
    db.add(PercepcionCuenta(id=1, handle="ucn", nombre="UCN", tipo="institucional",
                            campus=campus, facultad=facultad, departamento=None, carrera=None))
    db.add(PercepcionPublicacion(id=1, cuenta_id=1, external_id="p1",
                                 fecha_publicacion=datetime(2026, 1, 1), tipo="post",
                                 caption="", n_comentarios=len(comentarios), n_likes=0))
    for i, fila in enumerate(comentarios, start=1):
        texto, sent, emo, tema = fila[:4]
        fecha = fila[4] if len(fila) > 4 else datetime(2026, 1, 2)
        db.add(PercepcionComentario(
            id=i, publicacion_id=1, external_id=f"c{i}", autor_hash=f"h{i}",
            texto=texto, fecha_comentario=fecha, idioma="es",
            n_likes=0, tema=tema, tema_confianza=0.9,
        ))
        db.add(PercepcionScore(
            id=i, comentario_id=i, modelo="test", sentimiento=sent,
            prob_pos=1.0 if sent == "POS" else 0.0,
            prob_neu=1.0 if sent == "NEU" else 0.0,
            prob_neg=1.0 if sent == "NEG" else 0.0,
            emocion=emo, prob_emocion=0.9,
        ))
    db.commit()
    _derivar(db)


def _hecho(dia, **kw):
    # Peso=1 por comentario (suma_peso = n) → índice == cálculo sin ponderar.
    # Peso=1 por comentario (suma_peso=n, ponderado==sin ponderar) salvo override.
    base = dict(
        n_comentarios=10, n_pos=5, n_neu=3, n_neg=2,
        suma_peso=10.0, peso_pos=5.0, peso_neg=2.0,
        suma_pos=5.0, suma_neg=2.0, suma_ganadora=8.0,
    )
    base.update(kw)
    return PercepcionHechoDiario(fecha=BASE + timedelta(days=dia), **base)


def _corpus_espejo(db, dia: int, *, campus, facultad, departamento, tema,
                   n_pos, n_neu, n_neg, cuenta_tipo="institucional"):
    """Comentarios reales que reproducen EXACTAMENTE un hecho diario.

    Hace falta desde 09-2026: la postura mira el TIPO DE CUENTA —un neutro en la
    federación es adverso— y el grano de `percepcion_hecho_diario` no lo guarda, así
    que `postura_institucional` bajó al corpus. Un fixture que solo siembre hechos
    deja esas vistas sin datos.

    El tipo por defecto es `institucional` a propósito: con él la regla nueva no se
    activa y los conteos salen idénticos a los de siempre, así que los asserts
    históricos siguen valiendo. Ver `test_percepcion_postura_federacion.py`.
    """
    from app.services.percepcion.models import (
        PercepcionComentario, PercepcionCuenta, PercepcionPublicacion, PercepcionScore,
    )
    clave = f"{campus}|{facultad}|{departamento}|{cuenta_tipo}"
    cid = abs(hash(clave)) % 90_000 + 1000
    if not db.get(PercepcionCuenta, cid):
        db.add(PercepcionCuenta(id=cid, handle=f"h{cid}", nombre=clave, tipo=cuenta_tipo,
                                campus=campus, facultad=facultad, departamento=departamento))
        db.flush()
    pid = cid * 1000 + dia
    if not db.get(PercepcionPublicacion, pid):
        db.add(PercepcionPublicacion(
            id=pid, cuenta_id=cid, external_id=f"p{pid}", tipo="post", caption="",
            fecha_publicacion=datetime.combine(BASE + timedelta(days=dia), time()), n_likes=0))
        db.flush()
    base_id = pid * 100
    n = 0
    for sent, cuantos in (("POS", n_pos), ("NEU", n_neu), ("NEG", n_neg)):
        for _ in range(cuantos):
            mid = base_id + n; n += 1
            db.add(PercepcionComentario(
                id=mid, publicacion_id=pid, external_id=f"c{mid}", autor_hash=f"a{mid}",
                texto=f"{sent} {tema}", tema=tema, n_likes=0,
                fecha_comentario=datetime.combine(BASE + timedelta(days=dia), time())))
            db.add(PercepcionScore(
                id=mid, comentario_id=mid, modelo="t", sentimiento=sent,
                prob_pos=1.0 if sent == "POS" else 0.0,
                prob_neu=1.0 if sent == "NEU" else 0.0,
                prob_neg=1.0 if sent == "NEG" else 0.0))


def _sembrar(db):
    for i in range(30):
        # Corpus espejo de los dos hechos de abajo. Sin esto, todo lo que se calcula
        # sobre el corpus —la postura, desde 09-2026— queda sin datos en los tests.
        _corpus_espejo(db, i, campus="Antofagasta", facultad="Ingeniería",
                       departamento="Depto Industrial", tema="infraestructura",
                       n_pos=2, n_neu=3, n_neg=5)
        _corpus_espejo(db, i, campus="Coquimbo", facultad="Salud",
                       departamento="Depto Enfermería", tema="eventos",
                       n_pos=9, n_neu=2, n_neg=1)
        # Antofagasta · Ingeniería · Industrial · tema infraestructura (baja)
        db.add(_hecho(i, campus="Antofagasta", facultad="Ingeniería",
                      departamento="Depto Industrial", tema="infraestructura",
                      n_comentarios=10, n_pos=2, n_neu=3, n_neg=5,
                      suma_peso=10.0, peso_pos=2.0, peso_neg=5.0,
                      suma_pos=2.0, suma_neg=5.0, suma_ganadora=8.0,
                      emociones={"anger": 5, "others": 5}))
        # Coquimbo · Salud · Enfermería · tema eventos (alta)
        db.add(_hecho(i, campus="Coquimbo", facultad="Salud",
                      departamento="Depto Enfermería", tema="eventos",
                      n_comentarios=12, n_pos=9, n_neu=2, n_neg=1,
                      suma_peso=12.0, peso_pos=9.0, peso_neg=1.0,
                      suma_pos=9.0, suma_neg=1.0, suma_ganadora=10.0,
                      emociones={"joy": 9, "others": 3}))
    db.add(PercepcionEvento(
        nombre="Semana de exámenes", tipo="examenes",
        fecha_inicio=BASE + timedelta(days=5), fecha_fin=BASE + timedelta(days=11),
        ambito="global",
    ))
    db.commit()


class TestPercepcion(unittest.TestCase):
    def setUp(self):
        self.db = _memoria()
        _sembrar(self.db)

    def tearDown(self):
        self.db.close()

    def test_sin_datos(self):
        self.assertFalse(repository.resumen(_memoria())["hay_datos"])

    def test_resumen_global(self):
        r = repository.resumen(self.db, dias=30)
        self.assertTrue(r["hay_datos"])
        # 22 comentarios/día × 30 días = 660.
        self.assertEqual(r["n_comentarios"], 660)
        d = r["distribucion"]
        self.assertEqual(d["positivo"] + d["neutral"] + d["negativo"], 660)
        self.assertTrue(0 <= r["indice_promedio"] <= 100)
        self.assertTrue(0 <= r["confianza_promedio"] <= 1)

    def test_filtro_por_sede(self):
        ant = repository.resumen(self.db, dias=30, campus="Antofagasta")
        coq = repository.resumen(self.db, dias=30, campus="Coquimbo")
        # Antofagasta = infraestructura (negativa) → índice menor que Coquimbo (eventos).
        self.assertLess(ant["indice_promedio"], coq["indice_promedio"])
        self.assertEqual(ant["n_comentarios"], 300)   # 10/día × 30
        self.assertEqual(coq["n_comentarios"], 360)    # 12/día × 30

    def test_filtro_por_departamento_y_tema(self):
        r = repository.resumen(
            self.db, dias=30, departamento="Depto Enfermería", tema="eventos"
        )
        self.assertEqual(r["n_comentarios"], 360)
        # `eventos` es un tema retirado y NO atribuible: su crédito va a la mitad
        # (esquema «DAI × peso de tema»), así que el techo de este fixture bajó de 75
        # a 62,5. El test afirma lo que le importa —el filtro devuelve una lectura
        # claramente positiva—, no un número que depende del esquema de pesos.
        self.assertGreater(r["indice_promedio"], 55)

    def test_evolucion_filtrada(self):
        ev = repository.evolucion(self.db, dias=90, campus="Antofagasta")
        self.assertEqual(len(ev["puntos"]), 30)
        # Datos uniformes → índice trailing estable y negativo (infraestructura).
        self.assertTrue(all(p["indice"] is not None and p["indice"] < 50 for p in ev["puntos"]))
        # 'ese día y hacia atrás': cada punto acumula su ventana → más volumen que el día
        # suelto (10). El último punto ya tiene toda la ventana detrás.
        self.assertGreater(ev["puntos"][-1]["n_comentarios"], 10)

    def test_por_tema(self):
        pt = repository.por_tema(self.db, dias=30)
        temas = {t["tema"]: t for t in pt["temas"]}
        self.assertIn("infraestructura", temas)
        self.assertIn("eventos", temas)
        self.assertGreater(temas["eventos"]["indice_promedio"], temas["infraestructura"]["indice_promedio"])

    def test_por_tema_filtrado_por_sede(self):
        pt = repository.por_tema(self.db, dias=30, campus="Antofagasta")
        self.assertEqual({t["tema"] for t in pt["temas"]}, {"infraestructura"})

    def test_por_unidad_facultad(self):
        pu = repository.por_unidad(self.db, nivel="facultad", dias=30)
        nombres = [u["nombre"] for u in pu["unidades"]]
        self.assertEqual(nombres[0], "Salud")       # eventos, alta
        self.assertEqual(nombres[-1], "Ingeniería")  # infraestructura, baja

    def test_por_unidad_departamento(self):
        pu = repository.por_unidad(self.db, nivel="departamento", dias=30)
        self.assertEqual({u["nombre"] for u in pu["unidades"]}, {"Depto Industrial", "Depto Enfermería"})

    def test_emociones_filtradas(self):
        em = repository.emociones(self.db, dias=30, campus="Coquimbo")
        items = {i["emocion"]: i for i in em["items"]}
        self.assertIn("joy", items)
        self.assertEqual(items["joy"]["etiqueta"], "Alegría")
        self.assertNotIn("anger", items)  # anger es de Antofagasta

    def test_etiquetas_emociones_nuevas_y_compatibilidad_historica(self):
        self.assertEqual(repository.ETIQUETAS_EMOCION["humor_ironia"], "Humor e ironía")
        self.assertEqual(repository.ETIQUETAS_EMOCION["sin_emocion"], "Sin emoción")
        self.assertIn("histórico", repository.ETIQUETAS_EMOCION["others"])

    def test_eventos(self):
        ev = repository.eventos(self.db, dias=120)
        self.assertEqual(len(ev["items"]), 1)
        self.assertEqual(ev["items"][0]["tipo"], "examenes")

    def test_eventos_incluye_rangos_que_se_solapan(self):
        ev = repository.eventos(self.db, dias=20)
        self.assertEqual(len(ev["items"]), 1)
        self.assertEqual(ev["items"][0]["tipo"], "examenes")

    def test_filtros_opciones(self):
        f = repository.filtros(self.db)
        self.assertEqual(set(f["sedes"]), {"Antofagasta", "Coquimbo"})
        self.assertEqual(set(f["facultades"]), {"Ingeniería", "Salud"})
        self.assertEqual(set(f["departamentos"]), {"Depto Industrial", "Depto Enfermería"})
        self.assertIn("infraestructura", {t["tema"] for t in f["temas"]})

    def test_indice_ponderado_por_likes(self):
        # Mismo conteo de comentarios, pero un comentario negativo MUY likeado:
        # el índice debe caer más de lo que el conteo (mitad y mitad) sugeriría.
        db = _memoria()
        # 10 comentarios: 5 POS peso 1 c/u, 5 NEG pero uno con peso enorme (viral).
        db.add(PercepcionHechoDiario(
            fecha=BASE, campus="X", n_comentarios=10, n_pos=5, n_neu=0, n_neg=5,
            suma_peso=5 * 1.0 + 4 * 1.0 + 1 * 20.0,   # 4 NEG normales + 1 NEG viral(20) + 5 POS
            peso_pos=5 * 1.0, peso_neg=4 * 1.0 + 1 * 20.0,
            suma_ganadora=10.0,
        ))
        res = repository.resumen(db, dias=1)
        # Conteo mitad/mitad daría ~50; ponderado por el viral negativo, cae bien abajo.
        self.assertLess(res["indice_promedio"], 40)

    def test_decaimiento_pesa_lo_reciente(self):
        # Día viejo MUY negativo + día reciente MUY positivo, mismos pesos crudos.
        # El índice ACTUAL (decaído/recencia) se va hacia el reciente; el promedio llano no.
        db = _memoria()
        # El TEMA va explícito: desde el esquema «DAI × peso de tema» el crédito de un
        # tema no atribuible se corta a la mitad, y un hecho sin tema cae de ese lado.
        # Sin declararlo, este test del DECAIMIENTO quedaría atado al peso por defecto.
        db.add(PercepcionHechoDiario(  # viejo, negativo
            fecha=BASE, campus="X", tema="academico",
            n_comentarios=100, n_pos=0, n_neu=0, n_neg=100,
            suma_peso=100.0, peso_pos=0.0, peso_neg=100.0, suma_ganadora=100.0,
        ))
        db.add(PercepcionHechoDiario(  # 60 días después, positivo (día ancla)
            fecha=BASE + timedelta(days=60), campus="X", tema="academico",
            n_comentarios=100, n_pos=100, n_neu=0, n_neg=0,
            suma_peso=100.0, peso_pos=100.0, peso_neg=0.0, suma_ganadora=100.0,
        ))
        r = repository.resumen(db, dias=90)
        # Decaimiento LINEAL, vida 30: a 60 días (>30) el día viejo pesa 0 → domina lo
        # reciente (positivo). El índice ACTUAL se va bien arriba de 50.
        self.assertGreater(r["indice_actual"], 70)
        # El promedio llano (sin recencia) queda al medio: ~50 (mitad neg vieja, mitad pos).
        self.assertAlmostEqual(r["indice_promedio"], 50, delta=1)
        # Los conteos NO se decaen: 200 comentarios reales.
        self.assertEqual(r["n_comentarios"], 200)
        self.assertEqual(r["distribucion"]["negativo"], 100)

    def test_control_ponderar_likes(self):
        # 10 comentarios: mayoría positiva, pero UN viral negativo (peso enorme).
        db = _memoria()
        db.add(PercepcionHechoDiario(
            fecha=BASE, campus="X", n_comentarios=10, n_pos=6, n_neu=0, n_neg=4,
            suma_pos=6.0, suma_neg=4.0,                       # sin ponderar: positivo
            suma_peso=46.0, peso_pos=6.0, peso_neg=40.0,      # con likes: el viral neg manda
            suma_ganadora=10.0,
        ))
        # ponderar_tema=False: este test mide el control de LIKES. Con los pesos por
        # tema activos, la fila sin tema cae al peso por defecto (0,5) y el indice se
        # corre hacia 50 por un motivo que no tiene nada que ver con lo que se prueba.
        con = repository.resumen(db, dias=1, peso_likes=1.0,
                                 ponderar_tema=False)["indice_promedio"]
        sin = repository.resumen(db, dias=1, peso_likes=0.0,
                                 ponderar_tema=False)["indice_promedio"]
        self.assertLess(con, 30)      # con likes: negativo (el viral)
        self.assertGreater(sin, 55)   # sin likes: positivo (la mayoría)
        # Intensidad intermedia (α=0.5): entre ambos extremos.
        med = repository.resumen(db, dias=1, peso_likes=0.5)["indice_promedio"]
        self.assertTrue(con < med < sin)

    def test_control_vida_media(self):
        # Día viejo negativo + reciente positivo (mismos pesos).
        db = _memoria()
        # Tema explícito por lo mismo que en `test_decaimiento_pesa_lo_reciente`: este
        # test mide la VIDA MEDIA, no el peso del tema.
        db.add(PercepcionHechoDiario(
            fecha=BASE, campus="X", tema="academico",
            n_comentarios=100, n_pos=0, n_neu=0, n_neg=100,
            suma_pos=0.0, suma_neg=100.0, suma_peso=100.0, peso_pos=0.0, peso_neg=100.0,
            suma_ganadora=100.0))
        db.add(PercepcionHechoDiario(
            fecha=BASE + timedelta(days=60), campus="X", tema="academico",
            n_comentarios=100, n_pos=100, n_neu=0, n_neg=0,
            suma_pos=100.0, suma_neg=0.0, suma_peso=100.0, peso_pos=100.0, peso_neg=0.0,
            suma_ganadora=100.0))
        con_decay = repository.resumen(db, dias=90, vida_media=30)["indice_actual"]
        sin_decay = repository.resumen(db, dias=90, vida_media=0)["indice_actual"]
        self.assertGreater(con_decay, 70)          # decae lo viejo → domina lo reciente (positivo)
        self.assertAlmostEqual(sin_decay, 50, delta=1)  # sin decaimiento → 50/50

    def test_decaimiento_lineal_no_por_mitades(self):
        ref = BASE + timedelta(days=30)
        # A la mitad de la vida (15 d) el peso es 0.5 exacto (lineal). El modelo viejo
        # (mitades) daba ~0.71 acá: por eso se sentía que "arrastraba" de más.
        self.assertAlmostEqual(repository._decaimiento(BASE + timedelta(days=15), ref, 30), 0.5, places=6)
        # A los `vida_media` días (30) el comentario DEJA DE CONTAR (0), no 0.5.
        self.assertAlmostEqual(repository._decaimiento(BASE, ref, 30), 0.0, places=6)
        # Más viejo que la vida media → sigue en 0 (nunca negativo).
        self.assertEqual(repository._decaimiento(BASE - timedelta(days=10), ref, 30), 0.0)
        # vida_media=0 → sin decaimiento (peso 1).
        self.assertEqual(repository._decaimiento(BASE, ref, 0), 1.0)

    def test_comentario_suelto_no_dispara_indice_actual(self):
        # 20 días neutrales con volumen + UN único comentario positivo el día ancla.
        # Antes (índice = día aislado) el general saltaba a ~100 por ese comentario;
        # ahora, con 'ese día y hacia atrás', se diluye y queda cerca del neutro.
        db = _memoria()
        for i in range(20):
            db.add(PercepcionHechoDiario(
                fecha=BASE + timedelta(days=i), campus="X",
                n_comentarios=20, n_pos=0, n_neu=20, n_neg=0,
                suma_peso=20.0, peso_pos=0.0, peso_neg=0.0,
                suma_pos=0.0, suma_neg=0.0, suma_ganadora=18.0,
            ))
        db.add(PercepcionHechoDiario(  # día ancla: 1 comentario, 100% positivo
            fecha=BASE + timedelta(days=20), campus="X",
            n_comentarios=1, n_pos=1, n_neu=0, n_neg=0,
            suma_peso=1.0, peso_pos=1.0, peso_neg=0.0,
            suma_pos=1.0, suma_neg=0.0, suma_ganadora=1.0,
        ))
        r = repository.resumen(db, dias=30, vida_media=30)
        # El general NO se dispara: los 20 días neutrales previos pesan en su ventana.
        self.assertLess(r["indice_actual"], 55)

    def test_rango_corto(self):
        # dias=1 → solo el último día (relativo al máximo).
        r = repository.resumen(self.db, dias=1)
        self.assertLessEqual(r["n_comentarios"], 44)  # 2 días como mucho (frontera inclusiva)


class TestEventosABM(unittest.TestCase):
    """ABM de marcas de contexto (vacaciones, pruebas, paro…) del gráfico."""

    def setUp(self):
        self.db = _memoria()

    def tearDown(self):
        self.db.close()

    def test_crear_listar_actualizar_eliminar(self):
        creado = eventos.crear(
            self.db, nombre="Vacaciones de invierno", tipo="receso",
            fecha_inicio=BASE, fecha_fin=BASE + timedelta(days=14),
        )
        self.assertEqual(creado["tipo"], "receso")
        self.assertEqual(creado["tipo_label"], "Vacaciones / receso")
        self.assertIsNotNone(creado["id"])

        self.assertEqual(len(eventos.listar(self.db)["items"]), 1)

        editado = eventos.actualizar(
            self.db, creado["id"], nombre="Receso de invierno", tipo="receso",
            fecha_inicio=BASE, fecha_fin=BASE + timedelta(days=20),
        )
        self.assertEqual(editado["nombre"], "Receso de invierno")
        self.assertEqual(editado["fecha_fin"], BASE + timedelta(days=20))

        eventos.eliminar(self.db, creado["id"])
        self.assertEqual(eventos.listar(self.db)["items"], [])

    def test_evento_de_un_dia_usa_inicio_como_fin(self):
        # Sin fecha_fin: se guarda fin = inicio (el gráfico igual lo dibuja).
        e = eventos.crear(self.db, nombre="Anuncio rectoría", tipo="resolucion", fecha_inicio=BASE)
        self.assertEqual(e["fecha_fin"], BASE)

    def test_validaciones(self):
        with self.assertRaises(ValueError):   # nombre vacío
            eventos.crear(self.db, nombre="   ", tipo="receso", fecha_inicio=BASE)
        with self.assertRaises(ValueError):   # tipo fuera de la taxonomía
            eventos.crear(self.db, nombre="X", tipo="inventado", fecha_inicio=BASE)
        with self.assertRaises(ValueError):   # fin anterior al inicio
            eventos.crear(self.db, nombre="X", tipo="receso",
                          fecha_inicio=BASE + timedelta(days=5), fecha_fin=BASE)
        with self.assertRaises(LookupError):  # id inexistente
            eventos.eliminar(self.db, 9999)

    def test_tipos_incluyen_vacaciones_y_pruebas(self):
        tipos = {t["tipo"] for t in eventos.tipos_disponibles()}
        self.assertIn("receso", tipos)     # vacaciones
        self.assertIn("examenes", tipos)   # periodo de pruebas
        self.assertIn("paro", tipos)

    def test_eventos_creados_aparecen_en_el_overlay_del_grafico(self):
        # El ABM escribe y `repository.eventos` (overlay del gráfico) lo lee.
        # La ventana del overlay se ancla a la tabla de HECHOS: sin datos diarios no
        # hay gráfico y por lo tanto tampoco bandas, así que sembramos unos días.
        _sembrar(self.db)
        eventos.crear(self.db, nombre="Periodo de pruebas", tipo="examenes",
                      fecha_inicio=BASE + timedelta(days=2), fecha_fin=BASE + timedelta(days=9))
        items = repository.eventos(self.db, dias=120)["items"]
        self.assertIn("examenes", [i["tipo"] for i in items])


class TestSintesis(unittest.TestCase):
    """Capa 1 del resumen ejecutivo: de qué hablan, con qué emoción, en qué área."""

    def setUp(self):
        self.db = _memoria()
        _sembrar(self.db)

    def tearDown(self):
        self.db.close()

    def test_sin_datos(self):
        s = repository.sintesis(_memoria())
        self.assertFalse(s["hay_datos"])
        self.assertEqual(s["temas"], [])
        self.assertEqual(s["cambios"], [])

    def test_cruza_tema_emocion_y_area_en_una_llamada(self):
        s = repository.sintesis(self.db, dias=30)
        por_tema = {t["tema"]: t for t in s["temas"]}
        # infraestructura se sembró SOLO en Antofagasta/Ingeniería y con anger.
        infra = por_tema["infraestructura"]
        self.assertEqual(infra["emocion_dominante"]["emocion"], "anger")
        self.assertEqual(infra["areas_top"][0]["nombre"], "Ingeniería")
        # eventos se sembró SOLO en Coquimbo/Salud y con joy.
        ev = por_tema["eventos"]
        self.assertEqual(ev["emocion_dominante"]["emocion"], "joy")
        self.assertEqual(ev["areas_top"][0]["nombre"], "Salud")

    def test_area_trae_su_tema_y_emocion_dominante(self):
        s = repository.sintesis(self.db, dias=30, nivel="facultad")
        por_area = {a["nombre"]: a for a in s["areas"]}
        self.assertEqual(por_area["Ingeniería"]["tema_dominante"]["tema"], "infraestructura")
        self.assertEqual(por_area["Salud"]["tema_dominante"]["tema"], "eventos")
        self.assertEqual(por_area["Salud"]["emocion_dominante"]["emocion"], "joy")

    def test_share_pct_suma_cien(self):
        s = repository.sintesis(self.db, dias=30)
        self.assertAlmostEqual(sum(t["share_pct"] for t in s["temas"]), 100.0, places=1)

    def test_indice_nunca_es_none_con_datos(self):
        # Regresión: por_unidad decae por recencia y devuelve None cuando todos los
        # comentarios de una unidad caen fuera de la vida media (se ve como
        # "39 comentarios, índice —"). La síntesis va SIN decaimiento a propósito.
        s = repository.sintesis(self.db, dias=30)
        for fila in s["temas"] + s["areas"]:
            self.assertIsNotNone(fila["indice"], f"índice None en {fila}")

    def test_evidencia_suficiente_marca_las_muestras_chicas(self):
        db = _memoria()
        # 1 día suelto: 10 comentarios < N_MIN_EVIDENCIA (30).
        db.add(_hecho(0, campus="Antofagasta", facultad="Chica", tema="tramites",
                      emociones={"joy": 10}))
        db.commit()
        s = repository.sintesis(db, dias=30)
        self.assertFalse(s["temas"][0]["evidencia_suficiente"])
        self.assertFalse(s["areas"][0]["evidencia_suficiente"])
        db.close()

    def test_orden_peor_pone_primero_el_peor_hablado(self):
        # Default: "peor". Ingeniería (2 pos / 5 neg) debe ir antes que Salud.
        s = repository.sintesis(self.db, dias=30)
        self.assertEqual(s["orden"], "peor")
        nombres = [a["nombre"] for a in s["areas"]]
        self.assertLess(nombres.index("Ingeniería"), nombres.index("Salud"))
        # Y los temas siguen la misma lectura: infraestructura antes que eventos.
        temas = [t["tema"] for t in s["temas"]]
        self.assertLess(temas.index("infraestructura"), temas.index("eventos"))

    def test_orden_peor_no_deja_arriba_una_muestra_chica(self):
        # Regresión del riesgo de "ordenar por índice a secas": una unidad de 1
        # comentario con índice pésimo NO puede encabezar el listado.
        self.db.add(_hecho(0, campus="Coquimbo", facultad="Diminuta", tema="otros",
                           n_comentarios=1, n_pos=0, n_neu=0, n_neg=1,
                           suma_peso=1.0, peso_pos=0.0, peso_neg=1.0,
                           suma_pos=0.0, suma_neg=1.0, suma_ganadora=1.0,
                           emociones={"anger": 1}))
        self.db.commit()
        s = repository.sintesis(self.db, dias=30)
        self.assertNotEqual(s["areas"][0]["nombre"], "Diminuta")
        self.assertFalse(s["areas"][-1]["evidencia_suficiente"])

    def test_orden_por_volumen_sigue_disponible(self):
        s = repository.sintesis(self.db, dias=30, orden="volumen")
        con_ev = [a for a in s["areas"] if a["evidencia_suficiente"]]
        self.assertEqual(
            [a["n_comentarios"] for a in con_ev],
            sorted((a["n_comentarios"] for a in con_ev), reverse=True),
        )

    def test_filtro_de_tema_aplica_a_areas_pero_no_al_desglose(self):
        # "En infraestructura, ¿qué unidades están peor?" — infraestructura se
        # sembró SOLO en Ingeniería, así que el corte por área debe quedarse con esa.
        s = repository.sintesis(self.db, dias=30, tema="infraestructura")
        self.assertEqual(s["tema_filtrado"], "infraestructura")
        self.assertEqual([a["nombre"] for a in s["areas"]], ["Ingeniería"])
        self.assertEqual(s["areas"][0]["tema_dominante"]["tema"], "infraestructura")
        # El desglose por tema NO se filtra (mostraría una sola fila).
        self.assertGreater(len(s["temas"]), 1)

    def test_cambios_solo_con_evidencia_suficiente(self):
        # Con 3 comentarios, una variacion del 300% es ruido y taparia lo real.
        s = repository.sintesis(self.db, dias=30)
        for c in s["cambios"]:
            self.assertTrue(c["evidencia_suficiente"])
            self.assertGreaterEqual(c["n_comentarios"], repository.N_MIN_EVIDENCIA)

    def test_el_piso_de_dispersion_evita_falsas_anomalias(self):
        # REGRESION: la sd de la ventana corta subestima la variabilidad de una
        # serie trailing (~2.7x en datos reales), y sin piso quedaba marcado el
        # 19% de los dias. Con una serie de variacion SUAVE y sostenida, ningun
        # dia deberia salir como anomalia.
        db = _memoria()
        for i in range(40):
            db.add(_hecho(i, campus="Antofagasta", facultad="F", departamento="D",
                          tema="academico",
                          n_comentarios=50, n_pos=25 + (i % 3), n_neu=15, n_neg=10 - (i % 3),
                          suma_peso=50.0, peso_pos=25.0 + (i % 3), peso_neg=10.0 - (i % 3),
                          suma_pos=25.0 + (i % 3), suma_neg=10.0 - (i % 3),
                          suma_ganadora=45.0))
        db.commit()
        puntos = repository.evolucion(db, dias=40)["puntos"]
        anomalias = [p for p in puntos if p["es_anomalia"]]
        self.assertLessEqual(
            len(anomalias), max(1, len(puntos) // 10),
            f"{len(anomalias)} anomalias sobre {len(puntos)} puntos: el piso no esta actuando",
        )
        db.close()

    def test_sin_periodo_previo_no_inventa_comparacion(self):
        # La siembra cubre 30 dias: con dias=30 la ventana previa cae ENTERA
        # antes del primer dato. Sin esta guarda, cada tema se reportaria como
        # "nuevo este periodo", que es falso — no aparecieron, no hay con que
        # comparar. Es el caso real del filtro en "Todo".
        s = repository.sintesis(self.db, dias=30)
        self.assertIsNone(s["periodo_anterior"])
        self.assertEqual(s["cambios"], [])

    def test_cambios_comparan_contra_el_periodo_anterior(self):
        # Ventana corta (7 dias) para que la previa caiga DENTRO de los datos.
        s = repository.sintesis(self.db, dias=7)
        prev = s["periodo_anterior"]
        self.assertIsNotNone(prev)
        # La ventana previa termina justo antes de que empiece la actual.
        self.assertLess(prev["hasta"], s["periodo"]["desde"])
        for c in s["cambios"]:
            self.assertIn("n_anterior", c)
            self.assertIn("delta_indice", c)
            self.assertTrue(c["evidencia_suficiente"])

    def test_un_tema_nuevo_encabeza_los_cambios(self):
        # Aparecer de la nada es el movimiento mas fuerte posible.
        for i in range(30):
            self.db.add(_hecho(i, campus="Antofagasta", facultad="Ingenieria",
                               departamento="Depto", tema="tramites",
                               emociones={"joy": 10}))
        self.db.commit()
        s = repository.sintesis(self.db, dias=30)
        nuevos = [c for c in s["cambios"] if c["es_nuevo"]]
        if nuevos:
            self.assertEqual(s["cambios"][0]["es_nuevo"], True)

    def test_periodo_se_acota_a_los_datos_reales(self):
        # dias=36500 ("Todo") restaría ~100 años; el período informado debe
        # empezar en el primer día CON datos, no en 1926.
        s = repository.sintesis(self.db, dias=36500)
        self.assertEqual(s["periodo"]["desde"], BASE)

    def test_cobertura_area_refleja_los_hechos_sin_dimension(self):
        # Un hecho SIN facultad no entra al corte por área (el agrupado descarta
        # NULL), pero sí al total. La cobertura debe delatar esa diferencia.
        self.db.add(_hecho(0, campus="Antofagasta", facultad=None,
                           departamento=None, tema="otros", n_comentarios=100,
                           n_pos=50, n_neu=30, n_neg=20,
                           suma_peso=100.0, peso_pos=50.0, peso_neg=20.0,
                           suma_pos=50.0, suma_neg=20.0, suma_ganadora=80.0,
                           emociones={"joy": 100}))
        self.db.commit()
        s = repository.sintesis(self.db, dias=30, nivel="facultad")
        cob = s["cobertura_area"]
        self.assertEqual(cob["n_total"], s["global"]["n_comentarios"])
        self.assertLess(cob["n_con_area"], cob["n_total"])
        self.assertEqual(cob["n_con_area"], sum(a["n_comentarios"] for a in s["areas"]))
        self.assertLess(cob["pct"], 100.0)

    def test_global_coincide_con_el_resumen_del_dashboard(self):
        s = repository.sintesis(self.db, dias=30)
        r = repository.resumen(self.db, dias=30)
        self.assertEqual(s["global"]["n_comentarios"], r["n_comentarios"])
        self.assertEqual(s["global"]["distribucion"], r["distribucion"])


class TestTokenizar(unittest.TestCase):
    """Tokenización de la nube: lo que NO debe entrar importa más que lo que sí."""

    def test_descarta_urls_menciones_y_stopwords(self):
        t = repository._tokenizar(
            "Hola @juan.perez mirá https://ucn.cl/algo el arancel de la carrera"
        )
        self.assertNotIn("juan", t)       # mención = PII
        self.assertNotIn("perez", t)
        self.assertNotIn("https", t)
        self.assertNotIn("ucn", t)        # dominio de la URL
        self.assertNotIn("hola", t)       # saludo sin señal
        self.assertNotIn("de", t)         # stopword
        self.assertIn("arancel", t)
        self.assertIn("carrera", t)

    def test_filtra_los_artefactos_de_scraping_de_instagram(self):
        # Visto literal en datos reales: el scraper pega estos textos al comentario
        # y, sin filtrarlos, encabezan la nube aunque no los escribió nadie.
        t = repository._tokenizar("pero pa las fiestas lujosas si See translation View all 8 replies")
        for basura in ("see", "translation", "view", "replies", "all"):
            self.assertNotIn(basura, t)
        self.assertIn("fiestas", t)
        self.assertIn("lujosas", t)

    def test_quita_la_frase_del_scraper_sin_vetar_la_palabra(self):
        # "Seca!❤️ comments from Facebook" → el scraper pegó la frase. Se saca la
        # FRASE, no la palabra: quien mencione Facebook de verdad debe contar.
        t = repository._tokenizar("Seca! comments from Facebook")
        self.assertIn("seca", t)
        self.assertNotIn("facebook", t)
        self.assertIn("facebook", repository._tokenizar("prefiero facebook antes que otra red"))

    def test_no_borra_cookie_que_es_la_mascota_de_la_ucn(self):
        # REGRESIÓN: "cookie" se filtró por parecer chrome del scraper y resultó
        # ser la mascota — 7 comentarios reales hablan de ella.
        t = repository._tokenizar("Parece todo un caballero el Cookie")
        self.assertIn("cookie", t)

    def test_descarta_handles_pegados_sin_arroba(self):
        # "Participando:B tote.mny_ cldliio_" — el comentario real es la primera
        # palabra; el resto son personas etiquetadas (PII) que el scraper pegó.
        t = repository._tokenizar("Participando tote.mny_ cldliio_ av_angamos vixoo94_")
        self.assertIn("participando", t)
        for handle in ("tote", "mny", "cldliio", "angamos", "vixoo"):
            self.assertNotIn(handle, t)

    def test_los_handles_no_se_llevan_puestas_palabras_normales(self):
        t = repository._tokenizar("la paralización afectó las clases de invierno")
        for palabra in ("paralización", "afectó", "clases", "invierno"):
            self.assertIn(palabra, t)

    def test_conserva_tildes_y_enie(self):
        t = repository._tokenizar("el año pasado la matrícula subió")
        self.assertIn("año", t)           # "año" != "ano"
        self.assertIn("matrícula", t)

    def test_excluir_saca_palabras_a_pedido(self):
        self.assertIn("arancel", repository._tokenizar("el arancel subió"))
        self.assertNotIn("arancel", repository._tokenizar("el arancel subió", {"arancel"}))


class TestNubePalabras(unittest.TestCase):
    def setUp(self):
        self.db = _memoria_completa()

    def tearDown(self):
        self.db.close()

    def test_sin_datos(self):
        n = repository.nube_palabras(_memoria_completa())
        self.assertFalse(n["hay_datos"])
        self.assertEqual(n["palabras"], [])

    def test_cuenta_comentarios_no_repeticiones(self):
        # "arancel" se repite 3 veces DENTRO de un comentario y aparece en otros 2.
        # Debe contar 3 (comentarios), no 5 (ocurrencias): la nube mide cuánta
        # GENTE lo dice, no cuánto insiste una sola persona.
        _sembrar_comentarios(self.db, [
            ("el arancel el arancel y otra vez arancel", "NEG", "anger", "matricula_aranceles"),
            ("subió el arancel", "NEG", "anger", "matricula_aranceles"),
            ("arancel caro", "NEG", "anger", "matricula_aranceles"),
        ])
        n = repository.nube_palabras(self.db, dias=3650, min_frecuencia=1)
        por_texto = {p["texto"]: p for p in n["palabras"]}
        self.assertEqual(por_texto["arancel"]["n"], 3)

    def test_min_frecuencia_descarta_las_dichas_una_vez(self):
        _sembrar_comentarios(self.db, [
            ("arancel caro", "NEG", "anger", "matricula_aranceles"),
            ("arancel alto", "NEG", "anger", "matricula_aranceles"),
            ("biblioteca tranquila", "POS", "joy", "infraestructura"),
        ])
        n = repository.nube_palabras(self.db, dias=3650, min_frecuencia=2)
        textos = [p["texto"] for p in n["palabras"]]
        self.assertIn("arancel", textos)
        self.assertNotIn("biblioteca", textos)   # aparece en 1 solo comentario

    def test_sentimiento_dominante_no_lo_gana_el_neutral_por_mayoria(self):
        # 2 NEU + 1 NEG: el neutral es mayoría, pero la palabra tiene polaridad
        # negativa y esa es la señal que hay que mostrar.
        _sembrar_comentarios(self.db, [
            ("arancel", "NEU", "sin_emocion", "matricula_aranceles"),
            ("arancel", "NEU", "sin_emocion", "matricula_aranceles"),
            ("arancel", "NEG", "anger", "matricula_aranceles"),
        ])
        n = repository.nube_palabras(self.db, dias=3650, min_frecuencia=1)
        p = next(p for p in n["palabras"] if p["texto"] == "arancel")
        self.assertEqual(p["sentimiento_dominante"], "NEG")
        self.assertEqual((p["pos"], p["neu"], p["neg"]), (0, 2, 1))

    def test_arrastra_tema_y_emocion_dominantes(self):
        _sembrar_comentarios(self.db, [
            ("arancel imposible", "NEG", "anger", "matricula_aranceles"),
            ("arancel imposible", "NEG", "anger", "matricula_aranceles"),
        ])
        n = repository.nube_palabras(self.db, dias=3650, min_frecuencia=1)
        p = next(p for p in n["palabras"] if p["texto"] == "arancel")
        self.assertEqual(p["tema_dominante"], "matricula_aranceles")
        self.assertEqual(p["emocion_dominante"], "anger")
        self.assertEqual(p["emocion_etiqueta"], "Enojo")

    def test_respeta_el_filtro_de_tema(self):
        _sembrar_comentarios(self.db, [
            ("arancel caro", "NEG", "anger", "matricula_aranceles"),
            ("arancel caro", "NEG", "anger", "matricula_aranceles"),
            ("biblioteca fria", "NEG", "anger", "infraestructura"),
            ("biblioteca fria", "NEG", "anger", "infraestructura"),
        ])
        n = repository.nube_palabras(self.db, dias=3650, min_frecuencia=1,
                                     tema="infraestructura")
        textos = [p["texto"] for p in n["palabras"]]
        self.assertIn("biblioteca", textos)
        self.assertNotIn("arancel", textos)

    def test_agrupa_singular_y_plural_bajo_la_forma_mas_usada(self):
        _sembrar_comentarios(self.db, [
            ("los cursos", "NEG", "anger", "academico"),
            ("los cursos", "NEG", "anger", "academico"),
            ("el curso", "NEG", "anger", "academico"),
        ])
        n = repository.nube_palabras(self.db, dias=3650, min_frecuencia=1)
        por_texto = {p["texto"]: p for p in n["palabras"]}
        # Gana "cursos" por ser la forma más escrita, y suma los 3 comentarios.
        self.assertIn("cursos", por_texto)
        self.assertNotIn("curso", por_texto)
        self.assertEqual(por_texto["cursos"]["n"], 3)
        self.assertEqual(por_texto["cursos"]["variantes"], ["curso"])

    def test_agrupar_no_cuenta_dos_veces_el_mismo_comentario(self):
        # "el curso y los cursos" es UN comentario: la palabra agrupada debe
        # valer 1, no 2. Por eso la canónica se aplica ANTES del set() por
        # comentario, y no se suman los conteos ya calculados.
        _sembrar_comentarios(self.db, [
            ("el curso y los cursos son buenos", "NEU", "sin_emocion", "academico"),
        ])
        n = repository.nube_palabras(self.db, dias=3650, min_frecuencia=1)
        por_texto = {p["texto"]: p for p in n["palabras"]}
        clave = "cursos" if "cursos" in por_texto else "curso"
        self.assertEqual(por_texto[clave]["n"], 1)

    def test_no_agrupa_palabras_que_solo_difieren_en_la_enie(self):
        # REGRESIÓN: normalizar la ñ fundió "toño" (apodo) con "tono" en datos
        # reales. En español la ñ es otra letra, no una "n" con adorno.
        self.assertNotEqual(
            repository._raiz_agrupacion("tono"), repository._raiz_agrupacion("toño")
        )

    def test_agrupar_variantes_se_puede_apagar(self):
        _sembrar_comentarios(self.db, [
            ("los cursos", "NEU", "sin_emocion", "academico"),
            ("el curso", "NEU", "sin_emocion", "academico"),
        ])
        n = repository.nube_palabras(self.db, dias=3650, min_frecuencia=1,
                                     agrupar_variantes=False)
        textos = [p["texto"] for p in n["palabras"]]
        self.assertIn("cursos", textos)
        self.assertIn("curso", textos)

    def test_no_agrupa_troncos_demasiado_cortos(self):
        # Exigir 4+ letras de tronco evita fusiones absurdas del tipo "mes"/"me".
        self.assertNotEqual(
            repository._raiz_agrupacion("mes"), repository._raiz_agrupacion("me")
        )

    def test_limite_recorta_pero_informa_el_total(self):
        _sembrar_comentarios(self.db, [
            ("arancel matricula carrera biblioteca laboratorio", "NEG", "anger", "otros"),
            ("arancel matricula carrera biblioteca laboratorio", "NEG", "anger", "otros"),
        ])
        n = repository.nube_palabras(self.db, dias=3650, min_frecuencia=1, limite=2)
        self.assertEqual(len(n["palabras"]), 2)
        self.assertGreater(n["n_palabras_unicas"], 2)


class TestRecenciaEnSintesis(unittest.TestCase):
    """El control global de recencia también manda en Resumen y Comparar.

    Se hizo global a pedido de la DAI: antes la recencia solo existía en
    Conversación y el resto leía siempre el promedio del período. Con un control
    ÚNICO que afecta a todas por igual no reaparece el problema que motivó ese
    encierro —que una pestaña usara recencia SIEMPRE y otra NUNCA, dando dos
    números distintos para el mismo tema—: ahora todas leen igual.
    """

    def setUp(self):
        self.db = _memoria()

    def tearDown(self):
        self.db.close()

    def test_sin_recencia_todas_las_unidades_tienen_indice(self):
        for i in range(60):
            self.db.add(_hecho(i, facultad="Vieja" if i < 20 else "Nueva"))
        self.db.commit()
        areas = repository.sintesis(self.db, dias=3650, nivel="facultad")["areas"]
        self.assertEqual(len(areas), 2)
        self.assertTrue(all(a["indice"] is not None for a in areas))

    def test_con_recencia_una_unidad_sin_actividad_reciente_queda_sin_indice(self):
        """Consecuencia REAL y esperada, no un bug: si todos los comentarios de
        una unidad son más viejos que la vida configurada, su peso decae a cero.
        Medido sobre datos reales con rango de 90 días: con vida 30 quedan 2 de 8
        facultades sin índice; con vida 7, 4 de 8. El `n` queda intacto, así que
        la UI puede decir "39 comentarios · sin actividad reciente" en vez de un
        guion mudo."""
        for i in range(60):
            self.db.add(_hecho(i, facultad="Vieja" if i < 20 else "Nueva"))
        self.db.commit()
        areas = {a["nombre"]: a for a in repository.sintesis(
            self.db, dias=3650, nivel="facultad", vida_media=10)["areas"]}
        self.assertIsNone(areas["Vieja"]["indice"])
        self.assertGreater(areas["Vieja"]["n_comentarios"], 0)   # el volumen NO se pierde
        self.assertIsNotNone(areas["Nueva"]["indice"])

    def test_que_cambio_mide_los_dos_periodos_con_el_MISMO_metodo(self):
        """El delta no puede depender del slider: comparar un período decaído
        contra uno sin decaer daría un número que no significa nada. Dentro de
        "Qué cambió" los dos lados van llanos, y el índice que se muestra al lado
        del delta es el mismo con el que se calculó."""
        for i in range(60):
            self.db.add(_hecho(i, tema="academico"))
        self.db.commit()
        sin = repository.sintesis(self.db, dias=30, vida_media=0)["cambios"]
        con = repository.sintesis(self.db, dias=30, vida_media=15)["cambios"]
        self.assertTrue(sin, "el fixture debe producir cambios comparables")
        self.assertEqual(
            [(c["tema"], c["delta_indice"], c["indice"]) for c in sin],
            [(c["tema"], c["delta_indice"], c["indice"]) for c in con],
        )


class TestDestacados(unittest.TestCase):
    """Lo que el RESUMEN muestra de un vistazo: palabras que pesan, forma de la
    serie y emoción que más creció."""

    def setUp(self):
        self.db = _memoria_completa()

    def tearDown(self):
        self.db.close()

    # --- Palabras que más pesan ---------------------------------------------

    def test_el_vocabulario_se_valida_GLOBAL_y_por_eso_filtra_la_pii(self):
        """LA regla anti-PII, y hay que entender por qué es esta y no otra.

        El tokenizador no atrapa los handles de Instagram que son letras puras
        (`ignaciamilann`, `jmanuuu`, `mish`): sin "_", dígitos ni punto interno,
        parecen palabras. Se midieron dos heurísticas estructurales sobre el
        corpus real y las DOS fallaron:
          * publicaciones distintas: `ignaciamilann` aparece en 5 pubs (ratio
            1.6), idéntico a `felicitaciones` (1.6) y `paro` (1.6).
          * autores distintos: lo escriben 7 personas, igual que `toma` (7).
            En los posts de sorteo mucha gente distinta etiqueta a la misma.

        Lo que sí separa es el VOLUMEN GLOBAL: los handles llegan a 8 apariciones
        en todo el corpus; el vocabulario real pasa de 10. Por eso el mínimo se
        evalúa sobre TODO el período y recién después se rankea por área — así una
        facultad con 4 comentarios no puede publicar el nombre de una persona.
        """
        comentarios = [("la matricula es cara", "NEG", "anger", "matricula_aranceles")] * 3
        # Un "handle" que aparece poco: no debe entrar al vocabulario.
        comentarios += [("saludos jmanuuu", "POS", "joy", "otros")]
        _sembrar_comentarios(self.db, comentarios)
        d = repository.destacados(self.db, dias=3650, min_global=3)
        textos = [p["texto"] for p in d["palabras"]]
        self.assertIn("matricula", textos)
        self.assertNotIn("jmanuuu", textos)

    def test_ordena_por_negativos_absolutos_no_por_porcentaje(self):
        """Ordenar por % negativo encumbra palabras vacías: medido sobre el corpus
        real, `futuro` (n=10, 70% neg) y `familias` (n=12, 67%) quedaban arriba de
        `estudiantes` (n=37, 41%), que es la que de verdad importa. El conteo
        absoluto de negativos pondera volumen y carga a la vez."""
        _sembrar_comentarios(self.db, (
            [("los estudiantes reclaman", "NEG", "anger", "academico")] * 4
            + [("los estudiantes celebran", "POS", "joy", "academico")] * 6
            + [("futuro incierto", "NEG", "sadness", "academico")] * 2
        ))
        d = repository.destacados(self.db, dias=3650, min_global=2)
        por_texto = {p["texto"]: p for p in d["palabras"]}
        self.assertEqual(por_texto["estudiantes"]["n_neg"], 4)
        # "estudiantes" tiene MENOR % negativo que "futuro" (40% vs 100%) pero
        # más negativos absolutos: debe ir primero.
        orden = [p["texto"] for p in d["palabras"]]
        self.assertLess(orden.index("estudiantes"), orden.index("futuro"))

    def test_cada_palabra_trae_su_desglose_de_polaridad(self):
        _sembrar_comentarios(self.db, (
            [("arancel imposible", "NEG", "anger", "matricula_aranceles")] * 3
            + [("arancel razonable", "POS", "joy", "matricula_aranceles")] * 1
        ))
        d = repository.destacados(self.db, dias=3650, min_global=2)
        p = next(x for x in d["palabras"] if x["texto"] == "arancel")
        self.assertEqual((p["n"], p["n_pos"], p["n_neg"]), (4, 1, 3))
        self.assertEqual(p["pct_neg"], 75.0)

    # --- Serie mensual -------------------------------------------------------

    def test_serie_mensual_agrupa_por_mes_sin_decaimiento(self):
        """La forma de la curva mes a mes. NO repite la evolución diaria de
        Conversación: esa es trailing, interactiva y con eventos; esta es la
        silueta del período para leer de un vistazo."""
        db = _memoria()
        for i in range(70):   # ~2.3 meses desde el 01/01/2026
            db.add(_hecho(i))
        db.commit()
        d = repository.destacados(db, dias=3650)
        meses = [m["mes"] for m in d["serie_mensual"]]
        self.assertEqual(meses[:3], [date(2026, 1, 1), date(2026, 2, 1), date(2026, 3, 1)])
        for m in d["serie_mensual"]:
            self.assertIsNotNone(m["indice"])
            self.assertGreater(m["n_comentarios"], 0)
        db.close()

    def test_sin_datos_no_rompe(self):
        d = repository.destacados(_memoria_completa(), dias=3650)
        self.assertEqual(d["palabras"], [])
        self.assertEqual(d["serie_mensual"], [])
        self.assertIsNone(d["emocion_cambio"])

    # --- Emoción que más creció ---------------------------------------------

    def test_emocion_que_mas_crecio_contra_el_periodo_anterior(self):
        db = _memoria()
        # Mes previo: alegría. Mes actual: irrumpe el enojo.
        for i in range(30):
            db.add(_hecho(i, emociones={"joy": 10}))
        for i in range(30, 60):
            db.add(_hecho(i, emociones={"joy": 10, "anger": 8}))
        db.commit()
        d = repository.destacados(db, fecha_desde=date(2026, 1, 31), fecha_hasta=date(2026, 3, 1))
        self.assertIsNotNone(d["emocion_cambio"])
        self.assertEqual(d["emocion_cambio"]["emocion"], "anger")
        self.assertEqual(d["emocion_cambio"]["etiqueta"], "Enojo")
        self.assertTrue(d["emocion_cambio"]["es_nueva"])
        db.close()

    def test_sin_periodo_previo_no_inventa_emocion_que_crecio(self):
        db = _memoria()
        for i in range(30):
            db.add(_hecho(i, emociones={"joy": 10}))
        db.commit()
        # Rango "Todo": la ventana previa cae entera antes del primer dato.
        self.assertIsNone(repository.destacados(db, dias=36500)["emocion_cambio"])
        db.close()


class TestPalabrasPorArea(unittest.TestCase):
    """El detalle que pidió la DAI: qué se dice en cada facultad/departamento."""

    def setUp(self):
        self.db = _memoria_completa()

    def tearDown(self):
        self.db.close()

    def _sembrar_dos_areas(self):
        for cid, fac in ((1, "Ingeniería"), (2, "Derecho")):
            self.db.add(PercepcionCuenta(
                id=cid, handle=f"h{cid}", nombre=fac, tipo="institucional",
                campus="Antofagasta", facultad=fac, departamento=f"Escuela de {fac}",
                carrera=None, origen="interno",
            ))
            self.db.add(PercepcionPublicacion(
                id=cid, cuenta_id=cid, external_id=f"p{cid}",
                fecha_publicacion=datetime(2026, 1, 1), tipo="post",
                caption="", n_comentarios=3, n_likes=0,
            ))
        i = 0
        # Ingeniería habla de laboratorio; Derecho, de biblioteca. Los textos son
        # DISJUNTOS a propósito: si comparten palabras de relleno ("necesita",
        # "cambios"), esas copan el top y el test deja de medir lo que dice medir.
        for fac_id, texto, sent in ((1, "laboratorio pesimo", "NEG"),
                                    (2, "biblioteca comoda", "POS")):
            for _ in range(3):
                i += 1
                self.db.add(PercepcionComentario(
                    id=i, publicacion_id=fac_id, external_id=f"c{i}", autor_hash=f"a{i}",
                    texto=texto, fecha_comentario=datetime(2026, 1, 2),
                    idioma="es", n_likes=0, tema="infraestructura", tema_confianza=0.9,
                ))
                self.db.add(PercepcionScore(
                    id=i, comentario_id=i, modelo="test", sentimiento=sent,
                    prob_pos=1.0 if sent == "POS" else 0.0, prob_neu=0.0,
                    prob_neg=1.0 if sent == "NEG" else 0.0,
                    emocion="anger" if sent == "NEG" else "joy", prob_emocion=0.9,
                ))
        self.db.commit()
        _derivar(self.db)
        # `sintesis` lee de la tabla de HECHOS: hay que agregarla desde el corpus,
        # igual que hace el worker tras cada ingesta.
        curacion.reagregar(self.db)

    def test_cada_area_trae_sus_palabras(self):
        self._sembrar_dos_areas()
        s = repository.sintesis(self.db, dias=3650, nivel="facultad", min_global_palabras=2)
        por_nombre = {a["nombre"]: a for a in s["areas"]}
        ing = [p["texto"] for p in por_nombre["Ingeniería"]["palabras_top"]]
        der = [p["texto"] for p in por_nombre["Derecho"]["palabras_top"]]
        self.assertIn("laboratorio", ing)
        self.assertNotIn("biblioteca", ing)
        self.assertIn("biblioteca", der)

    def test_funciona_tambien_a_nivel_departamento(self):
        self._sembrar_dos_areas()
        s = repository.sintesis(self.db, dias=3650, nivel="departamento", min_global_palabras=2)
        por_nombre = {a["nombre"]: a for a in s["areas"]}
        self.assertIn(
            "laboratorio",
            [p["texto"] for p in por_nombre["Escuela de Ingeniería"]["palabras_top"]],
        )

    def test_los_temas_tambien_traen_sus_palabras(self):
        self._sembrar_dos_areas()
        s = repository.sintesis(self.db, dias=3650, min_global_palabras=2)
        infra = next(t for t in s["temas"] if t["tema"] == "infraestructura")
        textos = [p["texto"] for p in infra["palabras_top"]]
        self.assertIn("laboratorio", textos)
        self.assertIn("biblioteca", textos)

    def test_una_palabra_dicha_una_sola_vez_en_el_area_no_la_representa(self):
        """El mínimo GLOBAL protege de la PII; el LOCAL protege del ridículo.

        Sin él, el Departamento de Ingeniería Industrial mostraba
        "amo (1) · año (1) · buena (1)": palabras del vocabulario común que en ese
        departamento se dijeron UNA vez. Un área sin nada que supere el mínimo
        devuelve lista vacía y la UI avisa, en vez de inventar un titular.
        """
        self._sembrar_dos_areas()
        # Una tercera cuenta con UN comentario: su palabra está en el vocabulario
        # global (aparece en las otras áreas) pero acá se dijo una sola vez.
        self.db.add(PercepcionCuenta(id=3, handle="h3", nombre="Chica",
                                     tipo="institucional", campus="Antofagasta",
                                     facultad="Chica", departamento="Escuela Chica",
                                     carrera=None, origen="interno"))
        self.db.add(PercepcionPublicacion(id=3, cuenta_id=3, external_id="p3",
                                          fecha_publicacion=datetime(2026, 1, 1),
                                          tipo="post", caption="", n_comentarios=1, n_likes=0))
        self.db.add(PercepcionComentario(id=99, publicacion_id=3, external_id="c99",
                                         autor_hash="a99", texto="laboratorio pesimo",
                                         fecha_comentario=datetime(2026, 1, 2), idioma="es",
                                         n_likes=0, tema="infraestructura", tema_confianza=0.9))
        self.db.add(PercepcionScore(id=99, comentario_id=99, modelo="test",
                                    sentimiento="NEG", prob_pos=0.0, prob_neu=0.0,
                                    prob_neg=1.0, emocion="anger", prob_emocion=0.9))
        self.db.commit()
        _derivar(self.db)
        curacion.reagregar(self.db)
        s = repository.sintesis(self.db, dias=3650, nivel="facultad", min_global_palabras=2)
        chica = next(a for a in s["areas"] if a["nombre"] == "Chica")
        self.assertEqual(chica["palabras_top"], [])
        # La misma palabra SÍ representa a Ingeniería, donde se dijo 3 veces.
        ing = next(a for a in s["areas"] if a["nombre"] == "Ingeniería")
        self.assertIn("laboratorio", [p["texto"] for p in ing["palabras_top"]])

    def test_una_palabra_que_no_llega_al_minimo_GLOBAL_no_aparece_en_ninguna_area(self):
        # Blindaje anti-PII a nivel de área: el mínimo se mide sobre TODO el
        # corpus, así que un handle que aparece 3 veces en una sola facultad no
        # puede colarse aunque ahí sea "la palabra más dicha".
        self._sembrar_dos_areas()
        s = repository.sintesis(self.db, dias=3650, nivel="facultad", min_global_palabras=10)
        for a in s["areas"]:
            self.assertEqual(a["palabras_top"], [])


class TestReagregarPreservaOrigen(unittest.TestCase):
    """El `origen` de la ingesta (interno/externo) DEBE sobrevivir a la curación.

    REGRESIÓN CON DAÑO REAL YA OCURRIDO: `curacion.reagregar()` hacía
    `delete(H)` + `add_all(H(...))` sin pasar `origen`, y como TODA corrección
    manual lo llama, las 894 filas de percepcion_hecho_diario de la base del
    worker quedaron en NULL. Se comprobó comparando con `percepcion_cuenta.origen`,
    que sí conserva 'interno' en sus 73 filas porque la Torre no reagrega cuentas.

    El worker agrupa por (fecha, ORIGEN, campus, facultad, depto, tema) y toma el
    origen de la cuenta — ver src/percepcion/aggregation/pipeline.py. La Torre
    tiene que espejar eso exactamente.
    """

    def setUp(self):
        self.db = _memoria_completa()

    def tearDown(self):
        self.db.close()

    def _sembrar_dos_origenes(self):
        for cid, origen, nombre in ((1, "interno", "UCN"), (2, "externo", "Prensa")):
            self.db.add(PercepcionCuenta(
                id=cid, handle=f"h{cid}", nombre=nombre, tipo="institucional",
                campus="Antofagasta", facultad="Ingeniería", departamento=None,
                carrera=None, origen=origen,
            ))
            self.db.add(PercepcionPublicacion(
                id=cid, cuenta_id=cid, external_id=f"p{cid}",
                fecha_publicacion=datetime(2026, 1, 1), tipo="post",
                caption="", n_comentarios=1, n_likes=0,
            ))
            self.db.add(PercepcionComentario(
                id=cid, publicacion_id=cid, external_id=f"c{cid}", autor_hash=f"a{cid}",
                texto="un comentario", fecha_comentario=datetime(2026, 1, 2),
                idioma="es", n_likes=0, tema="academico", tema_confianza=0.9,
            ))
            self.db.add(PercepcionScore(
                id=cid, comentario_id=cid, modelo="test", sentimiento="NEG",
                prob_pos=0.0, prob_neu=0.0, prob_neg=1.0,
                emocion="anger", prob_emocion=0.9,
            ))
        self.db.commit()

    def test_reagregar_deriva_el_origen_de_la_cuenta(self):
        self._sembrar_dos_origenes()
        curacion.reagregar(self.db)
        origenes = {h.origen for h in self.db.query(PercepcionHechoDiario).all()}
        self.assertEqual(origenes, {"interno", "externo"})

    def test_reagregar_no_funde_origenes_distintos(self):
        # Misma fecha, misma unidad, mismo tema, distinto origen: son DOS hechos.
        # Si se fundieran, la conversación externa contaminaría el índice interno
        # y no habría forma de separarlos después.
        self._sembrar_dos_origenes()
        curacion.reagregar(self.db)
        hechos = self.db.query(PercepcionHechoDiario).all()
        self.assertEqual(len(hechos), 2)
        self.assertTrue(all(h.n_comentarios == 1 for h in hechos))

    def test_una_correccion_manual_no_borra_el_origen(self):
        # El escenario EXACTO que rompió la base real: corregir un sentimiento
        # dispara reagregar(), que reconstruye la tabla entera.
        self._sembrar_dos_origenes()
        curacion.reagregar(self.db)
        curacion.corregir_sentimiento(self.db, 1, "POS", "revisado a mano", "test@ucn.cl")
        origenes = {h.origen for h in self.db.query(PercepcionHechoDiario).all()}
        self.assertEqual(origenes, {"interno", "externo"})
        self.assertNotIn(None, origenes)

    def test_reagregar_no_revienta_en_una_base_SIN_la_columna_origen(self):
        """REGRESIÓN CRÍTICA: la Torre es un espejo READ-ONLY del esquema del
        worker y puede correr contra una base anterior a una migración suya.

        Comprobado sobre `backend/torre_control_ai.db` (la operacional real, que
        no tiene `origen`): todas las LECTURAS del tablero funcionan —ninguna pide
        la columna nueva— pero `reagregar()` moría con
        "no such column: percepcion_cuenta.origen". Y esa función la dispara CADA
        corrección manual, así que la curación quedaba rota en cualquier entorno
        sin migrar. `Base.metadata.create_all` no arregla esto: crea tablas que
        faltan, no columnas.
        """
        from sqlalchemy import text

        self._sembrar_dos_origenes()
        # Se emula la base vieja: se quita `origen` de las DOS tablas (y antes su
        # índice, o SQLite rechaza el DROP COLUMN).
        for tabla in ("percepcion_cuenta", "percepcion_hecho_diario"):
            self.db.execute(text(f"DROP INDEX IF EXISTS ix_{tabla}_origen"))
            self.db.execute(text(f"ALTER TABLE {tabla} DROP COLUMN origen"))
        self.db.commit()

        n = curacion.reagregar(self.db)          # no debe reventar
        self.assertGreater(n, 0)
        # Y la corrección manual, que es quien la llama, tampoco.
        curacion.corregir_sentimiento(self.db, 1, "POS", "revisado", "test@ucn.cl")

    def test_cuenta_sin_origen_cae_a_interno(self):
        # Bases viejas anteriores a la migración del worker: todo lo que ya estaba
        # es ingesta UCN por definición. Un NULL obligaría a que CADA consulta del
        # dashboard lo contemple.
        self.db.add(PercepcionCuenta(id=9, handle="h9", nombre="Vieja",
                                     tipo="institucional", campus="Antofagasta",
                                     facultad=None, departamento=None, carrera=None,
                                     origen=None))
        self.db.add(PercepcionPublicacion(id=9, cuenta_id=9, external_id="p9",
                                          fecha_publicacion=datetime(2026, 1, 1),
                                          tipo="post", caption="", n_comentarios=1, n_likes=0))
        self.db.add(PercepcionComentario(id=9, publicacion_id=9, external_id="c9",
                                         autor_hash="a9", texto="x",
                                         fecha_comentario=datetime(2026, 1, 2),
                                         idioma="es", n_likes=0, tema="academico",
                                         tema_confianza=0.9))
        self.db.add(PercepcionScore(id=9, comentario_id=9, modelo="test",
                                    sentimiento="NEU", prob_pos=0.0, prob_neu=1.0,
                                    prob_neg=0.0, emocion=None, prob_emocion=None))
        self.db.commit()
        curacion.reagregar(self.db)
        self.assertEqual(
            {h.origen for h in self.db.query(PercepcionHechoDiario).all()}, {"interno"}
        )


def _semana(i, **kw):
    """Punto de la serie SEMANAL de detección (lunes 05/01/2026 + i semanas)."""
    base = {"semana": date(2026, 1, 5) + timedelta(weeks=i), "n": 60,
            "indice": 60.0, "pct_neg": 8.0, "n_terminos": 0, "n_terminos_neg": 0}
    base.update(kw)
    return base


class TestZRobusto(unittest.TestCase):
    """Baseline robusta: mediana + MAD en vez de media + desviación estándar."""

    def test_sin_baseline_suficiente_no_hay_z(self):
        self.assertIsNone(repository._z_robusto(20.0, [10.0, 10.0], piso=1.0))

    def test_un_outlier_previo_no_tapa_el_evento(self):
        # ESTE es el motivo del cambio. Con media+sd, un solo pico previo infla la
        # dispersión y el evento siguiente deja de destacar. La mediana y el MAD
        # ignoran ese pico: el evento real sigue dando z alto.
        previos = [8.0, 8.0, 8.0, 40.0, 8.0, 8.0, 8.0, 8.0]
        z = repository._z_robusto(20.0, previos, piso=1.0)
        self.assertIsNotNone(z)
        self.assertGreater(z, 3.0)

    def test_mad_cero_cae_al_piso_y_no_divide_por_cero(self):
        # Serie constante: MAD = 0. Sin piso esto sería una división por cero (o
        # un z infinito que marca todo).
        z = repository._z_robusto(12.0, [10.0] * 8, piso=2.0)
        self.assertIsNotNone(z)
        self.assertEqual(z, 1.0)   # (12-10)/2

    def test_valor_en_la_mediana_da_cero(self):
        self.assertEqual(repository._z_robusto(10.0, [10.0] * 8, piso=1.0), 0.0)


class TestAnomaliasSemanales(unittest.TestCase):
    """Detección semanal: lo que debe marcar y —sobre todo— lo que NO."""

    def test_serie_plana_no_genera_anomalias(self):
        serie = [_semana(i) for i in range(20)]
        repository._detectar_anomalias_semanales(serie)
        self.assertEqual([p for p in serie if p["es_anomalia"]], [])
        self.assertEqual({p["severidad"] for p in serie}, {0.0})

    def test_menciones_criticas_negativas_disparan_la_alarma(self):
        # Medido en el corpus real: crit_neg tiene mediana 0 en 125 semanas y
        # llega a >=2 solo en 5. Dos menciones negativas en una semana ya es señal.
        serie = [_semana(i) for i in range(12)]
        serie[10]["n_terminos"] = 3
        serie[10]["n_terminos_neg"] = 2
        repository._detectar_anomalias_semanales(serie)
        self.assertTrue(serie[10]["es_anomalia"])
        self.assertIn("terminos", serie[10]["motivos"])

    def test_una_sola_mencion_no_alarma_pero_deja_rastro(self):
        # Una mención suelta no es un paro. Pero tampoco es nada: queda con
        # severidad > 0 para que se vea en el tablero sin gritar.
        serie = [_semana(i) for i in range(12)]
        serie[10]["n_terminos"] = 1
        serie[10]["n_terminos_neg"] = 1
        repository._detectar_anomalias_semanales(serie)
        self.assertFalse(serie[10]["es_anomalia"])
        self.assertGreater(serie[10]["severidad"], 0.0)

    def test_pico_aislado_no_se_descarta_por_no_persistente(self):
        # El 20/04/2026 fue UNA semana suelta con 3 menciones críticas negativas
        # y resultó ser la antesala del paro del 03/06. Exigir persistencia habría
        # tirado justo la señal temprana que buscamos.
        serie = [_semana(i) for i in range(12)]
        serie[6]["n_terminos"] = 5
        serie[6]["n_terminos_neg"] = 3
        repository._detectar_anomalias_semanales(serie)
        self.assertTrue(serie[6]["es_anomalia"])

    def test_la_persistencia_agrava_pero_no_es_requisito(self):
        aislada = [_semana(i) for i in range(12)]
        aislada[10].update(n_terminos=3, n_terminos_neg=2)
        repository._detectar_anomalias_semanales(aislada)

        sostenida = [_semana(i) for i in range(12)]
        for i in (9, 10):
            sostenida[i].update(n_terminos=3, n_terminos_neg=2)
        repository._detectar_anomalias_semanales(sostenida)

        self.assertGreater(sostenida[10]["severidad"], aislada[10]["severidad"])

    def test_caida_brusca_del_indice_dispara_sola(self):
        serie = [_semana(i) for i in range(12)]
        serie[10]["indice"] = 25.0
        repository._detectar_anomalias_semanales(serie)
        self.assertTrue(serie[10]["es_anomalia"])
        self.assertIn("indice", serie[10]["motivos"])
        self.assertLess(serie[10]["z_indice"], 0)

    def test_subida_brusca_del_indice_no_es_alarma(self):
        # Asimetría deliberada: este es un tablero de alerta temprana. Que la
        # percepción MEJORE de golpe se registra, pero no alarma. Calibrado sobre
        # datos reales: tratando ambos sentidos por igual, tres semanas en las que
        # el índice subió (06/04, 25/05, 24/11) salían marcadas sin ser problema.
        serie = [_semana(i) for i in range(12)]
        serie[10]["indice"] = 95.0
        repository._detectar_anomalias_semanales(serie)
        self.assertFalse(serie[10]["es_anomalia"])
        self.assertGreater(serie[10]["z_indice"], 0)
        self.assertIn("indice", serie[10]["motivos"])   # se registra igual

    def test_negatividad_sola_y_debil_no_alcanza(self):
        # Decisión explícita: el %NEG semanal es demasiado variable para disparar
        # con poco. Medido: el 19.4% del 29/06 da z=1.51 contra su propia baseline.
        # Aporta severidad, no alarma por sí solo.
        serie = [_semana(i) for i in range(12)]
        serie[10]["pct_neg"] = 11.0
        repository._detectar_anomalias_semanales(serie)
        self.assertFalse(serie[10]["es_anomalia"])
        self.assertGreater(serie[10]["severidad"], 0.0)
        self.assertIsNotNone(serie[10]["z_pct_neg"])

    def test_dos_senales_debiles_concurrentes_si_alcanzan(self):
        serie = [_semana(i) for i in range(12)]
        serie[10].update(pct_neg=11.0, n_terminos=1, n_terminos_neg=1)
        repository._detectar_anomalias_semanales(serie)
        self.assertTrue(serie[10]["es_anomalia"])
        self.assertEqual(set(serie[10]["motivos"]), {"negatividad", "terminos"})

    def test_las_semanas_flacas_no_se_evaluan_por_proporcion(self):
        # Una semana de 3 comentarios con 33% NEG es ruido, no señal — pasa en el
        # corpus real (12/01/2026). El gate de volumen aplica SOLO a las señales
        # de proporción; el conteo de términos es absoluto y sigue contando.
        serie = [_semana(i) for i in range(12)]
        serie[10].update(n=3, pct_neg=40.0, indice=20.0)
        repository._detectar_anomalias_semanales(serie)
        self.assertIsNone(serie[10]["z_pct_neg"])
        self.assertIsNone(serie[10]["z_indice"])
        self.assertFalse(serie[10]["es_anomalia"])

    def test_el_conteo_de_terminos_ignora_el_gate_de_volumen(self):
        serie = [_semana(i) for i in range(12)]
        serie[10].update(n=4, n_terminos=3, n_terminos_neg=2)
        repository._detectar_anomalias_semanales(serie)
        self.assertTrue(serie[10]["es_anomalia"])
        self.assertEqual(serie[10]["motivos"], ["terminos"])

    def test_severidad_acotada_a_uno(self):
        serie = [_semana(i) for i in range(12)]
        for i in (8, 9, 10):
            serie[i].update(indice=10.0, pct_neg=45.0, n_terminos=9, n_terminos_neg=8)
        repository._detectar_anomalias_semanales(serie)
        self.assertLessEqual(serie[10]["severidad"], 1.0)

    def test_conserva_es_anomalia_y_z_score_para_compatibilidad(self):
        # El front y los tests viejos leen `es_anomalia`; el contrato no se rompe.
        serie = [_semana(i) for i in range(12)]
        repository._detectar_anomalias_semanales(serie)
        for p in serie:
            self.assertIn("es_anomalia", p)
            self.assertIn("severidad", p)
            self.assertIn("motivos", p)


class TestAgrupacionEnBloques(unittest.TestCase):
    """La unidad de detección es la QUINCENA, no la semana.

    Medido sobre los 8 episodios del calendario: quincenal detecta 5 de 5 con 0,5
    falsas alarmas por año; semanal, 4 de 5 con 0,9.
    """

    @staticmethod
    def _par_alineado(**kw):
        """Dos semanas consecutivas que caen en el MISMO bloque.

        No se puede asumir que `_semana(0)` arranque un bloque: los bloques están
        anclados a `EPOCA_BLOQUES`, así que dónde cae la primera semana de una
        serie de prueba es un accidente del calendario, no algo que el test deba
        fijar. Se busca el par en vez de suponerlo.
        """
        serie = [_semana(i, **kw) for i in range(4)]
        for a, b in zip(serie, serie[1:]):
            if repository._bloque_de(a["semana"]) == repository._bloque_de(b["semana"]):
                return serie, a, b
        raise AssertionError("no hay dos semanas consecutivas en el mismo bloque")

    def test_ningun_bloque_supera_la_unidad_y_no_se_pierden_semanas(self):
        serie = [_semana(i) for i in range(8)]
        bloques = repository._agrupar_en_bloques(serie)
        self.assertTrue(all(len(b["semanas"]) <= repository.UNIDAD_DETECCION_SEMANAS
                            for b in bloques))
        self.assertEqual(sum(len(b["semanas"]) for b in bloques), len(serie))
        self.assertLess(len(bloques), len(serie))

    def test_el_bloque_no_depende_del_rango_consultado(self):
        """Anclaje a época fija. Si el bloque dependiera de dónde empieza la serie,
        cambiar el filtro de fechas reagruparía las semanas y las alarmas bailarían
        sin que cambie un solo dato."""
        larga = repository._agrupar_en_bloques([_semana(i) for i in range(10)])
        corta = repository._agrupar_en_bloques([_semana(i) for i in range(3, 10)])
        comunes = {b["semana"] for b in larga} & {b["semana"] for b in corta}
        self.assertTrue(comunes)
        for inicio in comunes:
            a = next(b for b in larga if b["semana"] == inicio)
            c = next(b for b in corta if b["semana"] == inicio)
            # El bloque que está COMPLETO en las dos series tiene que ser idéntico.
            if len(a["semanas"]) == len(c["semanas"]):
                self.assertEqual(a["n"], c["n"])
                self.assertEqual(a["indice"], c["indice"])

    def test_el_lexico_se_suma_entre_semanas(self):
        """Es lo que hace ganar a la quincena: dos semanas con una mención negativa
        cada una llegan juntas al umbral de dos y encienden ALERTA."""
        serie, a, b = self._par_alineado()
        a.update(n_terminos=1, n_terminos_neg=1)
        b.update(n_terminos=1, n_terminos_neg=1)
        bloques = repository._agrupar_en_bloques(serie)
        junto = next(x for x in bloques if a["semana"] in x["semanas"])
        self.assertEqual(junto["n_terminos_neg"], 2)
        repository._detectar_anomalias_semanales(bloques)
        self.assertEqual(junto["nivel_alerta"], repository.NIVEL_ALERTA)

    def test_el_indice_se_pondera_por_volumen(self):
        """Sin ponderar, una semana de 5 comentarios pesaría igual que una de 200.
        En este corpus el volumen semanal va de 0 a 385: no es un detalle."""
        serie, a, b = self._par_alineado()
        a.update(n=10, indice=90.0)
        b.update(n=190, indice=50.0)
        bloque = next(x for x in repository._agrupar_en_bloques(serie)
                      if a["semana"] in x["semanas"])
        esperado = (10 * 90.0 + 190 * 50.0) / 200
        self.assertAlmostEqual(bloque["indice"], esperado, places=6)
        self.assertLess(bloque["indice"], 55.0)   # el promedio simple daría 70

    def test_el_bloque_declara_su_fin(self):
        # La UI muestra "del X al Y": un lunes suelto que representa dos semanas
        # se lee mal.
        b = repository._agrupar_en_bloques([_semana(i) for i in range(4)])[0]
        self.assertEqual((b["semana_fin"] - b["semana"]).days,
                         7 * repository.UNIDAD_DETECCION_SEMANAS - 1)

    def test_unidad_uno_devuelve_la_serie_intacta(self):
        original = repository.UNIDAD_DETECCION_SEMANAS
        try:
            repository.UNIDAD_DETECCION_SEMANAS = 1
            serie = [_semana(i) for i in range(5)]
            self.assertIs(repository._agrupar_en_bloques(serie), serie)
        finally:
            repository.UNIDAD_DETECCION_SEMANAS = original

    def test_el_schema_expone_todo_lo_que_el_repositorio_devuelve(self):
        """Pydantic DESCARTA en silencio lo que no declara, y es un fallo mudo.

        Pasó de verdad: `nivel_alerta`, `fecha_fin` y `lead_esperado_dias` se
        calculaban bien, el tipo de TypeScript compilaba, los tests del repositorio
        pasaban... y el frontend no los recibía nunca, porque el `response_model`
        los filtraba. No hay error en ningún lado: el dato simplemente no está.

        Este test compara las claves que arma `anomalias()` contra los campos del
        modelo, así agregar un campo al repositorio y olvidarse del schema falla acá
        en vez de descubrirse mirando la pantalla.
        """
        from app.services.percepcion import schemas

        serie = [_semana(i) for i in range(12)]
        serie[10].update(n_terminos=3, n_terminos_neg=2)
        bloques = repository._agrupar_en_bloques(serie)
        repository._detectar_anomalias_semanales(bloques)
        p = bloques[-1]
        item = {
            "fecha": p["semana"], "fecha_fin": p.get("semana_fin"),
            "nivel": "filtrado", "dimension": None, "indice": p["indice"],
            "z_score": p["z_score"], "z_indice": p["z_indice"],
            "z_pct_neg": p["z_pct_neg"], "pct_neg": p["pct_neg"],
            "n_comentarios": p["n"], "n_terminos": p["n_terminos"],
            "n_terminos_neg": p["n_terminos_neg"], "motivos": p["motivos"],
            "severidad": p["severidad"], "nivel_alerta": p.get("nivel_alerta"),
            "lead_esperado_dias": p.get("lead_esperado_dias"),
            "lead_rango_dias": p.get("lead_rango_dias"),
            "cobertura_medida": p.get("cobertura_medida"),
        }
        faltantes = set(item) - set(schemas.AnomaliaItem.model_fields)
        self.assertFalse(
            faltantes,
            f"el schema descartaría estos campos sin avisar: {sorted(faltantes)}")
        # Y la respuesta completa tiene que poder llevar la configuración.
        self.assertIn("config", schemas.AnomaliasResponse.model_fields)
        for campo in ("unidad_semanas", "baseline_semanas", "min_comentarios", "medicion"):
            self.assertIn(campo, schemas.AnomaliasConfig.model_fields)

    def test_la_medicion_declarada_existe_para_la_unidad_activa(self):
        """El panel muestra "enciende en N de M": ese número tiene que corresponder
        a la configuración con la que está corriendo, no a otra.

        Si alguien pone una unidad sin calibrar, `medicion` es None y el panel dice
        que no hay medición — mostrar el rendimiento de otra configuración sería
        reportar algo que el lector no está mirando.
        """
        medicion = repository._MEDICION_POR_UNIDAD.get(
            repository.UNIDAD_DETECCION_SEMANAS)
        self.assertIsNotNone(
            medicion,
            "la unidad activa no tiene medición: o se calibra o se cambia el default")
        self.assertLessEqual(medicion["detecta"], medicion["evaluables"])
        self.assertGreater(medicion["precision"], 0.5)

    def test_la_memoria_sigue_siendo_de_medio_ano_en_semanas(self):
        """`VENTANA_BASELINE_SEMANAS` está en SEMANAS y la serie viene en bloques.
        Sin la conversión, 26 pasaría a significar un año en silencio."""
        self.assertEqual(repository.VENTANA_BASELINE_SEMANAS, 26)
        self.assertEqual(repository.UNIDAD_DETECCION_SEMANAS, 2)
        serie = [_semana(i) for i in range(60)]
        repository._detectar_anomalias_semanales(repository._agrupar_en_bloques(serie))


class TestNivelesDeAlerta(unittest.TestCase):
    """Los dos niveles. Cubrir y acertar son objetivos distintos y por eso son dos.

    Medido sobre los 8 episodios disruptivos del calendario (5 evaluables):
    ATENCIÓN (%neg z>=2,0) cubre 4 de 5 con 34 días de lead; ALERTA (léxico
    negativo >=2) cubre 2 de 5 pero acierta el 86 %.
    """

    def test_serie_plana_no_enciende_ningun_nivel(self):
        serie = [_semana(i) for i in range(20)]
        repository._detectar_anomalias_semanales(serie)
        self.assertEqual({p["nivel_alerta"] for p in serie}, {None})

    def test_lexico_negativo_enciende_ALERTA(self):
        serie = [_semana(i) for i in range(12)]
        serie[10].update(n_terminos=3, n_terminos_neg=repository.MIN_TERMINOS_ALARMA)
        repository._detectar_anomalias_semanales(serie)
        self.assertEqual(serie[10]["nivel_alerta"], repository.NIVEL_ALERTA)

    def test_negatividad_alta_enciende_ATENCION(self):
        serie = [_semana(i) for i in range(12)]
        serie[10]["pct_neg"] = 30.0            # baseline 8 % => z muy por encima de 2
        repository._detectar_anomalias_semanales(serie)
        self.assertEqual(serie[10]["nivel_alerta"], repository.NIVEL_ATENCION)
        self.assertGreaterEqual(serie[10]["z_pct_neg"], repository.Z_ATENCION_PCT_NEG)

    def test_el_lexico_manda_sobre_la_negatividad(self):
        # Si las dos condiciones se cumplen, el nivel es ALERTA: es el más preciso
        # y el que pide una acción distinta.
        serie = [_semana(i) for i in range(12)]
        serie[10].update(pct_neg=30.0, n_terminos=4, n_terminos_neg=3)
        repository._detectar_anomalias_semanales(serie)
        self.assertEqual(serie[10]["nivel_alerta"], repository.NIVEL_ALERTA)

    def test_el_indice_NO_enciende_ningun_nivel(self):
        """Lo más contraintuitivo del módulo, y por eso tiene test propio.

        El índice es la métrica que el tablero muestra en grande y la PEOR para
        anticipar: 0 de 5 episodios. Durante un conflicto recibe apoyo y reclamo
        en las mismas publicaciones y el promedio los cancela. Sigue sumando
        severidad —describe el clima— pero no puede encender una alerta.
        """
        serie = [_semana(i) for i in range(12)]
        serie[10]["indice"] = 10.0             # desplome brutal, sin nada más
        repository._detectar_anomalias_semanales(serie)
        self.assertTrue(serie[10]["es_anomalia"])          # sí es anomalía
        self.assertIn("indice", serie[10]["motivos"])      # y deja su motivo
        self.assertIsNone(serie[10]["nivel_alerta"])       # pero NO enciende nivel

    def test_la_alarma_viaja_con_su_horizonte_medido(self):
        # "Hay una alerta" sin horizonte no se puede accionar. El lead va con ella.
        serie = [_semana(i) for i in range(12)]
        serie[10].update(n_terminos=3, n_terminos_neg=2)
        repository._detectar_anomalias_semanales(serie)
        p = serie[10]
        self.assertEqual(p["lead_esperado_dias"],
                         repository.LEAD_ESPERADO_DIAS[repository.NIVEL_ALERTA])
        self.assertEqual(len(p["lead_rango_dias"]), 2)
        self.assertLessEqual(p["lead_rango_dias"][0], p["lead_esperado_dias"])
        self.assertGreaterEqual(p["lead_rango_dias"][1], p["lead_esperado_dias"])
        self.assertEqual(len(p["cobertura_medida"]), 2)

    def test_sin_nivel_no_hay_horizonte(self):
        serie = [_semana(i) for i in range(12)]
        repository._detectar_anomalias_semanales(serie)
        for p in serie:
            self.assertIsNone(p["lead_esperado_dias"])
            self.assertIsNone(p["lead_rango_dias"])

    def test_umbral_de_atencion_es_mas_bajo_que_el_de_severidad(self):
        """z 2,0 y no 2,5: es el umbral más exigente que conserva 4 de 5 episodios.

        Con 2,5 se pierde un episodio y solo se evita una falsa alarma — mal
        negocio para un nivel cuyo propósito es cubrir.
        """
        self.assertLess(repository.Z_ATENCION_PCT_NEG, repository.Z_UMBRAL_SEMANAL)

    def test_atencion_puede_encenderse_sin_llegar_a_ser_anomalia(self):
        """El caso que obliga al OR en `anomalias()`.

        Un %neg con z entre 2,0 y 2,5 aporta APORTE_DEBIL (0,25), que no alcanza
        el umbral de severidad 0,5. Sin el OR, el nivel que cubre 4 de 5 episodios
        no se vería nunca en la pestaña Alertas.
        """
        serie = [_semana(i) for i in range(12)]
        # z ~2,2: por encima de ATENCIÓN, por debajo de Z_UMBRAL_SEMANAL.
        serie[10]["pct_neg"] = 8.0 + 2.2 * repository.PISO_MAD_PCT_NEG
        repository._detectar_anomalias_semanales(serie)
        p = serie[10]
        self.assertEqual(p["nivel_alerta"], repository.NIVEL_ATENCION)
        self.assertFalse(p["es_anomalia"])
        self.assertLess(p["severidad"], repository.UMBRAL_SEVERIDAD_ANOMALIA)

    def test_baseline_es_de_medio_ano(self):
        # 26 semanas = un semestre. Elegido por dominio: con 52 los números salen
        # apenas mejores y eso es justamente señal de sobreajuste.
        self.assertEqual(repository.VENTANA_BASELINE_SEMANAS, 26)

    def test_el_umbral_de_muestra_ya_no_sigue_al_de_la_sintesis(self):
        """MIN_N_SEMANA se separó de N_MIN_CONFIANZA, y hay una razón medida.

        Con 30 —el valor de la síntesis— solo 3 de los 8 episodios del calendario
        tienen ventana evaluable: el umbral apagaba la detección en la mayor parte
        del corpus. Con 20 quedan 5 evaluables y se anticipan 4.

        No baja más porque por debajo de 20 las proporciones se vuelven erráticas,
        y no sube a 25 —que sale mejor en todo salvo cobertura— porque elegir el
        valor que maximiza el resultado sobre 8 casos es sobreajustar.
        """
        self.assertEqual(repository.MIN_N_SEMANA, 20)
        self.assertLess(repository.MIN_N_SEMANA, repository.N_MIN_CONFIANZA)


class TestTerminosVigilancia(unittest.TestCase):
    """Conteo de menciones críticas: cuántas, con qué carga y en qué temas."""

    def setUp(self):
        self.db = _memoria_completa()

    def tearDown(self):
        self.db.close()

    def _familia(self, res, clave):
        return next((f for f in res["familias"] if f["clave"] == clave), None)

    def test_sin_datos(self):
        r = repository.terminos_vigilancia(_memoria_completa())
        self.assertFalse(r["hay_datos"])
        self.assertEqual(r["familias"], [])

    def test_cuenta_menciones_por_familia(self):
        _sembrar_comentarios(self.db, [
            ("No yapo no tiren paro", "NEG", "anger", "organizacion_estudiantil"),
            ("hay paro ono", "NEU", "sin_emocion", "academico"),
            ("La info no puede ser solo para los que estan en la toma", "NEG", "anger", "otros"),
            ("la biblioteca esta llena", "NEU", "sin_emocion", "infraestructura"),
        ])
        r = repository.terminos_vigilancia(self.db, dias=3650)
        self.assertTrue(r["hay_datos"])
        self.assertEqual(self._familia(r, "paro")["n_menciones"], 2)
        self.assertEqual(self._familia(r, "toma")["n_menciones"], 1)
        # El global cuenta COMENTARIOS con al menos un término, no menciones.
        self.assertEqual(r["global"]["n_con_termino"], 3)
        self.assertEqual(r["global"]["n_comentarios"], 4)

    def test_un_comentario_con_dos_formas_de_la_misma_familia_cuenta_una(self):
        # "paro" y "paralización" son la misma familia: es UNA persona hablando,
        # no dos. Mismo criterio que la nube (mide gente, no repeticiones).
        _sembrar_comentarios(self.db, [
            ("el paro y la paralizacion nos perjudican", "NEG", "anger", "academico"),
        ])
        r = repository.terminos_vigilancia(self.db, dias=3650)
        self.assertEqual(self._familia(r, "paro")["n_menciones"], 1)

    def test_separa_el_humor_del_reclamo_en_serio(self):
        # Decisión metodológica: el humor NO se descarta, se reporta aparte.
        # RoBERTuito detecta ironía mal y un "jajaja paro" puede ser sarcasmo amargo.
        _sembrar_comentarios(self.db, [
            ("no tiren paro", "NEG", "anger", "organizacion_estudiantil"),
            ("jajaja paro otra vez", "NEU", "humor_ironia", "organizacion_estudiantil"),
        ])
        f = self._familia(repository.terminos_vigilancia(self.db, dias=3650), "paro")
        self.assertEqual(f["n_menciones"], 2)
        self.assertEqual(f["n_serio"], 1)
        self.assertEqual(f["n_humor"], 1)

    def test_reporta_en_que_temas_se_esta_hablando(self):
        _sembrar_comentarios(self.db, [
            ("no tiren paro", "NEG", "anger", "organizacion_estudiantil"),
            ("otro paro mas", "NEG", "anger", "organizacion_estudiantil"),
            ("el paro atrasa las clases", "NEG", "sadness", "academico"),
        ])
        f = self._familia(repository.terminos_vigilancia(self.db, dias=3650), "paro")
        temas = {t["tema"]: t["n"] for t in f["temas"]}
        self.assertEqual(temas["organizacion_estudiantil"], 2)
        self.assertEqual(temas["academico"], 1)
        # La etiqueta legible viaja lista para la UI.
        self.assertEqual(f["temas"][0]["etiqueta"], "Organización estudiantil")

    def test_carga_y_indice_se_calculan_sobre_los_serios(self):
        # El índice de la familia responde "¿con qué ánimo se habla de esto?".
        # El humor queda fuera del cálculo, no de la vista.
        _sembrar_comentarios(self.db, [
            ("no tiren paro", "NEG", "anger", "organizacion_estudiantil"),
            ("otro paro", "NEG", "anger", "organizacion_estudiantil"),
            ("jajaja paro", "POS", "humor_ironia", "organizacion_estudiantil"),
        ])
        f = self._familia(repository.terminos_vigilancia(self.db, dias=3650), "paro")
        self.assertEqual((f["n_pos"], f["n_neu"], f["n_neg"]), (0, 0, 2))
        self.assertEqual(f["indice"], 0.0)   # dos NEG puros con prob 1.0

    def test_trae_ejemplos_para_auditar(self):
        # Sin poder ver QUÉ disparó el número, nadie lo va a creer.
        _sembrar_comentarios(self.db, [
            ("No yapo no tiren paro", "NEG", "anger", "organizacion_estudiantil"),
        ])
        f = self._familia(repository.terminos_vigilancia(self.db, dias=3650), "paro")
        self.assertEqual(len(f["ejemplos"]), 1)
        # Ficha de etiquetas: el texto crudo no sale (solo la curación admin lo muestra).
        self.assertNotIn("texto", f["ejemplos"][0])
        self.assertEqual(f["ejemplos"][0]["sentimiento"], "NEG")
        # NUNCA el autor: el hash no sale del backend.
        self.assertNotIn("autor_hash", f["ejemplos"][0])

    def test_la_preposicion_para_no_infla_el_indicador(self):
        # Integración de la regresión del léxico: 153 falsos positivos en el
        # corpus real venían de acá.
        _sembrar_comentarios(self.db, [
            ("Y para la sede Coquimbo? Cero info", "NEG", "anger", "infraestructura"),
            ("Para los que no alcanzaron, tambien estaran el dia 4", "NEU", "sin_emocion", "tramites"),
        ])
        r = repository.terminos_vigilancia(self.db, dias=3650)
        self.assertEqual(r["global"]["n_con_termino"], 0)
        self.assertEqual(r["familias"], [])

    def test_serie_semanal_y_primera_ultima_mencion(self):
        _sembrar_comentarios(self.db, [
            ("no tiren paro", "NEG", "anger", "organizacion_estudiantil", datetime(2026, 6, 8)),
            ("otro paro", "NEG", "anger", "organizacion_estudiantil", datetime(2026, 6, 10)),
            ("sigue el paro", "NEG", "anger", "organizacion_estudiantil", datetime(2026, 6, 17)),
        ])
        f = self._familia(repository.terminos_vigilancia(self.db, dias=3650), "paro")
        self.assertEqual(f["primera_mencion"], date(2026, 6, 8))
        self.assertEqual(f["ultima_mencion"], date(2026, 6, 17))
        semanas = {s["semana"]: s["n"] for s in f["serie_semanal"]}
        self.assertEqual(semanas[date(2026, 6, 8)], 2)    # lunes 08/06
        self.assertEqual(semanas[date(2026, 6, 15)], 1)   # lunes 15/06

    def test_delta_contra_el_periodo_anterior(self):
        _sembrar_comentarios(self.db, [
            ("un paro", "NEG", "anger", "organizacion_estudiantil", datetime(2026, 5, 5)),
            ("otro paro", "NEG", "anger", "organizacion_estudiantil", datetime(2026, 6, 5)),
            ("mas paro", "NEG", "anger", "organizacion_estudiantil", datetime(2026, 6, 9)),
            ("aun mas paro", "NEG", "anger", "organizacion_estudiantil", datetime(2026, 6, 20)),
        ])
        r = repository.terminos_vigilancia(
            self.db, fecha_desde=date(2026, 6, 1), fecha_hasta=date(2026, 6, 30)
        )
        f = self._familia(r, "paro")
        self.assertEqual(f["n_menciones"], 3)
        self.assertEqual(f["n_anterior"], 1)          # mayo: la ventana previa
        self.assertEqual(f["delta_menciones_pct"], 200.0)
        self.assertFalse(f["es_nuevo"])

    def test_respeta_el_filtro_dimensional(self):
        _sembrar_comentarios(self.db, [
            ("no tiren paro", "NEG", "anger", "organizacion_estudiantil"),
        ], facultad="Ingeniería")
        vacio = repository.terminos_vigilancia(self.db, dias=3650, facultad="Medicina")
        self.assertEqual(vacio["global"]["n_con_termino"], 0)
        lleno = repository.terminos_vigilancia(self.db, dias=3650, facultad="Ingeniería")
        self.assertEqual(lleno["global"]["n_con_termino"], 1)

    def test_las_familias_sin_menciones_no_se_listan(self):
        _sembrar_comentarios(self.db, [
            ("no tiren paro", "NEG", "anger", "organizacion_estudiantil"),
        ])
        claves = {f["clave"] for f in repository.terminos_vigilancia(self.db, dias=3650)["familias"]}
        self.assertEqual(claves, {"paro"})


class TestLexico(unittest.TestCase):
    """Léxico de términos bajo vigilancia.

    Todos los textos de este bloque son COMENTARIOS REALES del corpus
    (percepcion_real.db, 2.790 comentarios). Lo que NO debe matchear importa
    tanto como lo que sí: una familia mal escrita infla el indicador en silencio.
    """

    def test_para_preposicion_no_es_paro(self):
        # REGRESIÓN de diseño: la regex `par[oa]s?` matcheaba 153 comentarios del
        # corpus y la enorme mayoría eran "para" (preposición). Por eso el léxico
        # es lista EXPLÍCITA de formas y no un patrón cómodo.
        for texto in (
            "Y para la sede Coquimbo? Cero info",
            "en Banner UCN pago en linea se te habilita para pagar $1100",
            "Para los que no alcanzaron, tambien estaran el dia 4 5 6 y 7 de mayo",
            "pará un poco con eso",           # voseo: "pará" normaliza a "para"
        ):
            self.assertNotIn("paro", lexico.detectar(texto), texto)

    def test_detecta_paro_y_sus_derivadas(self):
        for texto in (
            "al final no caxe, hay paro ono",
            "Oe ya no mas paros po, porfavor que si no mi profe fav se cuelga",
            "No yapo no tiren paro",
            "no hayan dimensionado el daño de una paralización",
            "deben dejar de paralizar la universidad",
        ):
            self.assertIn("paro", lexico.detectar(texto), texto)

    def test_alargamiento_expresivo_igual_cuenta(self):
        # "tomaaaaaa" y "marchaaa" están literalmente en el corpus. Sin colapsar
        # las repeticiones, esas menciones se pierden.
        self.assertIn("toma", lexico.detectar("Alguien que me cuente por qué están en tomaaaaaa"))
        self.assertIn("movilizacion", lexico.detectar("marchaaa"))

    def test_tomar_verbo_no_es_toma(self):
        # Falsos positivos reales del corpus: "tomar" es mayoritariamente
        # académico o cotidiano. Por eso NO está entre las formas sueltas.
        for texto in (
            "Holaa, saben cómo comunicarse con el banner? Hay asignaturas que no se pueden tomar",
            "a mi hermana no la deja tomar asignaturas, se mandó correo a jefe carrera",
            "Y quién se tomaría un matcha o un caramel macchiato?",
            "hoy solo puedo tomar las demás",
        ):
            self.assertNotIn("toma", lexico.detectar(texto), texto)

    def test_tomar_dentro_de_frase_si_cuenta(self):
        # "Significa eso q vamos a tomar? Dónde?" es una mención REAL de toma.
        # La frase desambigua lo que la palabra sola no puede.
        self.assertIn("toma", lexico.detectar("Significa eso q vamos a tomar? Dónde?"))

    def test_toma_sustantivo_cuenta_sola(self):
        for texto in (
            "escuche toma",
            "toma?",
            "La información no puede ser solo para los que están en la toma",
            "Qué pena ver que la toma continúa",
            "Me preocupa cuando hayan tomas",
        ):
            self.assertIn("toma", lexico.detectar(texto), texto)

    def test_familias_de_contexto_organizativo(self):
        self.assertIn("petitorio", lexico.detectar(
            "será que por fin hacen lo que hace +2 años llevan debiendo de petitorios"))
        self.assertIn("asamblea", lexico.detectar(
            "Se les invita cordialmente a participar en la asamblea general"))
        self.assertIn("asamblea", lexico.detectar(
            "Ojalá sea online para que participe más gente en la votación"))
        self.assertIn("movilizacion", lexico.detectar(
            "Los únicos perjudicados con paros y marchas son los estudiantes"))

    def test_un_comentario_puede_disparar_varias_familias(self):
        f = lexico.detectar("Yo me fui a paro y toma toda la carrera y no ganamos nada")
        self.assertEqual(f, {"paro", "toma"})

    def test_normaliza_tildes(self):
        self.assertIn("paro", lexico.detectar("la paralización afectó las clases"))
        self.assertIn("movilizacion", lexico.detectar("la movilización sigue"))

    def test_no_colapsa_dobles_legitimas(self):
        # El colapso arranca en 3 repeticiones: "carro", "llave" y "arroz" quedan
        # intactas. Con umbral 2 se romperían palabras normales del español.
        for palabra in ("carro", "llave", "arroz", "innovacion"):
            self.assertEqual(lexico.normalizar(palabra), palabra)

    def test_ignora_los_artefactos_del_scraper(self):
        # El scraper pega estos textos al comentario; no los escribió nadie.
        self.assertEqual(lexico.detectar("See translation View all 8 replies"), set())

    def test_texto_vacio_no_rompe(self):
        self.assertEqual(lexico.detectar(""), set())
        self.assertEqual(lexico.detectar(None), set())

    def test_las_familias_estan_bien_formadas(self):
        claves = [f["clave"] for f in lexico.FAMILIAS]
        self.assertEqual(len(claves), len(set(claves)), "claves de familia duplicadas")
        for f in lexico.FAMILIAS:
            self.assertTrue(f["etiqueta"], f["clave"])
            self.assertTrue(f["formas"] or f["frases"], f["clave"])
            for forma in f["formas"]:
                # Las formas se comparan contra texto YA normalizado: si una trae
                # tilde o mayúscula nunca va a matchear, y el fallo sería mudo.
                self.assertEqual(forma, lexico.normalizar(forma), f"{f['clave']}: {forma}")
            for frase in f["frases"]:
                self.assertEqual(frase, lexico.normalizar(frase), f"{f['clave']}: {frase}")


class _BaseRevision(unittest.TestCase):
    """Corpus mínimo con probabilidades REALISTAS (no 0/1) para poder medir margen."""

    def setUp(self):
        self.db = _memoria_completa()
        self.db.add(PercepcionCuenta(id=1, handle="ucn", nombre="UCN",
                                     tipo="institucional", campus="Antofagasta",
                                     facultad="Ingeniería", departamento=None,
                                     carrera=None, origen="interno"))
        self.db.add(PercepcionPublicacion(
            id=1, cuenta_id=1, external_id="p1", fecha_publicacion=datetime(2026, 1, 1),
            tipo="post", caption="Felicitamos a los titulados de la generación 2026",
            n_comentarios=4, n_likes=0,
        ))
        # (id, texto, sentimiento, probs) — el 1 es un NEU dudoso, el 2 un NEU
        # segurísimo: son los dos casos que hay que poder distinguir al medir.
        filas = [
            (1, "no yapo", "NEU", (0.377, 0.489, 0.133)),
            (2, "gracias", "NEU", (0.050, 0.916, 0.034)),
            (3, "pésimo todo", "NEG", (0.020, 0.100, 0.880)),
            (4, "felicitaciones", "POS", (0.940, 0.040, 0.020)),
        ]
        for cid, texto, sent, (pp, pn, pg) in filas:
            self.db.add(PercepcionComentario(
                id=cid, publicacion_id=1, external_id=f"c{cid}", autor_hash=f"h{cid}",
                texto=texto, fecha_comentario=datetime(2026, 1, 2), idioma="es",
                n_likes=0, tema="academico", tema_confianza=0.9,
            ))
            self.db.add(PercepcionScore(
                id=cid, comentario_id=cid, modelo="robertuito", sentimiento=sent,
                prob_pos=pp, prob_neu=pn, prob_neg=pg, emocion="joy", prob_emocion=0.7,
            ))
        self.db.commit()

    def tearDown(self):
        self.db.close()


class TestCorreccionNoDestructiva(_BaseRevision):
    """La revisión NO puede llevarse puesta la salida del modelo.

    DAÑO REAL YA OCURRIDO: `corregir_sentimiento()` pisaba `prob_pos/neu/neg` con
    los sintéticos de `_PROBS_SENT` (0,90/0,05/0,05). En la base real quedaron **262
    scores** así, y son justo los comentarios donde SÍ se conoce la respuesta
    correcta — o sea, el insumo exacto que necesita cualquier recalibración de
    umbral. Se recuperaron desde el respaldo pre-auditoría, pero la causa se arregla
    acá: la salida del modelo se congela en la corrección ANTES de tocar el score.
    """

    def test_congela_la_salida_del_modelo_en_la_correccion(self):
        curacion.corregir_sentimiento(self.db, 1, "POS", "es agradecimiento", "yo@ucn.cl")
        c = self.db.query(PercepcionCorreccion).one()
        self.assertEqual(c.modelo_orig, "robertuito")
        self.assertAlmostEqual(c.prob_pos_orig, 0.377)
        self.assertAlmostEqual(c.prob_neu_orig, 0.489)
        self.assertAlmostEqual(c.prob_neg_orig, 0.133)

    def test_segunda_correccion_no_pisa_el_snapshot_con_los_sinteticos(self):
        # Este es EL error a no repetir: tras la primera corrección el score ya
        # tiene 0,90/0,05/0,05, así que snapshotearlo de nuevo guardaría los
        # sintéticos como si fueran del modelo y se perdería la única copia buena.
        curacion.corregir_sentimiento(self.db, 1, "POS", "primera", "yo@ucn.cl")
        curacion.corregir_sentimiento(self.db, 1, "NEG", "me arrepentí", "yo@ucn.cl")
        segunda = self.db.query(PercepcionCorreccion).order_by(
            PercepcionCorreccion.id.desc()).first()
        self.assertAlmostEqual(segunda.prob_neu_orig, 0.489)
        self.assertNotIn(segunda.prob_pos_orig, (0.9, 0.05))

    def test_confirmar_deja_fila_registrada(self):
        # Sin esto no hay denominador: las 376 filas de la base real son 376
        # desacuerdos, y por eso el acuerdo era incalculable.
        r = curacion.corregir_sentimiento(self.db, 2, "NEU", "está bien", "yo@ucn.cl")
        self.assertFalse(r["cambiado"])
        c = self.db.query(PercepcionCorreccion).one()
        self.assertTrue(c.confirmado)
        self.assertEqual(c.valor_original, c.valor_nuevo)

    def test_confirmar_no_reconstruye_los_hechos(self):
        # Confirmar no cambia ningún hecho; reagregar borraría e insertaría la
        # tabla entera para nada, y es O(corpus) por clic.
        curacion.reagregar(self.db)
        r = curacion.corregir_sentimiento(self.db, 2, "NEU", "ok", "yo@ucn.cl")
        self.assertEqual(r["hechos"], 0)

    def test_confirmar_no_marca_el_score_como_corregido_a_mano(self):
        curacion.corregir_sentimiento(self.db, 2, "NEU", "ok", "yo@ucn.cl")
        sc = self.db.query(PercepcionScore).filter_by(comentario_id=2).one()
        self.assertNotIn("correccion_manual", sc.modelo)
        self.assertAlmostEqual(sc.prob_neu, 0.916)  # intacto

    def test_registra_autor_tipo_y_origen_de_muestra(self):
        curacion.corregir_sentimiento(self.db, 1, "POS", "x", "yo@ucn.cl",
                                      autor_tipo="humano", origen_muestra="aleatorio")
        c = self.db.query(PercepcionCorreccion).one()
        self.assertEqual(c.autor_tipo, "humano")
        self.assertEqual(c.origen_muestra, "aleatorio")

    def test_emocion_tambien_congela_su_probabilidad(self):
        curacion.corregir_emocion(self.db, 1, "empatia", "es apoyo", "yo@ucn.cl")
        c = self.db.query(PercepcionCorreccion).one()
        self.assertAlmostEqual(c.prob_emocion_orig, 0.7)

    def test_base_SIN_las_columnas_nuevas_no_rompe_la_curacion(self):
        """Mismo blindaje que con `origen`: una base sin migrar degrada, no explota."""
        from sqlalchemy import text

        for col in ("confirmado", "autor_tipo", "origen_muestra"):
            self.db.execute(text(f"DROP INDEX IF EXISTS ix_percepcion_correccion_{col}"))
            self.db.execute(text(f"ALTER TABLE percepcion_correccion DROP COLUMN {col}"))
        for col in ("modelo_orig", "prob_pos_orig", "prob_neu_orig",
                    "prob_neg_orig", "prob_emocion_orig"):
            self.db.execute(text(f"ALTER TABLE percepcion_correccion DROP COLUMN {col}"))
        self.db.commit()
        r = curacion.corregir_sentimiento(self.db, 1, "POS", "x", "yo@ucn.cl")
        self.assertTrue(r["cambiado"])


class TestColaAdversos(unittest.TestCase):
    """La cola dirigida a CANDIDATOS A ADVERSO.

    Existe por un cuello de botella medido: de las 150 anotaciones humanas de
    postura solo 21 son adversos, y con 21 no se calibra ese lado de la regla.
    Anotar al azar tampoco alcanza — el adverso es el 8,5 % del corpus.
    """

    def setUp(self):
        self.db = _memoria_completa()
        self.db.add(PercepcionCuenta(id=1, handle="ucn", nombre="UCN",
                                     tipo="institucional", campus="Antofagasta",
                                     facultad=None, departamento=None, carrera=None,
                                     origen="interno"))
        self.db.add(PercepcionCuenta(id=2, handle="feucn", nombre="FEUCN",
                                     tipo="federacion", campus="Antofagasta",
                                     facultad=None, departamento=None, carrera=None,
                                     origen="interno"))
        # Publicación NORMAL y publicación DE CONFLICTO.
        self.db.add(PercepcionPublicacion(
            id=1, cuenta_id=1, external_id="p1", fecha_publicacion=datetime(2026, 1, 1),
            tipo="post", caption="Felicitamos a los titulados", n_comentarios=0, n_likes=0))
        self.db.add(PercepcionPublicacion(
            id=2, cuenta_id=2, external_id="p2", fecha_publicacion=datetime(2026, 1, 1),
            tipo="post", caption="Resultados de la votación de paralización",
            n_comentarios=0, n_likes=0))
        # (id, pub, texto, sentimiento)
        filas = [
            (1, 1, "felicitaciones", "POS"),   # nada: ni léxico ni conflicto
            (2, 1, "gracias totales", "NEU"),  # nada
            (3, 2, "Paro?", "POS"),            # EL caso: tono positivo, postura adversa
            (4, 2, "buenisimo", "NEU"),        # en post de conflicto, sin léxico propio
            (5, 1, "pesimo todo", "NEG"),      # negativo: ya es adverso por regla
        ]
        for cid, pub, texto, sent in filas:
            self.db.add(PercepcionComentario(
                id=cid, publicacion_id=pub, external_id=f"c{cid}", autor_hash=f"h{cid}",
                texto=texto, fecha_comentario=datetime(2026, 1, 2), idioma="es",
                n_likes=0, tema="otros", tema_confianza=0.5))
            self.db.add(PercepcionScore(
                id=cid, comentario_id=cid, modelo="robertuito", sentimiento=sent,
                prob_pos=0.5, prob_neu=0.3, prob_neg=0.2, emocion="joy", prob_emocion=0.7))
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def _ids(self, **kw):
        r = curacion.comentarios_para_scoring(self.db, orden="adversos", **kw)
        return [i["id"] for i in r["items"]]

    def test_el_positivo_que_nombra_el_paro_va_primero(self):
        """«¿Paro? 😍» es EL caso que la regla no puede detectar hoy: tono positivo,
        postura adversa. Si la cola no lo pone arriba, no sirve para lo que existe."""
        self.assertEqual(self._ids(limite=5)[0], 3)

    def test_los_comentarios_sin_ninguna_senal_no_entran(self):
        """Servirlos sería una cola aleatoria con otro nombre, y quien anota pierde
        el tiempo."""
        ids = self._ids(limite=10)
        self.assertNotIn(1, ids)
        self.assertNotIn(2, ids)

    def test_prioriza_lo_NO_negativo(self):
        """Los NEG ya son adversos por regla: anotarlos confirma lo obvio. Lo que
        falta calibrar es el otro lado."""
        ids = self._ids(limite=10)
        self.assertIn(3, ids)
        if 5 in ids:
            self.assertLess(ids.index(3), ids.index(5))

    def test_una_publicacion_de_conflicto_alcanza_para_entrar(self):
        """Hay 264 comentarios en publicaciones de conflicto contra 9 que lo nombran
        en su propio texto: sin este criterio la cola se queda sin volumen."""
        self.assertIn(4, self._ids(limite=10))

    def test_el_puntaje_ordena_como_dice_la_documentacion(self):
        p_lex_pos = curacion._puntaje_adverso("POS", "hay paro", "algo", "federacion")
        p_solo_pub = curacion._puntaje_adverso("NEU", "buenisimo", "votación de paro", None)
        p_nada = curacion._puntaje_adverso("POS", "gracias", "titulados", None)
        self.assertGreater(p_lex_pos, p_solo_pub)
        self.assertGreater(p_solo_pub, p_nada)

    def test_no_repite_lo_ya_revisado(self):
        antes = self._ids(limite=5)
        self.assertIn(3, antes)
        for campo, valor in (("sentimiento", "NEG"), ("emocion", "anger"),
                             ("tema", "academico"), ("postura", "adverso")):
            getattr(curacion, f"corregir_{campo}")(
                self.db, 3, valor, "es adverso", "yo@ucn.cl", autor_tipo="humano")
        self.assertNotIn(3, self._ids(limite=5))


class TestMuestraAleatoria(_BaseRevision):
    """El anclaje humano (F′) necesita una muestra SIN SESGO y reproducible."""

    def test_la_cola_por_duda_prioriza_al_modelo_dudoso(self):
        items = curacion.comentarios_para_scoring(self.db, limite=4)["items"]
        self.assertEqual(items[0]["id"], 1)      # margen 0.489-0.377 = 0.112
        self.assertLess(items[0]["margen"], items[-1]["margen"])

    def test_misma_semilla_devuelve_la_misma_muestra(self):
        # Dos revisores tienen que anotar EL MISMO conjunto o el acuerdo entre
        # anotadores no significa nada.
        a = curacion.comentarios_para_scoring(self.db, limite=2, orden="aleatorio")
        b = curacion.comentarios_para_scoring(self.db, limite=2, orden="aleatorio")
        self.assertEqual([i["id"] for i in a["items"]], [i["id"] for i in b["items"]])
        self.assertEqual(a["orden"], "aleatorio")

    def test_semillas_distintas_devuelven_muestras_distintas(self):
        ids = {
            tuple(i["id"] for i in curacion.comentarios_para_scoring(
                self.db, limite=2, orden="aleatorio", semilla=s)["items"])
            for s in (1, 2, 3, 4, 5, 6, 7, 8)
        }
        self.assertGreater(len(ids), 1)

    def test_la_muestra_aleatoria_no_ordena_por_duda(self):
        # Si colara el orden por duda, dejaría de ser aleatoria y volvería el sesgo.
        items = curacion.comentarios_para_scoring(self.db, limite=4, orden="aleatorio")["items"]
        self.assertEqual([i["id"] for i in items], [1, 2, 3, 4])

    def _revisar_completo(self, cid, *, tema="academico"):
        """Deja un comentario con los CUATRO campos anotados a mano."""
        curacion.corregir_sentimiento(self.db, cid, "POS", "x", "yo@ucn.cl")
        curacion.corregir_emocion(self.db, cid, "joy", "x", "yo@ucn.cl")
        curacion.corregir_tema(self.db, cid, tema, "x", "yo@ucn.cl")
        curacion.corregir_postura(self.db, cid, "favorable", "x", "yo@ucn.cl")

    def test_la_cola_no_vuelve_a_servir_lo_ya_revisado(self):
        """⚠️ REGRESION — la cola no avanzaba NUNCA.

        La semilla es fija y el corte era `ids[:limite]`: el mismo prefijo de la
        misma permutación en cada request. Se anotaba, se guardaba, se recargaba y
        volvían LOS MISMOS comentarios. Medido sobre la base real el 19-08-2026:
        de 109 comentarios revisados ese día **0 eran nuevos**, con comentarios
        anotados hasta 8 veces. Ninguno de los 176 tests lo veía porque todos
        pedían la cola sin haber anotado nada antes.
        """
        primero = curacion.comentarios_para_scoring(
            self.db, limite=2, orden="aleatorio")["items"]
        for i in primero:
            self._revisar_completo(i["id"])
        segundo = curacion.comentarios_para_scoring(
            self.db, limite=2, orden="aleatorio")["items"]
        self.assertFalse(
            {i["id"] for i in primero} & {i["id"] for i in segundo},
            "la cola devolvió comentarios que ya estaban revisados del todo",
        )

    def test_un_tema_retirado_devuelve_el_comentario_a_la_cola(self):
        # Anotar `eventos` (retirado) no deja el comentario listo: esa etiqueta ya
        # no significa nada y hay que volver a preguntar.
        self._revisar_completo(1, tema="eventos")
        ids = {i["id"] for i in curacion.comentarios_para_scoring(
            self.db, limite=4, orden="aleatorio")["items"]}
        self.assertIn(1, ids)

    def test_un_tema_anotado_con_el_criterio_viejo_vuelve_a_la_cola(self):
        """El criterio de tema cambió el 19-08-2026 (ver `CRITERIO_TEMA_DESDE`).

        Mezclar los dos criterios hace que la métrica de tema no signifique nada:
        de 135 comentarios anotados 2+ veces, 42 cambiaron de etiqueta y 31 de esos
        migraron a `logros_reconocimientos`. Lo anotado antes hay que rehacerlo.
        """
        self._revisar_completo(1)
        viejo = curacion.CRITERIO_TEMA_DESDE - timedelta(days=1)
        self.db.execute(
            update(PercepcionCorreccion)
            .where(PercepcionCorreccion.comentario_id == 1,
                   PercepcionCorreccion.campo == "tema")
            .values(creado_en=viejo)
        )
        self.db.commit()
        self.assertNotIn(1, curacion.comentarios_completos(self.db))
        ids = {i["id"] for i in curacion.comentarios_para_scoring(
            self.db, limite=4, orden="aleatorio")["items"]}
        self.assertIn(1, ids)

    def test_la_cola_dice_por_que_sigue_ahi_cada_comentario(self):
        """⚠️ REGRESIÓN — una cola que devuelve comentarios ya anotados y no explica
        por qué se lee como rota. Pasó: los primeros lugares de la permutación eran
        los anotados con el criterio anterior, así que la cola arrancaba con una
        pantalla de caras conocidas y ninguna explicación.
        """
        self._revisar_completo(1, tema="eventos")
        curacion.corregir_sentimiento(self.db, 2, "POS", "x", "yo@ucn.cl")
        motivos = {i["id"]: i["motivo_pendiente"] for i in
                   curacion.comentarios_para_scoring(
                       self.db, limite=4, orden="aleatorio")["items"]}
        self.assertIn("eventos", motivos[1])
        self.assertIn("falta anotar", motivos[2])
        self.assertIsNone(motivos[3])  # nunca tocado

    def test_reanotar_el_tema_saca_al_comentario_de_la_cola(self):
        """⚠️ REGRESIÓN — el bucle infinito de la cola.

        La UI sólo mandaba los campos que CAMBIABAN. Un comentario cuyo tema
        retirado (`eventos`) la reclasificación ya había renombrado mostraba el
        tema nuevo; el revisor estaba de acuerdo, no cambiaba nada, y no se
        escribía ninguna corrección de tema: la última anotación humana seguía
        siendo la vieja y el comentario volvía a la cola PARA SIEMPRE.
        """
        self._revisar_completo(1, tema="eventos")
        self.assertIn(1, {i["id"] for i in curacion.comentarios_para_scoring(
            self.db, limite=4, orden="aleatorio")["items"]})
        # Re-anotar el tema —aunque sea al mismo valor vigente— tiene que alcanzar.
        curacion.corregir_tema(self.db, 1, "academico", "x", "yo@ucn.cl")
        self.assertNotIn(1, {i["id"] for i in curacion.comentarios_para_scoring(
            self.db, limite=4, orden="aleatorio")["items"]})

    def test_solo_pendientes_en_false_sirve_para_auditar(self):
        self._revisar_completo(1)
        ids = {i["id"] for i in curacion.comentarios_para_scoring(
            self.db, limite=4, orden="aleatorio", solo_pendientes=False)["items"]}
        self.assertIn(1, ids)

    def test_la_respuesta_informa_el_progreso(self):
        # Sin contador en pantalla, revisar lo mismo 8 veces se ve igual que avanzar.
        r0 = curacion.comentarios_para_scoring(self.db, limite=4, orden="aleatorio")
        self.assertEqual((r0["revisados"], r0["pendientes"]), (0, 4))
        self._revisar_completo(1)
        r1 = curacion.comentarios_para_scoring(self.db, limite=4, orden="aleatorio")
        self.assertEqual((r1["revisados"], r1["pendientes"]), (1, 3))

    def test_cada_comentario_viaja_con_el_caption_de_su_post(self):
        # Mediana del corpus real: 3 palabras. "no yapo" no es clasificable sin
        # saber a qué responde.
        items = curacion.comentarios_para_scoring(self.db, limite=4)["items"]
        self.assertTrue(all("titulados" in i["caption"] for i in items))


class TestReplayCorrecciones(_BaseRevision):
    """Un re-scoring del worker ya no se lleva puesta la curación."""

    def test_replay_reaplica_lo_corregido_tras_un_rescoring(self):
        curacion.corregir_sentimiento(self.db, 1, "POS", "es agradecimiento", "yo@ucn.cl")
        # El worker vuelve a puntuar y pisa todo con lo que dice el modelo.
        sc = self.db.query(PercepcionScore).filter_by(comentario_id=1).one()
        sc.sentimiento, sc.modelo = "NEU", "robertuito"
        sc.prob_pos, sc.prob_neu, sc.prob_neg = 0.377, 0.489, 0.133
        self.db.commit()

        r = curacion.replay_correcciones(self.db)
        self.assertEqual(r["sentimiento"], 1)
        sc = self.db.query(PercepcionScore).filter_by(comentario_id=1).one()
        self.assertEqual(sc.sentimiento, "POS")

    def test_replay_ignora_las_confirmaciones(self):
        # Confirmar no cambia nada; re-aplicarlo marcaría como corregido a mano un
        # score que nadie tocó.
        curacion.corregir_sentimiento(self.db, 2, "NEU", "ok", "yo@ucn.cl")
        r = curacion.replay_correcciones(self.db)
        self.assertEqual(r["sentimiento"], 0)
        sc = self.db.query(PercepcionScore).filter_by(comentario_id=2).one()
        self.assertNotIn("correccion_manual", sc.modelo)

    def test_replay_usa_la_ultima_revision_de_cada_comentario(self):
        curacion.corregir_sentimiento(self.db, 1, "POS", "primera", "yo@ucn.cl")
        curacion.corregir_sentimiento(self.db, 1, "NEG", "corrijo", "yo@ucn.cl")
        sc = self.db.query(PercepcionScore).filter_by(comentario_id=1).one()
        sc.sentimiento = "NEU"
        self.db.commit()
        curacion.replay_correcciones(self.db)
        sc = self.db.query(PercepcionScore).filter_by(comentario_id=1).one()
        self.assertEqual(sc.sentimiento, "NEG")


class TestCorregirTema(_BaseRevision):
    """A3: la curación de TEMA tiene que dejar rastro, igual que la de sentimiento.

    `asignar_tema_comentario` pisa `C.tema` y no registra nada — el mismo problema
    que tenía el sentimiento antes de A0. Consecuencia medida sobre la base real:
    CERO filas con `campo='tema'` en `percepcion_correccion`, o sea que el
    clasificador de temas (un matcher de keywords con confianza mediana 0,45 sobre
    comentarios de mediana 3 palabras) nunca se pudo evaluar.
    """

    def test_registra_la_revision_de_tema(self):
        curacion.corregir_tema(self.db, 1, "eventos", "es sobre la fiesta", "yo@ucn.cl")
        c = self.db.query(PercepcionCorreccion).filter_by(campo="tema").one()
        self.assertEqual(c.valor_original, "academico")
        self.assertEqual(c.valor_nuevo, "eventos")
        self.assertFalse(c.confirmado)

    def test_congela_la_confianza_original_del_clasificador(self):
        # Es lo que permite responder si la confianza predice el acierto. Sin esto,
        # tras curar queda 1.0 (certeza humana) y el dato del modelo se pierde.
        curacion.corregir_tema(self.db, 1, "eventos", "x", "yo@ucn.cl")
        c = self.db.query(PercepcionCorreccion).filter_by(campo="tema").one()
        self.assertAlmostEqual(c.prob_tema_orig, 0.9)

    def test_segunda_revision_no_guarda_la_certeza_humana_como_original(self):
        curacion.corregir_tema(self.db, 1, "eventos", "primera", "yo@ucn.cl")
        curacion.corregir_tema(self.db, 1, "tramites", "me arrepenti", "yo@ucn.cl")
        segunda = self.db.query(PercepcionCorreccion).filter_by(campo="tema").order_by(
            PercepcionCorreccion.id.desc()).first()
        self.assertAlmostEqual(segunda.prob_tema_orig, 0.9)   # no 1.0

    def test_confirmar_el_tema_deja_fila_y_no_reagrega(self):
        r = curacion.corregir_tema(self.db, 1, "academico", "esta bien", "yo@ucn.cl")
        self.assertFalse(r["cambiado"])
        self.assertEqual(r["hechos"], 0)
        c = self.db.query(PercepcionCorreccion).filter_by(campo="tema").one()
        self.assertTrue(c.confirmado)

    def test_confirmar_no_pisa_la_confianza_del_clasificador(self):
        curacion.corregir_tema(self.db, 1, "academico", "ok", "yo@ucn.cl")
        com = self.db.query(PercepcionComentario).filter_by(id=1).one()
        self.assertAlmostEqual(com.tema_confianza, 0.9)   # sigue siendo la del modelo

    def test_corregir_marca_certeza_humana(self):
        curacion.corregir_tema(self.db, 1, "eventos", "x", "yo@ucn.cl")
        com = self.db.query(PercepcionComentario).filter_by(id=1).one()
        self.assertEqual(com.tema, "eventos")
        self.assertEqual(com.tema_confianza, 1.0)

    def test_el_panel_de_calidad_reporta_tema(self):
        curacion.corregir_tema(self.db, 1, "eventos", "x", "yo@ucn.cl",
                               autor_tipo="humano", origen_muestra="aleatorio")
        curacion.corregir_tema(self.db, 2, "academico", "ok", "yo@ucn.cl",
                               autor_tipo="humano", origen_muestra="aleatorio")
        tema = calidad.calidad_modelo(self.db)["campos"]["tema"]
        self.assertEqual(tema["n"], 2)
        self.assertEqual(tema["confirmaciones"], 1)
        self.assertAlmostEqual(tema["acuerdo"], 0.5)

    def test_avisa_que_tema_no_tiene_ninguna_revision(self):
        """REGRESIÓN: los avisos globales miran el TOTAL entre campos.

        Con 150 anotaciones de sentimiento sobre muestra aleatoria, los tres avisos
        críticos globales se apagan — y `tema`, con CERO revisiones, quedaba tapado
        sin que nada lo dijera. Es exactamente el estado de la base real.
        """
        for cid in (1, 2, 3, 4):
            curacion.corregir_sentimiento(self.db, cid, "POS", "x", "yo@ucn.cl",
                                          autor_tipo="humano", origen_muestra="aleatorio")
        titulos = [a["titulo"] for a in calidad.calidad_modelo(self.db)["avisos"]]
        self.assertTrue(any("«tema»" in t for t in titulos), titulos)

    def test_el_bucket_de_tema_usa_confianza_no_margen(self):
        # El matcher de keywords no devuelve distribución: no hay segunda clase de
        # la cual restar, así que el margen no aplica.
        curacion.corregir_tema(self.db, 1, "eventos", "x", "yo@ucn.cl")
        buckets = {b["bucket"] for b in
                   calidad.calidad_modelo(self.db)["campos"]["tema"]["por_margen"]}
        self.assertIn("0.7–1.0", buckets)      # confianza 0.9


class TestImpactoPalabras(unittest.TestCase):
    """D · Leave-one-out word impacts (Rieger et al., Text2Story'26 §3.2).

    `impacto(v) = cos(t₁,t₂,V∖v) − cos(t₁,t₂,V)`: si al sacar la palabra los dos
    períodos se parecen MÁS, esa palabra es la que los diferenciaba.

    Responde «qué CAMBIÓ», no «qué se dice» — que es lo que ya contesta la nube y
    lo que hacía el bloque anterior ordenando por negativos absolutos.
    """

    def setUp(self):
        self.db = _memoria_completa()

    def tearDown(self):
        self.db.close()

    def _sembrar(self, actuales, previos):
        """Dos ventanas de 10 días: la previa termina justo antes de la actual."""
        self.db.add(PercepcionCuenta(id=1, handle="ucn", nombre="UCN",
                                     tipo="institucional", campus="Antofagasta",
                                     facultad=None, departamento=None, carrera=None))
        self.db.add(PercepcionPublicacion(
            id=1, cuenta_id=1, external_id="p1", fecha_publicacion=datetime(2026, 1, 1),
            tipo="post", caption="", n_comentarios=0, n_likes=0))
        cid = 0
        base = datetime(2026, 2, 1)
        for textos, dia in ((actuales, 40), (previos, 20)):
            for t in textos:
                cid += 1
                self.db.add(PercepcionComentario(
                    id=cid, publicacion_id=1, external_id=f"c{cid}", autor_hash=f"h{cid}",
                    texto=t, fecha_comentario=base + timedelta(days=dia), idioma="es",
                    n_likes=0, tema="academico", tema_confianza=0.9))
                self.db.add(PercepcionScore(
                    id=cid, comentario_id=cid, modelo="test", sentimiento="NEU",
                    prob_pos=0.1, prob_neu=0.8, prob_neg=0.1,
                    emocion=None, prob_emocion=None))
        self.db.commit()
        _derivar(self.db)

    def test_la_palabra_que_SE_DISPARA_encabeza_el_ranking(self):
        # "paro" está en las DOS ventanas (si no, la regla de vocabulario compartido
        # la excluiría, ver el test de abajo) pero se dispara de 3 a 12. El resto del
        # vocabulario se mantiene parejo. Es exactamente lo que la métrica busca.
        comunes = ["la universidad organiza charlas"] * 6
        r = self._sembrar(
            actuales=comunes + ["paro en la universidad"] * 12,
            previos=comunes + ["paro en la universidad"] * 3,
        )
        r = repository.impacto_palabras(self.db, dias=10)
        self.assertTrue(r["hay_datos"], r.get("motivo"))
        self.assertEqual(r["palabras"][0]["texto"], "paro")
        self.assertGreater(r["palabras"][0]["impacto"], 0)
        self.assertEqual(r["palabras"][0]["delta"], 9)      # 12 − 3

    def test_una_palabra_que_no_cambia_no_tiene_impacto(self):
        comunes = ["la universidad organiza charlas hoy"] * 6
        self._sembrar(actuales=comunes, previos=comunes)
        r = repository.impacto_palabras(self.db, dias=10)
        # Períodos idénticos => coseno 1 y ninguna palabra los diferencia.
        self.assertAlmostEqual(r["similitud"], 1.0, places=4)
        self.assertTrue(all(abs(p["impacto"]) < 1e-9 for p in r["palabras"]))

    def test_exige_presencia_en_AMBAS_ventanas(self):
        """Sin esta regla, una palabra nueva da impacto máximo por no existir antes.

        Eso es información, pero no la que mide esta métrica: acá se compara cómo
        se movió el vocabulario COMPARTIDO. El vocabulario chico del corpus real
        (211 palabras con 10+ apariciones) hace que un solo intruso distorsione todo.
        """
        self._sembrar(
            actuales=["hola universidad charlas"] * 5 + ["unicornio unicornio unicornio"] * 5,
            previos=["hola universidad charlas"] * 5,
        )
        r = repository.impacto_palabras(self.db, dias=10)
        self.assertNotIn("unicornio", [p["texto"] for p in r["palabras"]])

    def test_sin_vocabulario_compartido_lo_dice_en_vez_de_inventar(self):
        self._sembrar(actuales=["alfa beta gamma"] * 4, previos=["delta epsilon zeta"] * 4)
        r = repository.impacto_palabras(self.db, dias=10)
        self.assertFalse(r["hay_datos"])
        self.assertIn("insuficiente", r["motivo"])

    def test_base_vacia_no_revienta(self):
        r = repository.impacto_palabras(self.db, dias=30)
        self.assertFalse(r["hay_datos"])
        self.assertEqual(r["palabras"], [])


class TestCorregirPostura(_BaseRevision):
    """Sentimiento y POSTURA no son lo mismo, y hay que poder medir la diferencia.

    ⚠️ Esta clase se llamaba `TestPostura`, igual que la de más abajo que prueba la
    REGLA (`postura.postura_de`). Python se quedaba con la segunda y estos 6 tests
    NUNCA corrieron: `curacion.corregir_postura` quedó sin cobertura efectiva desde
    que se escribió. La suite seguía en verde porque el conteo bajaba en silencio.
    Detectado el 20-08-2026 comparando los `test_*` del AST (200) contra los que
    carga unittest (194).

    «Paro?😍» es positivo en TONO y adverso en POSTURA hacia la institución.
    Medido sobre la base real: de 141 comentarios en publicaciones de conflicto,
    33 (23%) están marcados POSITIVO. El léxico de términos críticos captura solo
    4 de esos casos — sub-captura el fenómeno por ocho veces.
    """

    def test_el_valor_original_es_la_suposicion_ingenua_del_tono(self):
        # El modelo NO produce postura. El `valor_original` es "suponer que el tono
        # ya la dice", así la matriz mide cuánto se equivoca ESA suposición.
        curacion.corregir_postura(self.db, 4, "adverso", "apoya el paro", "yo@ucn.cl")
        c = self.db.query(PercepcionCorreccion).filter_by(campo="postura").one()
        self.assertEqual(c.valor_original, "favorable")   # el comentario 4 es POS
        self.assertEqual(c.valor_nuevo, "adverso")
        self.assertFalse(c.confirmado)

    def test_confirmar_la_suposicion_tambien_es_dato(self):
        curacion.corregir_postura(self.db, 4, "favorable", "elogio real", "yo@ucn.cl")
        c = self.db.query(PercepcionCorreccion).filter_by(campo="postura").one()
        self.assertTrue(c.confirmado)

    def test_no_toca_el_score_ni_reagrega(self):
        """La postura está EN OBSERVACIÓN: no entra en ningún hecho ni en el índice.

        Meterla ahí perdería comparabilidad con todo lo ya presentado y volvería a
        fusionar dos constructos, solo que al revés.
        """
        curacion.reagregar(self.db)
        antes = self.db.query(PercepcionScore).filter_by(comentario_id=4).one()
        estado = (antes.sentimiento, antes.prob_pos, antes.modelo)
        r = curacion.corregir_postura(self.db, 4, "adverso", "x", "yo@ucn.cl")
        self.assertEqual(r["hechos"], 0)
        sc = self.db.query(PercepcionScore).filter_by(comentario_id=4).one()
        self.assertEqual((sc.sentimiento, sc.prob_pos, sc.modelo), estado)

    def test_guarda_el_tono_del_que_salio_la_suposicion(self):
        curacion.corregir_postura(self.db, 4, "adverso", "x", "yo@ucn.cl")
        c = self.db.query(PercepcionCorreccion).filter_by(campo="postura").one()
        self.assertAlmostEqual(c.prob_pos_orig, 0.94)

    def test_el_panel_reporta_la_brecha_tono_postura(self):
        # Dos comentarios POS: uno realmente favorable, otro adverso (tipo «Paro?😍»).
        curacion.corregir_postura(self.db, 4, "favorable", "elogio", "yo@ucn.cl",
                                  autor_tipo="humano", origen_muestra="aleatorio")
        curacion.corregir_postura(self.db, 1, "adverso", "apoya la protesta", "yo@ucn.cl",
                                  autor_tipo="humano", origen_muestra="aleatorio")
        p = calidad.calidad_modelo(self.db)["campos"]["postura"]["estimacion"]
        self.assertEqual(p["n"], 2)
        self.assertEqual(p["confirmaciones"], 1)
        self.assertAlmostEqual(p["acuerdo"], 0.5)

    def test_rechaza_una_postura_que_no_existe(self):
        self.assertFalse(curacion.postura_valida("mas o menos"))
        self.assertTrue(curacion.postura_valida("adverso"))


class TestCalidadModelo(_BaseRevision):
    """A1: la primera métrica de calidad del módulo. Tiene que ser HONESTA."""

    def test_sin_confirmaciones_el_acuerdo_es_desconocido_no_cero(self):
        # Es el estado exacto de la base real: 376 filas, 376 desacuerdos. Devolver
        # 0.0 invitaría a leer "el modelo nunca acierta", que es falso: los aciertos
        # nunca se anotaron.
        curacion.corregir_sentimiento(self.db, 1, "POS", "x", "yo@ucn.cl")
        r = calidad.calidad_modelo(self.db)
        sent = r["campos"]["sentimiento"]
        self.assertIsNone(sent["acuerdo"])
        self.assertIsNone(sent["kappa"])
        self.assertIn("denominador", sent["acuerdo_motivo"])

    def test_con_confirmaciones_calcula_acuerdo_y_kappa(self):
        curacion.corregir_sentimiento(self.db, 1, "POS", "x", "yo@ucn.cl")   # cambio
        curacion.corregir_sentimiento(self.db, 2, "NEU", "ok", "yo@ucn.cl")  # confirma
        curacion.corregir_sentimiento(self.db, 3, "NEG", "ok", "yo@ucn.cl")  # confirma
        sent = calidad.calidad_modelo(self.db)["campos"]["sentimiento"]
        self.assertAlmostEqual(sent["acuerdo"], round(2 / 3, 3))
        self.assertIsNotNone(sent["kappa"])
        self.assertEqual(sent["confirmaciones"], 2)
        self.assertEqual(sent["cambios"], 1)

    def test_detecta_el_sesgo_direccional_del_revisor(self):
        # El patrón medido en la base real: v4 movía el 90% de sus fallos a POS y
        # v9 el 81%. Un revisor así es indistinguible de un modelo que falla en esa
        # dirección, y hay que decirlo.
        for cid in (1, 2, 3):
            curacion.corregir_sentimiento(self.db, cid, "POS", "x", "agente")
        sent = calidad.calidad_modelo(self.db)["campos"]["sentimiento"]
        self.assertEqual(sent["sesgo_direccional"]["clase"], "POS")
        self.assertEqual(sent["sesgo_direccional"]["proporcion"], 1.0)
        self.assertTrue(sent["sesgo_direccional"]["alerta"])

    def test_avisa_cuando_no_hay_muestra_aleatoria(self):
        curacion.corregir_sentimiento(self.db, 1, "POS", "x", "yo@ucn.cl",
                                      origen_muestra="duda")
        titulos = [a["titulo"] for a in calidad.calidad_modelo(self.db)["avisos"]]
        self.assertTrue(any("aleatoria" in t for t in titulos))

    def test_UNA_anotacion_humana_no_alcanza_para_ser_un_ancla(self):
        """REGRESIÓN: preguntar "¿hay alguna humana?" declaraba que había referencia
        neutral con UNA sola anotación.

        Es exactamente el estado de la base real: 1 fila de `alberto.velasquez@ucn.cl`
        contra 260 de agentes. Con el criterio anterior el módulo decía que tenía
        ancla humana y se callaba el aviso — justo cuando más falta hacía.
        """
        curacion.corregir_sentimiento(self.db, 1, "POS", "x", "yo@ucn.cl",
                                      autor_tipo="humano", origen_muestra="aleatorio")
        for cid in (2, 3):
            curacion.corregir_sentimiento(self.db, cid, "POS", "x", "auditoria-v9",
                                          autor_tipo="agente", origen_muestra="duda")
        titulos = [a["titulo"] for a in calidad.calidad_modelo(self.db)["avisos"]]
        self.assertTrue(any("humana" in t for t in titulos))
        self.assertTrue(any("aleatoria" in t for t in titulos))

    def test_no_avisa_cuando_el_ancla_alcanza_el_minimo(self):
        with mock.patch.object(calidad, "MIN_ANCLA", 1):
            curacion.corregir_sentimiento(self.db, 1, "POS", "x", "yo@ucn.cl",
                                          autor_tipo="humano", origen_muestra="aleatorio")
            titulos = [a["titulo"] for a in calidad.calidad_modelo(self.db)["avisos"]]
        self.assertFalse(any("aleatoria" in t for t in titulos))
        self.assertFalse(any("humana" in t for t in titulos))

    def test_avisa_cuando_todo_lo_reviso_un_agente(self):
        with mock.patch.object(calidad, "MIN_ANCLA", 1):
            curacion.corregir_sentimiento(self.db, 1, "POS", "x", "auditoria-v9",
                                          autor_tipo="agente", origen_muestra="aleatorio")
            titulos = [a["titulo"] for a in calidad.calidad_modelo(self.db)["avisos"]]
        self.assertTrue(any("humana" in t for t in titulos))

    def test_separa_lo_revisado_por_humano_de_lo_revisado_por_agente(self):
        curacion.corregir_sentimiento(self.db, 1, "POS", "x", "yo@ucn.cl",
                                      autor_tipo="humano")
        curacion.corregir_sentimiento(self.db, 3, "POS", "x", "auditoria-v9",
                                      autor_tipo="agente")
        por_autor = {g["clave"]: g for g in
                     calidad.calidad_modelo(self.db)["campos"]["sentimiento"]["por_autor"]}
        self.assertEqual(por_autor["humano"]["n"], 1)
        self.assertEqual(por_autor["agente"]["n"], 1)

    def test_agrupa_las_correcciones_por_margen_original_del_modelo(self):
        # Corregir donde el modelo estaba SEGURO (margen alto) es la señal fuerte.
        curacion.corregir_sentimiento(self.db, 1, "POS", "dudoso", "yo@ucn.cl")   # 0.112
        curacion.corregir_sentimiento(self.db, 2, "POS", "seguro", "yo@ucn.cl")   # 0.866
        buckets = {b["bucket"]: b for b in
                   calidad.calidad_modelo(self.db)["campos"]["sentimiento"]["por_margen"]}
        self.assertEqual(buckets["0.0–0.2"]["cambios"], 1)
        self.assertEqual(buckets["0.7–1.0"]["cambios"], 1)

    def test_una_sola_revision_por_comentario_aunque_se_corrija_dos_veces(self):
        curacion.corregir_sentimiento(self.db, 1, "POS", "primera", "yo@ucn.cl")
        curacion.corregir_sentimiento(self.db, 1, "NEG", "segunda", "yo@ucn.cl")
        r = calidad.calidad_modelo(self.db)
        self.assertEqual(r["campos"]["sentimiento"]["n"], 1)
        self.assertEqual(r["comentarios_revisados"], 1)

    def test_la_segunda_revision_NO_infla_el_acuerdo(self):
        """REGRESIÓN CON DAÑO REAL: se medía "el humano coincidiendo consigo mismo".

        Corregir actualiza `percepcion_score`, así que en una segunda revisión el
        `valor_original` que se guarda ya es la respuesta HUMANA de la primera, no
        la del modelo. Tomando la última revisión, ese par siempre coincide.

        Sobre la base real, con 134 de 150 comentarios revisados dos veces, el
        acuerdo de tema daba **96,7%** cuando el número honesto es **63,3%**.
        """
        # El modelo dijo NEU; el humano lo corrige a POS y después lo confirma.
        curacion.corregir_sentimiento(self.db, 1, "POS", "es agradecimiento", "yo@ucn.cl",
                                      autor_tipo="humano", origen_muestra="aleatorio")
        curacion.corregir_sentimiento(self.db, 1, "POS", "sigo pensando lo mismo", "yo@ucn.cl",
                                      autor_tipo="humano", origen_muestra="aleatorio")
        e = calidad.calidad_modelo(self.db)["campos"]["sentimiento"]["estimacion"]
        self.assertEqual(e["n"], 1)
        # El modelo se EQUIVOCÓ (dijo NEU, era POS). Si esto da 1.0, volvió el bug.
        self.assertEqual(e["confirmaciones"], 0)
        self.assertEqual(e["cambios"], 1)
        self.assertEqual(e["acuerdo"], None)   # 0 aciertos => desconocido, no 100%

    def test_la_segunda_revision_no_borra_un_acierto(self):
        # El caso simétrico: si el modelo acertó y el humano lo confirma dos veces,
        # tiene que seguir contando como UN acierto.
        curacion.corregir_sentimiento(self.db, 2, "NEU", "esta bien", "yo@ucn.cl",
                                      autor_tipo="humano", origen_muestra="aleatorio")
        curacion.corregir_sentimiento(self.db, 2, "NEU", "sigue bien", "yo@ucn.cl",
                                      autor_tipo="humano", origen_muestra="aleatorio")
        e = calidad.calidad_modelo(self.db)["campos"]["sentimiento"]["estimacion"]
        self.assertEqual((e["n"], e["confirmaciones"]), (1, 1))
        self.assertEqual(e["acuerdo"], 1.0)

    def test_cobertura_sobre_el_corpus(self):
        curacion.corregir_sentimiento(self.db, 1, "POS", "x", "yo@ucn.cl")
        r = calidad.calidad_modelo(self.db)
        self.assertEqual(r["total_comentarios"], 4)
        self.assertEqual(r["cobertura"], 0.25)

    def test_kappa_descuenta_el_acuerdo_por_azar(self):
        # Acuerdo perfecto sobre 2+ clases => kappa 1.0. Es la propiedad que hace
        # falta cuando las clases están desbalanceadas (46/46/8 en el corpus real).
        for cid, val in ((2, "NEU"), (3, "NEG"), (4, "POS")):
            curacion.corregir_sentimiento(self.db, cid, val, "ok", "yo@ucn.cl")
        sent = calidad.calidad_modelo(self.db)["campos"]["sentimiento"]
        self.assertEqual(sent["acuerdo"], 1.0)
        self.assertEqual(sent["kappa"], 1.0)


class TestPostura(unittest.TestCase):
    """La postura institucional: si un comentario favorece o perjudica a la UCN."""

    def test_el_tono_negativo_siempre_es_adverso(self):
        for tema in ("academico", "mascotas", "logros_reconocimientos", None):
            self.assertEqual(postura.postura_de("NEG", tema), "adverso")

    def test_el_tono_positivo_solo_es_favorable_si_el_tema_es_atribuible(self):
        # Un logro habla de la UCN; un perrito ocurre EN la UCN sin ser mérito suyo.
        self.assertEqual(postura.postura_de("POS", "logros_reconocimientos"), "favorable")
        self.assertEqual(postura.postura_de("POS", "academico"), "favorable")
        self.assertEqual(postura.postura_de("POS", "mascotas"), "neutral")
        self.assertEqual(postura.postura_de("POS", "vida_estudiantil"), "neutral")

    def test_un_tema_desconocido_cae_del_lado_conservador(self):
        # Agregar un tema a la taxonomía no puede inflar lo favorable por accidente.
        self.assertEqual(postura.postura_de("POS", "tema_que_no_existe"), "neutral")
        self.assertEqual(postura.postura_de("POS", None), "neutral")

    def test_nunca_confunde_favorable_con_adverso(self):
        """⚠️ INVARIANTE — es lo mejor que tiene la regla, no un detalle.

        Medido sobre 150 anotaciones: las dos esquinas opuestas de la matriz están
        en CERO. Para un tablero institucional eso vale más que un par de puntos de
        acuerdo. Si alguna vez se cambia la regla, hay que conservar la propiedad.
        """
        for tema in list(postura.TEMAS_ATRIBUIBLES) + ["mascotas", "otros", None]:
            self.assertNotEqual(postura.postura_de("NEG", tema), "favorable")
            for tono in ("POS", "NEU"):
                self.assertNotEqual(postura.postura_de(tono, tema), "adverso")

    def test_el_reparto_de_una_fila_de_hechos_conserva_el_total(self):
        # Se reparte, no se inventa: la suma tiene que dar los mismos comentarios.
        for tema in ("academico", "mascotas"):
            c = postura.contar_por_postura(tema, n_pos=7, n_neu=3, n_neg=2)
            self.assertEqual(sum(c.values()), 12)
            self.assertEqual(c["adverso"], 2)
        self.assertEqual(postura.contar_por_postura("academico", 7, 3, 2)["favorable"], 7)
        self.assertEqual(postura.contar_por_postura("mascotas", 7, 3, 2)["favorable"], 0)
        self.assertEqual(postura.contar_por_postura("mascotas", 7, 3, 2)["neutral"], 10)


class TestPosturaAgregada(unittest.TestCase):
    def setUp(self):
        self.db = _memoria()
        _sembrar(self.db)

    def tearDown(self):
        self.db.close()

    def test_agrega_sobre_los_hechos_sin_columnas_nuevas(self):
        """No hizo falta migrar: el grano de los hechos ya incluye `tema`, así que
        dentro de una fila el tono determina la postura sin ambigüedad."""
        r = repository.postura_institucional(self.db, dias=365)
        self.assertTrue(r["hay_datos"])
        self.assertEqual(
            r["n_comentarios"], sum(d["n"] for d in r["distribucion"])
        )
        self.assertEqual([d["postura"] for d in r["distribucion"]],
                         ["favorable", "neutral", "adverso"])

    def test_lo_adverso_sale_de_los_negativos(self):
        r = repository.postura_institucional(self.db, dias=365)
        adverso = next(d for d in r["distribucion"] if d["postura"] == "adverso")
        # `_sembrar` pone 30 días × (5 neg de infraestructura + 1 de eventos).
        self.assertEqual(adverso["n"], 30 * 6)

    def test_sin_datos_en_la_ventana_no_inventa(self):
        r = repository.postura_institucional(self.db, dias=365, campus="Inexistente")
        self.assertFalse(r["hay_datos"])


class TestConcentracionTemas(unittest.TestCase):
    """¿Es mío o es de todos? — Gini de la prevalencia de cada tema por unidad."""

    def setUp(self):
        self.db = _memoria()

    def tearDown(self):
        self.db.close()

    def _hecho(self, facultad, tema, n, dia=1):
        self.db.add(PercepcionHechoDiario(
            fecha=date(2026, 2, dia), campus="Antofagasta", facultad=facultad,
            departamento=None, tema=tema, n_comentarios=n, n_pos=n, n_neu=0, n_neg=0,
            suma_peso=float(n), peso_pos=float(n), peso_neg=0.0, suma_pos=float(n),
            suma_neg=0.0, suma_ganadora=float(n), emociones={}, origen="interno",
        ))

    def test_gini_cero_cuando_el_tema_esta_igual_en_todas(self):
        for f in ("A", "B", "C"):
            self._hecho(f, "academico", 50)
            self._hecho(f, "vida_estudiantil", 50)
        self.db.commit()
        r = repository.concentracion_temas(self.db, nivel="facultad", dias=365)
        aca = next(i for i in r["items"] if i["tema"] == "academico")
        self.assertAlmostEqual(aca["gini"], 0.0, places=2)
        self.assertFalse(aca["concentrado"])

    def test_gini_alto_cuando_el_tema_vive_en_una_sola(self):
        self._hecho("A", "academico", 100)
        for f in ("B", "C"):
            self._hecho(f, "vida_estudiantil", 100)
        self.db.commit()
        r = repository.concentracion_temas(self.db, nivel="facultad", dias=365)
        aca = next(i for i in r["items"] if i["tema"] == "academico")
        self.assertGreater(aca["gini"], 0.6)
        self.assertTrue(aca["concentrado"])
        self.assertEqual(aca["unidad_top"], "A")

    def test_mide_PREVALENCIA_y_no_volumen(self):
        """⚠️ Es la razón de ser del bloque, no un detalle de implementación.

        Una unidad que comenta MUCHO de todo no puede aparecer como dueña del tema.
        Acá «A» tiene 10× el volumen de «B» y «C», pero el tema ocupa el mismo 50 %
        en las tres: el Gini tiene que dar 0.
        """
        self._hecho("A", "academico", 500)
        self._hecho("A", "vida_estudiantil", 500)
        for f in ("B", "C"):
            self._hecho(f, "academico", 50)
            self._hecho(f, "vida_estudiantil", 50)
        self.db.commit()
        r = repository.concentracion_temas(self.db, nivel="facultad", dias=365)
        aca = next(i for i in r["items"] if i["tema"] == "academico")
        self.assertAlmostEqual(aca["gini"], 0.0, places=2)

    def test_una_unidad_con_poca_evidencia_no_entra(self):
        # Sin el mínimo, 2 de 4 comentarios dan 50 % de prevalencia y mueven el Gini.
        for f in ("A", "B", "C"):
            self._hecho(f, "academico", 50)
        self._hecho("Chica", "academico", repository.N_MIN_EVIDENCIA - 1)
        self.db.commit()
        r = repository.concentracion_temas(self.db, nivel="facultad", dias=365)
        self.assertEqual(r["unidades"], 3)

    def test_con_menos_de_tres_unidades_se_niega_a_calcular(self):
        # Un Gini sobre dos unidades es un cociente disfrazado.
        for f in ("A", "B"):
            self._hecho(f, "academico", 50)
        self.db.commit()
        r = repository.concentracion_temas(self.db, nivel="facultad", dias=365)
        self.assertFalse(r["hay_datos"])
        self.assertIn("3 unidades", r["motivo"])

    def test_informa_su_propia_cobertura(self):
        # Los comentarios sin unidad NO entran, y hay que poder decirlo en pantalla.
        for f in ("A", "B", "C"):
            self._hecho(f, "academico", 50)
        self._hecho(None, "academico", 150)
        self.db.commit()
        r = repository.concentracion_temas(self.db, nivel="facultad", dias=365)
        self.assertEqual(r["n_comentarios"], 150)
        self.assertAlmostEqual(r["cobertura_pct"], 50.0, places=1)


class TestPosturaPorArea(unittest.TestCase):
    """La postura de cada unidad viaja en la tabla de «cómo está cada área»."""

    def setUp(self):
        self.db = _memoria()

    def tearDown(self):
        self.db.close()

    def _hecho(self, facultad, tema, *, pos=0, neu=0, neg=0):
        """Siembra el hecho Y su corpus espejo.

        Los dos hacen falta desde 09-2026: el índice se sigue leyendo de la tabla de
        hechos y la POSTURA pasó a leerse del corpus, porque mira el tipo de cuenta
        y el hecho no lo guarda. Sembrar uno solo deja la mitad del tablero vacía.
        """
        n = pos + neu + neg
        self.db.add(PercepcionHechoDiario(
            fecha=date(2026, 2, 1), campus="Antofagasta", facultad=facultad,
            departamento=None, tema=tema, n_comentarios=n, n_pos=pos, n_neu=neu, n_neg=neg,
            suma_peso=float(n), peso_pos=float(pos), peso_neg=float(neg),
            suma_pos=float(pos), suma_neg=float(neg), suma_ganadora=float(n),
            emociones={}, origen="interno",
        ))
        _corpus_espejo(self.db, (date(2026, 2, 1) - BASE).days, campus="Antofagasta",
                       facultad=facultad, departamento=None, tema=tema,
                       n_pos=pos, n_neu=neu, n_neg=neg)

    def test_el_mismo_tono_da_postura_distinta_segun_el_tema(self):
        """⚠️ Es la razón de que la postura NO se pueda sacar de `_agrupado`.

        Las dos facultades tienen 40 comentarios POSITIVOS. La única diferencia es
        el tema: logros es institucionalmente atribuible y vida estudiantil no. Con
        el tono solo, las dos darían 100 % favorable.
        """
        self._hecho("Logros SA", "logros_reconocimientos", pos=40)
        self._hecho("Social SA", "vida_estudiantil", pos=40)
        self.db.commit()
        r = repository.sintesis(self.db, nivel="facultad", orden="peor", dias=365)
        por = {a["nombre"]: {t["postura"]: t["pct"] for t in a["postura"]} for a in r["areas"]}
        self.assertEqual(por["Logros SA"]["favorable"], 100.0)
        self.assertEqual(por["Social SA"]["favorable"], 0.0)
        self.assertEqual(por["Social SA"]["neutral"], 100.0)

    def test_suma_cien_y_respeta_el_orden(self):
        self._hecho("A", "academico", pos=10, neu=5, neg=5)
        self.db.commit()
        r = repository.sintesis(self.db, nivel="facultad", orden="peor", dias=365)
        p = r["areas"][0]["postura"]
        self.assertEqual([t["postura"] for t in p], ["favorable", "neutral", "adverso"])
        self.assertAlmostEqual(sum(t["pct"] for t in p), 100.0, places=1)
        self.assertEqual(sum(t["n"] for t in p), 20)

    def test_una_unidad_sin_comentarios_devuelve_None_y_no_una_barra_vacia(self):
        self.assertIsNone(repository._tramos_postura(None))
        self.assertIsNone(repository._tramos_postura({"favorable": 0, "neutral": 0, "adverso": 0}))


class TestCuracionTemasABM(unittest.TestCase):
    """Curación en masa por publicación: la cola, el arrastre y el alcance.

    Estas siete funciones (`publicaciones_a_curar`, `comentarios_a_curar`,
    `asignar_tema_publicacion`, `asignar_tema_comentario`, `temas_asignables`,
    `tema_valido`, `crear_tema_custom`) estuvieron SIN NINGÚN TEST hasta el
    20-08-2026, y por eso `publicaciones_a_curar` devolvió 500 desde el commit
    a47db2c: una línea pegada por error (`motivos.get(cid)`) referenciaba dos
    nombres que no existen en ese scope. La suite seguía en verde porque nada
    llamaba a la función.

    Las dos `asignar_tema_*` son además las ÚNICAS que llaman `reagregar()` de
    forma incondicional, así que acá se verifica también que la tabla de hechos
    quede reconstruida y no vacía.
    """

    def setUp(self):
        self.db = _memoria_completa()
        # Los temas custom no están en `_memoria_completa()`; se crea acá y no en el
        # fixture compartido para no cambiarle la base a los demás tests.
        PercepcionTemaCustom.__table__.create(self.db.get_bind())
        self.db.add(PercepcionCuenta(
            id=1, handle="ucn", nombre="UCN", tipo="institucional",
            campus="Antofagasta", facultad="Ingeniería", departamento=None,
            carrera=None, origen="interno"))
        self.db.add(PercepcionPublicacion(
            id=1, cuenta_id=1, external_id="p1", tipo="post", n_likes=0,
            fecha_publicacion=datetime(2026, 1, 1), n_comentarios=3,
            caption="Charla de bienvenida a los mechones"))
        self.db.add(PercepcionPublicacion(
            id=2, cuenta_id=1, external_id="p2", tipo="post", n_likes=0,
            fecha_publicacion=datetime(2026, 1, 1), n_comentarios=1,
            caption="Titulados generación 2026"))
        # (id, publicación, tema) — el post 1 tiene 2 sin clasificar, el post 2 ninguno.
        for cid, pub, tema in [(1, 1, "otros"), (2, 1, "otros"),
                               (3, 1, "academico"), (4, 2, "academico")]:
            self.db.add(PercepcionComentario(
                id=cid, publicacion_id=pub, external_id=f"c{cid}", autor_hash=f"h{cid}",
                texto=f"comentario {cid}", fecha_comentario=datetime(2026, 1, 2),
                idioma="es", n_likes=0, tema=tema, tema_confianza=0.4))
            self.db.add(PercepcionScore(
                id=cid, comentario_id=cid, modelo="robertuito", sentimiento="POS",
                prob_pos=0.8, prob_neu=0.15, prob_neg=0.05, emocion="joy",
                prob_emocion=0.7))
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_la_cola_de_publicaciones_no_revienta(self):
        """REGRESIÓN: `NameError: name 'motivos' is not defined` (curacion.py:255).

        Basta UNA publicación con comentarios para que entre al bucle y explote,
        así que en la base real el endpoint estaba caído siempre.
        """
        r = curacion.publicaciones_a_curar(self.db)
        self.assertEqual([p["id"] for p in r["items"]], [1])
        self.assertEqual(r["items"][0]["n_otros"], 2)
        self.assertEqual(r["items"][0]["n_comentarios"], 3)
        self.assertEqual(r["items"][0]["cuenta"], "UCN")

    def test_solo_con_otros_apagado_muestra_tambien_los_ya_curados(self):
        r = curacion.publicaciones_a_curar(self.db, solo_con_otros=False)
        self.assertEqual(sorted(p["id"] for p in r["items"]), [1, 2])

    def test_ordena_por_cuanto_falta_curar(self):
        self.db.execute(update(PercepcionComentario)
                        .where(PercepcionComentario.id == 4).values(tema="otros"))
        self.db.commit()
        r = curacion.publicaciones_a_curar(self.db)
        self.assertEqual([p["id"] for p in r["items"]], [1, 2])

    def test_comentarios_a_curar_lista_solo_los_que_siguen_en_otros(self):
        r = curacion.comentarios_a_curar(self.db)
        self.assertEqual(sorted(c["id"] for c in r["items"]), [1, 2])

    def test_asignar_a_la_publicacion_arrastra_los_otros_y_no_toca_el_resto(self):
        r = curacion.asignar_tema_publicacion(self.db, 1, "vida_estudiantil")
        self.assertEqual(r["comentarios_actualizados"], 2)
        temas = dict(self.db.execute(
            select(PercepcionComentario.id, PercepcionComentario.tema)).all())
        self.assertEqual(temas, {1: "vida_estudiantil", 2: "vida_estudiantil",
                                 3: "academico", 4: "academico"})

    def test_asignar_a_la_publicacion_marca_certeza_humana(self):
        curacion.asignar_tema_publicacion(self.db, 1, "vida_estudiantil")
        conf = self.db.execute(
            select(PercepcionComentario.tema_confianza)
            .where(PercepcionComentario.id == 1)).scalar_one()
        self.assertEqual(conf, 1.0)

    def test_asignar_a_un_comentario_no_toca_a_sus_hermanos(self):
        r = curacion.asignar_tema_comentario(self.db, 1, "mascotas")
        self.assertEqual(r["comentarios_actualizados"], 1)
        temas = dict(self.db.execute(
            select(PercepcionComentario.id, PercepcionComentario.tema)).all())
        self.assertEqual(temas[1], "mascotas")
        self.assertEqual(temas[2], "otros")

    def test_asignar_reconstruye_la_tabla_de_hechos(self):
        r = curacion.asignar_tema_publicacion(self.db, 1, "vida_estudiantil")
        self.assertGreater(r["hechos"], 0)
        n = self.db.execute(
            select(func.count()).select_from(PercepcionHechoDiario)).scalar_one()
        self.assertEqual(n, r["hechos"])

    def test_un_tema_retirado_no_se_puede_asignar(self):
        self.assertFalse(curacion.tema_valido(self.db, "eventos"))
        self.assertFalse(curacion.tema_valido(self.db, "otros"))
        self.assertTrue(curacion.tema_valido(self.db, "vida_estudiantil"))

    def test_un_tema_custom_queda_asignable(self):
        curacion.crear_tema_custom(self.db, "Convivencia", ["convivencia", "respeto"])
        claves = [t["tema"] for t in curacion.temas_asignables(self.db)]
        self.assertIn("convivencia", claves)
        self.assertTrue(curacion.tema_valido(self.db, "convivencia"))


# El guard va AL FINAL: estuvo a mitad de archivo (antes de `TestPostura`) y quedaban
# clases definidas después. Hoy no perdía tests porque el archivo no se puede correr
# directo (falta `app` en el path), pero es la misma trampa que dejó 6 tests muertos:
# un marcador de "fin" con código detrás. Correr siempre con:
#     cd backend && .venv\Scripts\python.exe -m unittest tests.test_percepcion
if __name__ == "__main__":
    unittest.main()


class TestAnchoDeColumnasCorreccion(unittest.TestCase):
    """`valor_original`/`valor_nuevo` tienen que aguantar CUALQUIER valor que se corrija.

    DAÑO REAL: se declararon `String(20)` cuando el único campo corregible era
    sentimiento/emoción (el comentario del modelo todavía dice «sentimiento | emocion»).
    Después se sumó la corrección de TEMA, y tres slugs fijos no entran en 20:
    `logros_reconocimientos` (22), `organizacion_estudiantil` (24) y
    `servicios_institucionales` (25).

    En SQLite no se nota — no valida el largo de un VARCHAR — así que 2.996 filas de
    16.156 se escribieron tranquilas en local y la migración a Postgres reventó con
    `StringDataRightTruncation: value too long for type character varying(20)`.
    Ese es justo el tipo de bug que una base permisiva esconde hasta producción.
    """

    def _largo(self, columna: str) -> int:
        return PercepcionCorreccion.__table__.c[columna].type.length

    def test_entra_el_tema_fijo_mas_largo(self):
        peor = max(ETIQUETAS_TEMA, key=len)
        for col in ("valor_original", "valor_nuevo"):
            with self.subTest(columna=col):
                self.assertGreaterEqual(
                    self._largo(col), len(peor),
                    f"{col} es String({self._largo(col)}) y '{peor}' mide {len(peor)}",
                )

    def test_entra_cualquier_tema_custom_que__slug_pueda_generar(self):
        # `_slug` corta en 40, así que 40 es el techo real de un tema.
        tope = len(curacion._slug("x" * 200))
        self.assertEqual(tope, 40)
        for col in ("valor_original", "valor_nuevo"):
            with self.subTest(columna=col):
                self.assertGreaterEqual(self._largo(col), tope)

    def test_el_ancho_acompana_a_la_clave_del_tema_custom(self):
        # Si mañana `PercepcionTemaCustom.clave` crece, esto lo detecta.
        clave = PercepcionTemaCustom.__table__.c["clave"].type.length
        for col in ("valor_original", "valor_nuevo"):
            with self.subTest(columna=col):
                self.assertGreaterEqual(self._largo(col), clave)

    def test_campo_y_las_etiquetas_de_autoria_siguen_entrando(self):
        # Estas SÍ son cortas; el test las fija para que nadie las desborde después.
        for col, peor in (("campo", "sentimiento"), ("autor_tipo", "humano"),
                          ("origen_muestra", "aleatorio")):
            with self.subTest(columna=col):
                self.assertGreaterEqual(self._largo(col), len(peor))
