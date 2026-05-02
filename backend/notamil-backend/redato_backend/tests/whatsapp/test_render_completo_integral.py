"""Testes do renderer WhatsApp pro modo OF14 (completo_integral).

Bug que motivou (2026-05-01): após migração FT (commit 8554146),
mensagem do aluno virou "Avaliação concluída. (Não consegui formatar
o resumo.)". Logs mostraram que `_claude_grade_essay` retornava
tool_args com 5 cN_audit válidos, mas `render_aluno_whatsapp` caía
no fallback genérico.

Causa: dispatch em `render_aluno_whatsapp` exigia
`"essay_analysis" in args`, e o FT não retorna esse campo (schema
reduzido focado em audit por competência).

Fix: dispatch agora usa `_is_completo_integral(args)` que detecta OF14
por presença de cN_audit dicts com `nota` int. `_render_completo_integral`
foi reescrito pra renderizar nota + feedback_text + evidências por
competência (FT) com fallback pra `feedback_text` top-level (v2 legado).

Esses testes garantem:
- Payload FT completo NÃO cai no fallback "Não consegui formatar"
- Payload FT parcial (faltam 1-2 cN_audit) renderiza sem erro
- Payload v2 legado (Claude com essay_analysis + feedback_text solto)
  ainda renderiza
- Não regride foco_c2/c3/c4/c5 nem completo_parcial
- Render fail-safe: KeyError em qualquer ponto cai num fallback
  amigável + log
"""
from __future__ import annotations

from redato_backend.whatsapp.render import (
    render_aluno_whatsapp,
    _is_completo_integral,
)


# ──────────────────────────────────────────────────────────────────────
# Payloads de referência
# ──────────────────────────────────────────────────────────────────────

def _payload_ft_completo():
    """Schema FT BTBOS5VF — 5 cN_audit completos."""
    return {
        "c1_audit": {
            "nota": 160,
            "feedback_text": (
                "Texto bem escrito, com poucos desvios gramaticais. "
                "Atente-se à concordância em períodos longos."
            ),
            "evidencias": [
                {
                    "trecho": "a pesquisa mostraram resultados",
                    "comentario": "concordância: 'a pesquisa mostrou'",
                },
            ],
        },
        "c2_audit": {
            "nota": 200,
            "feedback_text": "Repertório legitimado e produtivo.",
            "evidencias": [],
        },
        "c3_audit": {
            "nota": 160,
            "feedback_text": "Argumentação progressiva. Tese clara.",
            "evidencias": [],
        },
        "c4_audit": {
            "nota": 120,
            "feedback_text": "Conectivos adequados mas pouca diversidade.",
            "evidencias": [],
        },
        "c5_audit": {
            "nota": 200,
            "feedback_text": "Proposta concreta com agente e finalidade.",
            "evidencias": [],
        },
    }


def _payload_ft_parcial():
    """Schema FT com 3 das 5 cN_audit (parser foi parcial mas
    aceitável — adapter não rejeitou). Renderer NÃO pode quebrar."""
    return {
        "c1_audit": {"nota": 80, "feedback_text": "Vários desvios.", "evidencias": []},
        "c2_audit": {"nota": 120, "feedback_text": "Repertório limitado.", "evidencias": []},
        "c3_audit": {"nota": 120, "feedback_text": "Argumentação rasa.", "evidencias": []},
        # c4_audit ausente
        # c5_audit ausente
    }


def _payload_v2_legado():
    """Schema v2 (Claude Sonnet 4.6 — fallback de
    REDATO_OF14_BACKEND=claude). Tem essay_analysis +
    feedback_text top-level + cN_audit com 12+ campos cada."""
    return {
        "essay_analysis": {"theme": "Direitos humanos", "word_count": 250},
        "preanulation_checks": {"should_annul": False},
        "feedback_text": (
            "Síntese geral. Pontos fortes A, B. Próximo passo: revisar C."
        ),
        "c1_audit": {
            "nota": 120,
            "desvios_gramaticais_count": 3,
            "erros_ortograficos_count": 1,
            "threshold_check": {"applies_nota_3": True},
        },
        "c2_audit": {"nota": 160, "tres_partes_completas": True},
        "c3_audit": {"nota": 120, "has_explicit_thesis": True},
        "c4_audit": {"nota": 80, "connector_variety_count": 2},
        "c5_audit": {"nota": 120, "respeita_direitos_humanos": True},
        "priorization": {"priority_1": {"actions": ["revisar concordância"]}},
        "meta_checks": {"total_calculated": 600},
    }


# ──────────────────────────────────────────────────────────────────────
# Tests — _is_completo_integral
# ──────────────────────────────────────────────────────────────────────

def test_is_completo_integral_aceita_ft_completo():
    assert _is_completo_integral(_payload_ft_completo()) is True


def test_is_completo_integral_aceita_ft_parcial_3_de_5():
    assert _is_completo_integral(_payload_ft_parcial()) is True


def test_is_completo_integral_aceita_v2_legado():
    assert _is_completo_integral(_payload_v2_legado()) is True


def test_is_completo_integral_rejeita_foco_c2():
    """foco_c2 só tem nota_c2_enem, não c1_audit/c2_audit dicts."""
    foco_c2 = {
        "modo": "foco_c2",
        "nota_c2_enem": 160,
        "rubrica_rej": {"compreensao_tema": 88},
    }
    assert _is_completo_integral(foco_c2) is False


def test_is_completo_integral_rejeita_dict_vazio():
    assert _is_completo_integral({}) is False
    assert _is_completo_integral({"foo": "bar"}) is False


def test_is_completo_integral_rejeita_apenas_2_audits():
    """Threshold é 3 audits válidos pra evitar falso positivo."""
    p = {
        "c1_audit": {"nota": 100},
        "c2_audit": {"nota": 100},
        "c3_audit": {"sem_nota": True},
    }
    assert _is_completo_integral(p) is False


# ──────────────────────────────────────────────────────────────────────
# Tests — render OF14 (cenário FT, parcial, v2)
# ──────────────────────────────────────────────────────────────────────

def test_render_ft_completo_nao_cai_no_fallback():
    """Bug do 01/05: payload FT virava 'Não consegui formatar'.
    Fix: dispatch usa _is_completo_integral em vez de essay_analysis."""
    out = render_aluno_whatsapp(_payload_ft_completo())
    assert "Não consegui formatar" not in out


def test_render_ft_completo_inclui_nota_total_e_faixa():
    """Render mostra '840/1000' (160+200+160+120+200) + faixa."""
    out = render_aluno_whatsapp(_payload_ft_completo())
    assert "840/1000" in out
    assert "muito boa" in out  # 840 cai em "muito boa" (>=801)


def test_render_ft_completo_lista_5_competencias_inline():
    """Linha em itálico com C1 160 · C2 200 · ... · C5 200."""
    out = render_aluno_whatsapp(_payload_ft_completo())
    for trecho in ("C1 160", "C2 200", "C3 160", "C4 120", "C5 200"):
        assert trecho in out, f"esperado '{trecho}' no render"


def test_render_ft_completo_inclui_feedback_text_por_competencia():
    """Cada cN_audit.feedback_text aparece resumido na mensagem."""
    out = render_aluno_whatsapp(_payload_ft_completo())
    assert "Texto bem escrito" in out  # c1
    assert "Repertório legitimado" in out  # c2
    assert "Argumentação progressiva" in out  # c3


def test_render_ft_completo_inclui_evidencia_em_c1():
    """Evidência de C1 (única no payload de teste) renderiza com
    formato '_"trecho"_ → comentário'."""
    out = render_aluno_whatsapp(_payload_ft_completo())
    assert '"a pesquisa mostraram resultados"' in out
    assert "concordância:" in out


def test_render_ft_parcial_nao_quebra():
    """Schema parcial (3/5 cN_audit) renderiza sem erro."""
    out = render_aluno_whatsapp(_payload_ft_parcial())
    assert "Não consegui formatar" not in out
    # Faixa total = 320 (80+120+120) → "insuficiente" (<401)
    assert "320/1000" in out
    assert "insuficiente" in out
    # Notas presentes aparecem; ausentes viram "—"
    assert "C1 80" in out
    assert "C4 —" in out
    assert "C5 —" in out


def test_render_v2_legado_usa_feedback_text_top_level():
    """Schema v2 legado (Claude Sonnet) — feedback_text top-level
    deve aparecer (cN_audit não tem feedback_text próprio)."""
    out = render_aluno_whatsapp(_payload_v2_legado())
    assert "Não consegui formatar" not in out
    assert "Síntese geral" in out  # do feedback_text top-level
    # Faixa total = 600 (120+160+120+80+120) → "em desenvolvimento"
    assert "600/1000" in out


def test_render_v2_legado_nao_acessa_campos_inexistentes_no_ft():
    """Renderer não pode quebrar se cN_audit do v2 vier com 12+ campos
    auxiliares (desvios_gramaticais_count, threshold_check, etc.) —
    só deve ler `nota` e `feedback_text`."""
    out = render_aluno_whatsapp(_payload_v2_legado())
    # Não deve aparecer nada do schema v2 detalhado
    assert "desvios_gramaticais_count" not in out
    assert "threshold_check" not in out


# ──────────────────────────────────────────────────────────────────────
# Tests — defesa em profundidade (render fail-safe)
# ──────────────────────────────────────────────────────────────────────

def test_render_dict_invalido_retorna_msg_amigavel():
    """Não-dict → mensagem amigável (já existia, garante que não
    regrediu com a guard global nova)."""
    assert render_aluno_whatsapp(None) is not None  # type: ignore[arg-type]
    assert "Algo deu errado" in render_aluno_whatsapp("xyz")  # type: ignore[arg-type]


def test_render_payload_bizarro_nao_explode():
    """Edge case extremo: cN_audit existe mas não é dict (LLM bagunçado).
    Renderer deve cair no fallback amigável, não no 500."""
    bizarro = {
        "c1_audit": "string em vez de dict",
        "c2_audit": ["lista"],
        "c3_audit": 42,
    }
    # _is_completo_integral retorna False → cai no fallback
    # "Não consegui formatar" (esperado pra payload tão bagunçado).
    out = render_aluno_whatsapp(bizarro)
    assert isinstance(out, str)
    assert len(out) > 0


# ──────────────────────────────────────────────────────────────────────
# Tests — não regrediu outros modos
# ──────────────────────────────────────────────────────────────────────

def test_render_foco_c2_continua_funcionando():
    """Smoke contra regressão do dispatch novo. Mode foco_c2 deve
    seguir _render_foco, não _render_completo_integral."""
    foco_c2 = {
        "modo": "foco_c2",
        "missao_id": "RJ2_OF04_MF",
        "rubrica_rej": {
            "compreensao_tema": 80,
            "tipo_textual": 75,
            "repertorio": 85,
        },
        "nota_rej_total": 240,
        "nota_c2_enem": 160,
        "flags": {},
        "feedback_aluno": {
            "acertos": ["bom uso de repertório"],
            "ajustes": ["aprofundar tese"],
        },
    }
    out = render_aluno_whatsapp(foco_c2)
    assert "Não consegui formatar" not in out
    # Não deve ser tratado como completo_integral (que mostraria
    # "Redação completa")
    assert "Redação completa" not in out


# ──────────────────────────────────────────────────────────────────────
# Truncamento (Passo 7b — fix em 2026-05-01)
# ──────────────────────────────────────────────────────────────────────
#
# Antes do fix: `_OF14_FB_CHARS=200` cortava 5x por mensagem com
# feedback típico do FT (250-350 chars). Investigação:
# docs/redato/v3/INVESTIGATION_truncamento_whatsapp.md.
# Fix: cap pra 450 (cobre 95% dos casos), `_OF14_TRECHO_CHARS` pra 120,
# `_OF14_COMENT_CHARS` pra 140, e `_truncate` ganha janela de busca
# proporcional ao limite + fallback pra pontuação.

_FB_FT_TIPICO_280 = (
    "Texto bem escrito, com poucos desvios gramaticais detectáveis. "
    "Atente-se à concordância em períodos longos para subir a nota. "
    "Trabalhe também as marcas de oralidade ainda presentes, "
    "especialmente no terceiro parágrafo."
)


def test_render_of14_feedback_tipico_ft_nao_trunca():
    """Feedback típico do FT (250-300 chars) deve renderizar inteiro
    sem ellipsis. Antes do fix, cap=200 cortava em todo feedback."""
    payload = {
        f"c{i}_audit": {
            "nota": 160, "feedback_text": _FB_FT_TIPICO_280,
            "evidencias": [],
        }
        for i in range(1, 6)
    }
    out = render_aluno_whatsapp(payload)
    assert "…" not in out, (
        f"feedback típico FT (~280 chars) ainda truncando — out:\n{out}"
    )
    # Cada feedback original aparece inteiro (busca por substring única)
    assert "especialmente no terceiro parágrafo." in out


def test_render_of14_feedback_acima_do_cap_trunca_uma_vez_por_comp():
    """Feedback acima do cap (450 chars) ainda corta — esperado.
    Cada competência tem 1 ellipsis. Total 5."""
    fb_grande = _FB_FT_TIPICO_280 * 3  # ~654 chars (acima de 450)
    assert len(fb_grande) > 450  # confirma que está acima do cap
    payload = {
        f"c{i}_audit": {
            "nota": 160, "feedback_text": fb_grande, "evidencias": [],
        }
        for i in range(1, 6)
    }
    out = render_aluno_whatsapp(payload)
    # 1 ellipsis por competência (5 totais), porque cada um corta 1x
    assert out.count("…") == 5, (
        f"esperado 5 ellipses pra feedback >cap, got {out.count('…')}"
    )


def test_truncate_corta_em_fronteira_de_palavra_quando_possivel():
    """Frase normal com espaços deve cortar em fronteira de palavra,
    não no meio. Janela de busca = 50% do limit (vs 30 fixos antes)."""
    from redato_backend.whatsapp.render import _truncate
    txt = "frase normal que tem palavras que devem cortar em fronteira de palavra"
    out = _truncate(txt, 30)
    # Antes do '…' deve haver fim de palavra (sem letra cortada)
    body = out.rstrip("…")
    # Última char antes do '…' não deve ser meio de palavra (heurística:
    # se cabe nos limites, palavra inteira aparece). Verifica que
    # o corte casa com fronteira do input.
    assert txt.startswith(body), f"corte fora do input: {body!r}"
    # body termina em palavra completa do input — garante que a próxima
    # char no input ORIGINAL é espaço (ou body é o input inteiro).
    next_idx = len(body)
    if next_idx < len(txt):
        # O caractere após o corte deve ser espaço (corte limpo)
        # OU pontuação (também aceita).
        assert txt[next_idx] in (" ", ".", ",", ";", ":", "-"), (
            f"corte no meio de palavra: prev={body[-10:]!r}, "
            f"next_char={txt[next_idx]!r}"
        )


def test_truncate_palavra_gigante_sem_espaco_corta_mas_termina_com_ellipsis():
    """Palavra de 60 chars sem espaço próximo: aceita corte mid-palavra,
    mas garante que termina com '…' e não cai em loop infinito."""
    from redato_backend.whatsapp.render import _truncate
    txt = "x" + "y" * 100 + "z"  # 102 chars contínuos sem espaço
    out = _truncate(txt, 30)
    assert len(out) <= 30
    assert out.endswith("…")
    # Output não cai abaixo do mínimo razoável (≥ 1/3 do limit)
    assert len(out) >= 10


def test_truncate_usa_pontuacao_como_fronteira():
    """Fallback pra '.' quando não há espaço na zona ideal."""
    from redato_backend.whatsapp.render import _truncate
    txt = "frase.um.dois.tres.quatro.cinco.seis.sete.oito.nove.dez"
    out = _truncate(txt, 30)
    body = out.rstrip("…")
    # Verifica que cortou em '.' (último char do body é palavra completa)
    next_idx = len(body)
    if next_idx < len(txt):
        assert txt[next_idx] == ".", (
            f"esperado corte em ponto, got next_char={txt[next_idx]!r}"
        )
