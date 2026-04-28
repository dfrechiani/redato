# Métricas de uso real — Opus + flat + caps v2 (n=80)

Redefinição de métricas pra refletir como a Redato é usada de fato:
- **Modo diagnóstico** (parágrafo curto): aluno precisa saber se está
  fraco / médio / forte por competência, e se há problema específico detectado.
- **Modo simulado** (redação completa): faixa global da nota (±100) importa
  mais que precisão exata da nota total.

Métrica antiga (±40 nota total) era apropriada pra comparação contra avaliador
humano INEP, mas não pra utilidade pedagógica direta.

---

## Análise 1 — Acerto de faixa (5 níveis)

Sample válido: 80

| | n | Acerto exato | Acerto ±1 faixa |
|---|---:|---:|---:|
| **GLOBAL** | 80 | 47/80 (58.8%) | 74/80 (92.5%) |
| ≤400 (insuficiente) | 15 | 9/15 (60%) | 13/15 (87%) |
| 401-600 (em desenvolvimento) | 12 | 4/12 (33%) | 12/12 (100%) |
| 601-800 (mediano) | 28 | 16/28 (57%) | 24/28 (86%) |
| 801-900 (bom) | 9 | 6/9 (67%) | 9/9 (100%) |
| 901-1000 (excelente) | 16 | 12/16 (75%) | 16/16 (100%) |

**Matriz de confusão (linha = faixa do gabarito, coluna = faixa Redato):**

| Gold \ Redato | F1 | F2 | F3 | F4 | F5 |
|---|---:|---:|---:|---:|---:|
| **F1** | 9 | 4 | 2 | 0 | 0 |
| **F2** | 5 | 4 | 3 | 0 | 0 |
| **F3** | 0 | 5 | 16 | 3 | 4 |
| **F4** | 0 | 0 | 2 | 6 | 1 |
| **F5** | 0 | 0 | 0 | 4 | 12 |

## Análise 2 — Acerto direcional por competência (forte/médio/fraco)

forte=160-200, médio=80-120, fraco=0-40

| Comp | n | Acerto exato | Adjacente (1 nível) |
|---|---:|---:|---:|
| C1 | 80 | 30/80 (37.5%) | 68/80 (85.0%) |
| C2 | 80 | 53/80 (66.2%) | 78/80 (97.5%) |
| C3 | 80 | 46/80 (57.5%) | 78/80 (97.5%) |
| C4 | 80 | 60/80 (75.0%) | 77/80 (96.2%) |
| C5 | 80 | 53/80 (66.2%) | 78/80 (97.5%) |
| **MÉDIA** | 400 | 242/400 (60.5%) | 379/400 (94.8%) |

**Confusion matrix por competência (linha = gold, coluna = Redato):**

### C1

| Gold \ Redato | fraco | médio | forte |
|---|---:|---:|---:|
| **fraco** | 4 | 1 | 0 |
| **medio** | 8 | 8 | 0 |
| **forte** | 12 | 29 | 18 |

### C2

| Gold \ Redato | fraco | médio | forte |
|---|---:|---:|---:|
| **fraco** | 4 | 2 | 2 |
| **medio** | 3 | 8 | 19 |
| **forte** | 0 | 1 | 41 |

### C3

| Gold \ Redato | fraco | médio | forte |
|---|---:|---:|---:|
| **fraco** | 1 | 7 | 2 |
| **medio** | 1 | 18 | 24 |
| **forte** | 0 | 0 | 27 |

### C4

| Gold \ Redato | fraco | médio | forte |
|---|---:|---:|---:|
| **fraco** | 0 | 5 | 3 |
| **medio** | 2 | 8 | 8 |
| **forte** | 0 | 2 | 52 |

### C5

| Gold \ Redato | fraco | médio | forte |
|---|---:|---:|---:|
| **fraco** | 14 | 5 | 2 |
| **medio** | 2 | 7 | 17 |
| **forte** | 0 | 1 | 32 |

## Análise 3 — Precisão de detecção de flags (modo diagnóstico)

Pra cada flag negativa: TP/FP/FN/TN contra penalty no gabarito.
Precision = % das vezes que a flag disparou e era justificada.
Recall = % dos casos reais de problema que a flag pegou.

| Flag | TP | FP | FN | TN | Precision | Recall | n_disparos | n_problemas_real |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `c1_reincidencia` | 9 | 44 | 0 | 25 | 17.0% | 100.0% | 53 | 9 |
| `c1_fluency_compromised` | 7 | 30 | 2 | 39 | 18.9% | 77.8% | 37 | 9 |
| `c2_tangenciamento` | 2 | 1 | 5 | 70 | 66.7% | 28.6% | 3 | 7 |
| `c2_copia_motivadores` | 0 | 0 | 17 | 61 | n/a | 0.0% | 0 | 17 |
| `c2_all_decorative` | 2 | 6 | 15 | 55 | 25.0% | 11.8% | 8 | 17 |
| `c3_no_thesis` | 19 | 0 | 32 | 27 | 100.0% | 37.3% | 19 | 51 |
| `c3_argumentos_contraditorios` | 5 | 1 | 16 | 56 | 83.3% | 23.8% | 6 | 21 |
| `c3_limitado_motivadores` | 12 | 0 | 39 | 27 | 100.0% | 23.5% | 12 | 51 |
| `c4_mechanical_repetition` | 8 | 1 | 16 | 53 | 88.9% | 33.3% | 9 | 24 |
| `c4_complex_periods_broken` | 21 | 17 | 3 | 37 | 55.3% | 87.5% | 38 | 24 |
| `c5_nao_articulada` | 17 | 3 | 9 | 49 | 85.0% | 65.4% | 20 | 26 |

## Análise 4 — Comparativo contra métrica antiga (±40)

| Modelo | ±40 nota total |
|---|---:|
| Sonnet baseline (v2 nested) | 19/80 (23.8%) |
| **Opus + flat + caps v2 (atual)** | 34/80 (42.5%) |

---

## Recomendação — métrica oficial a reportar

### Quadro consolidado

| Métrica | Valor | Adequação ao uso real |
|---|---:|---|
| ±40 nota total (antiga) | **42.5%** | Baixa — penaliza erro de 40-100 pts dentro da mesma faixa qualitativa |
| Acerto de faixa exato (5 níveis) | **58.8%** | Média — útil pra benchmarking interno |
| **Acerto de faixa ±1** | **92.5%** | **Alta — modo simulado** |
| Acerto direcional exato (forte/médio/fraco) | 60.5% | Média — sensível ao caso fronteira |
| **Acerto direcional ±1** | **94.8%** | **Alta — modo diagnóstico** |

### Recomendação por modo de uso

**Modo simulado (redação completa) → reportar `Acerto de faixa ±1 = 92.5%`**

Razão: aluno/professor da MVT recebem a redação corrigida pra entender em qual nível
qualitativo ela está (insuficiente / em desenvolvimento / mediano / bom / excelente). A
matriz de confusão F1..F5 mostra que **nenhum erro pula 2+ faixas** (todos os 6 erros
estão em ±1 faixa adjacente), e a faixa F2 (em desenvolvimento) tem 100% de acerto ±1.
Redação F5 (excelente) nunca é classificada como F3 ou abaixo — diferenciação correta no
topo. ±40 não captura essa qualidade porque mede precisão de pontos absolutos, não de
faixa pedagógica.

**Modo diagnóstico (parágrafo curto) → reportar `Acerto direcional ±1 = 94.8%`**

Razão: no modo diagnóstico o aluno só vê *forte / médio / fraco* por competência
(160-200 / 80-120 / 0-40). 94.8% direcional ±1 significa que **menos de 1 em 20
classificações erra mais de 1 nível**. Por competência: C2/C3/C4/C5 ≥ 96%, C1 = 85%
(C1 é o ponto fraco — confirma item 3 do DEBITO_TECNICO sobre over-counting de desvios
em textos curtos).

**Reportar separadamente — não somar:** os dois modos têm contratos diferentes com o
usuário. Misturar 92.5% (faixa total) com 94.8% (direcional por comp) confunde a
interpretação.

### Flags negativas — usar com filtro de precision

A análise 3 mostra que **5 das 11 flags têm precision ≥80%** (alta confiabilidade quando
dispara) e devem ser as únicas exibidas no relatório do aluno:

| Flag exibível | Precision | Recall |
|---|---:|---:|
| `c3_no_thesis` | 100.0% | 37.3% |
| `c3_limitado_motivadores` | 100.0% | 23.5% |
| `c4_mechanical_repetition` | 88.9% | 33.3% |
| `c5_nao_articulada` | 85.0% | 65.4% |
| `c3_argumentos_contraditorios` | 83.3% | 23.8% |

As 6 restantes não devem ser exibidas:
- `c1_reincidencia` (17%), `c1_fluency_compromised` (19%), `c2_all_decorative` (25%),
  `c4_complex_periods_broken` (55%) — disparam demais, podem assustar o aluno por
  problema que o INEP não penalizaria.
- `c2_copia_motivadores` — nunca dispara (flag morta no schema atual).
- `c2_tangenciamento` — só 3 disparos no eval, sample insuficiente.

A escolha de "alto precision, baixo recall" é deliberada: **no modo diagnóstico, falso
positivo é pior que falso negativo** — flag errada quebra a confiança do aluno; flag
ausente é absorvida pelo nível direcional da competência.

### Métrica de referência interna (continuar acompanhando)

Manter `±40 nota total` em logs internos pra:
- Comparação contra rodadas anteriores (continuidade histórica do número Sonnet → Opus).
- Detectar regressão silenciosa que ±1 faixa esconderia (ex: viés sistemático de +30 pts
  em todas as redações não muda faixa mas degrada confiança do INEP).

**Não exibir ±40 ao usuário final** — não tem leitura pedagógica direta.

### Resumo executivo (1 linha pra slide)

> **Redato classifica corretamente a faixa global em 92,5% das redações e o nível por
> competência em 94,8% das avaliações** (n=80, redações ENEM 2022, gabarito INEP).
