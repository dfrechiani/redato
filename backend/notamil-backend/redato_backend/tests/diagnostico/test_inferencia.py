"""Testes do pipeline de inferência (Fase 2).

Estratégia: mock do cliente OpenAI (factory injection) — testa toda a
lógica de prompt build, validação, cálculo de custo, sem chamada
real. Smoke estrutural via inspect.getsource.

Cobre:
1. Schema válido (mock devolve 40 descritores corretos) → dict
2. Falta de descritor → returns None + log
3. ID inválido (não existe no YAML) → returns None
4. Status inválido (não em {dominio,lacuna,incerto}) → returns None
5. Custo calculado pelos tokens
6. Timeout / exception OpenAI → returns None (não bloqueia)
"""
from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock

import pytest


# ──────────────────────────────────────────────────────────────────────
# Helpers — fake OpenAI response builder
# ──────────────────────────────────────────────────────────────────────

def _fake_response(args_dict: dict, *, prompt_tokens: int = 3000,
                   completion_tokens: int = 5000) -> Any:
    """Constrói objeto mockado tipo response.choices[0].message.tool_calls[0]
    .function.arguments == JSON string. Usage com tokens preenchidos."""
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


def _full_descritores_payload() -> dict:
    """Constrói payload válido com os 40 IDs C1.001 .. C5.008."""
    from redato_backend.diagnostico import load_descritores
    descs = load_descritores(force_reload=True)
    entries = [
        {
            "id": d.id,
            "status": "lacuna" if d.id.startswith("C5") else "dominio",
            "evidencias": [f"evidencia pra {d.id}"],
            "confianca": "media",
        }
        for d in descs
    ]
    return {
        "descritores": entries,
        "lacunas_prioritarias": [d.id for d in descs if d.competencia == "C5"][:5],
        "resumo_qualitativo": (
            "Aluno demonstra domínio nas competências C1-C4 mas tem "
            "lacunas claras em todas as 8 dimensões da C5 (proposta "
            "de intervenção). Texto bem articulado mas proposta vaga."
        ),
        "recomendacao_breve": (
            "Reforço prioritário nos 5 elementos da proposta (agente, "
            "ação, meio, finalidade, detalhamento) — oficinas OF05/OF06."
        ),
    }


def _make_client_factory(response_obj):
    def factory():
        client = MagicMock()
        client.chat.completions.create = MagicMock(return_value=response_obj)
        return client
    return factory


def _make_failing_factory(exc: Exception):
    def factory():
        client = MagicMock()
        client.chat.completions.create = MagicMock(side_effect=exc)
        return client
    return factory


# ──────────────────────────────────────────────────────────────────────
# 1. Schema válido (happy path)
# ──────────────────────────────────────────────────────────────────────

def test_inferir_diagnostico_schema_valido():
    """Mock devolve 40 descritores corretos → dict completo."""
    from redato_backend.diagnostico.inferencia import (
        SCHEMA_VERSION, inferir_diagnostico,
    )
    payload = _full_descritores_payload()
    response = _fake_response(payload)
    factory = _make_client_factory(response)

    result = inferir_diagnostico(
        texto_redacao="Texto da redação aqui.\nLinha 2.",
        redato_output={"modo": "completo", "nota_total_enem": 720},
        tema="Tema teste",
        client_factory=factory,
    )

    assert result is not None
    assert result["schema_version"] == SCHEMA_VERSION
    assert result["modelo_usado"]  # default model preenchido
    assert isinstance(result["latencia_ms"], int)
    assert result["custo_estimado_usd"] > 0
    assert result["input_tokens"] == 3000
    assert result["output_tokens"] == 5000
    assert len(result["descritores"]) == 40
    assert result["lacunas_prioritarias"] == payload["lacunas_prioritarias"]
    assert "Aluno" in result["resumo_qualitativo"]


# ──────────────────────────────────────────────────────────────────────
# 2-4. Validação (falha levanta ou retorna None — neste caso retorna None
#     pq inferir_diagnostico captura erro e loga)
# ──────────────────────────────────────────────────────────────────────

def test_inferir_diagnostico_falta_descritor_levanta():
    """Mock devolve 39 descritores → _validar levanta, função retorna None."""
    from redato_backend.diagnostico.inferencia import inferir_diagnostico
    payload = _full_descritores_payload()
    payload["descritores"] = payload["descritores"][:39]  # remove o último
    response = _fake_response(payload)
    factory = _make_client_factory(response)
    result = inferir_diagnostico(
        texto_redacao="t",
        redato_output={},
        tema="t",
        client_factory=factory,
    )
    assert result is None


def test_inferir_diagnostico_id_invalido_levanta():
    """ID inventado (não existe no YAML) → returns None."""
    from redato_backend.diagnostico.inferencia import inferir_diagnostico
    payload = _full_descritores_payload()
    payload["descritores"][0]["id"] = "C9.999"  # ID inválido
    response = _fake_response(payload)
    factory = _make_client_factory(response)
    result = inferir_diagnostico(
        texto_redacao="t",
        redato_output={},
        tema="t",
        client_factory=factory,
    )
    assert result is None


def test_inferir_diagnostico_status_invalido_levanta():
    """status fora de {dominio,lacuna,incerto} → returns None."""
    from redato_backend.diagnostico.inferencia import inferir_diagnostico
    payload = _full_descritores_payload()
    payload["descritores"][0]["status"] = "talvez_lacuna"  # inválido
    response = _fake_response(payload)
    factory = _make_client_factory(response)
    result = inferir_diagnostico(
        texto_redacao="t",
        redato_output={},
        tema="t",
        client_factory=factory,
    )
    assert result is None


# ──────────────────────────────────────────────────────────────────────
# 5. Cálculo de custo
# ──────────────────────────────────────────────────────────────────────

def test_inferir_diagnostico_calcula_custo():
    """Custo segue a fórmula GPT-4.1 (USD por milhão de tokens).

    Pricing 2026-05: input $2/MM, output $8/MM.
    Esperado pra 3000 input + 5000 output:
        3000 * 2 / 1_000_000 = 0.006
        5000 * 8 / 1_000_000 = 0.040
        total                = 0.046
    """
    from redato_backend.diagnostico.inferencia import _calcular_custo_usd
    custo = _calcular_custo_usd(input_tokens=3000, output_tokens=5000)
    assert custo == pytest.approx(0.046, abs=1e-6)
    # Caso típico real: ~$0.04 (briefing aceitou esse custo).
    custo_real = _calcular_custo_usd(input_tokens=2500, output_tokens=4500)
    assert 0.03 < custo_real < 0.05


# ──────────────────────────────────────────────────────────────────────
# 6. Timeout / exceção retorna None (não-bloqueante)
# ──────────────────────────────────────────────────────────────────────

def test_inferir_diagnostico_timeout_retorna_none():
    """Exception na chamada OpenAI → returns None, sem propagar."""
    from redato_backend.diagnostico.inferencia import inferir_diagnostico
    factory = _make_failing_factory(TimeoutError("api timed out after 90s"))
    result = inferir_diagnostico(
        texto_redacao="texto qualquer",
        redato_output={},
        tema="t",
        client_factory=factory,
    )
    assert result is None


def test_inferir_diagnostico_texto_vazio_retorna_none():
    """Texto da redação vazio/None → curto-circuita sem chamar OpenAI."""
    from redato_backend.diagnostico.inferencia import inferir_diagnostico
    # Factory que LEVANTA se chamada — não pode ser chamada quando texto vazio
    factory = _make_failing_factory(
        AssertionError("não deveria ter chamado client_factory"),
    )
    assert inferir_diagnostico(
        texto_redacao="",
        redato_output={},
        tema="t",
        client_factory=factory,
    ) is None
    assert inferir_diagnostico(
        texto_redacao="   \n\n",
        redato_output={},
        tema="t",
        client_factory=factory,
    ) is None
