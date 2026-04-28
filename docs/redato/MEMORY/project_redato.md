---
name: Redato project state
description: Redato is an ENEM essay grader. Current state, architecture, eval loop and pending calibration misses. Read this first in new sessions before touching docs/redato/ or scripts/run_calibration_eval.py.
type: project
originSessionId: 2aac15e8-ab4a-4f5b-a65f-357b646e5dea
---
## What Redato is

"Redato" is an AI essay grader for the Brazilian ENEM exam, part of the "Redação em Jogo" program (MVT Educação, ensino médio). Grades on the 5 INEP competencies (C1-C5, discrete scale 0/40/80/120/160/200 each, 0-1000 total).

The work lives in `/Users/danielfrechiani/Desktop/redato_hash/` (called "notamil" in legacy). It's a FastAPI backend + Next.js frontend. In dev-offline mode (`REDATO_DEV_OFFLINE=1`), Firebase/BQ/Firestore/Cloud Functions are all stubbed in memory (see `redato_backend/dev_offline.py`), and Claude grades essays locally via `ANTHROPIC_API_KEY` in `backend/notamil-backend/.env`.

## Current architecture (v2, as of 2026-04-25)

- **Authoritative rubric:** `docs/redato/v2/rubrica_v2.md` (PDF da corretora-parceira + correção Tensão 3). Replaced v1 `docs/redato/redato_system_prompt.md` (kept only for fallback).
- **System prompt base** (in `dev_offline.py`): persona block + v2 rubric, loaded at module import. ~13k chars.
- **Few-shots:** 3 worked examples in `_FEW_SHOT_EXAMPLES`, cached alongside the system prompt.
- **Tool schema** (`_SUBMIT_CORRECTION_TOOL`): audit-first, forces `preanulation_checks`, `c1_audit.threshold_check` (6 booleans), `c2_audit.theme_keywords_by_paragraph`, `c5_audit.elements_present` with 5 boolean elements, `meta_checks.no_competency_bleeding`.
- **BQ mapping:** `_persist_grading_to_bq` projects audit output into the stubbed `essays_graded / essays_detailed / essays_errors` tables. If `preanulation_checks.should_annul=true`, all 5 notas go to 0.
- **Preview streaming:** `_stream_quick_preview` runs Haiku in parallel with the main Sonnet call to emit a short "first impression" in Firestore in ~3s (see `job_tracker.append_preview`).
- **Opt-in flags:** `REDATO_SELF_CRITIQUE=1` (adds +30s 2nd pass), `REDATO_EXTENDED_THINKING=1`, `REDATO_CLAUDE_MODEL=claude-opus-4-7`.

## Calibration eval loop

- **Golden set** (canários used as few-shots): `docs/redato/v2/canarios.yaml` — 11 entries.
- **Test set** (new essays, NOT in prompt): `docs/redato/test_set/redacoes_teste_v2.yaml` — 10 entries.
- **Runner:** `scripts/run_calibration_eval.py` — accepts `--canarios <path>`, `--only <id>`, `--baseline`, `--compare <json>`, `--no-fail`, `--parallel N`.
- **Exit code 1** when ≥ 2 canários fail. Tolerance: ±40 per competency + per-canário `structural_checks` (kinds defined in `_run_structural_check`).

## Last measured state (2026-04-25, post-Tarefas 11/12)

- **Golden set v2 INEP**: **9/11 ensemble**, 8/11 single+cache, baseline 6/11.
- **Cache hit ratio**: 100% após warmup em todas chamadas (16.559 tokens cacheados, ~74% economia em input cost).
- Test set v2 (anterior): INEP 9/10 — não rerodado pós-cache, mas
  comportamento esperado é estável ou melhor (cache não muda output).
- Falhas INEP residuais: `c3_no_project`, `c3_weak_project_strong_repertoire`
  (drift -80 em c4 — bias persistente que ensemble e cache não resolvem).

## Tarefas concluídas em 2026-04-25 (sprint pós-plateau)

- **Tarefa 12 — Prompt caching**: 2 cache breakpoints com TTL 1h em
  `_call_claude_with_tool_inner` (`dev_offline.py:2353`) e
  `_run_self_critique` (`dev_offline.py:3055`). Helper de logging
  `_log_cache_metrics` sem PII. Economia medida: ~74% em input cost
  ($0.053 → $0.014/call).
- **Tarefa 11 — Confidence + HITL**:
  - `redato_backend/ensemble/confidence.py` — `calculate_confidence()`
    classifica em high/medium/low, anexado em `_merge_ensemble_results`
    quando N ≥ 2.
  - `redato_backend/routing/correction_router.py` — `route_correction()`
    + `HIGH_STAKES_ACTIVITIES` (RJ1-OF14, RJ2-OF13, RJ3-OF01, SIM1, SIM2,
    SIMFINAL1, SIMFINAL2 etc.).
  - `redato_backend/routing/review_queue.py` — `list_pending_reviews(teacher_id)`
    com filtragem e ordenação por `created_at desc`.
  - Persistência: `essays_graded` ganhou `review_state` +
    `confidence_metadata`; nova tabela `correction_review` em
    `shared/constants.py:CORRECTION_REVIEW_TABLE`.
  - **Bug fix**: `_run_self_critique` apagava `_confidence`. Captura
    `_confidence` antes do critique e re-anexa depois
    (`dev_offline.py:2502-2506`).
- **Tarefa 9 — Repetition flag**: REVERT em A/B (exit code 2). Default
  `REDATO_REPETITION_FLAG=0`. Detector preservado em
  `redato_backend/audits/lexical_repetition_detector.py` para iteração
  futura com detector mais cirúrgico (blacklist de palavras-chave do tema
  ou foco em conectores).
- **Total de testes unitários**: 17/17 passando em `redato_backend/tests/`.

## Decisões de produto (2026-04-25)

- **Modo cego é prioritário sobre revisão humana**: a infra de HITL
  (Tarefa 11) está pronta mas não é o caminho principal. Foco operacional
  é manter calibração limpa (audit-first + two-stage + ensemble) e usar
  HITL apenas como rede de segurança em simulados de alto stake.
- **Parceria com cursinhos via troca**: cursinhos parceiros recebem uso
  da plataforma em troca de validação humana das correções. Modelo
  permite escala de validação sem custo direto.
- **Frente atual: interface de co-correção para cursinhos parceiros** —
  professor do cursinho revisa correção da Redato lado a lado com o
  texto do aluno e marca aprovação/divergência. UI ainda não desenhada;
  validar fluxo com cursinhos antes de implementar.

## Pendências (2026-04-25)

- **Endpoint HTTP de `list_pending_reviews`**: a função Python existe e
  está testada, mas não está exposta via FastAPI route. Aguarda
  definição da UI de co-correção.
- **Validação com cursinhos antes de desenhar fluxo de co-correção**:
  conversar com 1-2 cursinhos parceiros pra entender qual workflow de
  revisão eles querem (lado a lado? cards? lista?) antes de gastar
  tempo em frontend.
- **Atividades não-redação (paragraph_short/full/dense)**: catálogo
  inspecionado em `/tmp/redato_files/` (33 atividades dos livros RJ1/2/3),
  integração postergada — depende de validação com cursinhos primeiro.
  - Critério **INEP** (drift ±40 por competência, critério oficial ENEM que
    define quando 2 corretores humanos concordam) — este é o que importa
    para operação em produção.
  - Critério **STRICT** (INEP + structural_checks internos que tentam pegar
    viés específicos) — diagnóstico de calibração, não gate de produção.
  - Progressão: 2/10 INEP → 4/10 → 6/10 → 8/10 STRICT → **9/10 INEP**
    (descobrimos tardiamente que estávamos aplicando critério mais duro
    que o oficial ENEM).
  - Two-stage + self-critique + 5 few-shots levam Sonnet 4.6 a estar
    DENTRO DA TOLERÂNCIA ENEM em 90% das redações-teste. Única falha
    INEP: teste_04 com c3 drift −80.

## Key architectural decision: two-stage mechanical scoring

`REDATO_TWO_STAGE=1` (default ON) makes Python derive the 5 notas mechanically from
Claude's audit fields, overriding Claude's own `audit.nota` field. Functions:
`_derive_c1_nota`, `_derive_c2_nota`, `_derive_c3_nota`, `_derive_c4_nota`,
`_derive_c5_nota` in `dev_offline.py`.

This eliminates LLM scoring biases (propagation, criticism) because each competency's
nota depends ONLY on its own audit — not on other competencies' notas. The LLM's
remaining job is the audit (counting, identifying, marking booleans); Python does the
arithmetic.

Trade-off: if Claude fills the audit wrongly (ex.: claims `has_explicit_thesis=true`
when there's no thesis), the nota is wrong — but the error is isolated to the audit
field and easy to diagnose.

C3 derivation uses a scoring-based map (count positives, subtract penalties) rather
than a strict ladder — more forgiving, aligned with PDF gabaritos.

## Defaults in backend/.env

```
REDATO_SELF_CRITIQUE=1   # +30s, second pass on the audit
REDATO_TWO_STAGE=1       # Python derives notas from audit
```

To roll back any: set to `0`.

## Calibration misses — STATUS post-two-stage

**Resolved:**
- ✅ Propagação inversa — two-stage fixed it. Competency isolation is guaranteed mechanically.
- ✅ Tangenciamento sutil — few-shot about "O Dilema das Redes" (palavra-chave em nome próprio) + mechanical C2=40 rule.
- ✅ C5 elements implícitos — rule forces `present: false` unless literal quote exists.
- ✅ AttributeError bug — `_dict_or_empty` guards in `_persist_grading_to_bq`.

**Persistent (plateau — 4-5 failing out of 10):**

The remaining failures all stem from **Claude's audit non-determinism** — same
essay, different run, different boolean flags. The two-stage architecture
correctly derives the nota from the audit, but the audit input itself varies.

1. **teste_01 / teste_05** criticism bias: C1=160 and/or C4=160 on impeccable texts.
   Claude's audit marks `threshold_check.applies_nota_4=true` when the counts
   warrant `applies_nota_5`. Cannot be fixed by rules alone — the flag IS wrong.
2. **teste_03** audit quality: Claude sometimes sees thesis where there is none.
   New rules about "descrição × tese argumentativa" helped on some runs but
   Claude still flips flags across runs.
3. **teste_04** audit quality: Claude sometimes counts lexical repetition as C1
   grammar errors or marks `ideias_progressivas=false` because of C4 repetition.
4. **teste_07** audit variance: C3 oscillates between 120 and 180 depending on
   whether Claude marked `conclusion_retakes_thesis` / `has_thesis` consistently.

Next-level fixes would require:
- Running multiple passes per essay and taking majority vote (cost 3-5x)
- ~~Switching to Opus 4.7~~ — tested 2026-04-24, REGRESSED to 2/10.
  Opus returns placeholder `{"$PARAMETER_NAME": ...}` as tool_use input on
  several essays, likely because the v2 schema is too deep/nested for its
  tool-use handling. To make Opus work: flatten schema + raise max_tokens
  to 12k+ + consider removing forced tool_choice. Not worth the cost/effort.
  **Sonnet 4.6 is the production choice.**
- Adding MANY more few-shots (currently 5; 10-15 might stabilise)

The architecture (audit-first + mechanical derivation) is sound. The plateau
is a model / non-determinism issue, not a design issue.

## Deployment strategy (decisão do usuário 2026-04-24)

- **Oficinas diárias / exercícios menores**: Sonnet 4.6 + two-stage +
  self-critique (padrão atual). Custo US$ 0,06/redação, ~2min, INEP 80-90%
  (oscila entre runs).
- **Simulados / provas finais**: ensemble disponível via `REDATO_ENSEMBLE=3`
  (ou maior). Implementado em `_merge_ensemble_results` — majority vote nos
  booleans, mediana nos counts, união deduplicada nas listas. Detecta e
  descarta placeholders do Opus (`$PARAMETER_NAME`).
  - **Custo**: N× o single-run. Para Sonnet: ~US$ 0,18/redação. Para Opus:
    ~US$ 0,90/redação.
  - **Tempo**: paralelo, então ~o tempo do run mais lento (não soma).
  - **Limitação descoberta**: ensemble resolve VARIÂNCIA, não BIAS. Em
    teste_04 e teste_03 do test set, Claude tem bias sistemático nos
    audits (flag thesis/planejamento de forma errada SEMPRE). Ensemble
    de 3 runs não muda — todos os 3 cometem o mesmo erro. Ensemble vale
    pena quando o problema é variância entre runs, não viés cognitivo.

## Plateau final (2026-04-24)

- **INEP**: 8-9/10 (oscila entre runs).
- **STRICT**: 6-8/10.
- Iterações finais (5º few-shot, regras estritas, refinamentos C3) não
  ultrapassaram este patamar — limite é a qualidade do audit do Claude,
  não da derivação Python.
- 4-5/10 das redações são ESTÁVEIS no patamar (sempre passam): teste_01,
  teste_02, teste_06, teste_07, teste_08, teste_09, teste_10.
- 1 redação é estável FORA: teste_04 (bias persistente em C3 — Claude
  interpreta repetição lexical como falta de progressão).
- 1 redação OSCILA: teste_03 (às vezes Claude vê tese, às vezes não).

## Validação estatística + tentativa v3 (2026-04-26)

Frente A do roadmap pós-OCR. Validou v2 contra 200 redações AES-ENEM com
gabarito INEP. Setup: `scripts/validation/` (build_validation_sets.py,
run_validation_eval.py, compare_v2_v3.py). Stratificação dupla
(fonte × faixa) no real-world set (200 BE+UOL+EBR), single (banda) no
gold (200 AES-ENEM).

**Baseline v2 medido:** 22.8% concordância ±40, MAE 137.8, ME -62.
Viés sistemático: +116 pts em redações ≤400, -150 em ≥800. Diagnóstico
em `scripts/validation/diagnostic/SUMMARY.md` (10 redações com viés
extremo, audit completo + derivação isolada): two-stage Python NÃO causa
o viés (deriv == final em 100% dos casos). Audit do LLM é a fonte —
super-conta erros em redações boas, sub-conta em ruins.

**v3 holística — REVERTIDA:** redesenho baseado em Cartilha INEP 2025 +
38 comentários banca + detectores binários (`tangenciamento`,
`argumentacao_previsivel`, `repertorio_de_bolso`, etc.). Eval mostrou
**12% concordância ±40** (pior que v2). `argumentacao_previsivel`
disparou em 94.5% das redações, rebaixando tudo. Mecanismo do fracasso:
detectores binários para juízo holístico = mecânica disfarçada.
Artefatos preservados em `docs/redato/v3/_failed/` com `README_FAILURE.md`.
Código de pipeline v3 (branches `REDATO_RUBRICA=v3` em `dev_offline.py`,
`_SYSTEM_PROMPT_V3`, `_SUBMIT_CORRECTION_V3_TOOL`, schema auto-detect em
`run_validation_eval.py`) mantido como andaime pra v4. Lições anotadas
no README_FAILURE pra evitar mesmo paradigma na v4.

**Eval real-world (Brasil-Escola + UOL + Essay-BR) NÃO foi rodado** —
pausado indefinidamente após falha estrutural da v3. Voltar quando v4
existir.

## OCR pipeline (2026-04-25)

- Modelo atual: `claude-opus-4-7` em `shared/constants.py:ANTHROPIC_CLAUDE_MODEL`.
  Migrado de Sonnet 3.7 (deprecated, 404) → Sonnet 4.6 → Opus 4.7
  (A/B com 5 redações: -3.2 pts vs Sonnet 4.6 PT-BR).
- Frontend: resize 1800px max + JPEG 0.92 em
  `frontend/notamil-frontend/app/submit-essay/ocr/page.tsx:130,155`.
- Prompt em PT-BR com seções `<atencao_especial_portugues>` +
  `<confusoes_comuns_manuscritas>` (Mudança 2). Mantém formato JSON com
  tags XML embedded.
- `JSONProcessor.extract_json` usa `strict=False` por padrão pra aceitar
  control chars não-escapados que o modelo emite (sem isso, ~todas as
  redações falham parse).
- `temperature=0` removido pra Opus 4.x (deprecado nesse modelo, retorna
  400). Lógica condicional em `anthropic_vision.py:_call_vision_api`.
- Mudança 4 (tool_use estruturado) foi avaliada e revertida em 2026-04-25 —
  induzia hipersensibilidade (Δ=+5.1 pts incerto, Δ/SE=4.5, n=3 confirmado).
  Infra preservada em `transcription_blocks.py` + 9 testes round-trip
  pra retomada futura com dataset real de cursinhos.
- Mudança 5 (Cloud Vision sim/não) fechada em 2026-04-25 — Cloud Vision
  removida do pipeline default via flag `OCR_USE_CLOUD_VISION=0` em
  `shared/constants.py`. A/B (5 redações × 3 configs × n=2) mostrou que CV
  adicionava +4.3 pts de uncertain, dobrava variância e triplicava latência.
  Pipeline atual: 3 imagens enhanced (original/pencil/pen) → Claude com
  `VISION_USER_PROMPT` (transcript vazio). Setar flag=1 reverte. Prompt
  comparativo venceu prompt limpo (`VISION_USER_PROMPT_SOLO`) — orig
  mantido, SOLO marcado UNUSED em `prompts.py`.
- Mudança 6 (3 enhanced vs 1 original) fechada em 2026-04-25 — mantidas
  3 versões enhanced. A/B (5 × 2 × n=3) mostrou +1.7 a +2.0 pts em letra
  difícil, empate em letra limpa. Custo (~$40/mês a 10k correções e +3.7s
  latência) proporcional ao ganho. Flag `OCR_USE_ENHANCED_IMAGES=0` é
  rollback (default `1`). `ProcessedImage` ganhou campos pencil/pen
  opcionais pra suportar o caminho de 1 imagem.

## Estado consolidado do OCR (Tier 1+2 fechado, 2026-04-25)

| # | Mudança | Status | Ganho |
|---|---|---|---|
| 1 | Frontend resize 1800px JPEG 0.92 | ✅ aplicada | mais detalhe, +1-2s upload |
| 2 | Prompt PT-BR (acentos + confusões manuscritas) | ✅ aplicada | -5.2 pts uncertain |
| 3 | Modelo Sonnet 3.7 (deprecated) → Opus 4.7 | ✅ aplicada | -3.2 pts adicionais |
| 4 | Tool call estruturado | ❌ revertida (hipersensibilidade); infra preservada em `transcription_blocks.py` + 9 testes round-trip | — |
| 5 | Cloud Vision removida | ✅ aplicada | -4.3 pts, -3× latência, -3 chamadas/correção |
| 6 | 3 imagens enhanced mantidas | ✅ decidido | melhor em letra difícil, $40/mês + 3.7s extra |

Pipeline final em produção (default flags):
- Frontend → 1800px JPEG 0.92 → backend
- `AnthropicVisionAgent`: 3 versões enhanced (original/pencil/pen)
- Claude Opus 4.7 com `VISION_SYSTEM_PROMPT` (PT-BR) + `VISION_USER_PROMPT`
  (transcript vazio porque `OCR_USE_CLOUD_VISION=0`)
- `JSONProcessor.extract_json` com `strict=False` (resolve control chars
  não-escapados)
- Sem Cloud Vision, sem tool_use estruturado.

Flags de rollback (todas no `.env`, default OFF/comportamento ideal):
- `OCR_USE_CLOUD_VISION=1` → reabilita Cloud Vision (Mudança 5 reverter)
- `OCR_USE_ENHANCED_IMAGES=0` → só imagem original (Mudança 6 reverter)

## Files most often touched during calibration work

- `backend/notamil-backend/redato_backend/dev_offline.py` — schema, few-shots, BQ mapping. Big file (~2500 lines).
- `docs/redato/v2/rubrica_v2.md` — authoritative prompt.
- `docs/redato/v2/canarios.yaml` — golden set + structural_checks.
- `docs/redato/test_set/redacoes_teste_v2.yaml` — test set + structural_checks.
- `scripts/run_calibration_eval.py` — eval runner.

## Loop operacional (unchanged)

```
Revisor pega miss em produção
 → Adiciona canário ao golden ou test set (with structural_checks)
 → run_calibration_eval.py --only <id>   confirms it fails
 → Patch rubric / few-shots / schema
 → run_calibration_eval.py             confirms delta positive without regressions
 → Commit canário + patch together
```

## Running locally (dev-offline)

```bash
cd /Users/danielfrechiani/Desktop/redato_hash/backend/notamil-backend
REDATO_DEV_OFFLINE=1 uvicorn main:app --reload --port 8080
# frontend: cd frontend/notamil-frontend && npm run dev
```

Demo users (password `redato123`): `aluno@demo.redato`, `professor@demo.redato`, `admin@demo.redato`.

Full dev docs: `DEV.md` at repo root.
