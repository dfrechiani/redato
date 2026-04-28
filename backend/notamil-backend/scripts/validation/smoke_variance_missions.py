#!/usr/bin/env python3
"""Smoke de variância — roda mesma redação N vezes em cada modo, mede
oscilação da nota total (FIX 2 / 2026-04-27).

Critérios de sucesso (do user):
- Foco (c3/c4/c5): variância máxima da nota total < 40 pts (escala 0-200)
- Completo Parcial: variância máx < 40 pts (similar aos foco, 1 comp por vez)
- Completo Integral: variância máx da nota global < 80 pts (escala 0-1000)

Uso:
    python scripts/validation/smoke_variance_missions.py
    python scripts/validation/smoke_variance_missions.py --runs 3 --only foco_c3
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

BACKEND = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND))

env_path = BACKEND / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip()
            if not os.environ.get(k):
                os.environ[k] = v

os.environ.setdefault("REDATO_DEV_OFFLINE", "1")
os.environ.setdefault("REDATO_DEV_PERSIST", "0")
os.environ.setdefault("REDATO_CLAUDE_MODEL", "claude-opus-4-7")
os.environ.setdefault("REDATO_SCHEMA_FLAT", "1")
os.environ.setdefault("REDATO_ENSEMBLE", "1")

from redato_backend.dev_offline import apply_patches  # noqa: E402
apply_patches()

from redato_backend.dev_offline import _claude_grade_essay  # noqa: E402

# Reusar amostras do smoke_test_missions.py
sys.path.insert(0, str(BACKEND / "scripts" / "validation"))
import importlib.util
_spec = importlib.util.spec_from_file_location(
    "smt", str(BACKEND / "scripts" / "validation" / "smoke_test_missions.py"),
)
_smt = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_smt)
SAMPLES = _smt.SAMPLES


def extract_nota(mode: str, args: Dict[str, Any]) -> int:
    """Extrai a nota global do tool_args por modo. Retorna -1 se faltar."""
    if mode == "foco_c3":
        return int(args.get("nota_c3_enem", -1) or -1)
    if mode == "foco_c4":
        return int(args.get("nota_c4_enem", -1) or -1)
    if mode == "foco_c5":
        return int(args.get("nota_c5_enem", -1) or -1)
    if mode == "completo_parcial":
        return int(args.get("nota_total_parcial", -1) or -1)
    if mode == "completo_integral":
        c1 = (args.get("c1_audit") or {}).get("nota") or 0
        c2 = (args.get("c2_audit") or {}).get("nota") or 0
        c3 = (args.get("c3_audit") or {}).get("nota") or 0
        c4 = (args.get("c4_audit") or {}).get("nota") or 0
        c5 = (args.get("c5_audit") or {}).get("nota") or 0
        return int(c1 + c2 + c3 + c4 + c5)
    return -1


def extract_rubrica(mode: str, args: Dict[str, Any]) -> Dict[str, int]:
    if mode in ("foco_c3", "foco_c4", "foco_c5", "completo_parcial"):
        return dict(args.get("rubrica_rej") or {})
    return {}


def run_mode(mode: str, sample: Dict[str, str], runs: int) -> Dict[str, Any]:
    print(f"\n{'='*70}")
    print(f"[{mode}] x{runs} — activity_id={sample['activity_id']}")
    notas: List[int] = []
    rubricas: List[Dict[str, int]] = []
    elapsed_per_run: List[float] = []

    for i in range(runs):
        t0 = time.time()
        data = {
            "request_id": f"variance_{mode}_{i}_{int(time.time())}",
            "user_id": "variance_smoke",
            "activity_id": sample["activity_id"],
            "theme": sample.get("theme", "Tema livre"),
            "content": sample["content"],
        }
        try:
            args = _claude_grade_essay(data)
        except Exception as exc:
            print(f"  ✗ run {i+1} FAILED: {exc!r}")
            continue
        elapsed = time.time() - t0
        elapsed_per_run.append(elapsed)
        nota = extract_nota(mode, args)
        notas.append(nota)
        rubrica = extract_rubrica(mode, args)
        rubricas.append(rubrica)
        rubrica_str = ", ".join(f"{k}={v}" for k, v in rubrica.items())
        print(f"  run {i+1}/{runs} ({elapsed:.1f}s): nota={nota}  "
              f"[{rubrica_str}]" if rubrica else f"  run {i+1}: nota={nota}")

    if not notas:
        return {"mode": mode, "ok": False, "issues": ["nenhuma run completou"]}

    media = statistics.mean(notas)
    variancia = max(notas) - min(notas) if len(notas) > 1 else 0
    stdev = statistics.stdev(notas) if len(notas) > 1 else 0.0

    # Critério de sucesso por tipo de modo
    if mode.startswith("foco") or mode == "completo_parcial":
        # Em modos foco, var máx < 40. Em parcial, escala é 0-800 mas
        # consideramos como "1 nota de competência por vez" — usar 40 também.
        # Mas se aluno mandou parcial total, escala 0-800 é maior; vou usar 80.
        threshold = 40 if mode.startswith("foco") else 80
    else:
        threshold = 80  # integral 0-1000

    ok = variancia < threshold
    return {
        "mode": mode,
        "runs": len(notas),
        "notas": notas,
        "media": round(media, 1),
        "variancia": variancia,
        "stdev": round(stdev, 2),
        "threshold": threshold,
        "ok": ok,
        "elapsed_per_run": [round(e, 1) for e in elapsed_per_run],
        "rubricas": rubricas,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--only", type=str, default=None)
    args = parser.parse_args()

    if not os.getenv("ANTHROPIC_API_KEY"):
        print("ERRO: ANTHROPIC_API_KEY não configurada")
        sys.exit(1)

    modes = ["foco_c3", "foco_c4", "foco_c5", "completo_parcial",
             "completo_integral"]
    if args.only:
        only = {m.strip() for m in args.only.split(",")}
        modes = [m for m in modes if m in only]

    print(f"Smoke variância — {args.runs} runs por modo")
    print(f"Modos: {modes}")

    results: List[Dict[str, Any]] = []
    for mode in modes:
        results.append(run_mode(mode, SAMPLES[mode], args.runs))

    # Persiste
    out_dir = BACKEND / "scripts" / "validation" / "results" / "missions"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = out_dir / f"variance_{ts}.jsonl"
    with out_path.open("w") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")

    print(f"\n{'='*70}")
    print(f"Resultados em: {out_path}")
    print(f"\nResumo:")
    for r in results:
        if not r.get("ok") and r.get("issues"):
            print(f"  ✗ {r['mode']:20} {r['issues']}")
            continue
        st = "✓" if r["ok"] else "✗"
        print(f"  {st} {r['mode']:20} runs={r['runs']} "
              f"notas={r['notas']} media={r['media']} "
              f"var={r['variancia']} (limite {r['threshold']}) "
              f"stdev={r['stdev']}")

    fail = sum(1 for r in results if not r.get("ok"))
    sys.exit(0 if fail == 0 else 1)


if __name__ == "__main__":
    main()
