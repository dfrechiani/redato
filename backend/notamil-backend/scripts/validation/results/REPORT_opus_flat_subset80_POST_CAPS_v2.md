# Opus 4.7 + schema flat — eval subset 80 redações estratificadas

**Sample:** 80 redações estratificadas do baseline (n=200) AES-ENEM.
Distribuição: 15×≤400 + 35×401-799 + 15×800-940 + 15×1000.

**Schema:** v2 com flatten (cN_audit.X → cN_X). Reduce profundidade nivel 4 → 3.
Conteúdo de rubrica/system_prompt v2 intactos.
---

## Tabela 1 — Sonnet baseline vs Opus flat por faixa

| Faixa | n | Sonnet ±40 | Opus ±40 | Δ ±40 | Sonnet MAE | Opus MAE | Sonnet ME | Opus ME |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| ≤400 | 15 | 40.0% | 20.0% | -20.0 pts | 101.3 | 178.7 | +80 | +109 |
| 401-799 | 35 | 17.1% | 37.1% | +20.0 pts | 146.3 | 116.6 | -87 | +9 |
| 800-940 | 15 | 20.0% | 46.7% | +26.7 pts | 138.7 | 58.7 | -133 | +5 |
| 1000 | 15 | 26.7% | 73.3% | +46.7 pts | 130.7 | 48.0 | -131 | -48 |

## Tabela 2 — Concordância progressiva por faixa (Opus flat)

| Faixa | n | ±40 | ±60 | ±80 | MAE | ME |
|---|---:|---:|---:|---:|---:|---:|
| ≤400 | 15 | 3/15 (20%) | 3/15 (20%) | 5/15 (33%) | 178.7 | +109 |
| 401-799 | 35 | 13/35 (37%) | 13/35 (37%) | 19/35 (54%) | 116.6 | +9 |
| 800-940 | 15 | 7/15 (47%) | 7/15 (47%) | 12/15 (80%) | 58.7 | +5 |
| 1000 | 15 | 11/15 (73%) | 11/15 (73%) | 12/15 (80%) | 48.0 | -48 |
| **GLOBAL** | **80** | 34/80 (42%) | 34/80 (42%) | 48/80 (60%) | - | - |

## Tabela 3 — Análise específica bucket 401-799 (n=35)

Cada redação: gabarito + nota Opus + erro. Audit completo na coluna `audit`.

| ID | Gab | Opus | Erro | C1 | C2 | C3 | C4 | C5 | audit |
|---|---:|---:|---:|---:|---:|---:|---:|---:|:---:|
| `aesenem_sourceB_full_000938` | 600 | 0 | -600 | 0 | 0 | 0 | 0 | 0 | ✗ |
| `aesenem_sourceB_full_002821` | 560 | 400 | -160 | 40 | 80 | 80 | 80 | 120 | ✓ |
| `aesenem_sourceB_full_000933` | 720 | 560 | -160 | 80 | 80 | 120 | 160 | 120 | ✓ |
| `aesenem_sourceB_full_002446` | 760 | 600 | -160 | 40 | 160 | 80 | 160 | 160 | ✓ |
| `aesenem_sourceB_full_001951` | 440 | 280 | -160 | 40 | 80 | 80 | 80 | 0 | ✓ |
| `aesenem_sourceAWithGraders_train_00010` | 520 | 360 | -160 | 40 | 40 | 80 | 80 | 120 | ✓ |
| `aesenem_sourceB_full_001904` | 680 | 560 | -120 | 40 | 160 | 160 | 80 | 120 | ✓ |
| `aesenem_sourceAWithGraders_train_00017` | 720 | 600 | -120 | 80 | 200 | 200 | 120 | 0 | ✓ |
| `aesenem_sourceB_full_000965` | 480 | 360 | -120 | 0 | 80 | 80 | 80 | 120 | ✓ |
| `aesenem_sourceB_full_001240` | 640 | 560 | -80 | 40 | 80 | 120 | 160 | 160 | ✓ |
| `aesenem_sourceB_full_000616` | 760 | 720 | -40 | 40 | 160 | 200 | 160 | 160 | ✓ |
| `aesenem_sourceB_full_002024` | 440 | 440 | +0 | 80 | 80 | 80 | 160 | 40 | ✓ |
| `aesenem_sourceB_full_001718` | 520 | 520 | +0 | 80 | 80 | 200 | 160 | 0 | ✓ |
| `aesenem_sourceB_full_000901` | 720 | 720 | +0 | 80 | 160 | 120 | 160 | 200 | ✓ |
| `aesenem_sourceB_full_002546` | 760 | 760 | +0 | 80 | 160 | 160 | 200 | 160 | ✓ |
| `aesenem_sourceB_full_000580` | 760 | 760 | +0 | 40 | 160 | 200 | 160 | 200 | ✓ |
| `aesenem_sourceB_full_002471` | 760 | 800 | +40 | 80 | 160 | 200 | 160 | 200 | ✓ |
| `aesenem_sourceB_full_002480` | 680 | 720 | +40 | 120 | 160 | 160 | 160 | 120 | ✓ |
| `aesenem_sourceB_full_002912` | 720 | 760 | +40 | 40 | 160 | 200 | 160 | 200 | ✓ |
| `aesenem_sourceB_full_000879` | 640 | 680 | +40 | 80 | 160 | 120 | 160 | 160 | ✓ |
| `aesenem_sourceB_full_003214` | 760 | 800 | +40 | 120 | 160 | 200 | 160 | 160 | ✓ |
| `aesenem_sourceAWithGraders_train_00025` | 560 | 600 | +40 | 160 | 160 | 80 | 80 | 120 | ✓ |
| `aesenem_sourceB_full_002840` | 760 | 800 | +40 | 120 | 160 | 120 | 200 | 200 | ✓ |
| `aesenem_sourceB_full_000495` | 680 | 760 | +80 | 80 | 160 | 160 | 160 | 200 | ✓ |
| `aesenem_sourceB_full_002123` | 520 | 600 | +80 | 40 | 160 | 160 | 160 | 80 | ✓ |
| `aesenem_sourceB_full_002504` | 720 | 800 | +80 | 80 | 160 | 200 | 160 | 200 | ✓ |
| `aesenem_sourceB_full_000569` | 720 | 800 | +80 | 40 | 200 | 200 | 160 | 200 | ✓ |
| `aesenem_sourceB_full_000521` | 760 | 840 | +80 | 80 | 200 | 200 | 160 | 200 | ✓ |
| `aesenem_sourceB_full_000319` | 720 | 840 | +120 | 80 | 200 | 200 | 200 | 160 | ✓ |
| `aesenem_sourceB_full_001097` | 640 | 800 | +160 | 80 | 160 | 200 | 160 | 200 | ✓ |
| `aesenem_sourceB_full_000590` | 480 | 640 | +160 | 40 | 40 | 200 | 200 | 160 | ✓ |
| `aesenem_sourceB_full_001695` | 720 | 960 | +240 | 160 | 200 | 200 | 200 | 200 | ✓ |
| `aesenem_sourceAWithGraders_validation_` | 680 | 920 | +240 | 160 | 160 | 200 | 200 | 200 | ✓ |
| `aesenem_sourceAWithGraders_test_000101` | 480 | 760 | +280 | 160 | 200 | 200 | 160 | 40 | ✓ |
| `aesenem_sourceAWithGraders_validation_` | 440 | 760 | +320 | 80 | 160 | 160 | 160 | 200 | ✓ |

## Verdict — critérios explícitos

### OPERACIONAL (consolidar Opus+flat como produção)

- ❌ **±40 global ≥ 45%** — 42.5%
- ❌ **|ME ≤400| < 60** — +109
- ✅ **|ME 401-799| < 60** — +9
- ✅ **|ME 800-940| < 60** — +5
- ✅ **audits ≤400 ≥ 80%** — 93%
- ✅ **audits 401-799 ≥ 80%** — 97%
- ✅ **audits 800-940 ≥ 80%** — 100%
- ✅ **audits 1000 ≥ 80%** — 100%

**Operacional:** ❌ NÃO APROVADO

### CIRÚRGICO (faixa 401-799)

- ✅ **401-799 ±40 ≥ 30%** — 37.1%
- ✅ **401-799 |ME| < 80** — +9

**Cirúrgico:** ✅ MAGNITUDE CONTROLADA

## Decisão

→ **CASO INTERMEDIÁRIO.** ±40 global abaixo de 45% mas sem indício de problema estrutural específico. Investigar onde está o erro residual.
