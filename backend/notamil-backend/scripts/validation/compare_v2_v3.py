#!/usr/bin/env python3
"""Comparação A/B v2 vs v3 contra gabarito INEP em 200 redações AES-ENEM.

Lê o JSONL do baseline v2 e o JSONL do run v3, calcula métricas alinhadas
com README_AB_TEST.md (concordância ±40, MAE, ME por faixa, distribuição
de flags), gera relatório executivo em markdown.

Uso (de backend/notamil-backend):
    python scripts/validation/compare_v2_v3.py \\
        --v2 scripts/validation/results/eval_gold_run_20260426_093436.jsonl \\
        --v3 scripts/validation/results/eval_gold_v3_run_*.jsonl
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from statistics import mean, stdev
from typing import Any, Dict, List, Optional, Tuple


COMPS = ("c1", "c2", "c3", "c4", "c5")


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def get_redato_notas(rec: Dict[str, Any]) -> Optional[Dict[str, int]]:
    """Compatível com schema antigo (rec['redato']) e novo (rec['redato_final'])."""
    notas = rec.get("redato_final") or rec.get("redato")
    if not isinstance(notas, dict):
        return None
    out = {}
    for k in COMPS:
        v = notas.get(k)
        out[k] = int(v) if isinstance(v, (int, float)) else 0
    out["total"] = int(notas.get("total", sum(out[k] for k in COMPS)))
    return out


def get_gabarito_notas(rec: Dict[str, Any]) -> Optional[Dict[str, int]]:
    g = rec.get("gabarito") or {}
    if not isinstance(g, dict) or g.get("total") is None:
        return None
    out = {}
    for k in COMPS:
        v = g.get(k)
        out[k] = int(v) if isinstance(v, (int, float)) else 0
    out["total"] = int(g.get("total", sum(out[k] for k in COMPS)))
    return out


def compute_metrics(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Computa métricas pra um run (v2 ou v3)."""
    valid = []
    for r in records:
        if r.get("error"):
            continue
        red = get_redato_notas(r)
        gab = get_gabarito_notas(r)
        if red is None or gab is None:
            continue
        valid.append((r, red, gab))

    if not valid:
        return {"n_valid": 0}

    # Concordância ±40 / ±60 / ±80 (global) — múltiplos thresholds pra
    # distinguir "perto-mas-não-exato" (calibração) de "longe" (estrutural).
    within_40_total = sum(1 for _, red, gab in valid
                          if abs(red["total"] - gab["total"]) <= 40)
    within_60_total = sum(1 for _, red, gab in valid
                          if abs(red["total"] - gab["total"]) <= 60)
    within_80_total = sum(1 for _, red, gab in valid
                          if abs(red["total"] - gab["total"]) <= 80)
    within_40_per_comp = {}
    for k in COMPS:
        within_40_per_comp[k] = sum(1 for _, red, gab in valid
                                    if abs(red[k] - gab[k]) <= 40)

    # MAE
    mae_total = mean(abs(red["total"] - gab["total"]) for _, red, gab in valid)
    mae_per_comp = {k: mean(abs(red[k] - gab[k]) for _, red, gab in valid)
                    for k in COMPS}

    # ME (viés direcional)
    me_total = mean(red["total"] - gab["total"] for _, red, gab in valid)
    me_per_comp = {k: mean(red[k] - gab[k] for _, red, gab in valid)
                   for k in COMPS}

    # Por faixa
    bands = {
        "≤ 400": (0, 400),
        "401-799": (401, 799),
        "≥ 800": (800, 1500),
    }
    by_band: Dict[str, Dict[str, Any]] = {}
    for label, (lo, hi) in bands.items():
        bucket = [(r, red, gab) for r, red, gab in valid
                  if lo <= gab["total"] <= hi]
        if not bucket:
            by_band[label] = {"n": 0}
            continue
        by_band[label] = {
            "n": len(bucket),
            "mae_total": mean(abs(red["total"] - gab["total"]) for _, red, gab in bucket),
            "me_total": mean(red["total"] - gab["total"] for _, red, gab in bucket),
            "within_40": sum(1 for _, red, gab in bucket
                             if abs(red["total"] - gab["total"]) <= 40) / len(bucket),
        }

    # Top 10 erros residuais (|erro| > 80)
    big_errors = [(abs(red["total"] - gab["total"]),
                   red["total"] - gab["total"], r, red, gab)
                  for r, red, gab in valid]
    big_errors.sort(key=lambda x: -x[0])
    top10 = [{
        "id": r["id"],
        "fonte": r.get("fonte", "?"),
        "gab_total": gab["total"],
        "redato_total": red["total"],
        "erro": signed,
    } for abs_err, signed, r, red, gab in big_errors[:10]]

    # Latência média (controle operacional, não otimização)
    latencies_ms = [r.get("latency_ms") for r, _, _ in valid
                    if isinstance(r.get("latency_ms"), (int, float))]
    latency_mean_s = (mean(latencies_ms) / 1000) if latencies_ms else 0.0
    latency_median_s = (sorted(latencies_ms)[len(latencies_ms)//2] / 1000
                        if latencies_ms else 0.0)

    return {
        "n_valid": len(valid),
        "n_total_records": len(records),
        "n_errors": sum(1 for r in records if r.get("error")),
        "within_40_total": within_40_total / len(valid),
        "within_60_total": within_60_total / len(valid),
        "within_80_total": within_80_total / len(valid),
        "within_40_per_comp": {k: v / len(valid) for k, v in within_40_per_comp.items()},
        "mae_total": mae_total,
        "mae_per_comp": mae_per_comp,
        "me_total": me_total,
        "me_per_comp": me_per_comp,
        "by_band": by_band,
        "top10_errors": top10,
        "latency_mean_s": latency_mean_s,
        "latency_median_s": latency_median_s,
    }


def compute_flag_distribution(records: List[Dict[str, Any]]) -> Dict[str, Dict[str, int]]:
    """Conta quantas redações disparam cada flag v3 (apenas registros v3)."""
    counts: Counter = Counter()
    n_v3 = 0
    for r in records:
        if r.get("error"):
            continue
        audit = r.get("redato_audit") or {}
        flags = audit.get("flags") if isinstance(audit, dict) else None
        if not isinstance(flags, dict):
            continue
        n_v3 += 1
        for k, v in flags.items():
            if k == "anulacao" and v is not None:
                counts[f"anulacao={v}"] += 1
            elif v is True:
                counts[k] += 1
    return {"n_v3_records": n_v3, "counts": dict(counts)}


_FLAG_KEYS = (
    "tangenciamento", "copia_motivadores_recorrente",
    "repertorio_de_bolso", "argumentacao_previsivel",
    "limitacao_aos_motivadores", "proposta_vaga_ou_constatatoria",
    "proposta_desarticulada", "desrespeito_direitos_humanos",
)


def compute_flag_error_correlation(records: List[Dict[str, Any]]) -> Dict[str, Dict[str, float]]:
    """Pra cada flag binária v3, calcula MAE/ME nas redações onde
    disparou vs onde não disparou. Diagnostica calibração:
    - Flag dispara + erro ~ 0  → detector calibrado
    - Flag dispara + ME muito negativo → detector rebaixa demais
    - Flag dispara + ME muito positivo → detector inflaciona (raro)
    - Flag nunca dispara → não consegue avaliar (registrar)
    """
    out: Dict[str, Dict[str, float]] = {}
    for fk in _FLAG_KEYS:
        with_flag = []  # (abs_err, signed_err)
        without_flag = []
        for r in records:
            if r.get("error"):
                continue
            audit = r.get("redato_audit") or {}
            flags = audit.get("flags") if isinstance(audit, dict) else None
            red = get_redato_notas(r)
            gab = get_gabarito_notas(r)
            if not isinstance(flags, dict) or red is None or gab is None:
                continue
            err = red["total"] - gab["total"]
            if flags.get(fk) is True:
                with_flag.append((abs(err), err))
            else:
                without_flag.append((abs(err), err))
        out[fk] = {
            "n_with": len(with_flag),
            "n_without": len(without_flag),
            "mae_with": (mean(a for a, _ in with_flag) if with_flag else None),
            "mae_without": (mean(a for a, _ in without_flag) if without_flag else None),
            "me_with": (mean(s for _, s in with_flag) if with_flag else None),
            "me_without": (mean(s for _, s in without_flag) if without_flag else None),
        }
    return out


def render_report(m_v2: dict, m_v3: dict, flag_dist: dict,
                  flag_error_corr: dict, v2_path: str, v3_path: str) -> str:
    L: List[str] = []
    L.append("# A/B v2 vs v3 — Validação contra gabarito INEP")
    L.append("")
    L.append(f"Inputs:")
    L.append(f"- v2 baseline: `{v2_path}`")
    L.append(f"- v3 run:      `{v3_path}`")
    L.append("")
    L.append(f"Cobertura:")
    L.append(f"- v2: {m_v2['n_valid']} válidas / {m_v2['n_total_records']} (erros: {m_v2['n_errors']})")
    L.append(f"- v3: {m_v3['n_valid']} válidas / {m_v3['n_total_records']} (erros: {m_v3['n_errors']})")
    L.append("")
    L.append("---")
    L.append("")

    # Tabela 1 — Métricas globais
    L.append("## Tabela 1 — Métricas globais")
    L.append("")
    L.append("| Métrica | v2 baseline | v3 | Δ |")
    L.append("|---|---:|---:|---:|")
    d = m_v3["within_40_total"] - m_v2["within_40_total"]
    L.append(f"| Concordância ±40 (total) | {m_v2['within_40_total']*100:.1f}% | "
             f"{m_v3['within_40_total']*100:.1f}% | {d*100:+.1f} pts |")
    d = m_v3["within_60_total"] - m_v2["within_60_total"]
    L.append(f"| Concordância ±60 (total) | {m_v2['within_60_total']*100:.1f}% | "
             f"{m_v3['within_60_total']*100:.1f}% | {d*100:+.1f} pts |")
    d = m_v3["within_80_total"] - m_v2["within_80_total"]
    L.append(f"| Concordância ±80 (total) | {m_v2['within_80_total']*100:.1f}% | "
             f"{m_v3['within_80_total']*100:.1f}% | {d*100:+.1f} pts |")
    d = m_v3["mae_total"] - m_v2["mae_total"]
    L.append(f"| MAE total | {m_v2['mae_total']:.1f} | {m_v3['mae_total']:.1f} | {d:+.1f} |")
    d = m_v3["me_total"] - m_v2["me_total"]
    L.append(f"| ME total (viés) | {m_v2['me_total']:+.1f} | {m_v3['me_total']:+.1f} | {d:+.1f} |")
    d = m_v3["latency_mean_s"] - m_v2["latency_mean_s"]
    L.append(f"| Latência média/redação | {m_v2['latency_mean_s']:.1f}s | "
             f"{m_v3['latency_mean_s']:.1f}s | {d:+.1f}s |")
    L.append("")
    L.append("**Leitura ±40 vs ±60 vs ±80:** se ±40 baixo mas ±80 alto → "
             "calibração de escala (corrigível). Se ±80 também baixo → erro estrutural.")
    L.append("")

    # Tabela 2 — Concordância e MAE por competência
    L.append("## Tabela 2 — Concordância ±40 e MAE por competência")
    L.append("")
    L.append("| | v2 ±40 | v3 ±40 | Δ ±40 | v2 MAE | v3 MAE | Δ MAE |")
    L.append("|---|---:|---:|---:|---:|---:|---:|")
    for k in COMPS:
        v2_w = m_v2["within_40_per_comp"][k] * 100
        v3_w = m_v3["within_40_per_comp"][k] * 100
        v2_mae = m_v2["mae_per_comp"][k]
        v3_mae = m_v3["mae_per_comp"][k]
        L.append(f"| {k.upper()} | {v2_w:.1f}% | {v3_w:.1f}% | {v3_w-v2_w:+.1f} pts | "
                 f"{v2_mae:.1f} | {v3_mae:.1f} | {v3_mae-v2_mae:+.1f} |")
    L.append("")

    # Tabela 3 — Viés (ME) por competência
    L.append("## Tabela 3 — Viés direcional (ME = Redato - Gabarito) por competência")
    L.append("")
    L.append("| | v2 ME | v3 ME | Δ ME |")
    L.append("|---|---:|---:|---:|")
    for k in COMPS:
        v2_me = m_v2["me_per_comp"][k]
        v3_me = m_v3["me_per_comp"][k]
        L.append(f"| {k.upper()} | {v2_me:+.1f} | {v3_me:+.1f} | {v3_me-v2_me:+.1f} |")
    L.append("")

    # Tabela 4 — Por faixa
    L.append("## Tabela 4 — Métricas por faixa de gabarito")
    L.append("")
    L.append("| Faixa | n | v2 MAE | v3 MAE | v2 ME | v3 ME | v2 ±40 | v3 ±40 |")
    L.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    for label in ("≤ 400", "401-799", "≥ 800"):
        b2 = m_v2["by_band"][label]
        b3 = m_v3["by_band"][label]
        if b2.get("n", 0) == 0 or b3.get("n", 0) == 0:
            L.append(f"| {label} | - | - | - | - | - | - | - |")
            continue
        L.append(f"| {label} | {b2['n']} | {b2['mae_total']:.1f} | {b3['mae_total']:.1f} | "
                 f"{b2['me_total']:+.1f} | {b3['me_total']:+.1f} | "
                 f"{b2['within_40']*100:.1f}% | {b3['within_40']*100:.1f}% |")
    L.append("")

    # Tabela 5 — Distribuição de flags v3 (sanity dos detectores)
    L.append("## Tabela 5 — Distribuição de flags v3 (sanity dos detectores)")
    L.append("")
    L.append(f"Registros v3 com flags presentes: {flag_dist['n_v3_records']}")
    L.append("")
    L.append("| Flag | Disparada em (n) | % |")
    L.append("|---|---:|---:|")
    for k in [
        "tangenciamento", "copia_motivadores_recorrente",
        "repertorio_de_bolso", "argumentacao_previsivel",
        "limitacao_aos_motivadores", "proposta_vaga_ou_constatatoria",
        "proposta_desarticulada", "desrespeito_direitos_humanos",
    ]:
        n = flag_dist["counts"].get(k, 0)
        pct = (n / flag_dist['n_v3_records'] * 100) if flag_dist['n_v3_records'] else 0
        L.append(f"| `{k}` | {n} | {pct:.1f}% |")
    # Anulações (categoria à parte)
    anul_keys = [k for k in flag_dist["counts"] if k.startswith("anulacao=")]
    if anul_keys:
        L.append("")
        L.append("**Anulações detectadas:**")
        for k in anul_keys:
            L.append(f"- `{k}`: {flag_dist['counts'][k]}")
    L.append("")

    # Tabela 5b — Correlação flag × erro (calibração dos detectores)
    L.append("## Tabela 5b — Correlação flag × erro (calibração dos detectores)")
    L.append("")
    L.append("Pra cada flag binária: MAE/ME nas redações onde disparou vs onde não disparou.")
    L.append("Leitura: flag dispara + ME ~ 0 → detector calibrado. Flag dispara + ME muito "
             "negativo → detector rebaixa demais. Flag nunca dispara → não consegue avaliar.")
    L.append("")
    L.append("| Flag | n_with | MAE_with | ME_with | n_without | MAE_without | ME_without | Diagnóstico |")
    L.append("|---|---:|---:|---:|---:|---:|---:|---|")
    for fk in _FLAG_KEYS:
        c = flag_error_corr.get(fk, {})
        n_w = c.get("n_with", 0)
        n_wo = c.get("n_without", 0)
        if n_w == 0:
            diag = "nunca dispara"
            mae_w = me_w = "-"
        else:
            mae_w = f"{c['mae_with']:.1f}"
            me_w = f"{c['me_with']:+.1f}"
            # Heurística: se ME_with é mais extremo que ME_without, sinal de detector rebaixando
            me_w_val = c["me_with"]
            me_wo_val = c.get("me_without") or 0
            if me_w_val < -50:
                diag = "rebaixa demais quando dispara"
            elif me_w_val > 50:
                diag = "infla quando dispara"
            elif abs(me_w_val) < 30:
                diag = "calibrado"
            else:
                diag = "moderado"
        mae_wo = f"{c['mae_without']:.1f}" if c.get("mae_without") is not None else "-"
        me_wo = f"{c['me_without']:+.1f}" if c.get("me_without") is not None else "-"
        L.append(f"| `{fk}` | {n_w} | {mae_w} | {me_w} | {n_wo} | {mae_wo} | {me_wo} | {diag} |")
    L.append("")

    # Tabela 6 — Top 10 erros residuais v3
    L.append("## Tabela 6 — Top 10 erros residuais v3 (|erro| > 80) — pra inspeção")
    L.append("")
    L.append("| ID | Fonte | Gab | v3 | Erro |")
    L.append("|---|---|---:|---:|---:|")
    for e in m_v3["top10_errors"]:
        L.append(f"| `{e['id']}` | {e['fonte']} | {e['gab_total']} | "
                 f"{e['redato_total']} | {e['erro']:+d} |")
    L.append("")

    # Critérios de sucesso (README_AB_TEST.md + 4ª categoria "falha estrutural")
    L.append("## Critérios de sucesso")
    L.append("")
    w40 = m_v3["within_40_total"]
    me_baixas_v3 = m_v3["by_band"].get("≤ 400", {}).get("me_total", 0)
    me_altas_v3 = m_v3["by_band"].get("≥ 800", {}).get("me_total", 0)
    me_medias_v3 = m_v3["by_band"].get("401-799", {}).get("me_total", 0)

    me_baixas_v2 = m_v2["by_band"].get("≤ 400", {}).get("me_total", 0)
    me_altas_v2 = m_v2["by_band"].get("≥ 800", {}).get("me_total", 0)

    # Falha estrutural: < 35% E/OU mesmo viés direcional que v2
    # v2 tinha: ME baixas positivo (inflate) + ME altas negativo (deflate)
    same_dir_baixas = (me_baixas_v2 > 0 and me_baixas_v3 > 0)
    same_dir_altas = (me_altas_v2 < 0 and me_altas_v3 < 0)
    same_direction_bias = same_dir_baixas and same_dir_altas
    falha_estrutural = (w40 < 0.35) or same_direction_bias

    parcial = (not falha_estrutural) and w40 >= 0.40 and abs(me_baixas_v3) < 60 and abs(me_altas_v3) < 80
    aceitavel = w40 >= 0.55 and all(abs(x) < 50 for x in (me_baixas_v3, me_medias_v3, me_altas_v3))
    pleno = w40 >= 0.70 and all(abs(x) < 30 for x in (me_baixas_v3, me_medias_v3, me_altas_v3))

    L.append(f"- **Falha estrutural** (±40 < 35% OU mesmo viés direcional da v2): "
             f"{'❌ DETECTADA' if falha_estrutural else '✅ não detectada'}")
    if same_direction_bias and w40 >= 0.35:
        L.append(f"  - ⚠ Mesmo viés direcional que v2: baixas v2={me_baixas_v2:+.0f} → "
                 f"v3={me_baixas_v3:+.0f}; altas v2={me_altas_v2:+.0f} → v3={me_altas_v3:+.0f}")
        L.append(f"  - Pipeline pode não estar absorvendo a rubrica nova; ver Tabela 5b")
    L.append(f"- **Parcial mínimo** (±40 ≥ 40%, |ME baixas| < 60, |ME altas| < 80): "
             f"{'✅ atingido' if parcial else '❌ não atingido'}")
    L.append(f"- **Aceitável** (±40 ≥ 55%, |ME| < 50 todas faixas): "
             f"{'✅ atingido' if aceitavel else '❌ não atingido'}")
    L.append(f"- **Pleno** (±40 ≥ 70%, |ME| < 30 todas faixas): "
             f"{'✅ atingido' if pleno else '❌ não atingido'}")
    L.append("")

    # Decisão
    L.append("## Decisão")
    L.append("")
    if falha_estrutural:
        L.append("→ **FALHA ESTRUTURAL — investigar pipeline antes de iterar v3.1.** "
                 "Sinais: pipeline não absorvendo a rubrica nova, LLM ignorando "
                 "instruções de gradação holística, ou ruído sistemático no gabarito. "
                 "Possíveis investigações: comparar audit_prose v3 com regras da "
                 "rubrica em redações específicas; checar se schema do tool_use "
                 "está restringindo demais; rodar 1-2 redações com Opus em vez de Sonnet "
                 "pra isolar capacidade-do-modelo vs rubrica.")
    elif aceitavel:
        L.append("→ **Consolidar v3 como nova baseline.** Ajustar system prompt para "
                 "reduzir erro residual; considerar fine-tuning leve com 38 comentários "
                 "INEP como few-shot examples.")
    elif parcial:
        L.append("→ **Iteração v3.1 cirúrgica.** v3 está no caminho certo — o viés "
                 "reduziu mas não atingiu critério aceitável. Identificar competências "
                 "específicas com erro residual (Tabela 2) e ajustar pontualmente.")
    else:
        L.append("→ **Caso intermediário (entre falha estrutural e parcial).** "
                 "Avaliar Tabela 5b (calibração dos detectores) antes de decidir.")
    L.append("")

    return "\n".join(L)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--v2", type=Path, required=True)
    parser.add_argument("--v3", type=Path, required=True)
    parser.add_argument("--out", type=Path,
                        default=Path("scripts/validation/results/REPORT_v2_vs_v3.md"))
    args = parser.parse_args()

    rec_v2 = load_jsonl(args.v2)
    rec_v3 = load_jsonl(args.v3)
    print(f"v2: {len(rec_v2)} registros")
    print(f"v3: {len(rec_v3)} registros")

    m_v2 = compute_metrics(rec_v2)
    m_v3 = compute_metrics(rec_v3)
    flag_dist = compute_flag_distribution(rec_v3)
    flag_error_corr = compute_flag_error_correlation(rec_v3)

    report = render_report(m_v2, m_v3, flag_dist, flag_error_corr,
                            str(args.v2), str(args.v3))
    args.out.write_text(report, encoding="utf-8")
    print(f"\nRelatório salvo em {args.out}")
    print()
    # Print headline
    print(f"v2 ±40 total: {m_v2['within_40_total']*100:.1f}%  →  "
          f"v3 ±40 total: {m_v3['within_40_total']*100:.1f}%  "
          f"(Δ {(m_v3['within_40_total']-m_v2['within_40_total'])*100:+.1f} pts)")
    print(f"v2 MAE total: {m_v2['mae_total']:.1f}  →  "
          f"v3 MAE total: {m_v3['mae_total']:.1f}  "
          f"(Δ {m_v3['mae_total']-m_v2['mae_total']:+.1f})")
    print(f"v2 ME total:  {m_v2['me_total']:+.1f}  →  "
          f"v3 ME total:  {m_v3['me_total']:+.1f}")


if __name__ == "__main__":
    main()
