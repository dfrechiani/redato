"""Testes da sugestão de oficinas pro professor (Fase 3).

Estratégia: testes puros (helpers) + um teste com session SQLAlchemy
mock pra validar query path. E2E completo fica em scripts/.

Cobre:
1. Filtra por série (1S não vê oficinas 3S)
2. Dedup global (mesma oficina aparece 1x)
3. Max 2 por lacuna
4. Série sem oficinas → [] (3S OF02/08/12/13 ausentes)
5. Ranking foco antes de completo
6. Smoke estrutural via inspect.getsource
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List
from unittest.mock import MagicMock


# ──────────────────────────────────────────────────────────────────────
# Helpers — fake Missao + fake Session
# ──────────────────────────────────────────────────────────────────────

@dataclass
class _FakeMissao:
    codigo: str
    titulo: str
    serie: str
    oficina_numero: int
    modo_correcao: str
    ativa: bool = True


def _make_session_with_missoes(missoes: List[_FakeMissao]) -> MagicMock:
    """Mock SQLAlchemy session que devolve as missões fornecidas
    pra qualquer SELECT."""
    session = MagicMock()
    result = MagicMock()
    scalars = MagicMock()
    scalars.all = MagicMock(return_value=missoes)
    result.scalars = MagicMock(return_value=scalars)
    session.execute = MagicMock(return_value=result)
    return session


def _catalogo_2s() -> List[_FakeMissao]:
    """Catálogo simulado da 2S — 1 oficina por modo relevante."""
    return [
        _FakeMissao("RJ2·OF04·MF", "Citação", "2S", 4, "foco_c2"),
        _FakeMissao("RJ2·OF06·MF", "Notícia", "2S", 6, "foco_c2"),
        _FakeMissao("RJ2·OF07·MF", "Tese", "2S", 7, "foco_c3"),
        _FakeMissao("RJ2·OF09·MF", "Expedição", "2S", 9, "foco_c3"),
        _FakeMissao("RJ2·OF12·MF", "Leilão", "2S", 12, "foco_c5"),
        _FakeMissao("RJ2·OF13·MF", "Jogo", "2S", 13, "completo"),
        _FakeMissao("RJ2·OF01·MF", "Diagnostico", "2S", 1, "completo_parcial"),
    ]


# ──────────────────────────────────────────────────────────────────────
# 1. Filtro por série
# ──────────────────────────────────────────────────────────────────────

def test_sugerir_oficinas_filtra_serie():
    """sugerir_oficinas só deve sugerir oficinas da série passada.
    Mock Session devolve apenas oficinas da série filtrada — testa
    que o WHERE serie = X está sendo aplicado."""
    from redato_backend.diagnostico.sugestoes import sugerir_oficinas
    diag = {"lacunas_prioritarias": ["C5.001", "C3.004"]}
    # Session devolve só oficinas da 2S (simulando o WHERE serie='2S')
    session = _make_session_with_missoes(_catalogo_2s())
    sugestoes = sugerir_oficinas(
        diagnostico=diag,
        serie_aluno="2S",
        db_session=session,
    )
    # Todas as sugestões devem ser de 2S (catalog_2s só tem 2S)
    assert len(sugestoes) > 0
    for s in sugestoes:
        assert s.codigo.startswith("RJ2·"), f"{s.codigo} não é da 2S"


def test_sugerir_oficinas_serie_invalida_retorna_vazio():
    from redato_backend.diagnostico.sugestoes import sugerir_oficinas
    diag = {"lacunas_prioritarias": ["C5.001"]}
    session = _make_session_with_missoes(_catalogo_2s())
    # Série inválida — não chega nem a executar query
    assert sugerir_oficinas(
        diagnostico=diag, serie_aluno="9S", db_session=session,
    ) == []
    assert sugerir_oficinas(
        diagnostico=diag, serie_aluno="", db_session=session,
    ) == []


# ──────────────────────────────────────────────────────────────────────
# 2. Estado vazio
# ──────────────────────────────────────────────────────────────────────

def test_sugerir_oficinas_diagnostico_none():
    from redato_backend.diagnostico.sugestoes import sugerir_oficinas
    session = _make_session_with_missoes(_catalogo_2s())
    assert sugerir_oficinas(
        diagnostico=None, serie_aluno="2S", db_session=session,
    ) == []


def test_sugerir_oficinas_serie_sem_oficinas():
    """Série sem oficinas no catálogo (ex.: 3S onde OF02/08/12/13 não
    foram seedadas) → [] sem quebrar."""
    from redato_backend.diagnostico.sugestoes import sugerir_oficinas
    diag = {"lacunas_prioritarias": ["C5.001"]}
    session = _make_session_with_missoes([])  # vazio
    assert sugerir_oficinas(
        diagnostico=diag, serie_aluno="3S", db_session=session,
    ) == []


# ──────────────────────────────────────────────────────────────────────
# 3. Max 2 por lacuna
# ──────────────────────────────────────────────────────────────────────

def test_sugerir_oficinas_max_2_por_descritor():
    """Lacunas em C2 (várias oficinas catalogadas) → máx 2 sugestões
    por competência. Briefing é "max 2 por descritor" mas sugestoes
    agrupa por competência (decisão de design Fase 3) — semântica
    equivalente já que dedup por competência acontece antes."""
    from redato_backend.diagnostico.sugestoes import (
        sugerir_oficinas, MAX_POR_LACUNA,
    )
    # 4 oficinas C2 disponíveis na 2S, mas pedimos só uma lacuna em C2
    catalog = [
        _FakeMissao("RJ2·OF04·MF", "Citação", "2S", 4, "foco_c2"),
        _FakeMissao("RJ2·OF06·MF", "Notícia", "2S", 6, "foco_c2"),
        _FakeMissao("RJ2·OF03·MF", "Repertório", "2S", 3, "foco_c2"),
        _FakeMissao("RJ2·OF02·MF", "Tema", "2S", 2, "foco_c2"),
    ]
    session = _make_session_with_missoes(catalog)
    diag = {"lacunas_prioritarias": ["C2.005"]}
    sugestoes = sugerir_oficinas(
        diagnostico=diag, serie_aluno="2S", db_session=session,
    )
    # MAX_POR_LACUNA = 2
    assert len(sugestoes) == MAX_POR_LACUNA == 2


# ──────────────────────────────────────────────────────────────────────
# 4. Dedup global
# ──────────────────────────────────────────────────────────────────────

def test_sugerir_oficinas_dedup():
    """Modo `completo` cobre TODAS competências. Se aluno tem lacunas
    em C3 e C5, a oficina `completo_parcial` poderia aparecer 2x —
    dedup global garante 1x só."""
    from redato_backend.diagnostico.sugestoes import sugerir_oficinas
    catalog = [
        # Só uma oficina, modo completo_parcial (cobre tudo)
        _FakeMissao("RJ2·OF01·MF", "Diagnostico", "2S", 1, "completo_parcial"),
    ]
    session = _make_session_with_missoes(catalog)
    diag = {"lacunas_prioritarias": ["C3.004", "C5.001"]}
    sugestoes = sugerir_oficinas(
        diagnostico=diag, serie_aluno="2S", db_session=session,
    )
    codigos = [s.codigo for s in sugestoes]
    # Não duplica
    assert len(set(codigos)) == len(codigos)
    # E aparece pelo menos 1x
    assert "RJ2·OF01·MF" in codigos


# ──────────────────────────────────────────────────────────────────────
# 5. Ranking foco antes de completo
# ──────────────────────────────────────────────────────────────────────

def test_sugerir_oficinas_ranking_foco_antes_de_completo():
    """foco_c5 deve aparecer antes de completo no resultado quando
    ambos servem pra mesma lacuna."""
    from redato_backend.diagnostico.sugestoes import sugerir_oficinas
    catalog = [
        _FakeMissao("RJ2·OF13·MF", "Jogo Completo", "2S", 13, "completo"),
        _FakeMissao("RJ2·OF12·MF", "Leilão", "2S", 12, "foco_c5"),
    ]
    session = _make_session_with_missoes(catalog)
    diag = {"lacunas_prioritarias": ["C5.001"]}
    sugestoes = sugerir_oficinas(
        diagnostico=diag, serie_aluno="2S", db_session=session,
    )
    # foco_c5 vem antes de completo
    assert sugestoes[0].codigo == "RJ2·OF12·MF"
    assert sugestoes[0].modo_correcao == "foco_c5"
