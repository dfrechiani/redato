"""Modos REJ 1S — Foco C3/C4/C5 + Completo Parcial (OF13).

Spec: docs/redato/v3/redato_1S_criterios.md.

Os modos Foco e Completo Parcial são novos pipelines com schema, prompt e
detectores próprios. O modo Completo Integral (OF14) continua usando o
pipeline v2 da Redato em produção, com apenas uma injeção de contexto da
oficina no user_msg.
"""
from redato_backend.missions.router import (
    MissionMode,
    resolve_mode,
    grade_mission,
    is_mission_activity,
)

__all__ = ["MissionMode", "resolve_mode", "grade_mission", "is_mission_activity"]
