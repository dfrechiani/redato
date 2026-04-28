# A/B v2 vs v3 — Validação contra gabarito INEP

Inputs:
- v2 baseline: `scripts/validation/results/eval_gold_run_20260426_093436.jsonl`
- v3 run:      `scripts/validation/results/eval_gold_v3_run_20260426_141244.jsonl`

Cobertura:
- v2: 193 válidas / 200 (erros: 7)
- v3: 200 válidas / 200 (erros: 0)

---

## Tabela 1 — Métricas globais

| Métrica | v2 baseline | v3 | Δ |
|---|---:|---:|---:|
| Concordância ±40 (total) | 22.8% | 12.0% | -10.8 pts |
| Concordância ±60 (total) | 22.8% | 12.0% | -10.8 pts |
| Concordância ±80 (total) | 37.8% | 19.0% | -18.8 pts |
| MAE total | 137.8 | 216.8 | +79.0 |
| ME total (viés) | -62.0 | -193.2 | -131.2 |
| Latência média/redação | 74.3s | 61.9s | -12.4s |

**Leitura ±40 vs ±60 vs ±80:** se ±40 baixo mas ±80 alto → calibração de escala (corrigível). Se ±80 também baixo → erro estrutural.

## Tabela 2 — Concordância ±40 e MAE por competência

| | v2 ±40 | v3 ±40 | Δ ±40 | v2 MAE | v3 MAE | Δ MAE |
|---|---:|---:|---:|---:|---:|---:|
| C1 | 30.6% | 57.5% | +26.9 pts | 83.7 | 55.6 | -28.1 |
| C2 | 79.8% | 68.0% | -11.8 pts | 40.4 | 45.2 | +4.8 |
| C3 | 82.9% | 88.5% | +5.6 pts | 29.6 | 31.6 | +2.0 |
| C4 | 80.3% | 51.0% | -29.3 pts | 38.1 | 57.0 | +18.9 |
| C5 | 74.6% | 68.0% | -6.6 pts | 41.2 | 46.2 | +5.0 |

## Tabela 3 — Viés direcional (ME = Redato - Gabarito) por competência

| | v2 ME | v3 ME | Δ ME |
|---|---:|---:|---:|
| C1 | -79.6 | -52.0 | +27.6 |
| C2 | -11.0 | -36.8 | -25.8 |
| C3 | +19.7 | -21.6 | -41.3 |
| C4 | -18.2 | -51.4 | -33.2 |
| C5 | +27.2 | -31.4 | -58.6 |

## Tabela 4 — Métricas por faixa de gabarito

| Faixa | n | v2 MAE | v3 MAE | v2 ME | v3 ME | v2 ±40 | v3 ±40 |
|---|---:|---:|---:|---:|---:|---:|---:|
| ≤ 400 | 40 | 130.0 | 104.4 | +116.0 | -20.5 | 27.5% | 36.6% |
| 401-799 | 98 | 133.5 | 214.5 | -85.3 | -202.4 | 25.5% | 8.1% |
| ≥ 800 | 55 | 151.3 | 297.3 | -149.8 | -296.0 | 14.5% | 1.7% |

## Tabela 5 — Distribuição de flags v3 (sanity dos detectores)

Registros v3 com flags presentes: 200

| Flag | Disparada em (n) | % |
|---|---:|---:|
| `tangenciamento` | 29 | 14.5% |
| `copia_motivadores_recorrente` | 7 | 3.5% |
| `repertorio_de_bolso` | 121 | 60.5% |
| `argumentacao_previsivel` | 189 | 94.5% |
| `limitacao_aos_motivadores` | 54 | 27.0% |
| `proposta_vaga_ou_constatatoria` | 108 | 54.0% |
| `proposta_desarticulada` | 99 | 49.5% |
| `desrespeito_direitos_humanos` | 0 | 0.0% |

**Anulações detectadas:**
- `anulacao=extensao_insuficiente`: 5
- `anulacao=nao_atende_tipo`: 1

## Tabela 5b — Correlação flag × erro (calibração dos detectores)

Pra cada flag binária: MAE/ME nas redações onde disparou vs onde não disparou.
Leitura: flag dispara + ME ~ 0 → detector calibrado. Flag dispara + ME muito negativo → detector rebaixa demais. Flag nunca dispara → não consegue avaliar.

| Flag | n_with | MAE_with | ME_with | n_without | MAE_without | ME_without | Diagnóstico |
|---|---:|---:|---:|---:|---:|---:|---|
| `tangenciamento` | 29 | 191.7 | -183.4 | 171 | 221.1 | -194.9 | rebaixa demais quando dispara |
| `copia_motivadores_recorrente` | 7 | 222.9 | -108.6 | 193 | 216.6 | -196.3 | rebaixa demais quando dispara |
| `repertorio_de_bolso` | 121 | 240.3 | -209.9 | 79 | 180.8 | -167.6 | rebaixa demais quando dispara |
| `argumentacao_previsivel` | 189 | 218.4 | -193.4 | 11 | 189.1 | -189.1 | rebaixa demais quando dispara |
| `limitacao_aos_motivadores` | 54 | 231.1 | -197.0 | 146 | 211.5 | -191.8 | rebaixa demais quando dispara |
| `proposta_vaga_ou_constatatoria` | 108 | 195.9 | -167.0 | 92 | 241.3 | -223.9 | rebaixa demais quando dispara |
| `proposta_desarticulada` | 99 | 195.6 | -174.5 | 101 | 237.6 | -211.5 | rebaixa demais quando dispara |
| `desrespeito_direitos_humanos` | 0 | - | - | 200 | 216.8 | -193.2 | nunca dispara |

## Tabela 6 — Top 10 erros residuais v3 (|erro| > 80) — pra inspeção

| ID | Fonte | Gab | v3 | Erro |
|---|---|---:|---:|---:|
| `aesenem_sourceB_full_001103` | aes-enem | 840 | 280 | -560 |
| `aesenem_sourceB_full_001099` | aes-enem | 840 | 400 | -440 |
| `aesenem_sourceB_full_000002` | aes-enem | 800 | 360 | -440 |
| `aesenem_sourceB_full_000055` | aes-enem | 840 | 400 | -440 |
| `aesenem_sourceB_full_002640` | aes-enem | 560 | 160 | -400 |
| `aesenem_sourceB_full_000768` | aes-enem | 680 | 280 | -400 |
| `aesenem_sourceB_full_002840` | aes-enem | 760 | 360 | -400 |
| `aesenem_sourceB_full_000933` | aes-enem | 720 | 320 | -400 |
| `aesenem_sourceB_full_000616` | aes-enem | 760 | 360 | -400 |
| `aesenem_sourceB_full_000876` | aes-enem | 680 | 280 | -400 |

## Critérios de sucesso

- **Falha estrutural** (±40 < 35% OU mesmo viés direcional da v2): ❌ DETECTADA
- **Parcial mínimo** (±40 ≥ 40%, |ME baixas| < 60, |ME altas| < 80): ❌ não atingido
- **Aceitável** (±40 ≥ 55%, |ME| < 50 todas faixas): ❌ não atingido
- **Pleno** (±40 ≥ 70%, |ME| < 30 todas faixas): ❌ não atingido

## Decisão

→ **FALHA ESTRUTURAL — investigar pipeline antes de iterar v3.1.** Sinais: pipeline não absorvendo a rubrica nova, LLM ignorando instruções de gradação holística, ou ruído sistemático no gabarito. Possíveis investigações: comparar audit_prose v3 com regras da rubrica em redações específicas; checar se schema do tool_use está restringindo demais; rodar 1-2 redações com Opus em vez de Sonnet pra isolar capacidade-do-modelo vs rubrica.
