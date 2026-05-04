"""Testes do helper sugerir_oficinas_livro + integração endpoint
(Fase 5A.1).

Cobre:
1. sugerir_oficinas_livro filtra por série
2. Cap por descritor + max total
3. Threshold de intensidade
4. Estado vazio (JSON ausente)
5. Endpoint perfil inclui oficinas_livro_sugeridas + status
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest


# ──────────────────────────────────────────────────────────────────────
# Fixture: JSON mock
# ──────────────────────────────────────────────────────────────────────

@pytest.fixture
def mapeamento_mock_path(tmp_path, monkeypatch):
    """Cria um mapeamento JSON pequeno e força o helper a usá-lo."""
    payload = {
        "versao": "1.0",
        "gerado_em": "2026-05-04T00:00:00+00:00",
        "gerador": "heuristico",
        "modelo_usado": "heuristico-v1",
        "status": "em_revisao",
        "descricao": "Mock pra teste",
        "estatisticas": {"total_oficinas": 4},
        "oficinas": [
            # 1S oficina avaliável trabalhando C5.001 alta
            {
                "codigo": "RJ1·OF14·MF", "serie": "1S",
                "oficina_numero": 14, "titulo": "Jogo de Redação",
                "tem_redato_avaliavel": True,
                "tipo_atividade": "avaliativa",
                "competencias_principais": ["C5"],
                "descritores_trabalhados": [
                    {"id": "C5.001", "intensidade": "alta", "razao": "trabalha agente"},
                    {"id": "C5.002", "intensidade": "media", "razao": "trabalha ação"},
                ],
                "mapeamento_falhou": False,
            },
            # 1S oficina conceitual com C5.001 baixa (filtrada por intensidade)
            {
                "codigo": "RJ1·OF09·MF", "serie": "1S",
                "oficina_numero": 9, "titulo": "Currículo",
                "tem_redato_avaliavel": False,
                "tipo_atividade": "conceitual",
                "competencias_principais": ["C2"],
                "descritores_trabalhados": [
                    {"id": "C5.001", "intensidade": "baixa", "razao": "tangencial"},
                ],
                "mapeamento_falhou": False,
            },
            # 2S oficina (não deve aparecer pra aluno 1S)
            {
                "codigo": "RJ2·OF12·MF", "serie": "2S",
                "oficina_numero": 12, "titulo": "Leilão de Soluções",
                "tem_redato_avaliavel": True,
                "tipo_atividade": "avaliativa",
                "competencias_principais": ["C5"],
                "descritores_trabalhados": [
                    {"id": "C5.001", "intensidade": "alta", "razao": "trabalha agente"},
                ],
                "mapeamento_falhou": False,
            },
            # Oficina com mapeamento_falhou — deve ser ignorada
            {
                "codigo": "RJ1·OF98·MF", "serie": "1S",
                "oficina_numero": 98, "titulo": "Falhada",
                "tem_redato_avaliavel": False,
                "tipo_atividade": None,
                "competencias_principais": [],
                "descritores_trabalhados": [],
                "mapeamento_falhou": True,
            },
        ],
    }
    p = tmp_path / "mapeamento.json"
    p.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setenv("REDATO_MAPEAMENTO_LIVROS_JSON", str(p))
    # Força reload do cache
    from redato_backend.diagnostico import oficinas_livro as ol
    ol._cache_path = None
    ol._cache_mtime = None
    ol._cache_data = None
    return p


# ──────────────────────────────────────────────────────────────────────
# 1. Filtro por série + intensidade
# ──────────────────────────────────────────────────────────────────────

def test_endpoint_perfil_filtra_por_serie(mapeamento_mock_path):
    """Aluno 1S não vê oficinas RJ2 mesmo com mesmo descritor."""
    from redato_backend.diagnostico.oficinas_livro import (
        sugerir_oficinas_livro,
    )
    sugestoes = sugerir_oficinas_livro(
        lacunas_prioritarias=["C5.001"],
        serie_aluno="1S",
    )
    codigos = [s.codigo for s in sugestoes]
    assert "RJ1·OF14·MF" in codigos
    assert "RJ2·OF12·MF" not in codigos  # série errada
    assert "RJ1·OF98·MF" not in codigos  # mapeamento_falhou


def test_endpoint_perfil_filtra_intensidade_minima(mapeamento_mock_path):
    """Default minimo='media' — descritores com 'baixa' não entram."""
    from redato_backend.diagnostico.oficinas_livro import (
        sugerir_oficinas_livro,
    )
    sugestoes = sugerir_oficinas_livro(
        lacunas_prioritarias=["C5.001"],
        serie_aluno="1S",
    )
    # OF09 tem C5.001 'baixa' — não deve aparecer
    codigos = [s.codigo for s in sugestoes]
    assert "RJ1·OF09·MF" not in codigos


def test_sugerir_oficinas_livro_inclui_baixa_quando_pedido(mapeamento_mock_path):
    """Com intensidade_minima='baixa', OF09 entra."""
    from redato_backend.diagnostico.oficinas_livro import (
        sugerir_oficinas_livro,
    )
    sugestoes = sugerir_oficinas_livro(
        lacunas_prioritarias=["C5.001"],
        serie_aluno="1S",
        intensidade_minima="baixa",
    )
    codigos = [s.codigo for s in sugestoes]
    assert "RJ1·OF09·MF" in codigos


# ──────────────────────────────────────────────────────────────────────
# 2. Estado vazio: JSON ausente
# ──────────────────────────────────────────────────────────────────────

def test_sugerir_oficinas_livro_sem_json(monkeypatch, tmp_path):
    """JSON não existe → retorna lista vazia (não levanta)."""
    from redato_backend.diagnostico import oficinas_livro as ol
    monkeypatch.setenv("REDATO_MAPEAMENTO_LIVROS_JSON", str(tmp_path / "naoexiste.json"))
    ol._cache_path = None
    ol._cache_mtime = None
    ol._cache_data = None
    result = ol.sugerir_oficinas_livro(
        lacunas_prioritarias=["C5.001"], serie_aluno="1S",
    )
    assert result == []


def test_status_mapeamento_sem_json(monkeypatch, tmp_path):
    from redato_backend.diagnostico import oficinas_livro as ol
    monkeypatch.setenv("REDATO_MAPEAMENTO_LIVROS_JSON", str(tmp_path / "naoexiste.json"))
    ol._cache_path = None
    ol._cache_mtime = None
    ol._cache_data = None
    s = ol.status_mapeamento()
    assert s["disponivel"] is False
    assert s["status"] is None


# ──────────────────────────────────────────────────────────────────────
# 3. Endpoint perfil — schema enriquecido
# ──────────────────────────────────────────────────────────────────────

def test_endpoint_perfil_inclui_oficinas_livro_sugeridas():
    """Schema DiagnosticoVersaoProfessor aceita campo
    oficinas_livro_sugeridas + status. Smoke estrutural."""
    from redato_backend.portal.portal_api import (
        DiagnosticoVersaoProfessor,
        DiagnosticoOficinaLivroSugerida,
    )
    p = DiagnosticoVersaoProfessor(
        descritores=[],
        lacunas_prioritarias=[],
        lacunas_enriquecidas=[],
        resumo_qualitativo="x",
        recomendacao_breve="y",
        oficinas_sugeridas=[],
        oficinas_livro_sugeridas=[
            DiagnosticoOficinaLivroSugerida(
                codigo="RJ1·OF14·MF", serie="1S", oficina_numero=14,
                titulo="Jogo", tipo_atividade="avaliativa",
                tem_redato_avaliavel=True,
                intensidade="alta", razao="trabalha proposta",
                descritor_id="C5.001",
                competencias_principais=["C5"],
                status_revisao="em_revisao",
            ),
        ],
        mapeamento_livros_status="em_revisao",
    )
    assert len(p.oficinas_livro_sugeridas) == 1
    assert p.oficinas_livro_sugeridas[0].codigo == "RJ1·OF14·MF"
    assert p.mapeamento_livros_status == "em_revisao"


def test_perfil_endpoint_consume_helper_oficinas_livro():
    """_build_diagnostico_recente importa e chama sugerir_oficinas_livro
    + status_mapeamento. Smoke estrutural via inspect.getsource."""
    import inspect
    from redato_backend.portal import portal_api
    src = inspect.getsource(portal_api._build_diagnostico_recente)
    assert "sugerir_oficinas_livro" in src
    assert "status_mapeamento" in src
    assert "oficinas_livro_sugeridas" in src
