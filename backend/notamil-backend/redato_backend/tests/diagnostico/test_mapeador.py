"""Testes do mapeador LLM e heurístico (Fase 5A.1).

Estratégia: mock OpenAI client pra LLM mapper. Heurístico testado
com OficinaLivro construído à mão.

Cobre:
1. mapeador LLM: schema válido, validação de IDs/intensidade
2. mapeador heurístico: keyword matching, sem chamada externa
3. Pipeline batch: persiste JSON com estrutura correta
"""
from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock

import pytest


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────

def _fake_oficina(codigo="RJ1·OF11·MF", titulo="Conectivos", serie="1S",
                  conteudo="Oficina sobre conectivos argumentativos. "
                           "Trabalha tese, conectivos, coesão."):
    from redato_backend.diagnostico.parser_livros import OficinaLivro, Secao
    return OficinaLivro(
        codigo=codigo, serie=serie, oficina_numero=11,
        titulo=titulo, tem_redato_avaliavel=True,
        secoes=[Secao(tipo="missao_final", titulo="Missão", conteudo_texto=conteudo)],
    )


def _fake_response(args_dict: dict, prompt_tokens=1000, completion_tokens=500):
    msg = MagicMock()
    tool_call = MagicMock()
    tool_call.function.arguments = json.dumps(args_dict)
    msg.tool_calls = [tool_call]
    choice = MagicMock()
    choice.message = msg
    response = MagicMock()
    response.choices = [choice]
    response.usage = MagicMock(
        prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
    )
    return response


def _make_factory(response_obj):
    def factory():
        client = MagicMock()
        client.chat.completions.create = MagicMock(return_value=response_obj)
        return client
    return factory


# ──────────────────────────────────────────────────────────────────────
# 1. Mapeador LLM — schema válido
# ──────────────────────────────────────────────────────────────────────

def test_mapeador_oficina_retorna_descritores_validos():
    """Mock devolve 3 descritores válidos → MapeamentoOficina ok."""
    from redato_backend.diagnostico.mapeador import (
        mapear_oficina_para_descritores,
    )
    payload = {
        "descritores_trabalhados": [
            {"id": "C4.001", "intensidade": "alta",
             "razao": "Oficina trabalha variedade de conectivos extensivamente"},
            {"id": "C4.002", "intensidade": "media",
             "razao": "Adequação semântica é discutida no DOJ"},
            {"id": "C3.001", "intensidade": "baixa",
             "razao": "Tese é mencionada como pré-requisito"},
        ],
        "competencias_principais": ["C4", "C3"],
        "tipo_atividade": "jogo",
    }
    response = _fake_response(payload)
    factory = _make_factory(response)
    of = _fake_oficina()
    result = mapear_oficina_para_descritores(of, client_factory=factory)
    assert result is not None
    assert result.codigo == "RJ1·OF11·MF"
    assert len(result.descritores_trabalhados) == 3
    assert result.descritores_trabalhados[0].id == "C4.001"
    assert result.tipo_atividade == "jogo"
    assert result.custo_estimado_usd > 0


def test_mapeador_oficina_max_8_descritores():
    """Schema limita a 8. Mock devolve 9 → validação falha → None.
    OpenAI tools normalmente bloqueia antes, mas caller deve segurar."""
    from redato_backend.diagnostico.mapeador import (
        mapear_oficina_para_descritores,
    )
    payload = {
        "descritores_trabalhados": [
            {"id": f"C1.00{i}", "intensidade": "media",
             "razao": f"razao {i} aqui suficientemente longa"}
            for i in range(1, 10)  # 9 entries — viola maxItems=8
        ],
        "competencias_principais": ["C1"],
        "tipo_atividade": "pratica",
    }
    response = _fake_response(payload)
    factory = _make_factory(response)
    of = _fake_oficina()
    result = mapear_oficina_para_descritores(of, client_factory=factory)
    assert result is None  # validação rejeita


def test_mapeador_oficina_id_invalido_retorna_none():
    """ID que não está no YAML → None (validação)."""
    from redato_backend.diagnostico.mapeador import (
        mapear_oficina_para_descritores,
    )
    payload = {
        "descritores_trabalhados": [
            {"id": "C9.999", "intensidade": "alta",
             "razao": "Inventado, não existe no YAML"},
        ],
        "competencias_principais": ["C1"],
        "tipo_atividade": "conceitual",
    }
    response = _fake_response(payload)
    factory = _make_factory(response)
    of = _fake_oficina()
    result = mapear_oficina_para_descritores(of, client_factory=factory)
    assert result is None


def test_mapeador_oficina_intensidade_invalida_retorna_none():
    """Intensidade fora de {alta, media, baixa} → None."""
    from redato_backend.diagnostico.mapeador import (
        mapear_oficina_para_descritores,
    )
    payload = {
        "descritores_trabalhados": [
            {"id": "C4.001", "intensidade": "extrema",
             "razao": "Razão suficientemente longa pra passar"},
        ],
        "competencias_principais": ["C4"],
        "tipo_atividade": "pratica",
    }
    response = _fake_response(payload)
    factory = _make_factory(response)
    of = _fake_oficina()
    result = mapear_oficina_para_descritores(of, client_factory=factory)
    assert result is None


# ──────────────────────────────────────────────────────────────────────
# 2. Mapeador heurístico
# ──────────────────────────────────────────────────────────────────────

def test_mapeador_heuristico_keyword_match():
    """Texto rico em conectivos → C4.001 alta."""
    from redato_backend.diagnostico.mapeador_heuristico import (
        mapear_oficina_heuristico,
    )
    of = _fake_oficina(
        codigo="RJ1·OF11·MF", titulo="Conectivos Argumentativos",
        conteudo=(
            "Esta oficina trabalha variedade de conectivos. "
            "O aluno aprende além disso, no entanto, portanto, "
            "porque, ou seja. Categorias de conectivos: causa, "
            "consequência, oposição, conclusão. Variedade de conectivos "
            "é o foco. Trabalho extensivo com conectivos."
        ),
    )
    result = mapear_oficina_heuristico(of)
    ids = [d.id for d in result.descritores_trabalhados]
    assert "C4.001" in ids
    # Intensidade alta porque "conectivos" + "variedade de conectivos"
    # bateram múltiplas vezes
    c4001 = next(d for d in result.descritores_trabalhados if d.id == "C4.001")
    assert c4001.intensidade in ("alta", "media")
    assert "C4" in result.competencias_principais


def test_mapeador_heuristico_sem_match_retorna_vazio():
    """Texto sem keywords → 0 descritores, mas não levanta."""
    from redato_backend.diagnostico.mapeador_heuristico import (
        mapear_oficina_heuristico,
    )
    of = _fake_oficina(
        codigo="RJ1·OF99·MF", titulo="Atividade",
        conteudo="Aaaaa bbbbb ccccc ddddd eeeee ffffff.",
    )
    result = mapear_oficina_heuristico(of)
    # Pode ser vazio (heurístico não filtra "outro" tipo)
    assert result.modelo_usado == "heuristico-v1"
    assert isinstance(result.descritores_trabalhados, list)


# ──────────────────────────────────────────────────────────────────────
# 3. Pipeline batch (script) — modo heurístico
# ──────────────────────────────────────────────────────────────────────

def test_pipeline_batch_persiste_json_modo_heuristico(tmp_path, monkeypatch):
    """Roda o pipeline em modo heurístico (sem API key) e confere
    que JSON gerado tem estrutura correta."""
    from redato_backend.diagnostico.scripts.gerar_mapeamento_livros import (
        gerar_mapeamento_completo,
    )
    output = tmp_path / "out.json"
    payload = gerar_mapeamento_completo(
        output_path=output, verbose=False, heuristic=True,
    )
    # Estrutura do payload
    assert payload["versao"] == "1.0"
    assert payload["gerador"] == "heuristico"
    assert payload["status"] == "em_revisao"
    assert payload["modelo_usado"] == "heuristico-v1"
    assert payload["estatisticas"]["total_oficinas"] >= 13
    # JSON foi gravado
    assert output.exists()
    written = json.loads(output.read_text())
    assert written["gerador"] == "heuristico"
