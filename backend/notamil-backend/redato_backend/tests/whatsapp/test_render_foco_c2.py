"""Testes do renderizador WhatsApp pra modo foco_c2 (M9.2).

Bug que motivou (2026-04-29): aluno turma 2A enviava redação,
Claude retornava JSON foco_c2 válido, mas mensagem WhatsApp era
'Avaliação concluída. (Não consegui formatar o resumo.)'

Causa: render_aluno_whatsapp tinha switch por modo sem branch
foco_c2 — caía no fallback genérico.

Fix: adicionar branch + 2 labels (compreensao_tema, tipo_textual)
em _CRITERIO_LABEL.

Estes testes garantem que:
- Payload foco_c2 NÃO cai no fallback "Não consegui formatar"
- Estrutura espelha foco_c3/c4/c5 (cabeçalho, faixa, critérios,
  feedback)
- Faixas qualitativas seguem escala 0-200 INEP
- Não regrediu render dos outros modos
"""
from __future__ import annotations


# ──────────────────────────────────────────────────────────────────────
# Payloads de referência
# ──────────────────────────────────────────────────────────────────────

def _payload_foco_c2_excelente():
    """Caso real do bug — todos os critérios na banda excelente."""
    return {
        "modo": "foco_c2",
        "missao_id": "RJ2_OF04_MF",
        "rubrica_rej": {
            "compreensao_tema": 88,
            "tipo_textual": 82,
            "repertorio": 90,
        },
        "nota_rej_total": 260,
        "nota_c2_enem": 160,
        "flags": {
            "tangenciamento_tema": False,
            "fuga_tema": False,
            "tipo_textual_inadequado": False,
            "repertorio_de_bolso": False,
            "copia_motivadores_recorrente": False,
        },
        "feedback_aluno": {
            "acertos": [
                "Sua citação está bem integrada ao argumento.",
                "O recorte temático foi respeitado.",
                "A fonte é verificável.",
            ],
            "ajustes": [
                "Pode aprofundar mais a relação citação-tese.",
                "Cuidado com formalidade no fechamento.",
            ],
        },
        "feedback_professor": {
            "padrao_falha": "x", "transferencia_c1": "y", "audit_completo": "z",
        },
    }


def _payload_foco_c2_tangenciamento():
    """Aluno tangenciou — cap C2 ≤ 80 já aplicado por scoring.py."""
    return {
        "modo": "foco_c2",
        "missao_id": "RJ2_OF06_MF",
        "rubrica_rej": {
            "compreensao_tema": 35,
            "tipo_textual": 70,
            "repertorio": 40,
        },
        "nota_rej_total": 145,
        "nota_c2_enem": 80,   # cap aplicado por scoring.py
        "flags": {
            "tangenciamento_tema": True,
            "fuga_tema": False,
            "tipo_textual_inadequado": False,
            "repertorio_de_bolso": False,
            "copia_motivadores_recorrente": False,
        },
        "feedback_aluno": {
            "acertos": ["O texto tem estrutura argumentativa identificável."],
            "ajustes": [
                "O tema pedia recorte específico — você abordou o tema amplo.",
                "Próxima vez, leia a proposta duas vezes antes de definir tese.",
            ],
        },
        "feedback_professor": {
            "padrao_falha": "tangenciamento",
            "transferencia_c1": "leitura crítica do tema",
            "audit_completo": "...",
        },
    }


# ──────────────────────────────────────────────────────────────────────
# Testes principais — bug fix
# ──────────────────────────────────────────────────────────────────────

def test_foco_c2_nao_cai_no_fallback():
    """Bug original: payload foco_c2 ia pro fallback genérico."""
    from redato_backend.whatsapp.render import render_aluno_whatsapp
    out = render_aluno_whatsapp(_payload_foco_c2_excelente())
    assert "Não consegui formatar" not in out
    assert "Avaliação concluída." not in out


def test_foco_c2_cabecalho_com_nota_e_faixa():
    """Cabeçalho deve ter '*C2* — <faixa> (<nota>/200)'."""
    from redato_backend.whatsapp.render import render_aluno_whatsapp
    out = render_aluno_whatsapp(_payload_foco_c2_excelente())
    assert "*C2*" in out
    assert "160/200" in out
    assert "muito boa" in out  # 160 → "muito boa" na escala _faixa_inep


def test_foco_c2_lista_3_criterios_da_rubrica():
    from redato_backend.whatsapp.render import render_aluno_whatsapp
    out = render_aluno_whatsapp(_payload_foco_c2_excelente())
    # Labels humanos dos 3 critérios C2
    assert "Compreensão do tema" in out
    assert "Tipo textual" in out
    assert "Repertório" in out


def test_foco_c2_inclui_feedback_acertos_e_ajustes():
    from redato_backend.whatsapp.render import render_aluno_whatsapp
    out = render_aluno_whatsapp(_payload_foco_c2_excelente())
    assert "*O que ficou bom:*" in out
    assert "Sua citação está bem integrada" in out
    assert "*Pra trabalhar:*" in out
    assert "Pode aprofundar" in out


def test_foco_c2_com_transcricao_inclui_bloco_ocr():
    from redato_backend.whatsapp.render import render_aluno_whatsapp
    texto = "O acesso à educação pública no Brasil enfrenta desafios."
    out = render_aluno_whatsapp(
        _payload_foco_c2_excelente(), texto_transcrito=texto,
    )
    assert "Texto identificado" in out
    assert "ocr errado" in out
    assert "educação pública no Brasil" in out


def test_foco_c2_sem_transcricao_omite_bloco_ocr():
    from redato_backend.whatsapp.render import render_aluno_whatsapp
    out = render_aluno_whatsapp(_payload_foco_c2_excelente())
    assert "Texto identificado" not in out


# ──────────────────────────────────────────────────────────────────────
# Faixa qualitativa por nota
# ──────────────────────────────────────────────────────────────────────

def test_foco_c2_faixa_excelente_nota_200():
    from redato_backend.whatsapp.render import render_aluno_whatsapp
    p = _payload_foco_c2_excelente()
    p["nota_c2_enem"] = 200
    out = render_aluno_whatsapp(p)
    assert "200/200" in out
    assert "excelente" in out


def test_foco_c2_faixa_muito_boa_nota_160():
    from redato_backend.whatsapp.render import render_aluno_whatsapp
    p = _payload_foco_c2_excelente()
    p["nota_c2_enem"] = 160
    out = render_aluno_whatsapp(p)
    assert "muito boa" in out


def test_foco_c2_faixa_regular_nota_120():
    from redato_backend.whatsapp.render import render_aluno_whatsapp
    p = _payload_foco_c2_excelente()
    p["nota_c2_enem"] = 120
    out = render_aluno_whatsapp(p)
    assert "regular" in out


def test_foco_c2_faixa_tangenciamento_capa_em_80():
    """Quando flag tangenciamento_tema=true, scoring.py já capou em 80
    antes do render. Render mostra a nota como veio."""
    from redato_backend.whatsapp.render import render_aluno_whatsapp
    out = render_aluno_whatsapp(_payload_foco_c2_tangenciamento())
    assert "80/200" in out
    assert "em desenvolvimento" in out  # _faixa_inep(80) → "em desenvolvimento"


def test_foco_c2_fuga_tema_zerada():
    """fuga_tema=true, scoring.py zerou. Render mostra 0/200."""
    from redato_backend.whatsapp.render import render_aluno_whatsapp
    p = _payload_foco_c2_excelente()
    p["nota_c2_enem"] = 0
    p["flags"]["fuga_tema"] = True
    out = render_aluno_whatsapp(p)
    assert "0/200" in out
    assert "abaixo do esperado" in out


# ──────────────────────────────────────────────────────────────────────
# Cap de tamanho da mensagem (mobile-friendly)
# ──────────────────────────────────────────────────────────────────────

def test_foco_c2_mensagem_dentro_do_cap_1200_chars():
    from redato_backend.whatsapp.render import render_aluno_whatsapp
    out = render_aluno_whatsapp(_payload_foco_c2_excelente())
    assert len(out) <= 1200


def test_foco_c2_feedback_muito_longo_e_truncado():
    """Mesmo com strings longas, mensagem fica dentro do cap."""
    from redato_backend.whatsapp.render import render_aluno_whatsapp
    p = _payload_foco_c2_excelente()
    p["feedback_aluno"]["acertos"] = ["A" * 500] * 3
    p["feedback_aluno"]["ajustes"] = ["B" * 500] * 3
    out = render_aluno_whatsapp(p)
    assert len(out) <= 1200


# ──────────────────────────────────────────────────────────────────────
# Não regressão dos outros modos
# ──────────────────────────────────────────────────────────────────────

def test_foco_c3_nao_regrediu():
    from redato_backend.whatsapp.render import render_aluno_whatsapp
    p = {
        "modo": "foco_c3",
        "missao_id": "RJ1_OF10_MF",
        "rubrica_rej": {
            "conclusao": 80, "premissa": 80, "exemplo": 80, "fluencia": 80,
        },
        "nota_c3_enem": 160,
        "flags": {
            "andaime_copiado": False, "tese_generica": False,
            "exemplo_redundante": False,
        },
        "feedback_aluno": {"acertos": ["a"], "ajustes": ["b"]},
        "feedback_professor": {
            "padrao_falha": "x", "transferencia_c1": "y", "audit_completo": "z",
        },
    }
    out = render_aluno_whatsapp(p)
    assert "*C3*" in out
    assert "160/200" in out
    assert "Não consegui formatar" not in out


def test_completo_parcial_nao_regrediu():
    from redato_backend.whatsapp.render import render_aluno_whatsapp
    p = {
        "modo": "completo_parcial",
        "missao_id": "RJ1_OF13_MF",
        "rubrica_rej": {
            "topico_frasal": 80, "argumento": 80,
            "repertorio": 80, "coesao": 80,
        },
        "notas_enem": {
            "c1": 160, "c2": 160, "c3": 160, "c4": 160, "c5": "não_aplicável",
        },
        "nota_total_parcial": 640,
        "flags": {
            "topico_e_pergunta": False, "repertorio_de_bolso": False,
            "argumento_superficial": False,
            "coesao_perfeita_sem_progressao": False,
        },
        "feedback_aluno": {"acertos": ["a"], "ajustes": ["b"]},
        "feedback_professor": {
            "padrao_falha": "x", "transferencia_c1": "y", "audit_completo": "z",
        },
    }
    out = render_aluno_whatsapp(p)
    assert "640/800" in out
    assert "C5 não se aplica" in out
    assert "Não consegui formatar" not in out


def test_modo_desconhecido_ainda_cai_no_fallback():
    """Garante que o fallback continua funcionando pra modos
    realmente não suportados."""
    from redato_backend.whatsapp.render import render_aluno_whatsapp
    out = render_aluno_whatsapp({"modo": "modo_inexistente"})
    assert "Não consegui formatar" in out


def test_args_nao_dict_retorna_erro_amigavel():
    from redato_backend.whatsapp.render import render_aluno_whatsapp
    out = render_aluno_whatsapp(None)  # type: ignore[arg-type]
    assert "Algo deu errado" in out


# ──────────────────────────────────────────────────────────────────────
# Catalogo de critérios — labels novos não quebraram os antigos
# ──────────────────────────────────────────────────────────────────────

def test_criterio_label_inclui_c2_e_preserva_outros():
    from redato_backend.whatsapp.render import _CRITERIO_LABEL
    # Novos (M9.2)
    assert _CRITERIO_LABEL["compreensao_tema"] == "Compreensão do tema"
    assert _CRITERIO_LABEL["tipo_textual"] == "Tipo textual"
    # Existentes preservados
    assert _CRITERIO_LABEL["conclusao"] == "Conclusão"
    assert _CRITERIO_LABEL["agente"] == "Agente"
    assert _CRITERIO_LABEL["topico_frasal"] == "Tópico frasal"
    assert _CRITERIO_LABEL["repertorio"] == "Repertório"
