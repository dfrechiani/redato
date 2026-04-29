"""Testes da defesa contra divergência de missao_id (M9.2, 2026-04-29).

Bug em prod (interaction id=3):
- Bot resolveu RJ2·OF06·MF como atividade ativa
- Bot enviou ao Claude tool com enum [RJ2_OF04_MF, RJ2_OF06_MF]
- Claude emitiu missao_id=RJ2_OF04_MF (errado)
- interactions.missao_id ficou RJ2·OF06·MF (correto, pelo bot)
- redato_output JSON ficou RJ2_OF04_MF (errado, pelo LLM)
- Mesma row com 2 valores diferentes pra mesma chave conceitual

Causa: foco_c2 tem 2 valores no enum de missao_id (modo→missão é 1:N
em 2S, diferente de 1:1 da 1S). LLM podia escolher qualquer um, e o
context_block compartilhado menciona AMBAS — induz erro.

Fix em 2 camadas (defesa em profundidade):

1. Prevenção (`_build_user_msg`): header explícito no TOPO do user_msg
   declara qual missão é + reforço na instrução final.

2. Correção (`_enforce_missao_id`): após receber tool_args, força
   `missao_id` correto baseado em activity_id que o bot processou.
   Idempotente — preserva valor se LLM acertou.

3. Auditoria (`_log_missao_id_divergence`): JSONL com kind="missao_id"
   pra rastrear frequência do erro.
"""
from __future__ import annotations


# ──────────────────────────────────────────────────────────────────────
# _build_user_msg — header explícito por missão
# ──────────────────────────────────────────────────────────────────────

def test_user_msg_of04_declara_of04_no_topo():
    from redato_backend.missions.router import _build_user_msg, MissionMode
    msg = _build_user_msg(
        mode=MissionMode.FOCO_C2,
        activity_id="RJ2·OF04·MF",
        content="texto do aluno",
        theme="Tema X",
    )
    # Topo do user_msg deve declarar a missão específica
    header_end = msg.index("---")
    header = msg[:header_end]
    assert "RJ2·OF04·MF" in header
    assert "RJ2_OF04_MF" in header
    # OF06 não deve aparecer no header (só no context_block depois)
    assert "RJ2·OF06·MF" not in header
    assert "RJ2_OF06_MF" not in header


def test_user_msg_of06_declara_of06_no_topo():
    from redato_backend.missions.router import _build_user_msg, MissionMode
    msg = _build_user_msg(
        mode=MissionMode.FOCO_C2,
        activity_id="RJ2·OF06·MF",
        content="texto do aluno",
        theme="Tema X",
    )
    header_end = msg.index("---")
    header = msg[:header_end]
    assert "RJ2·OF06·MF" in header
    assert "RJ2_OF06_MF" in header
    assert "RJ2·OF04·MF" not in header
    assert "RJ2_OF04_MF" not in header


def test_user_msg_instrucao_final_reforca_missao_id():
    """Sanduíche: header no topo + reforço na instrução final."""
    from redato_backend.missions.router import _build_user_msg, MissionMode
    msg = _build_user_msg(
        mode=MissionMode.FOCO_C2,
        activity_id="RJ2·OF04·MF",
        content="texto", theme="Y",
    )
    # Última seção (após último ---) tem a instrução final
    last_section = msg.rsplit("---", 1)[-1]
    assert "DEVE ser exatamente" in last_section
    assert "RJ2_OF04_MF" in last_section


def test_user_msg_normaliza_separadores_no_canonical():
    """Aceita variações de separador (·, _, -) e normaliza canonical."""
    from redato_backend.missions.router import _build_user_msg, MissionMode
    for activity_id in ("RJ2·OF04·MF", "RJ2_OF04_MF", "rj2-of04-mf",
                        "RJ2·OF04·MF·Foco C2"):
        msg = _build_user_msg(
            mode=MissionMode.FOCO_C2,
            activity_id=activity_id,
            content="texto", theme="Y",
        )
        assert "RJ2_OF04_MF" in msg
        assert "RJ2·OF04·MF" in msg


def test_user_msg_inclui_texto_e_tema():
    from redato_backend.missions.router import _build_user_msg, MissionMode
    msg = _build_user_msg(
        mode=MissionMode.FOCO_C2,
        activity_id="RJ2·OF04·MF",
        content="O acesso à educação no Brasil é desigual.",
        theme="Desigualdade educacional",
    )
    assert "Desigualdade educacional" in msg
    assert "O acesso à educação no Brasil é desigual." in msg


def test_user_msg_inclui_nome_da_ferramenta():
    from redato_backend.missions.router import _build_user_msg, MissionMode
    msg = _build_user_msg(
        mode=MissionMode.FOCO_C2,
        activity_id="RJ2·OF04·MF",
        content="texto", theme="Y",
    )
    assert "submit_foco_c2" in msg


def test_user_msg_funciona_pra_modos_1s():
    """Não regrediu: foco_c3/c4/c5/completo_parcial continuam montando
    user_msg com header + context + instrução."""
    from redato_backend.missions.router import _build_user_msg, MissionMode
    for mode, activity_id, expected_canonical in [
        (MissionMode.FOCO_C3, "RJ1·OF10·MF", "RJ1_OF10_MF"),
        (MissionMode.FOCO_C4, "RJ1·OF11·MF", "RJ1_OF11_MF"),
        (MissionMode.FOCO_C5, "RJ1·OF12·MF", "RJ1_OF12_MF"),
        (MissionMode.COMPLETO_PARCIAL, "RJ1·OF13·MF", "RJ1_OF13_MF"),
    ]:
        msg = _build_user_msg(
            mode=mode, activity_id=activity_id,
            content="t", theme="x",
        )
        assert expected_canonical in msg
        assert "DEVE ser exatamente" in msg


# ──────────────────────────────────────────────────────────────────────
# _enforce_missao_id — defesa pós-resposta
# ──────────────────────────────────────────────────────────────────────

def test_enforce_corrige_divergencia_lembra_emitido():
    """Caso real do bug: bot mandou OF06, LLM emitiu OF04. Enforce
    sobrescreve + retorna info pra log."""
    from redato_backend.missions.router import _enforce_missao_id
    tool_args = {
        "modo": "foco_c2",
        "missao_id": "RJ2_OF04_MF",   # LLM errou
        "rubrica_rej": {"compreensao_tema": 80, "tipo_textual": 80,
                         "repertorio": 80},
    }
    div = _enforce_missao_id(tool_args, "RJ2·OF06·MF")
    assert div is not None
    assert div["emitido"] == "RJ2_OF04_MF"
    assert div["esperado"] == "RJ2_OF06_MF"
    # tool_args foi atualizado in-place
    assert tool_args["missao_id"] == "RJ2_OF06_MF"


def test_enforce_idempotente_quando_bate():
    """LLM emitiu missao_id correto — preserva, não diverge."""
    from redato_backend.missions.router import _enforce_missao_id
    tool_args = {"missao_id": "RJ2_OF04_MF"}
    div = _enforce_missao_id(tool_args, "RJ2·OF04·MF")
    assert div is None
    assert tool_args["missao_id"] == "RJ2_OF04_MF"


def test_enforce_aceita_separadores_diversos_no_activity_id():
    from redato_backend.missions.router import _enforce_missao_id
    for activity_id in ("RJ2·OF04·MF", "RJ2_OF04_MF", "rj2-of04-mf",
                        "RJ2·OF04·MF·Foco C2"):
        tool_args = {"missao_id": "RJ2_OF06_MF"}
        div = _enforce_missao_id(tool_args, activity_id)
        assert div is not None
        assert tool_args["missao_id"] == "RJ2_OF04_MF"


def test_enforce_funciona_quando_llm_nao_emite_missao_id():
    """Edge: LLM omitiu missao_id (improvável dado required, mas
    defensivo). Enforce ainda preenche o correto."""
    from redato_backend.missions.router import _enforce_missao_id
    tool_args = {"modo": "foco_c2"}  # sem missao_id
    div = _enforce_missao_id(tool_args, "RJ2·OF04·MF")
    assert div is not None
    assert div["emitido"] is None
    assert tool_args["missao_id"] == "RJ2_OF04_MF"


def test_enforce_activity_id_invalido_retorna_none():
    """Se _canonicalize não consegue extrair RJ\\d_OF\\d+_MF, enforce
    no-op (deixa LLM como está)."""
    from redato_backend.missions.router import _enforce_missao_id
    tool_args = {"missao_id": "RJ2_OF04_MF"}
    # activity_id vazio
    div = _enforce_missao_id(tool_args, "")
    assert div is None
    assert tool_args["missao_id"] == "RJ2_OF04_MF"


def test_enforce_funciona_pra_1s():
    """Modos 1S têm 1:1 modo↔missão; LLM raramente diverge, mas o
    enforce funciona se acontecer."""
    from redato_backend.missions.router import _enforce_missao_id
    tool_args = {"missao_id": "RJ1_OF11_MF"}  # LLM emitiu OF11
    div = _enforce_missao_id(tool_args, "RJ1·OF10·MF")  # bot quer OF10
    assert div is not None
    assert tool_args["missao_id"] == "RJ1_OF10_MF"


# ──────────────────────────────────────────────────────────────────────
# Cenário integrado — atividade A vs atividade B
# ──────────────────────────────────────────────────────────────────────

def test_cenario_bot_resolve_a_prompt_e_enforce_garantem_a():
    """Cenário do bug em prod:

    1. Aluno turma 2A com atividades ativas A=OF04 e B=OF06
    2. Bot resolveu A (OF04) baseado no input do aluno
    3. user_msg DEVE declarar OF04 (não OF06)
    4. Mesmo se LLM emitir OF06 por engano, enforce corrige pra OF04
    5. Resultado: missao_id no JSON consistente com bot
    """
    from redato_backend.missions.router import (
        _build_user_msg, _enforce_missao_id, MissionMode,
    )

    # Bot resolveu OF04 (atividade A)
    activity_a = "RJ2·OF04·MF"

    # (1) user_msg menciona A explicitamente no topo
    msg = _build_user_msg(
        mode=MissionMode.FOCO_C2, activity_id=activity_a,
        content="texto do aluno", theme="Tema X",
    )
    header = msg[:msg.index("---")]
    assert "RJ2_OF04_MF" in header
    assert "RJ2_OF06_MF" not in header

    # (2) Suposição: LLM ficou confuso e emitiu OF06 mesmo assim
    tool_args = {
        "modo": "foco_c2",
        "missao_id": "RJ2_OF06_MF",  # LLM errado
        "rubrica_rej": {"compreensao_tema": 80, "tipo_textual": 80,
                         "repertorio": 80},
        "nota_c2_enem": 160,
    }

    # (3) Enforce sobrescreve pra A
    div = _enforce_missao_id(tool_args, activity_a)
    assert div is not None
    assert div["emitido"] == "RJ2_OF06_MF"
    assert div["esperado"] == "RJ2_OF04_MF"
    assert tool_args["missao_id"] == "RJ2_OF04_MF"

    # (4) Caller (grade_mission) salva tool_args como redato_output —
    # JSON agora bate com o que o bot quer salvar em interactions.
    # Resultado: zero divergência DB.


# ──────────────────────────────────────────────────────────────────────
# Auditoria — log JSONL
# ──────────────────────────────────────────────────────────────────────

def test_log_missao_id_divergence_grava_com_kind_correto(tmp_path):
    """Verifica formato do log JSONL — diferencia 'missao_id' de 'nota'."""
    import json
    import os
    from redato_backend.missions.router import _log_missao_id_divergence

    log_file = tmp_path / "div.jsonl"
    os.environ["REDATO_DIVERGENCES_FILE"] = str(log_file)
    try:
        _log_missao_id_divergence(
            mode="foco_c2",
            activity_id="RJ2·OF06·MF",
            divergence={"emitido": "RJ2_OF04_MF",
                        "esperado": "RJ2_OF06_MF"},
            tool_args={"rubrica_rej": {"x": 1}, "flags": {"y": True}},
        )
    finally:
        del os.environ["REDATO_DIVERGENCES_FILE"]

    lines = log_file.read_text().strip().split("\n")
    assert len(lines) == 1
    rec = json.loads(lines[0])
    assert rec["kind"] == "missao_id"
    assert rec["mode"] == "foco_c2"
    assert rec["activity_id"] == "RJ2·OF06·MF"
    assert rec["missao_id_emitido_llm"] == "RJ2_OF04_MF"
    assert rec["missao_id_esperado"] == "RJ2_OF06_MF"
    assert "ts" in rec
