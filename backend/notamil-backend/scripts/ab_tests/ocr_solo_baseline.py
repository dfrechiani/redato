#!/usr/bin/env python3
"""
Probe Claude vision SOLO em imagens redimensionadas pra 1800px max + JPEG 0.92
(simulando otimização do frontend). Sem Cloud Vision (require GCP creds).

Suporta override de modelo e versão de prompt (en pré-Mudança-2 vs ptbr pós).
Salva transcrição crua pra inspeção manual.

Uso (de backend/notamil-backend):
    python scripts/ab_tests/ocr_solo_baseline.py \\
        --samples scripts/ab_tests/ocr_samples/ \\
        --n 5 \\
        --model claude-sonnet-4-6 \\
        --prompt-version ptbr \\
        --output scripts/ab_tests/results/foo.json
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
from statistics import mean

try:
    from dotenv import load_dotenv
    load_dotenv(override=True)  # shell costuma ter ANTHROPIC_API_KEY='' vazio
except ImportError:
    pass

from PIL import Image
import anthropic

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from redato_backend.functions.essay_ocr.vision.prompts import (
    VISION_SYSTEM_PROMPT as PTBR_SYSTEM_PROMPT,
    VISION_USER_PROMPT as PTBR_USER_PROMPT,
)
from redato_backend.functions.essay_ocr.vision.transcription_blocks import (
    SUBMIT_TRANSCRIPTION_TOOL,
    blocks_to_xml_string,
)
from redato_backend.shared.constants import ANTHROPIC_CLAUDE_MODEL


# Prompt em inglês — versão pré-Mudança 2, embutida pra permitir A/B
# sem reverter prompts.py.
EN_SYSTEM_PROMPT = """
<background>
You are a strict document transcriptionist. Your ONLY task is to transcribe EXACTLY what you see, letter by letter.
</background>

<absolute_rules>
1. NEVER PARAPHRASE OR INTERPRET - only write exactly what you see
2. EVERY SINGLE WORD that isn't 100% clear must have XML tags
3. If you can't read something perfectly, you MUST use XML tags
4. DO NOT try to make sense of unclear text - mark it as uncertain
5. You MUST check your transcription character by character
</absolute_rules>

<required_xml_tags>
REQUIRED XML TAGS (MANDATORY USE):
For every word that isn't perfectly clear, you MUST use one of these:

1. For partially readable words:
   <uncertain confidence='HIGH'>word you think you see</uncertain>
   <uncertain confidence='MEDIUM'>possible word</uncertain>
   <uncertain confidence='LOW'>barely readable guess</uncertain>

2. For completely unreadable parts:
   <illegible/>

3. For words with multiple possible readings:
   <uncertain confidence="MEDIUM">best_guess</uncertain>
</required_xml_tags>

<transcription_method>
TRANSCRIPTION METHOD:
1. Start at the first word
2. For each word:
   - Can you read it perfectly? → Write it exactly
   - Any doubt at all? → Use <uncertain> tags alongside with your best guess
   - Can't read it? → Use <illegible/>
3. Never skip uncertain words
4. Never try to "fix" or "improve" the text
5. When there's a new paragraph just insert "\\n"
6. Types of text you must not include in the transcription:
   - "Aluno: João da Silva"
   - "Professor: José Oliveira"
   - "Data: 10/04/2024"
   - "Nota: 10"
   - "Assinatura: João da Silva"
   - "Outras informações do aluno: Nome: João da Silva"
   - "Outras informações do professor: José Oliveira"

Example of correct transcription:
"O <uncertain confidence='HIGH'>documento</uncertain> está <uncertain confidence='MEDIUM'>claro</uncertain> mas esta <illegible/> não."
</transcription_method>

<response_format>
Response json format:
{
    "theme": "Theme/Title which is commonly the first handwritten phrase",
    "transcription": "Rest of text with MANDATORY XML tags and without the theme",
}
</response_format>

<final_check>
Before submitting, verify:
1. Are there ANY unclear words without XML tags? (NOT ALLOWED)
2. Did you write exactly what you see? (REQUIRED)
3. Did you add or modify any words? (FORBIDDEN)
4. Did you try to make sense of unclear text? (FORBIDDEN)

Remember: It's better to mark something as uncertain than to guess wrong!
</final_check>
"""

EN_USER_PROMPT = """
I'm providing you with:
1. Previous OCR transcriptions from Google Cloud Vision for each version of the image
2. Three versions of the same document:
   - Original image
   - Enhanced for pencil marks
   - Enhanced for pen marks

Your task:
1. COMPARE the OCR results with what you actually see in the images
2. Create a NEW transcription that:
   - Uses the OCR as reference only, NOT as truth
   - Marks EVERY word where you see any discrepancy between OCR and images
   - Marks EVERY word that isn't 100% clear in the images
   - Uses <uncertain> tags for ANY word you're not completely sure about

Previous OCR results for reference:
{transcript}

IMPORTANT:
- Do NOT trust the OCR blindly
- Do NOT guess at unclear words
- Do NOT try to make sense of unclear text
- You MUST use XML tags for ANY uncertainty
- Better to mark as uncertain than to guess wrong
- When there's a paragraph break just insert "\\n\\n"

Example of correct output:
If OCR says "documento claro" but you see "documento escuro":
- Wrong: "documento claro"
- Right: "documento escuro"
- Correct: "<uncertain confidence="HIGH">escuro</uncertain>"
"""


def get_prompts(version: str) -> tuple[str, str]:
    if version == "en":
        return EN_SYSTEM_PROMPT, EN_USER_PROMPT
    if version == "ptbr":
        return PTBR_SYSTEM_PROMPT, PTBR_USER_PROMPT
    raise ValueError(f"--prompt-version inválido: {version}")


def resize_for_frontend_simulation(image_path: Path, max_width: int = 1800,
                                   jpeg_quality: int = 92) -> tuple[bytes, tuple[int, int]]:
    img = Image.open(image_path)
    if img.mode != "RGB":
        img = img.convert("RGB")
    if img.width > max_width:
        new_height = int(img.height * (max_width / img.width))
        img = img.resize((max_width, new_height), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=jpeg_quality)
    return buf.getvalue(), img.size


def count_metrics(transcription: str) -> dict:
    uncertain = len(re.findall(r"<uncertain\b", transcription))
    illegible = len(re.findall(r"<illegible\b", transcription))
    cleaned = re.sub(r"<[^>]+>", " ", transcription)
    words = cleaned.split()
    total_words = len(words)
    return {
        "uncertain_count": uncertain,
        "illegible_count": illegible,
        "total_words": total_words,
        "uncertain_pct": round(uncertain / max(total_words, 1) * 100, 1),
    }


def has_opus_placeholder(text: str) -> bool:
    """Detecta o bug do Opus que retorna $PARAMETER_NAME literal."""
    return "$PARAMETER_NAME" in text or '"$' in (text or "")[:200]


def run_one(client: anthropic.Anthropic, image_path: Path, model: str,
            system_prompt: str, user_prompt_template: str,
            use_tool: bool = False) -> dict:
    image_bytes, dims = resize_for_frontend_simulation(image_path)
    image_b64 = base64.b64encode(image_bytes).decode("ascii")
    size_kb = len(image_bytes) / 1024

    user_prompt_text = user_prompt_template.format(transcript=json.dumps([], indent=2))
    user_content = [
        {"type": "text", "text": user_prompt_text},
        {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/jpeg",
                "data": image_b64,
            },
        },
    ]

    start = time.time()
    try:
        kwargs = dict(
            model=model,
            max_tokens=8000 if use_tool else 4096,
            system=system_prompt,
            messages=[{"role": "user", "content": user_content}],
        )
        if not model.startswith("claude-opus-4"):
            kwargs["temperature"] = 0
        if use_tool:
            kwargs["tools"] = [SUBMIT_TRANSCRIPTION_TOOL]
            kwargs["tool_choice"] = {"type": "tool", "name": "submit_transcription"}
        response = client.messages.create(**kwargs)
        elapsed = time.time() - start
        stop_reason = getattr(response, "stop_reason", None)

        if use_tool:
            tool_use = next(
                (b for b in response.content
                 if getattr(b, "type", None) == "tool_use"
                 and getattr(b, "name", None) == "submit_transcription"),
                None,
            )
            if tool_use is None:
                return {
                    "image": image_path.name,
                    "model": model,
                    "ok": False,
                    "error": "NO_TOOL_USE_BLOCK",
                    "stop_reason": stop_reason,
                    "elapsed_s": round(elapsed, 1),
                }
            tool_input = dict(getattr(tool_use, "input", {}) or {})
            tool_input_json = json.dumps(tool_input, ensure_ascii=False)
            if has_opus_placeholder(tool_input_json):
                return {
                    "image": image_path.name,
                    "model": model,
                    "ok": False,
                    "error": "OPUS_PLACEHOLDER_BUG",
                    "raw_preview": tool_input_json[:300],
                    "stop_reason": stop_reason,
                    "elapsed_s": round(elapsed, 1),
                }
            blocks_list = tool_input.get("blocks") or []
            transcription = blocks_to_xml_string(blocks_list)
            metrics = count_metrics(transcription)
            return {
                "image": image_path.name,
                "model": model,
                "ok": True,
                "dims": dims,
                "size_kb": round(size_kb, 1),
                "elapsed_s": round(elapsed, 1),
                "stop_reason": stop_reason,
                "strict_would_fail": False,  # N/A no modo tool
                "tool_use_valid": True,
                "n_blocks": len(blocks_list),
                "tool_input_preview": tool_input_json[:300],
                "blocks_full": blocks_list,
                **metrics,
                "theme": str(tool_input.get("theme") or ""),
                "transcription": transcription,
            }

        text = "".join(b.text for b in response.content if b.type == "text")

        if has_opus_placeholder(text):
            return {
                "image": image_path.name,
                "model": model,
                "ok": False,
                "error": "OPUS_PLACEHOLDER_BUG",
                "raw_preview": text[:300],
                "elapsed_s": round(elapsed, 1),
            }

        strict_would_fail = False
        try:
            json.loads(text, strict=True)
        except json.JSONDecodeError:
            strict_would_fail = True

        def _try_parse(s: str) -> dict:
            return json.loads(s, strict=False)

        try:
            payload = _try_parse(text)
        except json.JSONDecodeError:
            m = re.search(r"\{.*\}", text, re.DOTALL)
            if m:
                try:
                    payload = _try_parse(m.group(0))
                except json.JSONDecodeError:
                    theme_m = re.search(r'"theme"\s*:\s*"([^"]*)"', m.group(0))
                    trans_m = re.search(r'"transcription"\s*:\s*"(.*)"\s*\}', m.group(0), re.DOTALL)
                    payload = {
                        "theme": theme_m.group(1) if theme_m else "",
                        "transcription": trans_m.group(1) if trans_m else m.group(0),
                    }
            else:
                payload = {"transcription": text, "theme": ""}

        transcription = payload.get("transcription", "")
        metrics = count_metrics(transcription)

        return {
            "image": image_path.name,
            "model": model,
            "ok": True,
            "dims": dims,
            "size_kb": round(size_kb, 1),
            "elapsed_s": round(elapsed, 1),
            "strict_would_fail": strict_would_fail,
            **metrics,
            "theme": payload.get("theme", ""),
            "transcription": transcription,
        }
    except Exception as exc:
        return {
            "image": image_path.name,
            "model": model,
            "ok": False,
            "error": repr(exc)[:300],
            "elapsed_s": round(time.time() - start, 1),
        }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=str, required=True)
    parser.add_argument("--n", type=int, default=5)
    parser.add_argument("--model", type=str, default=ANTHROPIC_CLAUDE_MODEL)
    parser.add_argument("--prompt-version", type=str, default="ptbr",
                        choices=["en", "ptbr"])
    parser.add_argument("--use-tool", action="store_true",
                        help="Usa SUBMIT_TRANSCRIPTION_TOOL (Mudança 4)")
    parser.add_argument("--output", type=str,
                        default="scripts/ab_tests/results/ocr_solo_baseline.json")
    args = parser.parse_args()

    samples_dir = Path(args.samples)
    images = sorted(
        [p for p in samples_dir.iterdir()
         if p.suffix.lower() in (".jpg", ".jpeg", ".png")]
    )[: args.n]

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERRO: ANTHROPIC_API_KEY não setada.", file=sys.stderr)
        sys.exit(2)

    sys_p, usr_p = get_prompts(args.prompt_version)
    client = anthropic.Anthropic()

    print(f"Modelo: {args.model}")
    print(f"Prompt: {args.prompt_version}")
    print(f"Tool mode: {'ON (Mudança 4)' if args.use_tool else 'off (JSON)'}")
    print(f"Amostras: {len(images)} de {samples_dir}\n")

    results = []
    for i, img in enumerate(images, 1):
        print(f"  [{i}/{len(images)}] {img.name}...", end=" ", flush=True)
        r = run_one(client, img, args.model, sys_p, usr_p, use_tool=args.use_tool)
        results.append(r)
        if r["ok"]:
            strict_mark = "  [strict-fail]" if r.get("strict_would_fail") else ""
            stop_mark = f"  stop={r.get('stop_reason')}" if r.get("stop_reason") else ""
            blocks_mark = f"  blocks={r.get('n_blocks')}" if r.get("n_blocks") is not None else ""
            print(f"✓ {r['uncertain_pct']}% incerto · {r['total_words']} palavras · "
                  f"{r['elapsed_s']}s{stop_mark}{blocks_mark}{strict_mark}")
        else:
            print(f"✗ {r.get('error', '?')[:80]}")

    print("\n" + "=" * 78)
    print(f"  RESULTADOS — {args.model} + prompt {args.prompt_version}")
    print("=" * 78)
    print(f"  {'Imagem':<36} {'%incerto':>8} {'palavras':>9} {'tempo':>7}")
    print("  " + "─" * 70)
    ok = [r for r in results if r["ok"]]
    for r in ok:
        print(f"  {r['image']:<36} {r['uncertain_pct']:>7.1f}% "
              f"{r['total_words']:>9} {r['elapsed_s']:>6.1f}s")
    if ok:
        print("  " + "─" * 70)
        avg_unc = mean(r["uncertain_pct"] for r in ok)
        avg_time = mean(r["elapsed_s"] for r in ok)
        print(f"  {'MÉDIA':<36} {avg_unc:>7.1f}%           {avg_time:>6.1f}s")
    failed = [r for r in results if not r["ok"]]
    if failed:
        print(f"\n  {len(failed)} falha(s):")
        for r in failed:
            print(f"    - {r['image']}: {r.get('error', '?')[:100]}")

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({
        "config": {
            "model": args.model,
            "prompt_version": args.prompt_version,
            "use_tool": args.use_tool,
            "max_width": 1800,
            "jpeg_quality": 92,
            "mode": "claude_solo_no_cloud_vision",
        },
        "results": results,
    }, indent=2, ensure_ascii=False))
    print(f"\n  Salvo em {out_path}")


if __name__ == "__main__":
    main()
