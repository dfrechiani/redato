"""Testes do gerador de narrativa storytelling (proposta D).

Cobre:
1. Cobertura alta (>=30%) → narrativa principal + cards de ação
2. Cobertura baixa (<30%) → diagnóstico em formação, sem ações
3. 0 alunos diagnosticados → mensagem de espera
4. Cards 'agora' max 2 com oficina sugerida
5. Cards 'semana' lacunas 30-49%, sem CTA
6. Cards 'mês' competência com >=2 descritores em alerta
7. Oficina sugerida no card 'agora' vem do top_lacuna
8. Endpoint diagnostico-agregado retorna narrativa
"""
from __future__ import annotations

from typing import Any, Dict


def _agregado_alta_cobertura() -> Dict[str, Any]:
    """Mock agregado: 18/25 alunos, top lacuna em C5.001 78%."""
    return {
        "turma": {
            "id": "uuid", "codigo": "1A", "serie": "1S",
            "total_alunos": 25, "alunos_com_diagnostico": 18,
            "alunos_sem_diagnostico": 7,
        },
        "atualizado_em": "2026-05-04T12:00:00+00:00",
        "top_lacunas": [
            {
                "id": "C5.001", "competencia": "C5", "nome": "Agente",
                "percent_lacuna": 78.0, "qtd_alunos": 14,
                "sugestao_pedagogica": "Mostre exemplos de propostas com agentes específicos.",
                "definicao_curta": "A proposta nomeia QUEM vai executar — instituição, órgão, ministério.",
                "oficinas_sugeridas": [
                    {"codigo": "RJ1·OF12·MF", "titulo": "Leilão de Soluções",
                     "modo_correcao": "foco_c5", "oficina_numero": 12,
                     "razao": "trabalha proposta"},
                ],
            },
            {
                "id": "C5.002", "competencia": "C5", "nome": "Ação",
                "percent_lacuna": 56.0, "qtd_alunos": 10,
                "sugestao_pedagogica": "Liste verbos concretos.",
                "definicao_curta": "Verbo de ação claro.",
                "oficinas_sugeridas": [],
            },
            {
                "id": "C2.005", "competencia": "C2", "nome": "Repertório",
                "percent_lacuna": 40.0, "qtd_alunos": 7,
                "sugestao_pedagogica": "Cite fontes nomeáveis.",
                "definicao_curta": "Inclua repertório.",
                "oficinas_sugeridas": [],
            },
        ],
        "agregado_por_descritor": [
            {"id": "C5.001", "competencia": "C5", "nome": "Agente",
             "percent_lacuna": 78.0, "alunos_com_lacuna": 14,
             "sugestao_pedagogica": "Mostre.", "definicao_curta": "Quem."},
            {"id": "C5.002", "competencia": "C5", "nome": "Ação",
             "percent_lacuna": 56.0, "alunos_com_lacuna": 10,
             "sugestao_pedagogica": "Verbos.", "definicao_curta": "O quê."},
            {"id": "C5.003", "competencia": "C5", "nome": "Meio",
             "percent_lacuna": 50.0, "alunos_com_lacuna": 9,
             "sugestao_pedagogica": "Por meio de.", "definicao_curta": "Como."},
            {"id": "C2.005", "competencia": "C2", "nome": "Repertório",
             "percent_lacuna": 40.0, "alunos_com_lacuna": 7,
             "sugestao_pedagogica": "Cite.", "definicao_curta": "Cite."},
            {"id": "C3.003", "competencia": "C3", "nome": "Tópico",
             "percent_lacuna": 35.0, "alunos_com_lacuna": 6,
             "sugestao_pedagogica": "Trabalhe.", "definicao_curta": "Topico."},
            {"id": "C1.005", "competencia": "C1", "nome": "Concordância",
             "percent_lacuna": 32.0, "alunos_com_lacuna": 6,
             "sugestao_pedagogica": "Revise.", "definicao_curta": "Concorda."},
        ],
        "agregado_por_competencia": [
            {"competencia": "C5", "percent_dominio_medio": 10,
             "percent_lacuna_medio": 65,
             "descritores_em_alerta": ["C5.001", "C5.002", "C5.003"]},
            {"competencia": "C2", "percent_dominio_medio": 50,
             "percent_lacuna_medio": 25, "descritores_em_alerta": []},
        ],
    }


# ──────────────────────────────────────────────────────────────────────
# 1. Cobertura alta — caminho feliz
# ──────────────────────────────────────────────────────────────────────

def test_gerar_narrativa_turma_cobertura_alta():
    """Cobertura 18/25 (72%) com top lacuna 78% → narrativa principal
    + cards em todas as 3 categorias."""
    from redato_backend.diagnostico.narrativa import gerar_narrativa_turma
    n = gerar_narrativa_turma(_agregado_alta_cobertura())

    # Narrativa principal mencionou o N de alunos + competência crítica
    assert "18 alunos" in n.narrativa_principal
    assert "1A" in n.narrativa_principal
    assert "proposta de intervenção" in n.narrativa_principal
    assert "Agente" in n.narrativa_principal
    assert "78%" in n.narrativa_principal

    # Cards 'agora': 2 (78% e 56% — ambos ≥50%)
    assert len(n.acoes_agora) == 2
    assert all(c.urgencia == "alta" for c in n.acoes_agora)

    # Cards 'semana': lacunas 30-49% (C2.005 40%, C3.003 35%, C1.005 32%)
    assert len(n.acoes_semana) >= 1
    assert all(c.urgencia == "media" for c in n.acoes_semana)

    # Cards 'mês': C5 tem 3 descritores em alerta → entra
    assert len(n.acoes_mes) == 1
    assert all(c.urgencia == "baixa" for c in n.acoes_mes)
    assert "C5" in n.acoes_mes[0].titulo


# ──────────────────────────────────────────────────────────────────────
# 2. Cobertura baixa — diagnóstico em formação
# ──────────────────────────────────────────────────────────────────────

def test_gerar_narrativa_turma_cobertura_baixa_diagnostico_formacao():
    """5/25 (20%) → mensagem 'em formação', 0 cards de ação."""
    from redato_backend.diagnostico.narrativa import gerar_narrativa_turma
    agg = _agregado_alta_cobertura()
    agg["turma"]["alunos_com_diagnostico"] = 5
    agg["turma"]["alunos_sem_diagnostico"] = 20
    n = gerar_narrativa_turma(agg)
    assert "em formação" in n.narrativa_principal.lower()
    assert "5 de 25" in n.narrativa_principal
    assert n.acoes_agora == []
    assert n.acoes_semana == []
    assert n.acoes_mes == []


# ──────────────────────────────────────────────────────────────────────
# 3. Zero alunos
# ──────────────────────────────────────────────────────────────────────

def test_gerar_narrativa_turma_zero_alunos():
    """0 diagnosticados → mensagem de espera, sem ações."""
    from redato_backend.diagnostico.narrativa import gerar_narrativa_turma
    agg = _agregado_alta_cobertura()
    agg["turma"]["alunos_com_diagnostico"] = 0
    agg["turma"]["alunos_sem_diagnostico"] = 25
    agg["top_lacunas"] = []
    n = gerar_narrativa_turma(agg)
    assert "Aguardando" in n.narrativa_principal
    assert "1A" in n.narrativa_principal
    assert n.acoes_agora == []


# ──────────────────────────────────────────────────────────────────────
# 4. Cap de cards em 'agora' = max 2
# ──────────────────────────────────────────────────────────────────────

def test_gerar_narrativa_acoes_agora_max_2():
    """Mesmo com 5 lacunas ≥50%, 'agora' fica capped em 2."""
    from redato_backend.diagnostico.narrativa import (
        gerar_narrativa_turma, MAX_ACOES_AGORA,
    )
    agg = _agregado_alta_cobertura()
    # Adiciona mais 3 lacunas ≥50%
    agg["top_lacunas"] = [
        {"id": f"C{i}.001", "competencia": f"C{i}", "nome": f"Test{i}",
         "percent_lacuna": 60.0 + i, "qtd_alunos": 12,
         "sugestao_pedagogica": "x", "definicao_curta": "y",
         "oficinas_sugeridas": []}
        for i in range(1, 6)
    ]
    n = gerar_narrativa_turma(agg)
    assert len(n.acoes_agora) <= MAX_ACOES_AGORA
    assert len(n.acoes_agora) == 2


# ──────────────────────────────────────────────────────────────────────
# 5. Cards de 'semana' com lacunas 30-49%
# ──────────────────────────────────────────────────────────────────────

def test_gerar_narrativa_acoes_semana_lacunas_medias():
    """Cards de semana só vêm de descritores 30-49% lacuna.
    Lacunas ≥50% vão pra 'agora', <30% não entram."""
    from redato_backend.diagnostico.narrativa import gerar_narrativa_turma
    n = gerar_narrativa_turma(_agregado_alta_cobertura())
    for c in n.acoes_semana:
        assert c.urgencia == "media"
        # CTA não deve aparecer (decisão de design)
        assert c.oficina_sugerida is None


# ──────────────────────────────────────────────────────────────────────
# 6. Card 'mês' quando competência tem >=2 descritores em alerta
# ──────────────────────────────────────────────────────────────────────

def test_gerar_narrativa_acoes_mes_competencia_alerta():
    """C5 com 3 descritores em alerta → 1 card 'mês'.
    Sem competências em alerta → sem card de mês."""
    from redato_backend.diagnostico.narrativa import gerar_narrativa_turma
    agg = _agregado_alta_cobertura()
    n = gerar_narrativa_turma(agg)
    assert len(n.acoes_mes) == 1
    assert "C5" in n.acoes_mes[0].titulo

    # Sem competências em alerta → sem mês
    agg["agregado_por_competencia"] = [
        {"competencia": c, "percent_dominio_medio": 70,
         "percent_lacuna_medio": 10, "descritores_em_alerta": []}
        for c in ("C1", "C2", "C3", "C4", "C5")
    ]
    n2 = gerar_narrativa_turma(agg)
    assert n2.acoes_mes == []


# ──────────────────────────────────────────────────────────────────────
# 7. Oficina sugerida vem do top_lacuna
# ──────────────────────────────────────────────────────────────────────

def test_gerar_narrativa_oficina_sugerida_existe_no_card_agora():
    """Card 'agora' do top lacuna #1 deve ter oficina_sugerida
    (banco da Fase 4 já populou as oficinas no agregado).
    Card sem oficina cai num shape com oficina_sugerida=None."""
    from redato_backend.diagnostico.narrativa import gerar_narrativa_turma
    n = gerar_narrativa_turma(_agregado_alta_cobertura())
    # 1ª lacuna tem oficina catalogada → vem populada
    primeiro = n.acoes_agora[0]
    assert primeiro.oficina_sugerida is not None
    assert primeiro.oficina_sugerida["codigo"] == "RJ1·OF12·MF"
    # 2ª lacuna NÃO tem oficina → fica None mas card ainda renderiza
    segundo = n.acoes_agora[1]
    assert segundo.oficina_sugerida is None
    assert segundo.urgencia == "alta"


# ──────────────────────────────────────────────────────────────────────
# 8. Endpoint inclui narrativa
# ──────────────────────────────────────────────────────────────────────

def test_endpoint_diagnostico_agregado_retorna_narrativa():
    """Smoke estrutural: endpoint chama gerar_narrativa_turma e
    inclui no payload (não dropa o resumo_executivo legacy)."""
    import inspect
    from redato_backend.portal import portal_api
    src = inspect.getsource(portal_api.diagnostico_agregado_turma)
    assert "gerar_narrativa_turma" in src
    assert "narrativa=" in src
    # Schema preserva resumo_executivo (retro-compat)
    assert "resumo_executivo=agregado" in src


def test_diagnostico_agregado_response_aceita_narrativa():
    """Schema aceita o campo `narrativa` com cards das 3 categorias."""
    from redato_backend.portal.portal_api import (
        DiagnosticoAgregadoResponse, DiagnosticoTurmaResumoTurma,
        DiagnosticoNarrativaTurma, DiagnosticoCardAcao,
    )
    r = DiagnosticoAgregadoResponse(
        turma=DiagnosticoTurmaResumoTurma(
            id="x", codigo="1A", serie="1S",
            total_alunos=25, alunos_com_diagnostico=18,
            alunos_sem_diagnostico=7,
        ),
        atualizado_em=None,
        agregado_por_descritor=[],
        agregado_por_competencia=[],
        top_lacunas=[],
        resumo_executivo="legacy",
        narrativa=DiagnosticoNarrativaTurma(
            narrativa_principal="Dos 18 alunos...",
            acoes_agora=[
                DiagnosticoCardAcao(
                    titulo="Mini-aula", descricao="14 alunos.",
                    urgencia="alta", lacunas_atendidas=["C5.001"],
                    oficina_sugerida={
                        "codigo": "RJ1·OF12·MF", "titulo": "Leilão",
                        "modo_correcao": "foco_c5",
                    },
                ),
            ],
            acoes_semana=[],
            acoes_mes=[],
        ),
    )
    assert r.narrativa.narrativa_principal.startswith("Dos")
    assert len(r.narrativa.acoes_agora) == 1
    assert r.narrativa.acoes_agora[0].oficina_sugerida["codigo"] == "RJ1·OF12·MF"
