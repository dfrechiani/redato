# Opus 4.7 + schema flat — eval subset 80 redações estratificadas

**Sample:** 80 redações estratificadas do baseline (n=200) AES-ENEM.
Distribuição: 15×≤400 + 35×401-799 + 15×800-940 + 15×1000.

**Schema:** v2 com flatten (cN_audit.X → cN_X). Reduce profundidade nivel 4 → 3.
Conteúdo de rubrica/system_prompt v2 intactos.
---

## Tabela 1 — Sonnet baseline vs Opus flat por faixa

| Faixa | n | Sonnet ±40 | Opus ±40 | Δ ±40 | Sonnet MAE | Opus MAE | Sonnet ME | Opus ME |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| ≤400 | 15 | 40.0% | 26.7% | -13.3 pts | 101.3 | 157.3 | +80 | +88 |
| 401-799 | 35 | 17.1% | 28.6% | +11.4 pts | 146.3 | 125.7 | -87 | -14 |
| 800-940 | 15 | 20.0% | 40.0% | +20.0 pts | 138.7 | 69.3 | -133 | -5 |
| 1000 | 15 | 26.7% | 73.3% | +46.7 pts | 130.7 | 48.0 | -131 | -48 |

## Tabela 2 — Concordância progressiva por faixa (Opus flat)

| Faixa | n | ±40 | ±60 | ±80 | MAE | ME |
|---|---:|---:|---:|---:|---:|---:|
| ≤400 | 15 | 4/15 (27%) | 4/15 (27%) | 5/15 (33%) | 157.3 | +88 |
| 401-799 | 35 | 10/35 (29%) | 10/35 (29%) | 17/35 (49%) | 125.7 | -14 |
| 800-940 | 15 | 6/15 (40%) | 6/15 (40%) | 10/15 (67%) | 69.3 | -5 |
| 1000 | 15 | 11/15 (73%) | 11/15 (73%) | 12/15 (80%) | 48.0 | -48 |
| **GLOBAL** | **80** | 31/80 (39%) | 31/80 (39%) | 44/80 (55%) | - | - |

## Tabela 3 — Análise específica bucket 401-799 (n=35)

Cada redação: gabarito + nota Opus + erro. Audit completo na coluna `audit`.

| ID | Gab | Opus | Erro | C1 | C2 | C3 | C4 | C5 | audit |
|---|---:|---:|---:|---:|---:|---:|---:|---:|:---:|
| `aesenem_sourceB_full_000938` | 600 | 0 | -600 | 0 | 0 | 0 | 0 | 0 | ✗ |
| `aesenem_sourceB_full_000933` | 720 | 480 | -240 | 80 | 80 | 120 | 80 | 120 | ✓ |
| `aesenem_sourceB_full_002821` | 560 | 400 | -160 | 40 | 80 | 80 | 80 | 120 | ✓ |
| `aesenem_sourceB_full_002446` | 760 | 600 | -160 | 40 | 160 | 80 | 160 | 160 | ✓ |
| `aesenem_sourceB_full_001951` | 440 | 280 | -160 | 40 | 80 | 80 | 80 | 0 | ✓ |
| `aesenem_sourceB_full_001240` | 640 | 480 | -160 | 40 | 80 | 120 | 80 | 160 | ✓ |
| `aesenem_sourceAWithGraders_train_00010` | 520 | 360 | -160 | 40 | 40 | 80 | 80 | 120 | ✓ |
| `aesenem_sourceB_full_000616` | 760 | 640 | -120 | 40 | 160 | 200 | 80 | 160 | ✓ |
| `aesenem_sourceB_full_001904` | 680 | 560 | -120 | 40 | 160 | 160 | 80 | 120 | ✓ |
| `aesenem_sourceAWithGraders_train_00017` | 720 | 600 | -120 | 80 | 200 | 200 | 120 | 0 | ✓ |
| `aesenem_sourceB_full_000965` | 480 | 360 | -120 | 0 | 80 | 80 | 80 | 120 | ✓ |
| `aesenem_sourceB_full_002024` | 440 | 360 | -80 | 80 | 80 | 80 | 80 | 40 | ✓ |
| `aesenem_sourceB_full_001718` | 520 | 440 | -80 | 80 | 80 | 200 | 80 | 0 | ✓ |
| `aesenem_sourceB_full_000580` | 760 | 680 | -80 | 40 | 160 | 200 | 80 | 200 | ✓ |
| `aesenem_sourceB_full_002912` | 720 | 680 | -40 | 40 | 160 | 200 | 80 | 200 | ✓ |
| `aesenem_sourceB_full_000879` | 640 | 600 | -40 | 80 | 160 | 120 | 80 | 160 | ✓ |
| `aesenem_sourceB_full_000901` | 720 | 720 | +0 | 80 | 160 | 120 | 160 | 200 | ✓ |
| `aesenem_sourceB_full_000569` | 720 | 720 | +0 | 40 | 200 | 200 | 80 | 200 | ✓ |
| `aesenem_sourceB_full_002546` | 760 | 760 | +0 | 80 | 160 | 160 | 200 | 160 | ✓ |
| `aesenem_sourceB_full_002471` | 760 | 800 | +40 | 80 | 160 | 200 | 160 | 200 | ✓ |
| `aesenem_sourceB_full_002480` | 680 | 720 | +40 | 120 | 160 | 160 | 160 | 120 | ✓ |
| `aesenem_sourceB_full_003214` | 760 | 800 | +40 | 120 | 160 | 200 | 160 | 160 | ✓ |
| `aesenem_sourceAWithGraders_train_00025` | 560 | 600 | +40 | 160 | 160 | 80 | 80 | 120 | ✓ |
| `aesenem_sourceB_full_002840` | 760 | 800 | +40 | 120 | 160 | 120 | 200 | 200 | ✓ |
| `aesenem_sourceB_full_000495` | 680 | 760 | +80 | 80 | 160 | 160 | 160 | 200 | ✓ |
| `aesenem_sourceB_full_002123` | 520 | 600 | +80 | 40 | 160 | 160 | 160 | 80 | ✓ |
| `aesenem_sourceB_full_002504` | 720 | 800 | +80 | 80 | 160 | 200 | 160 | 200 | ✓ |
| `aesenem_sourceB_full_000521` | 760 | 840 | +80 | 80 | 200 | 200 | 160 | 200 | ✓ |
| `aesenem_sourceB_full_000319` | 720 | 840 | +120 | 80 | 200 | 200 | 200 | 160 | ✓ |
| `aesenem_sourceB_full_001097` | 640 | 800 | +160 | 80 | 160 | 200 | 160 | 200 | ✓ |
| `aesenem_sourceB_full_000590` | 480 | 640 | +160 | 40 | 40 | 200 | 200 | 160 | ✓ |
| `aesenem_sourceAWithGraders_validation_` | 440 | 680 | +240 | 80 | 160 | 160 | 80 | 200 | ✓ |
| `aesenem_sourceB_full_001695` | 720 | 960 | +240 | 160 | 200 | 200 | 200 | 200 | ✓ |
| `aesenem_sourceAWithGraders_validation_` | 680 | 920 | +240 | 160 | 160 | 200 | 200 | 200 | ✓ |
| `aesenem_sourceAWithGraders_test_000101` | 480 | 760 | +280 | 160 | 200 | 200 | 160 | 40 | ✓ |

## Verdict — critérios explícitos

### OPERACIONAL (consolidar Opus+flat como produção)

- ❌ **±40 global ≥ 45%** — 38.8%
- ❌ **|ME ≤400| < 60** — +88
- ✅ **|ME 401-799| < 60** — -14
- ✅ **|ME 800-940| < 60** — -5
- ✅ **audits ≤400 ≥ 80%** — 93%
- ✅ **audits 401-799 ≥ 80%** — 97%
- ✅ **audits 800-940 ≥ 80%** — 100%
- ✅ **audits 1000 ≥ 80%** — 100%

**Operacional:** ❌ NÃO APROVADO

### CIRÚRGICO (faixa 401-799)

- ❌ **401-799 ±40 ≥ 30%** — 28.6%
- ✅ **401-799 |ME| < 80** — -14

**Cirúrgico:** ❌ PROBLEMA ESTRUTURAL

## Decisão

→ **PROBLEMA ESTRUTURAL na faixa 401-799.** Não escalar pra produção sem investigar a faixa média. Possíveis caminhos: (a) inspeção de auditorias individuais nessa faixa pra ver onde o LLM erra; (b) ajuste pontual de regras de derivação na zona 401-799; (c) few-shot específico pra faixa média.
