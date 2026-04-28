#!/usr/bin/env python3
"""Análise do Opus + schema flat em subset estratificado de 80 redações.

Verdict explícito contra 2 critérios:
- OPERACIONAL: ≥45% ±40 global, |ME| < 60 fora de 1000, ≥80% audits.
- CIRÚRGICO 401-799: ±40 ≥ 30% E |ME| < 80 → magnitude controlada.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean
from typing import Dict, Any, List, Tuple


COMPS = ("c1", "c2", "c3", "c4", "c5")
BANDS = [
    ("≤400", 0, 400),
    ("401-799", 401, 799),
    ("800-940", 800, 940),
    ("1000", 1000, 1000),
]


def load(p: Path) -> List[Dict[str, Any]]:
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]


def get_red_total(rec: Dict[str, Any]) -> int:
    n = rec.get("redato_final") or rec.get("redato") or {}
    return int(n.get("total", 0))


def is_audit_complete(rec: Dict[str, Any]) -> bool:
    """≥1 cN_audit com nota não-None confirma que o audit foi preenchido."""
    audit = rec.get("redato_audit")
    if not isinstance(audit, dict) or len(audit) == 0:
        return False
    filled = sum(
        1 for k in ("c1_audit", "c2_audit", "c3_audit", "c4_audit", "c5_audit")
        if isinstance(audit.get(k), dict)
        and audit.get(k).get("nota") is not None
    )
    return filled >= 5


def metrics_per_band(opus: Dict[str, Dict], baseline: Dict[str, Dict],
                     ids: List[str]) -> Dict[str, Any]:
    """Computa métricas por faixa: n, ±40 count, MAE, ME, audits completos."""
    out = {}
    for label, lo, hi in BANDS:
        in_band = [
            rid for rid in ids
            if rid in baseline and lo <= baseline[rid]["gabarito"]["total"] <= hi
        ]
        if not in_band:
            out[label] = {"n": 0}
            continue
        diffs = []
        audit_count = 0
        for rid in in_band:
            gab = baseline[rid]["gabarito"]["total"]
            opus_total = get_red_total(opus.get(rid) or {})
            err = opus_total - gab
            diffs.append(err)
            if is_audit_complete(opus.get(rid) or {}):
                audit_count += 1
        within_40 = sum(1 for d in diffs if abs(d) <= 40)
        within_60 = sum(1 for d in diffs if abs(d) <= 60)
        within_80 = sum(1 for d in diffs if abs(d) <= 80)
        out[label] = {
            "n": len(in_band),
            "within_40": within_40,
            "within_60": within_60,
            "within_80": within_80,
            "mae": mean(abs(d) for d in diffs),
            "me": mean(diffs),
            "audits_complete": audit_count,
            "audits_pct": audit_count / len(in_band),
        }
    return out


def evaluate_criteria(per_band: Dict[str, Dict], global_w40: float,
                      global_audits_pct: float) -> Dict[str, Any]:
    """Avalia critérios OPERACIONAL e CIRÚRGICO com explicação."""
    op_checks = []
    op_pass = True
    if global_w40 >= 0.45:
        op_checks.append(("±40 global ≥ 45%", True, f"{global_w40*100:.1f}%"))
    else:
        op_checks.append(("±40 global ≥ 45%", False, f"{global_w40*100:.1f}%"))
        op_pass = False

    for label in ("≤400", "401-799", "800-940"):
        b = per_band[label]
        if b["n"] == 0:
            continue
        if abs(b["me"]) < 60:
            op_checks.append((f"|ME {label}| < 60", True, f"{b['me']:+.0f}"))
        else:
            op_checks.append((f"|ME {label}| < 60", False, f"{b['me']:+.0f}"))
            op_pass = False

    for label in BANDS:
        l = label[0]
        b = per_band[l]
        if b["n"] == 0:
            continue
        if b["audits_pct"] >= 0.80:
            op_checks.append((f"audits {l} ≥ 80%", True,
                             f"{b['audits_pct']*100:.0f}%"))
        else:
            op_checks.append((f"audits {l} ≥ 80%", False,
                             f"{b['audits_pct']*100:.0f}%"))
            op_pass = False

    cir_checks = []
    cir_pass = True
    cir_problem = False
    b = per_band.get("401-799", {})
    if b.get("n", 0) > 0:
        w40_pct = b["within_40"] / b["n"]
        if w40_pct >= 0.30:
            cir_checks.append(("401-799 ±40 ≥ 30%", True, f"{w40_pct*100:.1f}%"))
        else:
            cir_checks.append(("401-799 ±40 ≥ 30%", False, f"{w40_pct*100:.1f}%"))
            cir_pass = False
            if w40_pct < 0.30:
                cir_problem = True
        if abs(b["me"]) < 80:
            cir_checks.append(("401-799 |ME| < 80", True, f"{b['me']:+.0f}"))
        else:
            cir_checks.append(("401-799 |ME| < 80", False, f"{b['me']:+.0f}"))
            cir_pass = False
            if b["me"] > 100:
                cir_problem = True

    return {
        "operacional_pass": op_pass,
        "operacional_checks": op_checks,
        "cirurgico_pass": cir_pass,
        "cirurgico_checks": cir_checks,
        "cirurgico_estrutural": cir_problem,
    }


def render(opus_per_band: Dict[str, Dict], baseline_per_band: Dict[str, Dict],
           verdict: Dict[str, Any], opus_results: List[Dict], baseline_by_id: Dict,
           ids: List[str]) -> str:
    L = []
    L.append("# Opus 4.7 + schema flat — eval subset 80 redações estratificadas\n")
    L.append("**Sample:** 80 redações estratificadas do baseline (n=200) AES-ENEM.")
    L.append("Distribuição: 15×≤400 + 35×401-799 + 15×800-940 + 15×1000.\n")
    L.append("**Schema:** v2 com flatten (cN_audit.X → cN_X). Reduce profundidade nivel 4 → 3.")
    L.append("Conteúdo de rubrica/system_prompt v2 intactos.\n---\n")

    # Tabela 1: faixa-por-faixa Sonnet baseline vs Opus flat
    L.append("## Tabela 1 — Sonnet baseline vs Opus flat por faixa\n")
    L.append("| Faixa | n | Sonnet ±40 | Opus ±40 | Δ ±40 | Sonnet MAE | Opus MAE | Sonnet ME | Opus ME |")
    L.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for label, _, _ in BANDS:
        sb = baseline_per_band[label]
        ob = opus_per_band[label]
        if sb["n"] == 0 or ob["n"] == 0:
            L.append(f"| {label} | 0 | - | - | - | - | - | - | - |")
            continue
        sb_w40 = sb["within_40"] / sb["n"]
        ob_w40 = ob["within_40"] / ob["n"]
        L.append(f"| {label} | {ob['n']} | {sb_w40*100:.1f}% | {ob_w40*100:.1f}% "
                 f"| {(ob_w40-sb_w40)*100:+.1f} pts "
                 f"| {sb['mae']:.1f} | {ob['mae']:.1f} | {sb['me']:+.0f} | {ob['me']:+.0f} |")
    L.append("")

    # Concordância progressiva (±40, ±60, ±80)
    L.append("## Tabela 2 — Concordância progressiva por faixa (Opus flat)\n")
    L.append("| Faixa | n | ±40 | ±60 | ±80 | MAE | ME |")
    L.append("|---|---:|---:|---:|---:|---:|---:|")
    total_w40 = total_w60 = total_w80 = total_n = 0
    total_audits = 0
    for label, _, _ in BANDS:
        b = opus_per_band[label]
        if b["n"] == 0:
            continue
        total_n += b["n"]
        total_w40 += b["within_40"]
        total_w60 += b["within_60"]
        total_w80 += b["within_80"]
        total_audits += b["audits_complete"]
        L.append(f"| {label} | {b['n']} | "
                 f"{b['within_40']}/{b['n']} ({b['within_40']/b['n']*100:.0f}%) | "
                 f"{b['within_60']}/{b['n']} ({b['within_60']/b['n']*100:.0f}%) | "
                 f"{b['within_80']}/{b['n']} ({b['within_80']/b['n']*100:.0f}%) | "
                 f"{b['mae']:.1f} | {b['me']:+.0f} |")
    L.append(f"| **GLOBAL** | **{total_n}** | "
             f"{total_w40}/{total_n} ({total_w40/total_n*100:.0f}%) | "
             f"{total_w60}/{total_n} ({total_w60/total_n*100:.0f}%) | "
             f"{total_w80}/{total_n} ({total_w80/total_n*100:.0f}%) | - | - |")
    L.append("")

    # Tabela 3 — análise específica do bucket 401-799
    L.append("## Tabela 3 — Análise específica bucket 401-799 (n=35)\n")
    L.append("Cada redação: gabarito + nota Opus + erro. Audit completo na coluna `audit`.\n")
    L.append("| ID | Gab | Opus | Erro | C1 | C2 | C3 | C4 | C5 | audit |")
    L.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|:---:|")
    by_id = {r["id"]: r for r in opus_results}
    in_401_799 = [
        rid for rid in ids
        if rid in baseline_by_id
        and 401 <= baseline_by_id[rid]["gabarito"]["total"] <= 799
    ]
    in_401_799.sort(key=lambda rid: get_red_total(by_id.get(rid) or {}) - baseline_by_id[rid]["gabarito"]["total"])
    for rid in in_401_799:
        gab = baseline_by_id[rid]["gabarito"]["total"]
        rec = by_id.get(rid) or {}
        notas = rec.get("redato_final") or {}
        err = notas.get("total", 0) - gab
        complete = "✓" if is_audit_complete(rec) else "✗"
        L.append(f"| `{rid[:38]}` | {gab} | {notas.get('total','-')} | {err:+d} | "
                 f"{notas.get('c1','-')} | {notas.get('c2','-')} | {notas.get('c3','-')} | "
                 f"{notas.get('c4','-')} | {notas.get('c5','-')} | {complete} |")
    L.append("")

    # Verdict
    L.append("## Verdict — critérios explícitos\n")
    L.append("### OPERACIONAL (consolidar Opus+flat como produção)\n")
    for desc, ok, val in verdict["operacional_checks"]:
        L.append(f"- {'✅' if ok else '❌'} **{desc}** — {val}")
    L.append(f"\n**Operacional:** {'✅ APROVADO' if verdict['operacional_pass'] else '❌ NÃO APROVADO'}\n")

    L.append("### CIRÚRGICO (faixa 401-799)\n")
    for desc, ok, val in verdict["cirurgico_checks"]:
        L.append(f"- {'✅' if ok else '❌'} **{desc}** — {val}")
    L.append(f"\n**Cirúrgico:** {'✅ MAGNITUDE CONTROLADA' if verdict['cirurgico_pass'] else '❌ PROBLEMA ESTRUTURAL' if verdict['cirurgico_estrutural'] else '⚠ MAGNITUDE FORA DO RANGE'}\n")

    # Decisão
    L.append("## Decisão\n")
    if verdict["operacional_pass"]:
        L.append("→ **CONSOLIDAR Opus + schema flat como produção.** Critério operacional "
                 "atingido. Próximo passo: documentar baseline novo, atualizar default de "
                 "modelo, validar em redações fora do AES-ENEM.")
    elif verdict["cirurgico_estrutural"]:
        L.append("→ **PROBLEMA ESTRUTURAL na faixa 401-799.** Não escalar pra produção sem "
                 "investigar a faixa média. Possíveis caminhos: (a) inspeção de auditorias "
                 "individuais nessa faixa pra ver onde o LLM erra; (b) ajuste pontual de "
                 "regras de derivação na zona 401-799; (c) few-shot específico pra faixa média.")
    elif not verdict["cirurgico_pass"]:
        L.append("→ **MAGNITUDE FORA DO RANGE no 401-799 mas não estrutural.** Consolida com "
                 "ressalva: avisar revisor humano em redações com nota Opus 401-799 com "
                 "concordância ainda baixa.")
    else:
        L.append("→ **CASO INTERMEDIÁRIO.** ±40 global abaixo de 45% mas sem indício de "
                 "problema estrutural específico. Investigar onde está o erro residual.")
    L.append("")

    return "\n".join(L)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--baseline", type=Path, required=True)
    p.add_argument("--opus", type=Path, required=True)
    p.add_argument("--ids", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()

    target_ids = [l.strip() for l in args.ids.read_text().splitlines() if l.strip()]
    baseline = {r["id"]: r for r in load(args.baseline)}
    opus = {r["id"]: r for r in load(args.opus)}
    opus_list = list(opus.values())

    # Filtra apenas IDs presentes em ambos
    present_ids = [rid for rid in target_ids if rid in baseline and rid in opus]

    opus_per_band = metrics_per_band(opus, baseline, present_ids)
    baseline_per_band = metrics_per_band(
        {rid: {"redato_final": baseline[rid].get("redato")} for rid in present_ids},
        baseline, present_ids
    )

    total_w40 = sum(b["within_40"] for b in opus_per_band.values() if b.get("n"))
    total_n = sum(b["n"] for b in opus_per_band.values())
    total_audits = sum(b.get("audits_complete", 0) for b in opus_per_band.values() if b.get("n"))
    global_w40 = total_w40 / max(total_n, 1)
    global_audits_pct = total_audits / max(total_n, 1)

    verdict = evaluate_criteria(opus_per_band, global_w40, global_audits_pct)

    report = render(opus_per_band, baseline_per_band, verdict, opus_list, baseline, present_ids)
    args.out.write_text(report, encoding="utf-8")
    print(f"Report: {args.out}")
    print(f"Resumo: ±40 global = {global_w40*100:.1f}%  ({total_w40}/{total_n})")
    print(f"Verdict: operacional={'PASS' if verdict['operacional_pass'] else 'FAIL'}, "
          f"cirurgico={'PASS' if verdict['cirurgico_pass'] else 'FAIL'}")


if __name__ == "__main__":
    main()
