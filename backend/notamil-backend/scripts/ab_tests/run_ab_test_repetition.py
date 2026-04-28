#!/usr/bin/env python3
"""
A/B test: repetition addendum vs baseline.

Roda cada canário N vezes em cada condição (A=baseline, B=com addendum),
salva resultados brutos em scripts/ab_tests/results/repetition_ab_*.json.

Uso (do diretório backend/notamil-backend):
    REDATO_DEV_OFFLINE=1 python scripts/ab_tests/run_ab_test_repetition.py

Custo estimado: 11 × 2 × 5 = 110 chamadas × ~$0.05 = ~$5.50.
"""
from __future__ import annotations

import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_DIR.parent.parent
CANARIOS_PATH = REPO_ROOT / "docs" / "redato" / "v2" / "canarios.yaml"
RESULTS_DIR = BACKEND_DIR / "scripts" / "ab_tests" / "results"

sys.path.insert(0, str(BACKEND_DIR))
os.environ.setdefault("REDATO_DEV_OFFLINE", "1")
os.environ.setdefault("REDATO_DEV_PERSIST", "0")
# Ensemble e self-critique desligados — variáveis separadas, não condições do A/B.
os.environ["REDATO_ENSEMBLE"] = "1"
os.environ["REDATO_SELF_CRITIQUE"] = "0"

from redato_backend.dev_offline import apply_patches  # noqa: E402

apply_patches()

from redato_backend.dev_offline import _claude_grade_essay  # noqa: E402


RUNS_PER_CONDITION = 5
MAX_PARALLEL = 3  # respeita rate limit


def load_canarios() -> List[Dict[str, Any]]:
    import yaml
    raw = yaml.safe_load(CANARIOS_PATH.read_text(encoding="utf-8"))
    if isinstance(raw, dict) and "canarios" in raw:
        return raw["canarios"]
    if isinstance(raw, list):
        return raw
    raise ValueError(f"Estrutura inesperada em {CANARIOS_PATH}")


def _extract_notas(tool_args: Dict[str, Any]) -> Dict[str, int]:
    notas: Dict[str, int] = {}
    for key in ("c1", "c2", "c3", "c4", "c5"):
        audit = tool_args.get(f"{key}_audit") or {}
        nota = audit.get("nota")
        notas[key] = int(nota) if isinstance(nota, (int, float)) else 0
    notas["total"] = sum(notas[k] for k in ("c1", "c2", "c3", "c4", "c5"))
    return notas


def run_single(canary: Dict[str, Any], condition: str, run_idx: int) -> Dict[str, Any]:
    """Roda um canário em uma condição. condition='A' (off) ou 'B' (on)."""
    os.environ["REDATO_REPETITION_FLAG"] = "1" if condition == "B" else "0"

    start = time.time()
    request_id = f"ab-{canary['id']}-{condition}-{run_idx}-{int(start)}"
    try:
        tool_args = _claude_grade_essay({
            "request_id": request_id,
            "user_id": "ab-bot",
            "content": canary["essay"],
            "theme": "Impactos das redes sociais na saúde mental dos jovens",
        })
        notas = _extract_notas(tool_args)
        return {
            "canary_id": canary["id"],
            "condition": condition,
            "run_idx": run_idx,
            "ok": True,
            "notas": notas,
            "tool_args": tool_args,
            "latency_ms": int((time.time() - start) * 1000),
        }
    except Exception as exc:
        return {
            "canary_id": canary["id"],
            "condition": condition,
            "run_idx": run_idx,
            "ok": False,
            "error": repr(exc),
            "latency_ms": int((time.time() - start) * 1000),
        }


def main() -> None:
    canarios = load_canarios()
    print(f"Carregados {len(canarios)} canários de {CANARIOS_PATH}")

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERRO: ANTHROPIC_API_KEY não setada. Defina em backend/.env.", file=sys.stderr)
        sys.exit(2)

    jobs = [
        (c, cond, idx)
        for c in canarios
        for cond in ("A", "B")
        for idx in range(RUNS_PER_CONDITION)
    ]
    print(f"Total: {len(jobs)} runs ({len(canarios)} × 2 condições × {RUNS_PER_CONDITION})")
    print(f"Custo estimado: ~${len(jobs) * 0.05:.2f}\n")

    results: List[Dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=MAX_PARALLEL) as ex:
        futures = {
            ex.submit(run_single, c, cond, idx): (c["id"], cond, idx)
            for c, cond, idx in jobs
        }
        for i, fut in enumerate(as_completed(futures), 1):
            r = fut.result()
            results.append(r)
            mark = "✓" if r["ok"] else "✗"
            cid = r["canary_id"]
            cond = r["condition"]
            idx = r["run_idx"]
            extra = ""
            if r["ok"]:
                extra = f" total={r['notas']['total']:>4} ({r['latency_ms']/1000:.1f}s)"
            else:
                extra = f" ERROR: {r.get('error', '?')[:80]}"
            print(f"  [{i:>3}/{len(jobs)}] {mark} {cid:<35} cond={cond} run={idx}{extra}")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output = RESULTS_DIR / f"repetition_ab_{timestamp}.json"

    with open(output, "w", encoding="utf-8") as f:
        json.dump({
            "experiment": "repetition_flag_ab",
            "timestamp": timestamp,
            "config": {
                "model": os.environ.get("REDATO_CLAUDE_MODEL", "claude-sonnet-4-6"),
                "runs_per_condition": RUNS_PER_CONDITION,
                "n_canarios": len(canarios),
            },
            "results": results,
        }, f, ensure_ascii=False, indent=2)

    print(f"\n  Saved: {output}")
    print(f"  Próximo passo: python scripts/ab_tests/analyze_ab_results.py {output} {CANARIOS_PATH}")


if __name__ == "__main__":
    main()
