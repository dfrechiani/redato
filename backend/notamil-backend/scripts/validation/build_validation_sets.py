#!/usr/bin/env python3
"""
Etapa 1 — Constrói os 2 subsets de validação (gold e real-world) a partir
do corpus unificado de 18k redações ENEM.

Aplica filtros, estratifica por faixa de nota, salva JSONL + stats.

Uso (de backend/notamil-backend):
    python scripts/validation/build_validation_sets.py
"""
from __future__ import annotations

import argparse
import json
import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Path do corpus — plano dizia ~/Mesa/... mas o caminho real é ~/Desktop/...
DEFAULT_CORPUS = Path.home() / "Desktop/redato_hash/ingest/data/final/unified.jsonl"

OUT_DIR = Path(__file__).resolve().parent / "data"

GOLD_SOURCES = {"inep", "aes-enem"}
REALWORLD_SOURCES = {"brasil-escola", "uol-xml", "essay-br"}

# Estratificação por faixa de nota (Etapa 1, tabela do plano)
BANDS: List[Tuple[str, int, int, int]] = [
    ("200-399", 200, 399, 30),
    ("400-599", 400, 599, 50),
    ("600-799", 600, 799, 60),
    ("800-999", 800, 999, 40),
    ("1000",    1000, 1000, 20),
]

SUM_TOLERANCE = 5  # soma c1..c5 vs nota_global, ±5 pra arredondamento/scraping
MIN_TEXT_CHARS = 100

# Real-world: estratificação dupla (fonte × faixa). Targets calculados pra
# somar 200, com proporções por faixa: 15% / 25% / 30% / 20% / 10%.
# BE+UOL=67 cada; Essay-BR=66 (-1 na faixa 1000) → 67+67+66=200.
TARGETS_REALWORLD: Dict[str, Dict[str, int]] = {
    "brasil-escola": {"200-399": 10, "400-599": 17, "600-799": 20, "800-999": 13, "1000": 7},
    "uol-xml":       {"200-399": 10, "400-599": 17, "600-799": 20, "800-999": 13, "1000": 7},
    "essay-br":      {"200-399": 10, "400-599": 17, "600-799": 20, "800-999": 13, "1000": 6},
}


def passes_filters(rec: Dict[str, Any]) -> Tuple[bool, str]:
    """Retorna (ok, motivo_rejeicao_quando_nao_ok)."""
    redacao = rec.get("redacao") or {}
    texto = (redacao.get("texto_original") or "").strip()
    if len(texto) < MIN_TEXT_CHARS:
        return False, f"texto_original < {MIN_TEXT_CHARS} chars"

    notas = rec.get("notas_competencia") or {}
    needed = ("c1", "c2", "c3", "c4", "c5")
    for k in needed:
        v = notas.get(k)
        if not isinstance(v, (int, float)) or v is None:
            return False, f"notas_competencia.{k} ausente/null"

    nota_global = rec.get("nota_global")
    if not isinstance(nota_global, (int, float)) or nota_global is None:
        return False, "nota_global ausente/null"
    if nota_global <= 0:
        return False, "nota_global <= 0 (provável draft/anulada)"

    soma = sum(int(notas[k]) for k in needed)
    if abs(soma - int(nota_global)) > SUM_TOLERANCE:
        return False, f"soma comp. ({soma}) ≠ nota_global ({nota_global})"

    tema = rec.get("tema") or {}
    titulo = (tema.get("titulo") or "").strip()
    if not titulo:
        return False, "tema.titulo vazio"

    return True, ""


def load_corpus(path: Path) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"  WARN: linha inválida ignorada: {e}")
    return out


def select_stratified(
    candidates: List[Dict[str, Any]],
    rng: random.Random,
) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, int]]]:
    """Seleciona conforme BANDS. Retorna (selecionados, stats_por_faixa)."""
    pool_by_band: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for c in candidates:
        n = int(c["nota_global"])
        for band, lo, hi, _target in BANDS:
            if lo <= n <= hi:
                pool_by_band[band].append(c)
                break

    selected: List[Dict[str, Any]] = []
    stats: Dict[str, Dict[str, int]] = {}
    for band, _lo, _hi, target in BANDS:
        pool = pool_by_band[band]
        rng.shuffle(pool)
        chosen = pool[:target]
        selected.extend(chosen)
        stats[band] = {
            "target": target,
            "available": len(pool),
            "chosen": len(chosen),
            "deficit": max(0, target - len(pool)),
        }
    return selected, stats


def select_realworld_dual_strat(
    pool: List[Dict[str, Any]],
    rng: random.Random,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Estratificação dupla (fonte × faixa) com redistribuição entre fontes
    quando uma combinação (fonte, faixa) não tem candidatos suficientes.

    Algoritmo:
    1. Bucketiza pool por (fonte, faixa)
    2. Pra cada (fonte, faixa) com target definido, pega `target` redações
    3. Acumula deficits por faixa
    4. Redistribui deficit pegando sobras da mesma faixa de outras fontes
    """
    buckets: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    for r in pool:
        fonte = r.get("fonte") or "?"
        n = int(r["nota_global"])
        for band, lo, hi, _ in BANDS:
            if lo <= n <= hi:
                buckets[(fonte, band)].append(r)
                break

    # Embaralha cada bucket pra escolha aleatória reprodutível
    for k in buckets:
        rng.shuffle(buckets[k])

    # Estatísticas pré-seleção
    pre_strat: Dict[str, Dict[str, int]] = {}
    for fonte in TARGETS_REALWORLD:
        pre_strat[fonte] = {band: len(buckets[(fonte, band)])
                            for band, _, _, _ in BANDS}

    selected: List[Dict[str, Any]] = []
    redistributions: List[Dict[str, Any]] = []

    # Primeira passada: tenta atender cada (fonte, faixa) target
    deficits_per_band: Dict[str, int] = {band: 0 for band, _, _, _ in BANDS}
    chosen_per_combo: Dict[Tuple[str, str], int] = {}

    for fonte, band_targets in TARGETS_REALWORLD.items():
        for band, target in band_targets.items():
            pool_b = buckets[(fonte, band)]
            taken = pool_b[:target]
            selected.extend(taken)
            chosen_per_combo[(fonte, band)] = len(taken)
            deficit = target - len(taken)
            if deficit > 0:
                deficits_per_band[band] += deficit
                redistributions.append({
                    "type": "deficit_detected",
                    "fonte": fonte,
                    "band": band,
                    "target": target,
                    "available": len(pool_b),
                    "deficit": deficit,
                })
            # Remove os já escolhidos do bucket pra próxima passada
            buckets[(fonte, band)] = pool_b[target:]

    # Segunda passada: redistribui deficits dentro da mesma faixa
    for band, total_deficit in deficits_per_band.items():
        if total_deficit == 0:
            continue
        leftover: List[Dict[str, Any]] = []
        for fonte in TARGETS_REALWORLD:
            leftover.extend(buckets[(fonte, band)])
        rng.shuffle(leftover)
        compensation = leftover[:total_deficit]
        selected.extend(compensation)
        if compensation:
            from_breakdown = dict(Counter(c.get("fonte", "?") for c in compensation))
            redistributions.append({
                "type": "redistribution",
                "band": band,
                "deficit_to_fill": total_deficit,
                "filled": len(compensation),
                "still_missing": total_deficit - len(compensation),
                "from_fontes": from_breakdown,
            })
        elif total_deficit > 0:
            redistributions.append({
                "type": "unfilled",
                "band": band,
                "missing": total_deficit,
            })

    summary = {
        "pre_stratification_pool": pre_strat,
        "chosen_per_combo": {f"{f}|{b}": n for (f, b), n in chosen_per_combo.items()},
        "redistributions": redistributions,
        "final_total": len(selected),
        "final_by_fonte": dict(Counter(r.get("fonte", "?") for r in selected)),
        "final_by_band": _band_breakdown(selected),
    }
    return selected, summary


def _band_breakdown(records: List[Dict[str, Any]]) -> Dict[str, int]:
    out = {band: 0 for band, _, _, _ in BANDS}
    for r in records:
        n = int(r["nota_global"])
        for band, lo, hi, _ in BANDS:
            if lo <= n <= hi:
                out[band] += 1
                break
    return out


def fonte_breakdown(records: List[Dict[str, Any]]) -> Dict[str, int]:
    return dict(Counter(r.get("fonte", "?") for r in records))


def write_jsonl(path: Path, records: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    if not args.corpus.exists():
        print(f"ERRO: corpus não encontrado em {args.corpus}")
        raise SystemExit(2)

    print(f"Lendo {args.corpus}...")
    corpus = load_corpus(args.corpus)
    print(f"  total: {len(corpus)} redações\n")

    # Aplica filtros
    filter_reasons: Counter = Counter()
    survivors: List[Dict[str, Any]] = []
    inep_excluded_count = 0
    for r in corpus:
        ok, reason = passes_filters(r)
        if ok:
            survivors.append(r)
        else:
            filter_reasons[reason] += 1
            # Conta INEP especificamente — todas falham por tema vazio (ausência
            # genuína no scraping; não é bug). Documentado no stats.json.
            if r.get("fonte") == "inep":
                inep_excluded_count += 1

    print("Filtragem:")
    print(f"  passaram: {len(survivors)} ({len(survivors)/len(corpus)*100:.1f}%)")
    rejected = sum(filter_reasons.values())
    print(f"  rejeitadas: {rejected}")
    for reason, n in filter_reasons.most_common():
        print(f"    - {reason}: {n}")
    print()

    # Separa por bucket de fonte
    gold_pool = [r for r in survivors if r.get("fonte") in GOLD_SOURCES]
    realworld_pool = [r for r in survivors if r.get("fonte") in REALWORLD_SOURCES]
    other = [r for r in survivors if r.get("fonte") not in GOLD_SOURCES | REALWORLD_SOURCES]

    print(f"Gold pool (INEP + AES-ENEM): {len(gold_pool)}")
    print(f"Real-world pool (Brasil-Escola + UOL-XML + Essay-BR): {len(realworld_pool)}")
    if other:
        print(f"  AVISO: {len(other)} redações de fonte desconhecida ignoradas:",
              dict(Counter(r.get("fonte", "?") for r in other)))
    print()

    # Estratifica
    rng = random.Random(args.seed)
    gold_set, gold_stats = select_stratified(gold_pool, rng)
    # Real-world usa estratificação dupla (fonte × faixa) com redistribuição.
    realworld_set, realworld_dual_stats = select_realworld_dual_strat(realworld_pool, rng)

    # Sanity: sem overlap
    gold_ids = {r["id"] for r in gold_set}
    rw_ids = {r["id"] for r in realworld_set}
    overlap = gold_ids & rw_ids
    if overlap:
        print(f"  ERRO: overlap entre gold e real-world ({len(overlap)} IDs)")
        raise SystemExit(2)

    # Saída
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    gold_path = OUT_DIR / "eval_gold_v1.jsonl"
    rw_path = OUT_DIR / "eval_realworld_v1.jsonl"
    write_jsonl(gold_path, gold_set)
    write_jsonl(rw_path, realworld_set)

    # Stats
    stats_payload = {
        "seed": args.seed,
        "corpus_total": len(corpus),
        "after_filters": len(survivors),
        "filter_rejections": dict(filter_reasons),
        "excluded_inep": {
            "count": inep_excluded_count,
            "reason": (
                "Todas as 47 redações INEP têm tema.titulo vazio no corpus "
                "(ausência genuína no scraping; cartilhas INEP têm tema na "
                "introdução do texto, não como campo separado). Filtro mantido "
                "estrito porque tema vazio polui avaliação de C2. Gold set é "
                "AES-ENEM (que inclui gradesThousand + PROPOR2024 + JBCS2025 — "
                "datasets acadêmicos com gabarito INEP-equivalente)."
            ),
        },
        "gold": {
            "pool_size": len(gold_pool),
            "selected": len(gold_set),
            "by_band": gold_stats,
            "by_fonte": fonte_breakdown(gold_set),
            "stratification": "single (band only)",
        },
        "realworld": {
            "pool_size": len(realworld_pool),
            "selected": len(realworld_set),
            "by_fonte": realworld_dual_stats["final_by_fonte"],
            "by_band": realworld_dual_stats["final_by_band"],
            "stratification": "dual (fonte × band)",
            "targets": TARGETS_REALWORLD,
            "pre_stratification_pool": realworld_dual_stats["pre_stratification_pool"],
            "chosen_per_combo": realworld_dual_stats["chosen_per_combo"],
            "redistributions": realworld_dual_stats["redistributions"],
        },
    }
    stats_path = OUT_DIR / "validation_sets_stats.json"
    stats_path.write_text(json.dumps(stats_payload, indent=2, ensure_ascii=False))

    # Print resumo
    print("=" * 78)
    print("  GOLD set (INEP + AES-ENEM)")
    print("=" * 78)
    print(f"  Pool: {len(gold_pool)} · Selecionados: {len(gold_set)}")
    print(f"  {'Faixa':<10} {'Target':>7} {'Disponível':>11} {'Escolhidos':>11} {'Déficit':>9}")
    for band, st in gold_stats.items():
        deficit_mark = "  ⚠" if st["deficit"] > 0 else ""
        print(f"  {band:<10} {st['target']:>7} {st['available']:>11} {st['chosen']:>11} {st['deficit']:>9}{deficit_mark}")
    print(f"  Por fonte: {fonte_breakdown(gold_set)}\n")

    print("=" * 78)
    print("  REAL-WORLD set (estratificação dupla fonte × faixa)")
    print("=" * 78)
    print(f"  Pool: {len(realworld_pool)} · Selecionados: {len(realworld_set)}\n")

    # Matriz target × disponível × escolhido por (fonte, faixa)
    print(f"  {'Fonte':<15} {'Faixa':<10} {'Target':>7} {'Pool':>6} {'Tomado':>7}")
    for fonte, band_targets in TARGETS_REALWORLD.items():
        for band, target in band_targets.items():
            pool_size = realworld_dual_stats["pre_stratification_pool"][fonte][band]
            chosen = realworld_dual_stats["chosen_per_combo"].get(f"{fonte}|{band}", 0)
            mark = "  ⚠" if chosen < target else ""
            print(f"  {fonte:<15} {band:<10} {target:>7} {pool_size:>6} {chosen:>7}{mark}")

    redistribs = realworld_dual_stats["redistributions"]
    if redistribs:
        print(f"\n  Redistribuições:")
        for r in redistribs:
            if r["type"] == "deficit_detected":
                print(f"    DEFICIT  {r['fonte']:<15} {r['band']:<10} "
                      f"target={r['target']} disp={r['available']} → falta {r['deficit']}")
            elif r["type"] == "redistribution":
                print(f"    REDIST.  faixa {r['band']:<10} preencheu {r['filled']}/{r['deficit_to_fill']}, "
                      f"fontes={r['from_fontes']}, "
                      f"ainda missing={r['still_missing']}")
            elif r["type"] == "unfilled":
                print(f"    UNFILL.  faixa {r['band']:<10} ainda faltam {r['missing']}")

    print(f"\n  Final por fonte: {realworld_dual_stats['final_by_fonte']}")
    print(f"  Final por faixa: {realworld_dual_stats['final_by_band']}\n")

    print(f"Gold     → {gold_path}")
    print(f"Realworld→ {rw_path}")
    print(f"Stats    → {stats_path}")


if __name__ == "__main__":
    main()
