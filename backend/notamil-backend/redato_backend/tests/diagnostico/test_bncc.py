"""Testes do mapeador descritor → BNCC + helper de leitura (Fase 5A.2).

Estratégia: mock OpenAI client pra mapeador. Helper testado com
JSON mock via env var override. Endpoint via inspect.getsource.

Cobre:
1. Catálogo BNCC: 54 habilidades EM13LP01-EM13LP54
2. mapeador LLM: schema válido, max 3 habilidades, código inválido,
   intensidade inválida
3. helper get_habilidades_bncc_por_descritor (com mock JSON)
4. helper get_descritores_por_habilidade_bncc (inversa)
5. status='nao_gerado_ainda' (placeholder bootstrap) → vazio
6. Pipeline batch: persiste JSON com estrutura correta
7. Endpoint perfil inclui habilidades_bncc nas lacunas_enriquecidas
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest


# ──────────────────────────────────────────────────────────────────────
# Helpers — fakes
# ──────────────────────────────────────────────────────────────────────

def _fake_response(args_dict: dict, prompt_tokens=500, completion_tokens=200):
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


def _fake_descritor():
    from redato_backend.diagnostico.descritores import Descritor
    return Descritor(
        id="C1.005",
        competencia="C1",
        categoria_inep="Desvios gramaticais",
        nome="Concordância (verbal e nominal)",
        definicao="Verbo concorda com sujeito em número e pessoa.",
        indicador_lacuna="'Fazem X anos'; 'houveram problemas'.",
        exemplo_lacuna="Existe muitos problemas.",
    )


# ──────────────────────────────────────────────────────────────────────
# 1. Catálogo BNCC — 54 habilidades
# ──────────────────────────────────────────────────────────────────────

def test_bncc_referencia_tem_54_habilidades():
    """Catálogo BNCC EM-LP cobre EM13LP01..EM13LP54."""
    from redato_backend.diagnostico.bncc_referencia import (
        BNCC_LP_EM, listar_codigos_ordenados,
    )
    assert len(BNCC_LP_EM) == 54
    codigos = listar_codigos_ordenados()
    assert codigos[0] == "EM13LP01"
    assert codigos[-1] == "EM13LP54"
    # Todos os códigos seguem padrão EM13LPNN
    for c in codigos:
        assert c.startswith("EM13LP")
        num = int(c.replace("EM13LP", ""))
        assert 1 <= num <= 54


def test_bncc_referencia_descricoes_nao_vazias():
    """Nenhuma habilidade tem descrição vazia."""
    from redato_backend.diagnostico.bncc_referencia import BNCC_LP_EM
    for codigo, h in BNCC_LP_EM.items():
        assert h.descricao and len(h.descricao) >= 30, (
            f"{codigo} sem descrição mínima"
        )


# ──────────────────────────────────────────────────────────────────────
# 2. Mapeador LLM
# ──────────────────────────────────────────────────────────────────────

def test_mapear_descritor_bncc_retorna_habilidades_validas():
    """Mock devolve 2 habilidades válidas → MapeamentoDescritorBncc ok."""
    from redato_backend.diagnostico.mapeador_bncc import (
        mapear_descritor_para_bncc,
    )
    payload = {
        "habilidades_bncc": [
            {"codigo": "EM13LP02", "intensidade": "alta",
             "razao": "Descritor trabalha relações lógico-discursivas"},
            {"codigo": "EM13LP38", "intensidade": "media",
             "razao": "Inclui análise de recursos linguísticos"},
        ],
    }
    factory = _make_factory(_fake_response(payload))
    result = mapear_descritor_para_bncc(_fake_descritor(), client_factory=factory)
    assert result is not None
    assert result.descritor_id == "C1.005"
    assert len(result.habilidades_bncc) == 2
    assert result.habilidades_bncc[0].codigo == "EM13LP02"
    assert result.habilidades_bncc[0].intensidade == "alta"
    assert result.custo_estimado_usd > 0


def test_mapear_descritor_bncc_max_3_habilidades():
    """Mock devolve 4 habilidades → validação rejeita → None.
    Schema OpenAI normalmente bloqueia antes (maxItems=3)."""
    from redato_backend.diagnostico.mapeador_bncc import (
        mapear_descritor_para_bncc,
    )
    payload = {
        "habilidades_bncc": [
            {"codigo": f"EM13LP0{i}", "intensidade": "media",
             "razao": f"razao {i} suficientemente longa pra passar validação"}
            for i in range(1, 5)  # 4 entries
        ],
    }
    factory = _make_factory(_fake_response(payload))
    result = mapear_descritor_para_bncc(_fake_descritor(), client_factory=factory)
    assert result is None


def test_mapear_descritor_bncc_codigo_invalido_levanta():
    """Código fora do catálogo (ex.: EM13LP99 não existe) → None."""
    from redato_backend.diagnostico.mapeador_bncc import (
        mapear_descritor_para_bncc,
    )
    payload = {
        "habilidades_bncc": [
            {"codigo": "EM13LP99", "intensidade": "alta",
             "razao": "Inventado, fora do catálogo de 54"},
        ],
    }
    factory = _make_factory(_fake_response(payload))
    result = mapear_descritor_para_bncc(_fake_descritor(), client_factory=factory)
    assert result is None


def test_mapear_descritor_bncc_codigo_lgg_rejeitado():
    """Códigos do componente Linguagens GERAL (EM13LGG*) NÃO entram
    no catálogo LP — devem ser rejeitados pela validação."""
    from redato_backend.diagnostico.mapeador_bncc import (
        mapear_descritor_para_bncc,
    )
    payload = {
        "habilidades_bncc": [
            {"codigo": "EM13LGG101", "intensidade": "alta",
             "razao": "Código LGG não pertence ao componente LP"},
        ],
    }
    factory = _make_factory(_fake_response(payload))
    result = mapear_descritor_para_bncc(_fake_descritor(), client_factory=factory)
    assert result is None


# ──────────────────────────────────────────────────────────────────────
# 3-4. Helpers de leitura (com JSON mock)
# ──────────────────────────────────────────────────────────────────────

@pytest.fixture
def mapeamento_bncc_mock(tmp_path, monkeypatch):
    """Cria um JSON BNCC pequeno e força o helper a usá-lo."""
    payload = {
        "versao": "1.0",
        "gerado_em": "2026-05-04T00:00:00+00:00",
        "modelo_usado": "gpt-4.1-2025-04-14",
        "status": "em_revisao",
        "estatisticas": {"total_descritores": 3},
        "mapeamentos": [
            {
                "descritor_id": "C1.005",
                "descritor_nome": "Concordância",
                "descritor_competencia": "C1",
                "habilidades_bncc": [
                    {"codigo": "EM13LP02", "intensidade": "alta",
                     "razao": "trabalha relações"},
                    {"codigo": "EM13LP38", "intensidade": "media",
                     "razao": "trabalha recursos linguísticos"},
                ],
                "mapeamento_falhou": False,
            },
            {
                "descritor_id": "C5.001",
                "descritor_nome": "Agente",
                "descritor_competencia": "C5",
                "habilidades_bncc": [
                    {"codigo": "EM13LP29", "intensidade": "alta",
                     "razao": "produz textos argumentativos"},
                ],
                "mapeamento_falhou": False,
            },
            # Mapeamento que falhou — não deve aparecer nos lookups
            {
                "descritor_id": "C9.999",
                "descritor_nome": "Falhado",
                "descritor_competencia": "C?",
                "habilidades_bncc": [],
                "mapeamento_falhou": True,
            },
        ],
    }
    p = tmp_path / "bncc.json"
    p.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setenv("REDATO_MAPEAMENTO_BNCC_JSON", str(p))
    # Reseta cache pra forçar reload
    from redato_backend.diagnostico import bncc as b
    b._cache_path = None
    b._cache_mtime = None
    b._cache_data = None
    b._index_por_descritor = None
    b._index_por_habilidade = None
    return p


def test_get_habilidades_bncc_por_descritor(mapeamento_bncc_mock):
    """Lookup direto: descritor → lista de habilidades."""
    from redato_backend.diagnostico.bncc import (
        get_habilidades_bncc_por_descritor,
    )
    habs = get_habilidades_bncc_por_descritor("C1.005")
    assert len(habs) == 2
    codigos = [h["codigo"] for h in habs]
    assert "EM13LP02" in codigos
    assert "EM13LP38" in codigos


def test_get_descritores_por_habilidade_bncc(mapeamento_bncc_mock):
    """Lookup inverso: habilidade BNCC → lista de descritores."""
    from redato_backend.diagnostico.bncc import (
        get_descritores_por_habilidade_bncc,
    )
    descs = get_descritores_por_habilidade_bncc("EM13LP02")
    assert len(descs) == 1
    assert descs[0]["descritor_id"] == "C1.005"
    assert descs[0]["intensidade"] == "alta"

    # Habilidade não-mapeada → lista vazia
    assert get_descritores_por_habilidade_bncc("EM13LP54") == []

    # Mapeamento falhou (C9.999) não conta
    descs_outros = get_descritores_por_habilidade_bncc("EM13LP29")
    assert all(d["descritor_id"] != "C9.999" for d in descs_outros)


# ──────────────────────────────────────────────────────────────────────
# 5. Status placeholder (nao_gerado_ainda)
# ──────────────────────────────────────────────────────────────────────

def test_helper_status_nao_gerado_ainda(tmp_path, monkeypatch):
    """JSON com status='nao_gerado_ainda' → helpers retornam vazio
    (mesmo se houver mapeamentos malformados — ignora total)."""
    payload = {
        "versao": "1.0",
        "status": "nao_gerado_ainda",
        "mapeamentos": [],
    }
    p = tmp_path / "placeholder.json"
    p.write_text(json.dumps(payload))
    monkeypatch.setenv("REDATO_MAPEAMENTO_BNCC_JSON", str(p))
    from redato_backend.diagnostico import bncc as b
    b._cache_path = None
    b._cache_mtime = None
    b._cache_data = None
    b._index_por_descritor = None
    b._index_por_habilidade = None

    assert b.get_habilidades_bncc_por_descritor("C1.005") == []
    assert b.get_descritores_por_habilidade_bncc("EM13LP02") == []
    s = b.status_mapeamento()
    assert s["disponivel"] is False
    assert s["status"] == "nao_gerado_ainda"


# ──────────────────────────────────────────────────────────────────────
# 6. Pipeline batch — sem API key sai com código 2
# ──────────────────────────────────────────────────────────────────────

def test_pipeline_batch_sem_api_key_sai(monkeypatch):
    """Script gerar_mapeamento_bncc exige OPENAI_API_KEY (sem
    fallback heurístico). Sem key → sys.exit(2)."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from redato_backend.diagnostico.scripts.gerar_mapeamento_bncc import (
        gerar_mapeamento_completo,
    )
    with pytest.raises(SystemExit) as exc_info:
        gerar_mapeamento_completo(verbose=False)
    assert exc_info.value.code == 2


# ──────────────────────────────────────────────────────────────────────
# 7. Endpoint perfil enriquece lacunas com BNCC
# ──────────────────────────────────────────────────────────────────────

def test_endpoint_perfil_inclui_habilidades_bncc():
    """Schema DiagnosticoLacunaEnriquecida aceita campo
    habilidades_bncc + endpoint chama o helper de lookup."""
    from redato_backend.portal.portal_api import (
        DiagnosticoLacunaEnriquecida, DiagnosticoHabilidadeBncc,
    )
    lac = DiagnosticoLacunaEnriquecida(
        id="C1.005",
        nome="Concordância",
        competencia="C1",
        status="lacuna",
        confianca="alta",
        evidencias=["fazem 5 anos"],
        definicao_curta="Verbo concorda com sujeito.",
        sugestao_pedagogica="Liste exemplos.",
        habilidades_bncc=[
            DiagnosticoHabilidadeBncc(
                codigo="EM13LP02", intensidade="alta",
                razao="trabalha relações lógico-discursivas",
                descricao="Estabelecer relações entre as partes do texto…",
            ),
        ],
    )
    assert len(lac.habilidades_bncc) == 1
    assert lac.habilidades_bncc[0].codigo == "EM13LP02"
    assert lac.habilidades_bncc[0].descricao is not None


def test_endpoint_perfil_consume_helper_bncc():
    """_build_diagnostico_recente importa get_habilidades_bncc_por_descritor
    e popula habilidades_bncc nas lacunas. Smoke estrutural."""
    import inspect
    from redato_backend.portal import portal_api
    src = inspect.getsource(portal_api._build_diagnostico_recente)
    assert "get_habilidades_bncc_por_descritor" in src
    assert "DiagnosticoHabilidadeBncc(" in src
    assert "habilidades_bncc=" in src
