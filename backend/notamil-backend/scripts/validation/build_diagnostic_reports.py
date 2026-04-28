#!/usr/bin/env python3
"""Gera 10 markdowns por redação + SUMMARY.md cruzando audit / derivação /
nota final / gabarito. Sem chamadas API.
"""
from __future__ import annotations

import json
from pathlib import Path

DIAG_RESULTS = Path("scripts/validation/results/eval_gold_diagnostic_run.jsonl")
CORPUS = Path("/Users/danielfrechiani/Desktop/redato_hash/ingest/data/final/unified.jsonl")
OUT_DIR = Path("scripts/validation/diagnostic")
OUT_DIR.mkdir(parents=True, exist_ok=True)


def load_corpus_for_ids(ids: set) -> dict:
    out = {}
    with CORPUS.open(encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if r["id"] in ids:
                out[r["id"]] = r
                if len(out) == len(ids):
                    break
    return out


def slug(rid: str) -> str:
    return rid.replace("/", "_")


def fmt_audit_summary(audit: dict | None, comp: str) -> str:
    """Resumo legível do audit de 1 competência."""
    if not isinstance(audit, dict):
        return "(sem audit)"
    nota = audit.get("nota")
    lines = [f"- nota emitida pelo LLM: **{nota}**"]
    # Top fields per competency
    for k, v in audit.items():
        if k in ("nota",):
            continue
        if isinstance(v, dict):
            sub = ", ".join(f"{kk}={vv}" for kk, vv in v.items()
                            if not isinstance(vv, (dict, list)))
            lines.append(f"- {k}: {{{sub}}}")
        elif isinstance(v, list):
            if v and isinstance(v[0], dict):
                lines.append(f"- {k}: list[{len(v)}]")
            else:
                lines.append(f"- {k}: {v}")
        else:
            lines.append(f"- {k}: {v}")
    return "\n".join(lines)


def render_essay_md(rec_corpus: dict, rec_diag: dict) -> str:
    rid = rec_corpus["id"]
    fonte = rec_corpus.get("fonte", "?")
    tema = (rec_corpus.get("tema") or {}).get("titulo") or "(sem tema)"
    texto = (rec_corpus.get("redacao") or {}).get("texto_original") or ""
    # Trunca redação muito longa pra markdown legível
    if len(texto) > 3000:
        texto_show = texto[:3000] + f"\n\n[...truncado, {len(texto)-3000} chars a mais]"
    else:
        texto_show = texto

    gab = rec_diag.get("gabarito") or {}
    audit_full = rec_diag.get("redato_audit") or {}
    derivacao = rec_diag.get("redato_derivacao") or {}
    final = rec_diag.get("redato_final") or {}

    delta = (final.get("total", 0) - (gab.get("total") or 0)) if gab.get("total") else 0
    direcao = "INFLAÇÃO" if delta > 0 else ("DEFLAÇÃO" if delta < 0 else "match")

    lines: list[str] = []
    lines.append(f"# Diagnóstico — {rid}\n")
    lines.append(f"**Fonte:** `{fonte}`\n")
    lines.append(f"**Tema:** {tema}\n")
    lines.append(f"**Tamanho do texto:** {len(texto)} chars · "
                 f"**Latência Redato:** {rec_diag.get('latency_ms', 0)/1000:.1f}s\n")
    lines.append(f"**Padrão:** {direcao} · Δ = `{delta:+d}` (Redato {final.get('total', '?')} vs Gabarito {gab.get('total', '?')})\n")
    lines.append("---\n")

    # Notas comparadas
    lines.append("## Notas comparadas\n")
    lines.append("| | C1 | C2 | C3 | C4 | C5 | TOTAL |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|")
    g = [str(gab.get(k, "-")) for k in ("c1","c2","c3","c4","c5")]
    d = [str(derivacao.get(k, "-")) for k in ("c1","c2","c3","c4","c5")]
    f = [str(final.get(k, "-")) for k in ("c1","c2","c3","c4","c5")]
    lines.append(f"| **Gabarito INEP** | {' | '.join(g)} | **{gab.get('total','-')}** |")
    lines.append(f"| Redato derivacao (Python) | {' | '.join(d)} | {derivacao.get('total','-')} |")
    lines.append(f"| Redato final (após two-stage) | {' | '.join(f)} | **{final.get('total','-')}** |")
    lines.append("")

    # Drift por competência
    lines.append("## Drift por competência (Redato_final − Gabarito)\n")
    lines.append("| | C1 | C2 | C3 | C4 | C5 |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    drifts = []
    for k in ("c1","c2","c3","c4","c5"):
        gv = gab.get(k); fv = final.get(k)
        if gv is None or fv is None:
            drifts.append("-")
        else:
            d_ = fv - gv
            drifts.append(f"{d_:+d}")
    lines.append(f"| Drift | {' | '.join(drifts)} |")
    lines.append("")

    # Audit por competência (resumo)
    lines.append("## Audit do LLM (resumido por competência)\n")
    for k in ("c1","c2","c3","c4","c5"):
        lines.append(f"### {k.upper()} — gabarito {gab.get(k, '?')} · derivação {derivacao.get(k, '?')} · final {final.get(k, '?')}\n")
        lines.append(fmt_audit_summary(audit_full.get(f"{k}_audit"), k))
        lines.append("")

    # Texto da redação
    lines.append("## Redação (texto_original)\n")
    lines.append("```")
    lines.append(texto_show)
    lines.append("```")

    return "\n".join(lines)


def render_summary(corpus_by_id: dict, diag_recs: list[dict]) -> str:
    """Tabela cruzada: ID, gab, derivacao, final, drift, padrão."""
    lines: list[str] = []
    lines.append("# SUMMARY — diagnóstico de viés (10 redações extremas)\n")
    lines.append("Re-run das 10 redações com viés mais grave do eval_gold (5 inflacionadas + 5 deflacionadas).\n")
    lines.append("Schema novo captura: `gabarito` (INEP), `redato_audit` (LLM raw), "
                 "`redato_derivacao` (`_derive_cN_nota` rodado isolado), "
                 "`redato_final` (após two-stage default).\n")
    lines.append("---\n")

    # Tabela 1: notas finais
    lines.append("## Tabela 1 — Notas: gabarito vs derivação vs final\n")
    lines.append("| ID | Gab tot | Deriv tot | Final tot | Δ tot | Padrão |")
    lines.append("|---|---:|---:|---:|---:|---|")
    for d in diag_recs:
        gab = d["gabarito"]; deriv = d["redato_derivacao"]; final = d["redato_final"]
        delta = final["total"] - gab["total"]
        pad = "infl" if delta > 0 else ("defl" if delta < 0 else "match")
        lines.append(f"| `{d['id']}` | {gab['total']} | {deriv['total']} | "
                     f"{final['total']} | {delta:+d} | {pad} |")
    lines.append("")

    # Tabela 2: drift por competência
    lines.append("## Tabela 2 — Drift por competência (final − gabarito)\n")
    lines.append("| ID | C1 | C2 | C3 | C4 | C5 | Total |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|")
    for d in diag_recs:
        gab = d["gabarito"]; final = d["redato_final"]
        cells = []
        for k in ("c1","c2","c3","c4","c5"):
            gv = gab.get(k); fv = final.get(k)
            cells.append(f"{(fv-gv):+d}" if gv is not None and fv is not None else "-")
        cells.append(f"{(final['total']-gab['total']):+d}")
        lines.append(f"| `{d['id'][:40]}` | {' | '.join(cells)} |")
    lines.append("")

    # Tabela 3: deriv vs final (detecta se two-stage está distorcendo)
    lines.append("## Tabela 3 — Derivação Python vs Final (two-stage post-processing impacto)\n")
    lines.append("Se derivação == final, two-stage não mudou nada (esperado com REDATO_TWO_STAGE=1, que sobrescreve audit.nota com a derivação). Se há diferença, é sinal de bug.\n")
    lines.append("| ID | C1 | C2 | C3 | C4 | C5 | Total |")
    lines.append("|---|:---:|:---:|:---:|:---:|:---:|:---:|")
    for d in diag_recs:
        deriv = d["redato_derivacao"]; final = d["redato_final"]
        cells = []
        for k in ("c1","c2","c3","c4","c5","total"):
            dv, fv = deriv.get(k), final.get(k)
            if dv == fv:
                cells.append("=")
            else:
                cells.append(f"{dv}→{fv}")
        lines.append(f"| `{d['id'][:40]}` | {' | '.join(cells)} |")
    lines.append("")

    # Tabela 4: contagem de erros graves identificados pelo LLM (C1) vs gabarito C1
    lines.append("## Tabela 4 — C1: contagem de desvios identificados pelo LLM vs nota INEP\n")
    lines.append("`desvios_gramaticais_count` é o que o LLM contou. Em escala INEP, ~10+ desvios = nota 0/40, ~7-9 = 80, ~4-6 = 120, ~2-3 = 160, ≤1 = 200.\n")
    lines.append("| ID | LLM desvios | LLM nota | Deriv C1 | Final C1 | Gab C1 |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    for d in diag_recs:
        c1 = (d["redato_audit"] or {}).get("c1_audit") or {}
        desvios_n = c1.get("desvios_gramaticais_count")
        llm_nota = c1.get("nota")
        deriv = d["redato_derivacao"]["c1"]
        final = d["redato_final"]["c1"]
        gab = d["gabarito"]["c1"]
        lines.append(f"| `{d['id'][:40]}` | {desvios_n} | {llm_nota} | {deriv} | {final} | {gab} |")
    lines.append("")

    # Tabela 5: C5 elementos
    lines.append("## Tabela 5 — C5: elementos da proposta identificados pelo LLM vs nota INEP\n")
    lines.append("INEP: 5 elementos = 200, 4 = 160, 3 = 120, 2 = 80, 1 = 40, 0 = 0.\n")
    lines.append("| ID | LLM elements_count | LLM nota | Deriv C5 | Final C5 | Gab C5 |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    for d in diag_recs:
        c5 = (d["redato_audit"] or {}).get("c5_audit") or {}
        # Conta elementos com present=true
        elements = c5.get("elements_present") or []
        if isinstance(elements, list):
            n_present = sum(1 for e in elements
                            if isinstance(e, dict) and e.get("present") is True)
        else:
            n_present = "?"
        llm_nota = c5.get("nota")
        deriv = d["redato_derivacao"]["c5"]
        final = d["redato_final"]["c5"]
        gab = d["gabarito"]["c5"]
        lines.append(f"| `{d['id'][:40]}` | {n_present} | {llm_nota} | {deriv} | {final} | {gab} |")
    lines.append("")

    # Síntese
    lines.append("## Padrão observado\n")

    # Calcula stats
    inflados = [d for d in diag_recs if d["redato_final"]["total"] > d["gabarito"]["total"]]
    deflados = [d for d in diag_recs if d["redato_final"]["total"] < d["gabarito"]["total"]]

    def avg_drift(group, comp):
        vals = []
        for d in group:
            g, f = d["gabarito"].get(comp), d["redato_final"].get(comp)
            if g is not None and f is not None:
                vals.append(f - g)
        return sum(vals) / max(len(vals), 1)

    def avg_deriv_diff(group, comp):
        """Diferença derivação vs final."""
        vals = []
        for d in group:
            de = d["redato_derivacao"].get(comp)
            fi = d["redato_final"].get(comp)
            if de is not None and fi is not None:
                vals.append(fi - de)
        return sum(vals) / max(len(vals), 1)

    lines.append(f"### Inflacionados (n={len(inflados)})\n")
    lines.append("Drift médio por competência:")
    for k in ("c1","c2","c3","c4","c5"):
        lines.append(f"- {k.upper()}: {avg_drift(inflados, k):+.1f}")
    lines.append("")

    lines.append(f"### Deflacionados (n={len(deflados)})\n")
    lines.append("Drift médio por competência:")
    for k in ("c1","c2","c3","c4","c5"):
        lines.append(f"- {k.upper()}: {avg_drift(deflados, k):+.1f}")
    lines.append("")

    # Quantos casos a derivação é diferente do final
    n_diff = sum(1 for d in diag_recs
                 if d["redato_derivacao"]["total"] != d["redato_final"]["total"])
    lines.append(f"### Two-stage post-processing\n")
    lines.append(f"Casos onde derivação ≠ final: {n_diff}/10. "
                 f"Com REDATO_TWO_STAGE=1 (default), o esperado é "
                 f"derivação == final em 100% dos casos.\n")

    lines.append("## Próximos passos sugeridos\n")
    lines.append("Inspecionar individualmente os markdowns. Buscar especificamente:")
    lines.append("")
    lines.append("- **Inflados:** o LLM contou poucos desvios em C1 mas o gabarito INEP marca C1=40? "
                 "Sinal: LLM sub-detecta erros em redações fracas.")
    lines.append("- **Deflados:** o LLM contou muitos desvios em C1 mas o gabarito INEP marca C1=200? "
                 "Sinal: LLM super-detecta erros em redações boas (criticismo).")
    lines.append("- **C5:** LLM contou poucos elementos da proposta em redações 1000? "
                 "Sinal: regras de strict-quoting do C5 punem demais.")
    lines.append("- **C2:** tema vazio (INEP) ou tema simples mas LLM marca tangenciamento? "
                 "Sinal: viés do detector de tangenciamento.")
    return "\n".join(lines)


def main() -> None:
    diag_recs = [json.loads(l) for l in DIAG_RESULTS.read_text().splitlines() if l.strip()]
    ids = {r["id"] for r in diag_recs}
    corpus_by_id = load_corpus_for_ids(ids)

    # Ordena pra ter inflados primeiro depois deflados
    diag_recs.sort(key=lambda r: -(r["redato_final"]["total"] - r["gabarito"]["total"]))

    for d in diag_recs:
        rec_c = corpus_by_id[d["id"]]
        md = render_essay_md(rec_c, d)
        out_path = OUT_DIR / f"{slug(d['id'])}.md"
        out_path.write_text(md, encoding="utf-8")
        print(f"  ✓ {out_path}")

    summary = render_summary(corpus_by_id, diag_recs)
    summary_path = OUT_DIR / "SUMMARY.md"
    summary_path.write_text(summary, encoding="utf-8")
    print(f"\n  ✓ {summary_path}")


if __name__ == "__main__":
    main()
