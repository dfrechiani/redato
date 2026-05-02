"""Testes do dispatcher de comandos do dashboard professor (M10
PROMPT 2/2).

Padrão deste arquivo: tests **isolados** que exercitam parser +
helpers de render sem precisar de Postgres real. Pra os 3 comandos
(/turma, /aluno, /atividade) que tocam DB, validamos:

- Parser de comando (variações sintáticas)
- Defensiva quando DB indisponível
- Estrutura dos handlers via inspect.getsource (regressão)
- Render de mensagens com fixtures sintéticas

Tests de integração full (com Postgres) ficam em scripts/test_*
separados — padrão do projeto.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Tuple
from unittest.mock import MagicMock

import pytest


# ──────────────────────────────────────────────────────────────────────
# Parser de comando
# ──────────────────────────────────────────────────────────────────────

def test_parse_comando_aceita_com_barra():
    from redato_backend.whatsapp.dashboard_commands import parse_comando
    assert parse_comando("/turma 1A") == ("turma", "1A")
    assert parse_comando("/aluno maria") == ("aluno", "maria")
    assert parse_comando("/atividade OF14") == ("atividade", "OF14")
    assert parse_comando("/ajuda") == ("ajuda", "")


def test_parse_comando_aceita_sem_barra():
    """Variação sintática comum — professor digita só "turma 1A"."""
    from redato_backend.whatsapp.dashboard_commands import parse_comando
    assert parse_comando("turma 1A") == ("turma", "1A")
    assert parse_comando("aluno joão silva") == ("aluno", "joão silva")


def test_parse_comando_case_insensitive():
    from redato_backend.whatsapp.dashboard_commands import parse_comando
    assert parse_comando("/Turma 1A") == ("turma", "1A")
    assert parse_comando("/AJUDA") == ("ajuda", "")
    assert parse_comando("ATIVIDADE of14") == ("atividade", "of14")


def test_parse_comando_normaliza_help_em_ajuda():
    """Aliases pra 'ajuda' aceitos por convenção (UX)."""
    from redato_backend.whatsapp.dashboard_commands import parse_comando
    assert parse_comando("/help") == ("ajuda", "")
    assert parse_comando("help") == ("ajuda", "")


def test_parse_comando_tolera_espacos_extras():
    from redato_backend.whatsapp.dashboard_commands import parse_comando
    assert parse_comando("  /turma   1A   ") == ("turma", "1A")
    assert parse_comando("/aluno    maria  silva  ") == (
        "aluno", "maria  silva",  # preserva espaço interno
    )


def test_parse_comando_retorna_none_pra_texto_livre():
    """Texto sem comando reconhecido → None. Caller mostra ajuda."""
    from redato_backend.whatsapp.dashboard_commands import parse_comando
    assert parse_comando("oi tudo bem?") is None
    assert parse_comando("") is None
    assert parse_comando(None) is None
    # Comando não-conhecido também retorna None
    assert parse_comando("/inexistente") is None


# ──────────────────────────────────────────────────────────────────────
# Helpers de parse de redato_output
# ──────────────────────────────────────────────────────────────────────

def test_nota_total_de_formato_ft():
    """Formato OF14 do FT BTBOS5VF — 5 cN_audit.nota → soma."""
    from redato_backend.whatsapp.dashboard_commands import _nota_total_de
    redato = {
        f"c{i}_audit": {"nota": 160} for i in range(1, 6)
    }
    redato["nota_total"] = 800  # canônico do fix eb5ddc9
    assert _nota_total_de(redato) == 800


def test_nota_total_de_formato_foco_c2():
    """Formato moderno foco_c2 do Sonnet."""
    from redato_backend.whatsapp.dashboard_commands import _nota_total_de
    redato = {"modo": "foco_c2", "nota_c2_enem": 160}
    assert _nota_total_de(redato) == 160


def test_nota_total_de_redato_com_erro_retorna_none():
    """redato_output com chave 'error' → None (correção falhou)."""
    from redato_backend.whatsapp.dashboard_commands import (
        _nota_total_de, _redato_tem_erro,
    )
    redato = {"error": "OpenAIFTGradingError: timeout"}
    assert _nota_total_de(redato) is None
    assert _redato_tem_erro(redato) is True


def test_redato_tem_erro_com_redato_none():
    """None ou dict vazio → erro (proxy pra 'sem nota')."""
    from redato_backend.whatsapp.dashboard_commands import _redato_tem_erro
    assert _redato_tem_erro(None) is True
    assert _redato_tem_erro({}) is True


def test_notas_por_competencia_extrai_5():
    from redato_backend.whatsapp.dashboard_commands import (
        _notas_por_competencia,
    )
    redato = {
        "c1_audit": {"nota": 120},
        "c2_audit": {"nota": 160},
        "c3_audit": {"nota": 120},
        "c4_audit": {"nota": 120},
        "c5_audit": {"nota": 80},
    }
    out = _notas_por_competencia(redato)
    assert out == {"c1": 120, "c2": 160, "c3": 120, "c4": 120, "c5": 80}


def test_notas_por_competencia_falta_uma_retorna_none():
    """Schema parcial (4 das 5) → None. Não tenta inventar."""
    from redato_backend.whatsapp.dashboard_commands import (
        _notas_por_competencia,
    )
    redato = {
        "c1_audit": {"nota": 120},
        "c2_audit": {"nota": 160},
        # c3 ausente
        "c4_audit": {"nota": 120},
        "c5_audit": {"nota": 80},
    }
    assert _notas_por_competencia(redato) is None


# ──────────────────────────────────────────────────────────────────────
# Defensiva — DB indisponível
# ──────────────────────────────────────────────────────────────────────

def test_cmd_turma_sem_match_resposta_amigavel():
    """Sem DATABASE_URL ou turma inexistente na escola do prof →
    mensagem amigável (nunca levanta exception). Cobre os 2 caminhos
    porque dependendo da ordem dos tests anteriores o engine pode ter
    sido criado ou não — ambos são UX aceitáveis."""
    from redato_backend.whatsapp import dashboard_commands as DC
    out = DC.cmd_turma(
        prof_id=uuid.uuid4(), escola_id=uuid.uuid4(), args="1A",
    )
    aceita = (
        "Não consegui" in out
        or "problema" in out.lower()
        or "não encontrada" in out.lower()
    )
    assert aceita, f"resposta inesperada: {out!r}"


def test_cmd_aluno_sem_match_resposta_amigavel():
    from redato_backend.whatsapp import dashboard_commands as DC
    out = DC.cmd_aluno(
        prof_id=uuid.uuid4(), escola_id=uuid.uuid4(), args="maria",
    )
    aceita = (
        "Não consegui" in out
        or "problema" in out.lower()
        or "encontrado" in out.lower()
    )
    assert aceita, f"resposta inesperada: {out!r}"


def test_cmd_atividade_sem_match_resposta_amigavel():
    from redato_backend.whatsapp import dashboard_commands as DC
    out = DC.cmd_atividade(
        prof_id=uuid.uuid4(), escola_id=uuid.uuid4(), args="OF14",
    )
    aceita = (
        "Não consegui" in out
        or "problema" in out.lower()
        or "não encontrada" in out.lower()
    )
    assert aceita, f"resposta inesperada: {out!r}"


# ──────────────────────────────────────────────────────────────────────
# Mensagens de uso (args ausentes)
# ──────────────────────────────────────────────────────────────────────

def test_cmd_turma_sem_args_pede_codigo():
    from redato_backend.whatsapp import dashboard_commands as DC
    out = DC.cmd_turma(
        prof_id=uuid.uuid4(), escola_id=uuid.uuid4(), args="",
    )
    assert "código da turma" in out.lower() or "/turma" in out


def test_cmd_aluno_sem_args_pede_nome():
    from redato_backend.whatsapp import dashboard_commands as DC
    out = DC.cmd_aluno(
        prof_id=uuid.uuid4(), escola_id=uuid.uuid4(), args="",
    )
    assert "nome do aluno" in out.lower() or "/aluno" in out


def test_cmd_atividade_sem_args_pede_codigo():
    from redato_backend.whatsapp import dashboard_commands as DC
    out = DC.cmd_atividade(
        prof_id=uuid.uuid4(), escola_id=uuid.uuid4(), args="",
    )
    assert "código da atividade" in out.lower() or "/atividade" in out


# ──────────────────────────────────────────────────────────────────────
# /ajuda
# ──────────────────────────────────────────────────────────────────────

def test_cmd_ajuda_lista_4_comandos():
    """Resposta de /ajuda lista os 4 comandos do dashboard."""
    from redato_backend.whatsapp import dashboard_commands as DC
    out = DC.cmd_ajuda(prof_id=uuid.uuid4(), escola_id=uuid.uuid4())
    for cmd in ("/turma", "/aluno", "/atividade", "/ajuda"):
        assert cmd in out, f"comando {cmd} faltando em /ajuda"
    # Aviso LGPD / uso pedagógico
    assert "pedagógico" in out.lower() or "compartilhe" in out.lower()


# ──────────────────────────────────────────────────────────────────────
# Dispatcher
# ──────────────────────────────────────────────────────────────────────

def test_dispatch_texto_invalido_retorna_ajuda():
    """Texto sem comando → ajuda."""
    from redato_backend.whatsapp import dashboard_commands as DC
    out = DC.dispatch(
        prof_id=uuid.uuid4(), escola_id=uuid.uuid4(),
        text="oi tudo bem",
    )
    assert "Comandos do dashboard" in out


def test_dispatch_ajuda_retorna_ajuda():
    from redato_backend.whatsapp import dashboard_commands as DC
    out = DC.dispatch(
        prof_id=uuid.uuid4(), escola_id=uuid.uuid4(), text="/ajuda",
    )
    assert "Comandos do dashboard" in out


def test_dispatch_aceita_variacoes_sintaticas():
    """Texto com variações ("turma 1A", "/Turma 1A", "TURMA 1A") cai
    no mesmo comando. Quando DB indisponível em test, retorna mensagem
    amigável — confirma que pelo menos chegou no handler."""
    from redato_backend.whatsapp import dashboard_commands as DC
    msgs = [
        "/turma 1A",
        "turma 1A",
        "/TURMA 1A",
    ]
    outs = [
        DC.dispatch(
            prof_id=uuid.uuid4(), escola_id=uuid.uuid4(), text=m,
        )
        for m in msgs
    ]
    # Todas devem ter mesma forma (DB indisponível ou turma não
    # encontrada — não cair em "Comandos do dashboard" da ajuda).
    for o in outs:
        assert "Comandos do dashboard" not in o, (
            f"comando turma caiu em ajuda: {o[:80]}"
        )


# ──────────────────────────────────────────────────────────────────────
# Estrutura — regressão via inspect.getsource
# ──────────────────────────────────────────────────────────────────────

def test_handle_professor_inbound_chama_dispatch_apos_lgpd():
    """Smoke estrutural: depois do aceite LGPD, _handle_professor_inbound
    deve chamar `dashboard_commands.dispatch`. Refactor que remova essa
    chamada quebra o caminho principal."""
    import inspect
    from redato_backend.whatsapp.bot import _handle_professor_inbound
    src = inspect.getsource(_handle_professor_inbound)
    assert "dashboard_commands" in src or "DC.dispatch" in src or "dispatch" in src
    assert "lgpd_aceito_em is None" in src, (
        "perdeu o gate LGPD — comando chamaria com prof não-aceitante"
    )


def test_dashboard_commands_filtra_por_escola_id():
    """LGPD: cada handler filtra queries por escola_id pra prof não
    ver dados de outras escolas. Smoke estrutural via getsource."""
    import inspect
    from redato_backend.whatsapp import dashboard_commands as DC
    for fn in (DC.cmd_turma, DC.cmd_aluno, DC.cmd_atividade):
        src = inspect.getsource(fn)
        assert "escola_id" in src, (
            f"{fn.__name__} não filtra por escola_id — risco LGPD"
        )


# ──────────────────────────────────────────────────────────────────────
# Render — fixtures sintéticas (sem DB)
# ──────────────────────────────────────────────────────────────────────

def test_render_resumo_turma_inclui_top3_e_alertas():
    """Render do resumo /turma: top 3, médias C1-C5, alertas."""
    from redato_backend.whatsapp.dashboard_commands import (
        _render_resumo_turma,
    )

    turma = MagicMock()
    turma.codigo = "1A"
    turma.serie = "1S"

    soma_cn = {
        "c1": [120, 160, 120],
        "c2": [160, 200, 160],
        "c3": [120, 160, 120],
        "c4": [120, 120, 80],
        "c5": [200, 160, 160],
    }
    top3 = [("Maria", 920), ("João", 880), ("Ana", 840)]
    out = _render_resumo_turma(
        turma=turma, n_alunos=25,
        codigos_ativos=["RJ1·OF14·MF"],
        soma_cn=soma_cn, top3=top3,
        n_erro=2, n_sem_envio=5,
    )
    # Cabeçalho
    assert "Turma 1A" in out
    assert "1S" in out
    assert "25" in out
    # Top 3
    assert "Maria" in out and "920" in out
    assert "João" in out
    # Médias C1-C5 inline
    assert "C1" in out and "C2" in out
    # Alertas
    assert "2 envio" in out
    assert "5 aluno" in out


def test_render_resumo_turma_sem_dados_nao_quebra():
    """Edge: turma sem envios → não mostra blocos vazios mas não
    levanta exception."""
    from redato_backend.whatsapp.dashboard_commands import (
        _render_resumo_turma,
    )
    turma = MagicMock()
    turma.codigo = "9Z"
    turma.serie = None
    out = _render_resumo_turma(
        turma=turma, n_alunos=0, codigos_ativos=[],
        soma_cn={f"c{i}": [] for i in range(1, 6)},
        top3=[], n_erro=0, n_sem_envio=0,
    )
    assert "Turma 9Z" in out
    # Sem médias quando não há notas
    assert "Médias" not in out or "Geral" not in out
