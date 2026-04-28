# Plano — Validação estatística da Redato contra corpus real ENEM

> Documento focado pro Claude Code executar. Frente A do roadmap pós-OCR:
> validar precisão da Redato em redações reais ENEM (não em canários adversariais).
>
> **Princípio operacional:** roda 2 evals paralelos (gold vs real-world) com 200
> redações cada, mede MAE por competência contra gabarito, compara concordância
> entre os dois conjuntos pra entender se Redato está calibrada pra banca oficial,
> pra cursinho, ou pros dois.

## Estado de partida

- Corpus de 18.165 redações em `~/Mesa/redato_hash/ingest/data/final/unified.jsonl`
- 5 fontes: AES-ENEM (3.772), Essay-BR (5.769), Brasil-Escola (6.364), UOL-XML (2.213), INEP (47)
- Schema confirmado: `redacao.texto_original`, `tema.titulo`, `nota_global`, `notas_competencia.{c1..c5}`, `fonte`
- Redato pós-OCR: pipeline estável (Opus 4.7 OCR, Sonnet 4.6 grading, prompt PT-BR, sem CV, 3 enhanced)

**Nota crítica:** este eval usa só `texto_original`. OCR não entra aqui — texto já está digitalizado no corpus. Estamos validando **grading**, não OCR.

## Objetivos

1. Medir MAE (mean absolute error) da Redato vs gabarito INEP por competência
2. Identificar onde Redato infla / deflate sistematicamente
3. Medir % de correções dentro de ±40 pontos do total (critério INEP)
4. **Comparar concordância em 2 conjuntos distintos:** gold (banca oficial) vs real-world (cursinho/usuário)

**O que NÃO é objetivo:** treinar/fine-tunar nada. Não mexe em system prompt sem evidência clara. Só medir.

## Estratégia: 2 evals paralelos

### Eval 1 — Gold (banca oficial)

**Fontes incluídas:**
- INEP (47 redações nota 1000, comentário extenso)
- AES-ENEM (3.772 — inclui `gradesThousand` oficial + PROPOR2024 + JBCS2025, datasets de pesquisa)

**Total disponível:** ~3.819 redações com gabarito de origem oficial/acadêmica.

**Selecionar:** 200 estratificadas por faixa de nota (ver tabela abaixo).

**Pergunta que responde:** *"A Redato concorda com a banca ENEM oficial?"*

### Eval 2 — Real-world (cursinho + usuário)

**Fontes incluídas:**
- Brasil-Escola (6.364)
- UOL-XML (2.213)
- Essay-BR (5.769)

**Total disponível:** ~14.346 redações com gabarito de cursinho ou crowdsourced.

**Selecionar:** 200 estratificadas por faixa de nota.

**Pergunta que responde:** *"A Redato concorda com correção de cursinho/mercado?"*

### Por que 2 evals separados

- INEP/AES-ENEM = verdade oficial. Redato tem que bater com isso pra ser confiável em simulado de alto stake.
- Brasil-Escola/UOL/Essay-BR = realidade de mercado. Redato vai competir/complementar essas plataformas.
- Discrepância entre os dois é dado pedagogicamente útil: se Redato concorda com banca mas discorda de cursinho, ela está dura ou branda em relação ao mercado.

## Estratificação por faixa de nota

Pra cada eval, 200 redações balanceadas:

| Faixa total | Quantidade | Justificativa |
|---|---:|---|
| 200-399 | 30 | Notas baixas (raras no corpus) |
| 400-599 | 50 | Faixa intermediária |
| 600-799 | 60 | Maior cluster real |
| 800-999 | 40 | Faixa alta |
| 1000 | 20 | Gold (cap em 20 pra não enviesar) |
| **Total** | **200** | |

Mesma distribuição em ambos evals.

## Etapa 1 — Construir os 2 subsets

**Arquivo a criar:** `backend/notamil-backend/scripts/validation/build_validation_sets.py`

### Critérios de filtragem (aplicados a ambos evals)

1. `redacao.texto_original` não vazio (string > 100 chars)
2. `notas_competencia` tem 5 campos preenchidos (c1..c5 não-null)
3. `nota_global` preenchido e bate com soma dos 5 (sanity check; tolerância ±5 pra arredondamento)
4. `tema.titulo` preenchido e não vazio
5. `nota_global > 0` (excluir os 2.906 zeros, são drafts/anuladas)

### Estratificação

```python
# Pseudo-código
def select_stratified(candidates, n_per_band):
    bands = {
        "200-399": (200, 399, 30),
        "400-599": (400, 599, 50),
        "600-799": (600, 799, 60),
        "800-999": (800, 999, 40),
        "1000":    (1000, 1000, 20),
    }
    selected = []
    for band, (lo, hi, n) in bands.items():
        pool = [c for c in candidates if lo <= c["nota_global"] <= hi]
        random.shuffle(pool)
        selected.extend(pool[:n])
    return selected

random.seed(42)  # reprodutibilidade
gold_set = select_stratified(filter_gold_sources(corpus), bands)
realworld_set = select_stratified(filter_realworld_sources(corpus), bands)
```

### Saída

```
scripts/validation/data/
├── eval_gold_v1.jsonl              ← 200 do INEP + AES-ENEM
├── eval_realworld_v1.jsonl         ← 200 do Brasil-Escola + UOL + Essay-BR
└── validation_sets_stats.json      ← distribuição por faixa, fonte, ano em cada eval
```

### Critérios de aceitação Etapa 1

- [ ] Script roda em < 30s
- [ ] Cada eval tem exatamente 200 redações (ou registra explicitamente se faixa não tem volume — caso provável: faixa 1000 no real-world)
- [ ] JSONL válido em ambos
- [ ] Stats mostra distribuição por fonte dentro de cada eval
- [ ] Sem overlap entre os dois (ID único entre gold e real-world)

**Possível ajuste necessário:** se alguma faixa do real-world não tem volume (ex: nota 1000 só tem 81 candidatos no Brasil-Escola/UOL), reduzir target dessa faixa e redistribuir. Documentar.

## Etapa 2 — Rodar Redato em batch (em paralelo nos 2 evals)

**Arquivo a criar:** `backend/notamil-backend/scripts/validation/run_validation_eval.py`

### Configuração

- Modelo: `claude-sonnet-4-6` (mesmo da produção atual de grading)
- Cache: ligado (TTL 1h, breakpoints já configurados)
- Self-critique: **DESLIGADO** (`REDATO_SELF_CRITIQUE=0`) — eval estatístico não precisa
- Ensemble: **DESLIGADO** (N=1) — eval é descritivo, não decisório
- Two-stage: **LIGADO** (`REDATO_TWO_STAGE=1`) — derivação mecânica reduz variância

### Por que essa configuração

- Self-critique custa 2x e adiciona latência. Em eval de 400 redações, não vale.
- Ensemble triplica custo. Variância intra-modelo já é absorvida pelo N=200 por eval.
- Two-stage mantido porque é o pipeline padrão de produção.

### Custo e tempo estimados

- 400 redações × ~$0.014/call (com cache hit): ~$5.60
- Tempo: ~25s/correção × 400 / paralelismo 5 = ~33 minutos wall time
- Vale rodar com `concurrent.futures.ThreadPoolExecutor(max_workers=5)`

### Implementação

```python
# Pseudo-código
def run_eval(input_jsonl, output_jsonl, eval_name):
    redacoes = load_jsonl(input_jsonl)
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            executor.submit(grade_via_redato, r): r
            for r in redacoes
        }
        for future in as_completed(futures):
            redacao = futures[future]
            try:
                redato_output = future.result()
                result = {
                    "id": redacao["id"],
                    "fonte": redacao["fonte"],
                    "eval_name": eval_name,
                    "tema": redacao["tema"]["titulo"],
                    "gabarito": {
                        "total": redacao["nota_global"],
                        **redacao["notas_competencia"],
                    },
                    "redato": {
                        "total": redato_output["notas"]["total"],
                        **{k: redato_output["notas"][k] for k in ["c1","c2","c3","c4","c5"]},
                    },
                    "latency_ms": redato_output.get("_latency_ms"),
                }
            except Exception as e:
                result = {"id": redacao["id"], "error": str(e)}
            
            append_jsonl(output_jsonl, result)
```

### Saída

```
scripts/validation/results/
├── eval_gold_run_YYYYMMDD_HHMMSS.jsonl
└── eval_realworld_run_YYYYMMDD_HHMMSS.jsonl
```

### Critérios de aceitação Etapa 2

- [ ] Ambos evals processam 200 redações sem crash do script
- [ ] Taxa de erro < 5% (registra falhas, não interrompe)
- [ ] Cache hit ratio > 80% após warmup
- [ ] Resultado salvo em JSONL válido pra cada eval

## Etapa 3 — Análise estatística

**Arquivo a criar:** `backend/notamil-backend/scripts/validation/analyze_validation.py`

### Métricas calculadas pra CADA eval (gold e real-world)

**Métricas principais:**

1. **MAE por competência** — `mean(|redato.cN - gabarito.cN|)` para N em 1..5
2. **MAE no total** — `mean(|redato.total - gabarito.total|)`
3. **% dentro de ±40 pontos no total** — critério INEP de concordância
4. **% dentro de ±40 pontos por competência**

**Métricas de viés:**

5. **Bias por competência** — `mean(redato.cN - gabarito.cN)` (positivo = Redato infla, negativo = deflate)
6. **Bias por faixa de nota** — MAE separado pra cada faixa. Detecta se erra mais em alunos fracos ou fortes
7. **Bias por fonte** (dentro do eval) — MAE separado por fonte. Detecta se Redato performa diferente por origem

**Distribuição de erro:**

8. **Histograma de erros por competência** — quantas vezes errou +40, +80, +120, etc.
9. **Casos catastróficos** — redações onde erro total > 200 pontos

### Métricas comparativas (gold vs real-world)

10. **Tabela comparativa MAE total** — gold vs real-world
11. **Tabela comparativa % ±40** — gold vs real-world
12. **Discrepância de viés** — Redato é mais alinhada com qual conjunto?

### Saída

```
scripts/validation/results/
├── analysis_eval_gold_YYYYMMDD.json
├── analysis_eval_realworld_YYYYMMDD.json
├── analysis_comparison_YYYYMMDD.json
└── validation_report_YYYYMMDD.md       ← human-readable consolidado
```

### Estrutura do relatório markdown

1. **TL;DR** — 4-6 linhas: MAE total gold, MAE total real-world, % ±40 em cada, viés geral
2. **Tabela 1: MAE por competência** (gold | real-world | delta)
3. **Tabela 2: MAE por faixa de nota** (em cada eval)
4. **Tabela 3: MAE por fonte** (dentro de cada eval)
5. **Tabela 4: Bias direcional** (Redato infla ou deflate cada competência?)
6. **Top 10 casos catastróficos** (de cada eval, com ID, gabarito, Redato, erro)
7. **Histograma textual** de erros por competência
8. **Conclusão** — pergunta-resposta:
   - Redato bate com banca oficial? (ler tabela 1 gold)
   - Redato bate com cursinho? (ler tabela 1 real-world)
   - Onde infla/deflate sistematicamente?
   - Performa pior em alunos fortes ou fracos?

### Critérios de aceitação Etapa 3

- [ ] Análise roda em < 1 min (processa JSONL local, sem chamadas API)
- [ ] Relatório markdown gerado é legível
- [ ] Casos catastróficos têm IDs identificáveis pra investigação manual

## Etapa 4 — Reporte e decisão

Quando Etapa 3 terminar, **pausa e reporta números antes de qualquer ação.**

Vou olhar:

1. **MAE total em cada eval** — esperado: 30-50 pontos. Se < 30, suspeitamente bom. Se > 80, problema sério.
2. **% dentro de ±40 em cada eval** — esperado: 70-85% pra estar alinhado com critério INEP.
3. **Discrepância gold vs real-world** — Redato concorda mais com qual?
4. **Viés sistemático** — alguma competência inflada/deflate consistentemente?
5. **Top casos catastróficos** — padrão neles? Tema, faixa, tamanho?

Com base nisso decidimos próximos passos:
- Se ambos evals ≥ 75% ±40: Redato está calibrada. Documenta como baseline e fechou.
- Se gold passa mas real-world falha: Redato está alinhada com banca, dura/branda em relação ao mercado. Decisão de produto.
- Se nenhum passa: identifica viés concreto, ajusta system prompt ou derivação mecânica, re-roda subset menor.
- Se casos catastróficos têm padrão: investiga manualmente, talvez vire canário novo no v2.

## Pendências e ressalvas

**1. Texto digitalizado, não OCR.** Eval usa `texto_original` direto. Não passa por OCR. Avalia só grading.

**2. Gabarito do corpus não é perfeito.** AES-ENEM e Brasil-Escola são scraping; UOL é XML estruturado mas pode ter erros; Essay-BR só tem nota crua. INEP é gold. Por isso vale rodar separação por fonte (Etapa 3 item 7).

**3. 200 redações por eval é amostra, não censo.** Resultado é estimativa. MAE de 35 pontos significa intervalo real ~32-38, não exatos 35.

**4. Bias de seleção do corpus.** Distribuição real de redação ENEM tem mais notas baixas e poucos 1000. Estratificação tenta corrigir mas não elimina.

**5. Faixa 1000 no real-world pode não ter 20 candidatos.** Nesse caso documenta e usa o que tiver.

**6. Essay-BR sem comentário, só nota.** Inclusão dele no real-world serve só pra volume e diversidade. Análise por fonte vai mostrar se gabarito Essay-BR é confiável ou ruído.

## Não-objetivos explícitos

- **Não vai treinar nada.** Sem fine-tuning, sem few-shot dinâmico. Só medição.
- **Não vai mexer no system prompt** a não ser que análise revele algo claro.
- **Não vai validar OCR.** Outra frente, depois.
- **Não vai integrar com produção.** Pasta `scripts/validation/` fica isolada.

## Estrutura final de pastas

```
backend/notamil-backend/
└── scripts/
    └── validation/
        ├── build_validation_sets.py
        ├── run_validation_eval.py
        ├── analyze_validation.py
        ├── data/
        │   ├── eval_gold_v1.jsonl
        │   ├── eval_realworld_v1.jsonl
        │   └── validation_sets_stats.json
        └── results/
            ├── eval_gold_run_YYYYMMDD_HHMMSS.jsonl
            ├── eval_realworld_run_YYYYMMDD_HHMMSS.jsonl
            ├── analysis_eval_gold_YYYYMMDD.json
            ├── analysis_eval_realworld_YYYYMMDD.json
            ├── analysis_comparison_YYYYMMDD.json
            └── validation_report_YYYYMMDD.md
```

## Custo total estimado

- Etapa 1 (build): zero (processamento local)
- Etapa 2 (eval): ~$5.60 com cache hit
- Etapa 3 (análise): zero
- **Total: ~$6**

Tempo estimado de execução end-to-end: ~45-60 minutos (build < 1min, eval ~33min, análise < 1min).

## Ordem de execução

```
1. Implementa build_validation_sets.py
2. Roda build_validation_sets.py
3. Pausa: confirma que stats batem com tabela esperada
4. Implementa run_validation_eval.py
5. Roda eval_gold (200 chamadas, ~17min)
6. Pausa: confirma cache hit > 80%, taxa de erro < 5%
7. Roda eval_realworld (200 chamadas, ~17min)
8. Implementa analyze_validation.py
9. Roda analyze_validation.py
10. Pausa: reporta os números pra decisão
```

Não emendar etapas sem checkpoint. Especificamente:
- Antes do passo 5: confirma que stats da Etapa 1 fazem sentido
- Antes do passo 7: confirma que eval_gold rodou limpo
- Antes do passo 10: confirma que análise tem todas as métricas

## Variáveis de ambiente esperadas

Antes de rodar:

```bash
export REDATO_DEV_OFFLINE=0          # eval real, não stub
export REDATO_SELF_CRITIQUE=0        # desligado pra eval
export REDATO_ENSEMBLE=1             # N=1
export REDATO_TWO_STAGE=1            # mantém two-stage
export REDATO_CLAUDE_MODEL=claude-sonnet-4-6
# ANTHROPIC_API_KEY já configurado
```

---

*Versão 1.0 · abril de 2026*
