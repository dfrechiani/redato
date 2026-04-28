#!/usr/bin/env python3
"""
A/B Mudança 5 — Cloud Vision SIM vs Cloud Vision NÃO + variantes de prompt.

3 configs × n=2 reps × 5 redações = 30 chamadas Claude + 5 Cloud Vision (cached).

Configs:
  1. pipeline      — Cloud Vision (3 enhanced) + Claude com VISION_USER_PROMPT (orig)
  2. solo-orig     — Sem Cloud Vision, Claude com VISION_USER_PROMPT (transcript=[])
  3. solo-clean    — Sem Cloud Vision, Claude com VISION_USER_PROMPT_SOLO (sem ref a OCR)

Uso (de backend/notamil-backend):
    python scripts/ab_tests/ocr_change5_ab.py \\
        --samples scripts/ab_tests/ocr_samples/ \\
        --n-images 5 --n-reps 2
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
from typing import Any, Dict, List, Optional

try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except ImportError:
    pass

from PIL import Image
import anthropic

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from redato_backend.functions.essay_ocr.vision.prompts import (
    VISION_SYSTEM_PROMPT,
    VISION_USER_PROMPT,
    VISION_USER_PROMPT_SOLO,
)
from redato_backend.shared.constants import ANTHROPIC_CLAUDE_MODEL


def resize_for_frontend(image_path: Path, max_width: int = 1800,
                        jpeg_quality: int = 92) -> bytes:
    img = Image.open(image_path)
    if img.mode != "RGB":
        img = img.convert("RGB")
    if img.width > max_width:
        new_height = int(img.height * (max_width / img.width))
        img = img.resize((max_width, new_height), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=jpeg_quality)
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


def parse_json_response(text: str) -> dict:
    """Tenta json.loads(strict=False) com fallbacks (igual JSONProcessor)."""
    try:
        return json.loads(text, strict=False)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0), strict=False)
            except json.JSONDecodeError:
                theme_m = re.search(r'"theme"\s*:\s*"([^"]*)"', m.group(0))
                trans_m = re.search(r'"transcription"\s*:\s*"(.*)"\s*\}',
                                    m.group(0), re.DOTALL)
                return {
                    "theme": theme_m.group(1) if theme_m else "",
                    "transcription": trans_m.group(1) if trans_m else m.group(0),
                }
        return {"theme": "", "transcription": text}


# ──────────────────────────────────────────────────────────────────
# Config 1: Pipeline atual via AnthropicVisionAgent.deploy()
# ──────────────────────────────────────────────────────────────────

def run_pipeline(image_path: Path) -> dict:
    """Roda pipeline completo: Cloud Vision (3 enhanced versions) + Claude."""
    from redato_backend.functions.essay_ocr.vision.anthropic_vision import (
        AnthropicVisionAgent,
    )

    image_bytes = resize_for_frontend(image_path)
    image_b64 = base64.b64encode(image_bytes).decode("ascii")

    start = time.time()
    try:
        agent = AnthropicVisionAgent(image_b64)
        result, accuracy = agent.deploy()
        elapsed = time.time() - start
        transcription = result.transcription
        metrics = count_metrics(transcription)
        return {
            "image": image_path.name,
            "config": "pipeline",
            "ok": True,
            "elapsed_s": round(elapsed, 1),
            **metrics,
            "theme": result.theme,
            "transcription": transcription,
        }
    except Exception as exc:
        return {
            "image": image_path.name,
            "config": "pipeline",
            "ok": False,
            "error": repr(exc)[:300],
            "elapsed_s": round(time.time() - start, 1),
        }


# ──────────────────────────────────────────────────────────────────
# Configs 2 e 3: Solo (sem Cloud Vision), prompts diferentes
# ──────────────────────────────────────────────────────────────────

def run_solo(image_path: Path, client: anthropic.Anthropic, prompt_variant: str) -> dict:
    """
    prompt_variant:
      - 'orig'  → VISION_USER_PROMPT com transcript vazio (replica baseline)
      - 'clean' → VISION_USER_PROMPT_SOLO (sem referência a OCR)
    """
    image_bytes = resize_for_frontend(image_path)
    image_b64 = base64.b64encode(image_bytes).decode("ascii")

    if prompt_variant == "orig":
        user_text = VISION_USER_PROMPT.format(transcript=json.dumps([], indent=2))
        config = "solo-orig"
    elif prompt_variant == "clean":
        user_text = VISION_USER_PROMPT_SOLO
        config = "solo-clean"
    else:
        raise ValueError(prompt_variant)

    user_content = [
        {"type": "text", "text": user_text},
        {
            "type": "image",
            "source": {"type": "base64", "media_type": "image/jpeg", "data": image_b64},
        },
    ]

    start = time.time()
    try:
        kwargs = dict(
            model=ANTHROPIC_CLAUDE_MODEL,
            max_tokens=4096,
            system=VISION_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}],
        )
        if not ANTHROPIC_CLAUDE_MODEL.startswith("claude-opus-4"):
            kwargs["temperature"] = 0
        response = client.messages.create(**kwargs)
        elapsed = time.time() - start
        text = "".join(b.text for b in response.content if b.type == "text")
        payload = parse_json_response(text)
        transcription = payload.get("transcription", "")
        metrics = count_metrics(transcription)
        return {
            "image": image_path.name,
            "config": config,
            "ok": True,
            "elapsed_s": round(elapsed, 1),
            "stop_reason": getattr(response, "stop_reason", None),
            **metrics,
            "theme": payload.get("theme", ""),
            "transcription": transcription,
        }
    except Exception as exc:
        return {
            "image": image_path.name,
            "config": config,
            "ok": False,
            "error": repr(exc)[:300],
            "elapsed_s": round(time.time() - start, 1),
        }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=str, required=True)
    parser.add_argument("--n-images", type=int, default=5)
    parser.add_argument("--n-reps", type=int, default=2)
    parser.add_argument("--output", type=str,
                        default="scripts/ab_tests/results/ocr_change5_ab.json")
    args = parser.parse_args()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERRO: ANTHROPIC_API_KEY não setada.", file=sys.stderr)
        sys.exit(2)
    if not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        print("ERRO: GOOGLE_APPLICATION_CREDENTIALS não setada.", file=sys.stderr)
        sys.exit(2)

    samples_dir = Path(args.samples)
    images = sorted(
        [p for p in samples_dir.iterdir()
         if p.suffix.lower() in (".jpg", ".jpeg", ".png")]
    )[: args.n_images]

    client = anthropic.Anthropic()
    print(f"Modelo: {ANTHROPIC_CLAUDE_MODEL}")
    print(f"Amostras: {len(images)} · n_reps: {args.n_reps}")
    print(f"Total chamadas Claude: {len(images) * 3 * args.n_reps}")
    print(f"Total chamadas Cloud Vision: {len(images) * 3 * args.n_reps} (3 versões × pipeline reps)\n")

    results: List[Dict[str, Any]] = []
    for rep in range(args.n_reps):
        print(f"━━━ Repetição {rep+1}/{args.n_reps} ━━━")
        for i, img in enumerate(images, 1):
            for config in ("pipeline", "solo-orig", "solo-clean"):
                tag = f"[r{rep+1} {i}/{len(images)}] {img.name:<26} {config:<11}"
                if config == "pipeline":
                    r = run_pipeline(img)
                else:
                    r = run_solo(img, client, "orig" if config == "solo-orig" else "clean")
                r["rep"] = rep + 1
                results.append(r)
                if r["ok"]:
                    print(f"  {tag} ✓ {r['uncertain_pct']:>5.1f}%  {r['total_words']:>4} palavras  {r['elapsed_s']:>5.1f}s")
                else:
                    print(f"  {tag} ✗ {r.get('error', '?')[:100]}")

    # Agregação
    print("\n" + "=" * 100)
    print("  AGREGADO (n=2 por imagem×config)")
    print("=" * 100)
    print(f"  {'Imagem':<26} | {'Pipeline (CV+CL)':>18} | {'Solo orig':>14} | {'Solo clean':>14}")
    print("  " + "─" * 95)

    per_img: Dict[str, Dict[str, List[float]]] = {}
    for r in results:
        if not r["ok"]:
            continue
        per_img.setdefault(r["image"], {}).setdefault(r["config"], []).append(r["uncertain_pct"])

    cfgs = ["pipeline", "solo-orig", "solo-clean"]
    for img in [i.name for i in images]:
        row = [f"{img:<26}"]
        for cfg in cfgs:
            xs = per_img.get(img, {}).get(cfg, [])
            if len(xs) >= 2:
                m, s = mean(xs), stdev(xs)
                row.append(f"{m:>6.1f}% ± {s:>4.1f} (n={len(xs)})")
            elif xs:
                row.append(f"{xs[0]:>6.1f}%        (n=1)")
            else:
                row.append(f"{'(no data)':>18}")
        print("  " + " | ".join(row))

    print("  " + "─" * 95)
    row = [f"{'MÉDIA GLOBAL':<26}"]
    for cfg in cfgs:
        all_pcts = [pct for img in per_img.values() for pct in img.get(cfg, [])]
        if len(all_pcts) >= 2:
            m, s = mean(all_pcts), stdev(all_pcts)
            row.append(f"{m:>6.1f}% ± {s:>4.1f} (n={len(all_pcts)})")
        else:
            row.append(f"{'(insuf)':>18}")
    print("  " + " | ".join(row))

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({
        "config": {
            "model": ANTHROPIC_CLAUDE_MODEL,
            "n_images": len(images),
            "n_reps": args.n_reps,
        },
        "results": results,
    }, indent=2, ensure_ascii=False))
    print(f"\n  Salvo em {out_path}")


if __name__ == "__main__":
    main()
