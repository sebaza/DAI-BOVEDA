-- DAI Neural 018: point-in-time snapshot of task T6 ("matricula en postgrado UCN despues del egreso",
-- docs/12_benchmark_t6.md). Rebuilt as a whole by `python -m pipelines.snapshots.t6`. One row per T3 trajectory (D47) that
-- reached egreso in a closed regular period; the cut is the egreso semester (`semestres_a_egreso` = its slot). Features use
-- only facts of the slots <= the cut; the label is the time, in calendar semesters after the egreso, to the first semester
-- in which the person is ENROLLED in a UCN postgrado program (`evento` = 1) or the follow-up until the last closed period
-- (`evento` = 0, `seguimiento`). Persons already enrolled in a postgrado program at or before the egreso semester are not in
-- the table (they are counted in the summary table). Only UCN postgrado enrollment is observable. Pseudonymous keys only.
-- `sexo_equidad` exists for fairness evaluation and is NEVER a model feature (decision M1); `cohorte_anio` and `anio_egreso`
-- only define the split and the subgroup tables. `episodio_especialidad_id` is the audit trail of the Plan Comun link.
-- `*_cualquier_fila` is a sensitivity label (any postgrado row, enrolled or not). Idempotent: safe to run more than once.

CREATE TABLE IF NOT EXISTS neural_mart.snapshot_t6 (
    episodio_id              bigint   NOT NULL PRIMARY KEY,
    persona_key              text     NOT NULL,
    cod_programa             text     NOT NULL,
    periodo_admision         text     NOT NULL,
    cohorte_anio             integer  NOT NULL,
    anio_egreso              integer  NOT NULL,
    split                    text     NOT NULL CHECK (split IN ('train', 'valid', 'test')),
    -- label (calendar semesters after the egreso)
    seguimiento              smallint NOT NULL CHECK (seguimiento >= 1),
    tiempo                   smallint NOT NULL CHECK (tiempo >= 1),
    evento                   smallint NOT NULL CHECK (evento IN (0, 1)),
    tiempo_cualquier_fila    smallint NOT NULL CHECK (tiempo_cualquier_fila >= 1),
    evento_cualquier_fila    smallint NOT NULL CHECK (evento_cualquier_fila IN (0, 1)),
    episodio_especialidad_id bigint,
    -- pre-entry
    via_clase                text,
    cod_admision             text,
    sede                     text,
    tipo_colegio             text,
    depend_colegio           text,
    region_colegio           text,
    preferencia              real,
    con_postulacion          boolean  NOT NULL,
    pct_leng                 real,
    pct_mat                  real,
    pct_ciencias             real,
    pct_historia             real,
    pct_nem                  real,
    pct_ranking              real,
    pct_notas_em             real,
    pct_ponderado            real,
    -- program in force at the cut
    duracion_nominal         real,
    creditos_malla_total     real,
    malla_conocida           boolean  NOT NULL,
    trayectoria_plan_comun   boolean  NOT NULL,
    especialidad_conocida_al_corte boolean NOT NULL,
    -- academic record up to the cut
    creditos_aprobados       real     NOT NULL,
    intentos_evaluados       integer  NOT NULL,
    aprobados                integer  NOT NULL,
    reprobados               integer  NOT NULL,
    tasa_aprobacion          real,
    promedio_evaluado        real,
    n_notas_promedio         integer  NOT NULL,
    convalidaciones          integer  NOT NULL,
    cursos_verano_invierno   integer  NOT NULL,
    n_interrupcion           integer  NOT NULL,
    cambios_catalogo         integer  NOT NULL,
    semestres_matriculados   integer  NOT NULL,
    intentos_ult_semestre    integer  NOT NULL,
    tasa_ult_semestre        real,
    promedio_ult_semestre    real,
    creditos_esperados       real,
    avance_malla             real,
    fraccion_malla           real,
    n_sem_sin_reprobacion    smallint NOT NULL,
    -- the egreso itself
    semestres_a_egreso       smallint NOT NULL CHECK (semestres_a_egreso >= 1),
    exceso_duracion          real,
    razon_duracion           real,
    titulado_al_corte        boolean  NOT NULL,
    -- fairness only (never a feature)
    sexo_equidad             text
);

CREATE INDEX IF NOT EXISTS snapshot_t6_split_ix ON neural_mart.snapshot_t6 (split);

CREATE TABLE IF NOT EXISTS neural_mart.snapshot_t6_resumen (
    clave   text PRIMARY KEY,
    valor   text NOT NULL,
    nota    text
);
