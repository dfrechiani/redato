"""Testes da diversificação do top-5 lacunas prioritárias (fix Fase 3 #2).

Sintoma observado: LLM retornava 4 lacunas da mesma competência +
1 de outra (validação envio af8556f6, 2026-05-03). UI virava lista
redundante. Fix aplica cap de 2 por competência.
"""
from __future__ import annotations


def _desc(id_, status="lacuna", confianca="media"):
    """Helper pra construir descritor mínimo."""
    return {"id": id_, "status": status, "confianca": confianca,
            "evidencias": []}


# ──────────────────────────────────────────────────────────────────────
# 1. Cap por competência aplica quando LLM retorna concentrado
# ──────────────────────────────────────────────────────────────────────

def test_diversificar_lacunas_max_2_por_competencia():
    """Cenário real (envio af8556f6): top-5 do LLM = 4 C5 + 1 C3.
    Pós-processamento força max 2 por competência, completa com
    outras lacunas reais do diagnóstico."""
    from redato_backend.diagnostico.inferencia import (
        diversificar_lacunas_prioritarias,
    )
    descritores = [
        _desc("C5.001", confianca="alta"),
        _desc("C5.002", confianca="alta"),
        _desc("C5.003", confianca="alta"),
        _desc("C5.004", confianca="media"),
        _desc("C3.001", confianca="alta"),
        _desc("C3.004", confianca="alta"),  # disponível pra preencher
        _desc("C1.005", confianca="media"), # disponível pra preencher
    ]
    original = ["C5.001", "C5.002", "C5.003", "C5.004", "C3.001"]
    result = diversificar_lacunas_prioritarias(
        descritores, original, max_por_competencia=2,
    )
    # Cap aplicado: max 2 C5
    cnt_c5 = sum(1 for r in result if r.startswith("C5"))
    assert cnt_c5 == 2
    # Mantém prioridade do LLM dentro do cap (C5.001 e C5.002, não C5.003/4)
    assert "C5.001" in result and "C5.002" in result
    assert "C5.003" not in result and "C5.004" not in result
    # C3.001 do top original mantido
    assert "C3.001" in result
    # Total = 5
    assert len(result) == 5


def test_diversificar_lacunas_preserva_ordem_quando_ja_diverso():
    """LLM já retornou diverso (1 por competência) → output idêntico
    em conteúdo e ordem. Não inventa reordenação."""
    from redato_backend.diagnostico.inferencia import (
        diversificar_lacunas_prioritarias,
    )
    descritores = [
        _desc("C1.005"),
        _desc("C2.005"),
        _desc("C3.004"),
        _desc("C4.001"),
        _desc("C5.001"),
    ]
    original = ["C5.001", "C3.004", "C2.005", "C4.001", "C1.005"]
    result = diversificar_lacunas_prioritarias(descritores, original)
    assert result == original  # ordem do LLM preservada


def test_diversificar_lacunas_substitui_excedentes_por_outras_competencias():
    """3 C5 + 2 outras → mantém 2 C5 + 2 outras + 1 nova de C com
    lacuna disponível, ordenada por confiança."""
    from redato_backend.diagnostico.inferencia import (
        diversificar_lacunas_prioritarias,
    )
    descritores = [
        _desc("C5.001", confianca="alta"),
        _desc("C5.002", confianca="alta"),
        _desc("C5.003", confianca="alta"),    # excedente, sai
        _desc("C3.004", confianca="alta"),
        _desc("C1.005", confianca="alta"),
        _desc("C4.001", confianca="alta"),    # candidata pra preencher
        _desc("C2.005", confianca="baixa"),   # outra candidata, baixa prio
    ]
    original = ["C5.001", "C5.002", "C5.003", "C3.004", "C1.005"]
    result = diversificar_lacunas_prioritarias(descritores, original, max_por_competencia=2)
    # 2 C5 mantidos
    assert sum(1 for r in result if r.startswith("C5")) == 2
    # 5 entries (target_total)
    assert len(result) == 5
    # Quinta vaga preenchida com C4.001 (alta confiança) antes de C2.005 (baixa)
    assert "C4.001" in result
    # C5.003 saiu (excedente)
    assert "C5.003" not in result


def test_diversificar_lacunas_menos_de_5_total():
    """Aluno com só 3 lacunas → retorna 3 (não inventa)."""
    from redato_backend.diagnostico.inferencia import (
        diversificar_lacunas_prioritarias,
    )
    descritores = [
        _desc("C1.005"),
        _desc("C3.004"),
        _desc("C5.001"),
        # Resto status=dominio (não vira lacuna)
        _desc("C2.001", status="dominio"),
        _desc("C4.001", status="dominio"),
    ]
    original = ["C1.005", "C3.004", "C5.001"]
    result = diversificar_lacunas_prioritarias(descritores, original)
    assert len(result) == 3
    assert set(result) == {"C1.005", "C3.004", "C5.001"}


def test_diversificar_lacunas_caso_extremo_todas_uma_competencia():
    """Aluno com TODAS 8 lacunas em C5, sem outras competências em
    lacuna. Mantém 2 (cap) — não inventa lacunas em outras comps."""
    from redato_backend.diagnostico.inferencia import (
        diversificar_lacunas_prioritarias,
    )
    descritores = [
        _desc(f"C5.{i:03d}") for i in range(1, 9)
    ] + [
        _desc(f"C{c}.{i:03d}", status="dominio")
        for c in range(1, 5) for i in range(1, 9)
    ]
    original = [f"C5.{i:03d}" for i in range(1, 6)]
    result = diversificar_lacunas_prioritarias(
        descritores, original, max_por_competencia=2,
    )
    # Caso extremo: 3ª passada reincorpora descartados (C5.003-005)
    # pra não retornar lista artificialmente curta. Briefing manda
    # "garante 5 entries (ou todas as lacunas se < 5)".
    assert len(result) == 5
    # Ainda assim, os 2 PRIMEIROS são os top do LLM (C5.001, C5.002)
    assert result[0] == "C5.001"
    assert result[1] == "C5.002"
