"""Adaptadores Claude pro A/B 3-vias (Fase 2 toolchain).

Dois caminhos:

- `grade_prod`: Sonnet 4.6 + rubrica v2 + ensemble. Chama
  `_claude_grade_essay` direto do dev_offline.py — mesmo path
  que prod usa pra OF14 (commit 614af41 em diante). NÃO seta
  REDATO_CLAUDE_MODEL nem REDATO_RUBRICA — default = Sonnet 4.6 + v2.

- `grade_tuned`: Opus 4.7 + system v2 + fewshot INEP nota 1000.
  Reproduz o experimento offline de 2026-04-27 que deu 42.5% ±40 em
  subset 80. NÃO usa flat schema nem caps (Daniel concordou em manter
  só Opus + fewshot). Caminho do `run_test_fewshot_inep.py`,
  inlinado aqui pra A/B ficar autocontido.

Saída padronizada (mesmo schema dos outros adaptadores):
    {
      "id", "fonte", "tema", "gabarito",
      "modelo": "claude-...",
      "notas_geradas": {"c1"..."c5", "total"},
      "raw_output": <tool_args completo>,
      "latency_ms", "cost_usd", "error",
    }

`cost_usd` é estimativa — Anthropic não retorna custo na resposta.
Calculado por contagem de tokens (input + output) × tabela de preço.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional


REPO = Path(__file__).resolve().parents[2]
BACKEND = REPO / "backend" / "notamil-backend"


def _bootstrap_backend_path() -> None:
    """Adiciona backend/notamil-backend ao sys.path. Idempotente —
    pode ser chamado múltiplas vezes sem efeito colateral."""
    s = str(BACKEND)
    if s not in sys.path:
        sys.path.insert(0, s)


# Tabela de preços Anthropic (USD por 1M tokens). Atualizar quando
# Anthropic mudar — eval roda esporádico, não vale automatizar.
_PRECOS_ANTHROPIC = {
    "claude-sonnet-4-6": {"input": 3.0, "output": 15.0},
    "claude-opus-4-7":  {"input": 15.0, "output": 75.0},
}


def _estimar_custo(
    model: str, input_tokens: int, output_tokens: int,
) -> float:
    """Retorna custo USD baseado em tokens reais (Anthropic devolve
    `usage.input_tokens` e `usage.output_tokens` em cada response)."""
    p = _PRECOS_ANTHROPIC.get(model)
    if p is None:
        # Fallback conservador (Opus rate)
        p = _PRECOS_ANTHROPIC["claude-opus-4-7"]
    return (
        (input_tokens / 1_000_000) * p["input"]
        + (output_tokens / 1_000_000) * p["output"]
    )


def _extrair_notas_v2(tool_args: Dict[str, Any]) -> Dict[str, int]:
    """Extrai notas C1-C5 + total do tool_args (schema v2 audit-first
    com `cN_audit.nota`). Retorna dict com inteiros ou 0 se ausente."""
    notas: Dict[str, int] = {}
    for k in ("c1", "c2", "c3", "c4", "c5"):
        audit = tool_args.get(f"{k}_audit") or {}
        n = audit.get("nota")
        if isinstance(n, (int, float)):
            notas[k] = int(n)
        else:
            notas[k] = 0
    notas["total"] = sum(notas[k] for k in ("c1", "c2", "c3", "c4", "c5"))
    return notas


# ──────────────────────────────────────────────────────────────────────
# Caminho prod (Sonnet 4.6 v2)
# ──────────────────────────────────────────────────────────────────────

def grade_prod(rec: Dict[str, Any]) -> Dict[str, Any]:
    """Avalia 1 redação no caminho prod atual de OF14.

    `rec` é uma linha do eval_gold_v1.jsonl (com `id`, `tema`,
    `redacao.texto_original`, `notas_competencia`, `nota_global`).

    Pré-condições: caller já setou env vars antes do primeiro call:
        REDATO_DEV_OFFLINE=1
        REDATO_DEV_PERSIST=0
        REDATO_ENSEMBLE=1            (default; mantém comportamento prod)
        REDATO_SELF_CRITIQUE=0       (default; sem 2ª pass do Claude)
        ANTHROPIC_API_KEY=<key>
    NÃO seta REDATO_CLAUDE_MODEL (default Sonnet 4.6).
    NÃO seta REDATO_RUBRICA (default v2).
    """
    _bootstrap_backend_path()

    # Import lazy: dev_offline.apply_patches() precisa rodar depois
    # do REDATO_DEV_OFFLINE=1 estar setado.
    from redato_backend.dev_offline import (
        _claude_grade_essay, apply_patches,
    )
    apply_patches()

    rid = rec["id"]
    tema = (rec.get("tema") or {}).get("titulo") or "Tema livre"
    content = (rec.get("redacao") or {}).get("texto_original") or ""

    payload = {
        "request_id": rid,
        "content": content,
        "theme": tema,
        "user_id": "ab_test",
        "activity_id": "of14_completo_integral",
    }

    start = time.time()
    try:
        tool_args = _claude_grade_essay(payload)
    except Exception as exc:  # noqa: BLE001
        return _erro(rec, model="claude-sonnet-4-6",
                     elapsed=time.time() - start, exc=exc)

    elapsed_ms = int((time.time() - start) * 1000)
    notas = _extrair_notas_v2(tool_args)
    # Prod path não devolve usage; estimamos pelos chars do payload
    # (~4 chars/token) — número aproximado, suficiente pra comparar
    # custo entre os 3 modelos no relatório.
    aprox_in = (len(content) + len(tema) + 8000) // 4   # +8K do system
    aprox_out = 1500
    custo = _estimar_custo("claude-sonnet-4-6", aprox_in, aprox_out)
    return _saida(
        rec, model="claude-sonnet-4-6",
        notas=notas, raw=tool_args,
        elapsed_ms=elapsed_ms, cost=custo,
    )


# ──────────────────────────────────────────────────────────────────────
# Caminho tuned (Opus 4.7 + fewshot INEP)
# ──────────────────────────────────────────────────────────────────────

# Cache do fewshot block — construído uma vez por execução, reusado
# em todas as 200 redações.
_fewshot_cache: Optional[str] = None


def _build_fewshot_block() -> str:
    """Constrói o bloco de calibração com 2 redações INEP nota 1000.
    Reaproveita a função do `run_test_fewshot_inep.py` — copiada aqui
    pra A/B ficar autocontido (sem depender de path de scripts/
    backend/notamil-backend interno).

    Resultado é cacheado no módulo — chamado N×, retorna mesmo bloco.
    """
    global _fewshot_cache
    if _fewshot_cache is not None:
        return _fewshot_cache

    import json
    inep_path = REPO / "ingest" / "data" / "interim" / "inep.jsonl"
    if not inep_path.exists():
        raise RuntimeError(
            f"INEP corpus não encontrado em {inep_path}. Necessário "
            f"pro fewshot block do tuned. Verifica se rodou o ingest."
        )

    fewshot_ids = ("inep_2024_07", "inep_2025_01")
    inep_by_id: Dict[str, Dict[str, Any]] = {}
    with inep_path.open(encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if r["id"] in fewshot_ids:
                inep_by_id[r["id"]] = r

    parts = [
        "## Exemplos calibradores — comentários oficiais INEP em redações nota 1000\n",
        "Estes 2 exemplos vêm da Cartilha do Participante INEP. São redações que a "
        "**banca oficial avaliou nota 1000**, com o comentário detalhado da própria banca. "
        "Use-os como calibração de PADRÃO REAL: redação 1000 NÃO é redação perfeita "
        "(35 dos 38 comentários INEP em nota 1000 mencionam pelo menos um desvio). "
        "A banca aponta imprecisões, repetições e pequenos problemas — sem rebaixar a nota. "
        "Sua tarefa é calibrar seu julgamento por essa régua: tolerância em redações de "
        "qualidade, severidade em redações claramente fracas.\n",
    ]
    for idx, fid in enumerate(fewshot_ids, 1):
        rec = inep_by_id[fid]
        tema = (rec.get("tema") or {}).get("titulo") or "(tema na cartilha)"
        texto = (rec.get("redacao") or {}).get("texto_original") or ""
        gab = rec.get("notas_competencia") or {}
        comentario = (rec.get("comentarios") or {}).get("geral") or ""
        parts.append(f"---\n### Exemplo INEP {idx} — {fid}\n")
        parts.append(f"**Tema:** {tema}\n")
        parts.append(
            f"**Gabarito INEP:** "
            f"C1={gab.get('c1')} · C2={gab.get('c2')} · "
            f"C3={gab.get('c3')} · C4={gab.get('c4')} · "
            f"C5={gab.get('c5')} · TOTAL={rec.get('nota_global')}\n",
        )
        parts.append(f"**Texto da redação:**\n```\n{texto.strip()}\n```\n")
        parts.append(
            f"**Comentário oficial da banca INEP "
            f"(calibração de tom e severidade):**\n\n"
            f"{comentario.strip()}\n",
        )
    parts.append("---\n")
    parts.append(
        "**Como usar estes exemplos:** ao avaliar uma nova redação, "
        "ajuste sua escala considerando que 1000 não exige perfeição. "
        "Em C1, a banca tolera 1-3 desvios pontuais não-reincidentes em "
        "texto longo bem estruturado. Em C2, repertório produtivo "
        "(não decorativo) é o que conta — não busque fonte citada "
        "formalmente. Em C3, projeto de texto bem definido com estratégia "
        "argumentativa legível é 200, mesmo sem 'autoria' explícita. "
        "Em C4, conectivo com relação semântica adequada é o critério, "
        "não diversidade pela diversidade. Em C5, qualidade integrada da "
        "proposta (concreta + detalhada + articulada à discussão) supera "
        "contagem de elementos.\n",
    )
    parts.append(
        "Mas: o tool schema desta avaliação ainda exige preenchimento dos "
        "campos de auditoria da v2 (c1_audit, c2_audit, etc.). Preencha-os "
        "com fidelidade aos campos requeridos, mas calibre as notas finais "
        "(nota_final em cada cN_audit) pelo padrão INEP demonstrado acima.\n",
    )
    _fewshot_cache = "\n".join(parts)
    return _fewshot_cache


def grade_tuned(rec: Dict[str, Any]) -> Dict[str, Any]:
    """Avalia 1 redação com Opus 4.7 + system v2 + fewshot INEP.

    Reproduz o experimento offline de 2026-04-27 (subset 80,
    42.5% ±40 global). NÃO usa flat schema nem caps por flag — só
    o fewshot calibrador. Daniel decide depois se rola re-rodar com
    flat+caps em iteração futura.
    """
    _bootstrap_backend_path()

    import anthropic
    from redato_backend.dev_offline import (
        _SYSTEM_PROMPT_BASE,
        _GRADING_TAIL_INSTRUCTION,
        _SUBMIT_CORRECTION_TOOL,
    )

    rid = rec["id"]
    tema = (rec.get("tema") or {}).get("titulo") or "Tema livre"
    content = (rec.get("redacao") or {}).get("texto_original") or ""
    fewshot_block = _build_fewshot_block()

    user_msg = (
        f"TEMA: {tema}\n\n"
        f"REDAÇÃO DO ALUNO:\n\"\"\"\n{content}\n\"\"\"\n\n"
        "Avalie a redação acima pelas 5 competências ENEM, calibrando "
        "seu julgamento pelos exemplos INEP do system prompt. "
        "Chame `submit_correction` preenchendo TODOS os campos de auditoria."
    )

    model = "claude-opus-4-7"
    client = anthropic.Anthropic(
        api_key=os.environ["ANTHROPIC_API_KEY"],
    )

    start = time.time()
    try:
        message = client.messages.create(
            model=model,
            max_tokens=8000,
            system=[
                {"type": "text", "text": _SYSTEM_PROMPT_BASE},
                {
                    "type": "text", "text": fewshot_block,
                    "cache_control": {"type": "ephemeral", "ttl": "1h"},
                },
                {
                    "type": "text", "text": _GRADING_TAIL_INSTRUCTION,
                    "cache_control": {"type": "ephemeral", "ttl": "1h"},
                },
            ],
            tools=[_SUBMIT_CORRECTION_TOOL],
            tool_choice={"type": "tool", "name": "submit_correction"},
            messages=[{"role": "user", "content": user_msg}],
        )
    except Exception as exc:  # noqa: BLE001
        return _erro(rec, model=model,
                     elapsed=time.time() - start, exc=exc)

    elapsed_ms = int((time.time() - start) * 1000)
    tool_args: Optional[Dict[str, Any]] = None
    for block in message.content:
        if (getattr(block, "type", None) == "tool_use"
                and getattr(block, "name", None) == "submit_correction"):
            tool_args = dict(getattr(block, "input", {}) or {})
            break

    if tool_args is None:
        return _erro(
            rec, model=model, elapsed=elapsed_ms / 1000,
            exc=RuntimeError("Claude não invocou submit_correction"),
        )

    notas = _extrair_notas_v2(tool_args)
    usage = getattr(message, "usage", None)
    in_t = getattr(usage, "input_tokens", 0) if usage else 0
    out_t = getattr(usage, "output_tokens", 0) if usage else 0
    custo = _estimar_custo(model, in_t, out_t)
    return _saida(
        rec, model=model, notas=notas, raw=tool_args,
        elapsed_ms=elapsed_ms, cost=custo,
    )


# ──────────────────────────────────────────────────────────────────────
# Helpers de saída
# ──────────────────────────────────────────────────────────────────────

def _gabarito_de(rec: Dict[str, Any]) -> Dict[str, Optional[int]]:
    gab = rec.get("notas_competencia") or {}
    return {
        "total": rec.get("nota_global"),
        "c1": gab.get("c1"), "c2": gab.get("c2"),
        "c3": gab.get("c3"), "c4": gab.get("c4"),
        "c5": gab.get("c5"),
    }


def _saida(
    rec: Dict[str, Any], *, model: str,
    notas: Dict[str, int], raw: Dict[str, Any],
    elapsed_ms: int, cost: float,
) -> Dict[str, Any]:
    tema = (rec.get("tema") or {}).get("titulo") or "Tema livre"
    return {
        "id": rec["id"],
        "fonte": rec.get("fonte"),
        "tema": tema,
        "gabarito": _gabarito_de(rec),
        "modelo": model,
        "notas_geradas": notas,
        "raw_output": raw,
        "latency_ms": elapsed_ms,
        "cost_usd": round(cost, 6),
        "error": None,
    }


def _erro(
    rec: Dict[str, Any], *, model: str, elapsed: float, exc: Exception,
) -> Dict[str, Any]:
    tema = (rec.get("tema") or {}).get("titulo") or "Tema livre"
    return {
        "id": rec["id"],
        "fonte": rec.get("fonte"),
        "tema": tema,
        "gabarito": _gabarito_de(rec),
        "modelo": model,
        "notas_geradas": {"c1": 0, "c2": 0, "c3": 0,
                           "c4": 0, "c5": 0, "total": 0},
        "raw_output": None,
        "latency_ms": int(elapsed * 1000),
        "cost_usd": 0.0,
        "error": f"{type(exc).__name__}: {exc}"[:300],
    }
