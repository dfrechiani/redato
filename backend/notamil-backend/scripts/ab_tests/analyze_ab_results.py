#!/usr/bin/env python3
"""
Análise estatística do A/B test do repetition flag.

Exit codes:
    0 = SHIP — todos os critérios primários atendidos
    1 = SHIP CAUTELOSO — primários OK mas alguma anti-métrica em risco
    2 = REVERT — falha algum critério primário
    99 = uso incorreto

Uso:
    python scripts/ab_tests/analyze_ab_results.py <results.json> <canarios.yaml>
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List

ESTAVEIS = {
    "control_nota_1000",
    "c1_frequent_diverse_errors",
    "c2_false_repertoire",
    "c5_three_elements",
    "c5_two_elements_only",
    "c2_tangenciamento",
    "c2_heavy_copy",
}
TARGET = "c4_mechanical_cohesion"


def passes_inep(notas: Dict[str, int], gabarito: Dict[str, int]) -> bool:
    """INEP: cada competência ±40 do gabarito (critério oficial ENEM)."""
    for comp in ("c1", "c2", "c3", "c4", "c5"):
        if abs(notas.get(comp, 0) - gabarito.get(comp, 0)) > 40:
            return False
    return True


def passes_strict(
    result: Dict[str, Any],
    gabarito: Dict[str, int],
    structural_checks: List[Dict[str, Any]],
) -> bool:
    """STRICT: INEP + structural_checks declarados no canário."""
    notas = result["notas"]
    if not passes_inep(notas, gabarito):
        return False

    tool_args = result.get("tool_args") or {}
    for check in structural_checks:
        kind = check.get("kind")
        value = check.get("value")
        if kind == "c1_desvios_gramaticais_count_min":
            count = (tool_args.get("c1_audit") or {}).get("desvios_gramaticais_count", 0)
            if count < value:
                return False
        elif kind == "c1_nota_exact":
            if notas.get("c1") != value:
                return False
        elif kind == "c2_nota_max":
            if notas.get("c2", 200) > value:
                return False
        elif kind == "c2_tangenciamento_detected":
            tang = (tool_args.get("c2_audit") or {}).get("tangenciamento_detected")
            if bool(tang) != bool(value):
                return False
        elif kind == "c5_elements_count_exact":
            els = (tool_args.get("c5_audit") or {}).get("elements_present") or []
            if isinstance(els, list):
                count = sum(1 for e in els if isinstance(e, dict) and e.get("present"))
                if count != value:
                    return False
        elif kind == "priority_1_target":
            prior = tool_args.get("priorizacao") or []
            if not prior or prior[0].get("target_competency") != value:
                return False
        elif kind == "preanulation_should_annul":
            pre = tool_args.get("preanulation_checks") or {}
            if bool(pre.get("should_annul")) != bool(value):
                return False
        # Outros tipos: ignora silenciosamente para não falhar checks novos.
    return True


def analyze(results_path: Path, canarios_path: Path) -> int:
    import yaml

    data = json.loads(results_path.read_text(encoding="utf-8"))
    canarios_data = yaml.safe_load(canarios_path.read_text(encoding="utf-8"))
    canarios = (
        canarios_data.get("canarios", canarios_data)
        if isinstance(canarios_data, dict)
        else canarios_data
    )
    canarios_by_id = {c["id"]: c for c in canarios}

    grouped: Dict[str, Dict[str, List[Dict[str, Any]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for r in data["results"]:
        if r.get("ok"):
            grouped[r["canary_id"]][r["condition"]].append(r)

    print("=" * 92)
    print(f"  A/B TEST RESULTS — {results_path.name}")
    print("=" * 92)

    rows: List[Dict[str, Any]] = []
    for canary_id in sorted(grouped):
        canary = canarios_by_id.get(canary_id)
        if not canary:
            continue
        gabarito = canary.get("gabarito") or {}
        checks = canary.get("structural_checks") or []
        a = grouped[canary_id]["A"]
        b = grouped[canary_id]["B"]
        if not a or not b:
            print(f"  ⚠ {canary_id}: faltam runs (A={len(a)}, B={len(b)})")
            continue

        a_strict = sum(passes_strict(r, gabarito, checks) for r in a) / len(a)
        b_strict = sum(passes_strict(r, gabarito, checks) for r in b) / len(b)
        a_inep = sum(passes_inep(r["notas"], gabarito) for r in a) / len(a)
        b_inep = sum(passes_inep(r["notas"], gabarito) for r in b) / len(b)

        a_c3_mae = mean(abs(r["notas"]["c3"] - gabarito.get("c3", 0)) for r in a)
        b_c3_mae = mean(abs(r["notas"]["c3"] - gabarito.get("c3", 0)) for r in b)
        a_c4_mae = mean(abs(r["notas"]["c4"] - gabarito.get("c4", 0)) for r in a)
        b_c4_mae = mean(abs(r["notas"]["c4"] - gabarito.get("c4", 0)) for r in b)

        rows.append({
            "canary": canary_id,
            "a_strict": a_strict,
            "b_strict": b_strict,
            "delta_strict": b_strict - a_strict,
            "a_inep": a_inep,
            "b_inep": b_inep,
            "a_c3_mae": a_c3_mae,
            "b_c3_mae": b_c3_mae,
            "delta_c3_mae": b_c3_mae - a_c3_mae,
            "a_c4_mae": a_c4_mae,
            "b_c4_mae": b_c4_mae,
            "delta_c4_mae": b_c4_mae - a_c4_mae,
        })

    print()
    print(f"  {'Canário':<35} {'A_str':>6} {'B_str':>6} {'Δ':>6}  "
          f"{'A_C3':>6} {'B_C3':>6} {'Δ_C3':>6}  "
          f"{'A_C4':>6} {'B_C4':>6} {'Δ_C4':>6}")
    print("  " + "─" * 100)
    for r in rows:
        marker = "✓" if r["delta_strict"] >= 0 and r["delta_c3_mae"] <= 0 else "·"
        print(
            f"  {r['canary']:<35} "
            f"{r['a_strict']:>6.2f} {r['b_strict']:>6.2f} {r['delta_strict']:>+6.2f}  "
            f"{r['a_c3_mae']:>6.1f} {r['b_c3_mae']:>6.1f} {r['delta_c3_mae']:>+6.1f}  "
            f"{r['a_c4_mae']:>6.1f} {r['b_c4_mae']:>6.1f} {r['delta_c4_mae']:>+6.1f}  {marker}"
        )

    print("\n" + "=" * 92)
    print("  DECISION ANALYSIS")
    print("=" * 92)

    target_row = next((r for r in rows if r["canary"] == TARGET), None)
    estaveis_rows = [r for r in rows if r["canary"] in ESTAVEIS]

    if target_row is None:
        print(f"\n  ✗ Canário alvo '{TARGET}' não tem runs válidos. Não dá pra decidir.")
        return 2

    target_improved = target_row["b_strict"] >= 0.8
    print(
        f"\n  [1] {TARGET} STRICT: A={target_row['a_strict']:.2f} → "
        f"B={target_row['b_strict']:.2f}  "
        f"{'✓ ATINGIU 0.8' if target_improved else '✗ NÃO atingiu 0.8'}"
    )

    regressions = [r for r in estaveis_rows if r["delta_strict"] < -0.2]
    no_regression = len(regressions) == 0
    print(f"  [2] Estáveis sem regressão: {'✓ SIM' if no_regression else '✗ NÃO'}")
    for r in regressions:
        print(f"      REGREDIU: {r['canary']} delta={r['delta_strict']:+.2f}")

    avg_delta_c3_mae = mean(r["delta_c3_mae"] for r in rows) if rows else 0.0
    avg_delta_c4_mae = mean(r["delta_c4_mae"] for r in rows) if rows else 0.0
    mae_improved = avg_delta_c3_mae <= 0
    print(
        f"  [3] MAE C3 médio: Δ={avg_delta_c3_mae:+.2f}  "
        f"{'✓ MELHOROU' if mae_improved else '✗ PIOROU'}"
    )
    print(
        f"  [4] MAE C4 médio: Δ={avg_delta_c4_mae:+.2f}  (diagnóstico)"
    )

    print("\n" + "=" * 92)
    if target_improved and no_regression and mae_improved:
        print("  DECISÃO: ✓ SHIP — todos os critérios atendidos")
        return 0
    if target_improved and no_regression:
        print("  DECISÃO: ⚠ SHIP CAUTELOSO — primários OK, MAE C3 não melhorou globalmente")
        print("           Recomenda-se segunda rodada antes de produção")
        return 1
    print("  DECISÃO: ✗ REVERT — algum critério primário falhou")
    return 2


def main() -> int:
    if len(sys.argv) < 3:
        print("Uso: analyze_ab_results.py <results.json> <canarios.yaml>", file=sys.stderr)
        return 99
    return analyze(Path(sys.argv[1]), Path(sys.argv[2]))


if __name__ == "__main__":
    sys.exit(main())
