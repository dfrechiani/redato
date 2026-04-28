#!/usr/bin/env python3
"""Compara Sonnet v2 (baseline), Opus v2, Sonnet v2+fewshot INEP nas mesmas
20 redações. Output: REPORT_modelo_vs_fewshot.md.

Trata explicitamente outputs vazios do Opus (bug schema profundo) — separa
"válidos" dos "audit vazio" pra não distorcer estatística.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional, Tuple


COMPS = ("c1", "c2", "c3", "c4", "c5")


def load_jsonl(p: Path) -> List[Dict[str, Any]]:
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]


def get_notas(rec: Dict[str, Any]) -> Optional[Dict[str, int]]:
    notas = rec.get("redato_final") or rec.get("redato")
    if not isinstance(notas, dict):
        return None
    out = {k: int(notas.get(k) or 0) for k in COMPS}
    out["total"] = int(notas.get("total", sum(out[k] for k in COMPS)))
    return out


def get_gab(rec: Dict[str, Any]) -> Optional[Dict[str, int]]:
    g = rec.get("gabarito") or {}
    if g.get("total") is None:
        return None
    out = {k: int(g.get(k) or 0) for k in COMPS}
    out["total"] = int(g["total"])
    return out


def is_opus_empty_output(rec: Dict[str, Any]) -> bool:
    """Detecta output vazio do Opus: notas todas zero E sem qualquer
    sinal de audit preenchido. Schemas diferentes (baseline/fewshot/opus)
    têm campos diferentes — só detectamos quando todas as cN são 0 sem
    error explícito."""
    if rec.get("error"):
        return False
    notas = rec.get("redato_final") or rec.get("redato")
    if not isinstance(notas, dict):
        return False
    if any(int(notas.get(k) or 0) > 0 for k in COMPS):
        return False
    # Todas as 5 notas são 0 — possível empty output. Confirma com audit.
    audit = rec.get("redato_audit")
    if isinstance(audit, dict) and len(audit) == 0:
        return True
    if isinstance(audit, dict):
        # Audit presente: checa se todos os cN_audit têm nota=None
        all_none = all(
            (audit.get(f"{k}_audit") or {}).get("nota") is None
            for k in COMPS
        )
        return all_none
    return False


def metrics_for(records: List[Dict[str, Any]],
                target_ids: List[str]) -> Dict[str, Any]:
    """Computa métricas filtrando só registros válidos. Retorna stats por
    faixa, MAE, ME, ±40, ±80, e contagem de inválidos (erro/output vazio)."""
    by_id = {r["id"]: r for r in records}
    valid: List[Tuple[Dict, Dict, Dict]] = []  # (rec, redato, gab)
    n_error = 0
    n_empty = 0
    n_missing = 0
    for tid in target_ids:
        r = by_id.get(tid)
        if r is None:
            n_missing += 1
            continue
        if r.get("error"):
            n_error += 1
            continue
        if is_opus_empty_output(r):
            n_empty += 1
            continue
        red = get_notas(r)
        gab = get_gab(r)
        if red is None or gab is None:
            n_error += 1
            continue
        valid.append((r, red, gab))

    if not valid:
        return {"n_valid": 0, "n_error": n_error, "n_empty": n_empty,
                "n_missing": n_missing, "n_target": len(target_ids)}

    within_40 = sum(1 for _, red, gab in valid
                    if abs(red["total"] - gab["total"]) <= 40)
    within_80 = sum(1 for _, red, gab in valid
                    if abs(red["total"] - gab["total"]) <= 80)
    mae_total = mean(abs(red["total"] - gab["total"]) for _, red, gab in valid)
    me_total = mean(red["total"] - gab["total"] for _, red, gab in valid)

    mae_per = {k: mean(abs(red[k] - gab[k]) for _, red, gab in valid) for k in COMPS}
    me_per = {k: mean(red[k] - gab[k] for _, red, gab in valid) for k in COMPS}

    bands = {"≤ 400": (0, 400), "401-799": (401, 799),
             "800-940": (800, 940), "1000": (1000, 1000)}
    by_band = {}
    for label, (lo, hi) in bands.items():
        b = [(r, red, gab) for r, red, gab in valid if lo <= gab["total"] <= hi]
        if not b:
            by_band[label] = {"n": 0}
            continue
        by_band[label] = {
            "n": len(b),
            "mae": mean(abs(red["total"] - gab["total"]) for _, red, gab in b),
            "me": mean(red["total"] - gab["total"] for _, red, gab in b),
            "within_40": sum(1 for _, red, gab in b
                              if abs(red["total"] - gab["total"]) <= 40) / len(b),
        }

    valid_ids = [r["id"] for r, _, _ in valid]
    return {
        "n_target": len(target_ids),
        "n_valid": len(valid),
        "n_error": n_error,
        "n_empty": n_empty,
        "n_missing": n_missing,
        "valid_ids": valid_ids,
        "within_40_pct": within_40 / len(valid),
        "within_80_pct": within_80 / len(valid),
        "mae_total": mae_total,
        "me_total": me_total,
        "mae_per_comp": mae_per,
        "me_per_comp": me_per,
        "by_band": by_band,
    }


def filter_records_to_ids(records: List[Dict[str, Any]],
                          ids: List[str]) -> List[Dict[str, Any]]:
    by_id = {r["id"]: r for r in records}
    return [by_id[i] for i in ids if i in by_id]


def render(m_baseline_full, m_opus_full, m_fewshot_full,
           m_baseline_intersec, m_opus_intersec, m_fewshot_intersec,
           ids_full: List[str], ids_intersec: List[str]) -> str:
    L = []
    L.append("# Test — Opus v2 vs Sonnet v2+fewshot INEP vs Sonnet v2 baseline\n")
    L.append("**Sample:** 20 redações estratificadas (4×≤400 + 8×401-799 + 4×800-940 + 4×1000), "
             "as mesmas avaliadas no eval_gold v2 baseline (Sonnet 4.6).\n")
    L.append("---\n")

    # Cobertura
    L.append("## Cobertura por condição\n")
    L.append("| Condição | n alvo | n válidas | erros | outputs vazios |")
    L.append("|---|---:|---:|---:|---:|")
    L.append(f"| Sonnet v2 baseline (full 20) | {m_baseline_full['n_target']} | "
             f"{m_baseline_full['n_valid']} | {m_baseline_full['n_error']} | 0 |")
    L.append(f"| Opus v2 puro | {m_opus_full['n_target']} | {m_opus_full['n_valid']} | "
             f"{m_opus_full['n_error']} | **{m_opus_full['n_empty']}** |")
    L.append(f"| Sonnet v2 + fewshot INEP | {m_fewshot_full['n_target']} | "
             f"{m_fewshot_full['n_valid']} | {m_fewshot_full['n_error']} | "
             f"{m_fewshot_full.get('n_empty', 0)} |")
    L.append("")
    L.append(f"⚠ **Opus produziu {m_opus_full['n_empty']} outputs com audit vazio** "
             f"(`audit_keys=[]`, todos `cN_audit.nota=None`). É o bug histórico de "
             f"schemas profundos em Opus 4.7 (memória do projeto registra). "
             f"As 4 redações nota 1000 estão entre os outputs vazios — Opus não "
             f"completou tool_use em nenhuma delas. Inviável em produção sem "
             f"flatten do schema v2.\n")
    L.append("")

    # Comparação justa: usar interseção de IDs onde TODAS as 3 condições têm output válido
    L.append(f"**Sample efetivo da comparação:** {len(ids_intersec)} redações onde "
             f"todas as 3 condições produziram output válido. Métricas abaixo "
             f"são sobre essa interseção, pra evitar viés de cobertura desigual.\n")
    L.append("---\n")

    # Tabela 1 — Métricas globais (na interseção)
    L.append("## Tabela 1 — Métricas globais (interseção)\n")
    L.append("| Métrica | Sonnet baseline | Opus v2 | Sonnet+fewshot | Δ Opus | Δ Fewshot |")
    L.append("|---|---:|---:|---:|---:|---:|")
    rows = [
        ("±40", "within_40_pct", lambda x: f"{x*100:.1f}%", lambda d: f"{d*100:+.1f} pts"),
        ("±80", "within_80_pct", lambda x: f"{x*100:.1f}%", lambda d: f"{d*100:+.1f} pts"),
        ("MAE total", "mae_total", lambda x: f"{x:.1f}", lambda d: f"{d:+.1f}"),
        ("ME total", "me_total", lambda x: f"{x:+.1f}", lambda d: f"{d:+.1f}"),
    ]
    for label, key, fmt, dfmt in rows:
        v_b = m_baseline_intersec.get(key)
        v_o = m_opus_intersec.get(key)
        v_f = m_fewshot_intersec.get(key)
        if v_b is None or v_o is None or v_f is None:
            L.append(f"| {label} | - | - | - | - | - |")
            continue
        d_o = v_o - v_b
        d_f = v_f - v_b
        L.append(f"| {label} | {fmt(v_b)} | {fmt(v_o)} | {fmt(v_f)} | "
                 f"{dfmt(d_o)} | {dfmt(d_f)} |")
    L.append("")

    # Tabela 2 — ME por competência (viés direcional)
    L.append("## Tabela 2 — ME (viés direcional) por competência\n")
    L.append("| | Sonnet baseline | Opus v2 | Sonnet+fewshot |")
    L.append("|---|---:|---:|---:|")
    for k in COMPS:
        b_me = m_baseline_intersec["me_per_comp"].get(k)
        o_me = m_opus_intersec["me_per_comp"].get(k)
        f_me = m_fewshot_intersec["me_per_comp"].get(k)
        if b_me is None: continue
        L.append(f"| {k.upper()} | {b_me:+.1f} | {o_me:+.1f} | {f_me:+.1f} |")
    L.append("")

    # Tabela 3 — Por faixa de gabarito
    L.append("## Tabela 3 — ME por faixa de gabarito\n")
    L.append("| Faixa | Sonnet baseline (n=ME) | Opus v2 (n=ME) | Sonnet+fewshot (n=ME) |")
    L.append("|---|---|---|---|")
    for label in ("≤ 400", "401-799", "800-940", "1000"):
        b = m_baseline_intersec["by_band"].get(label, {})
        o = m_opus_intersec["by_band"].get(label, {})
        f = m_fewshot_intersec["by_band"].get(label, {})
        def fmt(d):
            if d.get("n", 0) == 0: return "n=0 (sem dado)"
            return f"n={d['n']}, ME={d['me']:+.0f}"
        L.append(f"| {label} | {fmt(b)} | {fmt(o)} | {fmt(f)} |")
    L.append("")

    # Análise por hipótese
    L.append("## Verdict — qual variável tem alavancagem?\n")

    b_w40 = m_baseline_intersec["within_40_pct"]
    o_w40 = m_opus_intersec["within_40_pct"]
    f_w40 = m_fewshot_intersec["within_40_pct"]
    b_me = m_baseline_intersec["me_total"]
    o_me = m_opus_intersec["me_total"]
    f_me = m_fewshot_intersec["me_total"]

    L.append("### Variável MODELO (Sonnet → Opus)\n")
    L.append(f"- Δ ±40: {(o_w40-b_w40)*100:+.1f} pts  ·  Δ MAE: {m_opus_intersec['mae_total']-m_baseline_intersec['mae_total']:+.1f}  ·  Δ ME: {o_me-b_me:+.1f}")
    L.append(f"- **Inviabilidade técnica:** {m_opus_full['n_empty']}/20 outputs vazios. Schema v2 é incompatível com Opus em produção.")
    L.append("")
    L.append("### Variável FEW-SHOT (Sonnet+rubrica v2 → +2 exemplos INEP nota 1000)\n")
    L.append(f"- Δ ±40: {(f_w40-b_w40)*100:+.1f} pts  ·  Δ MAE: {m_fewshot_intersec['mae_total']-m_baseline_intersec['mae_total']:+.1f}  ·  Δ ME: {f_me-b_me:+.1f}")
    L.append("")

    # Verdict pragmático
    L.append("### Recomendação")
    L.append("")
    if (o_w40 - b_w40) > 0.1 and m_opus_full['n_empty'] == 0:
        L.append("→ **Modelo é a alavanca dominante.** Migrar pra Opus.")
    elif (f_w40 - b_w40) > 0.1 and (f_me - b_me) > 0:
        L.append("→ **Few-shot é a alavanca dominante e viável.** Caminho v4: rubrica v2 + "
                 "few-shot INEP expandido (mais exemplos, cobertura por faixa). Não precisa "
                 "trocar modelo nem reinventar rubrica.")
    elif m_opus_full['n_empty'] >= 5:
        L.append("→ **Modelo (Opus) é tecnicamente inviável** com schema v2 atual "
                 f"({m_opus_full['n_empty']}/20 outputs vazios). Restam 2 caminhos: "
                 "(a) flatten do schema v2 + Opus (~3-4 dias de trabalho), "
                 "(b) iterar few-shot com Sonnet (custo baixo). "
                 "Decisão depende de magnitude de Δ no few-shot.")
    else:
        L.append("→ **Sinal fraco em ambas variáveis.** Problema pode estar na rubrica em si, "
                 "não em modelo nem calibração de few-shot. Voltar pra design v4 com "
                 "paradigma diferente (não detectores binários como v3, mas talvez "
                 "ajustes pontuais cirúrgicos na v2).")
    L.append("")

    return "\n".join(L)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--baseline", type=Path, required=True,
                   help="JSONL do eval gold completo (200 redações)")
    p.add_argument("--opus", type=Path, required=True)
    p.add_argument("--fewshot", type=Path, required=True)
    p.add_argument("--ids", type=Path, required=True,
                   help="Lista dos 20 IDs do test")
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()

    target_ids = [l.strip() for l in args.ids.read_text().splitlines() if l.strip()]
    baseline = load_jsonl(args.baseline)
    opus = load_jsonl(args.opus)
    fewshot = load_jsonl(args.fewshot)

    # Métricas full sample
    m_baseline_full = metrics_for(baseline, target_ids)
    m_opus = metrics_for(opus, target_ids)
    m_fewshot = metrics_for(fewshot, target_ids)

    # Interseção: IDs com output válido em todas as 3 condições
    valid_b = set(m_baseline_full.get("valid_ids", []))
    valid_o = set(m_opus.get("valid_ids", []))
    valid_f = set(m_fewshot.get("valid_ids", []))
    intersec = sorted(valid_b & valid_o & valid_f)
    print(f"Interseção válida: {len(intersec)}/20")

    # Re-computa cada uma na interseção
    m_baseline_intersec = metrics_for(baseline, intersec)
    m_opus_intersec = metrics_for(opus, intersec)
    m_fewshot_intersec = metrics_for(fewshot, intersec)

    report = render(m_baseline_full, m_opus, m_fewshot,
                    m_baseline_intersec, m_opus_intersec, m_fewshot_intersec,
                    target_ids, intersec)
    args.out.write_text(report, encoding="utf-8")
    print(f"\nReport: {args.out}")
    print(f"\nQuick summary:")
    print(f"  Baseline (n={m_baseline_intersec['n_valid']}): ±40={m_baseline_intersec['within_40_pct']*100:.1f}%  ME={m_baseline_intersec['me_total']:+.0f}")
    print(f"  Opus     (n={m_opus_intersec['n_valid']}): ±40={m_opus_intersec['within_40_pct']*100:.1f}%  ME={m_opus_intersec['me_total']:+.0f}")
    print(f"  Fewshot  (n={m_fewshot_intersec['n_valid']}): ±40={m_fewshot_intersec['within_40_pct']*100:.1f}%  ME={m_fewshot_intersec['me_total']:+.0f}")


if __name__ == "__main__":
    main()
