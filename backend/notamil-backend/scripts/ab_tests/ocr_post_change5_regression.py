#!/usr/bin/env python3
"""Regression eval pós-Mudança 5: chama o AnthropicVisionAgent real
(que agora respeita OCR_USE_CLOUD_VISION). Confere que % uncertain bate
com baseline Solo orig (~3.5%).

Uso (de backend/notamil-backend):
    python scripts/ab_tests/ocr_post_change5_regression.py \\
        --samples scripts/ab_tests/ocr_samples/ --n-images 5 --n-reps 2
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import os
import re
import sys
import time
from pathlib import Path
from statistics import mean, stdev
from typing import Any, Dict, List

try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except ImportError:
    pass

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from redato_backend.functions.essay_ocr.vision.anthropic_vision import (
    AnthropicVisionAgent,
)
from redato_backend.shared.constants import (
    ANTHROPIC_CLAUDE_MODEL,
    OCR_USE_CLOUD_VISION,
)


def resize_for_frontend(p: Path, max_w=1800, q=92) -> bytes:
    img = Image.open(p)
    if img.mode != "RGB":
        img = img.convert("RGB")
    if img.width > max_w:
        h = int(img.height * (max_w / img.width))
        img = img.resize((max_w, h), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=q)
    return buf.getvalue()


def count_metrics(transcription: str) -> dict:
    uncertain = len(re.findall(r"<uncertain\b", transcription))
    cleaned = re.sub(r"<[^>]+>", " ", transcription)
    words = cleaned.split()
    total = len(words)
    return {
        "uncertain_count": uncertain,
        "total_words": total,
        "uncertain_pct": round(uncertain / max(total, 1) * 100, 1),
    }


def run_one(image_path: Path) -> dict:
    image_bytes = resize_for_frontend(image_path)
    image_b64 = base64.b64encode(image_bytes).decode("ascii")
    start = time.time()
    try:
        agent = AnthropicVisionAgent(image_b64)
        result, _ = agent.deploy()
        elapsed = time.time() - start
        m = count_metrics(result.transcription)
        return {"image": image_path.name, "ok": True,
                "elapsed_s": round(elapsed, 1), **m,
                "theme": result.theme,
                "transcription": result.transcription}
    except Exception as e:
        return {"image": image_path.name, "ok": False,
                "error": repr(e)[:300],
                "elapsed_s": round(time.time() - start, 1)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=str, required=True)
    parser.add_argument("--n-images", type=int, default=5)
    parser.add_argument("--n-reps", type=int, default=2)
    parser.add_argument("--output", type=str,
                        default="scripts/ab_tests/results/ocr_post_change5_regression.json")
    args = parser.parse_args()

    samples = sorted([
        p for p in Path(args.samples).iterdir()
        if p.suffix.lower() in (".jpg", ".jpeg", ".png")
    ])[: args.n_images]

    print(f"Modelo: {ANTHROPIC_CLAUDE_MODEL}")
    print(f"OCR_USE_CLOUD_VISION: {OCR_USE_CLOUD_VISION}")
    print(f"Amostras: {len(samples)} · n_reps: {args.n_reps}\n")

    results = []
    for rep in range(args.n_reps):
        print(f"━━ Repetição {rep+1}/{args.n_reps} ━━")
        for i, p in enumerate(samples, 1):
            r = run_one(p)
            r["rep"] = rep + 1
            results.append(r)
            if r["ok"]:
                print(f"  [{i}/{len(samples)}] {p.name:<26} ✓ "
                      f"{r['uncertain_pct']:>5.1f}% · "
                      f"{r['total_words']:>4} palavras · {r['elapsed_s']:>5.1f}s")
            else:
                print(f"  [{i}/{len(samples)}] {p.name:<26} ✗ {r.get('error','?')[:80]}")

    print("\n" + "=" * 80)
    print("  REGRESSION RESULTS — Pipeline AnthropicVisionAgent (CV OFF)")
    print("=" * 80)
    by_img: Dict[str, List[float]] = {}
    for r in results:
        if r["ok"]:
            by_img.setdefault(r["image"], []).append(r["uncertain_pct"])

    print(f"  {'Imagem':<26} | {'mean ± std':>20}")
    print("  " + "─" * 50)
    for p in samples:
        xs = by_img.get(p.name, [])
        if len(xs) >= 2:
            print(f"  {p.name:<26} | {mean(xs):>6.1f}% ± {stdev(xs):>4.1f} (n={len(xs)})")
        elif xs:
            print(f"  {p.name:<26} | {xs[0]:>6.1f}%        (n=1)")
        else:
            print(f"  {p.name:<26} | (no data)")

    all_pcts = [pct for pcts in by_img.values() for pct in pcts]
    if len(all_pcts) >= 2:
        print("  " + "─" * 50)
        print(f"  {'MÉDIA GLOBAL':<26} | {mean(all_pcts):>6.1f}% ± {stdev(all_pcts):>4.1f} (n={len(all_pcts)})")

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "config": {
            "model": ANTHROPIC_CLAUDE_MODEL,
            "OCR_USE_CLOUD_VISION": OCR_USE_CLOUD_VISION,
            "n_images": len(samples),
            "n_reps": args.n_reps,
        },
        "results": results,
    }, indent=2, ensure_ascii=False))
    print(f"\n  Salvo em {out}")


if __name__ == "__main__":
    main()
