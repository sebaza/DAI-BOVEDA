"""Episode derivation over one person's states (RA06-RA09).

Episode key = (cod_programa, cod_admision, periodo_admision). A key that
reappears after another key forms a new ``tramo`` of the same episode. System
reversal rows (1/2/5) are kept but ignored for episodes and ``tramo_n``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, NamedTuple, Optional, Sequence, Tuple

from .fechas import FechaInfo, impute_dates
from .models import EstadoRow
from .states import EstadoInfo, canonical_order, classify_estado

ADMISION_DESCONOCIDA = "NN"


class EpisodioKey(NamedTuple):
    cod_programa: str
    cod_admision: str
    periodo_admision: Optional[str]


@dataclass(frozen=True)
class EventoDerivado:
    estado: EstadoRow
    orden_canonico: int
    info: EstadoInfo
    es_correccion_sistema: bool
    episodio_key: Optional[EpisodioKey]
    tramo_n: Optional[int]
    cod_admision_imputado: bool
    fecha: FechaInfo


@dataclass
class EpisodioDerivado:
    key: EpisodioKey
    seq: int
    primer_periodo: str
    ultimo_periodo: str
    n_estados: int = 0
    n_tramos: int = 0
    catalogos: Tuple[str, ...] = ()
    catalogo_inicial: Optional[str] = None
    catalogo_final: Optional[str] = None
    ultimo_estado_clase: Optional[str] = None
    cod_admision_imputado: bool = False
    no_contiguo: bool = False


@dataclass
class Timeline:
    events: List[EventoDerivado] = field(default_factory=list)
    episodes: List[EpisodioDerivado] = field(default_factory=list)


def build_timeline(estados: Sequence[EstadoRow], corte: date) -> Timeline:
    ordered = canonical_order(estados)
    fechas = impute_dates(ordered, corte)

    episodes: Dict[EpisodioKey, EpisodioDerivado] = {}
    events: List[EventoDerivado] = []
    current: Optional[EpisodioKey] = None

    for orden, (row, fecha) in enumerate(zip(ordered, fechas), start=1):
        info = classify_estado(row.cod_estado)
        if info.es_correccion_sistema:
            events.append(EventoDerivado(row, orden, info, True, None, None, False, fecha))
            continue

        imputed = not (row.cod_admision or "").strip()
        key = EpisodioKey(row.cod_programa, ADMISION_DESCONOCIDA if imputed else row.cod_admision, row.periodo_admision)

        ep = episodes.get(key)
        if ep is None:
            ep = EpisodioDerivado(key, len(episodes) + 1, row.periodo, row.periodo)
            episodes[key] = ep
        if key != current:
            ep.n_tramos += 1
            if ep.n_tramos > 1:
                ep.no_contiguo = True
            current = key

        ep.n_estados += 1
        ep.primer_periodo = min(ep.primer_periodo, row.periodo)
        ep.ultimo_periodo = max(ep.ultimo_periodo, row.periodo)
        ep.ultimo_estado_clase = info.clase_estado
        ep.cod_admision_imputado = ep.cod_admision_imputado or imputed
        if row.catalogo and row.catalogo not in ep.catalogos:
            ep.catalogos = ep.catalogos + (row.catalogo,)
        if row.catalogo:
            ep.catalogo_inicial = ep.catalogo_inicial or row.catalogo
            ep.catalogo_final = row.catalogo

        events.append(EventoDerivado(row, orden, info, False, key, ep.n_tramos, imputed, fecha))

    return Timeline(events=events, episodes=list(episodes.values()))
