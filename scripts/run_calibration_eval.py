#!/usr/bin/env python
"""Calibration regression eval for the Redato grader.

Loads docs/redato/calibration_set/canarios.yaml, grades every canário against
the live Claude pipeline, validates notas (±40 tolerance) + per-canário
structural checks, reports pass/fail, and exits 1 when >= 2 canários fail.

Usage (from repo root):

    cd backend/notamil-backend
    pip install pyyaml  # only extra dep besides requirements-dev.txt
    REDATO_DEV_OFFLINE=1 python ../../scripts/run_calibration_eval.py

Options:
    --only <canario_id>     run a single canário
    --baseline              write docs/redato/calibration_set/baseline_YYYY-MM-DD.json
    --compare <path>        compare against a prior baseline JSON
    --no-fail               always exit 0 (useful while iterating on prompts)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend" / "notamil-backend"
DEFAULT_CANARIOS_PATH = REPO_ROOT / "docs" / "redato" / "v2" / "canarios.yaml"

# Make ``redato_backend`` importable before we set up the offline patches.
sys.path.insert(0, str(BACKEND_DIR))
os.environ.setdefault("REDATO_DEV_OFFLINE", "1")
os.environ.setdefault("REDATO_DEV_PERSIST", "0")  # keep eval deterministic

from redato_backend.dev_offline import apply_patches  # noqa: E402

apply_patches()

from redato_backend.dev_offline import _claude_grade_essay  # noqa: E402


TOLERANCE = 40
DEPLOY_BLOCK_THRESHOLD = 2


# ---------------------------------------------------------------------------
# YAML loading (we support either canarios at the top level or under a key).
# ---------------------------------------------------------------------------

def _load_canarios(path: Path) -> List[Dict[str, Any]]:
    try:
        import yaml
    except ImportError:
        print("ERROR: pyyaml is required. `pip install pyyaml`.")
        sys.exit(2)
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if isinstance(raw, list):
        return [c for c in raw if isinstance(c, dict) and "id" in c]
    if isinstance(raw, dict) and "canarios" in raw:
        return raw["canarios"]
    raise ValueError(f"Unexpected structure in {path}: {type(raw)}")


# ---------------------------------------------------------------------------
# Structural-check dispatcher.
#
# Each check declared in the YAML has a ``kind`` and optional ``value``. This
# dispatcher knows how to run each kind against the ``tool_args`` payload
# returned by ``_claude_grade_essay``.
# ---------------------------------------------------------------------------

def _nota(tool_args: Dict[str, Any], key: str) -> int:
    return int(((tool_args.get(f"{key}_audit") or {}).get("nota")) or 0)


def _run_structural_check(tool_args: Dict[str, Any], check: Dict[str, Any]) -> tuple[bool, str]:
    """Structural check dispatcher for v2 canários (PDF-based rubric)."""
    kind = check.get("kind")
    expected = check.get("value")
    audits = {key: tool_args.get(f"{key}_audit") or {} for key in ("c1", "c2", "c3", "c4", "c5")}

    # --- Per-competency max/min/exact ------------------------------------
    for comp in ("c1", "c2", "c3", "c4", "c5"):
        if kind == f"{comp}_nota_max":
            got = _nota(tool_args, comp)
            return (got <= expected, f"{comp}.nota={got} (esperado <= {expected})")
        if kind == f"{comp}_nota_min":
            got = _nota(tool_args, comp)
            return (got >= expected, f"{comp}.nota={got} (esperado >= {expected})")
        if kind == f"{comp}_nota_exact":
            got = _nota(tool_args, comp)
            return (got == expected, f"{comp}.nota={got} (esperado == {expected})")

    # --- C1 (v2) ---------------------------------------------------------
    if kind == "c1_desvios_gramaticais_count_min":
        got = int(audits["c1"].get("desvios_gramaticais_count") or 0)
        return (got >= expected, f"desvios_gramaticais_count={got} (esperado >= {expected})")
    if kind == "c1_applies_nota":
        tc = audits["c1"].get("threshold_check") or {}
        got = bool(tc.get(f"applies_nota_{expected}"))
        return (got, f"applies_nota_{expected}={got} (esperado True)")

    # --- C2 (v2) ---------------------------------------------------------
    if kind == "c2_has_false_attribution_ref":
        refs = audits["c2"].get("repertoire_references") or []
        got = any(isinstance(r, dict) and r.get("legitimacy") == "false_attribution" for r in refs)
        return (got == expected, f"has_false_attribution_ref={got} (esperado {expected})")
    if kind == "c2_has_not_legitimated_ref":
        refs = audits["c2"].get("repertoire_references") or []
        got = any(isinstance(r, dict) and r.get("legitimacy") == "not_legitimated" for r in refs)
        return (got == expected, f"has_not_legitimated_ref={got} (esperado {expected})")
    if kind == "c2_tangenciamento_detected":
        got = bool(audits["c2"].get("tangenciamento_detected"))
        return (got == expected, f"tangenciamento_detected={got} (esperado {expected})")
    if kind == "c2_fuga_total_detected":
        got = bool(audits["c2"].get("fuga_total_detected"))
        return (got == expected, f"fuga_total_detected={got} (esperado {expected})")
    if kind == "c2_repertoire_count_min":
        refs = audits["c2"].get("repertoire_references") or []
        return (len(refs) >= expected, f"repertoire count={len(refs)} (esperado >= {expected})")
    if kind == "c2_has_reference_in_d1":
        got = bool(audits["c2"].get("has_reference_in_d1"))
        return (got == expected, f"has_reference_in_d1={got} (esperado {expected})")
    if kind == "c2_has_reference_in_d2":
        got = bool(audits["c2"].get("has_reference_in_d2"))
        return (got == expected, f"has_reference_in_d2={got} (esperado {expected})")
    if kind == "c2_copia_motivadores_sem_aspas":
        got = bool(audits["c2"].get("copia_motivadores_sem_aspas"))
        return (got == expected, f"copia_motivadores_sem_aspas={got} (esperado {expected})")

    # --- C3 (v2) ---------------------------------------------------------
    if kind == "c3_has_explicit_thesis":
        got = bool(audits["c3"].get("has_explicit_thesis"))
        return (got == expected, f"has_explicit_thesis={got} (esperado {expected})")
    if kind == "c3_argumentos_contraditorios":
        got = bool(audits["c3"].get("argumentos_contraditorios"))
        return (got == expected, f"argumentos_contraditorios={got} (esperado {expected})")

    # --- C4 (v2) ---------------------------------------------------------
    if kind == "c4_most_used_connector_min_count":
        got = int(audits["c4"].get("most_used_connector_count") or 0)
        return (got >= expected, f"most_used_connector_count={got} (esperado >= {expected})")
    if kind == "c4_has_mechanical_repetition":
        got = bool(audits["c4"].get("has_mechanical_repetition"))
        return (got == expected, f"has_mechanical_repetition={got} (esperado {expected})")

    # --- C5 (v2) ---------------------------------------------------------
    if kind == "c5_elements_count_exact":
        got = int(audits["c5"].get("elements_count") or 0)
        return (got == expected, f"elements_count={got} (esperado == {expected})")
    if kind == "c5_elements_count_min":
        got = int(audits["c5"].get("elements_count") or 0)
        return (got >= expected, f"elements_count={got} (esperado >= {expected})")
    if kind == "c5_elements_count_max":
        got = int(audits["c5"].get("elements_count") or 0)
        return (got <= expected, f"elements_count={got} (esperado <= {expected})")
    if kind == "c5_proposta_articulada":
        got = bool(audits["c5"].get("proposta_articulada_ao_tema"))
        return (got == expected, f"proposta_articulada_ao_tema={got} (esperado {expected})")

    # --- Priorization ----------------------------------------------------
    if kind == "priority_1_target":
        got = ((tool_args.get("priorization") or {}).get("priority_1") or {}).get(
            "target_competency"
        )
        return (got == expected, f"priority_1.target={got!r} (esperado {expected!r})")

    # --- Totals / controle -----------------------------------------------
    if kind == "total_min":
        total = sum(_nota(tool_args, k) for k in ("c1", "c2", "c3", "c4", "c5"))
        return (total >= expected, f"total={total} (esperado >= {expected})")
    if kind == "max_one_competency_below_200":
        below = [k for k in ("c1", "c2", "c3", "c4", "c5") if _nota(tool_args, k) < 200]
        return (len(below) <= 1, f"abaixo de 200: {below} (máx 1)")

    # --- Preanulation ----------------------------------------------------
    if kind == "preanulation_should_annul":
        got = bool((tool_args.get("preanulation_checks") or {}).get("should_annul"))
        return (got == expected, f"should_annul={got} (esperado {expected})")

    return (True, f"(check não reconhecido: {kind})")


# ---------------------------------------------------------------------------
# Per-canário runner
# ---------------------------------------------------------------------------

@dataclass
class CanarioResult:
    id: str
    passed: bool
    # "INEP pass": todas as 5 competências dentro de ±40 do gabarito. Critério
    # oficial do ENEM — 2 corretores podem diferir em até 1 nível antes de
    # disparar 3º corretor. Se a redação está dentro disso, o aluno não é
    # prejudicado face ao corretor humano.
    inep_passed: bool = False
    notas: Dict[str, int] = field(default_factory=dict)
    gabarito: Dict[str, int] = field(default_factory=dict)
    drift: Dict[str, int] = field(default_factory=dict)
    structural_fails: List[str] = field(default_factory=list)
    elapsed_s: float = 0.0
    error: Optional[str] = None


def _grade_canario(canario: Dict[str, Any]) -> CanarioResult:
    t0 = time.time()
    result = CanarioResult(id=canario["id"], passed=False, gabarito=canario.get("gabarito") or {})
    try:
        tool_args = _claude_grade_essay({
            "request_id": f"eval-{canario['id']}-{int(t0)}",
            "user_id": "eval-bot",
            "content": canario["essay"],
            "theme": "Impactos das redes sociais na saúde mental dos jovens",
        })
    except Exception as exc:  # noqa: BLE001
        result.error = f"{type(exc).__name__}: {exc}"
        result.elapsed_s = time.time() - t0
        return result

    notas = {key: _nota(tool_args, key) for key in ("c1", "c2", "c3", "c4", "c5")}
    total = sum(notas.values())
    result.notas = dict(notas, total=total)

    # Numerical drift vs gabarito (per-competency).
    # A canário can declare ``tolerance_override.per_competency`` to widen (or
    # effectively disable) the drift check for ambiguous cases like annulment.
    gabarito = canario.get("gabarito") or {}
    override = (canario.get("tolerance_override") or {}).get("per_competency")
    tolerance = override if isinstance(override, int) else TOLERANCE
    tol_fail = False
    for key in ("c1", "c2", "c3", "c4", "c5"):
        expected = gabarito.get(key)
        got = notas[key]
        drift = got - (expected or 0)
        result.drift[key] = drift
        if expected is not None and abs(drift) > tolerance:
            tol_fail = True
            result.structural_fails.append(
                f"numeric:{key}: got {got}, expected {expected} (drift {drift:+d})"
            )

    # Structural checks.
    for check in canario.get("structural_checks") or []:
        ok, reason = _run_structural_check(tool_args, check)
        if not ok:
            result.structural_fails.append(f"structural:{check.get('kind')}: {reason}")

    result.passed = not tol_fail and not result.structural_fails
    # INEP criterion: apenas tolerance numérica. Ignora structural_checks, que
    # são nossas checagens internas de calibração (detecção de viés), não
    # critérios oficiais do ENEM.
    numeric_fails = [f for f in result.structural_fails if f.startswith("numeric:")]
    result.inep_passed = not numeric_fails
    result.elapsed_s = time.time() - t0
    return result


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def _format_table(results: List[CanarioResult]) -> str:
    lines = []
    header = (
        f"{'ID':<28} {'NOTA':>5}/{'GAB':<5}  "
        f"{'C1':>4} {'C2':>4} {'C3':>4} {'C4':>4} {'C5':>4}  "
        f"{'INEP':>5}  {'STRICT':>6}  {'TEMPO':>6}"
    )
    lines.append(header)
    lines.append("-" * len(header))
    for r in results:
        total = r.notas.get("total", 0)
        gab = r.gabarito.get("total", 0)
        strict = "OK" if r.passed else ("ERR" if r.error else "FAIL")
        inep = "OK" if r.inep_passed else ("ERR" if r.error else "FAIL")
        drift_cols = [f"{r.drift.get(k, 0):+d}" for k in ("c1", "c2", "c3", "c4", "c5")]
        lines.append(
            f"{r.id:<28} {total:>5}/{gab:<5}  "
            f"{drift_cols[0]:>4} {drift_cols[1]:>4} {drift_cols[2]:>4} "
            f"{drift_cols[3]:>4} {drift_cols[4]:>4}  "
            f"{inep:>5}  {strict:>6}  {r.elapsed_s:5.1f}s"
        )
        for fail in r.structural_fails[:5]:
            lines.append(f"    · {fail}")
        if r.error:
            lines.append(f"    · error: {r.error}")
    return "\n".join(lines)


def _to_json(results: List[CanarioResult]) -> Dict[str, Any]:
    return {
        "timestamp": datetime.now().isoformat(),
        "results": [
            {
                "id": r.id,
                "passed": r.passed,
                "inep_passed": r.inep_passed,
                "notas": r.notas,
                "gabarito": r.gabarito,
                "drift": r.drift,
                "structural_fails": r.structural_fails,
                "elapsed_s": round(r.elapsed_s, 2),
                "error": r.error,
            }
            for r in results
        ],
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", help="Run only the canário with this id")
    parser.add_argument("--baseline", action="store_true", help="Save results as baseline_YYYY-MM-DD.json")
    parser.add_argument("--compare", help="Compare against a prior baseline JSON")
    parser.add_argument("--no-fail", action="store_true", help="Always exit 0")
    parser.add_argument("--parallel", type=int, default=4, help="Max concurrent canários (default 4)")
    parser.add_argument(
        "--canarios",
        help="Path to canarios.yaml (default docs/redato/v2/canarios.yaml). "
        "Use docs/redato/test_set/redacoes_teste_v2.yaml for the test set.",
    )
    args = parser.parse_args()

    canarios_path = Path(args.canarios) if args.canarios else DEFAULT_CANARIOS_PATH
    if not canarios_path.is_absolute():
        canarios_path = (Path.cwd() / canarios_path).resolve()
    if not canarios_path.exists():
        print(f"Canarios file not found: {canarios_path}")
        return 2

    baselines_dir = canarios_path.parent

    canarios = _load_canarios(canarios_path)
    if args.only:
        canarios = [c for c in canarios if c["id"] == args.only]
        if not canarios:
            print(f"No canário found with id={args.only}")
            return 2

    if not os.getenv("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY not set (in .env or env). Cannot run real grading.")
        return 2

    print(f"Running {len(canarios)} canário(s) (parallel={args.parallel})...\n")

    results: List[CanarioResult] = []
    with ThreadPoolExecutor(max_workers=max(1, args.parallel)) as executor:
        futures = {executor.submit(_grade_canario, c): c["id"] for c in canarios}
        for fut in as_completed(futures):
            results.append(fut.result())
    results.sort(key=lambda r: r.id)

    print(_format_table(results))
    strict_fails = [r for r in results if not r.passed]
    inep_fails = [r for r in results if not r.inep_passed]
    inep_pass = len(results) - len(inep_fails)
    strict_pass = len(results) - len(strict_fails)
    print()
    print(
        f"Resultado: INEP {inep_pass}/{len(results)} "
        f"(todas as competências dentro de ±40 — critério oficial ENEM) | "
        f"STRICT {strict_pass}/{len(results)} "
        f"(INEP + structural checks internos)"
    )

    if args.baseline:
        baselines_dir.mkdir(parents=True, exist_ok=True)
        out_path = baselines_dir / f"baseline_{datetime.now().strftime('%Y-%m-%d')}.json"
        out_path.write_text(json.dumps(_to_json(results), indent=2, ensure_ascii=False), encoding="utf-8")
        try:
            rel = out_path.relative_to(REPO_ROOT)
            print(f"\nBaseline salvo em: {rel}")
        except ValueError:
            print(f"\nBaseline salvo em: {out_path}")

    if args.compare:
        _report_compare(Path(args.compare), results)

    # Deploy block uses INEP criterion (numeric tolerance only) — structural
    # checks are internal diagnostics, not production gates.
    if inep_fails and not args.no_fail and len(inep_fails) >= DEPLOY_BLOCK_THRESHOLD:
        print(
            f"\nDEPLOY BLOCKED: {len(inep_fails)} canários falharam no critério INEP "
            f"(threshold={DEPLOY_BLOCK_THRESHOLD})."
        )
        return 1

    return 0


def _report_compare(baseline_path: Path, current: List[CanarioResult]) -> None:
    try:
        data = json.loads(baseline_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        print(f"Falha ao ler baseline: {exc}")
        return
    base_by_id = {r["id"]: r for r in data.get("results") or []}
    print("\nDelta vs baseline:")
    for r in current:
        b = base_by_id.get(r.id)
        if not b:
            print(f"  {r.id}: sem dado na baseline")
            continue
        for key in ("c1", "c2", "c3", "c4", "c5"):
            bn = (b.get("notas") or {}).get(key)
            cn = r.notas.get(key)
            if bn is None or cn is None:
                continue
            delta = cn - bn
            if delta != 0:
                print(f"  {r.id}.{key}: {bn} → {cn} ({delta:+d})")


if __name__ == "__main__":
    sys.exit(main())
