"""Testes do helper de conversão UTC → America/Sao_Paulo (M9.5).

Bug que motivou: bot disse ao aluno "Recebi essa redação em 29/04 às
16:45" quando o aluno mandou às 13:45 BRT. Causa: `_format_data_pt` em
`bot.py` e `portal_api.py` faziam `dt.strftime(...)` direto no
datetime UTC sem conversão pra America/Sao_Paulo.

Cobre:
- utc_to_brt com naive (assume UTC) e aware
- fmt_brt formatos curto/longo
- fmt_brt_iso_to_brt com strings ISO de várias formas
- Casos críticos cross-day:
    * 02:00 UTC vira 23:00 do dia anterior em BRT
    * 03:00 UTC vira 00:00 (meia-noite) do dia seguinte (rolagem
      reversa)
- Caso histórico: dt UTC do dia D vira BRT do dia D-1 quando
  hora UTC < 03:00
"""
from __future__ import annotations

from datetime import datetime, timezone


# ──────────────────────────────────────────────────────────────────────
# utc_to_brt
# ──────────────────────────────────────────────────────────────────────

def test_utc_to_brt_naive_assume_utc():
    """Datetime naive (sem tzinfo) é tratado como UTC.
    Defensivo: muito código antigo usa datetime.utcnow() naive."""
    from redato_backend.utils.timezone import utc_to_brt
    naive = datetime(2026, 4, 29, 16, 45, 0)  # 16:45 sem tz
    result = utc_to_brt(naive)
    assert result.tzinfo is not None
    # 16:45 UTC = 13:45 BRT (UTC-3)
    assert result.hour == 13
    assert result.minute == 45


def test_utc_to_brt_aware_utc():
    """Datetime aware UTC explícito."""
    from redato_backend.utils.timezone import utc_to_brt
    aware = datetime(2026, 4, 29, 16, 45, 0, tzinfo=timezone.utc)
    result = utc_to_brt(aware)
    assert result.hour == 13
    assert result.minute == 45


def test_utc_to_brt_preserva_data_no_meio_do_dia():
    from redato_backend.utils.timezone import utc_to_brt
    aware = datetime(2026, 4, 29, 16, 45, 0, tzinfo=timezone.utc)
    result = utc_to_brt(aware)
    assert result.day == 29
    assert result.month == 4
    assert result.year == 2026


# ──────────────────────────────────────────────────────────────────────
# Cross-day — UTC madrugada vira BRT do dia anterior
# ──────────────────────────────────────────────────────────────────────

def test_utc_madrugada_vira_dia_anterior_brt():
    """Caso crítico: 02:00 UTC do dia 30/04 = 23:00 BRT do dia 29/04.
    Bug clássico de log/PDF mostrando dia trocado."""
    from redato_backend.utils.timezone import utc_to_brt
    aware = datetime(2026, 4, 30, 2, 0, 0, tzinfo=timezone.utc)
    result = utc_to_brt(aware)
    assert result.day == 29   # dia ANTERIOR em BRT
    assert result.hour == 23
    assert result.minute == 0


def test_utc_inicio_dia_vira_fim_do_dia_anterior():
    """00:00 UTC do dia 30/04 = 21:00 BRT do dia 29/04."""
    from redato_backend.utils.timezone import utc_to_brt
    aware = datetime(2026, 4, 30, 0, 0, 0, tzinfo=timezone.utc)
    result = utc_to_brt(aware)
    assert result.day == 29
    assert result.hour == 21


def test_utc_03h_vira_meia_noite_mesmo_dia_brt():
    """03:00 UTC do dia 30/04 = 00:00 BRT do mesmo dia 30/04 (limite)."""
    from redato_backend.utils.timezone import utc_to_brt
    aware = datetime(2026, 4, 30, 3, 0, 0, tzinfo=timezone.utc)
    result = utc_to_brt(aware)
    assert result.day == 30
    assert result.hour == 0


# ──────────────────────────────────────────────────────────────────────
# fmt_brt + fmt_brt_short + fmt_brt_long
# ──────────────────────────────────────────────────────────────────────

def test_fmt_brt_short_caso_real_do_bug():
    """Caso EXATO do bug em produção: aluno enviou às 16:45 UTC
    (13:45 BRT). Bot deve dizer '29/04 às 13:45', NÃO '29/04 às 16:45'."""
    from redato_backend.utils.timezone import fmt_brt_short
    dt_utc = datetime(2026, 4, 29, 16, 45, 0, tzinfo=timezone.utc)
    assert fmt_brt_short(dt_utc) == "29/04 às 13:45"


def test_fmt_brt_long_completo():
    from redato_backend.utils.timezone import fmt_brt_long
    dt_utc = datetime(2026, 4, 29, 16, 45, 0, tzinfo=timezone.utc)
    assert fmt_brt_long(dt_utc) == "29/04/2026 às 13:45"


def test_fmt_brt_format_customizado():
    from redato_backend.utils.timezone import fmt_brt
    dt_utc = datetime(2026, 4, 29, 16, 45, 0, tzinfo=timezone.utc)
    assert fmt_brt(dt_utc, "%H:%M") == "13:45"
    assert fmt_brt(dt_utc, "%d/%m") == "29/04"


def test_fmt_brt_cross_day_renderiza_dia_anterior():
    """Render do dia EM BRT — não do dia em UTC."""
    from redato_backend.utils.timezone import fmt_brt_short
    # 30/04 02:00 UTC = 29/04 23:00 BRT
    dt_utc = datetime(2026, 4, 30, 2, 0, 0, tzinfo=timezone.utc)
    assert fmt_brt_short(dt_utc) == "29/04 às 23:00"


# ──────────────────────────────────────────────────────────────────────
# fmt_brt_iso_to_brt (recebe ISO string)
# ──────────────────────────────────────────────────────────────────────

def test_fmt_brt_iso_to_brt_string_aware():
    from redato_backend.utils.timezone import fmt_brt_iso_to_brt
    iso = "2026-04-29T16:45:00+00:00"
    assert fmt_brt_iso_to_brt(iso) == "29/04 às 13:45"


def test_fmt_brt_iso_to_brt_aceita_z_no_final():
    """JS gera ISO com Z (Zulu time = UTC). Backend tolera."""
    from redato_backend.utils.timezone import fmt_brt_iso_to_brt
    iso = "2026-04-29T16:45:00Z"
    assert fmt_brt_iso_to_brt(iso) == "29/04 às 13:45"


def test_fmt_brt_iso_to_brt_short_false_retorna_long():
    from redato_backend.utils.timezone import fmt_brt_iso_to_brt
    iso = "2026-04-29T16:45:00+00:00"
    assert fmt_brt_iso_to_brt(iso, short=False) == "29/04/2026 às 13:45"


def test_fmt_brt_iso_to_brt_invalid_retorna_fallback():
    """Defensivo: callers em bot.py dependem desse fallback pra não
    quebrar mensagem ao aluno quando created_at vem corrompido."""
    from redato_backend.utils.timezone import fmt_brt_iso_to_brt
    assert fmt_brt_iso_to_brt(None) == "data anterior"
    assert fmt_brt_iso_to_brt("") == "data anterior"
    assert fmt_brt_iso_to_brt("não é uma data") == "data anterior"


# ──────────────────────────────────────────────────────────────────────
# now_brt — datetime atual em BRT
# ──────────────────────────────────────────────────────────────────────

def test_now_brt_e_tz_aware_em_brt():
    from redato_backend.utils.timezone import now_brt, BRT
    n = now_brt()
    assert n.tzinfo is not None
    # Deve estar em America/Sao_Paulo (BRT)
    # ZoneInfo equality é por nome — comparamos pela conversão
    assert n.utcoffset().total_seconds() in (-3 * 3600, -2 * 3600)
    # -3h = BRT padrão; -2h = BRST (descontinuado em 2019, mas o
    # ZoneInfo respeita histórico). Hoje deve ser sempre -3h.


# ──────────────────────────────────────────────────────────────────────
# Smoke do bot._format_data_pt — caller real
# ──────────────────────────────────────────────────────────────────────

def test_bot_format_data_pt_caso_do_bug():
    """Smoke do helper em produção. ISO string vinda do SQLite
    (created_at de uma interaction antiga) renderiza BRT."""
    from redato_backend.whatsapp.bot import _format_data_pt
    iso = "2026-04-29T16:45:00+00:00"
    assert _format_data_pt(iso) == "29/04 às 13:45"


def test_bot_format_data_pt_dt_caso_atividade():
    """Smoke do helper que formata MSG_ATIVIDADE_AGENDADA / ENCERRADA."""
    from redato_backend.whatsapp.bot import _format_data_pt_dt
    dt = datetime(2026, 4, 30, 2, 0, 0, tzinfo=timezone.utc)
    # 02:00 UTC = 23:00 BRT do dia anterior
    assert _format_data_pt_dt(dt) == "29/04 23:00"


def test_portal_format_data_pt_caso_notificacao():
    """Smoke do portal_api._format_data_pt usado em
    MSG_NOTIFICACAO_NOVA_ATIVIDADE."""
    from redato_backend.portal.portal_api import _format_data_pt
    dt = datetime(2026, 5, 6, 2, 59, 0, tzinfo=timezone.utc)
    # 02:59 UTC = 23:59 BRT do dia anterior (05/05)
    assert _format_data_pt(dt) == "05/05 23:59"
