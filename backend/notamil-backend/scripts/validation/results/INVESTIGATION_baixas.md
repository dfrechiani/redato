# Investigation — bucket ≤400 do eval Opus + flat (n=15)

> 15 redações com gabarito INEP ≤400, classificadas por padrão de erro.
> Objetivo: identificar onde o Opus + schema flat falha em redações de
> nota baixa (bucket que regrediu vs Sonnet baseline: 40% → 20% ±40,
> ME +131).

## Tabela 1 — Os 15 casos com classificação atribuída

| # | ID | Gab | Opus | Δ | Categoria |
|---|---|---:|---:|---:|---|
| 1 | `aesenem_sourceB_full_002860` | 200 | 760 | **+560** | BORDERLINE (texto truncado) |
| 2 | `aesenem_sourceAWithGraders_train_000416` | 400 | 800 | +400 | CARIDOSA |
| 3 | `aesenem_sourceAWithGraders_validation_000083` | 360 | 600 | +240 | TETO BAIXO RUBRICA |
| 4 | `aesenem_sourceB_full_000089` | 280 | 480 | +200 | TETO BAIXO RUBRICA |
| 5 | `aesenem_sourceAWithGraders_train_000462` | 200 | 400 | +200 | TETO BAIXO RUBRICA |
| 6 | `aesenem_sourceAWithGraders_train_000082` | 280 | 480 | +200 | TETO BAIXO RUBRICA |
| 7 | `aesenem_sourceAWithGraders_test_000050` | 200 | 400 | +200 | TETO BAIXO RUBRICA |
| 8 | `aesenem_sourceAWithGraders_train_000419` | 240 | 400 | +160 | TETO BAIXO RUBRICA |
| 9 | `aesenem_sourceB_full_001783` | 320 | 440 | +120 | VARIÂNCIA NORMAL |
| 10 | `aesenem_sourceB_full_000978` | 400 | 480 | +80 | C1 OVER-COUNTING |
| 11 | `aesenem_sourceB_full_002464` | 400 | 400 | 0 | VARIÂNCIA NORMAL (compensação) |
| 12 | `aesenem_sourceAWithGraders_train_000134` | 280 | 280 | 0 | VARIÂNCIA NORMAL (compensação) |
| 13 | `aesenem_sourceAWithGraders_train_000652` | 200 | 200 | 0 | VARIÂNCIA NORMAL |
| 14 | `aesenem_sourceB_full_000132` | 400 | 320 | -80 | C1 OVER-COUNTING |
| 15 | `aesenem_sourceB_full_001817` | 320 | 0 | -320 | FALHA TÉCNICA (audit vazio) |

## Distribuição por categoria

| Categoria | n | % | Direção |
|---|---:|---:|---|
| **TETO BAIXO RUBRICA** | 6 | 40% | infla |
| VARIÂNCIA NORMAL | 4 | 27% | ± |
| **C1 OVER-COUNTING** | 2 | 13% | deflate C1 |
| **CARIDOSA** | 1 | 7% | infla |
| **BORDERLINE (truncado)** | 1 | 7% | infla |
| FALHA TÉCNICA | 1 | 7% | vazio |

**Padrão dominante:** TETO BAIXO RUBRICA (6/15 = 40% dos casos) é responsável pela maioria do viés de inflação no bucket ≤400. Em todos os 6, o audit do LLM **identifica corretamente os problemas**, mas a derivação Python produz nota acima do que o gold considera adequado.

## Categoria 1 — TETO BAIXO RUBRICA (n=6)

**Definição:** audit identifica problemas concretos (flags negativas, contagens altas, repertoire decorativo, períodos não estruturados) mas a derivação `_derive_cN_nota` produz nota 1-2 níveis acima do gold.

### Exemplo A — caso #6 (`aesenem_sourceAWithGraders_train_000082`, gab 400 → opus 480)

**Tema:** A Volta da Política Conservadora no Brasil

**C3 — gold=120, opus=160 (+40):**
```
has_explicit_thesis: False
ponto_de_vista_claro: False
ideias_progressivas: True
planejamento_evidente: True
```
Audit diz **sem tese explícita e sem ponto de vista claro**, mas dá 160. INEP rebaixaria pra 80 ou 120 com `has_explicit_thesis=False`. A derivação Python aceita "ideias_progressivas + plan_evidente" como suficiente pra 160 mesmo sem tese.

**C4 — gold=40, opus=120 (+80):**
```
most_used_connector: 'onde'×4
has_mechanical_repetition: True
complex_periods_well_structured: False
ambiguous_pronouns: 3 ocorrências
```
4 sinais negativos simultâneos, audit dá 120. INEP daria 40 com mech_repetition + 'onde' inadequado + complex_periods quebrados. **A derivação não pune adequadamente o conjunto de flags negativas em C4.**

### Exemplo B — caso #5 (`aesenem_sourceAWithGraders_train_000462`, gab 200 → opus 400)

**C2 — gold=40, opus=160 (+120):**
```
repertoire_references (n=3):
  prods=['decorative', 'decorative', 'decorative']
tres_partes_completas: True
```
**Todos os 3 repertórios marcados como decorativos.** INEP daria C2=80 (recorre à cópia/decoração) ou menos. Derivação aceita "3 partes + repertoire_n≥2" como 160 ignorando que ALL são decorativos.

**Análise unificada da categoria:** A `_derive_c2_nota`, `_derive_c3_nota` e `_derive_c4_nota` parecem priorizar **presença** de elementos sobre **qualidade**. A `_derive_cN_nota` precisa receber regras de rebaixamento explícitas pra: (a) C2 com 100% repertoire decorativo, (b) C3 sem tese explícita, (c) C4 com 3+ flags negativas simultâneas.

## Categoria 2 — C1 OVER-COUNTING (n=2)

**Definição:** Opus identifica mais desvios gramaticais que o gold considera, rebaixando excessivamente C1.

### Exemplo — caso #14 (`aesenem_sourceB_full_000132`, gab 400 → opus 320)

**C1 — gold=160, opus=40 (-120):**
```
desvios_gramaticais_count: 13
reincidencia_de_erro: True
reading_fluency_compromised: True
threshold_check: applies_nota_1=True (≥10 desvios)
```
Texto tem 941 chars (curto). Opus achou 13 desvios → cai pra threshold "diversificados e frequentes". Gold considerou apenas 160 (poucos desvios). Possível causa: Opus está contando como desvios coisas que gold tolera (vírgula em adjunto adverbial, espaços antes de pontuação, etc.).

**Análise:** o threshold "≥10 desvios = nota 1" pode ser severo demais pra textos curtos. INEP usa critério qualitativo (frequência relativa + impacto), não absoluto. **Possível ajuste:** normalizar contagem por palavras totais OU dar peso diferente pra severidade do desvio.

## Categoria 3 — CARIDOSA (n=1)

**Definição:** audit elogia todas as competências (não há flag negativa relevante), mas o gold contradiz amplamente.

### Único exemplo — caso #2 (`aesenem_sourceAWithGraders_train_000416`, gab 400 → opus 800)

**Tema:** Apropriação cultural é só no carnaval?

Texto é razoavelmente coerente: define apropriação cultural via UNESCO, dá exemplo (carnaval, dreads), diferencia de intercâmbio cultural. Mas gold deu **80 em todas as 5 competências (=400)**.

| | Audit Opus | Gold | Comentário |
|---|---|---|---|
| C1 | 80 (9 desvios, sem fluency comprometida) | 80 | match |
| C2 | 200 (repertoire 3× productive, 3 partes) | 80 | gold viu copia? decoração? |
| C3 | 200 (tese, pdv claro, plan evid) | 80 | gold viu projeto raso? |
| C4 | 200 (variety 8, complex_well=True, sem ambig) | 80 | gold viu pouca diversidade? |
| C5 | 120 (4/5 elementos, generic) | 80 | match-ish |

Aqui não há sinal NO AUDIT que justifique a discrepância. O LLM lê a redação como sólida, gold como mediana. Pode ser:
- (a) Gold INEP foi severo demais nessa redação (ruído do gabarito)
- (b) LLM lê estrutura como qualidade quando o tecido argumentativo é raso
- (c) Há critério INEP qualitativo (ex: "argumentação previsível") que o schema v2 não captura

**Análise:** sem instrumento no schema atual pra detectar "previsibilidade argumentativa". Esse caso é o caminho mais próximo do que a v3 tentava resolver — mas v3 falhou exatamente por excesso de detectores binários. Aqui é 1/15 dos casos.

## Categoria 4 — BORDERLINE / TEXTO TRUNCADO (n=1)

### Único exemplo — caso #1 (`aesenem_sourceB_full_002860`, gab 200 → opus 760, **+560**)

Texto contém **buracos literais**:
```
"E, para , foi aprovadano fim do ano passado, a PEC 241 que  os investimentos"
"o número de vagas nas  ."
"É para  que ele possui uma educação"
"da unificação de todas as  em quatro áreas"
```

Várias palavras faltando — o texto está incompleto/com OCR ou digitação ruim. **Gold deu 200 total (40 em todas as 5)** porque a redação está estruturalmente quebrada.

**Audit do Opus:**
- C3=200 ("projeto bem definido", planejamento evidente)
- C5=200 (5 elementos identificados, articulada)
- C4=160 (1 ambiguous pronoun apenas)

**O audit lê o ESQUELETO** (presença de tese, presença de elementos, presença de conectivos) **sem perceber que o tecido entre os marcos está QUEBRADO**. Frases incompletas não estão registradas como flag.

**Análise:** o schema v2 não tem campo pra "frases incompletas / texto truncado / buracos lexicais". Esse é o caso mais grave (Δ+560) e pode existir em volume na população real (redações OCR com falhas, digitação parcial, etc).

## Categoria 5 — VARIÂNCIA NORMAL (n=4)

Casos 9, 11, 12, 13. Δ entre 0 e +120, mas com mistura de inflações e deflações por competência que se compensam parcialmente. Variância natural do LLM, não há padrão sistemático claro.

## Categoria 6 — FALHA TÉCNICA (n=1)

**Caso #15** (`aesenem_sourceB_full_001817`): audit retornou completamente vazio mesmo com schema flat. 1/80 do eval (1.25%) — abaixo do threshold de 80% audits completos por faixa, mas é um único caso isolado.

## Recomendações

### Recomendação principal — corrigir TETO BAIXO RUBRICA (40% dos casos)

A categoria dominante é **TETO BAIXO RUBRICA**. Ajuste cirúrgico em `_derive_cN_nota`:

1. **C2:** se `all(p == 'decorative' for p in repertoire_prods)` E `n_repertoire ≥ 2` → cap em 80 (não 120-160)
2. **C3:** se `has_explicit_thesis = False` → cap em 120 (não 160). Se também `ponto_de_vista_claro = False` → cap em 80.
3. **C4:** se `(has_mechanical_repetition + complex_well_structured = False + ambiguous_pronouns ≥ 2) ≥ 2 simultâneos` → cap em 80.

Custo do ajuste: alterações localizadas em `_derive_c2_nota`, `_derive_c3_nota`, `_derive_c4_nota`. Sem rodada de API. Testável com re-derivação dos dados existentes (zero custo).

### Recomendação secundária — investigar C1 OVER-COUNTING

2/15 casos. Não urgente, mas vale checar se threshold "≥10 desvios = nota 1" é apropriado para textos curtos (≤1000 chars). Possível ajuste: normalizar por densidade (`desvios / chars_texto * 1000`).

### Casos não-actionable agora

- **CARIDOSA** (1/15): difícil de fixar sem instrumento de "previsibilidade argumentativa". Schema v2 não captura. Preço de aceitar a v2.
- **BORDERLINE / texto truncado** (1/15): caso extremo +560, mas texto está objetivamente quebrado. Detector de buraco lexical seria útil em produção (`if texto contains "  " or "[\.\,]\s*$"` etc.) mas é tema separado.
- **FALHA TÉCNICA** (1/15): rate de output vazio do schema flat ainda existe em casos isolados. 97.5% audits completos no eval 80 já está bem acima do threshold operacional.

## Próximo passo proposto

**Aplicar Recomendação principal** em `_derive_c2_nota`, `_derive_c3_nota`, `_derive_c4_nota` e re-derivar os 80 resultados existentes do Opus + flat (custo zero, sem novas API calls). Se os 6 casos TETO BAIXO RUBRICA descerem 1 nível, ME ≤400 cai de +131 pra ~+50 e ±40 global atinge ≥45% (target operacional).

Validação: rodar `compare_opus_flat_subset80.py` no JSONL re-derivado e checar se ±40 global ≥ 45% e |ME ≤400| < 60.

Custo total estimado: 30-60 min de trabalho, $0 de API.
