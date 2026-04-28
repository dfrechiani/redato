#!/usr/bin/env python3
"""Re-roda só as 10 redações selecionadas para diagnóstico cirúrgico do
viés observado no eval_gold. Saída inclui audit completo, derivação Python
isolada e nota final.
"""
from __future__ import annotations

import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND_DIR))

os.environ.setdefault("REDATO_DEV_OFFLINE", "1")
os.environ.setdefault("REDATO_DEV_PERSIST", "0")

from redato_backend.dev_offline import apply_patches
apply_patches()
os.environ["REDATO_SELF_CRITIQUE"] = "0"
os.environ["REDATO_ENSEMBLE"] = "1"
os.environ["REDATO_TWO_STAGE"] = "1"
os.environ.setdefault("REDATO_CLAUDE_MODEL", "claude-sonnet-4-6")

# Re-uses helpers from run_validation_eval
from scripts.validation.run_validation_eval import grade_one  # type: ignore

CORPUS = Path("/Users/danielfrechiani/Desktop/redato_hash/ingest/data/final/unified.jsonl")
IDS = Path("/tmp/diagnostic_ids.txt")
OUT = Path("scripts/validation/results/eval_gold_diagnostic_run.jsonl")


def main() -> None:
    ids = [line.strip() for line in IDS.read_text().splitlines() if line.strip()]
    print(f"IDs alvo: {len(ids)}")

    # Carrega só esses do corpus
    selected = []
    with CORPUS.open(encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if r["id"] in ids:
                selected.append(r)
                if len(selected) == len(ids):
                    break
    print(f"Encontradas: {len(selected)}\n")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("")

    t0 = time.time()
    results = []
    with ThreadPoolExecutor(max_workers=5) as ex:
        futures = {ex.submit(grade_one, r, "gold-diagnostic"): r for r in selected}
        for fut in as_completed(futures):
            res = fut.result()
            results.append(res)
            with OUT.open("a", encoding="utf-8") as f:
                f.write(json.dumps(res, ensure_ascii=False) + "\n")
            mark = "✓" if not res.get("error") else "✗"
            note = ""
            if res.get("redato_final"):
                note = f"  red={res['redato_final']['total']:>4}"
            print(f"  {mark} {res['id']:<45}{note}  {res['latency_ms']/1000:.1f}s")

    print(f"\nTotal: {(time.time()-t0)/60:.1f}min")
    print(f"Output: {OUT}")


if __name__ == "__main__":
    main()
