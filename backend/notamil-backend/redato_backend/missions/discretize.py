"""Discretização de scores 0-100 para bandas qualitativas.

FIX 2 (2026-04-27): cada critério da rubrica REJ agora vem como integer
0-100 (em vez de string enum). Bandas:
- 0-49   → "insuficiente"
- 50-79  → "adequado"
- 80-100 → "excelente"

Nota: as bandas finais (3 níveis) usam thresholds 50 e 80, ligeiramente
diferentes das sub-bandas mostradas no prompt (que tem 5 níveis com
sub-banda "leve" vs "notável" pra orientar o LLM). A discretização
binária (3 níveis) é o que o consumer humano vê.
"""
from __future__ import annotations
from typing import Dict


def discretiza_score(score: int) -> str:
    """Score 0-100 → 'insuficiente' / 'adequado' / 'excelente'."""
    if score < 50:
        return "insuficiente"
    if score < 80:
        return "adequado"
    return "excelente"


def discretiza_rubrica(rubrica: Dict[str, int]) -> Dict[str, str]:
    """Aplica discretiza_score em cada critério.
    Útil pra log e relatórios qualitativos."""
    return {k: discretiza_score(int(v)) for k, v in rubrica.items()
            if isinstance(v, (int, float))}


def media_rubrica(rubrica: Dict[str, int]) -> float:
    """Média dos scores 0-100 da rubrica. Útil pra heurística banda → ENEM."""
    nums = [int(v) for v in rubrica.values() if isinstance(v, (int, float))]
    if not nums:
        return 0.0
    return sum(nums) / len(nums)


def media_to_inep_estimate(media: float) -> int:
    """Heurística da média de scores 0-100 pra nota INEP discreta.
    Serve como sanity check do que o LLM emitiu, não como override."""
    if media < 30:
        return 0
    if media < 50:
        return 40
    if media < 65:
        return 80
    if media < 80:
        return 120
    if media < 90:
        return 160
    return 200
