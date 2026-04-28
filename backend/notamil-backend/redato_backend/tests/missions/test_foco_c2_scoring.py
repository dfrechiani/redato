"""Testes do Modo Foco C2 (M9.1, 2S).

Cobre:
- `rej_to_c2_score` — caps semânticos das 5 flags
- `apply_override` em modo `foco_c2` — override determinístico, divergência
- `resolve_mode` — RJ2·OF04·MF e RJ2·OF06·MF resolvem para FOCO_C2
- `TOOLS_BY_MODE["foco_c2"]` — schema básico válido
- `_modo_disponivel("foco_c2")` no portal_api — desbloqueio automático

Spec: docs/redato/v3/proposta_flags_foco_c1_c2.md (Seção F).
Decisão pedagógica: defesa em profundidade — tool emite a flag, Python
aplica o cap (decisão Daniel 2026-04-28, G.4).
"""
from __future__ import annotations


# ──────────────────────────────────────────────────────────────────────
# rej_to_c2_score — caps semânticos
# ──────────────────────────────────────────────────────────────────────

def _rubrica_excelente():
    return {"compreensao_tema": 95, "tipo_textual": 95, "repertorio": 95}


def _flags_zero():
    return {
        "tangenciamento_tema": False,
        "fuga_tema": False,
        "tipo_textual_inadequado": False,
        "repertorio_de_bolso": False,
        "copia_motivadores_recorrente": False,
    }


def test_rubrica_excelente_sem_flags_da_200():
    from redato_backend.missions.scoring import rej_to_c2_score
    assert rej_to_c2_score(_rubrica_excelente(), _flags_zero()) == 200


def test_rubrica_media_da_120():
    from redato_backend.missions.scoring import rej_to_c2_score
    rubrica = {"compreensao_tema": 70, "tipo_textual": 70, "repertorio": 70}
    # média 70 → faixa 65-79 → 120
    assert rej_to_c2_score(rubrica, _flags_zero()) == 120


def test_fuga_tema_zera_independente_da_rubrica():
    from redato_backend.missions.scoring import rej_to_c2_score
    flags = {**_flags_zero(), "fuga_tema": True}
    assert rej_to_c2_score(_rubrica_excelente(), flags) == 0


def test_tipo_textual_inadequado_zera():
    from redato_backend.missions.scoring import rej_to_c2_score
    flags = {**_flags_zero(), "tipo_textual_inadequado": True}
    assert rej_to_c2_score(_rubrica_excelente(), flags) == 0


def test_tangenciamento_capa_em_80():
    from redato_backend.missions.scoring import rej_to_c2_score
    flags = {**_flags_zero(), "tangenciamento_tema": True}
    # rubrica excelente daria 200; cap puxa pra 80
    assert rej_to_c2_score(_rubrica_excelente(), flags) == 80


def test_repertorio_de_bolso_capa_em_120():
    from redato_backend.missions.scoring import rej_to_c2_score
    flags = {**_flags_zero(), "repertorio_de_bolso": True}
    assert rej_to_c2_score(_rubrica_excelente(), flags) == 120


def test_copia_motivadores_capa_em_160():
    from redato_backend.missions.scoring import rej_to_c2_score
    flags = {**_flags_zero(), "copia_motivadores_recorrente": True}
    assert rej_to_c2_score(_rubrica_excelente(), flags) == 160


def test_caps_acumulam_com_min():
    """Tangenciamento (≤80) + repertorio_de_bolso (≤120): vence o mais
    restritivo (80)."""
    from redato_backend.missions.scoring import rej_to_c2_score
    flags = {
        **_flags_zero(),
        "tangenciamento_tema": True,
        "repertorio_de_bolso": True,
    }
    assert rej_to_c2_score(_rubrica_excelente(), flags) == 80


def test_fuga_zera_mesmo_com_outros_caps_positivos():
    """fuga_tema é o cap mais alto da hierarquia — vence sempre."""
    from redato_backend.missions.scoring import rej_to_c2_score
    flags = {
        **_flags_zero(),
        "fuga_tema": True,
        "tangenciamento_tema": True,
        "repertorio_de_bolso": True,
    }
    assert rej_to_c2_score(_rubrica_excelente(), flags) == 0


def test_rubrica_baixa_sem_flags_nao_anula():
    """Sem flag de anulação, rubrica baixa cai por média, não por cap."""
    from redato_backend.missions.scoring import rej_to_c2_score
    rubrica = {"compreensao_tema": 30, "tipo_textual": 30, "repertorio": 30}
    # média 30 → faixa 30-49 → 40
    assert rej_to_c2_score(rubrica, _flags_zero()) == 40


# ──────────────────────────────────────────────────────────────────────
# apply_override — defesa em profundidade
# ──────────────────────────────────────────────────────────────────────

def test_apply_override_idempotente_quando_llm_ja_capa():
    """LLM já emitiu cap correto; apply_override não diverge."""
    from redato_backend.missions.scoring import apply_override
    tool_args = {
        "rubrica_rej": _rubrica_excelente(),
        "flags": {**_flags_zero(), "tangenciamento_tema": True},
        "nota_c2_enem": 80,  # LLM já aplicou o cap
    }
    res = apply_override("foco_c2", tool_args)
    assert res["nota_final_python"] == 80
    assert res["divergiu"] is False
    assert tool_args["nota_c2_enem"] == 80


def test_apply_override_corrige_quando_llm_emitiu_acima_do_cap():
    """LLM emitiu 180; tangenciamento exige cap 80. Python força."""
    from redato_backend.missions.scoring import apply_override
    tool_args = {
        "rubrica_rej": _rubrica_excelente(),
        "flags": {**_flags_zero(), "tangenciamento_tema": True},
        "nota_c2_enem": 180,
    }
    res = apply_override("foco_c2", tool_args)
    assert res["nota_emitida_llm"] == 180
    assert res["nota_final_python"] == 80
    assert res["divergiu"] is True
    assert tool_args["nota_c2_enem"] == 80


def test_apply_override_zera_quando_fuga_mesmo_se_llm_emitiu_alto():
    from redato_backend.missions.scoring import apply_override
    tool_args = {
        "rubrica_rej": _rubrica_excelente(),
        "flags": {**_flags_zero(), "fuga_tema": True},
        "nota_c2_enem": 200,  # LLM ignorou anulação
    }
    res = apply_override("foco_c2", tool_args)
    assert res["nota_final_python"] == 0
    assert res["divergiu"] is True
    assert tool_args["nota_c2_enem"] == 0


# ──────────────────────────────────────────────────────────────────────
# Roteamento — RJ2·OF04·MF e RJ2·OF06·MF resolvem para FOCO_C2
# ──────────────────────────────────────────────────────────────────────

def test_resolve_mode_rj2_of04_mf():
    from redato_backend.missions.router import resolve_mode, MissionMode
    assert resolve_mode("RJ2·OF04·MF") == MissionMode.FOCO_C2
    assert resolve_mode("RJ2·OF04·MF·Foco C2") == MissionMode.FOCO_C2
    assert resolve_mode("RJ2_OF04_MF") == MissionMode.FOCO_C2
    assert resolve_mode("rj2-of04-mf") == MissionMode.FOCO_C2


def test_resolve_mode_rj2_of06_mf():
    from redato_backend.missions.router import resolve_mode, MissionMode
    assert resolve_mode("RJ2·OF06·MF") == MissionMode.FOCO_C2
    assert resolve_mode("RJ2·OF06·MF·Foco C2") == MissionMode.FOCO_C2


def test_resolve_mode_outras_2s_nao_existem_ainda():
    """OF01, OF07, OF09, OF12, OF13 da 2S ainda não foram roteadas
    (tarefas separadas). Deve retornar None até serem mapeadas."""
    from redato_backend.missions.router import resolve_mode
    assert resolve_mode("RJ2·OF01·MF") is None
    assert resolve_mode("RJ2·OF07·MF") is None


def test_default_model_foco_c2_e_sonnet():
    from redato_backend.missions.router import (
        _DEFAULT_MODEL_BY_MODE, MissionMode,
    )
    assert _DEFAULT_MODEL_BY_MODE[MissionMode.FOCO_C2] == "claude-sonnet-4-6"


# ──────────────────────────────────────────────────────────────────────
# Schema — FOCO_C2_TOOL bem formado
# ──────────────────────────────────────────────────────────────────────

def test_foco_c2_tool_existe_em_tools_by_mode():
    from redato_backend.missions.schemas import TOOLS_BY_MODE, FOCO_C2_TOOL
    assert "foco_c2" in TOOLS_BY_MODE
    assert TOOLS_BY_MODE["foco_c2"] is FOCO_C2_TOOL


def test_foco_c2_tool_schema_basico():
    from redato_backend.missions.schemas import FOCO_C2_TOOL
    assert FOCO_C2_TOOL["name"] == "submit_foco_c2"
    schema = FOCO_C2_TOOL["input_schema"]
    assert schema["type"] == "object"
    # Campos obrigatórios documentados na proposta F.2.
    expected_required = {
        "modo", "missao_id", "rubrica_rej", "nota_rej_total",
        "nota_c2_enem", "flags", "feedback_aluno", "feedback_professor",
    }
    assert set(schema["required"]) == expected_required


def test_foco_c2_tool_5_flags_required():
    from redato_backend.missions.schemas import FOCO_C2_TOOL
    flags = FOCO_C2_TOOL["input_schema"]["properties"]["flags"]
    expected = {
        "tangenciamento_tema", "fuga_tema", "tipo_textual_inadequado",
        "repertorio_de_bolso", "copia_motivadores_recorrente",
    }
    assert set(flags["required"]) == expected
    assert set(flags["properties"].keys()) == expected


def test_foco_c2_tool_aceita_2_missoes():
    from redato_backend.missions.schemas import FOCO_C2_TOOL
    enum = FOCO_C2_TOOL["input_schema"]["properties"]["missao_id"]["enum"]
    assert "RJ2_OF04_MF" in enum
    assert "RJ2_OF06_MF" in enum
    assert len(enum) == 2


def test_foco_c1_continua_adiado_em_tools_by_mode():
    """Decisão G.5 — foco_c1 não entra em TOOLS_BY_MODE até existir
    oficina pedagogicamente alocada."""
    from redato_backend.missions.schemas import TOOLS_BY_MODE
    assert "foco_c1" not in TOOLS_BY_MODE


# ──────────────────────────────────────────────────────────────────────
# Catálogo de detectores — 4 flags novas + repertorio_de_bolso compartilhado
# ──────────────────────────────────────────────────────────────────────

def test_4_flags_c2_no_catalogo():
    from redato_backend.portal.detectores import is_canonical, get_canonical
    novas = (
        "tangenciamento_tema",
        "fuga_tema",
        "tipo_textual_inadequado",
        "copia_motivadores_recorrente",
    )
    for flag in novas:
        assert is_canonical(flag), f"{flag} não está no catálogo"
        det = get_canonical(flag)
        assert det.severidade in ("alta", "media")
        assert det.descricao  # texto pedagógico não-vazio


def test_repertorio_de_bolso_compartilhada_unica_no_catalogo():
    """G.2 — mesma flag em foco_c2 e completo_parcial, cadastrada UMA
    vez no catálogo."""
    from redato_backend.portal.detectores import canonical_detectores
    cat = canonical_detectores()
    assert "repertorio_de_bolso" in cat
    # Não há variantes tipo "repertorio_decorativo" ou "repertorio_clichê"
    assert "repertorio_decorativo" not in cat
    assert "repertorio_clichê" not in cat


def test_catalogo_tem_45_detectores():
    """41 (M9) + 4 novos C2 = 45. repertorio_de_bolso já estava."""
    from redato_backend.portal.detectores import canonical_detectores
    assert len(canonical_detectores()) == 45


# ──────────────────────────────────────────────────────────────────────
# Portal — desbloqueio automático
# ──────────────────────────────────────────────────────────────────────

def test_portal_desbloqueia_foco_c2_automaticamente():
    """_MODOS_COM_PROMPT é set(TOOLS_BY_MODE.keys()) | {"completo"} —
    adicionar foco_c2 ao TOOLS_BY_MODE faz o helper desbloquear sozinho."""
    from redato_backend.portal.portal_api import _modo_disponivel
    assert _modo_disponivel("foco_c2") is True
    # foco_c1 continua bloqueado (decisão G.5)
    assert _modo_disponivel("foco_c1") is False


def test_compute_pre_flags_foco_c2_retorna_dict_vazio():
    """MVP do M9.1: sem detectores Python heurísticos pra foco_c2."""
    from redato_backend.missions.detectors import compute_pre_flags
    out = compute_pre_flags("foco_c2", "Texto qualquer do aluno")
    assert out == {}


# ──────────────────────────────────────────────────────────────────────
# Não-regressão — outros modos continuam funcionando
# ──────────────────────────────────────────────────────────────────────

def test_foco_c3_nao_regrediu():
    from redato_backend.missions.scoring import rej_to_c3_score
    rubrica = {"conclusao": 95, "premissa": 95, "exemplo": 95, "fluencia": 95}
    flags = {"andaime_copiado": False, "tese_generica": False, "exemplo_redundante": False}
    assert rej_to_c3_score(rubrica, flags) == 200


def test_foco_c5_nao_regrediu():
    from redato_backend.missions.scoring import rej_to_c5_score
    rubrica = {
        "agente": 95, "acao_verbo": 95, "meio": 95,
        "finalidade": 95, "detalhamento": 95, "direitos_humanos": 95,
    }
    flags = {
        "desrespeito_direitos_humanos": False,
        "proposta_vaga_constatatoria": False,
        "proposta_desarticulada": False,
        "agente_generico": False,
        "verbo_fraco": False,
    }
    assert rej_to_c5_score(rubrica, flags, "clara") == 200
