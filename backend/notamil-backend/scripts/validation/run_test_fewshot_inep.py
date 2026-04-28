#!/usr/bin/env python3
"""Test 2 — Sonnet 4.6 em v2 + few-shot INEP, mesmas 20 redações do Test 1.

Substitui o bloco _FEW_SHOT_EXAMPLES (v2 mecânico) por demonstrações
baseadas em comentários oficiais INEP (corpus inep.jsonl). Mantém persona,
rubrica v2 e grading tail intactos. Usa o mesmo schema _SUBMIT_CORRECTION_TOOL
da v2 — só muda calibração via few-shot.

Uso (de backend/notamil-backend):
    python scripts/validation/run_test_fewshot_inep.py \\
        --ids /tmp/test20_ids.txt \\
        --output scripts/validation/results/eval_test_fewshot_run.jsonl
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List

BACKEND = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND))

os.environ.setdefault("REDATO_DEV_OFFLINE", "1")
os.environ.setdefault("REDATO_DEV_PERSIST", "0")

try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except ImportError:
    pass

import anthropic

from redato_backend.dev_offline import (
    _SYSTEM_PROMPT_BASE,
    _GRADING_TAIL_INSTRUCTION,
    _SUBMIT_CORRECTION_TOOL,
)

CORPUS = Path("/Users/danielfrechiani/Desktop/redato_hash/ingest/data/final/unified.jsonl")
INEP = Path("/Users/danielfrechiani/Desktop/redato_hash/ingest/data/interim/inep.jsonl")

# 2 INEP nota 1000 selecionados manualmente:
# - inep_2024_07: abertura por C1 ("excelente domínio modalidade"), 3880 chars
# - inep_2025_01: abertura por C3 ("projeto bem estruturado"), 3736 chars
FEWSHOT_IDS = ("inep_2024_07", "inep_2025_01")


def build_fewshot_block() -> str:
    """Constrói bloco de few-shot a partir de 2 redações INEP nota 1000.

    Cada exemplo: tema + texto da redação + gabarito numérico (5 comp +
    total) + comentário oficial INEP. Frame: 'banca real avaliou assim'.
    """
    inep_by_id: Dict[str, Dict[str, Any]] = {}
    with INEP.open(encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if r["id"] in FEWSHOT_IDS:
                inep_by_id[r["id"]] = r

    parts: List[str] = []
    parts.append("## Exemplos calibradores — comentários oficiais INEP em redações nota 1000\n")
    parts.append(
        "Estes 2 exemplos vêm da Cartilha do Participante INEP. São redações que a "
        "**banca oficial avaliou nota 1000**, com o comentário detalhado da própria banca. "
        "Use-os como calibração de PADRÃO REAL: redação 1000 NÃO é redação perfeita "
        "(35 dos 38 comentários INEP em nota 1000 mencionam pelo menos um desvio). "
        "A banca aponta imprecisões, repetições e pequenos problemas — sem rebaixar a nota. "
        "Sua tarefa é calibrar seu julgamento por essa régua: tolerância em redações de "
        "qualidade, severidade em redações claramente fracas.\n"
    )

    for idx, fid in enumerate(FEWSHOT_IDS, 1):
        rec = inep_by_id[fid]
        tema = (rec.get("tema") or {}).get("titulo") or "(tema na cartilha)"
        texto = (rec.get("redacao") or {}).get("texto_original") or ""
        gab = rec.get("notas_competencia") or {}
        comentario = (rec.get("comentarios") or {}).get("geral") or ""

        parts.append(f"---\n### Exemplo INEP {idx} — {fid}\n")
        parts.append(f"**Tema:** {tema}\n")
        parts.append(f"**Gabarito INEP:** "
                     f"C1={gab.get('c1')} · C2={gab.get('c2')} · "
                     f"C3={gab.get('c3')} · C4={gab.get('c4')} · "
                     f"C5={gab.get('c5')} · TOTAL={rec.get('nota_global')}\n")
        parts.append(f"**Texto da redação:**\n```\n{texto.strip()}\n```\n")
        parts.append(f"**Comentário oficial da banca INEP (calibração de tom e severidade):**\n\n"
                     f"{comentario.strip()}\n")

    parts.append("---\n")
    parts.append(
        "**Como usar estes exemplos:** ao avaliar uma nova redação, ajuste sua escala "
        "considerando que 1000 não exige perfeição. Em C1, a banca tolera 1-3 desvios "
        "pontuais não-reincidentes em texto longo bem estruturado. Em C2, repertório "
        "produtivo (não decorativo) é o que conta — não busque fonte citada formalmente. "
        "Em C3, projeto de texto bem definido com estratégia argumentativa legível é "
        "200, mesmo sem 'autoria' explícita. Em C4, conectivo com relação semântica "
        "adequada é o critério, não diversidade pela diversidade. Em C5, qualidade "
        "integrada da proposta (concreta + detalhada + articulada à discussão) "
        "supera contagem de elementos.\n"
    )
    parts.append(
        "Mas: o tool schema desta avaliação ainda exige preenchimento dos campos de "
        "auditoria da v2 (c1_audit, c2_audit, etc.). Preencha-os com fidelidade aos "
        "campos requeridos, mas calibre as notas finais (nota_final em cada cN_audit) "
        "pelo padrão INEP demonstrado acima.\n"
    )
    return "\n".join(parts)


def grade_one(client: anthropic.Anthropic, model: str, fewshot_block: str,
              rec: Dict[str, Any]) -> Dict[str, Any]:
    """Roda Claude com v2 + fewshot INEP, schema v2."""
    rid = rec["id"]
    tema = (rec.get("tema") or {}).get("titulo") or "Tema livre"
    content = (rec.get("redacao") or {}).get("texto_original") or ""

    user_msg = (
        f"TEMA: {tema}\n\n"
        f"REDAÇÃO DO ALUNO:\n\"\"\"\n{content}\n\"\"\"\n\n"
        "Avalie a redação acima pelas 5 competências ENEM, calibrando seu "
        "julgamento pelos exemplos INEP do system prompt. "
        "Chame `submit_correction` preenchendo TODOS os campos de auditoria."
    )

    start = time.time()
    try:
        message = client.messages.create(
            model=model,
            max_tokens=8000,
            system=[
                {"type": "text", "text": _SYSTEM_PROMPT_BASE},
                {"type": "text", "text": fewshot_block,
                 "cache_control": {"type": "ephemeral", "ttl": "1h"}},
                {"type": "text", "text": _GRADING_TAIL_INSTRUCTION,
                 "cache_control": {"type": "ephemeral", "ttl": "1h"}},
            ],
            tools=[_SUBMIT_CORRECTION_TOOL],
            tool_choice={"type": "tool", "name": "submit_correction"},
            messages=[{"role": "user", "content": user_msg}],
        )
        elapsed_ms = int((time.time() - start) * 1000)

        for block in message.content:
            if (getattr(block, "type", None) == "tool_use"
                    and getattr(block, "name", None) == "submit_correction"):
                tool_args = dict(getattr(block, "input", {}) or {})
                # Extrai notas direto do audit (sem two-stage — fewshot
                # objetivo é calibração de juízo do LLM, não derivação)
                notas = {}
                for k in ("c1", "c2", "c3", "c4", "c5"):
                    audit = tool_args.get(f"{k}_audit") or {}
                    n = audit.get("nota")
                    notas[k] = int(n) if isinstance(n, (int, float)) else 0
                notas["total"] = sum(notas[k] for k in ("c1","c2","c3","c4","c5"))
                gab_notas = rec.get("notas_competencia") or {}
                return {
                    "id": rid,
                    "fonte": rec.get("fonte"),
                    "tema": tema,
                    "gabarito": {
                        "total": rec.get("nota_global"),
                        "c1": gab_notas.get("c1"), "c2": gab_notas.get("c2"),
                        "c3": gab_notas.get("c3"), "c4": gab_notas.get("c4"),
                        "c5": gab_notas.get("c5"),
                    },
                    "redato_final": notas,
                    "latency_ms": elapsed_ms,
                    "error": None,
                }

        return {"id": rid, "error": "no tool_use", "latency_ms": elapsed_ms}
    except Exception as exc:
        return {"id": rid, "error": repr(exc)[:300],
                "latency_ms": int((time.time()-start)*1000)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ids", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", type=str, default="claude-sonnet-4-6")
    parser.add_argument("--workers", type=int, default=5)
    args = parser.parse_args()

    target_ids = set(l.strip() for l in args.ids.read_text().splitlines() if l.strip())
    print(f"Target IDs: {len(target_ids)}")

    selected = []
    with CORPUS.open(encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if r["id"] in target_ids:
                selected.append(r)
    print(f"Encontradas no corpus: {len(selected)}")

    fewshot_block = build_fewshot_block()
    print(f"Fewshot block: {len(fewshot_block)} chars")
    print(f"Modelo: {args.model}")
    print()

    client = anthropic.Anthropic()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("")

    t0 = time.time()
    n_ok = 0
    n_err = 0
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = {ex.submit(grade_one, client, args.model, fewshot_block, r): r
                   for r in selected}
        for i, fut in enumerate(as_completed(futures), 1):
            r = fut.result()
            with args.output.open("a", encoding="utf-8") as f:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
            mark = "✓" if not r.get("error") else "✗"
            if r.get("error"):
                n_err += 1
                extra = f"  ERR: {r['error'][:60]}"
            else:
                n_ok += 1
                extra = f"  total={r['redato_final']['total']:>4}  ({r['latency_ms']/1000:.0f}s)"
            print(f"  [{i:>2}/{len(selected)}] {mark} {r['id']:<45}{extra}")

    elapsed_min = (time.time()-t0) / 60
    print(f"\nFinalizado em {elapsed_min:.1f}min")
    print(f"OK: {n_ok}  Errors: {n_err}")


if __name__ == "__main__":
    main()
