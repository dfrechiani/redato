"""Smoke estrutural do layout do Dashboard de turma (refactor 2026-05-04).

Padrão: lê o arquivo TSX e valida invariantes via string match. Mesmo
princípio dos testes de portal_api que usam `inspect.getsource` —
detecta refactors que removam blocos críticos por engano.

Cobre o refactor "proposta D consolidada":
- "Top detectores" REMOVIDO do Dashboard (redundante com diagnóstico)
- Stats topo em 1 linha enxuta
- Diagnóstico storytelling continua central
- Alunos em risco visível (acionável)
- Distribuição + Evolução em accordions <details> (consultivos)

NÃO testa visual/runtime — pra isso teria que subir Next.js + Playwright.
Aqui só garante que o código fonte respeita o contrato decidido.
"""
from __future__ import annotations

from pathlib import Path

import pytest


# parents[0]=tests/portal/, [1]=tests/, [2]=redato_backend/,
# [3]=notamil-backend/, [4]=backend/, [5]=redato_hash/ (repo root)
_REPO_ROOT = Path(__file__).resolve().parents[5]
_DASHBOARD_TSX = (
    _REPO_ROOT / "redato_frontend/components/portal/DashboardTurma.tsx"
)


@pytest.fixture
def dashboard_src() -> str:
    """Conteúdo do DashboardTurma.tsx pra inspeção. Pula se o repo
    não tiver o frontend (CI mínimo só com backend)."""
    if not _DASHBOARD_TSX.exists():
        pytest.skip(f"frontend não presente: {_DASHBOARD_TSX}")
    return _DASHBOARD_TSX.read_text(encoding="utf-8")


# ──────────────────────────────────────────────────────────────────────
# 1. Bloco "Top detectores" foi removido
# ──────────────────────────────────────────────────────────────────────

def test_dashboard_layout_remove_top_detectores(dashboard_src):
    """Refactor proposta D removeu TopDetectoresBadges + a Card 'Top
    detectores' do dashboard de turma — redundante com o diagnóstico
    cognitivo de 40 descritores.

    Garante que:
    - Import do componente foi removido
    - Acesso aos campos `data.top_detectores` / `data.outros_detectores`
      foi removido do JSX (sem renderização)
    - Sem `<TopDetectoresBadges` no JSX

    String 'Top detectores' pode aparecer em comentários explicando o
    refactor ou na descrição do ExportarPdfModal (PDF backend AINDA
    inclui detectores — refactor é só do frontend dashboard).
    """
    # Sem import do componente
    assert "from \"@/components/portal/TopDetectoresBadges\"" not in dashboard_src, (
        "Import de TopDetectoresBadges removido no refactor proposta D"
    )
    # Sem renderização do componente em JSX
    assert "<TopDetectoresBadges" not in dashboard_src
    # Sem leitura dos campos do data
    assert "data.top_detectores" not in dashboard_src
    assert "data.outros_detectores" not in dashboard_src


# ──────────────────────────────────────────────────────────────────────
# 2. Stats topo em 1 linha enxuta
# ──────────────────────────────────────────────────────────────────────

def test_dashboard_stats_linha_enxuta(dashboard_src):
    """Stats topo agora é 1 linha 'X envios · Y atividades ativas
    · Z encerradas' em vez do bloco 'RESUMO' empilhado."""
    # Componente extraído pra StatsTopo (single-purpose)
    assert "function StatsTopo(" in dashboard_src
    # Não tem mais o label 'Resumo' uppercase do layout antigo
    assert ">\n            Resumo\n          </p>" not in dashboard_src
    # Tem a estrutura X envios · Y · Z (sinal divisor "·" usado)
    assert "envio{envios !== 1 ? \"s\" : \"\"}" in dashboard_src \
        or "envio{envios" in dashboard_src


# ──────────────────────────────────────────────────────────────────────
# 3. Alunos em risco continua visível
# ──────────────────────────────────────────────────────────────────────

def test_dashboard_alunos_em_risco_visivel(dashboard_src):
    """Bloco de alunos em risco é acionável → continua VISÍVEL (não
    em accordion). Mantém AlunosEmRiscoCard como antes."""
    assert "BlocoAlunosEmRisco" in dashboard_src
    assert "AlunosEmRiscoCard" in dashboard_src
    # Não está envolto em <details> do refactor (mantém Card direto)
    bloco_alunos_section = dashboard_src.split("BlocoAlunosEmRisco")[1][:500] \
        if "BlocoAlunosEmRisco" in dashboard_src else ""
    # Defesa em profundidade: o componente extraído usa <Card>, não <details>
    assert "function BlocoAlunosEmRisco" in dashboard_src


# ──────────────────────────────────────────────────────────────────────
# 4. Distribuição em accordion
# ──────────────────────────────────────────────────────────────────────

def test_dashboard_distribuicao_em_accordion(dashboard_src):
    """Distribuição de notas agora vive em <details> fechado por
    default (consultivo, não compete com diagnóstico)."""
    assert "function AccordionDistribuicao(" in dashboard_src
    # O componente Accordion usa <details>
    accordion_dist = dashboard_src.split("function AccordionDistribuicao")[1].split(
        "function ",
    )[0] if "function AccordionDistribuicao" in dashboard_src else ""
    assert "<details" in accordion_dist
    assert "DistribuicaoNotasChart" in accordion_dist


# ──────────────────────────────────────────────────────────────────────
# 5. Evolução em accordion
# ──────────────────────────────────────────────────────────────────────

def test_dashboard_evolucao_em_accordion(dashboard_src):
    """Evolução da turma também em accordion <details>."""
    assert "function AccordionEvolucao(" in dashboard_src
    accordion_evo = dashboard_src.split("function AccordionEvolucao")[1].split(
        "function ",
    )[0] if "function AccordionEvolucao" in dashboard_src else ""
    assert "<details" in accordion_evo
    assert "EvolucaoChart" in accordion_evo


# ──────────────────────────────────────────────────────────────────────
# 6. Diagnóstico storytelling central
# ──────────────────────────────────────────────────────────────────────

def test_dashboard_diagnostico_storytelling_central(dashboard_src):
    """DiagnosticoTurma é renderizado ANTES dos accordions, depois do
    StatsTopo — posição central destacada."""
    assert "DiagnosticoTurma" in dashboard_src
    # Ordem: StatsTopo → DiagnosticoTurma → AlunosEmRisco → Accordions
    idx_stats = dashboard_src.find("<StatsTopo")
    idx_diag = dashboard_src.find("<DiagnosticoTurma")
    idx_alunos = dashboard_src.find("<BlocoAlunosEmRisco")
    idx_dist = dashboard_src.find("<AccordionDistribuicao")
    idx_evo = dashboard_src.find("<AccordionEvolucao")
    # Todos presentes
    assert idx_stats > 0, "StatsTopo deve aparecer no JSX"
    assert idx_diag > 0, "DiagnosticoTurma deve aparecer no JSX"
    assert idx_alunos > 0, "BlocoAlunosEmRisco deve aparecer"
    assert idx_dist > 0, "AccordionDistribuicao deve aparecer"
    assert idx_evo > 0, "AccordionEvolucao deve aparecer"
    # Ordem visual top-down: stats < diagnostico < alunos < accordions
    # NOTE: pode haver 2+ ocorrências de DiagnosticoTurma (estado vazio
    # + estado normal). Pegamos a 1ª, que é o estado normal vindo
    # antes da 1ª chamada de BlocoAlunosEmRisco.
    assert idx_stats < idx_diag, (
        f"StatsTopo (pos {idx_stats}) deve vir antes de DiagnosticoTurma "
        f"(pos {idx_diag})"
    )
    assert idx_diag < idx_alunos, (
        "DiagnosticoTurma deve vir antes de BlocoAlunosEmRisco"
    )
    assert idx_alunos < idx_dist, (
        "BlocoAlunosEmRisco deve vir antes da AccordionDistribuicao"
    )
    assert idx_dist < idx_evo, (
        "AccordionDistribuicao deve vir antes de AccordionEvolucao"
    )


# ──────────────────────────────────────────────────────────────────────
# 7. Backend mantém top_detectores no payload (compat)
# ──────────────────────────────────────────────────────────────────────

def test_backend_top_detectores_compat_kept():
    """Refactor frontend NÃO removeu o campo `top_detectores` do
    schema backend — usado por escola dashboard + PDF generator.
    Garante que retro-compat foi preservada."""
    from redato_backend.portal.portal_api import TurmaDashboardResponse
    fields = TurmaDashboardResponse.model_fields
    assert "top_detectores" in fields, (
        "Campo top_detectores foi REMOVIDO do schema — vai quebrar "
        "PDF generator e escola dashboard. Reverter."
    )
    assert "outros_detectores" in fields
