#!/usr/bin/env python3
"""Reusa run_validation_eval.grade_one nas N redações listadas em --ids.
Modelo controlado via REDATO_CLAUDE_MODEL no env. Usado pelo Test 1 (Opus
em v2 nas mesmas 20 redações do Test 2)."""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND))

os.environ.setdefault("REDATO_DEV_OFFLINE", "1")
os.environ.setdefault("REDATO_DEV_PERSIST", "0")

from redato_backend.dev_offline import apply_patches
apply_patches()

# Override .env após apply_patches (load_dotenv override=True roda lá dentro)
os.environ["REDATO_SELF_CRITIQUE"] = "0"
os.environ["REDATO_ENSEMBLE"] = "1"
os.environ["REDATO_TWO_STAGE"] = "1"
os.environ.pop("REDATO_RUBRICA", None)  # default v2

from scripts.validation.run_validation_eval import grade_one


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--ids", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--eval-name", type=str, required=True)
    p.add_argument("--workers", type=int, default=5)
    args = p.parse_args()

    target = set(l.strip() for l in args.ids.read_text().splitlines() if l.strip())
    corpus = []
    with open("/Users/danielfrechiani/Desktop/redato_hash/ingest/data/final/unified.jsonl") as f:
        for line in f:
            r = json.loads(line)
            if r["id"] in target:
                corpus.append(r)
    print(f"Modelo: {os.environ.get('REDATO_CLAUDE_MODEL', 'claude-sonnet-4-6')}")
    print(f"Eval: {args.eval_name}  ·  Targets: {len(corpus)}/{len(target)}\n")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("")

    t0 = time.time()
    n_ok = n_err = 0
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = {ex.submit(grade_one, r, args.eval_name): r for r in corpus}
        for i, fut in enumerate(as_completed(futures), 1):
            res = fut.result()
            with args.output.open("a", encoding="utf-8") as f:
                f.write(json.dumps(res, ensure_ascii=False) + "\n")
            mark = "✓" if not res.get("error") else "✗"
            if res.get("error"):
                n_err += 1
                extra = f"  ERR: {res['error'][:60]}"
            else:
                n_ok += 1
                rf = res.get("redato_final") or {}
                extra = f"  total={rf.get('total','?'):>4}  ({res['latency_ms']/1000:.0f}s)"
            print(f"  [{i:>2}/{len(corpus)}] {mark} {res['id']:<45}{extra}")

    print(f"\nFinalizado em {(time.time()-t0)/60:.1f}min  OK={n_ok} ERR={n_err}")


if __name__ == "__main__":
    main()
