"""Assign a grade row to an episode by program and period range (R36)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

from .timeline import EpisodioDerivado, EpisodioKey


@dataclass(frozen=True)
class EpisodeAssignment:
    episodio_key: Optional[EpisodioKey]
    episodio_ambiguo: bool
    sin_episodio: bool


def assign_episode(periodo: str, cod_carrera: str, episodes: Sequence[EpisodioDerivado]) -> EpisodeAssignment:
    """One candidate -> assigned. Zero -> ``sin_episodio``. Two or more -> ambiguous, not picked."""
    candidates = [
        e for e in episodes
        if e.key.cod_programa == cod_carrera and e.primer_periodo <= periodo <= e.ultimo_periodo
    ]
    if len(candidates) == 1:
        return EpisodeAssignment(candidates[0].key, False, False)
    if not candidates:
        return EpisodeAssignment(None, False, True)
    return EpisodeAssignment(None, True, False)
