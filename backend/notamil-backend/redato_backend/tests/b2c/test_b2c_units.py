"""Unidades puras do B2C — extração de correção, CPF, formatação."""
from __future__ import annotations

import pytest

from redato_backend.b2c.correction import extrair_resultado
from redato_backend.b2c.router import _cpf_valido, _fmt_reais, _fmt_evolucao


# ── extrair_resultado ─────────────────────────────────────────────────

def test_extrair_resultado_do_schema_v3():
    tool_args = {
        "notas_enem": {"c1": 200, "c2": 160, "c3": 120, "c4": 200, "c5": 80},
        "nota_total_enem": 760,
        "feedback_aluno": {
            "acertos": ["boa tese", "coesão"],
            "ajustes": ["repertório raso", "conclusão fraca"],
        },
    }
    r = extrair_resultado(tool_args)
    assert r.nota_total == 760
    assert r.notas == {"c1": 200, "c2": 160, "c3": 120, "c4": 200, "c5": 80}
    assert r.ponto_forte == "boa tese"
    assert r.foco_melhoria == "repertório raso"


def test_extrair_resultado_fallback_cN_audit():
    """Sem notas_enem, cai no cN_audit.nota e soma pro total."""
    tool_args = {
        "c1_audit": {"nota": 160}, "c2_audit": {"nota": 160},
        "c3_audit": {"nota": 120}, "c4_audit": {"nota": 120},
        "c5_audit": {"nota": 80},
    }
    r = extrair_resultado(tool_args)
    assert r.notas["c1"] == 160
    assert r.nota_total == 640           # soma quando total ausente


def test_extrair_resultado_vazio_nao_quebra():
    r = extrair_resultado({})
    assert r.nota_total == 0
    assert set(r.notas) == {"c1", "c2", "c3", "c4", "c5"}
    assert r.ponto_forte and r.foco_melhoria     # textos default


# ── CPF ───────────────────────────────────────────────────────────────

def test_cpf_valido_aceita_valido():
    assert _cpf_valido("111.444.777-35") == "11144477735"


def test_cpf_valido_rejeita():
    assert _cpf_valido("123.456.789-00") is None
    assert _cpf_valido("111.111.111-11") is None      # todos iguais
    assert _cpf_valido("123") is None
    assert _cpf_valido("") is None


# ── formatação ────────────────────────────────────────────────────────

def test_fmt_reais():
    assert _fmt_reais(3990) == "39,90"
    assert _fmt_reais(4900) == "49,00"


def test_fmt_evolucao():
    assert _fmt_evolucao([800, 840, 880]) == "800 → 840 → 880"
    assert _fmt_evolucao([]) == "primeira correção"


# ── alerta de fuga ao tema (backlog B2C) ──────────────────────────────

def test_alerta_fuga_tema_dispara_com_c2_zero():
    from redato_backend.b2c import messages as M
    assert M.alerta_fuga_tema({"c1": 120, "c2": 0, "c3": 80, "c4": 120,
                               "c5": 40}) == M.M_ALERTA_FUGA_TEMA


def test_alerta_fuga_tema_silencioso_com_c2_positiva():
    from redato_backend.b2c import messages as M
    assert M.alerta_fuga_tema({"c1": 120, "c2": 40, "c3": 80}) == ""
    assert M.alerta_fuga_tema({}) == ""   # sem c2 → sem alerta
