"""Canários de prompt do modo jogo_redacao (Fase 2 passo 5).

Cobre 5 cenários canônicos da rubrica do jogo:

1. Cópia literal (transformacao=0-15, flag copia_literal=true, C3 cap)
2. Conectivos trocados (transformacao=30-50)
3. Reescrita autoral substancial (transformacao=70-100)
4. Fuga do tema (flag fuga_do_tema_do_minideck, C2 cap em 80)
5. Reescrita ofensiva DH (flag desrespeito_direitos_humanos, C1=0+C5=0)

Estes testes NÃO chamam Claude API real — usam responses pré-gravadas
em `_RESPONSES` e exercitam o pipeline pós-chamada (scoring, sanear
sugestões, formatação). Testes que precisariam de Claude real estão
marcados `@pytest.mark.skip(reason="manual_only")`.

Pra rodar manualmente os de Claude real:
    pytest -m manual_only --runxfail tests/missions/test_jogo_redacao_canarios.py

Custo estimado por chamada manual: ~10 KB input × 5 canários
≈ 50 KB tokens prompt + ~2 KB output × 5 ≈ 10 KB tokens completion.
Com Sonnet 4.6: ~$0.20-0.30 por execução completa dos 5 canários.
Cache hit no system+catálogo (TTL=1h) reduz pra ~$0.10 nos runs
subsequentes.
"""
from __future__ import annotations

import pytest

from redato_backend.missions.scoring import apply_override
from redato_backend.missions.router import _sanear_sugestoes


# ──────────────────────────────────────────────────────────────────────
# Helpers — fixtures de cartas e canários
# ──────────────────────────────────────────────────────────────────────

class _LacunaSnap:
    def __init__(self, codigo, tipo, conteudo):
        self.codigo = codigo
        self.tipo = tipo
        self.conteudo = conteudo


def _lacunas_minideck_saude_mental():
    """Subconjunto representativo do minideck de Saúde Mental — bate
    com seed_minideck.py + xlsx commitado em data/seeds/. Suficiente
    pra testar sanear_sugestoes."""
    return {
        "P01": _LacunaSnap("P01", "PROBLEMA", "estigma social"),
        "P03": _LacunaSnap("P03", "PROBLEMA", "preconceito"),
        "P05": _LacunaSnap("P05", "PROBLEMA", "falta de profissionais"),
        "R01": _LacunaSnap("R01", "REPERTORIO", "OMS (86%)"),
        "R05": _LacunaSnap("R05", "REPERTORIO", "IBGE 2022"),
        "K01": _LacunaSnap("K01", "PALAVRA_CHAVE", "investimento"),
        "K11": _LacunaSnap("K11", "PALAVRA_CHAVE", "estigma cultural"),
        "K22": _LacunaSnap("K22", "PALAVRA_CHAVE", "preconceito"),
        "A01": _LacunaSnap("A01", "AGENTE", "Ministério da Saúde"),
        "A02": _LacunaSnap("A02", "AGENTE", "CAPS"),
        "AC07": _LacunaSnap("AC07", "ACAO", "ampliar CAPS"),
        "ME04": _LacunaSnap("ME04", "MEIO", "via emendas"),
        "F02": _LacunaSnap("F02", "FIM", "garantir tratamento"),
    }


# ──────────────────────────────────────────────────────────────────────
# Canários — apply_override + sanear_sugestoes
# ──────────────────────────────────────────────────────────────────────

def test_canario_copia_literal_cap_transformacao_em_15():
    """LLM detectou cópia literal e marcou flag — cap transformacao
    em 15 mesmo que LLM tenha emitido > 15."""
    tool_args = {
        "modo": "jogo_redacao",
        "tema_minideck": "saude_mental",
        "notas_enem": {"c1": 160, "c2": 120, "c3": 80, "c4": 120, "c5": 80},
        "nota_total_enem": 560,
        "transformacao_cartas": 30,  # LLM exagerou
        "flags": {
            "copia_literal_das_cartas": True,
            "cartas_mal_articuladas": False,
            "fuga_do_tema_do_minideck": False,
            "tipo_textual_inadequado": False,
            "desrespeito_direitos_humanos": False,
        },
        "sugestoes_cartas_alternativas": [],
        "feedback_aluno": {"acertos": [], "ajustes": []},
        "feedback_professor": {
            "pontos_fortes": [], "pontos_fracos": [],
            "padrao_falha": "", "transferencia_competencia": "",
        },
    }
    out = apply_override("jogo_redacao", tool_args)
    assert tool_args["transformacao_cartas"] == 15
    assert tool_args["nota_total_enem"] == 560


def test_canario_paragrafo_so_conectivos_trocados_transformacao_baixa():
    """LLM avaliou em banda 30-50 (esqueleto reconhecível). Sem flag
    de cópia literal, score passa direto."""
    tool_args = {
        "modo": "jogo_redacao",
        "tema_minideck": "saude_mental",
        "notas_enem": {"c1": 160, "c2": 120, "c3": 120, "c4": 120, "c5": 120},
        "nota_total_enem": 640,
        "transformacao_cartas": 40,
        "flags": {
            "copia_literal_das_cartas": False,
            "cartas_mal_articuladas": False,
            "fuga_do_tema_do_minideck": False,
            "tipo_textual_inadequado": False,
            "desrespeito_direitos_humanos": False,
        },
        "sugestoes_cartas_alternativas": [],
        "feedback_aluno": {"acertos": [], "ajustes": []},
        "feedback_professor": {
            "pontos_fortes": [], "pontos_fracos": [],
            "padrao_falha": "", "transferencia_competencia": "",
        },
    }
    apply_override("jogo_redacao", tool_args)
    assert tool_args["transformacao_cartas"] == 40
    # Notas não mudam (sem flags)
    assert tool_args["notas_enem"]["c1"] == 160
    assert tool_args["notas_enem"]["c5"] == 120


def test_canario_reescrita_autoral_substancial_passa_intacta():
    """Caso feliz — reescrita 71-100, sem flags, scoring no-op."""
    tool_args = {
        "modo": "jogo_redacao",
        "tema_minideck": "saude_mental",
        "notas_enem": {"c1": 200, "c2": 200, "c3": 160, "c4": 160, "c5": 160},
        "nota_total_enem": 880,
        "transformacao_cartas": 85,
        "flags": {
            "copia_literal_das_cartas": False,
            "cartas_mal_articuladas": False,
            "fuga_do_tema_do_minideck": False,
            "tipo_textual_inadequado": False,
            "desrespeito_direitos_humanos": False,
        },
        "sugestoes_cartas_alternativas": [],
        "feedback_aluno": {"acertos": [], "ajustes": []},
        "feedback_professor": {
            "pontos_fortes": [], "pontos_fracos": [],
            "padrao_falha": "", "transferencia_competencia": "",
        },
    }
    out = apply_override("jogo_redacao", tool_args)
    assert tool_args["nota_total_enem"] == 880
    assert tool_args["transformacao_cartas"] == 85
    assert out["divergiu"] is False  # LLM emitiu o total certo


def test_canario_fuga_tema_minideck_cap_c2_em_80():
    """Aluno escreveu sobre Educação Digital quando minideck era Saúde
    Mental. C2 cap em 80, demais notas preservadas."""
    tool_args = {
        "modo": "jogo_redacao",
        "tema_minideck": "saude_mental",
        "notas_enem": {"c1": 200, "c2": 200, "c3": 160, "c4": 160, "c5": 160},
        "nota_total_enem": 880,
        "transformacao_cartas": 70,
        "flags": {
            "copia_literal_das_cartas": False,
            "cartas_mal_articuladas": False,
            "fuga_do_tema_do_minideck": True,
            "tipo_textual_inadequado": False,
            "desrespeito_direitos_humanos": False,
        },
        "sugestoes_cartas_alternativas": [],
        "feedback_aluno": {"acertos": [], "ajustes": []},
        "feedback_professor": {
            "pontos_fortes": [], "pontos_fracos": [],
            "padrao_falha": "", "transferencia_competencia": "",
        },
    }
    apply_override("jogo_redacao", tool_args)
    assert tool_args["notas_enem"]["c2"] == 80
    # Total recalculado: 200+80+160+160+160 = 760
    assert tool_args["nota_total_enem"] == 760


def test_canario_desrespeito_dh_zera_c1_e_c5():
    """Reescrita defendendo violação de DH — C1=0 + C5=0."""
    tool_args = {
        "modo": "jogo_redacao",
        "tema_minideck": "saude_mental",
        "notas_enem": {"c1": 200, "c2": 160, "c3": 160, "c4": 160, "c5": 160},
        "nota_total_enem": 840,
        "transformacao_cartas": 50,
        "flags": {
            "copia_literal_das_cartas": False,
            "cartas_mal_articuladas": False,
            "fuga_do_tema_do_minideck": False,
            "tipo_textual_inadequado": False,
            "desrespeito_direitos_humanos": True,
        },
        "sugestoes_cartas_alternativas": [],
        "feedback_aluno": {"acertos": [], "ajustes": []},
        "feedback_professor": {
            "pontos_fortes": [], "pontos_fracos": [],
            "padrao_falha": "", "transferencia_competencia": "",
        },
    }
    apply_override("jogo_redacao", tool_args)
    assert tool_args["notas_enem"]["c1"] == 0
    assert tool_args["notas_enem"]["c5"] == 0
    # Total: 0 + 160 + 160 + 160 + 0 = 480
    assert tool_args["nota_total_enem"] == 480


# ──────────────────────────────────────────────────────────────────────
# _sanear_sugestoes
# ──────────────────────────────────────────────────────────────────────

def test_sanear_aceita_sugestao_valida():
    """Original P03 (escolhido pelo grupo), sugerida P05 (no minideck,
    mesmo tipo). Aceita."""
    lacunas = _lacunas_minideck_saude_mental()
    tool_args = {
        "sugestoes_cartas_alternativas": [
            {
                "codigo_original": "P03",
                "codigo_sugerido": "P05",
                "motivo": "P05 dá mais especificidade ao recorte.",
            },
        ],
    }
    _sanear_sugestoes(
        tool_args,
        codigos_escolhidos=["E01", "E10", "P03", "R01"],
        lacunas_por_codigo=lacunas,
    )
    assert len(tool_args["sugestoes_cartas_alternativas"]) == 1
    assert tool_args["sugestoes_cartas_alternativas"][0]["codigo_original"] == "P03"


def test_sanear_remove_codigo_original_fora_do_grupo():
    """LLM sugeriu trocar P05 (que o grupo NÃO escolheu) — descarta."""
    lacunas = _lacunas_minideck_saude_mental()
    tool_args = {
        "sugestoes_cartas_alternativas": [
            {
                "codigo_original": "P05",  # grupo não tem P05
                "codigo_sugerido": "P01",
                "motivo": "qualquer",
            },
        ],
    }
    _sanear_sugestoes(
        tool_args,
        codigos_escolhidos=["P03"],
        lacunas_por_codigo=lacunas,
    )
    assert tool_args["sugestoes_cartas_alternativas"] == []


def test_sanear_remove_codigo_sugerido_fora_do_minideck():
    """LLM alucinou P99 (que não existe no catálogo) — descarta."""
    lacunas = _lacunas_minideck_saude_mental()
    tool_args = {
        "sugestoes_cartas_alternativas": [
            {
                "codigo_original": "P03",
                "codigo_sugerido": "P99",
                "motivo": "alucinação",
            },
        ],
    }
    _sanear_sugestoes(
        tool_args,
        codigos_escolhidos=["P03"],
        lacunas_por_codigo=lacunas,
    )
    assert tool_args["sugestoes_cartas_alternativas"] == []


def test_sanear_remove_sugestao_de_tipo_diferente():
    """Original P03 mas sugerida R05 (tipo REPERTORIO ≠ PROBLEMA) —
    descarta. Sugestão deve ser do mesmo tipo (P→P)."""
    lacunas = _lacunas_minideck_saude_mental()
    tool_args = {
        "sugestoes_cartas_alternativas": [
            {
                "codigo_original": "P03",
                "codigo_sugerido": "R05",
                "motivo": "tipo errado",
            },
        ],
    }
    _sanear_sugestoes(
        tool_args,
        codigos_escolhidos=["P03"],
        lacunas_por_codigo=lacunas,
    )
    assert tool_args["sugestoes_cartas_alternativas"] == []


def test_sanear_limita_em_2_itens():
    """Schema diz maxItems=2; sanear aplica como hard limit."""
    lacunas = _lacunas_minideck_saude_mental()
    tool_args = {
        "sugestoes_cartas_alternativas": [
            {"codigo_original": "P03", "codigo_sugerido": "P05",
             "motivo": "1"},
            {"codigo_original": "K22", "codigo_sugerido": "K11",
             "motivo": "2"},
            {"codigo_original": "A02", "codigo_sugerido": "A01",
             "motivo": "3 — extra"},  # extra
        ],
    }
    _sanear_sugestoes(
        tool_args,
        codigos_escolhidos=["P03", "K22", "A02"],
        lacunas_por_codigo=lacunas,
    )
    assert len(tool_args["sugestoes_cartas_alternativas"]) == 2


def test_sanear_lista_vazia_passa():
    """Lista vazia é feedback positivo legítimo (decisão G.1.7)."""
    tool_args = {"sugestoes_cartas_alternativas": []}
    _sanear_sugestoes(
        tool_args, codigos_escolhidos=["P03"],
        lacunas_por_codigo=_lacunas_minideck_saude_mental(),
    )
    assert tool_args["sugestoes_cartas_alternativas"] == []


def test_sanear_corrige_tipo_invalido_de_sugestoes():
    """Caller passa string em vez de lista — coerção pra lista vazia."""
    tool_args = {"sugestoes_cartas_alternativas": "alguma coisa"}
    _sanear_sugestoes(
        tool_args, codigos_escolhidos=["P03"],
        lacunas_por_codigo=_lacunas_minideck_saude_mental(),
    )
    assert tool_args["sugestoes_cartas_alternativas"] == []


# ──────────────────────────────────────────────────────────────────────
# Render WhatsApp pra modo jogo_redacao
# ──────────────────────────────────────────────────────────────────────

def test_render_jogo_redacao_inclui_5_competencias():
    from redato_backend.whatsapp.render import render_aluno_whatsapp
    out = render_aluno_whatsapp({
        "modo": "jogo_redacao",
        "notas_enem": {"c1": 160, "c2": 120, "c3": 120, "c4": 120, "c5": 80},
        "nota_total_enem": 600,
        "transformacao_cartas": 60,
        "flags": {},
        "sugestoes_cartas_alternativas": [],
        "feedback_aluno": {"acertos": ["a"], "ajustes": ["b"]},
    })
    for c in ("C1 160", "C2 120", "C3 120", "C4 120", "C5 80"):
        assert c in out, f"Faltou {c} em: {out}"
    assert "600/1000" in out


def test_render_inclui_badge_transformacao_separado():
    """Decisão G.1.6: badge visualmente separado da nota ENEM."""
    from redato_backend.whatsapp.render import render_aluno_whatsapp
    out = render_aluno_whatsapp({
        "modo": "jogo_redacao",
        "notas_enem": {"c1": 160, "c2": 160, "c3": 120, "c4": 120, "c5": 120},
        "nota_total_enem": 680,
        "transformacao_cartas": 95,  # autoria plena
        "flags": {},
        "sugestoes_cartas_alternativas": [],
        "feedback_aluno": {"acertos": ["a"], "ajustes": ["b"]},
    })
    assert "Transformação das cartas" in out
    assert "95/100" in out
    assert "autoria plena" in out


def test_render_inclui_sugestoes_quando_populadas():
    from redato_backend.whatsapp.render import render_aluno_whatsapp
    out = render_aluno_whatsapp({
        "modo": "jogo_redacao",
        "notas_enem": {"c1": 160, "c2": 120, "c3": 120, "c4": 120, "c5": 80},
        "nota_total_enem": 600,
        "transformacao_cartas": 50,
        "flags": {},
        "sugestoes_cartas_alternativas": [
            {
                "codigo_original": "P03", "codigo_sugerido": "P05",
                "motivo": "P05 é mais específica.",
            },
        ],
        "feedback_aluno": {"acertos": [], "ajustes": []},
    })
    assert "Cartas alternativas" in out
    assert "P03 → P05" in out


def test_render_omite_sugestoes_quando_vazias():
    """Lista vazia = feedback positivo (decisão G.1.7) — render NÃO
    mostra a seção."""
    from redato_backend.whatsapp.render import render_aluno_whatsapp
    out = render_aluno_whatsapp({
        "modo": "jogo_redacao",
        "notas_enem": {"c1": 200, "c2": 200, "c3": 160, "c4": 160, "c5": 160},
        "nota_total_enem": 880,
        "transformacao_cartas": 90,
        "flags": {},
        "sugestoes_cartas_alternativas": [],
        "feedback_aluno": {"acertos": ["bom"], "ajustes": []},
    })
    assert "Cartas alternativas" not in out


def test_render_badge_indica_copia_literal_quando_baixo():
    from redato_backend.whatsapp.render import render_aluno_whatsapp
    out = render_aluno_whatsapp({
        "modo": "jogo_redacao",
        "notas_enem": {"c1": 120, "c2": 80, "c3": 80, "c4": 80, "c5": 80},
        "nota_total_enem": 440,
        "transformacao_cartas": 10,  # cópia
        "flags": {"copia_literal_das_cartas": True},
        "sugestoes_cartas_alternativas": [],
        "feedback_aluno": {"acertos": [], "ajustes": ["reescrever de verdade"]},
    })
    assert "cópia das cartas" in out or "10/100" in out


# ──────────────────────────────────────────────────────────────────────
# Manual-only — chamada Claude real (skip por padrão)
# ──────────────────────────────────────────────────────────────────────

@pytest.mark.skip(reason="manual_only — chama Claude API real (~$0.05)")
def test_canario_e2e_claude_real_caso_feliz():  # pragma: no cover
    """Smoke contra Claude API real. Roda com:
        DATABASE_URL=... ANTHROPIC_API_KEY=... pytest \
          -k test_canario_e2e_claude_real -v --runxfail

    Espera que pra reescrita autoral substancial, transformacao_cartas
    >= 60 e nota_total_enem >= 600. Custo ~$0.05.
    """
    import os
    if not os.getenv("ANTHROPIC_API_KEY"):
        pytest.skip("ANTHROPIC_API_KEY não definido")

    from redato_backend.missions.router import grade_jogo_redacao
    lacunas = _lacunas_minideck_saude_mental()
    payload = {
        "tema_minideck": "saude_mental",
        "nome_humano_tema": "Saúde Mental",
        "cartas_lacuna_full": list(lacunas.values()),
        "codigos_escolhidos": ["P01", "R01", "K01", "A01", "AC07"],
        "estruturais_por_codigo": {},
        "lacunas_por_codigo": lacunas,
        "texto_montado": (
            "No Brasil, estigma social associado aos transtornos mentais "
            "persiste. OMS demanda atenção. Investimento é estrutural. "
            "Ministério ampliar CAPS."
        ),
        "reescrita_texto": (
            "O estigma cultural em torno dos transtornos mentais "
            "configura-se como um dos principais obstáculos ao acesso "
            "à saúde no Brasil. Segundo a Organização Mundial da "
            "Saúde, mais de 86% das pessoas com transtornos mentais "
            "no país não recebem tratamento adequado, dado que escancara "
            "a urgência do tema. Essa exclusão tem raízes culturais — "
            "o silêncio sobre sofrimento psíquico ainda é regra em "
            "muitas famílias — mas é potencializada pelo desinvestimento "
            "estrutural na rede pública. Cabe ao Ministério da Saúde, "
            "por meio da ampliação efetiva da rede de Centros de "
            "Atenção Psicossocial, garantir que o tratamento "
            "psicológico deixe de ser privilégio e se torne direito "
            "exercido cotidianamente."
        ),
    }
    result = grade_jogo_redacao(payload)
    assert result["transformacao_cartas"] >= 60
    assert result["nota_total_enem"] >= 600
