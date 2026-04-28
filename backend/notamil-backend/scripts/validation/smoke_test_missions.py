#!/usr/bin/env python3
"""Smoke test dos 5 modos REJ 1S.

Roda 1 chamada por modo (foco_c3, foco_c4, foco_c5, completo_parcial,
completo_integral) com texto-amostra curto. Persiste output em JSONL pra
auditoria. Valida que cada schema retorna estrutura esperada.

Uso:
    python scripts/validation/smoke_test_missions.py [--skip-of14]

Custo estimado: ~$1.80 (4 modos foco/parcial em Opus + 1 OF14 completo
em Opus). --skip-of14 reduz pra ~$0.80.

Pré-requisito: ANTHROPIC_API_KEY no ambiente ou .env.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

BACKEND = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND))

# Carrega .env (forma simples — sem dependência externa). setdefault() não
# funciona quando a env existe mas está vazia; usamos check explícito.
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
# Modos foco/parcial: default por modo (Sonnet pra foco, Opus pra parcial).
# OF14: pipeline v2 — REDATO_CLAUDE_MODEL=opus reflete produção.
os.environ.setdefault("REDATO_CLAUDE_MODEL", "claude-opus-4-7")
os.environ.setdefault("REDATO_SCHEMA_FLAT", "1")  # OF14 usa flat schema
os.environ.setdefault("REDATO_ENSEMBLE", "1")  # smoke = single call

from redato_backend.dev_offline import apply_patches  # noqa: E402
apply_patches()  # patcheia google.cloud, firebase, firestore antes do grade

from redato_backend.dev_offline import _claude_grade_essay  # noqa: E402


# ──────────────────────────────────────────────────────────────────────
# Texto-amostra por modo
# ──────────────────────────────────────────────────────────────────────

SAMPLES: Dict[str, Dict[str, str]] = {
    "foco_c3": {
        "activity_id": "RJ1·OF10·MF·Foco C3",
        "theme": "Trabalho em equipe no ambiente profissional",
        "content": (
            "O trabalho em equipe é fundamental para qualquer projeto "
            "complexo, porque a diversidade de perspectivas reduz pontos "
            "cegos individuais e produz decisões mais robustas. Em uma "
            "pesquisa da Harvard Business Review, equipes com composição "
            "diversa tomaram melhores decisões em 87% dos casos analisados — "
            "evidência concreta de que a colaboração estruturada supera o "
            "esforço individual isolado."
        ),
    },
    "foco_c4": {
        "activity_id": "RJ1·OF11·MF·Foco C4",
        "theme": "Entrevista de emprego — apresentação pessoal",
        "content": (
            "Na entrevista, eu seria um candidato adequado para a vaga "
            "porque sou organizado, e essa qualidade gera valor mensurável "
            "para a empresa. Pragmaticamente, organização permite cumprir "
            "prazos sem retrabalho, o que reduz custos operacionais. "
            "No plano principiológico, organização demonstra respeito pelo "
            "tempo dos colegas, premissa essencial de qualquer time saudável. "
            "Por exemplo, no estágio anterior, ao implementar um checklist "
            "semanal, mitiguei o atraso no fechamento mensal em 30%."
        ),
    },
    "foco_c5": {
        "activity_id": "RJ1·OF12·MF·Foco C5",
        "theme": "Evasão escolar no ensino médio brasileiro",
        "content": (
            "Diante do quadro de abandono escolar discutido, é necessário "
            "que o Ministério da Educação, em parceria com as Secretarias "
            "Estaduais de Educação, implemente um programa de Bolsa de "
            "Permanência para estudantes do ensino médio em risco de "
            "evasão. O programa deve atender alunos de 14 a 17 anos em "
            "escolas com taxa de evasão acima de 15%, por meio de "
            "transferência mensal condicionada à frequência mínima de 75% "
            "e à participação em mentoria pedagógica. A finalidade é "
            "reduzir o abandono em 30% até 2028, garantindo o direito "
            "constitucional à educação previsto no art. 205 da CF."
        ),
    },
    "completo_parcial": {
        "activity_id": "RJ1·OF13·MF·Correção 5 comp.",
        "theme": "Educação pública e desigualdade no Brasil",
        "content": (
            "A educação pública brasileira sofre com desigualdade "
            "estrutural que limita seu papel transformador. O "
            "analfabetismo funcional, que atinge 29% dos brasileiros "
            "segundo o Inaf 2024, demonstra que mesmo a presença na escola "
            "não garante apropriação efetiva do conhecimento. Como aponta "
            "Paulo Freire em Pedagogia do Oprimido, a educação bancária "
            "reproduz desigualdade em vez de combatê-la. Por consequência, "
            "transformar o sistema exige investimento estrutural articulado "
            "a metodologias ativas que tratem o aluno como sujeito do "
            "processo, não como receptor passivo."
        ),
    },
    "completo_integral": {
        "activity_id": "RJ1·OF14·MF·Correção 5 comp.",
        "theme": "Educação pública e desigualdade no Brasil",
        # Redação curta de 3 parágrafos — suficiente pra smoke test do
        # pipeline v2 com preâmbulo REJ. Não é teste de qualidade, só
        # confirmação de schema válido.
        "content": (
            "A educação pública brasileira enfrenta uma crise estrutural "
            "que limita seu potencial transformador na sociedade. Esse "
            "cenário precisa ser revertido para que o país avance em "
            "termos de mobilidade social.\n\n"
            "Em primeiro lugar, o analfabetismo funcional atinge 29% dos "
            "brasileiros segundo o Inaf 2024, o que demonstra que a "
            "presença na escola não garante o domínio efetivo dos "
            "saberes essenciais. Paulo Freire, em Pedagogia do Oprimido, "
            "alertou que a educação bancária reproduz desigualdades em "
            "vez de combatê-las. Além disso, a infraestrutura precária "
            "das escolas em regiões periféricas amplifica a distância "
            "entre os estudantes da rede pública e os da rede privada.\n\n"
            "Portanto, é necessário que o Ministério da Educação, em "
            "parceria com as Secretarias Estaduais, implemente programas "
            "de formação continuada de professores e reforma da "
            "infraestrutura escolar. O programa deve priorizar municípios "
            "com IDEB inferior a 4,0 e contar com avaliação trianual de "
            "impacto, a fim de reduzir o analfabetismo funcional em 30% "
            "até 2030."
        ),
    },
}


# Validação por modo: campos obrigatórios que precisam estar presentes
EXPECTED_FIELDS: Dict[str, List[str]] = {
    "foco_c3": [
        "modo", "missao_id", "rubrica_rej", "nota_rej_total", "nota_c3_enem",
        "flags", "feedback_aluno", "feedback_professor",
    ],
    "foco_c4": [
        "modo", "missao_id", "rubrica_rej", "nota_rej_total", "nota_c4_enem",
        "flags", "feedback_aluno", "feedback_professor",
    ],
    "foco_c5": [
        "modo", "missao_id", "rubrica_rej", "articulacao_a_discussao",
        "nota_rej_total", "nota_c5_enem", "flags", "feedback_aluno",
        "feedback_professor",
    ],
    "completo_parcial": [
        "modo", "missao_id", "rubrica_rej", "nota_rej_total", "notas_enem",
        "nota_total_parcial", "flags", "feedback_aluno", "feedback_professor",
    ],
    "completo_integral": [
        # Schema v2 (após unflatten)
        "essay_analysis", "preanulation_checks", "c1_audit", "c2_audit",
        "c3_audit", "c4_audit", "c5_audit", "priorization", "meta_checks",
        "feedback_text",
    ],
}


def validate_schema(mode: str, args: Dict[str, Any]) -> List[str]:
    """Retorna lista de problemas. Lista vazia = schema OK."""
    issues: List[str] = []
    expected = EXPECTED_FIELDS[mode]
    for field in expected:
        if field not in args:
            issues.append(f"campo obrigatório ausente: {field}")
    # Validações específicas
    if mode == "foco_c3" and isinstance(args.get("nota_c3_enem"), int):
        if args["nota_c3_enem"] not in (0, 40, 80, 120, 160, 200):
            issues.append(f"nota_c3_enem fora do enum INEP: {args['nota_c3_enem']}")
    if mode == "completo_parcial":
        notas = args.get("notas_enem") or {}
        if notas.get("c5") != "não_aplicável":
            issues.append(f"notas_enem.c5 deve ser 'não_aplicável', got {notas.get('c5')!r}")
    return issues


# ──────────────────────────────────────────────────────────────────────
# Validação de vocabulário pedagógico
# ──────────────────────────────────────────────────────────────────────

# Termos proibidos por padrão (regex word-boundary, case-insensitive).
# Cada modo tem whitelist de termos que a oficina ensinou.
import re  # noqa: E402

_FORBIDDEN_TERMS_BASE = [
    r"\btese\b",
    r"\btes(es|al|aico)\b",
    r"\bdado verific[áa]ve(l|is)\b",
    r"\bdados verific[áa]ve(l|is)\b",
    r"\bmecanismo causal\b",
    r"\breformula[çc][ãa]o\b",
    r"\bargumenta[çc][ãa]o por reformula[çc][ãa]o\b",
    r"\bprosa( cont[íi]nua)?\b",
    r"\bterreno previs[íi]vel\b",
    r"\brecorte tem[áa]tico\b",
    r"\bautoria\b",
    r"\bconfigura(ndo|r) autoria\b",
    r"\boperadores argumentativos\b",
    r"\bprojeto de texto\b",
    r"\bproposi[çc][ãa]o\b",
    r"\bdefesa do ponto de vista\b",
    r"\bponto de vista\b",  # PDV — também é jargão
]

_FORBIDDEN_TERMS_FEEDBACK_ALUNO_PER_MODE: Dict[str, List[str]] = {
    "foco_c3": _FORBIDDEN_TERMS_BASE + [
        r"\brepert[óo]rio\b",
    ],
    "foco_c4": _FORBIDDEN_TERMS_BASE + [
        r"\brepert[óo]rio\b",
    ],
    "foco_c5": _FORBIDDEN_TERMS_BASE + [
        r"\bpremissa(s)?\b",  # OF12 não ensinou premissa
        r"\brepert[óo]rio\b",
    ],
    "completo_parcial": [
        # OF13 ensinou repertório, tópico frasal, argumento, coesão →
        # remove esses da lista. Mas mantém "tese", "dado verificável",
        # "mecanismo causal", "autoria" como proibidos.
        r"\btese\b",
        r"\btes(es|al|aico)\b",
        r"\bdado verific[áa]ve(l|is)\b",
        r"\bdados verific[áa]ve(l|is)\b",
        r"\bmecanismo causal\b",
        r"\breformula[çc][ãa]o\b",
        r"\bterreno previs[íi]vel\b",
        r"\brecorte tem[áa]tico\b",
        r"\bautoria\b",
        r"\boperadores argumentativos\b",
        r"\bprojeto de texto\b",
        r"\bproposi[çc][ãa]o\b",
        r"\bdefesa do ponto de vista\b",
    ],
}

# Diminutivos: nunca permitidos (reforçado pelo user — aluno é
# interlocutor adulto). Lista heurística — pega -inho/-inha em palavras
# referentes a texto/aluno/ideia, mas evita pegar nomes próprios e
# palavras comuns ("trabalhinho" sim, "Pedrinho" não).
_DIMINUTIVE_RE = re.compile(
    r"\b(palavr|fras|ajuste|trech|ide|prazo|detalh|argument|"
    r"explica[çc][ãa]o|exempl|conex|toque|coisa|defeito|erro|coes|"
    r"pequen|levezin)\w*(inho|inha|inhos|inhas|zinho|zinha|zinhos|zinhas|"
    r"itos|itas)\b",
    re.IGNORECASE,
)


def _find_terms(text: str, patterns: List[str]) -> List[str]:
    found: List[str] = []
    for pat in patterns:
        m = re.search(pat, text or "", re.IGNORECASE)
        if m:
            found.append(m.group(0).lower())
    return found


def validate_vocabulary(mode: str, args: Dict[str, Any]) -> Dict[str, List[str]]:
    """Retorna {field: [violações]} pra cada campo de feedback.

    Aplica:
    - Lista proibida de termos por modo no `feedback_aluno`.
    - Diminutivos proibidos em todos os campos de feedback (aluno + prof).
    - `feedback_professor.audit_completo` recebe escrutínio mais leve
      (termos técnicos ok com explicação) — checagem só de diminutivos.
    """
    if mode == "completo_integral":
        # OF14 reusa pipeline v2 — feedback_text já tem seu próprio prompt.
        # Validação de vocabulário só pra o resumo final.
        text = args.get("feedback_text", "")
        out: Dict[str, List[str]] = {}
        diminutives = list({m.group(0).lower()
                            for m in _DIMINUTIVE_RE.finditer(text)})
        if diminutives:
            out["feedback_text/diminutivos"] = sorted(set(diminutives))
        return out

    out: Dict[str, List[str]] = {}
    fa = args.get("feedback_aluno") or {}
    fp = args.get("feedback_professor") or {}

    # Concat acertos + ajustes pra checagem do feedback_aluno.
    aluno_text = " ".join(
        list(fa.get("acertos") or []) + list(fa.get("ajustes") or [])
    )
    forbidden = _FORBIDDEN_TERMS_FEEDBACK_ALUNO_PER_MODE.get(
        mode, _FORBIDDEN_TERMS_BASE
    )
    found = _find_terms(aluno_text, forbidden)
    if found:
        out["feedback_aluno/termos_proibidos"] = sorted(set(found))

    # Diminutivos: aluno + audit_completo + padrao_falha + transferencia_c1
    full_aluno = aluno_text
    full_prof = " ".join([
        fp.get("padrao_falha", ""),
        fp.get("transferencia_c1", ""),
        fp.get("audit_completo", ""),
    ])
    aluno_dims = list({m.group(0).lower()
                       for m in _DIMINUTIVE_RE.finditer(full_aluno)})
    if aluno_dims:
        out["feedback_aluno/diminutivos"] = sorted(set(aluno_dims))
    prof_dims = list({m.group(0).lower()
                      for m in _DIMINUTIVE_RE.finditer(full_prof)})
    if prof_dims:
        out["feedback_professor/diminutivos"] = sorted(set(prof_dims))
    return out


def run_one(mode: str, sample: Dict[str, str]) -> Dict[str, Any]:
    """Roda 1 modo e retorna registro para JSONL."""
    print(f"\n{'='*70}")
    print(f"[{mode}] activity_id={sample['activity_id']}")
    print(f"  content: {len(sample['content'])} chars")
    t0 = time.time()
    data = {
        "request_id": f"smoke_{mode}_{int(time.time())}",
        "user_id": "smoke_test",
        "activity_id": sample["activity_id"],
        "theme": sample["theme"],
        "content": sample["content"],
    }
    try:
        tool_args = _claude_grade_essay(data)
        elapsed = time.time() - t0
        issues = validate_schema(mode, tool_args)
        vocab_issues = validate_vocabulary(mode, tool_args)
        print(f"  ✓ tool_args returned in {elapsed:.1f}s")
        if issues:
            print(f"  ✗ schema issues: {issues}")
        else:
            print(f"  ✓ schema valid: {len(EXPECTED_FIELDS[mode])} fields present")
        if vocab_issues:
            print(f"  ✗ vocabulário: {vocab_issues}")
        else:
            print(f"  ✓ vocabulário OK (nenhum termo proibido / diminutivo detectado)")
        # Print mini summary por modo
        if mode == "foco_c3":
            print(f"    nota_c3_enem={tool_args.get('nota_c3_enem')}, "
                  f"flags={tool_args.get('flags')}")
        elif mode == "foco_c4":
            print(f"    nota_c4_enem={tool_args.get('nota_c4_enem')}, "
                  f"flags={tool_args.get('flags')}")
        elif mode == "foco_c5":
            print(f"    nota_c5_enem={tool_args.get('nota_c5_enem')}, "
                  f"articulacao={tool_args.get('articulacao_a_discussao')}, "
                  f"flags={tool_args.get('flags')}")
        elif mode == "completo_parcial":
            print(f"    notas_enem={tool_args.get('notas_enem')}, "
                  f"total_parcial={tool_args.get('nota_total_parcial')}")
        elif mode == "completo_integral":
            ea = tool_args.get("essay_analysis") or {}
            c1 = (tool_args.get("c1_audit") or {}).get("nota")
            c2 = (tool_args.get("c2_audit") or {}).get("nota")
            c3 = (tool_args.get("c3_audit") or {}).get("nota")
            c4 = (tool_args.get("c4_audit") or {}).get("nota")
            c5 = (tool_args.get("c5_audit") or {}).get("nota")
            total = sum(n or 0 for n in (c1, c2, c3, c4, c5))
            print(f"    word_count={ea.get('word_count')}, "
                  f"notas={(c1, c2, c3, c4, c5)}, total={total}")
        return {
            "mode": mode,
            "activity_id": sample["activity_id"],
            "elapsed_s": round(elapsed, 2),
            "schema_valid": len(issues) == 0,
            "schema_issues": issues,
            "vocab_valid": len(vocab_issues) == 0,
            "vocab_issues": vocab_issues,
            "tool_args": tool_args,
        }
    except Exception as exc:
        elapsed = time.time() - t0
        print(f"  ✗ FAILED in {elapsed:.1f}s: {exc!r}")
        return {
            "mode": mode,
            "activity_id": sample["activity_id"],
            "elapsed_s": round(elapsed, 2),
            "schema_valid": False,
            "schema_issues": [f"exception: {exc!r}"],
            "vocab_valid": False,
            "vocab_issues": {"exception": str(exc)},
            "tool_args": None,
        }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-of14", action="store_true",
                        help="Skip Modo Completo Integral (OF14) pra economizar custo.")
    parser.add_argument("--only", type=str, default=None,
                        help="Comma-separated modes to run (default: all)")
    args = parser.parse_args()

    if not os.getenv("ANTHROPIC_API_KEY"):
        print("ERRO: ANTHROPIC_API_KEY não configurada no ambiente nem no .env.")
        sys.exit(1)

    modes_to_run = ["foco_c3", "foco_c4", "foco_c5", "completo_parcial"]
    if not args.skip_of14:
        modes_to_run.append("completo_integral")
    if args.only:
        only = {m.strip() for m in args.only.split(",")}
        modes_to_run = [m for m in modes_to_run if m in only]

    print(f"Smoke test REJ 1S — modos: {modes_to_run}")
    print(f"Modelo: {os.getenv('REDATO_CLAUDE_MODEL')}")

    results: List[Dict[str, Any]] = []
    for mode in modes_to_run:
        results.append(run_one(mode, SAMPLES[mode]))

    # Persist JSONL
    out_dir = BACKEND / "scripts" / "validation" / "results" / "missions"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = out_dir / f"smoke_test_{ts}.jsonl"
    with out_path.open("w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")

    print(f"\n{'='*70}")
    print(f"Resultados em: {out_path}")
    print(f"\nResumo (schema | vocabulário):")
    for r in results:
        s_st = "✓" if r["schema_valid"] else "✗"
        v_st = "✓" if r.get("vocab_valid") else "✗"
        s_msg = "schema OK" if not r["schema_issues"] else "; ".join(r["schema_issues"])
        v_msg = "vocab OK" if not r.get("vocab_issues") else "; ".join(
            f"{k}={v}" for k, v in (r.get("vocab_issues") or {}).items()
        )
        print(f"  {s_st}/{v_st} {r['mode']:20} ({r['elapsed_s']}s) "
              f"[{s_msg}] [{v_msg}]")


if __name__ == "__main__":
    main()
