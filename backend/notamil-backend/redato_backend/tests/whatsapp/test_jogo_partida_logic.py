"""Testes do módulo `whatsapp/jogo_partida.py` — lógica pura (Fase 2 passo 4).

Sem DB. Cobre parsing, classificação, validação e montagem do texto.
Camada DB-aware fica em `test_bot_jogo_partida.py` (skip sem
DATABASE_URL).
"""
from __future__ import annotations

import pytest


# ──────────────────────────────────────────────────────────────────────
# Helpers — fixtures de catálogo
# ──────────────────────────────────────────────────────────────────────

def _ctx_minimo():
    """Constrói ContextoValidacao com 10 estruturais (1 por seção) +
    cartas do minideck cobrindo todos os tipos. Suficiente pra testar
    happy path da validação."""
    from redato_backend.whatsapp.jogo_partida import (
        CartaEstruturalSnapshot, CartaLacunaSnapshot, ContextoValidacao,
    )
    estr = {
        "E01": CartaEstruturalSnapshot(
            "E01", "ABERTURA", "AZUL",
            "No Brasil, [PROBLEMA] persiste. Conforme [REPERTORIO], "
            "demanda atenção.",
            ("PROBLEMA", "REPERTORIO"),
        ),
        "E10": CartaEstruturalSnapshot(
            "E10", "TESE", "AZUL",
            "Cenário impulsionado por [PALAVRA_CHAVE].",
            ("PALAVRA_CHAVE",),
        ),
        "E17": CartaEstruturalSnapshot(
            "E17", "TOPICO_DEV1", "AMARELO",
            "Em primeira análise, [PROBLEMA] liga-se a [PALAVRA_CHAVE].",
            ("PROBLEMA", "PALAVRA_CHAVE"),
        ),
        "E19": CartaEstruturalSnapshot(
            "E19", "ARGUMENTO_DEV1", "AMARELO",
            "Tal realidade é agravada por [PALAVRA_CHAVE].",
            ("PALAVRA_CHAVE",),
        ),
        "E21": CartaEstruturalSnapshot(
            "E21", "REPERTORIO_DEV1", "AMARELO",
            "Comprovado por [REPERTORIO]. [PALAVRA_CHAVE] demanda ação.",
            ("REPERTORIO", "PALAVRA_CHAVE"),
        ),
        "E33": CartaEstruturalSnapshot(
            "E33", "TOPICO_DEV2", "VERDE",
            "Outro fator: [PALAVRA_CHAVE] amplia [PROBLEMA].",
            ("PALAVRA_CHAVE", "PROBLEMA"),
        ),
        "E35": CartaEstruturalSnapshot(
            "E35", "ARGUMENTO_DEV2", "VERDE",
            "Há sérios prejuízos para [PALAVRA_CHAVE].",
            ("PALAVRA_CHAVE",),
        ),
        "E37": CartaEstruturalSnapshot(
            "E37", "REPERTORIO_DEV2", "VERDE",
            "Análise encontra respaldo em [REPERTORIO].",
            ("REPERTORIO",),
        ),
        "E49": CartaEstruturalSnapshot(
            "E49", "RETOMADA", "LARANJA",
            "Evidencia-se que [PROBLEMA] exige [ACAO_MEIO].",
            ("PROBLEMA", "ACAO_MEIO"),
        ),
        "E51": CartaEstruturalSnapshot(
            "E51", "PROPOSTA", "LARANJA",
            "[AGENTE] tem como prioridade [ACAO_MEIO].",
            ("AGENTE", "ACAO_MEIO"),
        ),
    }
    lac = {
        "P01": CartaLacunaSnapshot("P01", "PROBLEMA", "estigma social"),
        "P02": CartaLacunaSnapshot("P02", "PROBLEMA", "falta de acesso"),
        "R01": CartaLacunaSnapshot("R01", "REPERTORIO", "OMS"),
        "R05": CartaLacunaSnapshot("R05", "REPERTORIO", "IBGE 2022"),
        "K01": CartaLacunaSnapshot("K01", "PALAVRA_CHAVE", "investimento"),
        "K11": CartaLacunaSnapshot("K11", "PALAVRA_CHAVE", "estigma"),
        "K22": CartaLacunaSnapshot("K22", "PALAVRA_CHAVE", "preconceito"),
        "A01": CartaLacunaSnapshot("A01", "AGENTE", "Ministério"),
        "AC07": CartaLacunaSnapshot("AC07", "ACAO", "ampliar CAPS"),
        "ME04": CartaLacunaSnapshot("ME04", "MEIO", "via emendas"),
        "F02": CartaLacunaSnapshot("F02", "FIM", "garantir tratamento"),
    }
    return ContextoValidacao(
        estruturais_por_codigo=estr, lacunas_por_codigo=lac,
        minideck_tema="saude_mental",
        minideck_nome_humano="Saúde Mental",
    )


# ──────────────────────────────────────────────────────────────────────
# parse_codigos
# ──────────────────────────────────────────────────────────────────────

def test_parse_codigos_separadores_mistos():
    from redato_backend.whatsapp.jogo_partida import parse_codigos
    text = "E01, E10\nE17 E19, P01 R05  K11; A01 AC07-ME04 F02"
    out = parse_codigos(text)
    # Não casa K11; (com ;), parser deveria ignorar separador
    assert "E01" in out
    assert "P01" in out
    assert "AC07" in out
    assert "ME04" in out


def test_parse_codigos_case_insensitive_normaliza_pra_upper():
    from redato_backend.whatsapp.jogo_partida import parse_codigos
    out = parse_codigos("e01, p03, ac07, me04")
    assert out == ["E01", "P03", "AC07", "ME04"]


def test_parse_codigos_AC_ME_nao_quebra_em_A_M():
    """Sanity crítica: regex ordena AC e ME ANTES de A e M sozinhos.
    `AC07` deve casar como AC07, não como A0+ algo."""
    from redato_backend.whatsapp.jogo_partida import parse_codigos
    out = parse_codigos("AC07 ME04 A01 F02")
    assert "AC07" in out
    assert "ME04" in out
    assert "A01" in out
    assert "F02" in out
    # Sem fragmentação — não deve aparecer "A07" ou "M04" como
    # códigos separados
    assert "A07" not in out
    assert "M04" not in out


def test_parse_codigos_texto_sem_codigos():
    from redato_backend.whatsapp.jogo_partida import parse_codigos
    assert parse_codigos("oi tudo bem?") == []
    assert parse_codigos("") == []


def test_codigo_to_tipo():
    from redato_backend.whatsapp.jogo_partida import codigo_to_tipo
    assert codigo_to_tipo("E01") == "ESTRUTURAL"
    assert codigo_to_tipo("P15") == "PROBLEMA"
    assert codigo_to_tipo("R01") == "REPERTORIO"
    assert codigo_to_tipo("K30") == "PALAVRA_CHAVE"
    assert codigo_to_tipo("A10") == "AGENTE"
    assert codigo_to_tipo("AC12") == "ACAO"
    assert codigo_to_tipo("ME01") == "MEIO"
    assert codigo_to_tipo("F10") == "FIM"
    assert codigo_to_tipo("X01") is None


# ──────────────────────────────────────────────────────────────────────
# validar_partida — happy path + erros
# ──────────────────────────────────────────────────────────────────────

def _codigos_completos():
    """Lista de codigos cobrindo todas as 10 seções + lacunas P/R/K +
    todos os 4 tipos de proposta. Validação deve passar sem warnings."""
    return [
        "E01", "E10", "E17", "E19", "E21",
        "E33", "E35", "E37", "E49", "E51",
        "P01", "R01", "K01", "A01", "AC07", "ME04", "F02",
    ]


def test_validar_caso_feliz_completo():
    from redato_backend.whatsapp.jogo_partida import validar_partida
    ctx = _ctx_minimo()
    res = validar_partida(_codigos_completos(), ctx)
    assert res.ok is True, res.mensagem_erro
    assert res.warnings == []
    assert len(res.estruturais_em_ordem) == 10
    # Ordem do tabuleiro respeitada (ABERTURA primeiro)
    assert res.estruturais_em_ordem[0] == "E01"
    assert res.estruturais_em_ordem[-1] == "E51"


def test_validar_proposta_com_3_tipos_aceita_com_warning():
    """Faltar 1 lacuna da proposta (G.1.1) — warning, não erro."""
    from redato_backend.whatsapp.jogo_partida import validar_partida
    ctx = _ctx_minimo()
    codigos = [c for c in _codigos_completos() if c != "F02"]
    res = validar_partida(codigos, ctx)
    assert res.ok is True
    assert any("FIM" in w or "lacuna" in w for w in res.warnings), res.warnings
    assert "FIM" in res.placeholders_vazios


def test_validar_proposta_com_2_tipos_aceita_com_warning():
    from redato_backend.whatsapp.jogo_partida import validar_partida
    ctx = _ctx_minimo()
    # Tira ME04 e F02 — sobra A01 + AC07 (2 tipos)
    codigos = [c for c in _codigos_completos() if c not in ("ME04", "F02")]
    res = validar_partida(codigos, ctx)
    assert res.ok is True
    assert len(res.placeholders_vazios) == 2


def test_validar_proposta_com_1_tipo_erro():
    """< 2 lacunas da proposta → erro (G.1.1)."""
    from redato_backend.whatsapp.jogo_partida import validar_partida
    ctx = _ctx_minimo()
    codigos = [c for c in _codigos_completos()
               if c not in ("AC07", "ME04", "F02")]
    res = validar_partida(codigos, ctx)
    assert res.ok is False
    assert "Faltam" in res.mensagem_erro
    assert "proposta" in res.mensagem_erro.lower()


def test_validar_codigo_inexistente_no_minideck():
    """P99 não existe no minideck — erro com nome do tema."""
    from redato_backend.whatsapp.jogo_partida import validar_partida
    ctx = _ctx_minimo()
    codigos = _codigos_completos() + ["P99"]
    res = validar_partida(codigos, ctx)
    assert res.ok is False
    assert "P99" in res.mensagem_erro
    assert "Saúde Mental" in res.mensagem_erro


def test_validar_falta_secao_obrigatoria():
    """Sem ABERTURA — erro com nome legível da seção."""
    from redato_backend.whatsapp.jogo_partida import validar_partida
    ctx = _ctx_minimo()
    codigos = [c for c in _codigos_completos() if c != "E01"]
    res = validar_partida(codigos, ctx)
    assert res.ok is False
    assert "Abertura" in res.mensagem_erro


def test_validar_lacuna_pre_obrigatoria_em_dev_falta():
    """Estrutural pediu [PROBLEMA] mas aluno não escolheu P##."""
    from redato_backend.whatsapp.jogo_partida import validar_partida
    ctx = _ctx_minimo()
    codigos = [c for c in _codigos_completos() if c != "P01"]
    res = validar_partida(codigos, ctx)
    assert res.ok is False
    assert "P##" in res.mensagem_erro
    assert "[PROBLEMA]" in res.mensagem_erro


def test_validar_codigo_duplicado_warning_nao_erro():
    """E01 mandado 2x — aceita com warning."""
    from redato_backend.whatsapp.jogo_partida import validar_partida
    ctx = _ctx_minimo()
    codigos = ["E01"] + _codigos_completos()
    res = validar_partida(codigos, ctx)
    assert res.ok is True
    assert any("repetiu" in w.lower() for w in res.warnings)


def test_validar_2_estruturais_mesma_secao_warning():
    """Aluno mandou E01 + outra carta da seção ABERTURA por engano —
    aceita com warning + considera primeira."""
    from redato_backend.whatsapp.jogo_partida import (
        CartaEstruturalSnapshot, validar_partida,
    )
    ctx = _ctx_minimo()
    # Adiciona uma 2ª estrutural na seção ABERTURA
    estr_modificado = dict(ctx.estruturais_por_codigo)
    estr_modificado["E02"] = CartaEstruturalSnapshot(
        "E02", "ABERTURA", "AZUL",
        "De acordo com [REPERTORIO], [PROBLEMA] é grave.",
        ("REPERTORIO", "PROBLEMA"),
    )
    from redato_backend.whatsapp.jogo_partida import ContextoValidacao
    ctx2 = ContextoValidacao(
        estruturais_por_codigo=estr_modificado,
        lacunas_por_codigo=ctx.lacunas_por_codigo,
        minideck_tema=ctx.minideck_tema,
        minideck_nome_humano=ctx.minideck_nome_humano,
    )
    codigos = ["E01", "E02"] + _codigos_completos()[1:]
    res = validar_partida(codigos, ctx2)
    assert res.ok is True
    assert any("Abertura" in w for w in res.warnings)


# ──────────────────────────────────────────────────────────────────────
# montar_texto_montado
# ──────────────────────────────────────────────────────────────────────

def test_montar_substitui_todos_placeholders():
    from redato_backend.whatsapp.jogo_partida import (
        montar_texto_montado, validar_partida,
    )
    ctx = _ctx_minimo()
    res = validar_partida(_codigos_completos(), ctx)
    assert res.ok
    texto = montar_texto_montado(
        res.estruturais_em_ordem, res.lacunas_por_tipo, ctx,
    )
    # Não deve sobrar nenhum placeholder
    assert "[PROBLEMA]" not in texto
    assert "[REPERTORIO]" not in texto
    assert "[PALAVRA_CHAVE]" not in texto
    assert "[AGENTE]" not in texto
    assert "[ACAO_MEIO]" not in texto
    # Conteúdos das cartas escolhidas presentes
    assert "estigma social" in texto    # P01
    assert "OMS" in texto               # R01
    assert "Ministério" in texto        # A01
    assert "ampliar CAPS" in texto      # AC07
    assert "via emendas" in texto       # ME04


def test_montar_proposta_incompleta_marca_a_definir():
    """Aluno faltou ME04 e F02 — montador marca [a definir] na
    proposta (decisão B.1 passo 4)."""
    from redato_backend.whatsapp.jogo_partida import (
        montar_texto_montado, validar_partida,
    )
    ctx = _ctx_minimo()
    codigos = [c for c in _codigos_completos() if c not in ("ME04", "F02")]
    res = validar_partida(codigos, ctx)
    assert res.ok
    texto = montar_texto_montado(
        res.estruturais_em_ordem, res.lacunas_por_tipo, ctx,
        placeholders_vazios=res.placeholders_vazios,
    )
    # AC07 ainda está, mas como ME está em placeholders_vazios, o
    # ACAO_MEIO da E51 vira só "ampliar CAPS" sem o "via emendas".
    # E E49 que tem ACAO_MEIO sem AC e sem ME → "[a definir]"
    # (A01 na proposta E51 ainda preenche o [AGENTE]).
    assert "Ministério" in texto    # A01 — proposta A##
    assert "ampliar CAPS" in texto  # AC07 ainda existe
    # ME está vazio então não deve aparecer "via emendas"
    assert "via emendas" not in texto


def test_montar_palavra_chave_em_2_slots_distintos():
    """E04 do mundo real tem [PALAVRA_CHAVE] 2x. Montador deve
    distribuir cartas distintas em cada slot — não repetir a mesma."""
    from redato_backend.whatsapp.jogo_partida import (
        CartaEstruturalSnapshot, ContextoValidacao,
        montar_texto_montado,
    )
    ctx = _ctx_minimo()
    # Substitui E10 por uma versão com 2x [PALAVRA_CHAVE]
    estr_modificado = dict(ctx.estruturais_por_codigo)
    estr_modificado["E10"] = CartaEstruturalSnapshot(
        "E10", "TESE", "AZUL",
        "Origina-se de [PALAVRA_CHAVE] e [PALAVRA_CHAVE], "
        "que se retroalimentam.",
        ("PALAVRA_CHAVE", "PALAVRA_CHAVE"),
    )
    ctx2 = ContextoValidacao(
        estruturais_por_codigo=estr_modificado,
        lacunas_por_codigo=ctx.lacunas_por_codigo,
        minideck_tema=ctx.minideck_tema,
        minideck_nome_humano=ctx.minideck_nome_humano,
    )
    estruturais_em_ordem = [
        "E01", "E10", "E17", "E19", "E21",
        "E33", "E35", "E37", "E49", "E51",
    ]
    lacunas_por_tipo = {
        "PROBLEMA": ["P01"], "REPERTORIO": ["R01"],
        "PALAVRA_CHAVE": ["K01", "K11", "K22"],
        "AGENTE": ["A01"], "ACAO": ["AC07"],
        "MEIO": ["ME04"], "FIM": ["F02"],
    }
    texto = montar_texto_montado(
        estruturais_em_ordem, lacunas_por_tipo, ctx2,
    )
    # E10 expandida deve ter "investimento e estigma" (K01 + K11) —
    # 2 slots consumiram K01 e K11 distintas
    assert "investimento" in texto
    assert "estigma" in texto


# ──────────────────────────────────────────────────────────────────────
# classificar_codigos
# ──────────────────────────────────────────────────────────────────────

def test_classificar_codigos_agrupa_por_tipo():
    from redato_backend.whatsapp.jogo_partida import classificar_codigos
    out = classificar_codigos(["E01", "P03", "P05", "K11", "AC07"])
    assert out["ESTRUTURAL"] == ["E01"]
    assert out["PROBLEMA"] == ["P03", "P05"]
    assert out["PALAVRA_CHAVE"] == ["K11"]
    assert out["ACAO"] == ["AC07"]
    assert "AGENTE" not in out  # não tem A##


# ──────────────────────────────────────────────────────────────────────
# Passo 7b — Acumulação de códigos parciais entre tentativas
# (commit fix(jogo) 2026-05-01). Bug original: quando aluno mandava
# 17 códigos com 1 inválido, validar_partida fazia fail-fast, descartava
# os 16 válidos. Aluno corrigia só o errado — mas os 16 válidos não
# estavam mais em lugar nenhum, então a 2ª chamada falhava por falta
# de estruturais.
# Fix: validar_partida aceita `codigos_existentes_acumulados` e popula
# `codigos_aceitos` em qualquer return ok=False — caller (bot.py)
# persiste em `cartas_escolhidas.codigos_parciais` e merge na próxima.
# ──────────────────────────────────────────────────────────────────────

def test_validar_partida_acumula_parciais_step1_falha():
    """1ª tentativa: 16 válidos + 1 desconhecido (X99). Validação falha
    no Step 1 mas codigos_aceitos traz os 16 válidos."""
    from redato_backend.whatsapp.jogo_partida import validar_partida
    ctx = _ctx_minimo()
    out = validar_partida(
        ["E01", "E10", "E17", "E19", "E21", "E33", "E35", "E37",
         "E49", "E51", "P01", "R01", "K01", "A01", "AC07", "ME04",
         "X99"],  # X99 não existe
        ctx,
    )
    assert out.ok is False
    assert "X99" in (out.mensagem_erro or "")
    # 16 válidos populam codigos_aceitos (ordem de aparição)
    aceitos = set(out.codigos_aceitos)
    assert "E01" in aceitos and "E51" in aceitos
    assert "P01" in aceitos and "AC07" in aceitos
    assert "X99" not in aceitos
    assert len(aceitos) == 16


def test_validar_partida_acumula_parciais_step2_falha():
    """1ª tentativa: 9 estruturais (sem PROPOSTA) + algumas lacunas.
    Validação falha no Step 2 (seção faltando). codigos_aceitos inclui
    os 9 estruturais + as lacunas."""
    from redato_backend.whatsapp.jogo_partida import validar_partida
    ctx = _ctx_minimo()
    # Pula E51 (PROPOSTA) — vai dar "Faltou seção Proposta"
    out = validar_partida(
        ["E01", "E10", "E17", "E19", "E21", "E33", "E35", "E37", "E49",
         "P01", "R01", "K01"],
        ctx,
    )
    assert out.ok is False
    assert "Proposta" in (out.mensagem_erro or "")
    # Os 9 estruturais + 3 lacunas estão em codigos_aceitos
    aceitos = set(out.codigos_aceitos)
    assert len(aceitos) == 12
    assert "E51" not in aceitos


def test_validar_partida_acumula_parciais_passa_quando_completa():
    """2ª tentativa: aluno corrige 1 código. validar_partida com
    codigos_existentes_acumulados=16_validos + ["K22"] (1 corrigido)
    monta os 17 e passa."""
    from redato_backend.whatsapp.jogo_partida import validar_partida
    ctx = _ctx_minimo()

    # Simula 16 válidos parciais persistidos da 1ª tentativa
    # (que falhou por causa de "X99" inválido — Cenário A do briefing).
    parciais = [
        "E01", "E10", "E17", "E19", "E21", "E33", "E35", "E37",
        "E49", "E51", "P01", "R01", "A01", "AC07", "ME04", "F02",
    ]
    # Aluno corrige só o que estava errado (manda K22 — antes faltava K)
    novos = ["K22"]

    out = validar_partida(
        novos, ctx,
        codigos_existentes_acumulados=parciais,
    )
    assert out.ok is True
    # codigos_aceitos no caminho feliz lista todos os 17 (16 parciais
    # + 1 novo, dedup automático preservando ordem)
    assert "K22" in out.codigos_aceitos
    assert "E01" in out.codigos_aceitos
    assert len(out.codigos_aceitos) == 17


def test_validar_partida_idempotente_re_envio_de_codigo_valido():
    """Aluno re-envia código que JÁ estava nos parciais junto com
    a correção. Dedup do validar_partida impede duplicata fatal —
    vira só warning. Cenário C do briefing."""
    from redato_backend.whatsapp.jogo_partida import validar_partida
    ctx = _ctx_minimo()

    parciais = [
        "E01", "E10", "E17", "E19", "E21", "E33", "E35", "E37",
        "E49", "E51", "P01", "R01", "A01", "AC07", "ME04", "F02",
    ]
    # Aluno re-envia E01 (já estava válido) + K22 (correção)
    novos = ["E01", "K22"]

    out = validar_partida(
        novos, ctx,
        codigos_existentes_acumulados=parciais,
    )
    assert out.ok is True
    # E01 não vira duplicata fatal; K22 entra normalmente
    assert "K22" in out.codigos_aceitos
    # Total ainda 17 (E01 não dobrou)
    assert len(out.codigos_aceitos) == 17


def test_validar_partida_codigos_aceitos_caminho_feliz_sem_acumulado():
    """Aluno manda lista completa de 17 numa só mensagem (sem acumular
    nada). codigos_aceitos no return ok=True espelha a lista válida
    — caller usa pra limpar parciais."""
    from redato_backend.whatsapp.jogo_partida import validar_partida
    ctx = _ctx_minimo()
    out = validar_partida(
        ["E01", "E10", "E17", "E19", "E21", "E33", "E35", "E37",
         "E49", "E51", "P01", "R01", "K01", "A01", "AC07", "ME04",
         "F02"],
        ctx,
    )
    assert out.ok is True
    assert len(out.codigos_aceitos) == 17


def test_validar_partida_codigos_existentes_acumulados_none_eh_default():
    """Compatibilidade: chamadas legadas sem o param novo continuam
    funcionando idênticas ao comportamento anterior do fix."""
    from redato_backend.whatsapp.jogo_partida import validar_partida
    ctx = _ctx_minimo()
    # Sem o param novo
    out = validar_partida(["E01", "X99"], ctx)
    assert out.ok is False
    # codigos_aceitos ainda é populado (mesmo sem o param novo)
    assert "E01" in out.codigos_aceitos
    assert "X99" not in out.codigos_aceitos
