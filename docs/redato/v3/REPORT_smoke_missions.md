# REJ 1S — Smoke Test dos 5 modos (relatório executivo)

**Data:** 2026-04-27 (otimizado + vocabulário pedagógico)
**Modelos:** Sonnet 4.6 (Foco C3/C4/C5) + Opus 4.7 (Completo Parcial OF13 e Integral OF14)
**Spec:** [redato_1S_criterios.md](redato_1S_criterios.md)
**Resultados:** [scripts/validation/results/missions/](../../../backend/notamil-backend/scripts/validation/results/missions/)

## Resumo (rodada com vocabulário pedagógico — substituto "recorte temático" → "ponto de vista próprio")

| Modo | activity_id | Modelo | Schema | Vocab | Latência | Custo aprox./call |
|------|-------------|--------|--------|-------|----------|--------------------|
| `foco_c3` | `RJ1·OF10·MF·Foco C3` | Sonnet 4.6 | ✓ | ✓ | 14.7s | ~$0.02 |
| `foco_c4` | `RJ1·OF11·MF·Foco C4` | Sonnet 4.6 | ✓ | ✓ | 15.8s | ~$0.02 |
| `foco_c5` | `RJ1·OF12·MF·Foco C5` | Sonnet 4.6 | ✓ | ✓ | 20.4s | ~$0.02 |
| `completo_parcial` | `RJ1·OF13·MF·Correção 5 comp.` | Opus 4.7 | ✓ | ✓ | 28.9s | ~$0.19 |
| `completo_integral` | `RJ1·OF14·MF·Correção 5 comp.` | Opus 4.7 | ✓ | ✓ | 111.8s¹ | ~$0.86¹ (cold ~$1.50) |

¹ OF14 inclui self-critique (2 passes) + system cache de 21k tokens. Cache
hit ratio 100% em rajadas dentro do TTL (1h) — custo cai ~70% vs cold.

**Total gasto neste smoke:** ~$1.00 (5 chamadas, cache hit no OF14).
Alvo de "~$1.00" atingido. Persona cresceu ~2k chars com regras de
vocabulário, mas cache absorveu sem custo extra perceptível.

## Otimizações aplicadas

1. **Sonnet 4.6 para Modos Foco** (default em
   [`_DEFAULT_MODEL_BY_MODE`](../../../backend/notamil-backend/redato_backend/missions/router.py)):
   problema mais restrito (1 competência, 1 parágrafo curto), modelo menor
   é suficiente. Override geral via `REDATO_MISSION_MODEL` (separado de
   `REDATO_CLAUDE_MODEL` que afeta o pipeline v2 do OF14).

2. **Tamanho-alvo de audit** declarado no schema e no prompt:
   - Modo Foco: `feedback_professor.audit_completo` 100-200 palavras.
   - Completo Parcial: 200-400 palavras.
   - OF14: inalterado (pipeline v2).
   Resultado medido: foco 112-136 palavras, parcial 273 palavras —
   dentro do alvo.

3. **Persona reforçada** com regra explícita: "Economia de palavras é
   critério de qualidade. Cada campo tem tamanho-alvo declarado no
   schema (`description`). Cumpra o alvo — verbosidade não agrega
   informação pedagógica e desperdiça tokens."

4. **Vocabulário pedagógico calibrado para 1ª série EM** — ver seção
   dedicada abaixo.

## Vocabulário pedagógico

**Princípio:** aluno é interlocutor adulto da 1ª série EM. `feedback_aluno`
= conversa de sala de aula (substitutos cotidianos para jargão técnico).
`feedback_professor` = colega de sala (termos técnicos com explicação
contextual, não como categoria abstrata).

### Termos PROIBIDOS por padrão no `feedback_aluno` (com substitutos)

| Termo proibido | Substituto |
|---|---|
| tese | "a frase que você quer provar" / "a ideia central" |
| premissa | "a explicação" / "o porquê" (exceto OF10/OF11/OF13) |
| repertório | "o que comprova" / "número ou pesquisa" (exceto OF13/OF14) |
| dado verificável | "número que dá pra checar" |
| mecanismo causal | "como isso acontece na prática" |
| argumentação por reformulação | "repetir a mesma ideia" |
| prosa / prosa contínua | "texto corrido" |
| terreno previsível | "previsível" / "esperado" |
| recorte temático | "ponto de vista próprio" |
| autoria | "voz própria" / "jeito seu de pensar" |
| operadores argumentativos | "as palavras de ligação" / "conectivos" |
| projeto de texto | "como o texto se organiza" |
| proposição | "a ideia que você defende" |
| defesa do ponto de vista | "explicar por que você acha isso" |

### Whitelist por missão (termos que a oficina ensinou)

| Modo | Termos permitidos no aluno |
|---|---|
| `foco_c3` (OF10) | conclusão, premissa, exemplo |
| `foco_c4` (OF11) | conclusão, premissa (pragmática/principiológica), exemplo, conectivo, cadeia lógica, Palavra do Dia |
| `foco_c5` (OF12) | agente, ação, meio, finalidade, detalhamento, proposta de intervenção, direitos humanos |
| `completo_parcial` (OF13) | tópico frasal, argumento, repertório, coesão + acumulado das oficinas anteriores |
| `completo_integral` (OF14) | vocabulário REJ pleno (tudo do programa) |

### Diminutivos

**Banidos em todos os campos** — aluno é interlocutor adulto.
- ✗ "palavrinhas", "frasezinha", "trechinho", "ajustezinhos", "pequeninhos"
- ✓ "as palavras", "a frase", "trecho", "ajustes"

### Sem condescendência

Banidas: "que legal!", "show!", "que coisa boa!", elogios infantilizantes
em geral. Aluno é interlocutor adulto, não criança.

### Fidelidade aos substitutos

Em caso de dúvida sobre um termo específico, **manter a forma simples
listada**. Não inventar variantes literárias ou paráfrases criativas.
Se o termo proibido não tem substituto perfeito para o caso, prefira a
forma genérica e ajuste o resto da frase pra dar contexto.

### Resultado medido (rodada smoke)

Validador automático (regex word-boundary, case-insensitive) sobre
`feedback_aluno.acertos`, `feedback_aluno.ajustes`,
`feedback_professor.padrao_falha`, `transferencia_c1`, `audit_completo`,
e `feedback_text` (OF14). Banco de termos:
[`smoke_test_missions.py`](../../../backend/notamil-backend/scripts/validation/smoke_test_missions.py)
seção "Validação de vocabulário pedagógico".

| Modo | Termos proibidos no aluno | Diminutivos | Whitelist usada |
|---|:-:|:-:|---|
| `foco_c3` | 0 | 0 | "conclusão", "premissa", "exemplo" presentes |
| `foco_c4` | 0 | 0 | "conclusão", "premissa pragmática", "premissa principiológica", "Palavra do Dia 'mitigar'", "cadeia lógica" presentes |
| `foco_c5` | 0 | 0 | "agente", "finalidade", "detalhamento", "direitos humanos", "proposta de intervenção" presentes |
| `completo_parcial` | 0 | 0 | "tópico frasal", "repertório", "argumento", "coesão", "agente", "ação", "meio", "finalidade" presentes |
| `completo_integral` | 0 | 0 | feedback_text REJ + INEP (esperado, OF14 ensina pleno) |

**Tom verificado por amostra (rodada nova)**:

- Foco_c3 ajuste: *"A conclusão 'o trabalho em equipe é fundamental para
  qualquer projeto complexo' é genérica demais — esse mesmo começo
  funcionaria em qualquer redação sobre qualquer tema. Tente afinar: o
  que, especificamente, o trabalho em equipe garante nesse contexto?"*
  — direto, segunda pessoa, sem "tese" nem condescendência.

- Foco_c4 acerto: *"O uso de 'mitiguei' na Palavra do Dia está preciso:
  redução concreta, com número que dá pra checar."* — substituto exato
  ("número que dá pra checar" no lugar de "dado verificável").

- Foco_c5 ajuste: *"Revise se a ação e o meio estão conectados de forma
  que qualquer leitor consiga visualizar como o programa seria
  executado — pergunte a si mesmo: 'alguém consegue implementar isso
  só lendo minha proposta?'"* — usa pergunta direta como prova de
  qualidade, vocabulário OF12 estrito.

- **Completo_parcial usa o substituto novo:** *"Seu tópico frasal é
  assertivo e tem ponto de vista próprio: você não diz só que 'educação
  é importante', mas que a desigualdade estrutural limita o papel
  transformador dela."* — "ponto de vista próprio" entrou exatamente
  como pedido, no lugar de "recorte temático".

- Completo_parcial argumento: *"O argumento se sustenta porque você
  mostra como a coisa acontece na prática"* — substituto perfeito de
  "mecanismo causal" ("como a coisa acontece na prática").

## Comparação contra rodada anterior (tudo em Opus)

| Modo | Custo Opus (anterior) | Custo otimizado | Redução |
|---|---:|---:|---:|
| `foco_c3` | ~$0.20 | ~$0.02 | **-90%** |
| `foco_c4` | ~$0.20 | ~$0.02 | **-90%** |
| `foco_c5` | ~$0.20 | ~$0.02 | **-90%** |
| `completo_parcial` | ~$0.20 | ~$0.19 | -5% |
| `completo_integral` | ~$1.50 (cold) | ~$0.86 (cache hit) | -43%¹ |

¹ Redução do OF14 vem do cache hit (não da otimização desta sessão);
incluída só pra contexto.

**Qualidade:** validação positiva — Sonnet 4.6 em foco_c3 detectou tese
genérica que Opus 4.7 tinha deixado passar na rodada anterior (texto
"trabalho em equipe é fundamental para qualquer projeto..."). Marcou
`flags.tese_generica=True`, baixou `conclusao` para `adequado`, derivou
`nota_c3_enem=160` (consistente com tabela 8-9 → 160) — schema permitiu
o cap pedagogicamente correto, e o `audit_completo` cita explicitamente
"descritor C3-160" da Cartilha INEP.

## Projeção de custo em escala — 5000 calls/ano

Estimativa baseada na distribuição esperada de uso entre os modos (a
ajustar quando vier dado real de turmas piloto):

| Modo | % uso est. | Calls/ano | $/call | $/ano |
|---|---:|---:|---:|---:|
| Foco (3 modos somados) | 60% | 3000 | $0.02 | $60 |
| Completo Parcial | 20% | 1000 | $0.19 | $190 |
| Completo Integral | 20% | 1000 | $0.86 | $860 |
| **Total otimizado** | 100% | 5000 | — | **~$1110/ano** |
| Total se tudo Opus (baseline) | — | — | — | ~$2300/ano |

**Economia projetada:** ~$1190/ano (~52%) sobre o cenário "tudo Opus".

A maior parcela do custo vem do OF14 (redação completa com
self-critique e ensemble v2), que é a única missão que justifica o
custo do Opus pelo número de competências avaliadas e pela latência
aceitável (90s+) num exercício final de oficina.

## Validações por modo (rodada otimizada)

### `foco_c3` (OF10) — Modo Foco C3 (Sonnet 4.6)

Texto-amostra: parágrafo argumentativo sobre trabalho em equipe, abrindo
com clichê genérico ("...é fundamental para qualquer projeto complexo").

- **rubrica_rej:** `conclusao=adequado, premissa=excelente, exemplo=excelente, fluencia=excelente` → `nota_rej_total=9`
- **nota_c3_enem:** 160 (tabela: 8-9 → 160 ✓)
- **flags:** `tese_generica=True` (Sonnet detectou; Opus tinha deixado passar)
- **audit (126 palavras):** cita Cartilha INEP descritor C3-160 explicitamente, contrasta tese clichê × premissa sólida × exemplo concreto
- **observação:** com a rubrica capturando explicitamente `tese_generica`, modelo menor produziu avaliação mais rigorosa e auditável que Opus em texto-amostra elogiosa demais.

### `foco_c4` (OF11) — Modo Foco C4

Texto-amostra: parágrafo entrevista de emprego com 4 peças (conclusão +
premissa pragmática + premissa principiológica + exemplo) ligadas por
conectivos variados. Inclui palavra do dia "premissa" usada corretamente.

- **rubrica_rej:** todos excelente → `nota_rej_total=12`
- **nota_c4_enem:** 200
- **flags:** todas False
- **feedback_aluno:** vocabulário REJ ("operadores argumentativos", "Palavra do Dia", "cadeia")
- **feedback_professor:** identifica especificamente os conectivos com função lógica precisa

### `foco_c5` (OF12) — Modo Foco C5

Texto-amostra: proposta de intervenção sobre evasão escolar — agente
nomeado (MEC + Secretarias), ação concreta, meio detalhado, finalidade
mensurável (-30% até 2028), articulação explícita à discussão prévia.

- **rubrica_rej:** todos excelente
- **articulacao_a_discussao:** `tematizada` (categoria mais alta)
- **nota_c5_enem:** 200 (consistente — articulação primária OK + qualidade integrada excelente)
- **flags:** todas False (importante: `agente_generico=False` apesar de "o governo" ser uma palavra-chave do detector — o LLM corretamente percebeu que "MEC + Secretarias Estaduais" especifica)
- **feedback_professor:** identifica explicitamente que "Diante do quadro de abandono escolar discutido" é o conector que tematiza articulação

### `completo_parcial` (OF13) — Modo Completo Parcial (Opus 4.7)

Texto-amostra: parágrafo argumentativo completo sobre desigualdade na
educação pública — tópico, argumento com mecanismo causal, repertório
duplo (Inaf 2024 + Paulo Freire), coesão com progressão.

- **rubrica_rej:** `{topico_frasal, argumento, repertorio, coesao} = 3×4` → `nota_rej_total=12`
- **notas_enem:** `{c1: 200, c2: 200, c3: 200, c4: 200, c5: "não_aplicável"}`
- **nota_total_parcial:** 800 (soma C1-C4, sem C5)
- **flags:** todas False
- **audit (312 palavras):** dentro do alvo 200-400.
- **C5 corretamente marcado como string `"não_aplicável"`** — schema valida, app não precisa de fallback heurístico.

### `completo_integral` (OF14) — Pipeline v2 padrão + preâmbulo REJ

Redação completa de 3 parágrafos (~178 palavras) sobre desigualdade na
educação pública. Pipeline v2 inteiro (Opus + flat schema + caps cirúrgicos
+ self-critique).

- **notas:** `{c1: 200, c2: 160, c3: 200, c4: 200, c5: 200}` total **960**
- **schema:** 10 campos v2 presentes (essay_analysis, preanulation_checks,
  c1-c5_audit, priorization, meta_checks, feedback_text)
- **two-stage funcionou:** "c4: LLM said 160, mechanical=200" — derivação
  Python corrigiu a nota do LLM via cap.
- **cache:** 21k tokens write na 1ª chamada, 100% hit no self-critique.
- **preâmbulo REJ assimilado:** o `feedback_text` abre exatamente com
  *"Neste seu primeiro contato com a redação completa do ano..."* — tom
  formativo solicitado no `OF14_REJ_PREAMBLE` foi adotado pelo LLM.

## Coberturas dos detectores Python

Detectores foram acionados na fase pre-LLM mas **nenhum disparou** nas
amostras-base (textos limpos por construção). Validação positiva dos
detectores em texto-controle:

| Detector | Texto-positivo | Disparou? |
|---|---|---|
| `andaime_copiado` | "Conclusão: X. Premissa: Y. Exemplo: Z." | ✓ |
| `andaime_copiado` (negativo) | parágrafo em prosa contínua | ✗ (correto) |
| `conectivo_repetido` | "Além disso ... Além disso ... Além disso" | ✓ |
| `agente_generico` | "O governo deve agir." | ✓ |
| `agente_generico` (com institucional) | "O governo, por meio do MEC..." | ✗ (correto) |
| `verbo_fraco` | "é necessário fazer algo" | ✓ |
| `topico_e_pergunta` | "Por que a educação importa?" | ✓ |

Detectores conservadores por design — preferem falso negativo (LLM ainda
decide) a falso positivo (poluir feedback do aluno). Validação empírica
em uso real é Fase 2 do plano.

## Observações técnicas

1. **`max_tokens=8000`** é o mínimo seguro pros modos foco/parcial. A
   primeira tentativa com `max_tokens=4000` truncou `feedback_aluno` em
   `foco_c3` e `foco_c4` quando o texto-amostra produzia feedback longo
   (acertos elaborados em 3 itens). Subimos pra 8000, consistente com o
   pipeline v2.

2. **Cache TTL=1h** mantido em todos os system prompts dos modos novos —
   cobre rajadas de uma turma inteira na mesma oficina.

3. **`tool_choice` forçado** garante que o Opus/Sonnet invoque a
   ferramenta correta — sem isso, o modelo às vezes responde em texto
   livre.

4. **Roteamento aceita variantes de separador**: `RJ1·OF10·MF·Foco C3`,
   `RJ1_OF10_MF`, `RJ1-OF10-MF`, `RJ1.OF10.MF` são todos aceitos pelo
   `resolve_mode()`. Isso reduz fricção no app.

5. **Sem persistência BQ pros modos foco/parcial** — o entry point
   `grade_mission` retorna o `tool_args` direto, sem passar por
   `_persist_grading_to_bq` (que assume schema v2). Persistência é
   responsabilidade do caller (app).

6. **Variável `REDATO_MISSION_MODEL` é separada de `REDATO_CLAUDE_MODEL`.**
   `REDATO_CLAUDE_MODEL` controla o pipeline v2 do OF14;
   `REDATO_MISSION_MODEL` controla os modos foco/parcial. Isolamento
   deliberado pra que mudanças de modelo no completo integral não afetem
   o custo dos modos formativos do livro.

## O que **não** foi feito (declarado fora de escopo)

- **Validação empírica com turmas reais** — Fase 2 do plano (turmas
  piloto da MVT). Esta sessão é técnica.
- **Chat Redator** — Fase 3, sessão separada.
- **Testes pytest formais** — só smoke test com API real. Adicionar
  unit tests é trabalho de hardening posterior.
- **Endpoint HTTP** — função existe, falta route. Mesma situação do
  `list_pending_reviews` da T11.

## Próximos passos sugeridos

1. **Pytest sobre o roteamento + detectores** (custo zero — sem API).
   Cobre `resolve_mode`, `compute_pre_flags`, `validate_schema`.
2. **Endpoint HTTP** que mapeia POST `/grade_mission` → `_claude_grade_essay`.
3. **Validação com turmas piloto** (Fase 2) — coletar 20-30 redações
   reais por modo, conferir se rubrica REJ e flags batem com o
   julgamento pedagógico do professor.
