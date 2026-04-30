"""Adaptador GPT fine-tuned pro A/B 3-vias.

Modelo: `ft:gpt-4.1-2025-04-14:redato:redato-enem:BTBOS5VF`
(treinado em Apr/2025 — 2.348M tokens, 10 epochs, batch 3, LR 0.95).

Diferente dos adaptadores Claude (que usam tool_use), o FT foi
treinado pra retornar texto livre — pode vir em formato JSON inline,
em formato "C1: 160, C2: 160, ..." ou em qualquer outra forma. Por
isso, parser tem 3 níveis de fallback:

  1. JSON parse direto da resposta
     (`{"c1": 160, "c2": 160, "c3": 160, "c4": 160, "c5": 160}`)
  2. Regex extraindo "C1: 160" / "C1 - 160" / "C1=160" etc.
  3. Fallback: marca error + raw_output salvo pra inspeção manual.

Saída padronizada (mesmo schema do grade_claude.py):
    {
      "id", "fonte", "tema", "gabarito",
      "modelo": "ft:gpt-4.1-...",
      "notas_geradas": {"c1"..."c5", "total"},
      "raw_output": <conteúdo bruto da resposta>,
      "latency_ms", "cost_usd", "error",
    }

`cost_usd` é calculado por `usage.prompt_tokens` e
`usage.completion_tokens` reais (OpenAI devolve em cada response).
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional


REPO = Path(__file__).resolve().parents[2]
BACKEND = REPO / "backend" / "notamil-backend"


def _bootstrap_backend_path() -> None:
    """Adiciona backend ao sys.path pra importar _SYSTEM_PROMPT_BASE."""
    s = str(BACKEND)
    if s not in sys.path:
        sys.path.insert(0, s)


# Modelo FT (hardcoded — único pro A/B; trocar exige re-treino)
FT_MODEL = "ft:gpt-4.1-2025-04-14:redato:redato-enem:BTBOS5VF"


# Tabela de preços OpenAI (USD por 1M tokens). FT do gpt-4.1 tem
# pricing diferente do gpt-4.1 base — atualizado em Abr/2025:
# input $5.00, output $20.00 (1.67× do base por causa do FT serving).
_PRECOS_OPENAI = {
    FT_MODEL: {"input": 5.0, "output": 20.0},
}


def _estimar_custo(input_tokens: int, output_tokens: int) -> float:
    """Custo USD baseado em tokens reais retornados em `usage`."""
    p = _PRECOS_OPENAI[FT_MODEL]
    return (
        (input_tokens / 1_000_000) * p["input"]
        + (output_tokens / 1_000_000) * p["output"]
    )


# ──────────────────────────────────────────────────────────────────────
# Parser de saída (3 níveis de fallback)
# ──────────────────────────────────────────────────────────────────────

# Regex pra "C1: 160" / "C1 = 160" / "C1 - 160" / "Competência 1: 160"
# Captura número de 0-200 (qualquer múltiplo de 40 cabe — não força).
_REGEX_NOTA_COMP = re.compile(
    r"(?:C(?:omp\w*)?\s*)?([1-5])\s*[:=\-–]\s*(\d{1,3})",
    re.IGNORECASE,
)


def _parse_notas(raw: str) -> Optional[Dict[str, int]]:
    """Tenta extrair notas {c1..c5, total} de `raw` (texto bruto da
    resposta do FT). 3 níveis:

    1. JSON direto — procura `{...}` no texto e tenta parsear. Aceita
       chaves c1/c2/c3/c4/c5 (lowercase) ou C1/C2/... (uppercase).
    2. Regex C1: 160 — varre texto procurando padrão "C<n>: <número>".
       Pega último match de cada competência (caso modelo justifique
       e depois dê nota final).
    3. Retorna None se nenhum funcionou.

    Sempre que retorna dict, garante 5 competências. `total` é soma.
    """
    if not raw or not raw.strip():
        return None

    # ── Nível 1: JSON inline ─────────────────────────────────────
    notas = _try_json_parse(raw)
    if notas is not None:
        return notas

    # ── Nível 2: Regex C1: 160 ───────────────────────────────────
    notas = _try_regex_parse(raw)
    if notas is not None:
        return notas

    return None


def _try_json_parse(raw: str) -> Optional[Dict[str, int]]:
    """Procura blocos `{...}` e tenta parsear como JSON com chaves
    c1-c5. Aceita variantes (cN, CN, competencia_N, etc.)."""
    # 3 estratégias, do mais provável ao menos:
    #   a. Texto inteiro como JSON (caso o FT respeitou formato puro).
    #   b. Maior bloco `{...}` balanceado (envelope com nested dicts).
    #   c. Blocos `{...}` flat (regex simples; pra notas sem aninhamento).
    candidates: List[str] = []
    stripped = raw.strip()
    if stripped.startswith("{"):
        candidates.append(stripped)

    # Maior bloco `{...}` balanceado — varre o texto contando braces.
    # Cobre o caso `{"C1": {"nota": 160}, ...}` (regex flat falha aí).
    stack = 0
    start = -1
    for i, ch in enumerate(raw):
        if ch == "{":
            if stack == 0:
                start = i
            stack += 1
        elif ch == "}":
            if stack > 0:
                stack -= 1
                if stack == 0 and start >= 0:
                    candidates.append(raw[start:i + 1])
                    start = -1

    # Blocos `{...}` flat (sem nesting) — fallback histórico.
    candidates.extend(re.findall(r"\{[^{}]*\}", raw, flags=re.DOTALL))

    # Dedupe preservando ordem (envelope grande vem antes do interno)
    seen: set = set()
    unique: List[str] = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            unique.append(c)

    for cand in unique:
        try:
            data = json.loads(cand)
        except (json.JSONDecodeError, ValueError):
            continue
        if not isinstance(data, dict):
            continue

        notas = _extrai_notas_dict(data)
        if notas is not None:
            return notas
    return None


def _extrai_notas_dict(data: Dict[str, Any]) -> Optional[Dict[str, int]]:
    """Recebe um dict possivelmente parseado de JSON; tenta extrair
    notas das chaves. Aceita várias variações de nomes de chave."""
    # Variantes aceitas: "c1"/"C1"/"competencia_1"/"competência_1"
    extraidas: Dict[str, int] = {}
    for n in range(1, 6):
        candidatos = [
            f"c{n}", f"C{n}",
            f"competencia_{n}", f"competência_{n}",
            f"competencia{n}", f"competência{n}",
            f"comp_{n}", f"comp{n}",
        ]
        valor: Optional[int] = None
        for k in candidatos:
            if k in data:
                v = data[k]
                if isinstance(v, dict):
                    # Caso aninhado: {"c1": {"nota": 160, ...}}
                    v = v.get("nota") or v.get("score") or v.get("valor")
                if isinstance(v, (int, float)):
                    valor = int(v)
                    break
        if valor is None:
            return None
        extraidas[f"c{n}"] = valor

    extraidas["total"] = sum(extraidas[f"c{n}"] for n in range(1, 6))
    return extraidas


def _try_regex_parse(raw: str) -> Optional[Dict[str, int]]:
    """Varre `raw` procurando padrões C<n>: <número>. Pega último
    match de cada competência (caso o FT justifique 'em C1 dei 160
    porque ...' e depois redunde 'C1: 160' no fim)."""
    matches = _REGEX_NOTA_COMP.findall(raw)
    if not matches:
        return None

    ultimo: Dict[str, int] = {}
    for comp_num, nota_str in matches:
        try:
            nota = int(nota_str)
        except ValueError:
            continue
        # Aceita só notas plausíveis (0-200; ENEM é múltiplo de 40)
        if nota < 0 or nota > 200:
            continue
        ultimo[f"c{comp_num}"] = nota

    if len(ultimo) < 5:
        return None
    for n in range(1, 6):
        if f"c{n}" not in ultimo:
            return None

    ultimo["total"] = sum(ultimo[f"c{n}"] for n in range(1, 6))
    return ultimo


# ──────────────────────────────────────────────────────────────────────
# Caminho principal
# ──────────────────────────────────────────────────────────────────────

def grade_ft(rec: Dict[str, Any]) -> Dict[str, Any]:
    """Avalia 1 redação com o GPT FT BTBOS5VF.

    `rec` é uma linha do eval_gold_v1.jsonl (com `id`, `tema`,
    `redacao.texto_original`, `notas_competencia`, `nota_global`).

    Pré-condição: OPENAI_API_KEY no env (caller valida).
    """
    _bootstrap_backend_path()

    # Lazy import — OpenAI SDK só carrega quando esse caminho roda
    from openai import OpenAI
    from redato_backend.dev_offline import _SYSTEM_PROMPT_BASE

    rid = rec["id"]
    tema = (rec.get("tema") or {}).get("titulo") or "Tema livre"
    content = (rec.get("redacao") or {}).get("texto_original") or ""

    user_msg = (
        f"TEMA: {tema}\n\n"
        f"REDAÇÃO DO ALUNO:\n\"\"\"\n{content}\n\"\"\"\n\n"
        "Avalie a redação acima pelas 5 competências ENEM. "
        "Retorne as notas no formato:\n"
        '{"c1": <0-200>, "c2": <0-200>, "c3": <0-200>, '
        '"c4": <0-200>, "c5": <0-200>}'
    )

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    start = time.time()
    try:
        response = client.chat.completions.create(
            model=FT_MODEL,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT_BASE},
                {"role": "user", "content": user_msg},
            ],
            temperature=0,
            max_tokens=4000,
        )
    except Exception as exc:  # noqa: BLE001
        return _erro(rec, elapsed=time.time() - start, exc=exc)

    elapsed_ms = int((time.time() - start) * 1000)

    # Extrai conteúdo da primeira choice
    if not response.choices:
        return _erro(
            rec, elapsed=elapsed_ms / 1000,
            exc=RuntimeError("FT retornou sem choices"),
        )

    raw_text = response.choices[0].message.content or ""

    # Parser robusto
    notas = _parse_notas(raw_text)
    if notas is None:
        return _erro(
            rec, elapsed=elapsed_ms / 1000,
            exc=RuntimeError(
                f"FT não retornou notas parseáveis. "
                f"Raw[:200]: {raw_text[:200]!r}"
            ),
            raw_output=raw_text,
        )

    # Custo via usage real
    usage = response.usage
    in_t = usage.prompt_tokens if usage else 0
    out_t = usage.completion_tokens if usage else 0
    custo = _estimar_custo(in_t, out_t)

    return _saida(
        rec, notas=notas, raw=raw_text,
        elapsed_ms=elapsed_ms, cost=custo,
    )


# ──────────────────────────────────────────────────────────────────────
# Helpers de saída (mesmo schema do grade_claude.py)
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
    rec: Dict[str, Any], *,
    notas: Dict[str, int], raw: str,
    elapsed_ms: int, cost: float,
) -> Dict[str, Any]:
    tema = (rec.get("tema") or {}).get("titulo") or "Tema livre"
    return {
        "id": rec["id"],
        "fonte": rec.get("fonte"),
        "tema": tema,
        "gabarito": _gabarito_de(rec),
        "modelo": FT_MODEL,
        "notas_geradas": notas,
        "raw_output": raw,
        "latency_ms": elapsed_ms,
        "cost_usd": round(cost, 6),
        "error": None,
    }


def _erro(
    rec: Dict[str, Any], *,
    elapsed: float, exc: Exception,
    raw_output: Optional[str] = None,
) -> Dict[str, Any]:
    tema = (rec.get("tema") or {}).get("titulo") or "Tema livre"
    return {
        "id": rec["id"],
        "fonte": rec.get("fonte"),
        "tema": tema,
        "gabarito": _gabarito_de(rec),
        "modelo": FT_MODEL,
        "notas_geradas": {"c1": 0, "c2": 0, "c3": 0,
                          "c4": 0, "c5": 0, "total": 0},
        "raw_output": raw_output,
        "latency_ms": int(elapsed * 1000),
        "cost_usd": 0.0,
        "error": f"{type(exc).__name__}: {exc}"[:300],
    }
