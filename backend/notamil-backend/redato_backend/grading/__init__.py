"""Correção de redação — motor público, compartilhado por B2G e B2C.

D12 (ADENDO_B2C_REDATO.md §6): o grader completo (5 competências ENEM)
vivia como função privada `_claude_grade_essay` dentro de
`redato_backend/dev_offline.py` — módulo cujo nome sugere "só dev",
mas que na verdade hospeda o grader de produção. Tanto o bot (B2G)
quanto o B2C importavam essa função privada de lá; um refactor do
dev_offline quebraria o B2C em silêncio.

Este pacote é o ponto público único: `grade_essay_completo(texto,
tema, ...)`. bot.py e b2c/correction.py importam DAQUI. `dev_offline`
re-exporta `_claude_grade_essay` (mesma função) por compatibilidade
com os ~8 call-sites e testes que ainda o referenciam pelo nome antigo.
"""
from redato_backend.grading.essay import (
    grade_essay_completo,
    _claude_grade_essay,
)

__all__ = ["grade_essay_completo", "_claude_grade_essay"]
