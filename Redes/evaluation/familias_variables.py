"""Plain-language families of the input columns of the kept models (T1 ``cb_acad`` / ``lr_acad``, T2 ``cb_c_nuevas``, T5 ``gru_adm`` /
``gru_agg``), used by the permutation importance of "Cómo decide el modelo".

``FAMILIA`` maps every input column to a family id; ``ETIQUETA_FAMILIA`` gives the label shown to vice-rectors (no technical jargon).
The sequence channels of the T3 / T5 networks are keyed ``seq:<channel>`` (the same family as the static columns they echo).
Sex is never an input of any model (decision M1), so no family names it.
"""
from __future__ import annotations

from typing import Dict, List

ETIQUETA_FAMILIA: Dict[str, str] = {
    "puntajes_admision": "Puntajes de admisión",
    "forma_ingreso": "Forma de ingreso a la universidad",
    "colegio": "Colegio de origen",
    "carrera_sede": "Carrera y sede",
    "plan_estudios": "Plan de estudios de la carrera",
    "anio_ingreso": "Año de ingreso",
    "notas_acumuladas": "Notas acumuladas",
    "notas_ultimo_semestre": "Notas del último semestre",
    "reprobaciones": "Reprobaciones acumuladas",
    "avance_creditos": "Avance en créditos",
    "convalidaciones": "Convalidaciones y cursos de verano o invierno",
    "matricula_interrupciones": "Matrícula e interrupciones de estudios",
    "carga_semestre": "Carga de ramos del semestre",
    "dificultad_ramo": "Dificultad histórica del ramo y su departamento",
    "intentos_previos_ramo": "Intentos anteriores del mismo ramo",
    "prerrequisitos": "Prerrequisitos del ramo",
    "posicion_malla": "Posición en la malla de la carrera",
}

_POR_FAMILIA: Dict[str, List[str]] = {
    "puntajes_admision": ["mm_leng", "mm_mat", "mm_ciencias", "mm_historia", "mm_nem", "mm_ranking", "mm_notas_em", "mm_ponderado"],
    "forma_ingreso": ["via_clase", "cod_admision", "preferencia", "con_postulacion", "prueba_admision"],
    "colegio": ["tipo_colegio", "depend_colegio", "region_colegio"],
    "carrera_sede": ["cod_programa", "sede"],
    "plan_estudios": ["duracion_nominal", "creditos_malla_total", "malla_conocida", "trayectoria_plan_comun",
                      "especialidad_conocida_al_corte"],
    "anio_ingreso": ["cohorte_anio"],
    "notas_acumuladas": ["promedio_evaluado", "n_notas_promedio", "prom_acum", "n_notas_acum"],
    "notas_ultimo_semestre": ["intentos_ult_semestre", "tasa_ult_semestre", "promedio_ult_semestre", "prom_sem_prev", "tasa_sem_prev"],
    "reprobaciones": ["intentos_evaluados", "aprobados", "reprobados", "tasa_aprobacion", "n_reprob_acum", "n_intentos_acum",
                      "tasa_aprob_acum"],
    "avance_creditos": ["creditos_aprobados", "creditos_aprob_acum", "creditos_esperados", "avance_malla", "fraccion_malla",
                        "semestres_matriculados", "sem_matriculados", "seq:creditos_aprobados", "seq:creditos_acumulados"],
    "convalidaciones": ["convalidaciones", "cursos_verano_invierno", "seq:convalidaciones", "seq:cursos_verano_invierno"],
    "matricula_interrupciones": ["n_interrupcion", "cambios_catalogo", "seq:matriculado", "seq:interrupcion"],
    "carga_semestre": ["n_cursos_carga", "creditos_carga", "n_repetidos_carga", "tasa_hist_media_carga"],
    "dificultad_ramo": ["creditos", "formacion", "depto", "tasa_hist_curso", "n_hist_curso", "prom_hist_curso", "tasa_hist_curso_suav",
                        "tasa_hist_curso_prog", "n_hist_curso_prog", "prom_depto", "n_depto", "dif_prom_depto"],
    "intentos_previos_ramo": ["oportunidad", "n_prev_curso", "mejor_nota_prev_curso", "aprobo_antes_curso"],
    "prerrequisitos": ["info_prereq", "n_prereq", "n_prereq_aprob", "n_prereq_conva", "n_prereq_pend_reprob", "n_prereq_en_carga",
                       "min_nota_prereq", "mean_nota_prereq"],
    "posicion_malla": ["k", "sem_malla", "en_malla", "desfase"],
}

FAMILIA: Dict[str, str] = {col: fam for fam, cols in _POR_FAMILIA.items() for col in cols}


def agrupar(columnas) -> Dict[str, List[str]]:
    """``{familia: [columnas del modelo]}`` for the given input columns; a column without a family is an error (never silently dropped)."""
    sin = [c for c in columnas if c not in FAMILIA]
    if sin:
        raise KeyError(f"input columns without a family: {sorted(sin)}")
    out: Dict[str, List[str]] = {}
    for c in columnas:
        out.setdefault(FAMILIA[c], []).append(c)
    return out
