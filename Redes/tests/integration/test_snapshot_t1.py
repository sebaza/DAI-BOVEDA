"""Invariants of the built ``neural_mart.snapshot_t1`` (read only). Skipped without DEV_* or an empty snapshot."""
import os

import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not all(os.environ.get(k) for k in ("DEV_HOST", "DEV_PORT", "DEV_DB", "DEV_USER", "DEV_PASSWORD")),
        reason="DEV_* environment variables not set",
    ),
]


@pytest.fixture(scope="module")
def conn():
    from pipelines.common.db import dev_connection

    with dev_connection() as c:
        with c.cursor() as cur:
            cur.execute("SELECT count(*) FROM neural_mart.snapshot_t1")
            if cur.fetchone()[0] == 0:
                pytest.skip("snapshot_t1 not built (python -m pipelines.snapshots.t1)")
        yield c


def scalar(conn, sql):
    with conn.cursor() as cur:
        cur.execute(sql)
        return cur.fetchone()[0]


def test_label_period_is_strictly_after_the_cutoff_and_two_regular_periods_ahead(conn):
    assert scalar(conn, "SELECT count(*) FROM neural_mart.snapshot_t1 WHERE periodo_horizonte <= periodo_corte") == 0
    assert scalar(conn, """SELECT count(*) FROM neural_mart.snapshot_t1
        WHERE (substr(periodo_horizonte, 1, 4)::int * 2 + (substr(periodo_horizonte, 5, 2) = '20')::int)
            - (substr(periodo_corte, 1, 4)::int * 2 + (substr(periodo_corte, 5, 2) = '20')::int) <> 2""") == 0


def test_censored_and_uncovered_rows_have_no_label_and_observed_rows_have_one(conn):
    assert scalar(conn, """SELECT count(*) FROM neural_mart.snapshot_t1
        WHERE estado_muestra <> 'observada' AND (continua IS NOT NULL OR no_continua_tipo IS NOT NULL
                                                  OR continua_mismo_programa IS NOT NULL)""") == 0
    assert scalar(conn, "SELECT count(*) FROM neural_mart.snapshot_t1 WHERE estado_muestra = 'observada' "
                        "AND continua IS NULL") == 0


def test_every_horizon_of_an_observed_row_is_before_the_latest_period(conn):
    latest = scalar(conn, "SELECT valor FROM neural_mart.snapshot_t1_resumen WHERE clave = 'periodo_maximo'")
    assert scalar(conn, f"SELECT count(*) FROM neural_mart.snapshot_t1 WHERE estado_muestra = 'observada' "
                        f"AND periodo_horizonte >= '{latest}'") == 0
    assert scalar(conn, f"SELECT count(*) FROM neural_mart.snapshot_t1 WHERE estado_muestra = 'censurada' "
                        f"AND periodo_horizonte < '{latest}'") == 0


def test_cutoff_is_a_regular_period_and_k_matches_the_admission(conn):
    assert scalar(conn, "SELECT count(*) FROM neural_mart.snapshot_t1 WHERE substr(periodo_corte, 5, 2) NOT IN ('10', '20')") == 0
    assert scalar(conn, """SELECT count(*) FROM neural_mart.snapshot_t1
        WHERE (substr(periodo_corte, 1, 4)::int * 2 + (substr(periodo_corte, 5, 2) = '20')::int)
            - (substr(periodo_admision, 1, 4)::int * 2 + (substr(periodo_admision, 5, 2) >= '20')::int) + 1 <> k""") == 0


def test_features_never_look_past_the_cutoff_slots(conn):
    # a slot j > k can exist in the semester table, but a snapshot row of k only aggregates slots <= k:
    # its attempts are a subset of the slots 1..k totals
    assert scalar(conn, """SELECT count(*) FROM neural_mart.snapshot_t1 s
        JOIN (SELECT episodio_id, j, sum(intentos_evaluados) OVER (PARTITION BY episodio_id ORDER BY j) AS acum
              FROM neural_mart.snapshot_t1_semestre) t ON t.episodio_id = s.episodio_id AND t.j = s.k
        WHERE t.acum <> s.intentos_evaluados""") == 0


def test_split_follows_the_cohort_year_and_population_is_undergraduate(conn):
    assert scalar(conn, """SELECT count(*) FROM neural_mart.snapshot_t1
        WHERE split <> CASE WHEN cohorte_anio <= 2019 THEN 'train' WHEN cohorte_anio <= 2021 THEN 'valid'
                            WHEN cohorte_anio <= 2023 THEN 'test' ELSE 'posterior' END""") == 0
    assert scalar(conn, """SELECT count(*) FROM neural_mart.snapshot_t1 s
        JOIN neural_core.episodio_programa e USING (episodio_id)
        JOIN neural_core.programa p ON p.cod_programa = e.cod_programa
        WHERE p.id_nivel <> 1 OR e.cod_admision IN ('IN', 'PE', 'IE')""") == 0


def test_snapshot_rows_are_unique_per_episode_and_k_and_sex_is_not_a_feature_column_name(conn):
    assert scalar(conn, "SELECT count(*) FROM (SELECT 1 FROM neural_mart.snapshot_t1 GROUP BY episodio_id, k "
                        "HAVING count(*) > 1) t") == 0
    pytest.importorskip("pandas")
    from models import data as D

    assert "sexo_equidad" not in set(D.PRE_NUM + D.PRE_CAT + D.ACAD_NUM)
