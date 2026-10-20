"""Laya (System 1 tipado, derivado de Jev) contra el pipeline de TEMA y POSTURA.

VEREDICTO (23-09-2026): no aporta en ninguna de las dos, ni sola ni combinada.
Pero la medicion dejo un hallazgo mas util que el veredicto — ver POSTURA.

                          pipeline   Laya sola   techo oraculo
    tema   (n=171)          0.8304      0.3216        0.9298
    postura (n=491)         0.6171      0.4745        0.7536

TEMA. Laya pierde por 51 puntos. El primer intento dio 36.8% con criterios
largos y sospeche truncamiento: `laya/common.py::build_sequence` reparte 192
tokens de cabecera entre instrucciones y opciones, y con 8 temas cada opcion
cae a (192-16)//8 = 22 tokens. Rehice la prueba con criterios cortos y el
presupuesto VERIFICADO antes de correr (158 tok de opciones, 34 de sobra, sin
truncar). Resultado: 32.2%, o sea PEOR. La hipotesis del truncamiento era
correcta como mecanismo y falsa como explicacion.

La razon real es otra: la taxonomia de temas es un CONSTRUCTO INSTITUCIONAL. La
regla vigente —"un post que DESTACA A UNA PERSONA es `logros_reconocimientos`,
aunque la persona sea academica"— la fijo el dueno del dominio el 19-08-2026 y
cambio 42 de 135 etiquetas al aplicarse. Ningun modelo de proposito general
adivina una convencion decidida en una reunion.

POSTURA, Y ACA ESTA LO IMPORTANTE. Hoy la postura se DERIVA con una regla de
cuatro lineas. Nunca se habia intentado predecirla directamente; Laya lo hace y
da 47.5%, contra el techo de 74.9% que alcanza la regla con tono y tema humanos.

Pero el dato que vale es este: el TECHO ORACULO de combinar el valor guardado
con Laya —un oraculo perfecto eligiendo el mejor de los dos comentario por
comentario— da **75.4%**. Practicamente el mismo 74.9% de la regla con insumos
perfectos. DOS RUTAS COMPLETAMENTE DISTINTAS CONVERGEN EN EL MISMO TECHO.

Eso dice que el ~25% que falta no es un problema de modelo: es que el constructo
`postura` es ambiguo. Dos caminos independientes chocan contra la misma pared.
La consecuencia practica es que la proxima medicion util NO es probar otro
clasificador, es medir el ACUERDO ENTRE DOS ANOTADORES HUMANOS sobre postura. Si
dos personas coinciden cerca del 75%, el techo queda explicado y la pregunta deja
de ser tecnica. `SEMILLA_MUESTRA` en `curacion.py` ya esta fija justamente para
que dos personas reciban los mismos comentarios; falta la segunda persona.

POR QUE TAMPOCO SIRVE COMBINARLOS. El techo oraculo esta 9.9 y 13.6 puntos sobre
el pipeline, asi que los errores SI son complementarios: hay informacion en Laya
que el pipeline no tiene. Pero ningun selector realista la captura. Laya rescata
17 casos de tema que el pipeline falla y rompe 104 que acierta (67 contra 137 en
postura), y delegar en Laya cuando el pipeline tiene poca confianza PIERDE en
todos los umbrales probados (-1.2 a -14.0 en tema, -0.4 a -0.8 en postura). Un
oraculo que no se puede construir no es una mejora.

Es el tercer resultado negativo del modulo en la misma direccion: embeddings
50.7% vs keywords 55.3%; juez LLM 52.3% vs regla de cuatro lineas 90.0%; y ahora
un scorer tipado 32.2% vs 83.0%. En este corpus lo general pierde contra lo
ajustado al dominio.

COMO CORRERLO. `laya` NO esta —ni debe estar— en el venv del backend: arrastra
torch y transformers. Se instala aislado, sin mutar ningun entorno:

    pip install --target <dir> --no-deps laya==0.3.5
    PYTHONPATH=<dir> HF_HOME=<cache> <venv-del-worker>/python.exe \\
        scripts/evaluar_laya_percepcion.py

El venv del worker ya trae torch 2.6.0+cpu y transformers 5.13.1. Todo corre
LOCAL: no sale un solo comentario de la UCN a un servicio externo.
"""
import sqlite3
import time
from collections import Counter

import laya
from laya.common import render_options

DB = "../Sentiment_Analisys_University/percepcion_real.db"

# Criterios CORTOS a proposito: con 8 opciones el presupuesto de cabecera son
# 192 tokens y cada opcion se recorta si no caben. `presupuesto()` lo verifica.
TEMA = {
    "academico": "clases, profesores, notas, carrera, investigacion",
    "vida_estudiantil": "actividades, deporte, musica, ambiente del campus",
    "mascotas": "perros, gatos, animales, adopcion",
    "logros_reconocimientos": "premios, felicitaciones, destacar a alguien",
    "organizacion_estudiantil": "federacion, asamblea, petitorio, paro",
    "bienestar_salud": "salud mental, becas, beneficios, alimentacion",
    "servicios_institucionales": "tramites, matricula, aranceles, salas, wifi",
}
POSTURA = {
    "favorable": "habla bien de la universidad o le reconoce algo",
    "neutral": "ni elogia ni critica a la universidad",
    "adverso": "critica, reclama o se queja de la universidad",
}
INSTR_TEMA = "De que trata este comentario sobre una universidad?"
INSTR_POST = "Que postura tiene este comentario hacia la universidad?"


def kappa(pares):
    n = len(pares)
    po = sum(1 for a, b in pares if a == b) / n
    ca, cb = Counter(a for a, _ in pares), Counter(b for _, b in pares)
    pe = sum(ca[k] / n * cb[k] / n for k in set(ca) | set(cb))
    return (po - pe) / (1 - pe) if pe < 1 else float("nan")


def presupuesto(tok, crit, instr, etiqueta):
    """Verifica que las opciones NO se trunquen. Sin esto se mide otra cosa."""
    opts = render_options({"t": "choice", "ins": instr, "crit": crit})
    total = sum(min(len(tok(" " + o, add_special_tokens=False)["input_ids"]), 48) + 1
                for o in opts)
    sobra = 192 - total
    print(f"  [{etiqueta}] opciones {total} tok · sobran {sobra} -> "
          f"{'OK' if sobra >= 16 else f'SE TRUNCAN a {max(4,(192-16)//len(opts))} tok c/u'}")


def datos(con, campo, extra=""):
    return con.execute(f"""
        SELECT c.texto, k.valor_nuevo, k.valor_original, c.tema_confianza
        FROM percepcion_correccion k
        JOIN percepcion_comentario c ON c.id = k.comentario_id
        WHERE k.campo='{campo}' AND k.autor_tipo='humano' AND k.origen_muestra='aleatorio'
          AND k.valor_nuevo IS NOT NULL AND k.valor_original IS NOT NULL
          AND c.texto IS NOT NULL AND length(trim(c.texto)) > 0 {extra}
    """).fetchall()


def evalua(ag, filas, crit, instr, campo):
    q = {"x": {"type": "choice", "instructions": instr, "criteria": crit}}
    t0 = time.time()
    out = [ag.predict(f[0], q)["answers"]["x"] for f in filas]
    ms = (time.time() - t0) / len(filas) * 1000
    hum, act = [f[1] for f in filas], [f[2] for f in filas]
    lay, conf_a = [o["choice"] for o in out], [f[3] for f in filas]
    n = len(hum)

    a_act = sum(1 for a, h in zip(act, hum) if a == h) / n
    a_lay = sum(1 for l, h in zip(lay, hum) if l == h) / n
    oraculo = sum(1 for a, l, h in zip(act, lay, hum) if a == h or l == h) / n

    print(f"\n{'='*66}\n{campo.upper()}  (n={n})  [{ms:.0f} ms/comentario]")
    print(f"  pipeline actual   {a_act:.4f}")
    print(f"  Laya sola         {a_lay:.4f}   kappa {kappa(list(zip(lay,hum))):+.3f}")
    print(f"  TECHO ORACULO     {oraculo:.4f}   ({(oraculo-a_act)*100:+.1f} pts sobre el actual)")
    print(f"    Laya rescata {sum(1 for a,l,h in zip(act,lay,hum) if a!=h and l==h)} casos · "
          f"romperia {sum(1 for a,l,h in zip(act,lay,hum) if a==h and l!=h)}")

    if any(c is not None for c in conf_a):
        print("  delegar en Laya bajo umbral de confianza del pipeline:")
        for u in (0.3, 0.5, 0.7, 0.9):
            mix = [l if (ca is not None and ca < u) else a
                   for a, l, ca in zip(act, lay, conf_a)]
            am = sum(1 for m, h in zip(mix, hum) if m == h) / n
            k = sum(1 for ca in conf_a if ca is not None and ca < u)
            print(f"    umbral {u:.1f} -> {am:.4f}  ({k} delegados)  {(am-a_act)*100:+.1f} pts")


def main():
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    ag = laya.load("convaiinnovations/laya", subfolder="multilingual")
    tok = getattr(ag, "tok", None) or ag.tokenizer

    print("VERIFICACION DE PRESUPUESTO DE CABECERA")
    presupuesto(tok, TEMA, INSTR_TEMA, "tema")
    presupuesto(tok, POSTURA, INSTR_POST, "postura")

    evalua(ag, datos(con, "tema", " AND k.creado_en >= '2026-08-19'"),
           TEMA, INSTR_TEMA, "tema")
    evalua(ag, datos(con, "postura"), POSTURA, INSTR_POST, "postura")


if __name__ == "__main__":
    main()
