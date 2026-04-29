"""Conversão UTC → America/Sao_Paulo (BRT) pra exibição ao usuário.

Política do projeto:
- Banco grava sempre em UTC (todos os Mapped[datetime] têm
  timezone=True e default=_utc_now). Cálculos internos comparam UTC.
- Strings exibidas ao usuário (mensagens do bot WhatsApp, PDFs do
  professor, emails) precisam estar em horário de Brasília (BRT).

Helpers:
- `utc_to_brt(dt)` — converte datetime UTC (naive ou aware) pra BRT
- `fmt_brt(dt, format)` — formata datetime UTC como string BRT
- `fmt_brt_short(dt)` — atalho '29/04 às 13:45'
- `fmt_brt_long(dt)` — atalho '29/04/2026 às 13:45'
- `fmt_brt_iso_to_brt(iso_str)` — atalho pra ISO strings vindas do
  banco/JSON (formato '2026-04-29T16:45:00+00:00')

Bug que motivou (M9.5, 2026-04-29): bot disse ao aluno "Recebi essa
redação em 29/04 às 16:45" quando aluno mandou às 13:45 BRT.
Causa: `_format_data_pt` em `bot.py` e `portal_api.py` faziam
`dt.strftime(...)` direto no datetime UTC sem conversão.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo


# America/Sao_Paulo cobre BRT (UTC-3) e BRST (historicamente UTC-2),
# embora horário de verão tenha sido descontinuado em 2019.
# Usar nome de timezone (não offset fixo) é o correto pra futuro-proof.
BRT = ZoneInfo("America/Sao_Paulo")
UTC = timezone.utc


def utc_to_brt(dt: datetime) -> datetime:
    """Converte datetime UTC pra America/Sao_Paulo.

    Aceita:
    - naive (sem tzinfo) — assume UTC. Defensivo: muito código antigo
      usa `datetime.utcnow()` que retorna naive.
    - aware (com tzinfo) — converte de qualquer tz pra BRT.

    Retorna sempre tz-aware em BRT.
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(BRT)


def fmt_brt(dt: datetime, format: str = "%d/%m/%Y às %H:%M") -> str:
    """Formata datetime UTC como string em horário de Brasília."""
    return utc_to_brt(dt).strftime(format)


def fmt_brt_short(dt: datetime) -> str:
    """Atalho — '29/04 às 13:45'. Usado em mensagens WhatsApp curtas."""
    return fmt_brt(dt, "%d/%m às %H:%M")


def fmt_brt_long(dt: datetime) -> str:
    """Atalho — '29/04/2026 às 13:45'. Usado em PDFs e emails."""
    return fmt_brt(dt, "%d/%m/%Y às %H:%M")


def fmt_brt_iso_to_brt(iso_str: Optional[str], short: bool = True) -> str:
    """Recebe ISO string (do banco / JSON), retorna string BRT.

    Tolera 'Z' como sufixo (formato JS). Retorna 'data anterior' em
    caso de input vazio ou inválido (defensivo — antigos callers em
    bot.py dependiam disso).
    """
    if not iso_str:
        return "data anterior"
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return "data anterior"
    return fmt_brt_short(dt) if short else fmt_brt_long(dt)


def now_brt() -> datetime:
    """Datetime atual em BRT (tz-aware). Usado em footers de PDF.
    Pra escrita no banco use sempre UTC via _utc_now() dos models."""
    return datetime.now(UTC).astimezone(BRT)
