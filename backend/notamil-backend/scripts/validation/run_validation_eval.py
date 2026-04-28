#!/usr/bin/env python3
"""
Etapa 2 — Roda Redato em batch contra um eval set (gold ou real-world).

Usa o pipeline real (mesmo `_claude_grade_essay` que produção) com:
  REDATO_DEV_OFFLINE=1   (BQ/Firestore stubados em memória, sem GCP)
  REDATO_SELF_CRITIQUE=0 (eval estatístico — desligado)
  REDATO_ENSEMBLE=1      (N=1)
  REDATO_TWO_STAGE=1     (derivação mecânica ON, padrão de produção)
  Modelo: claude-sonnet-4-6

Threading: ThreadPoolExecutor max_workers=5.

Uso (de backend/notamil-backend):
    python scripts/validation/run_validation_eval.py \\
        --input scripts/validation/data/eval_gold_v1.jsonl \\
        --output scripts/validation/results/eval_gold_run.jsonl \\
        --eval-name gold
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

BACKEND_DIR = Path(__file__).resolve().parents[2]

sys.path.insert(0, str(BACKEND_DIR))

# Configura ambiente ANTES de importar redato_backend pra que dev_offline.py
# leia os flags corretos.
os.environ.setdefault("REDATO_DEV_OFFLINE", "1")
os.environ.setdefault("REDATO_DEV_PERSIST", "0")
os.environ["REDATO_SELF_CRITIQUE"] = "0"
os.environ["REDATO_ENSEMBLE"] = "1"
os.environ["REDATO_TWO_STAGE"] = "1"
os.environ.setdefault("REDATO_CLAUDE_MODEL", "claude-sonnet-4-6")

from redato_backend.dev_offline import apply_patches  # noqa: E402

apply_patches()

# IMPORTANTE: apply_patches() chama load_dotenv(override=True), que sobrescreve
# nossas configs com o .env (que tem REDATO_SELF_CRITIQUE=1 por padrão pra
# uso casual). Re-aplicamos as configs aqui pra que o eval estatístico não
# inflate custo/tempo nem polua cache com 2x de chamadas.
os.environ["REDATO_SELF_CRITIQUE"] = "0"
os.environ["REDATO_ENSEMBLE"] = "1"
os.environ["REDATO_TWO_STAGE"] = "1"

from redato_backend.dev_offline import (  # noqa: E402
    _claude_grade_essay,
    _derive_c1_nota,
    _derive_c2_nota,
    _derive_c3_nota,
    _derive_c4_nota,
    _derive_c5_nota,
)


def extract_notas(tool_args: Dict[str, Any]) -> Dict[str, int]:
    """Extrai notas finais. Auto-detecta schema:
    - v3 (holística): top-level `notas` dict.
    - v2 (mecânica): `cN_audit.nota` por competência.
    """
    out: Dict[str, int] = {}
    notas_v3 = tool_args.get("notas") if isinstance(tool_args, dict) else None
    if isinstance(notas_v3, dict):
        for k in ("c1", "c2", "c3", "c4", "c5"):
            v = notas_v3.get(k)
            out[k] = int(v) if isinstance(v, (int, float)) else 0
    else:
        for k in ("c1", "c2", "c3", "c4", "c5"):
            audit = tool_args.get(f"{k}_audit") or {}
            v = audit.get("nota")
            out[k] = int(v) if isinstance(v, (int, float)) else 0
    out["total"] = sum(out[k] for k in ("c1", "c2", "c3", "c4", "c5"))
    return out


def derive_notas_from_audit(tool_args: Dict[str, Any]) -> Dict[str, int]:
    """Roda _derive_cN_nota em cada audit (só faz sentido em v2).
    Em v3 (holística), retorna mesmas notas finais — não há "derivação"."""
    if isinstance(tool_args.get("notas"), dict):
        # v3: derivação == final (notas vêm direto do LLM, sem post-processing)
        return extract_notas(tool_args)
    derivers = {"c1": _derive_c1_nota, "c2": _derive_c2_nota,
                "c3": _derive_c3_nota, "c4": _derive_c4_nota,
                "c5": _derive_c5_nota}
    out: Dict[str, int] = {}
    for k, fn in derivers.items():
        audit = tool_args.get(f"{k}_audit") or {}
        try:
            out[k] = int(fn(audit))
        except Exception:
            out[k] = 0
    out["total"] = sum(out[k] for k in ("c1", "c2", "c3", "c4", "c5"))
    return out


def _strip_audit_only(tool_args: Dict[str, Any]) -> Dict[str, Any]:
    """Mantém só os campos diagnósticos. Auto-detecta schema:
    - v3: notas, flags, evidencias, audit_prose
    - v2: cN_audit + meta_checks (sem feedback_text/priorization gigantes)
    """
    if isinstance(tool_args.get("notas"), dict):
        keep = ("notas", "flags", "evidencias", "audit_prose", "_rubrica")
    else:
        keep = ("essay_analysis", "preanulation_checks",
                "c1_audit", "c2_audit", "c3_audit", "c4_audit", "c5_audit",
                "meta_checks")
    return {k: tool_args.get(k) for k in keep if k in tool_args}


def grade_one(rec: Dict[str, Any], eval_name: str) -> Dict[str, Any]:
    """Roda Redato em uma redação. Retorna dict com gabarito + redato + meta."""
    start = time.time()
    rid = rec["id"]
    tema = ((rec.get("tema") or {}).get("titulo") or "").strip()
    content = ((rec.get("redacao") or {}).get("texto_original") or "").strip()
    fonte = rec.get("fonte", "?")

    request_id = f"val-{eval_name}-{rid}-{int(start*1000)}"
    try:
        tool_args = _claude_grade_essay({
            "request_id": request_id,
            "user_id": "validation-bot",
            "content": content,
            "theme": tema,
        })
        elapsed_ms = int((time.time() - start) * 1000)
        gabarito_notas = rec.get("notas_competencia") or {}
        gabarito_total = rec.get("nota_global")

        # `tool_args["cN_audit"]["nota"]` já vem com a derivação aplicada
        # (REDATO_TWO_STAGE=1). Pra ter a derivação isolada, rodamos os
        # _derive_cN_nota de novo. Se two-stage estivesse OFF, redato_final
        # seria a nota emitida pelo LLM, não a derivada.
        return {
            "id": rid,
            "fonte": fonte,
            "eval_name": eval_name,
            "tema": tema,
            "gabarito": {
                "total": gabarito_total,
                "c1": gabarito_notas.get("c1"),
                "c2": gabarito_notas.get("c2"),
                "c3": gabarito_notas.get("c3"),
                "c4": gabarito_notas.get("c4"),
                "c5": gabarito_notas.get("c5"),
            },
            "redato_audit": _strip_audit_only(tool_args),
            "redato_derivacao": derive_notas_from_audit(tool_args),
            "redato_final": extract_notas(tool_args),
            "latency_ms": elapsed_ms,
            "error": None,
        }
    except Exception as exc:
        return {
            "id": rid,
            "fonte": fonte,
            "eval_name": eval_name,
            "tema": tema,
            "gabarito": {
                "total": rec.get("nota_global"),
                **(rec.get("notas_competencia") or {}),
            },
            "redato_audit": None,
            "redato_derivacao": None,
            "redato_final": None,
            "latency_ms": int((time.time() - start) * 1000),
            "error": repr(exc)[:300],
        }


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def append_jsonl(path: Path, record: Dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--eval-name", type=str, required=True,
                        help="Tag descritivo: 'gold' ou 'realworld'")
    parser.add_argument("--workers", type=int, default=5)
    parser.add_argument("--limit", type=int, default=0,
                        help="Se > 0, processa apenas as N primeiras redações (debug)")
    args = parser.parse_args()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERRO: ANTHROPIC_API_KEY não setada", file=sys.stderr)
        sys.exit(2)

    redacoes = load_jsonl(args.input)
    if args.limit > 0:
        redacoes = redacoes[: args.limit]

    print(f"Eval: {args.eval_name}")
    print(f"Modelo: {os.environ['REDATO_CLAUDE_MODEL']}")
    print(f"Input:  {args.input} ({len(redacoes)} redações)")
    print(f"Output: {args.output}")
    print(f"Workers: {args.workers}\n")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    # Trunca arquivo de saída pra esse run
    args.output.write_text("")

    t_start = time.time()
    n_done = 0
    n_ok = 0
    n_err = 0

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(grade_one, rec, args.eval_name): rec
            for rec in redacoes
        }
        for fut in as_completed(futures):
            try:
                result = fut.result()
            except Exception as exc:
                rec = futures[fut]
                result = {
                    "id": rec.get("id"),
                    "fonte": rec.get("fonte"),
                    "eval_name": args.eval_name,
                    "redato": None,
                    "error": f"unhandled_in_executor: {repr(exc)[:200]}",
                }
            append_jsonl(args.output, result)
            n_done += 1
            if result.get("error"):
                n_err += 1
            else:
                n_ok += 1

            # Progress a cada 10 ou na última
            if n_done % 10 == 0 or n_done == len(redacoes):
                elapsed = time.time() - t_start
                rate = n_done / max(elapsed, 1)
                eta_min = (len(redacoes) - n_done) / max(rate, 0.001) / 60
                print(f"  [{n_done:>3}/{len(redacoes)}] "
                      f"ok={n_ok} err={n_err} "
                      f"rate={rate:.2f}/s "
                      f"elapsed={elapsed/60:.1f}min "
                      f"eta={eta_min:.1f}min")

    total_min = (time.time() - t_start) / 60
    print(f"\nFinalizado em {total_min:.1f}min")
    print(f"Sucessos: {n_ok}/{len(redacoes)} ({n_ok/len(redacoes)*100:.1f}%)")
    print(f"Erros: {n_err}")
    print(f"Output: {args.output}")


if __name__ == "__main__":
    main()
