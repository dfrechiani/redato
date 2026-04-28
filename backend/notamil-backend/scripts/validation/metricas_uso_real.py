#!/usr/bin/env python3
"""Re-mede o eval Opus + flat (POST caps v2) com métricas adequadas ao
uso real da Redato (diagnóstico em parágrafo curto + simulado em redação
completa). 3 análises + comparativo vs ±40.

Uso:
    python scripts/validation/metricas_uso_real.py \\
        --opus scripts/validation/results/eval_opus_flat_80_POST_CAPS_v2_*.jsonl \\
        --baseline scripts/validation/results/eval_gold_run_20260426_093436.jsonl \\
        --ids /tmp/test80_ids.txt \\
        --out scripts/validation/results/REPORT_metricas_uso_real.md
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional, Tuple


COMPS = ("c1", "c2", "c3", "c4", "c5")

# 5 faixas pra acerto de faixa
BANDS_5 = [
    (1, "≤400 (insuficiente)", 0, 400),
    (2, "401-600 (em desenvolvimento)", 401, 600),
    (3, "601-800 (mediano)", 601, 800),
    (4, "801-900 (bom)", 801, 900),
    (5, "901-1000 (excelente)", 901, 1000),
]


def total_to_band(total: int) -> int:
    for n, _label, lo, hi in BANDS_5:
        if lo <= total <= hi:
            return n
    return 0


def band_label(n: int) -> str:
    for num, label, _, _ in BANDS_5:
        if num == n:
            return label
    return "?"


def nota_to_level(n: int) -> str:
    """C1-C5 nota → forte / médio / fraco."""
    if n >= 160:
        return "forte"
    if n >= 80:
        return "medio"
    return "fraco"


LEVEL_RANK = {"fraco": 0, "medio": 1, "forte": 2}


def load(path: Path) -> List[Dict[str, Any]]:
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def get_red_notas(rec: Dict[str, Any]) -> Optional[Dict[str, int]]:
    n = rec.get("redato_final") or rec.get("redato")
    if not isinstance(n, dict):
        return None
    out = {k: int(n.get(k) or 0) for k in COMPS}
    out["total"] = int(n.get("total", sum(out[k] for k in COMPS)))
    return out


def get_gab(rec: Dict[str, Any]) -> Optional[Dict[str, int]]:
    g = rec.get("gabarito") or {}
    if g.get("total") is None:
        return None
    out = {k: int(g.get(k) or 0) for k in COMPS}
    out["total"] = int(g["total"])
    return out


# ──────────────────────────────────────────────────────────────────────
# Análise 1 — Acerto de faixa
# ──────────────────────────────────────────────────────────────────────

def analise_1_faixas(opus_by: Dict, baseline_by: Dict, ids: List[str]) -> Dict:
    exact = 0
    tolerance_1 = 0
    valid = 0
    by_gold_band: Dict[int, Dict[str, int]] = defaultdict(lambda: {"n": 0, "exact": 0, "tol1": 0})
    confusion: Dict[Tuple[int, int], int] = defaultdict(int)

    for rid in ids:
        red = get_red_notas(opus_by.get(rid) or {})
        gab = get_gab(baseline_by.get(rid) or {})
        if red is None or gab is None:
            continue
        gb = total_to_band(gab["total"])
        rb = total_to_band(red["total"])
        if gb == 0 or rb == 0:
            continue
        valid += 1
        if gb == rb:
            exact += 1
            by_gold_band[gb]["exact"] += 1
        if abs(gb - rb) <= 1:
            tolerance_1 += 1
            by_gold_band[gb]["tol1"] += 1
        by_gold_band[gb]["n"] += 1
        confusion[(gb, rb)] += 1

    return {
        "valid": valid,
        "exact": exact,
        "tolerance_1": tolerance_1,
        "exact_pct": exact / max(valid, 1),
        "tol1_pct": tolerance_1 / max(valid, 1),
        "by_gold_band": dict(by_gold_band),
        "confusion": dict(confusion),
    }


# ──────────────────────────────────────────────────────────────────────
# Análise 2 — Acerto direcional por competência (forte/médio/fraco)
# ──────────────────────────────────────────────────────────────────────

def analise_2_direcional(opus_by: Dict, baseline_by: Dict, ids: List[str]) -> Dict:
    per_comp: Dict[str, Dict[str, int]] = {k: {"valid": 0, "exact": 0, "adjacent": 0}
                                            for k in COMPS}
    confusion_per_comp: Dict[str, Dict[Tuple[str, str], int]] = {
        k: defaultdict(int) for k in COMPS
    }

    for rid in ids:
        red = get_red_notas(opus_by.get(rid) or {})
        gab = get_gab(baseline_by.get(rid) or {})
        if red is None or gab is None:
            continue
        for k in COMPS:
            g_lvl = nota_to_level(gab[k])
            r_lvl = nota_to_level(red[k])
            per_comp[k]["valid"] += 1
            if g_lvl == r_lvl:
                per_comp[k]["exact"] += 1
                per_comp[k]["adjacent"] += 1
            elif abs(LEVEL_RANK[g_lvl] - LEVEL_RANK[r_lvl]) == 1:
                per_comp[k]["adjacent"] += 1
            confusion_per_comp[k][(g_lvl, r_lvl)] += 1

    return {
        "per_comp": per_comp,
        "confusion": {k: dict(v) for k, v in confusion_per_comp.items()},
    }


# ──────────────────────────────────────────────────────────────────────
# Análise 3 — Precisão de detecção de flags
# ──────────────────────────────────────────────────────────────────────

def evaluate_flag(rec_audit: dict, gold: dict, flag_name: str) -> Tuple[bool, bool, str]:
    """Avalia se uma flag está disparada e se gabarito penalizou competência
    correspondente. Retorna (flag_fired, gold_penalized, comp)."""
    if not isinstance(rec_audit, dict):
        return False, False, "?"

    # Mapeia flag → função de checagem + competência alvo + threshold gold
    if flag_name == "c1_reincidencia":
        ca = rec_audit.get("c1_audit") or {}
        fired = bool(ca.get("reincidencia_de_erro"))
        return fired, gold["c1"] <= 80, "c1"
    if flag_name == "c1_fluency_compromised":
        ca = rec_audit.get("c1_audit") or {}
        fired = bool(ca.get("reading_fluency_compromised"))
        return fired, gold["c1"] <= 80, "c1"
    if flag_name == "c2_tangenciamento":
        ca = rec_audit.get("c2_audit") or {}
        fired = bool(ca.get("tangenciamento_detected"))
        return fired, gold["c2"] <= 40, "c2"
    if flag_name == "c2_copia_motivadores":
        ca = rec_audit.get("c2_audit") or {}
        fired = bool(ca.get("copia_motivadores_sem_aspas"))
        return fired, gold["c2"] <= 80, "c2"
    if flag_name == "c2_all_decorative":
        ca = rec_audit.get("c2_audit") or {}
        refs = ca.get("repertoire_references") or []
        if not isinstance(refs, list) or len(refs) < 2:
            return False, gold["c2"] <= 80, "c2"
        productive = [r for r in refs if isinstance(r, dict) and r.get("productivity") == "productive"]
        fired = len(productive) == 0
        return fired, gold["c2"] <= 80, "c2"
    if flag_name == "c3_no_thesis":
        ca = rec_audit.get("c3_audit") or {}
        fired = ca.get("has_explicit_thesis") is False
        return fired, gold["c3"] <= 120, "c3"
    if flag_name == "c3_argumentos_contraditorios":
        ca = rec_audit.get("c3_audit") or {}
        fired = bool(ca.get("argumentos_contraditorios"))
        return fired, gold["c3"] <= 80, "c3"
    if flag_name == "c3_limitado_motivadores":
        ca = rec_audit.get("c3_audit") or {}
        fired = bool(ca.get("limitado_aos_motivadores"))
        return fired, gold["c3"] <= 120, "c3"
    if flag_name == "c4_mechanical_repetition":
        ca = rec_audit.get("c4_audit") or {}
        fired = bool(ca.get("has_mechanical_repetition"))
        return fired, gold["c4"] <= 120, "c4"
    if flag_name == "c4_complex_periods_broken":
        ca = rec_audit.get("c4_audit") or {}
        # nota: complex_periods_well_structured=False = "broken"
        fired = ca.get("complex_periods_well_structured") is False
        return fired, gold["c4"] <= 120, "c4"
    if flag_name == "c5_nao_articulada":
        ca = rec_audit.get("c5_audit") or {}
        fired = ca.get("proposta_articulada_ao_tema") is False
        return fired, gold["c5"] <= 80, "c5"
    return False, False, "?"


FLAGS_TO_EVAL = [
    "c1_reincidencia",
    "c1_fluency_compromised",
    "c2_tangenciamento",
    "c2_copia_motivadores",
    "c2_all_decorative",
    "c3_no_thesis",
    "c3_argumentos_contraditorios",
    "c3_limitado_motivadores",
    "c4_mechanical_repetition",
    "c4_complex_periods_broken",
    "c5_nao_articulada",
]


def analise_3_flags(opus_by: Dict, baseline_by: Dict, ids: List[str]) -> Dict:
    per_flag: Dict[str, Dict[str, int]] = {
        f: {"tp": 0, "fp": 0, "tn": 0, "fn": 0} for f in FLAGS_TO_EVAL
    }
    for rid in ids:
        rec = opus_by.get(rid) or {}
        gab = get_gab(baseline_by.get(rid) or {})
        audit = rec.get("redato_audit") or {}
        if not isinstance(audit, dict) or len(audit) == 0 or gab is None:
            continue
        for f in FLAGS_TO_EVAL:
            fired, penalized, _comp = evaluate_flag(audit, gab, f)
            if fired and penalized:
                per_flag[f]["tp"] += 1
            elif fired and not penalized:
                per_flag[f]["fp"] += 1
            elif not fired and penalized:
                per_flag[f]["fn"] += 1
            else:
                per_flag[f]["tn"] += 1
    out = {}
    for f, c in per_flag.items():
        tp, fp, tn, fn = c["tp"], c["fp"], c["tn"], c["fn"]
        precision = tp / max(tp + fp, 1) if (tp + fp) > 0 else None
        recall = tp / max(tp + fn, 1) if (tp + fn) > 0 else None
        out[f] = {
            **c, "precision": precision, "recall": recall,
            "fired_n": tp + fp, "penalty_n": tp + fn,
        }
    return out


# ──────────────────────────────────────────────────────────────────────
# Comparação contra ±40 antigo
# ──────────────────────────────────────────────────────────────────────

def analise_4_old_metric(opus_by: Dict, baseline_by: Dict, ids: List[str]) -> Dict:
    within_40 = 0
    valid = 0
    for rid in ids:
        red = get_red_notas(opus_by.get(rid) or {})
        gab = get_gab(baseline_by.get(rid) or {})
        if red is None or gab is None:
            continue
        valid += 1
        if abs(red["total"] - gab["total"]) <= 40:
            within_40 += 1
    return {"valid": valid, "within_40": within_40,
            "within_40_pct": within_40 / max(valid, 1)}


# ──────────────────────────────────────────────────────────────────────
# Render
# ──────────────────────────────────────────────────────────────────────

def render_report(a1, a2, a3, a4_opus, a4_baseline, opus_label: str) -> str:
    L: List[str] = []
    L.append(f"# Métricas de uso real — {opus_label}\n")
    L.append("Redefinição de métricas pra refletir como a Redato é usada de fato:")
    L.append("- **Modo diagnóstico** (parágrafo curto): aluno precisa saber se está")
    L.append("  fraco / médio / forte por competência, e se há problema específico detectado.")
    L.append("- **Modo simulado** (redação completa): faixa global da nota (±100) importa")
    L.append("  mais que precisão exata da nota total.")
    L.append("\nMétrica antiga (±40 nota total) era apropriada pra comparação contra avaliador")
    L.append("humano INEP, mas não pra utilidade pedagógica direta.\n")
    L.append("---\n")

    # ---- Análise 1 ----
    L.append("## Análise 1 — Acerto de faixa (5 níveis)\n")
    L.append(f"Sample válido: {a1['valid']}\n")
    L.append("| | n | Acerto exato | Acerto ±1 faixa |")
    L.append("|---|---:|---:|---:|")
    L.append(f"| **GLOBAL** | {a1['valid']} | "
             f"{a1['exact']}/{a1['valid']} ({a1['exact_pct']*100:.1f}%) | "
             f"{a1['tolerance_1']}/{a1['valid']} ({a1['tol1_pct']*100:.1f}%) |")
    for n, label, _, _ in BANDS_5:
        b = a1["by_gold_band"].get(n, {"n": 0, "exact": 0, "tol1": 0})
        if b["n"] == 0:
            L.append(f"| {label} | 0 | - | - |")
            continue
        L.append(f"| {label} | {b['n']} | "
                 f"{b['exact']}/{b['n']} ({b['exact']/b['n']*100:.0f}%) | "
                 f"{b['tol1']}/{b['n']} ({b['tol1']/b['n']*100:.0f}%) |")
    L.append("")
    # Matriz de confusão
    L.append("**Matriz de confusão (linha = faixa do gabarito, coluna = faixa Redato):**\n")
    L.append("| Gold \\ Redato | F1 | F2 | F3 | F4 | F5 |")
    L.append("|---|---:|---:|---:|---:|---:|")
    for gb in range(1, 6):
        cells = [str(a1["confusion"].get((gb, rb), 0)) for rb in range(1, 6)]
        L.append(f"| **F{gb}** | {' | '.join(cells)} |")
    L.append("")

    # ---- Análise 2 ----
    L.append("## Análise 2 — Acerto direcional por competência (forte/médio/fraco)\n")
    L.append("forte=160-200, médio=80-120, fraco=0-40\n")
    L.append("| Comp | n | Acerto exato | Adjacente (1 nível) |")
    L.append("|---|---:|---:|---:|")
    total_exact = total_adj = total_n = 0
    for k in COMPS:
        c = a2["per_comp"][k]
        total_exact += c["exact"]
        total_adj += c["adjacent"]
        total_n += c["valid"]
        if c["valid"] == 0:
            L.append(f"| {k.upper()} | 0 | - | - |")
            continue
        L.append(f"| {k.upper()} | {c['valid']} | "
                 f"{c['exact']}/{c['valid']} ({c['exact']/c['valid']*100:.1f}%) | "
                 f"{c['adjacent']}/{c['valid']} ({c['adjacent']/c['valid']*100:.1f}%) |")
    if total_n:
        L.append(f"| **MÉDIA** | {total_n} | "
                 f"{total_exact}/{total_n} ({total_exact/total_n*100:.1f}%) | "
                 f"{total_adj}/{total_n} ({total_adj/total_n*100:.1f}%) |")
    L.append("")
    # Confusion matrix por comp
    L.append("**Confusion matrix por competência (linha = gold, coluna = Redato):**\n")
    for k in COMPS:
        L.append(f"### {k.upper()}\n")
        L.append("| Gold \\ Redato | fraco | médio | forte |")
        L.append("|---|---:|---:|---:|")
        for g in ("fraco", "medio", "forte"):
            cells = [str(a2["confusion"][k].get((g, r), 0)) for r in ("fraco", "medio", "forte")]
            L.append(f"| **{g}** | {' | '.join(cells)} |")
        L.append("")

    # ---- Análise 3 ----
    L.append("## Análise 3 — Precisão de detecção de flags (modo diagnóstico)\n")
    L.append("Pra cada flag negativa: TP/FP/FN/TN contra penalty no gabarito.")
    L.append("Precision = % das vezes que a flag disparou e era justificada.")
    L.append("Recall = % dos casos reais de problema que a flag pegou.\n")
    L.append("| Flag | TP | FP | FN | TN | Precision | Recall | n_disparos | n_problemas_real |")
    L.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for f in FLAGS_TO_EVAL:
        c = a3[f]
        prec = f"{c['precision']*100:.1f}%" if c["precision"] is not None else "n/a"
        rec = f"{c['recall']*100:.1f}%" if c["recall"] is not None else "n/a"
        L.append(f"| `{f}` | {c['tp']} | {c['fp']} | {c['fn']} | {c['tn']} | "
                 f"{prec} | {rec} | {c['fired_n']} | {c['penalty_n']} |")
    L.append("")

    # ---- Análise 4 ----
    L.append("## Análise 4 — Comparativo contra métrica antiga (±40)\n")
    L.append("| Modelo | ±40 nota total |")
    L.append("|---|---:|")
    L.append(f"| Sonnet baseline (v2 nested) | "
             f"{a4_baseline['within_40']}/{a4_baseline['valid']} "
             f"({a4_baseline['within_40_pct']*100:.1f}%) |")
    L.append(f"| **Opus + flat + caps v2 (atual)** | "
             f"{a4_opus['within_40']}/{a4_opus['valid']} "
             f"({a4_opus['within_40_pct']*100:.1f}%) |")
    L.append("")

    return "\n".join(L)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--opus", type=Path, required=True)
    p.add_argument("--baseline", type=Path, required=True)
    p.add_argument("--ids", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--label", type=str, default="Opus + flat + caps v2 (n=80)")
    args = p.parse_args()

    ids = [l.strip() for l in args.ids.read_text().splitlines() if l.strip()]
    opus_by = {r["id"]: r for r in load(args.opus)}
    baseline_by = {r["id"]: r for r in load(args.baseline)}

    a1 = analise_1_faixas(opus_by, baseline_by, ids)
    a2 = analise_2_direcional(opus_by, baseline_by, ids)
    a3 = analise_3_flags(opus_by, baseline_by, ids)
    a4_opus = analise_4_old_metric(opus_by, baseline_by, ids)

    # Pra comparação histórica: Sonnet baseline na mesma população
    a4_baseline = analise_4_old_metric(
        {rid: {"redato_final": baseline_by[rid].get("redato")}
         for rid in baseline_by},
        baseline_by, ids
    )

    report = render_report(a1, a2, a3, a4_opus, a4_baseline, args.label)
    args.out.write_text(report, encoding="utf-8")
    print(f"Report: {args.out}")
    print(f"\nQuick summary:")
    print(f"  Acerto faixa exato:  {a1['exact_pct']*100:.1f}%")
    print(f"  Acerto faixa ±1:     {a1['tol1_pct']*100:.1f}%")
    direct_total_n = sum(a2["per_comp"][k]["valid"] for k in COMPS)
    direct_total_exact = sum(a2["per_comp"][k]["exact"] for k in COMPS)
    direct_total_adj = sum(a2["per_comp"][k]["adjacent"] for k in COMPS)
    print(f"  Acerto direcional exato: {direct_total_exact/direct_total_n*100:.1f}%")
    print(f"  Acerto direcional ±1:    {direct_total_adj/direct_total_n*100:.1f}%")
    print(f"  ±40 (métrica antiga):    {a4_opus['within_40_pct']*100:.1f}%")


if __name__ == "__main__":
    main()
