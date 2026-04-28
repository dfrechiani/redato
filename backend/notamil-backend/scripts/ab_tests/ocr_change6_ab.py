#!/usr/bin/env python3
"""
A/B Mudança 6 — 3 imagens enhanced vs 1 imagem original.

Para cada redação, roda AnthropicVisionAgent.deploy() em duas configs
controlando OCR_USE_ENHANCED_IMAGES via env var dentro do mesmo processo
(usa importlib.reload pra reaplicar o flag em cada chamada).

5 redações × 2 configs × n=3 = 30 chamadas.
Mantém OCR_USE_CLOUD_VISION=0 fixo (Mudança 5 já fechada).

Uso (de backend/notamil-backend):
    python scripts/ab_tests/ocr_change6_ab.py \\
        --samples scripts/ab_tests/ocr_samples/ \\
        --n-images 5 --n-reps 3
"""
from __future__ import annotations

import argparse
import base64
import importlib
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


def run_one(image_path: Path, use_enhanced: bool) -> dict:
    """Roda AnthropicVisionAgent.deploy() com flag específica.

    Reimporta os módulos pra que constants.OCR_USE_ENHANCED_IMAGES seja
    re-lida do env. Necessário porque imports cacheiam valores.
    """
    os.environ["OCR_USE_ENHANCED_IMAGES"] = "1" if use_enhanced else "0"
    os.environ["OCR_USE_CLOUD_VISION"] = "0"

    import redato_backend.shared.constants as constants
    importlib.reload(constants)
    import redato_backend.functions.essay_ocr.vision.anthropic_vision as av
    importlib.reload(av)

    image_bytes = resize_for_frontend(image_path)
    image_b64 = base64.b64encode(image_bytes).decode("ascii")

    config = "3enh" if use_enhanced else "1orig"
    start = time.time()
    try:
        agent = av.AnthropicVisionAgent(image_b64)
        result, _ = agent.deploy()
        elapsed = time.time() - start
        m = count_metrics(result.transcription)
        return {
            "image": image_path.name,
            "config": config,
            "ok": True,
            "elapsed_s": round(elapsed, 1),
            **m,
            "theme": result.theme,
            "transcription": result.transcription,
        }
    except Exception as e:
        return {
            "image": image_path.name,
            "config": config,
            "ok": False,
            "error": repr(e)[:300],
            "elapsed_s": round(time.time() - start, 1),
        }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=str, required=True)
    parser.add_argument("--n-images", type=int, default=5)
    parser.add_argument("--n-reps", type=int, default=3)
    parser.add_argument("--output", type=str,
                        default="scripts/ab_tests/results/ocr_change6_ab.json")
    args = parser.parse_args()

    samples = sorted([
        p for p in Path(args.samples).iterdir()
        if p.suffix.lower() in (".jpg", ".jpeg", ".png")
    ])[: args.n_images]

    print(f"Amostras: {len(samples)} · n_reps: {args.n_reps}")
    print(f"Total chamadas: {len(samples) * 2 * args.n_reps}\n")

    results: List[Dict[str, Any]] = []
    for rep in range(args.n_reps):
        print(f"━━━ Repetição {rep+1}/{args.n_reps} ━━━")
        for i, p in enumerate(samples, 1):
            for use_enh in (True, False):
                cfg = "3enh" if use_enh else "1orig"
                tag = f"[r{rep+1} {i}/{len(samples)}] {p.name:<26} {cfg:<5}"
                r = run_one(p, use_enh)
                r["rep"] = rep + 1
                results.append(r)
                if r["ok"]:
                    print(f"  {tag} ✓ {r['uncertain_pct']:>5.1f}%  {r['total_words']:>4} palavras  {r['elapsed_s']:>5.1f}s")
                else:
                    print(f"  {tag} ✗ {r.get('error', '?')[:80]}")

    # Aggregate
    print("\n" + "=" * 95)
    print(f"  AGREGADO Mudança 6 (n={args.n_reps} por imagem×config)")
    print("=" * 95)
    print(f"  {'Imagem':<26} | {'3 enhanced (mean ± σ)':>22} | {'1 original (mean ± σ)':>22} | {'Δ':>6} | {'t3':>5} {'t1':>5}")
    print("  " + "─" * 95)

    by: Dict[str, Dict[str, List[float]]] = {}
    times: Dict[str, Dict[str, List[float]]] = {}
    for r in results:
        if not r["ok"]:
            continue
        by.setdefault(r["image"], {}).setdefault(r["config"], []).append(r["uncertain_pct"])
        times.setdefault(r["image"], {}).setdefault(r["config"], []).append(r["elapsed_s"])

    enh_all, orig_all = [], []
    enh_t, orig_t = [], []
    for p in samples:
        n = p.name
        e = by.get(n, {}).get("3enh", [])
        o = by.get(n, {}).get("1orig", [])
        et = times.get(n, {}).get("3enh", [])
        ot = times.get(n, {}).get("1orig", [])
        enh_all += e; orig_all += o
        enh_t += et; orig_t += ot

        def fmt(xs):
            if len(xs) >= 2:
                return f"{mean(xs):>5.1f}% ± {stdev(xs):>4.1f} (n={len(xs)})"
            elif xs:
                return f"{xs[0]:>5.1f}%        (n=1)"
            return f"{'(no data)':>22}"

        delta = mean(o) - mean(e) if (e and o) else 0.0
        t_e = f"{mean(et):>5.1f}" if et else "-"
        t_o = f"{mean(ot):>5.1f}" if ot else "-"
        print(f"  {n:<26} | {fmt(e):>22} | {fmt(o):>22} | {delta:>+6.2f} | {t_e:>5} {t_o:>5}")

    print("  " + "─" * 95)
    if enh_all and orig_all:
        delta = mean(orig_all) - mean(enh_all)
        s_e = stdev(enh_all) if len(enh_all) >= 2 else 0.0
        s_o = stdev(orig_all) if len(orig_all) >= 2 else 0.0
        print(f"  {'MÉDIA GLOBAL':<26} | "
              f"{mean(enh_all):>5.1f}% ± {s_e:>4.1f} (n={len(enh_all)}) | "
              f"{mean(orig_all):>5.1f}% ± {s_o:>4.1f} (n={len(orig_all)}) | "
              f"{delta:>+6.2f} | "
              f"{mean(enh_t):>5.1f} {mean(orig_t):>5.1f}")

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "config": {"n_images": len(samples), "n_reps": args.n_reps},
        "results": results,
    }, indent=2, ensure_ascii=False))
    print(f"\n  Salvo em {out}")


if __name__ == "__main__":
    main()
