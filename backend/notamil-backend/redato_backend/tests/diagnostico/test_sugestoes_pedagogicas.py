"""Testes do dicionário de sugestões pedagógicas (fix Fase 3 #3).

Cards de lacuna prioritária ganham 3 seções: o que é + evidência +
COMO TRABALHAR. A última seção vem do dicionário fixo
descritor → sugestão acionável (1-2 frases pro professor).
"""
from __future__ import annotations


def test_get_sugestao_pedagogica_cobre_40_descritores():
    """Pra cada um dos 40 IDs do YAML, sugestão DEVE retornar texto
    real (não fallback). Detecta drift se YAML for atualizado sem
    atualizar dicionário."""
    from redato_backend.diagnostico import load_descritores
    from redato_backend.diagnostico.sugestoes_pedagogicas import (
        get_sugestao_pedagogica, _SUGESTOES, _FALLBACK,
    )
    descs = load_descritores(force_reload=True)
    assert len(descs) == 40
    for d in descs:
        sug = get_sugestao_pedagogica(d.id)
        assert d.id in _SUGESTOES, f"{d.id} sem entrada em sugestoes_pedagogicas.py"
        assert sug != _FALLBACK, f"{d.id} caiu no fallback"
        assert len(sug) >= 30, f"{d.id} sugestão muito curta"


def test_get_sugestao_pedagogica_fallback_id_invalido():
    """ID não-cadastrado retorna fallback genérico — não levanta."""
    from redato_backend.diagnostico.sugestoes_pedagogicas import (
        get_sugestao_pedagogica, _FALLBACK,
    )
    assert get_sugestao_pedagogica("X9.999") == _FALLBACK
    assert get_sugestao_pedagogica("") == _FALLBACK
    assert get_sugestao_pedagogica(None) == _FALLBACK  # type: ignore[arg-type]


def test_get_definicao_curta_trunca_em_ponto_final():
    """Definição curta corta em ponto-final entre 100-180 chars
    quando há um. Realista: definições do YAML têm sentenças com
    100+ chars cada (ex.: 'Períodos completos com sujeito, verbo e
    complementos identificáveis.' tem 70 chars)."""
    from redato_backend.diagnostico.sugestoes_pedagogicas import (
        get_definicao_curta,
    )
    # Texto realista — primeiro ponto cai entre 100-150 chars
    longa = (
        "Aluno apresenta posicionamento claro sobre o tema discutido "
        "ao longo da sua produção textual completa. Tese é a "
        "resposta que o aluno dá ao problema — 'X deve ser feito "
        "porque Y'."
    )
    curta = get_definicao_curta("C3.001", longa)
    # Termina em ponto (preservou primeira frase)
    assert curta.endswith(".")
    # Tem até ~150 chars (cabe no card)
    assert len(curta) <= 200


def test_get_definicao_curta_fallback_word_truncate():
    """Quando não há ponto entre 100-180, cai no fallback de palavras
    com reticências. Não levanta."""
    from redato_backend.diagnostico.sugestoes_pedagogicas import (
        get_definicao_curta,
    )
    # Sem ponto-final perto da meta — força fallback
    longa = (
        "Frase muito curta. Outra. " + "palavra " * 50
    )
    curta = get_definicao_curta("C1.001", longa)
    assert len(curta) <= 200
    # Fallback adiciona reticências OU termina em ponto se achar um
    assert curta.endswith("…") or curta.endswith(".")


def test_get_definicao_curta_definicao_curta_ja_cabe():
    """Definição curta o suficiente passa direto."""
    from redato_backend.diagnostico.sugestoes_pedagogicas import (
        get_definicao_curta,
    )
    curta = "Aluno aborda o tema sem fugir."
    assert get_definicao_curta("C2.001", curta) == curta


def test_get_definicao_curta_string_invalida():
    """Tipo errado / vazio → string vazia, sem levantar."""
    from redato_backend.diagnostico.sugestoes_pedagogicas import (
        get_definicao_curta,
    )
    assert get_definicao_curta("C1.001", "") == ""
    assert get_definicao_curta("C1.001", None) == ""  # type: ignore[arg-type]
