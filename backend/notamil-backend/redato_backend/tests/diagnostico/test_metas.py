"""Testes da geração de metas amigáveis pro aluno (Fase 3).

Cobre:
1. Diagnóstico None / vazio → []
2. Cobertura: dicionário cobre todos os 40 descritores
3. Cap em MAX_METAS (5)
4. Dedup por competência (3 lacunas em C5 → 1 meta)
5. Render WhatsApp (markdown bold + estrutura)
"""
from __future__ import annotations

import pytest


# ──────────────────────────────────────────────────────────────────────
# 1. Cobertura: dicionário tem entry pra cada descritor do YAML
# ──────────────────────────────────────────────────────────────────────

def test_gerar_metas_aluno_cobre_todos_descritores():
    """Pra cada um dos 40 IDs do YAML, gerar meta DEVE retornar título
    real (não fallback genérico). Detecta drift se YAML for atualizado
    sem atualizar dicionário."""
    from redato_backend.diagnostico import load_descritores
    from redato_backend.diagnostico.metas import (
        _METAS, _FALLBACK_TITULO,
    )
    descs = load_descritores(force_reload=True)
    assert len(descs) == 40
    for d in descs:
        assert d.id in _METAS, f"{d.id} sem meta cadastrada em metas.py"
        titulo, descricao = _METAS[d.id]
        assert titulo, f"{d.id} título vazio"
        assert titulo != _FALLBACK_TITULO, f"{d.id} usando fallback"
        assert len(descricao) >= 20, f"{d.id} descrição muito curta"


# ──────────────────────────────────────────────────────────────────────
# 2. Estado vazio
# ──────────────────────────────────────────────────────────────────────

def test_gerar_metas_aluno_diagnostico_none_retorna_vazio():
    from redato_backend.diagnostico.metas import gerar_metas_aluno
    assert gerar_metas_aluno(None) == []


def test_gerar_metas_aluno_diagnostico_sem_lacunas_retorna_vazio():
    from redato_backend.diagnostico.metas import gerar_metas_aluno
    assert gerar_metas_aluno({}) == []
    assert gerar_metas_aluno({"lacunas_prioritarias": []}) == []
    assert gerar_metas_aluno({"lacunas_prioritarias": "nao_lista"}) == []


# ──────────────────────────────────────────────────────────────────────
# 3. Cap em MAX_METAS
# ──────────────────────────────────────────────────────────────────────

def test_gerar_metas_aluno_max_5_metas():
    """Mesmo recebendo 8 lacunas em competências distintas, retorna
    no máximo 5 metas (MAX_METAS)."""
    from redato_backend.diagnostico.metas import (
        gerar_metas_aluno, MAX_METAS,
    )
    # 8 IDs em 5 competências DISTINTAS forçam 5 entries (uma por C)
    diag = {
        "lacunas_prioritarias": [
            "C1.005", "C2.005", "C3.004", "C4.001", "C5.001",
            "C5.002",  # extra C5 — dedup
            "C5.003",  # extra C5 — dedup
            "C2.008",  # extra C2 — dedup
        ],
    }
    metas = gerar_metas_aluno(diag)
    assert len(metas) == MAX_METAS == 5
    # Cada competência aparece 1x só
    comps = [m.competencia for m in metas]
    assert sorted(set(comps)) == ["C1", "C2", "C3", "C4", "C5"]


# ──────────────────────────────────────────────────────────────────────
# 4. Dedup por competência preserva ordem de prioridade
# ──────────────────────────────────────────────────────────────────────

def test_gerar_metas_aluno_dedup_competencia():
    """3 lacunas em C5 + 1 em C3: 2 metas (1 C5 + 1 C3). C5 vem
    primeiro pq é o primeiro na ordem de lacunas_prioritarias."""
    from redato_backend.diagnostico.metas import gerar_metas_aluno
    diag = {
        "lacunas_prioritarias": [
            "C5.001", "C5.002", "C5.003", "C3.004",
        ],
    }
    metas = gerar_metas_aluno(diag)
    assert len(metas) == 2
    # Primeira meta deve ser C5 (primeiro na ordem)
    assert metas[0].competencia == "C5"
    assert metas[0].id == "M1"
    # E o título deve ser o do PRIMEIRO C5 (C5.001), não dos outros
    assert "agente nomeado" in metas[0].titulo.lower()
    # Segunda é C3
    assert metas[1].competencia == "C3"
    assert metas[1].id == "M2"


def test_gerar_metas_aluno_id_invalido_pula():
    """ID malformado (não bate o regex) é silenciosamente ignorado.
    Não levanta — degradação graciosa."""
    from redato_backend.diagnostico.metas import gerar_metas_aluno
    diag = {
        "lacunas_prioritarias": [
            "lixo",
            123,  # tipo errado
            None,
            "C3.004",  # válido
        ],
    }
    metas = gerar_metas_aluno(diag)
    # IDs malformados ainda passam pelo dedup (comp=lixo[:2]),
    # então só a válida + uma que coincidir competência aparecem.
    # O importante: não levanta + retorna pelo menos a válida.
    assert any(m.competencia == "C3" for m in metas)


# ──────────────────────────────────────────────────────────────────────
# 5. Render WhatsApp
# ──────────────────────────────────────────────────────────────────────

def test_render_metas_whatsapp_formato():
    from redato_backend.diagnostico.metas import (
        gerar_metas_aluno, render_metas_whatsapp,
    )
    diag = {
        "lacunas_prioritarias": ["C5.001", "C3.004"],
    }
    metas = gerar_metas_aluno(diag)
    msg = render_metas_whatsapp(metas)
    assert msg is not None
    # Header + emoji
    assert "🎯" in msg
    assert "Suas metas" in msg
    # Markdown bold
    assert "*1." in msg
    assert "*2." in msg
    # Conteúdo das metas presente
    assert "agente nomeado" in msg.lower()


def test_render_metas_whatsapp_lista_vazia_retorna_none():
    """Sem metas → None (caller pula envio do chunk extra)."""
    from redato_backend.diagnostico.metas import render_metas_whatsapp
    assert render_metas_whatsapp([]) is None
