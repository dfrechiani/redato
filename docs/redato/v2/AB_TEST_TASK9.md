# Tarefa 9 · Plano de testes A/B — Repetition Flag

> Companion document to `IMPLEMENTATION_GUIDE_NEXT.md` Tarefa 9.
> Define metodologia experimental para validar se o pré-flag mecânico de repetição lexical melhora teste_04 (`c4_mechanical_cohesion`) sem regredir os 7 canários estáveis.

## Objetivo experimental

**H0:** o repetition addendum não muda o comportamento da Redato.

**H1:** o repetition addendum melhora a avaliação de C3 em textos com repetição lexical, sem alterar a avaliação dos demais textos.

## Desenho

### Tipo: A/B controlado within-subjects

Cada canário é avaliado **duas vezes**: uma com flag (B), uma sem (A). Como o canário é o mesmo texto, a única variável que muda é a presença do addendum. Isso elimina variância entre textos como confundidor.

### Tamanho de amostra

Para reduzir variância da LLM, **cada canário roda N=5 vezes em cada condição**. Total: 11 canários × 2 condições × 5 runs = **110 chamadas** por experimento.

Custo estimado: 110 × ~$0.05 (Sonnet 4.6 com cache) ≈ **$5,50 por rodada**.

### Pareamento

Todas as runs usam:
- Mesmo modelo (`claude-sonnet-4-6` como referência; o código já usa o que estiver em `REDATO_CLAUDE_MODEL`)
- Mesma versão da rubrica (atual)
- Mesma temperatura (a usada em produção, geralmente 0.0 ou 0.2)
- Sem ensemble (`REDATO_ENSEMBLE` desabilitado — ensemble é variável separada, não condição)

**Único delta entre A e B:** variável de ambiente `REDATO_REPETITION_FLAG` (0 ou 1).

## Métricas

### Primárias (decisão de ship)

1. **STRICT pass rate em `c4_mechanical_cohesion`**
   - Esperado em A: 0/5 ou 1/5
   - Alvo em B: ≥ 4/5 (passa pelo menos 80%)

2. **STRICT pass rate nos 7 canários estáveis**
   - Esperado em A: 5/5 cada
   - Alvo em B: 5/5 cada (sem regressão)

3. **MAE de C3 contra gabarito (todos os 11 canários)**
   - MAE em B ≤ MAE em A (não pode piorar globalmente)

### Secundárias (diagnóstico)

4. **MAE de C4** — esperado: melhorar (repetição agora marcada explicitamente)
5. **Distribuição de `c3_audit.progressivas`** — esperamos shift `false → true` apenas onde apropriado
6. **Custo de tokens** — addendum injeta ~150 tokens, impacto deve ser < 5%

### Anti-métricas (sinais de regressão)

7. **C3 inflado em canários sem repetição** — se B sobe C3 onde C3 era corretamente baixo, é regressão
8. **C4 reduzido** — se Redato relaxa em C4 ("já está sinalizado"), perdemos ali

## Estrutura de arquivos

```
backend/notamil-backend/
├── scripts/
│   └── ab_tests/
│       ├── run_ab_test_repetition.py        ← orquestra experimento
│       ├── analyze_ab_results.py            ← análise estatística + decisão
│       └── results/
│           └── repetition_ab_YYYYMMDD.json  ← gerado
```

## `run_ab_test_repetition.py`

```python
#!/usr/bin/env python3
"""
A/B test: repetition addendum vs baseline.
Roda cada canário N vezes em cada condição, salva resultados brutos.
"""
import os
import json
import time
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

import yaml

# Importa o pipeline real do dev_offline (mesma função que produção usa)
from redato_backend.dev_offline import _claude_grade_essay, _load_rubric

CANARIOS_PATH = Path("docs/redato/v2/canarios.yaml")
RESULTS_DIR = Path("scripts/ab_tests/results")
RUNS_PER_CONDITION = 5
MAX_PARALLEL = 3  # respeita rate limit


def load_canaries():
    with open(CANARIOS_PATH) as f:
        data = yaml.safe_load(f)
    return data["canarios"], data.get("metadata", {})


def run_single(canary: dict, condition: str, run_idx: int):
    """Roda um canário em uma condição."""
    # Seta env var para a condição
    if condition == "B":
        os.environ["REDATO_REPETITION_FLAG"] = "1"
    else:
        os.environ["REDATO_REPETITION_FLAG"] = "0"

    start = time.time()
    try:
        # _claude_grade_essay assina com (essay_text, theme, theme_keywords, ...)
        # ajustar conforme assinatura real após inspecionar dev_offline.py
        result = _claude_grade_essay(
            essay_text=canary["essay"],
            activity_id=canary.get("activity_id", "RJ3_OF09_MF"),
            # ... outros params conforme assinatura real
        )
        latency_ms = (time.time() - start) * 1000
        return {
            "canary_id": canary["id"],
            "condition": condition,
            "run_idx": run_idx,
            "ok": True,
            "result": result,
            "latency_ms": latency_ms,
        }
    except Exception as e:
        return {
            "canary_id": canary["id"],
            "condition": condition,
            "run_idx": run_idx,
            "ok": False,
            "error": str(e),
        }


def main():
    canaries, metadata = load_canaries()
    print(f"Loaded {len(canaries)} canaries from v{metadata.get('version', '?')}")

    jobs = [
        (c, cond, idx)
        for c in canaries
        for cond in ["A", "B"]
        for idx in range(RUNS_PER_CONDITION)
    ]
    print(f"Running {len(jobs)} total runs ({len(canaries)} × 2 conditions × {RUNS_PER_CONDITION})")

    results = []
    with ThreadPoolExecutor(max_workers=MAX_PARALLEL) as executor:
        futures = {executor.submit(run_single, c, cond, idx): (c["id"], cond, idx)
                   for c, cond, idx in jobs}
        for i, future in enumerate(as_completed(futures), 1):
            r = future.result()
            results.append(r)
            cid, cond, idx = futures[future]
            mark = "✓" if r["ok"] else "✗"
            print(f"  [{i}/{len(jobs)}] {mark} {cid} cond={cond} run={idx}")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output = RESULTS_DIR / f"repetition_ab_{timestamp}.json"

    with open(output, "w") as f:
        json.dump({
            "experiment": "repetition_flag_ab",
            "timestamp": timestamp,
            "config": {
                "model": os.environ.get("REDATO_CLAUDE_MODEL", "claude-sonnet-4-6"),
                "runs_per_condition": RUNS_PER_CONDITION,
                "n_canaries": len(canaries),
            },
            "results": results,
        }, f, indent=2, ensure_ascii=False)

    print(f"\n  Saved to {output}")


if __name__ == "__main__":
    main()
```

## `analyze_ab_results.py`

```python
#!/usr/bin/env python3
"""
Análise estatística do A/B test. Decide ship vs revert via exit code.

Exit codes:
    0 = SHIP — todos os critérios atendidos
    1 = SHIP CAUTELOSO — primários OK mas alguma anti-métrica em risco
    2 = REVERT — falha algum critério primário
"""
import json
import sys
from pathlib import Path
from collections import defaultdict
from statistics import mean

import yaml

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


def passes_strict(result: dict, gabarito: dict, structural_checks: list) -> bool:
    """STRICT: cada competência ±40 do gabarito + structural checks passam."""
    for comp in ("c1", "c2", "c3", "c4", "c5"):
        diff = abs(result["notas"][comp] - gabarito[comp])
        if diff > 40:
            return False
    for check in structural_checks:
        kind = check["kind"]
        value = check["value"]
        if kind == "c1_desvios_gramaticais_count_min":
            count = result.get("c1_audit", {}).get("desvios_gramaticais_count", 0)
            if count < value:
                return False
        elif kind == "c1_nota_exact":
            if result["notas"]["c1"] != value:
                return False
        elif kind == "priority_1_target":
            priorizacao = result.get("priorizacao", [])
            if not priorizacao or priorizacao[0].get("target_competency") != value:
                return False
        # ... outros tipos conforme schema do canários.yaml
    return True


def passes_inep(result: dict, gabarito: dict) -> bool:
    """INEP: total ±40."""
    return abs(result["notas"]["total"] - gabarito["total"]) <= 40


def analyze(results_path: Path, canarios_path: Path):
    with open(results_path) as f:
        data = json.load(f)
    with open(canarios_path) as f:
        canarios_data = yaml.safe_load(f)

    canarios_by_id = {c["id"]: c for c in canarios_data["canarios"]}

    grouped = defaultdict(lambda: defaultdict(list))
    for r in data["results"]:
        if r["ok"]:
            grouped[r["canary_id"]][r["condition"]].append(r["result"])

    print("=" * 90)
    print(f"  A/B TEST RESULTS — {results_path.name}")
    print("=" * 90)

    rows = []
    for canary_id in sorted(grouped):
        canary = canarios_by_id[canary_id]
        gabarito = canary["gabarito"]
        checks = canary.get("structural_checks", [])
        a = grouped[canary_id]["A"]
        b = grouped[canary_id]["B"]

        if not a or not b:
            print(f"  ⚠ {canary_id}: faltam runs em A ou B (a={len(a)}, b={len(b)})")
            continue

        a_strict = sum(passes_strict(r, gabarito, checks) for r in a) / len(a)
        b_strict = sum(passes_strict(r, gabarito, checks) for r in b) / len(b)
        a_inep = sum(passes_inep(r, gabarito) for r in a) / len(a)
        b_inep = sum(passes_inep(r, gabarito) for r in b) / len(b)

        a_c3_mae = mean(abs(r["notas"]["c3"] - gabarito["c3"]) for r in a)
        b_c3_mae = mean(abs(r["notas"]["c3"] - gabarito["c3"]) for r in b)

        rows.append({
            "canary": canary_id,
            "a_strict": a_strict, "b_strict": b_strict,
            "delta_strict": b_strict - a_strict,
            "a_c3_mae": a_c3_mae, "b_c3_mae": b_c3_mae,
            "delta_c3_mae": b_c3_mae - a_c3_mae,
        })

    print(f"\n  {'Canário':<32} {'A_strict':>9} {'B_strict':>9} {'Δ':>7} {'A_C3_MAE':>9} {'B_C3_MAE':>9} {'Δ':>7}")
    print(f"  {'─'*92}")
    for r in rows:
        delta_strict = r["delta_strict"]
        delta_mae = r["delta_c3_mae"]
        marker = "✓" if delta_strict >= 0 and delta_mae <= 0 else "·"
        print(f"  {r['canary']:<32} {r['a_strict']:>9.2f} {r['b_strict']:>9.2f} "
              f"{delta_strict:>+7.2f} {r['a_c3_mae']:>9.1f} {r['b_c3_mae']:>9.1f} "
              f"{delta_mae:>+7.1f}  {marker}")

    print("\n" + "=" * 90)
    print("  DECISION ANALYSIS")
    print("=" * 90)

    target_row = next((r for r in rows if r["canary"] == TARGET), None)
    estaveis_rows = [r for r in rows if r["canary"] in ESTAVEIS]

    target_improved = bool(target_row and target_row["b_strict"] >= 0.8)
    print(f"\n  [1] {TARGET} STRICT: A={target_row['a_strict']:.2f} → "
          f"B={target_row['b_strict']:.2f}  "
          f"{'✓ ATINGIU 0.8' if target_improved else '✗ NÃO atingiu 0.8'}")

    regressions = [r for r in estaveis_rows if r["delta_strict"] < -0.2]
    no_regression = len(regressions) == 0
    print(f"  [2] Estáveis sem regressão: {'✓ SIM' if no_regression else '✗ NÃO'}")
    for r in regressions:
        print(f"      REGREDIU: {r['canary']} delta={r['delta_strict']:+.2f}")

    avg_delta_mae = mean(r["delta_c3_mae"] for r in rows)
    mae_improved = avg_delta_mae <= 0
    print(f"  [3] MAE C3 médio (todos): Δ={avg_delta_mae:+.2f}  "
          f"{'✓ MELHOROU' if mae_improved else '✗ PIOROU'}")

    print("\n" + "=" * 90)
    if target_improved and no_regression and mae_improved:
        print("  DECISÃO: ✓ SHIP — todos os critérios atendidos")
        sys.exit(0)
    elif target_improved and no_regression:
        print("  DECISÃO: ⚠ SHIP CAUTELOSO — primários OK, MAE não melhorou globalmente")
        print("           Recomenda-se segunda rodada antes de produção")
        sys.exit(1)
    else:
        print("  DECISÃO: ✗ REVERT — algum critério primário falhou")
        sys.exit(2)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: analyze_ab_results.py <results.json> <canarios.yaml>")
        sys.exit(99)
    analyze(Path(sys.argv[1]), Path(sys.argv[2]))
```

## Workflow recomendado

```bash
cd backend/notamil-backend

# 1. Garantir que detector e calibrador foram implementados (Tarefa 9)
python -m redato_backend.scripts.calibrate_repetition_threshold

# 2. Rodar baseline (só A) para confirmar estado atual sem regressão histórica
REDATO_REPETITION_FLAG=0 python -m redato_backend.scripts.run_calibration_eval

# 3. Rodar A/B completo
python scripts/ab_tests/run_ab_test_repetition.py
# saída: scripts/ab_tests/results/repetition_ab_20260424_153022.json

# 4. Analisar
python scripts/ab_tests/analyze_ab_results.py \
    scripts/ab_tests/results/repetition_ab_20260424_153022.json \
    docs/redato/v2/canarios.yaml

# Exit code: 0 = ship, 1 = ship cauteloso, 2 = revert
echo "Decision exit code: $?"
```

## Critérios de decisão

| Resultado | Decisão | Próximo passo |
|---|---|---|
| `c4_mechanical_cohesion` ≥ 4/5 STRICT, zero regressão, MAE C3 médio cai | **SHIP** | Merge para main, monitorar produção |
| Target ≥ 4/5, zero regressão, MAE não cai | **SHIP CAUTELOSO** | Segunda rodada antes de produção |
| Target melhora mas regrediu canário estável | **REVERT** | Investigar qual aspecto causou regressão |
| Target não atingiu 4/5 | **REVERT** | Hipótese do framing afirmativo é falsa, partir para Tarefa 10 |

## Limitações

1. **N=5 é estatisticamente fraco.** Ideal seria N=20+, mas custo cresce. Se houver dúvida em algum canário (resultado borderline), aumentar N só para esse canário.

2. **Calibration set tem viés de seleção.** Os 11 canários cobrem o espectro mas não são amostra aleatória da população real. Se A/B passar, ainda vale rodar contra ~50 redações reais antes do ship final.

3. **Variância da LLM não é controlável perfeitamente.** Mesmo `temperature=0.0` tem não-determinismo residual. N=5 mitiga.

4. **Mede impacto técnico, não pedagógico.** Se Redato sobe C3 indevidamente em algum caso, o aluno recebe feedback errado mesmo passando STRICT. Validação humana de 5-10 corrections completa o ciclo.

## Pós-ship: monitoramento contínuo

- **% de correções com addendum injetado** (esperado: 30-40% após calibração)
- **Distribuição de C3 com vs sem addendum** — shift muito grande indica calibração precisa ajuste
- **Concordância C3 entre Redato e revisão humana** — KPI mensal, idealmente > 85%

---

*Versão 1.1 · abril de 2026 (corrigida para Python no backend Redato)*
