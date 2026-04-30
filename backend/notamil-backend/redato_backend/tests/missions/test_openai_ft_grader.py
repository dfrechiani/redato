"""Testes do grader OF14 via FT (`redato_backend.missions.openai_ft_grader`).

Mocka `client.chat.completions.create` — não chama API real. Cobre:

1. Caso feliz (parse_status=ok): JSON válido com 5 cN_audit completos.
2. JSON balanceado nested (cobre fence ```json ... ``` markdown).
3. Partial aceitável (evidencias vazia em alguns) — não levanta erro.
4. Parse failed → levanta OpenAIFTGradingError.
5. Roteamento `REDATO_OF14_BACKEND=claude` pula adapter (smoke-test do
   ramo no `dev_offline.py` via `_claude_grade_essay`).

Pra (5) usamos um stub leve do `_claude_grade_essay` em vez de mockar
o módulo todo — testar o env-var routing puro, sem precisar mockar
Anthropic.
"""
from __future__ import annotations

import os
import json
from typing import Any, Dict
from unittest.mock import MagicMock

import pytest

from redato_backend.missions.openai_ft_grader import (
    OpenAIFTGradingError,
    grade_of14_with_ft,
    parse_audit_response,
)


# ──────────────────────────────────────────────────────────────────────
# Fixtures comuns
# ──────────────────────────────────────────────────────────────────────


def _mock_client_returning(text: str) -> MagicMock:
    """Constrói cliente mock que retorna `text` como `choices[0].message.content`.

    Reproduz o formato do `client.chat.completions.create()` retornado
    pelo openai SDK (ChatCompletion → choices → ChatCompletionMessage).
    """
    msg = MagicMock()
    msg.content = text
    choice = MagicMock()
    choice.message = msg
    response = MagicMock()
    response.choices = [choice]
    response.usage = MagicMock(
        prompt_tokens=1000, completion_tokens=500,
    )

    client = MagicMock()
    client.chat.completions.create = MagicMock(return_value=response)
    return client


def _client_factory(client: MagicMock):
    """Adapta um MagicMock pra o tipo `ClientFactory` esperado pelo adapter."""
    return lambda: client


SAMPLE_AUDIT_OK = json.dumps({
    "c1_audit": {
        "nota": 160,
        "feedback_text": (
            "Texto em geral bem escrito, com poucos desvios. "
            "Alguns deslizes de pontuação não comprometem a leitura. "
            "Atente-se à concordância em períodos longos."
        ),
        "evidencias": [
            {"trecho": "a pesquisa mostraram resultados",
             "comentario": "concordância verbal: 'a pesquisa mostrou'"},
        ],
    },
    "c2_audit": {
        "nota": 200,
        "feedback_text": (
            "Repertório legitimado e produtivo, articulado ao tema. "
            "Citações funcionam como apoio argumentativo, não decoração."
        ),
        "evidencias": [],
    },
    "c3_audit": {
        "nota": 160,
        "feedback_text": (
            "Argumentação progressiva e bem encadeada. "
            "A tese aparece já no parágrafo de abertura e é retomada na conclusão."
        ),
        "evidencias": [],
    },
    "c4_audit": {
        "nota": 120,
        "feedback_text": (
            "Conectivos adequados mas pouca diversidade — 'além disso' "
            "domina as transições. Diversifique sem perder a clareza."
        ),
        "evidencias": [],
    },
    "c5_audit": {
        "nota": 160,
        "feedback_text": (
            "Proposta concreta com agente, ação e meio definidos. "
            "Falta articular melhor a finalidade ao problema do tema."
        ),
        "evidencias": [],
    },
})


# ──────────────────────────────────────────────────────────────────────
# 1. Caso feliz
# ──────────────────────────────────────────────────────────────────────

def test_grade_of14_caso_feliz_retorna_5_audits():
    """Resposta com 5 cN_audit completos → adapter retorna dict
    estruturado com 5 chaves cN_audit, cada uma com nota int + feedback +
    evidencias (lista)."""
    client = _mock_client_returning(SAMPLE_AUDIT_OK)
    out = grade_of14_with_ft(
        content="Texto da redação aqui.",
        theme="Direitos humanos no século XXI",
        client_factory=_client_factory(client),
    )

    assert set(out.keys()) == {"c1_audit", "c2_audit", "c3_audit",
                                "c4_audit", "c5_audit"}
    assert out["c1_audit"]["nota"] == 160
    assert out["c2_audit"]["nota"] == 200
    assert out["c3_audit"]["nota"] == 160
    assert out["c4_audit"]["nota"] == 120
    assert out["c5_audit"]["nota"] == 160
    assert out["c1_audit"]["feedback_text"].startswith("Texto em geral")
    assert isinstance(out["c1_audit"]["evidencias"], list)
    assert len(out["c1_audit"]["evidencias"]) == 1
    assert "concordância" in out["c1_audit"]["evidencias"][0]["comentario"]

    # Soma das notas: 160+200+160+120+160 = 800
    soma = sum(out[c]["nota"] for c in out)
    assert soma == 800


# ──────────────────────────────────────────────────────────────────────
# 2. JSON dentro de markdown fence (FT às vezes ignora a instrução
#    "sem markdown fence" — parser deve tolerar)
# ──────────────────────────────────────────────────────────────────────

def test_grade_of14_tolera_markdown_fence():
    """Resposta envolvida em ```json ... ``` deve ser parseada
    corretamente (parser tier markdown fence stripping)."""
    raw = "Aqui o resultado:\n```json\n" + SAMPLE_AUDIT_OK + "\n```\nObrigado."
    client = _mock_client_returning(raw)
    out = grade_of14_with_ft(
        content="x", theme="y",
        client_factory=_client_factory(client),
    )
    assert out["c3_audit"]["nota"] == 160
    assert sum(out[c]["nota"] for c in out) == 800


# ──────────────────────────────────────────────────────────────────────
# 3. Partial aceitável (evidencias ausente em 1 competência) — não erra
# ──────────────────────────────────────────────────────────────────────

def test_grade_of14_partial_sem_evidencias_aceito():
    """JSON válido com nota+feedback_text mas evidencias ausente em
    algumas competências = parse_status=partial. Adapter aceita
    (notas estão íntegras), normalizando evidencias pra lista vazia."""
    payload = {
        "c1_audit": {"nota": 120, "feedback_text": "Bom."},
        "c2_audit": {"nota": 160, "feedback_text": "Ok.", "evidencias": []},
        "c3_audit": {"nota": 160, "feedback_text": "Ok.", "evidencias": []},
        "c4_audit": {"nota": 120, "feedback_text": "Ok.", "evidencias": []},
        "c5_audit": {"nota": 80, "feedback_text": "Ok.", "evidencias": []},
    }
    client = _mock_client_returning(json.dumps(payload))
    out = grade_of14_with_ft(
        content="x", theme="y",
        client_factory=_client_factory(client),
    )
    # c1 não tinha evidencias no input → adapter normaliza pra []
    assert out["c1_audit"]["evidencias"] == []
    assert out["c1_audit"]["nota"] == 120
    assert sum(out[c]["nota"] for c in out) == 640


# ──────────────────────────────────────────────────────────────────────
# 4. Parse falha → OpenAIFTGradingError
# ──────────────────────────────────────────────────────────────────────

def test_grade_of14_parser_failed_levanta_erro():
    """Resposta texto livre sem JSON parseável → OpenAIFTGradingError
    com raw_output preservado pra debug."""
    raw = (
        "Não consegui avaliar essa redação no formato pedido. "
        "C1: 160, C2: 200 (mas sem JSON estruturado)."
    )
    client = _mock_client_returning(raw)
    with pytest.raises(OpenAIFTGradingError) as exc_info:
        grade_of14_with_ft(
            content="x", theme="y",
            client_factory=_client_factory(client),
        )
    err = exc_info.value
    assert err.parse_status == "failed"
    assert err.raw_output == raw
    assert "json_não_parseou" in (err.missing_fields or [])


def test_grade_of14_nota_fora_da_escala_levanta_erro():
    """Notas válidas no ENEM são 0/40/80/120/160/200. Se FT inventar
    algo como 150, parser detecta e adapter levanta erro (não silencia
    o problema retornando um dict potencialmente errado)."""
    payload = {
        "c1_audit": {"nota": 150, "feedback_text": "x", "evidencias": []},
        "c2_audit": {"nota": 160, "feedback_text": "x", "evidencias": []},
        "c3_audit": {"nota": 160, "feedback_text": "x", "evidencias": []},
        "c4_audit": {"nota": 120, "feedback_text": "x", "evidencias": []},
        "c5_audit": {"nota": 80, "feedback_text": "x", "evidencias": []},
    }
    client = _mock_client_returning(json.dumps(payload))
    with pytest.raises(OpenAIFTGradingError) as exc_info:
        grade_of14_with_ft(
            content="x", theme="y",
            client_factory=_client_factory(client),
        )
    assert any("fora_da_escala" in m for m in (exc_info.value.missing_fields or []))


# ──────────────────────────────────────────────────────────────────────
# 5. Roteamento env var REDATO_OF14_BACKEND=claude pula o FT
# ──────────────────────────────────────────────────────────────────────

def test_dev_offline_tem_roteamento_of14_ft_com_rollback():
    """Smoke estrutural: garante que `_claude_grade_essay` em
    `dev_offline.py` tem o roteamento OF14→FT com env var de rollback.

    Lê o source da função e confere que os 4 elementos críticos estão
    presentes:
      1. Importa `grade_of14_with_ft`
      2. Lê `REDATO_OF14_BACKEND` (default `"ft"`)
      3. Compara com `COMPLETO_INTEGRAL`
      4. Tem fallback graceful (`except` cai pro Claude)

    Se algum desses ramos for removido num refactor futuro (ex.: alguém
    deletar o try/except esperando que o FT seja sempre confiável), esse
    teste avisa cedo. Não exige rodar pipeline completo (que precisaria
    mockar Anthropic, Firestore, BQ).
    """
    import inspect
    from redato_backend import dev_offline

    src = inspect.getsource(dev_offline._claude_grade_essay)
    assert "grade_of14_with_ft" in src, (
        "perdeu o import/uso do FT grader em _claude_grade_essay"
    )
    assert "REDATO_OF14_BACKEND" in src, (
        "perdeu o check do env var de rollback"
    )
    assert "COMPLETO_INTEGRAL" in src, (
        "perdeu o gate de modo (FT só roda em OF14)"
    )
    assert "falling back to Claude" in src, (
        "perdeu o fallback graceful — FT pode falhar e derrubar correção"
    )


# ──────────────────────────────────────────────────────────────────────
# Bônus: parser unit (sem o adapter)
# ──────────────────────────────────────────────────────────────────────

def test_parse_audit_response_ok():
    audit, status, missing = parse_audit_response(SAMPLE_AUDIT_OK)
    assert status == "ok"
    assert missing == []
    assert audit is not None
    assert audit["c1_audit"]["nota"] == 160


def test_parse_audit_response_resposta_vazia():
    audit, status, missing = parse_audit_response("")
    assert status == "failed"
    assert missing == ["resposta_vazia"]
    assert audit is None
