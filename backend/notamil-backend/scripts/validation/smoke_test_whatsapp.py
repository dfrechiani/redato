#!/usr/bin/env python3
"""Smoke test end-to-end do bot WhatsApp.

Pipeline simulado: aluno se cadastra → manda foto + missão → bot OCR →
grade_mission → render → resposta WhatsApp.

5 fluxos (1 por modo). Foto sintética: PIL → PNG com texto digitado
(brilho alto, sem blur), garante quality_check pass.

Uso:
    python scripts/validation/smoke_test_whatsapp.py
    python scripts/validation/smoke_test_whatsapp.py --only foco_c3,foco_c4

Custo: ~$1.00 (5 OCRs Sonnet + 4 grade Sonnet + 1 grade Opus com cache).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import textwrap
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

BACKEND = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND))

# Carrega .env
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

# DB de teste isolado
test_db = BACKEND / "data" / "whatsapp" / "redato_smoke.db"
if test_db.exists():
    test_db.unlink()
os.environ["REDATO_WHATSAPP_DB"] = str(test_db)

from redato_backend.dev_offline import apply_patches  # noqa: E402
apply_patches()

from PIL import Image, ImageDraw, ImageFont  # noqa: E402
from redato_backend.whatsapp.api_simulator import WhatsAppSimulator  # noqa: E402
from redato_backend.whatsapp import persistence as P  # noqa: E402


# ──────────────────────────────────────────────────────────────────────
# Helpers — fotos sintéticas
# ──────────────────────────────────────────────────────────────────────

def _load_font(size: int = 22) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def make_synthetic_photo(text: str, out_path: Path,
                         width: int = 900) -> Path:
    """Cria PNG branco com texto wrappado preto. Brilho ~245, alta var."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    font = _load_font(20)
    wrapper = textwrap.TextWrapper(width=int(width / 11))
    lines: List[str] = []
    for paragraph in text.split("\n"):
        if not paragraph.strip():
            lines.append("")
            continue
        lines.extend(wrapper.wrap(paragraph))
    line_h = 28
    height = max(400, 80 + line_h * len(lines))
    img = Image.new("RGB", (width, height), (250, 250, 248))
    draw = ImageDraw.Draw(img)
    y = 40
    for line in lines:
        draw.text((50, y), line, fill=(15, 15, 20), font=font)
        y += line_h
    img.save(out_path, "PNG")
    return out_path


# ──────────────────────────────────────────────────────────────────────
# Texto-amostra por modo (mesmos do smoke_test_missions.py)
# ──────────────────────────────────────────────────────────────────────

SAMPLES: Dict[str, Dict[str, str]] = {
    "foco_c3": {
        "missao_code": "RJ1OF10MF",
        "content": (
            "O trabalho em equipe é fundamental para qualquer projeto "
            "complexo, porque a diversidade de perspectivas reduz pontos "
            "cegos individuais e produz decisões mais robustas. Em uma "
            "pesquisa da Harvard Business Review, equipes com composição "
            "diversa tomaram melhores decisões em 87% dos casos analisados."
        ),
    },
    "foco_c4": {
        "missao_code": "RJ1OF11MF",
        "content": (
            "Na entrevista, eu seria um candidato adequado para a vaga "
            "porque sou organizado, e essa qualidade gera valor mensurável "
            "para a empresa. Pragmaticamente, organização permite cumprir "
            "prazos sem retrabalho. No plano principiológico, organização "
            "demonstra respeito pelo tempo dos colegas. Por exemplo, no "
            "estágio anterior, ao implementar um checklist semanal, "
            "mitiguei o atraso em 30%."
        ),
    },
    "foco_c5": {
        "missao_code": "RJ1OF12MF",
        "content": (
            "Diante do quadro de abandono escolar discutido, é necessário "
            "que o Ministério da Educação, em parceria com as Secretarias "
            "Estaduais de Educação, implemente um programa de Bolsa de "
            "Permanência para estudantes do ensino médio em risco de "
            "evasão. O programa deve atender alunos de 14 a 17 anos em "
            "escolas com taxa de evasão acima de 15%, com transferência "
            "mensal condicionada à frequência mínima de 75%. A finalidade "
            "é reduzir o abandono em 30% até 2028."
        ),
    },
    "completo_parcial": {
        "missao_code": "RJ1OF13MF",
        "content": (
            "A educação pública brasileira sofre com desigualdade "
            "estrutural que limita seu papel transformador. O "
            "analfabetismo funcional, que atinge 29% dos brasileiros "
            "segundo o Inaf 2024, demonstra que mesmo a presença na "
            "escola não garante apropriação efetiva do conhecimento. "
            "Como aponta Paulo Freire em Pedagogia do Oprimido, a "
            "educação bancária reproduz desigualdade em vez de combatê-la. "
            "Por consequência, transformar o sistema exige investimento "
            "estrutural articulado a metodologias ativas."
        ),
    },
    "completo_integral": {
        "missao_code": "RJ1OF14MF",
        "content": (
            "A educação pública brasileira enfrenta uma crise estrutural "
            "que limita seu potencial transformador na sociedade. Esse "
            "cenário precisa ser revertido para que o país avance em "
            "termos de mobilidade social.\n\n"
            "Em primeiro lugar, o analfabetismo funcional atinge 29% "
            "dos brasileiros segundo o Inaf 2024, o que demonstra que "
            "a presença na escola não garante o domínio efetivo dos "
            "saberes essenciais. Paulo Freire, em Pedagogia do Oprimido, "
            "alertou que a educação bancária reproduz desigualdades em "
            "vez de combatê-las.\n\n"
            "Portanto, é necessário que o Ministério da Educação, em "
            "parceria com as Secretarias Estaduais, implemente programas "
            "de formação continuada de professores e reforma da "
            "infraestrutura escolar, priorizando municípios com IDEB "
            "inferior a 4,0, a fim de reduzir o analfabetismo funcional "
            "em 30% até 2030."
        ),
    },
}


# ──────────────────────────────────────────────────────────────────────
# Smoke runner
# ──────────────────────────────────────────────────────────────────────

def _phone_for(mode: str) -> str:
    return f"+5511555{mode[-3:].rjust(3, '0')[-3:]}001"


def run_one(sim: WhatsAppSimulator, mode: str, sample: Dict[str, str]) -> Dict[str, Any]:
    """Roda 1 fluxo completo: cadastro + missão + foto."""
    phone = _phone_for(mode)
    photos_dir = BACKEND / "data" / "whatsapp" / "smoke_photos"
    foto_path = make_synthetic_photo(
        sample["content"],
        photos_dir / f"{mode}.png",
    )

    print(f"\n{'='*70}")
    print(f"[{mode}] phone={phone}")

    # Step 1 — cadastro
    sim.send_from_aluno(phone, text="oi")
    sim.send_from_aluno(phone, text="João da Silva (smoke_test)")
    sim.send_from_aluno(
        phone,
        text=f"1A — Colégio Smoke Test {mode}",
    )

    # Step 2 — manda código + foto na mesma msg
    t0 = time.time()
    responses = sim.send_from_aluno(
        phone,
        text=sample["missao_code"],
        image_path=foto_path,
    )
    elapsed = time.time() - t0

    final_reply = responses[-1].text if responses else ""
    print(f"  ⏱  pipeline {elapsed:.1f}s")
    print(f"  📝 reply ({len(final_reply)} chars):")
    for line in final_reply.splitlines():
        print(f"    │ {line}")

    # Validações
    issues: List[str] = []
    if len(final_reply) > 800:
        issues.append(f"reply > 800 chars ({len(final_reply)})")
    if elapsed > 90:
        issues.append(f"latency > 90s ({elapsed:.1f}s)")
    if "Algo deu errado" in final_reply:
        issues.append("erro genérico retornado")
    if "deu errado" in final_reply.lower() and "tira outra" not in final_reply.lower():
        # quality issue retornado?
        pass

    # Verificar persistence
    aluno = P.get_aluno(phone)
    interactions = P.list_interactions_by_aluno(phone)
    has_interaction = bool(interactions)
    if not has_interaction:
        issues.append("sem interação persistida")

    # Última interação tem texto transcrito?
    last = interactions[0] if interactions else {}
    has_text = bool(last.get("texto_transcrito"))
    if not has_text:
        issues.append("OCR não persistiu texto")

    if issues:
        print(f"  ✗ issues: {issues}")
    else:
        print(f"  ✓ smoke OK")

    return {
        "mode": mode,
        "phone": phone,
        "elapsed_s": round(elapsed, 2),
        "reply_chars": len(final_reply),
        "reply": final_reply,
        "issues": issues,
        "ok": not issues,
        "ocr_metrics": json.loads(last.get("ocr_metrics") or "{}"),
        "ocr_issues": json.loads(last.get("ocr_quality_issues") or "[]"),
        "transcript_chars": len(last.get("texto_transcrito") or ""),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", type=str, default=None)
    parser.add_argument("--skip-of14", action="store_true")
    args = parser.parse_args()

    if not os.getenv("ANTHROPIC_API_KEY"):
        print("ERRO: ANTHROPIC_API_KEY não configurada")
        sys.exit(1)

    sim = WhatsAppSimulator()
    P.init_db()

    modes = ["foco_c3", "foco_c4", "foco_c5", "completo_parcial",
             "completo_integral"]
    if args.skip_of14:
        modes = [m for m in modes if m != "completo_integral"]
    if args.only:
        only = {m.strip() for m in args.only.split(",")}
        modes = [m for m in modes if m in only]

    print(f"Smoke WhatsApp — modos: {modes}")
    print(f"DB: {os.environ['REDATO_WHATSAPP_DB']}")

    results: List[Dict[str, Any]] = []
    for mode in modes:
        results.append(run_one(sim, mode, SAMPLES[mode]))

    # Persiste JSONL
    out_dir = BACKEND / "scripts" / "validation" / "results" / "whatsapp"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = out_dir / f"smoke_test_{ts}.jsonl"
    with out_path.open("w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")

    # Verificar agregação por turma (Fase B prep)
    print(f"\n{'='*70}")
    print(f"Agregação por turma (smoke):")
    seen_turmas = set()
    for r in results:
        a = P.get_aluno(r["phone"]) or {}
        t = a.get("turma_id")
        if t and t not in seen_turmas:
            seen_turmas.add(t)
            ts_ints = P.list_interactions_by_turma(t)
            print(f"  turma={t} interações={len(ts_ints)}")

    print(f"\n{'='*70}")
    print(f"Resultados em: {out_path}")
    print(f"\nResumo:")
    for r in results:
        st = "✓" if r["ok"] else "✗"
        msg = "OK" if r["ok"] else "; ".join(r["issues"])
        print(f"  {st} {r['mode']:20} {r['elapsed_s']}s "
              f"reply={r['reply_chars']}ch transcript={r['transcript_chars']}ch — {msg}")

    fail = sum(1 for r in results if not r["ok"])
    sys.exit(0 if fail == 0 else 1)


if __name__ == "__main__":
    main()
