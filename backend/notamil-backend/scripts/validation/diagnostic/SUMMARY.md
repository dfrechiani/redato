# SUMMARY — diagnóstico de viés (10 redações extremas)

Re-run das 10 redações com viés mais grave do eval_gold (5 inflacionadas + 5 deflacionadas).

Schema novo captura: `gabarito` (INEP), `redato_audit` (LLM raw), `redato_derivacao` (`_derive_cN_nota` rodado isolado), `redato_final` (após two-stage default).

---

## Tabela 1 — Notas: gabarito vs derivação vs final

| ID | Gab tot | Deriv tot | Final tot | Δ tot | Padrão |
|---|---:|---:|---:|---:|---|
| `aesenem_sourceB_full_002860` | 200 | 680 | 680 | +480 | infl |
| `aesenem_sourceAWithGraders_train_000593` | 200 | 520 | 520 | +320 | infl |
| `aesenem_sourceB_full_001441` | 200 | 440 | 440 | +240 | infl |
| `aesenem_sourceAWithGraders_train_000519` | 240 | 480 | 480 | +240 | infl |
| `aesenem_sourceAWithGraders_train_000694` | 360 | 600 | 600 | +240 | infl |
| `aesenem_sourceB_full_001122` | 800 | 600 | 600 | -200 | defl |
| `aesenem_sourceB_full_000756` | 920 | 720 | 720 | -200 | defl |
| `aesenem_sourceB_full_002422` | 920 | 680 | 680 | -240 | defl |
| `aesenem_sourceB_full_001882` | 840 | 560 | 560 | -280 | defl |
| `aesenem_sourceAWithGraders_validation_000068` | 1000 | 600 | 600 | -400 | defl |

## Tabela 2 — Drift por competência (final − gabarito)

| ID | C1 | C2 | C3 | C4 | C5 | Total |
|---|---:|---:|---:|---:|---:|---:|
| `aesenem_sourceB_full_002860` | +0 | +120 | +80 | +120 | +160 | +480 |
| `aesenem_sourceAWithGraders_train_000593` | +0 | +40 | +80 | +80 | +120 | +320 |
| `aesenem_sourceB_full_001441` | +0 | +40 | +80 | +40 | +80 | +240 |
| `aesenem_sourceAWithGraders_train_000519` | -40 | +80 | +80 | +0 | +120 | +240 |
| `aesenem_sourceAWithGraders_train_000694` | +0 | +160 | +40 | +0 | +40 | +240 |
| `aesenem_sourceB_full_001122` | -80 | +0 | +40 | -80 | -80 | -200 |
| `aesenem_sourceB_full_000756` | -120 | -40 | +40 | -80 | +0 | -200 |
| `aesenem_sourceB_full_002422` | -160 | -120 | +40 | -40 | +40 | -240 |
| `aesenem_sourceB_full_001882` | -120 | +0 | -40 | -120 | +0 | -280 |
| `aesenem_sourceAWithGraders_validation_00` | +0 | -200 | +0 | +0 | -200 | -400 |

## Tabela 3 — Derivação Python vs Final (two-stage post-processing impacto)

Se derivação == final, two-stage não mudou nada (esperado com REDATO_TWO_STAGE=1, que sobrescreve audit.nota com a derivação). Se há diferença, é sinal de bug.

| ID | C1 | C2 | C3 | C4 | C5 | Total |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| `aesenem_sourceB_full_002860` | = | = | = | = | = | = |
| `aesenem_sourceAWithGraders_train_000593` | = | = | = | = | = | = |
| `aesenem_sourceB_full_001441` | = | = | = | = | = | = |
| `aesenem_sourceAWithGraders_train_000519` | = | = | = | = | = | = |
| `aesenem_sourceAWithGraders_train_000694` | = | = | = | = | = | = |
| `aesenem_sourceB_full_001122` | = | = | = | = | = | = |
| `aesenem_sourceB_full_000756` | = | = | = | = | = | = |
| `aesenem_sourceB_full_002422` | = | = | = | = | = | = |
| `aesenem_sourceB_full_001882` | = | = | = | = | = | = |
| `aesenem_sourceAWithGraders_validation_00` | = | = | = | = | = | = |

## Tabela 4 — C1: contagem de desvios identificados pelo LLM vs nota INEP

`desvios_gramaticais_count` é o que o LLM contou. Em escala INEP, ~10+ desvios = nota 0/40, ~7-9 = 80, ~4-6 = 120, ~2-3 = 160, ≤1 = 200.

| ID | LLM desvios | LLM nota | Deriv C1 | Final C1 | Gab C1 |
|---|---:|---:|---:|---:|---:|
| `aesenem_sourceB_full_002860` | 16 | 40 | 40 | 40 | 40 |
| `aesenem_sourceAWithGraders_train_000593` | 7 | 40 | 40 | 40 | 40 |
| `aesenem_sourceB_full_001441` | 18 | 40 | 40 | 40 | 40 |
| `aesenem_sourceAWithGraders_train_000519` | 10 | 40 | 40 | 40 | 80 |
| `aesenem_sourceAWithGraders_train_000694` | 7 | 120 | 120 | 120 | 120 |
| `aesenem_sourceB_full_001122` | 7 | 80 | 80 | 80 | 160 |
| `aesenem_sourceB_full_000756` | 13 | 40 | 40 | 40 | 160 |
| `aesenem_sourceB_full_002422` | 11 | 40 | 40 | 40 | 200 |
| `aesenem_sourceB_full_001882` | 13 | 40 | 40 | 40 | 160 |
| `aesenem_sourceAWithGraders_validation_00` | 0 | 200 | 200 | 200 | 200 |

## Tabela 5 — C5: elementos da proposta identificados pelo LLM vs nota INEP

INEP: 5 elementos = 200, 4 = 160, 3 = 120, 2 = 80, 1 = 40, 0 = 0.

| ID | LLM elements_count | LLM nota | Deriv C5 | Final C5 | Gab C5 |
|---|---:|---:|---:|---:|---:|
| `aesenem_sourceB_full_002860` | ? | 200 | 200 | 200 | 40 |
| `aesenem_sourceAWithGraders_train_000593` | ? | 160 | 160 | 160 | 40 |
| `aesenem_sourceB_full_001441` | ? | 120 | 120 | 120 | 40 |
| `aesenem_sourceAWithGraders_train_000519` | ? | 120 | 120 | 120 | 0 |
| `aesenem_sourceAWithGraders_train_000694` | ? | 120 | 120 | 120 | 80 |
| `aesenem_sourceB_full_001122` | ? | 80 | 80 | 80 | 160 |
| `aesenem_sourceB_full_000756` | ? | 200 | 200 | 200 | 200 |
| `aesenem_sourceB_full_002422` | ? | 200 | 200 | 200 | 160 |
| `aesenem_sourceB_full_001882` | ? | 160 | 160 | 160 | 160 |
| `aesenem_sourceAWithGraders_validation_00` | ? | 0 | 0 | 0 | 200 |

## Padrão observado

### Inflacionados (n=5)

Drift médio por competência:
- C1: -8.0
- C2: +88.0
- C3: +72.0
- C4: +48.0
- C5: +104.0

### Deflacionados (n=5)

Drift médio por competência:
- C1: -96.0
- C2: -72.0
- C3: +16.0
- C4: -64.0
- C5: -48.0

### Two-stage post-processing

Casos onde derivação ≠ final: 0/10. Com REDATO_TWO_STAGE=1 (default), o esperado é derivação == final em 100% dos casos.

## Próximos passos sugeridos

Inspecionar individualmente os markdowns. Buscar especificamente:

- **Inflados:** o LLM contou poucos desvios em C1 mas o gabarito INEP marca C1=40? Sinal: LLM sub-detecta erros em redações fracas.
- **Deflados:** o LLM contou muitos desvios em C1 mas o gabarito INEP marca C1=200? Sinal: LLM super-detecta erros em redações boas (criticismo).
- **C5:** LLM contou poucos elementos da proposta em redações 1000? Sinal: regras de strict-quoting do C5 punem demais.
- **C2:** tema vazio (INEP) ou tema simples mas LLM marca tangenciamento? Sinal: viés do detector de tangenciamento.