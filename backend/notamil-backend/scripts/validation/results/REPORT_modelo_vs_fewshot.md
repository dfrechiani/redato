# Test — Opus v2 vs Sonnet v2+fewshot INEP vs Sonnet v2 baseline

**Sample:** 20 redações estratificadas (4×≤400 + 8×401-799 + 4×800-940 + 4×1000), as mesmas avaliadas no eval_gold v2 baseline (Sonnet 4.6).

---

## Cobertura por condição

| Condição | n alvo | n válidas | erros | outputs vazios |
|---|---:|---:|---:|---:|
| Sonnet v2 baseline (full 20) | 20 | 20 | 0 | 0 |
| Opus v2 puro | 20 | 11 | 0 | **9** |
| Sonnet v2 + fewshot INEP | 20 | 17 | 3 | 0 |

⚠ **Opus produziu 9 outputs com audit vazio** (`audit_keys=[]`, todos `cN_audit.nota=None`). É o bug histórico de schemas profundos em Opus 4.7 (memória do projeto registra). As 4 redações nota 1000 estão entre os outputs vazios — Opus não completou tool_use em nenhuma delas. Inviável em produção sem flatten do schema v2.


**Sample efetivo da comparação:** 11 redações onde todas as 3 condições produziram output válido. Métricas abaixo são sobre essa interseção, pra evitar viés de cobertura desigual.

---

## Tabela 1 — Métricas globais (interseção)

| Métrica | Sonnet baseline | Opus v2 | Sonnet+fewshot | Δ Opus | Δ Fewshot |
|---|---:|---:|---:|---:|---:|
| ±40 | 27.3% | 45.5% | 18.2% | +18.2 pts | -9.1 pts |
| ±80 | 36.4% | 54.5% | 27.3% | +18.2 pts | -9.1 pts |
| MAE total | 120.0 | 112.7 | 181.8 | -7.3 | +61.8 |
| ME total | +3.6 | +47.3 | -181.8 | +43.6 | -185.5 |

## Tabela 2 — ME (viés direcional) por competência

| | Sonnet baseline | Opus v2 | Sonnet+fewshot |
|---|---:|---:|---:|
| C1 | -87.3 | -87.3 | -94.5 |
| C2 | -3.6 | -3.6 | -36.4 |
| C3 | +43.6 | +50.9 | -29.1 |
| C4 | -3.6 | +29.1 | -58.2 |
| C5 | +54.5 | +58.2 | +36.4 |

## Tabela 3 — ME por faixa de gabarito

| Faixa | Sonnet baseline (n=ME) | Opus v2 (n=ME) | Sonnet+fewshot (n=ME) |
|---|---|---|---|
| ≤ 400 | n=4, ME=+110 | n=4, ME=+40 | n=4, ME=-100 |
| 401-799 | n=5, ME=-32 | n=5, ME=+128 | n=5, ME=-208 |
| 800-940 | n=2, ME=-120 | n=2, ME=-140 | n=2, ME=-280 |
| 1000 | n=0 (sem dado) | n=0 (sem dado) | n=0 (sem dado) |

## Verdict — qual variável tem alavancagem?

### Variável MODELO (Sonnet → Opus)

- Δ ±40: +18.2 pts  ·  Δ MAE: -7.3  ·  Δ ME: +43.6
- **Inviabilidade técnica:** 9/20 outputs vazios. Schema v2 é incompatível com Opus em produção.

### Variável FEW-SHOT (Sonnet+rubrica v2 → +2 exemplos INEP nota 1000)

- Δ ±40: -9.1 pts  ·  Δ MAE: +61.8  ·  Δ ME: -185.5

### Recomendação

→ **Modelo (Opus) é tecnicamente inviável** com schema v2 atual (9/20 outputs vazios). Restam 2 caminhos: (a) flatten do schema v2 + Opus (~3-4 dias de trabalho), (b) iterar few-shot com Sonnet (custo baixo). Decisão depende de magnitude de Δ no few-shot.
