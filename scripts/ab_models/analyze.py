"""Gera REPORT_AB_<timestamp>.md a partir dos 3 jsonl produzidos
pelo `run_ab.py`.

Lê:
  - scripts/ab_models/results/eval_prod_<ts>.jsonl
  - scripts/ab_models/results/eval_tuned_<ts>.jsonl
  - scripts/ab_models/results/eval_ft_<ts>.jsonl
  - backend/notamil-backend/scripts/validation/data/eval_gold_v1.jsonl

Produz:
  - scripts/ab_models/results/REPORT_AB_<ts>.md  (mesmo timestamp)

Estrutura do relatório:
  1. TL;DR — vencedor por ±40 global, recomendação MIGRAR/INVESTIGAR/NENHUM
  2. Tabela 1 globais (n_ok, ±40/60/80, MAE, ME, latency, custo)
  3. Tabela 2 ±40 por faixa de gabarito (≤400, 401-599, 600-799, 800-999, 1000)
  4. Tabela 3 MAE por competência (C1-C5)
  5. Tabela 4 viés ME por faixa
  6. Top 10 catastróficos por modelo (|erro| > 200)
  7. Erros de pipeline (max 10 por modelo)
  8. Decisão final com checklist

Uso:
    python scripts/ab_models/analyze.py --timestamp 20260429_143022
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional, Tuple


REPO = Path(__file__).resolve().parents[2]
EVAL_PATH = (
    REPO / "backend" / "notamil-backend"
    / "scripts" / "validation" / "data" / "eval_gold_v1.jsonl"
)
RESULTS_DIR = Path(__file__).resolve().parent / "results"

MODELOS = ["prod", "tuned", "ft"]
NOMES = {
    "prod":  "Claude prod (Sonnet 4.6 + v2)",
    "tuned": "Claude tuned (Opus 4.7 + fewshot INEP)",
    "ft":    "GPT-FT BTBOS5VF",
}


# ──────────────────────────────────────────────────────────────────────
# Loading
# ──────────────────────────────────────────────────────────────────────

def _carregar_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    out: List[Dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if not ln:
                continue
            try:
                out.append(json.loads(ln))
            except json.JSONDecodeError:
                continue
    return out


def _carregar_resultados(timestamp: str) -> Dict[str, List[Dict[str, Any]]]:
    """Lê os 3 jsonl. Modelos sem arquivo → lista vazia."""
    return {
        m: _carregar_jsonl(RESULTS_DIR / f"eval_{m}_{timestamp}.jsonl")
        for m in MODELOS
    }


# ──────────────────────────────────────────────────────────────────────
# Cálculo de métricas
# ──────────────────────────────────────────────────────────────────────

def _faixa_de(total: Optional[int]) -> str:
    """Faixa do gabarito INEP. Estratificação igual ao eval_gold_v1."""
    if total is None:
        return "?"
    if total <= 400:
        return "≤400"
    if total <= 599:
        return "401-599"
    if total <= 799:
        return "600-799"
    if total <= 999:
        return "800-999"
    return "1000"


FAIXAS = ["≤400", "401-599", "600-799", "800-999", "1000"]


def _erro(predito: int, gabarito: Optional[int]) -> Optional[int]:
    """Erro = predito - gabarito (sinal preserva direção do viés).
    Retorna None se gabarito ausente."""
    if gabarito is None:
        return None
    return predito - gabarito


def _calcular_metricas_globais(
    resultados: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Stats por modelo: n_ok, n_erro, ±40/60/80, MAE, ME, latency,
    custo total."""
    n_ok = 0
    n_erro_pipeline = 0
    n_40 = n_60 = n_80 = 0
    mae_vals: List[float] = []
    me_vals: List[float] = []
    lat_vals: List[float] = []
    custo_total = 0.0
    n_total = 0

    for r in resultados:
        n_total += 1
        if r.get("error"):
            n_erro_pipeline += 1
            continue
        notas = r.get("notas_geradas") or {}
        gab = r.get("gabarito") or {}
        pred = notas.get("total", 0)
        gold = gab.get("total")
        if gold is None:
            continue
        n_ok += 1
        diff = pred - gold
        absdiff = abs(diff)
        if absdiff <= 40:
            n_40 += 1
        if absdiff <= 60:
            n_60 += 1
        if absdiff <= 80:
            n_80 += 1
        mae_vals.append(absdiff)
        me_vals.append(diff)
        lat = r.get("latency_ms") or 0
        lat_vals.append(lat)
        custo_total += float(r.get("cost_usd") or 0)

    pct = lambda n: (100 * n / n_ok) if n_ok else 0.0
    return {
        "n_total": n_total,
        "n_ok": n_ok,
        "n_erro_pipeline": n_erro_pipeline,
        "pct_40": pct(n_40),
        "pct_60": pct(n_60),
        "pct_80": pct(n_80),
        "mae": mean(mae_vals) if mae_vals else 0.0,
        "me":  mean(me_vals)  if me_vals  else 0.0,
        "latency_med_seg": (mean(lat_vals) / 1000) if lat_vals else 0.0,
        "custo_total": custo_total,
        "custo_por_redacao": (custo_total / n_ok) if n_ok else 0.0,
    }


def _calcular_por_faixa(
    resultados: List[Dict[str, Any]],
) -> Dict[str, Dict[str, float]]:
    """Pra cada faixa: ±40%, ME (viés), n na faixa, MAE."""
    buckets: Dict[str, Dict[str, List[float]]] = {
        f: {"diff": [], "absdiff": [], "n_40": [], "n_total": []}
        for f in FAIXAS
    }
    for r in resultados:
        if r.get("error"):
            continue
        gab = r.get("gabarito") or {}
        gold = gab.get("total")
        if gold is None:
            continue
        notas = r.get("notas_geradas") or {}
        pred = notas.get("total", 0)
        diff = pred - gold
        faixa = _faixa_de(gold)
        if faixa not in buckets:
            continue
        buckets[faixa]["diff"].append(diff)
        buckets[faixa]["absdiff"].append(abs(diff))
        buckets[faixa]["n_40"].append(1.0 if abs(diff) <= 40 else 0.0)
        buckets[faixa]["n_total"].append(1.0)

    out: Dict[str, Dict[str, float]] = {}
    for f, b in buckets.items():
        n = int(sum(b["n_total"]))
        out[f] = {
            "n": n,
            "pct_40": (100 * sum(b["n_40"]) / n) if n else 0.0,
            "me": mean(b["diff"]) if b["diff"] else 0.0,
            "mae": mean(b["absdiff"]) if b["absdiff"] else 0.0,
        }
    return out


def _calcular_mae_por_competencia(
    resultados: List[Dict[str, Any]],
) -> Dict[str, float]:
    """MAE de cada C1-C5 separado. Útil pra ver se 1 competência
    específica tá puxando o MAE total."""
    buckets: Dict[str, List[float]] = {f"c{i}": [] for i in range(1, 6)}
    for r in resultados:
        if r.get("error"):
            continue
        gab = r.get("gabarito") or {}
        notas = r.get("notas_geradas") or {}
        for c in ("c1", "c2", "c3", "c4", "c5"):
            gold = gab.get(c)
            pred = notas.get(c)
            if gold is None or pred is None:
                continue
            buckets[c].append(abs(pred - gold))
    return {c: (mean(v) if v else 0.0) for c, v in buckets.items()}


def _top_catastroficos(
    resultados: List[Dict[str, Any]], k: int = 10,
) -> List[Tuple[Dict[str, Any], int]]:
    """Top k redações com |erro_total| > 200, ordenadas por |erro|."""
    cands: List[Tuple[Dict[str, Any], int]] = []
    for r in resultados:
        if r.get("error"):
            continue
        gab = r.get("gabarito") or {}
        notas = r.get("notas_geradas") or {}
        gold = gab.get("total")
        pred = notas.get("total")
        if gold is None or pred is None:
            continue
        diff = pred - gold
        if abs(diff) > 200:
            cands.append((r, diff))
    cands.sort(key=lambda x: -abs(x[1]))
    return cands[:k]


def _erros_pipeline(
    resultados: List[Dict[str, Any]], k: int = 10,
) -> List[Dict[str, Any]]:
    """Lista até k records com `error` setado."""
    return [r for r in resultados if r.get("error")][:k]


# ──────────────────────────────────────────────────────────────────────
# Decisão
# ──────────────────────────────────────────────────────────────────────

def _decidir(
    metricas: Dict[str, Dict[str, Any]],
    por_faixa: Dict[str, Dict[str, Dict[str, float]]],
) -> Tuple[str, str, List[str]]:
    """Decide MIGRAR / INVESTIGAR / NENHUM baseado em:
      ✓ Vencedor de ±40 deve superar prod em ≥5pp
      ✓ Viés ME na faixa baixa (≤400) deve ser <60 (regressão à média
        sob controle)
      ✓ Sem regressão grosseira (faixa 1000 ME muito negativo)

    Retorna: (recomendacao, vencedor, motivos)
    """
    motivos: List[str] = []

    pct_prod  = metricas["prod"]["pct_40"]
    pct_tuned = metricas["tuned"]["pct_40"]
    pct_ft    = metricas["ft"]["pct_40"]

    candidatos = sorted(
        [("prod", pct_prod), ("tuned", pct_tuned), ("ft", pct_ft)],
        key=lambda x: -x[1],
    )
    melhor_modelo, melhor_pct = candidatos[0]

    # Critério 1: ±40 vencedor não-prod com +5pp
    if melhor_modelo == "prod":
        motivos.append(
            f"prod ({pct_prod:.1f}%) já é o vencedor de ±40 — "
            "nenhum candidato supera baseline."
        )
        return "NENHUM", "prod", motivos

    delta_prod = melhor_pct - pct_prod
    if delta_prod < 5.0:
        motivos.append(
            f"vencedor {melhor_modelo} ({melhor_pct:.1f}%) supera prod "
            f"({pct_prod:.1f}%) por apenas {delta_prod:+.1f}pp — abaixo "
            f"do limiar de +5pp pra MIGRAR."
        )
        return "INVESTIGAR", melhor_modelo, motivos

    motivos.append(
        f"vencedor {melhor_modelo}: ±40 = {melhor_pct:.1f}% "
        f"(prod = {pct_prod:.1f}%, +{delta_prod:.1f}pp)."
    )

    # Critério 2: viés ME na faixa baixa < 60
    me_baixa = por_faixa[melhor_modelo].get("≤400", {}).get("me", 0)
    if abs(me_baixa) >= 60:
        motivos.append(
            f"viés ME na faixa ≤400 = {me_baixa:+.0f} (≥60 em |abs|) "
            f"— regressão à média alta. INVESTIGAR antes de migrar."
        )
        return "INVESTIGAR", melhor_modelo, motivos
    motivos.append(
        f"viés ≤400 = {me_baixa:+.0f} (sob controle, <|60|)."
    )

    # Critério 3: sem regressão grosseira em 1000
    me_1000 = por_faixa[melhor_modelo].get("1000", {}).get("me", 0)
    if me_1000 < -200:
        motivos.append(
            f"regressão grosseira em redações 1000: ME = {me_1000:+.0f} "
            f"(predição vai 200+ pts abaixo). INVESTIGAR."
        )
        return "INVESTIGAR", melhor_modelo, motivos

    motivos.append("sem regressão grosseira em 1000 (ME > -200).")
    motivos.append("Todos os critérios bateram — recomendação MIGRAR.")
    return "MIGRAR", melhor_modelo, motivos


# ──────────────────────────────────────────────────────────────────────
# Renderização do markdown
# ──────────────────────────────────────────────────────────────────────

def _f(v: float, digits: int = 1) -> str:
    return f"{v:.{digits}f}"


def _f_signed(v: float, digits: int = 1) -> str:
    return f"{v:+.{digits}f}"


def _render_relatorio(
    timestamp: str,
    metricas: Dict[str, Dict[str, Any]],
    por_faixa: Dict[str, Dict[str, Dict[str, float]]],
    mae_comp: Dict[str, Dict[str, float]],
    catastroficos: Dict[str, List[Tuple[Dict[str, Any], int]]],
    erros_pipe: Dict[str, List[Dict[str, Any]]],
    decisao: Tuple[str, str, List[str]],
) -> str:
    rec, vencedor, motivos = decisao
    nome_vencedor = NOMES.get(vencedor, vencedor)

    lines: List[str] = []
    lines.append(f"# REPORT A/B 3-vias — {timestamp}")
    lines.append("")
    lines.append(
        f"Eval set: `eval_gold_v1.jsonl` (200 redações AES-ENEM, "
        f"gabarito INEP)."
    )
    lines.append(
        f"Critério primário: % concordância **±40 pontos no total**."
    )
    lines.append("")

    # ── TL;DR ────────────────────────────────────────────────────
    lines.append("## TL;DR")
    lines.append("")
    lines.append(f"**Recomendação: {rec}**")
    lines.append("")
    lines.append(f"Vencedor por ±40 global: **{nome_vencedor}**")
    lines.append("")
    for m in motivos:
        lines.append(f"- {m}")
    lines.append("")

    # ── Tabela 1: globais ────────────────────────────────────────
    lines.append("## Tabela 1 — Métricas globais")
    lines.append("")
    lines.append(
        "| Modelo | n_ok | erros | ±40% | ±60% | ±80% | MAE | ME | "
        "latency | custo total | $/redação |"
    )
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for m in MODELOS:
        s = metricas[m]
        lines.append(
            f"| {NOMES[m]} | {s['n_ok']} | {s['n_erro_pipeline']} | "
            f"{_f(s['pct_40'])}% | {_f(s['pct_60'])}% | "
            f"{_f(s['pct_80'])}% | {_f(s['mae'], 0)} | "
            f"{_f_signed(s['me'], 0)} | "
            f"{_f(s['latency_med_seg'])}s | "
            f"${_f(s['custo_total'], 3)} | "
            f"${_f(s['custo_por_redacao'], 4)} |"
        )
    lines.append("")

    # ── Tabela 2: ±40 por faixa ──────────────────────────────────
    lines.append("## Tabela 2 — ±40% por faixa de gabarito")
    lines.append("")
    lines.append(
        "Estratificação do eval (igual a `eval_gold_v1.jsonl`): "
        "≤400 (n=30), 401-599 (n=50), 600-799 (n=60), 800-999 (n=40), "
        "1000 (n=20)."
    )
    lines.append("")
    lines.append(
        "| Faixa | "
        + " | ".join(NOMES[m] for m in MODELOS)
        + " |"
    )
    lines.append("|" + "---|" * (len(MODELOS) + 1))
    for f in FAIXAS:
        cells: List[str] = [f]
        for m in MODELOS:
            d = por_faixa[m].get(f, {})
            n = int(d.get("n", 0))
            pct = d.get("pct_40", 0)
            cells.append(f"{_f(pct)}% (n={n})")
        lines.append("| " + " | ".join(cells) + " |")
    lines.append("")

    # ── Tabela 3: MAE por competência ────────────────────────────
    lines.append("## Tabela 3 — MAE por competência (C1-C5)")
    lines.append("")
    lines.append(
        "MAE em pontos absolutos. Quanto menor melhor. ENEM: 0/40/80/"
        "120/160/200, então diferença de 40 = 1 nível na rubrica."
    )
    lines.append("")
    lines.append(
        "| Modelo | C1 | C2 | C3 | C4 | C5 |"
    )
    lines.append("|---|---|---|---|---|---|")
    for m in MODELOS:
        d = mae_comp[m]
        lines.append(
            f"| {NOMES[m]} | "
            + " | ".join(_f(d.get(f"c{i}", 0), 0) for i in range(1, 6))
            + " |"
        )
    lines.append("")

    # ── Tabela 4: viés ME por faixa ──────────────────────────────
    lines.append("## Tabela 4 — Viés ME por faixa (predito − gabarito)")
    lines.append("")
    lines.append(
        "ME = média do erro com sinal. ME positivo = modelo INFLA notas; "
        "ME negativo = modelo REBAIXA notas. Regressão à média típica: "
        "ME positivo em faixas baixas + ME negativo em faixas altas."
    )
    lines.append("")
    lines.append(
        "| Faixa | "
        + " | ".join(NOMES[m] for m in MODELOS)
        + " |"
    )
    lines.append("|" + "---|" * (len(MODELOS) + 1))
    for f in FAIXAS:
        cells = [f]
        for m in MODELOS:
            d = por_faixa[m].get(f, {})
            me = d.get("me", 0)
            cells.append(f"{me:+.0f}")
        lines.append("| " + " | ".join(cells) + " |")
    lines.append("")

    # ── Top catastróficos ────────────────────────────────────────
    lines.append("## Top 10 catastróficos por modelo (|erro| > 200)")
    lines.append("")
    for m in MODELOS:
        lines.append(f"### {NOMES[m]}")
        lines.append("")
        cats = catastroficos[m]
        if not cats:
            lines.append("_Nenhum caso com |erro| > 200._")
            lines.append("")
            continue
        lines.append("| ID | Faixa | Gabarito | Predito | Erro |")
        lines.append("|---|---|---|---|---|")
        for r, diff in cats:
            gab = (r.get("gabarito") or {}).get("total")
            pred = (r.get("notas_geradas") or {}).get("total")
            lines.append(
                f"| `{r['id']}` | {_faixa_de(gab)} | "
                f"{gab} | {pred} | {diff:+d} |"
            )
        lines.append("")

    # ── Erros de pipeline ────────────────────────────────────────
    qtd_erros = sum(metricas[m]["n_erro_pipeline"] for m in MODELOS)
    if qtd_erros > 0:
        lines.append("## Erros de pipeline (max 10 por modelo)")
        lines.append("")
        for m in MODELOS:
            errs = erros_pipe[m]
            if not errs:
                continue
            lines.append(
                f"### {NOMES[m]} — {metricas[m]['n_erro_pipeline']} erro(s)"
            )
            lines.append("")
            lines.append("| ID | Erro |")
            lines.append("|---|---|")
            for r in errs:
                lines.append(
                    f"| `{r.get('id')}` | "
                    f"{(r.get('error') or '')[:120]} |"
                )
            lines.append("")

    # ── Decisão final ────────────────────────────────────────────
    lines.append("## Decisão final")
    lines.append("")
    lines.append("**Critérios (todos devem bater pra MIGRAR):**")
    lines.append("")
    lines.append(
        "- [ ] Vencedor por ±40 global supera prod em ≥5pp"
    )
    lines.append(
        "- [ ] Viés ME na faixa ≤400 com módulo <60 "
        "(regressão à média sob controle)"
    )
    lines.append(
        "- [ ] Sem regressão grosseira na faixa 1000 (ME > -200)"
    )
    lines.append("")
    lines.append(f"**Recomendação: {rec}**")
    lines.append("")
    if rec == "MIGRAR":
        lines.append(
            f"Migrar OF14 do path atual para **{nome_vencedor}**. "
            f"Próximo passo: ajustar `_claude_grade_essay` (ou criar "
            f"branch dedicado pro tuned/FT) e atualizar CLAUDE.md."
        )
    elif rec == "INVESTIGAR":
        lines.append(
            f"Vencedor é {nome_vencedor}, mas pelo menos 1 critério "
            f"falhou. Investigar a causa antes de decidir migração — "
            f"priorizar análise dos motivos listados no TL;DR."
        )
    else:
        lines.append(
            "Manter prod (Sonnet 4.6 + v2). Nenhum candidato superou "
            "baseline. Se quiser tentar de novo, considerar tuning "
            "diferente (outro fewshot, outro paradigma, prompt v3 "
            "redesenhado, etc.)."
        )
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(
        f"_Gerado por `scripts/ab_models/analyze.py` — "
        f"timestamp `{timestamp}`._"
    )
    lines.append("")
    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────
# Entry
# ──────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Gera relatório markdown do A/B 3-vias"
    )
    parser.add_argument(
        "--timestamp",
        required=True,
        help="Timestamp do run (ex: 20260429_143022). Lê eval_*_<ts>."
        "jsonl e escreve REPORT_AB_<ts>.md em scripts/ab_models/results/.",
    )
    args = parser.parse_args()

    print(f"[analyze] timestamp = {args.timestamp}")
    res = _carregar_resultados(args.timestamp)
    for m in MODELOS:
        print(f"  {m}: {len(res[m])} records carregados")

    if all(len(v) == 0 for v in res.values()):
        raise SystemExit(
            f"[erro] nenhum jsonl encontrado pra timestamp "
            f"{args.timestamp}. Rodou o run_ab.py primeiro?"
        )

    metricas = {m: _calcular_metricas_globais(res[m]) for m in MODELOS}
    por_faixa = {m: _calcular_por_faixa(res[m]) for m in MODELOS}
    mae_comp = {m: _calcular_mae_por_competencia(res[m]) for m in MODELOS}
    catastroficos = {m: _top_catastroficos(res[m]) for m in MODELOS}
    erros_pipe = {m: _erros_pipeline(res[m]) for m in MODELOS}
    decisao = _decidir(metricas, por_faixa)

    md = _render_relatorio(
        timestamp=args.timestamp,
        metricas=metricas,
        por_faixa=por_faixa,
        mae_comp=mae_comp,
        catastroficos=catastroficos,
        erros_pipe=erros_pipe,
        decisao=decisao,
    )

    out_path = RESULTS_DIR / f"REPORT_AB_{args.timestamp}.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(md, encoding="utf-8")
    print(f"[analyze] ✓ relatório escrito em:")
    print(f"    {out_path.relative_to(REPO)}")
    print()
    print(f"Recomendação: {decisao[0]} (vencedor: {NOMES.get(decisao[1], decisao[1])})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
