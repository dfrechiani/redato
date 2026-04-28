# Débito técnico — Redato v2 (estado em 2026-04-27)

> Itens identificados em ciclos de validação contra gabarito INEP que não
> foram corrigidos no ciclo atual. Cada item tem origem documentada,
> magnitude estimada e custo aproximado de fix.

## 1. CARIDOSA — falta instrumento de "previsibilidade argumentativa"

**Origem:** [INVESTIGATION_baixas.md](../../../backend/notamil-backend/scripts/validation/results/INVESTIGATION_baixas.md), categoria 3 (1/15 casos do bucket ≤400).

**Sintoma:** redações em que o audit do LLM elogia consistentemente todas as competências (tese clara, repertório produtivo, projeto evidente, 3 partes completas) mas o gold INEP atribui notas baixas (~80 em todas as competências). Ex: caso `aesenem_sourceAWithGraders_train_000416` (gab=400, opus=800, Δ+400 com C2/C3/C4 todos em 200).

**Causa raiz:** o schema v2 não tem campo pra capturar **"argumentação previsível"** — clichê estrutural, argumentos genéricos aplicáveis a qualquer tema, ausência de recorte original. INEP rebaixa essas redações pra C3=120, C2=120 mas o LLM não tem onde marcar isso.

**Magnitude:** ~5-10% do bucket ≤400 (estimativa amostral n=15, intervalo grande). Pode ser mais comum em populações maiores.

**Tentativa anterior:** v3 holística adicionou flag `argumentacao_previsivel` mas disparou em 94.5% das redações — resultado pior. **Detector binário não é o caminho.**

**Fix proposto (não implementado):** instrumento qualitativo no schema (ex: campo `argumentation_originality` em escala 1-3, com critérios objetivos: "estrutura é clichê", "argumentos são genéricos", "ausência de recorte"). Validar com poucos exemplos antes de generalizar.

**Custo estimado:** 1-2 dias dev + ~$5 de API pra eval de validação. Risco: replicar o problema da v3 (over-detection).

---

## 2. BORDERLINE / texto truncado — falta detector de buraco lexical

**Origem:** [INVESTIGATION_baixas.md](../../../backend/notamil-backend/scripts/validation/results/INVESTIGATION_baixas.md), categoria 4 (1/15 casos, mas Δ=+560 — o mais grave).

**Sintoma:** redações com **buracos literais** (`"E, para , foi aprovadano"`, `"vagas nas  ."`, `"É para  que ele possui"`) recebem nota alta porque o audit avalia presença de elementos (tese, conectores, proposta) sem detectar que partes do texto estão faltando ou incoerentes.

**Caso documentado:** `aesenem_sourceB_full_002860` — gab 200 → opus 760 (+560). Audit deu C3=200 ("projeto bem definido"), C5=200 (5 elementos), C4=160. Texto está objetivamente quebrado.

**Causa raiz:** schema v2 não tem campo pra "frases incompletas / texto truncado / buracos lexicais". O audit lê o **esqueleto** sem perceber que o **tecido** está quebrado.

**Magnitude:** difícil estimar do dataset AES-ENEM (textos digitalizados, raros buracos). **Em produção real**, esse padrão pode ser comum em redações com OCR falho ou digitação parcial.

**Fix proposto (não implementado):** detector regex/heurístico pré-LLM em `_claude_grade_essay`:
- Sequências `\s\s+` de espaços não-iniciais
- `[\.\,]\s*$` (vírgula/ponto seguido só de fim de linha)
- Períodos terminando com preposição (`para`, `de`, `em` antes de `\.`)
Se ≥3 ocorrências, anexar warning ao user_msg pedindo pro LLM verificar coerência semântica antes de avaliar.

**Custo estimado:** 0.5 dia dev + smoke test 5 redações. Risco baixo (detector pré-LLM não afeta caminho principal).

---

## 3. C1 OVER-COUNTING — threshold "≥10 desvios = nota 1" é severo em textos curtos

**Origem:** [INVESTIGATION_baixas.md](../../../backend/notamil-backend/scripts/validation/results/INVESTIGATION_baixas.md), categoria 2 (2/15 casos do bucket ≤400).

**Sintoma:** Opus identifica mais desvios gramaticais que o gold tolera, deflacionando excessivamente C1 em textos curtos (≤1000 chars). Casos:
- `aesenem_sourceB_full_000132` (gab C1=160, opus C1=40, 13 desvios em 941 chars)
- `aesenem_sourceB_full_000978` (gab C1=120, opus C1=40, 25 desvios)

**Causa raiz:** `c1_audit.threshold_check.applies_nota_1` exige "desvios diversificados e frequentes" — **critério INEP é qualitativo (frequência relativa), schema v2 traduz em absoluto (≥10)**. Textos curtos têm mais "densidade" de erros mesmo com poucos absolutos.

**Magnitude:** 2/15 = ~13% do bucket ≤400 nesta amostra. Provavelmente menor em redações longas (≥2k chars).

**Fix proposto (não implementado):** ajustar threshold pra normalizar por tamanho do texto:
- Em vez de `desvios_count >= 10 → nota_1`, usar `desvios_count / words >= 0.012 → nota_1`
- Ou: peso diferente pra desvio (acentuação leve = 0.5x, regência grave = 1.5x)
- Ou: usar `reading_fluency_compromised` (já no audit) como gating de aplicação dos thresholds.

**Custo estimado:** 0.5-1 dia dev + re-derivação dos 80 (zero API). Risco: pode subir nota em textos curtos onde o gold realmente penalizou (validar primeiro com casos individuais).

---

## 4. Caps cirúrgicos C2/C3/C4 (aplicados parcialmente em 2026-04-27)

**Status:** **PARCIALMENTE APLICADO**. Ver `dev_offline.py:_derive_c2_nota`, `_derive_c3_nota`, `_derive_c4_nota` (caps marcados com comentário "INVESTIGATION_baixas 2026-04-27").

**O que foi aplicado:**
- C2: cap 80 quando `repertoire_references` tem ≥2 itens e TODOS são `productivity != "productive"` (all-decorative)
- C3: cap 120 quando `has_explicit_thesis = False`. Cap 80 quando também `ponto_de_vista_claro = False`.
- C4: cap 80 quando ≥3 flags negativas simultâneas (`mechanical`, `complex_periods=False`, `ambiguous≥2`, `most_used≥4`)

**Resultado medido (eval subset 80):**
- ±40 global: 42.5% (idem PRE caps — nem regrediu nem melhorou globalmente)
- |ME ≤400|: 131 → 109 (melhora marginal)
- 12 redações tiveram nota deflacionada em -40 ou -120 (audit alinha com derivação agora)
- Faixa 401-799 NÃO regrediu

**Por que não move métrica:** os 6 casos TETO BAIXO RUBRICA do bucket ≤400 não são suficientes pra mover ±40 global. Os bottlenecks dominantes nas baixas são CARIDOSA + BORDERLINE (itens 1 e 2 deste documento).

**O que NÃO foi aplicado (variante mais agressiva, testada e revertida):**
- C4 cap ≥2 flags (em vez de ≥3): regrediu 401-799 e 800-940 em ~7 pts cada. **Não usar**.

**Decisão:** caps mantidos por **fidelidade semântica** (derivação agora reflete melhor o audit), mesmo sem ganho de métrica.

---

## Próximas frentes possíveis (não no escopo atual)

Em ordem de ROI estimado:

1. **Detector de buraco lexical (item 2)** — custo baixo, risco baixo, pode pegar caso extremo +560.
2. **Normalização C1 por densidade (item 3)** — custo médio, risco médio. Resolve 2/15 casos do bucket baixas.
3. **Instrumento de previsibilidade argumentativa (item 1)** — custo alto, risco alto (v3 falhou). Só atacar se houver dataset pedagógico real (cursinho parceiro) pra validar.

**Gating geral:** nenhum desses fixes faz sentido em isolamento. Avaliar em ciclo com eval-200 completo pra ter sample size adequado por faixa.
