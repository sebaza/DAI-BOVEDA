"""Pure helpers of the Neural API (no database): transfer types, the balance of a program, the «pocos casos» mark and field
whitelists. Nothing here hides data: the API serves the marts as stored and only marks small groups."""
from __future__ import annotations

POCOS_CASOS = 10            # a group of fewer people than this carries the «pocos casos» mark (a mark, never a filter)


def pocos_casos(n: int | None) -> bool:
    """Is this group small enough to carry the «pocos casos» mark? Unknown sizes are not marked."""
    return n is not None and n < POCOS_CASOS


# --------------------------------------------------------------------------- #
# Transfers between programs (P61): meaning of each type and balance of a program
# --------------------------------------------------------------------------- #
TIPOS_TRASLADO: dict[str, dict] = {
    "eleccion_especialidad": {
        "etiqueta": "Elección de especialidad", "cuenta_abandono": False,
        "descripcion": "Paso de un plan común (p. ej. Ingeniería Civil Plan Común) a una especialidad. No es una "
                       "pérdida del programa de origen."},
    "cambio_ciclo": {
        "etiqueta": "Cambio de ciclo", "cuenta_abandono": False,
        "descripcion": "El último estado del programa de origen es «Cambio de ciclo» (D) y la persona sigue en otro programa."},
    "continuacion_estudios": {
        "etiqueta": "Continuación tras egreso o titulación", "cuenta_abandono": False,
        "descripcion": "La persona egresó o se tituló del programa de origen y luego ingresa a otro: completó el ciclo."},
    "cambio_carrera": {
        "etiqueta": "Cambio de carrera", "cuenta_abandono": True,
        "descripcion": "Ingreso al programa de destino con la vía «Cambio de Carrera» (CC). Cuenta como abandono del origen."},
    "traslado_sede": {
        "etiqueta": "Cambio de sede", "cuenta_abandono": True,
        "descripcion": "Ingreso al programa de destino con la vía «Cambio de Sede» (CS). Cuenta como salida del programa de origen."},
    "traslado_otro": {
        "etiqueta": "Otro traslado", "cuenta_abandono": True,
        "descripcion": "Pasa a otro programa por cualquier otra vía (p. ej. nueva postulación). Cuenta como abandono del origen."},
}


def balance_programa(ganados: int, ganados_eleccion: int, perdidos: int, perdidos_eleccion: int) -> dict:
    """Gained / lost / net of one program, with and without specialty elections (every count as stored)."""
    sin_g, sin_p = ganados - ganados_eleccion, perdidos - perdidos_eleccion
    return {
        "ganados_total": ganados, "perdidos_total": perdidos, "neto_total": ganados - perdidos,
        "ganados_sin_eleccion": sin_g, "perdidos_sin_eleccion": sin_p, "neto_sin_eleccion": sin_g - sin_p,
    }


# --------------------------------------------------------------------------- #
# View "Lo que pasó": blocks copied field by field (a key outside the schema never goes through)
# --------------------------------------------------------------------------- #
def _etiquetas_modelo(b: dict | None) -> dict:
    """Model label of a block that describes the model, not a population: ``aplica_a_poblacion`` is always False."""
    b = b or {}
    return {"aplica_a_poblacion": False, "modelo": b.get("modelo"), "modelos": b.get("modelos")}


def campos_senales(b: dict | None) -> dict | None:
    """Signals the models rely on: percentages of importance, no counts. Rows are copied field by field."""
    tareas = [{"tarea": t["tarea"], "k": t["k"], "modelo": t["modelo"], "n_muestra": t["n_muestra"],
               "senales": [{"familia": s["familia"], "etiqueta": s["etiqueta"], "peso_pct": s["peso_pct"], "caida_ap": s["caida_ap"]}
                           for s in t.get("senales") or []]}
              for t in (b or {}).get("tareas") or []]
    return {"tareas": tareas, **_etiquetas_modelo(b)} if tareas else None


def campos_esperar(b: dict | None) -> dict | None:
    """Wait one semester: how many of every ten who leave the model reaches, before and after. Rates only, copied field by field."""
    comps = [{"tarea": c["tarea"], "k_antes": c["k_antes"], "k_despues": c["k_despues"],
              "de_cada_10_antes": c.get("de_cada_10_antes"), "de_cada_10_despues": c.get("de_cada_10_despues")}
             for c in (b or {}).get("comparaciones") or []]
    return {"comparaciones": comps, "nota_poblaciones": bool((b or {}).get("nota_poblaciones", True)),
            **_etiquetas_modelo(b)} if comps else None
