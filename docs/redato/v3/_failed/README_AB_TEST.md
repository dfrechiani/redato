# REDATO v3 — A/B Test contra v2

Este pacote contém a rubrica v3 e o system prompt v3, derivados de:
1. Cartilha do Participante INEP 2025 (fonte canônica)
2. 38 comentários oficiais INEP em redações nota 1000 (corpus inep.jsonl)

Tem como propósito ser testado contra a v2 (rubrica_v2.md, baseline 22.8% concordância ±40 contra gabarito INEP em 200 redações AES-ENEM).

## Arquivos

- **rubrica_v3.md** — rubrica completa, 8 seções. Substituição da v2.
- **system_prompt_v3.md** — system prompt para o LLM, com modelos de fraseologia INEP.

## Hipótese de impacto

Baseada no diagnóstico da Etapa 4:

| Mecanismo do viés v2 | Correção v3 | Lado afetado | Magnitude esperada |
|---|---|---|---|
| Contagem absoluta C1 | Excepcionalidade + reincidência | Altas | -40 a -60 → +0 |
| Contagem aritmética C5 | 4 atributos qualitativos | Ambos | -30 a -40 → +0 / +30 a +50 → +0 |
| Critérios formais C2 | Cobertura do recorte | Altas | -30 a -50 → +0 |
| Repertório de bolso ausente | Detector com 4 heurísticas | Baixas | +30 a +50 → +0 |
| Reincidência mal posicionada | Reincidência divide 200/160 | Mistas | -20 a -30 → +0 |

**Estimativa otimista:** v3 deve mover concordância ±40 de 22.8% para 50-65% em uma iteração, dependendo de quanto o LLM consegue absorver as 5 correções simultaneamente.

**Estimativa conservadora:** v3 melhora consistentemente em uma faixa específica (provavelmente as altas, onde o sinal é mais limpo) e ganha 15-25 pontos percentuais. Faixa baixa demanda 2ª iteração para refinar detector de repertório de bolso e proposta vaga.

**Cenário de fracasso a observar:** se v3 não move o eval em pelo menos 10 pontos percentuais em uma iteração, isso sugere que o problema não é a rubrica/prompt mas algo mais estrutural (qualidade do parser de redação, OCR, decoupling entre rubrica declarada e raciocínio efetivo do LLM). Aí o caminho é rever a pipeline antes de iterar a rubrica.

## Como rodar o A/B test

### 1. Implementação no pipeline

No código atual da Redato:

```python
# Carregar rubrica e system prompt v3
RUBRICA_V3 = open("docs/redato/v3/rubrica_v3.md").read()
SYSTEM_V3 = open("docs/redato/v3/system_prompt_v3.md").read()

# A/B flag controlada por variável de ambiente
USE_V3 = os.environ.get("REDATO_RUBRICA") == "v3"

if USE_V3:
    rubrica = RUBRICA_V3
    system = SYSTEM_V3
else:
    rubrica = RUBRICA_V2
    system = SYSTEM_V2
```

### 2. Eval contra gabarito

Rodar o mesmo set de 200 redações AES-ENEM contra v2 (baseline conhecido) e v3, separadamente:

```bash
REDATO_RUBRICA=v2 python scripts/validation/run_eval.py --output results/eval_v2_run_$(date +%s).jsonl
REDATO_RUBRICA=v3 python scripts/validation/run_eval.py --output results/eval_v3_run_$(date +%s).jsonl
```

### 3. Métricas comparativas

Para cada run, calcular:
- **Concordância ±40 por competência** (C1, C2, C3, C4, C5).
- **Concordância ±40 nota global**.
- **MAE (Mean Absolute Error)** por competência e global.
- **Viés sistemático**: erro médio (ME) — positivo significa inflar, negativo deflate.
- **Distribuição de erros por faixa de nota gabarito**: ≤400, 400-600, 600-800, ≥800.

Tabela esperada:

| Métrica | v2 baseline | v3 | Δ |
|---|---|---|---|
| Concordância ±40 global | 22.8% | ?% | ?? |
| MAE global | ?? | ?? | ?? |
| ME ≤400 | +116 | ?? | ?? |
| ME ≥800 | -150 | ?? | ?? |
| MAE por competência | ?? | ?? | ?? |

### 4. Análise de erro residual

Para o v3, examinar redações onde |erro| > 80:

- Ler o audit em prosa do LLM.
- Verificar se o raciocínio do LLM segue a rubrica v3 ou se desvia.
- Categorizar tipo de erro: (a) LLM aplicou rubrica corretamente mas a rubrica está errada para esse caso; (b) LLM aplicou rubrica incorretamente; (c) gabarito INEP é discrepante com a própria Cartilha.

A categoria (a) sinaliza ajuste necessário na v3 → v4. A categoria (b) sinaliza ajuste no system prompt. A categoria (c) é ruído do gabarito (humans disagree too).

### 5. Critério de sucesso

**Sucesso parcial mínimo:** concordância ±40 ≥ 40% E redução do viés sistemático em ambos os lados (ME nas baixas < +60, ME nas altas > -80). Já é melhoria substantiva.

**Sucesso aceitável:** concordância ±40 ≥ 55% E |ME| < 50 em todas as faixas. Sistema usável.

**Sucesso pleno:** concordância ±40 ≥ 70% E |ME| < 30 em todas as faixas. Padrão INEP de concordância humana.

Sucesso aceitável é o objetivo realista de iteração 1. Sucesso pleno provavelmente exige 2-3 iterações.

## Próximos passos após eval v3

**Se v3 ≥ 55% concordância:** consolidar v3 como nova baseline, ajustar system prompt para reduzir erro residual, considerar fine-tuning leve com os 38 comentários INEP como few-shot examples.

**Se v3 entre 35% e 55%:** identificar onde está o erro residual, fazer v3.1 cirúrgico (ajuste pontual nas competências problemáticas).

**Se v3 < 35%:** investigar pipeline antes de iterar rubrica. Possíveis problemas: (a) LLM não está absorvendo o system prompt completamente; (b) parser de redação está perdendo estrutura; (c) gabarito AES-ENEM tem ruído maior que esperado.

## Avisos sobre limitações conhecidas

1. **Os 38 comentários INEP são todos de redação nota 1000.** A v3 modela com confiança a faixa alta (validação + crítica intra-1000), mas a faixa baixa é modelada via Cartilha + descritores 80/40/0 + detectores de rebaixamento. Não há comentário oficial de banca em redação 400 para comparação direta.

2. **A v3 é mais permissiva nas notas altas e mais rigorosa nas notas baixas que a v2.** Isso é intencional — corrige o viés observado. Mas se o gabarito AES-ENEM tem ruído na faixa baixa (escolha de nota humana com discordância intra-banca), o eval pode subestimar a melhoria do v3 nessa faixa.

3. **O detector de "argumentação previsível" e "repertório de bolso" depende de juízo qualitativo do LLM.** São os pontos mais frágeis da v3 — podem ser inconsistentes entre runs. Vale rodar o eval 2-3 vezes para medir variância antes de comparar com v2.

4. **A rubrica v3 não foi validada empiricamente ainda.** Esta versão é a melhor reconstrução possível dos critérios INEP a partir das fontes disponíveis. A validação acontece no eval. Se os números mostrarem que alguma decisão da v3 está errada, ajusta.
