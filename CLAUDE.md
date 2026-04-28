# CLAUDE.md — guia rápido pra Claude Code

> Arquivo instructional pra sessões futuras. Lê isso primeiro pra ter mapa
> mental do projeto antes de mexer em código. Detalhes mais profundos em
> `docs/redato/IMPLEMENTATION_GUIDE.md` e `docs/redato/MEMORY/project_redato.md`.

## O que é a Redato

Corretor automático de redações ENEM, parte do programa "Redação em Jogo"
(MVT Educação, ensino médio brasileiro). Avalia textos pelas 5 competências
oficiais do INEP (C1-C5, escala discreta 0/40/80/120/160/200, total 0-1000)
usando Claude (Sonnet 4.6 padrão). Foco pedagógico: assistente do professor,
não substituto.

## Stack

- **Backend:** Python (FastAPI) em `backend/notamil-backend/`. Anthropic SDK
  para grading via tool_use + prompt caching. Dev-offline mode stuba Firebase,
  BigQuery, Firestore e Cloud Functions em memória (`redato_backend/dev_offline.py`).
- **Frontend:** Next.js (App Router) em `frontend/notamil-frontend/`.
- **APIs externas:** Anthropic (`claude-sonnet-4-6` grading, `claude-haiku-4-5`
  preview streaming). Sem dependência GCP em dev.
- **Eval / scripts:** Python em `scripts/` e `backend/notamil-backend/scripts/`.

## Como rodar localmente

Veja `DEV.md` na raiz — fluxo completo (backend, frontend, demo users,
roteiros de validação). Resumo:

```bash
# backend
cd backend/notamil-backend
pip install -r requirements-dev.txt
REDATO_DEV_OFFLINE=1 uvicorn main:app --reload --port 8080

# frontend
cd frontend/notamil-frontend
npm install && npm run dev   # com .env.local apontando pra :8080
```

Demo users (senha `redato123`): `aluno@demo.redato`, `professor@demo.redato`,
`admin@demo.redato`. ANTHROPIC_API_KEY em `backend/notamil-backend/.env`
ativa correção real; sem ela, cai no stub determinístico.

## Variáveis de ambiente importantes

Todas no `backend/notamil-backend/.env` (já no `.gitignore`).

| Variável | Default | O que faz |
|---|---|---|
| `REDATO_DEV_OFFLINE` | `0` | `1` = stuba Firebase/BQ/Firestore em memória, sem GCP. |
| `REDATO_TWO_STAGE` | `1` | `1` = Python deriva notas mecanicamente do audit (elimina bias). |
| `REDATO_SELF_CRITIQUE` | `0` | `1` = 2ª pass do Claude reavalia o audit. +30s, +2× custo. |
| `REDATO_ENSEMBLE` | `1` | N=runs paralelos com majority vote. Use `3` em simulados. |
| `REDATO_REPETITION_FLAG` | `0` | Tarefa 9 revertida — manter `0`. |
| `REDATO_EXTENDED_THINKING` | `0` | `1` = thinking budget de 4k tokens antes do tool. |
| `REDATO_CLAUDE_MODEL` | `claude-sonnet-4-6` | Override do modelo principal. Opus tem bugs conhecidos. |
| `ANTHROPIC_API_KEY` | — | Sem ela, sistema cai no stub determinístico. |

## Mapa do código

```
backend/notamil-backend/
├── redato_backend/
│   ├── dev_offline.py            # ~3500 linhas. Coração do sistema:
│   │                             #   - _claude_grade_essay (entrypoint)
│   │                             #   - _call_claude_with_tool_inner (chamada principal, com cache)
│   │                             #   - _run_self_critique (2ª pass)
│   │                             #   - _merge_ensemble_results (majority vote + _confidence)
│   │                             #   - _derive_cN_nota (derivação mecânica)
│   │                             #   - _persist_grading_to_bq (escreve em essays_graded + correction_review)
│   │                             #   - _SUBMIT_CORRECTION_TOOL (schema audit-first)
│   │                             #   - _FEW_SHOT_EXAMPLES, _GRADING_TAIL_INSTRUCTION
│   │                             #   - _stream_quick_preview (Haiku em paralelo)
│   ├── audits/
│   │   └── lexical_repetition_detector.py   # Tarefa 9 (revertida, infra preservada)
│   ├── ensemble/
│   │   └── confidence.py         # calculate_confidence — high/medium/low + flags
│   ├── routing/
│   │   ├── correction_router.py  # route_correction + HIGH_STAKES_ACTIVITIES
│   │   └── review_queue.py       # list_pending_reviews(teacher_id)
│   ├── shared/constants.py       # Nomes das tabelas BQ (ESSAYS_GRADED_TABLE etc.)
│   └── tests/                    # 17 testes pytest (ensemble + routing)
├── scripts/
│   ├── calibrate_repetition_threshold.py   # Tarefa 9 — calibrador
│   └── ab_tests/                 # run_ab_test_repetition.py + analyze_ab_results.py
└── .env                          # API key + flags

scripts/
└── run_calibration_eval.py       # Eval contra docs/redato/v2/canarios.yaml

docs/redato/
├── IMPLEMENTATION_GUIDE.md       # Guia de tarefas (parcialmente desatualizado)
├── v2/
│   ├── rubrica_v2.md             # Rubrica autoritativa (PDF da corretora-parceira)
│   ├── canarios.yaml             # Golden set: 11 canários + structural_checks
│   ├── IMPLEMENTATION_GUIDE_NEXT.md  # Tarefas 9-12 (T9 revert, T10 pendente, T11/T12 done)
│   ├── AB_TEST_TASK9.md          # Spec do A/B (T9 deu revert)
│   └── teacher_dashboard_mockup.html # Referência visual pro dashboard professor
└── test_set/redacoes_teste_v2.yaml  # 10 redações novas pra validação
```

## Estado atual (2026-04-25)

**Plateau atingido. Infra de qualidade pronta. Frente atual é UX.**

- **INEP**: 9/11 ensemble=3 · 8/11 single+cache · baseline era 6/11
- **STRICT**: 8/11 ensemble · 7/11 single (mesmo plateau histórico)
- **Cache hit ratio**: 100% após warmup. Economia ~74% em input cost.
- **Tarefa 12 (prompt caching)**: ✓ fechada. 2 breakpoints com TTL 1h em
  `_call_claude_with_tool_inner` e `_run_self_critique`.
- **Tarefa 11 (confidence + HITL)**: ✓ fechada. `_merge_ensemble_results`
  anexa `_confidence`; `route_correction` enfileira `pending_review` em
  baixa confiança ou alto stake; `list_pending_reviews()` consulta a fila.
  Bug do self-critique apagando `_confidence` foi corrigido.
- **Tarefa 9 (repetition flag)**: ✗ revertida em A/B (3 canários estáveis
  regrediram por inflação de C4). Infra preservada em
  `redato_backend/audits/` para iteração futura com detector mais
  cirúrgico.
- **Testes**: 17/17 passando em `redato_backend/tests/`.

**Frente atual:** interface de co-correção pra cursinhos parceiros.
Modelo: cursinho recebe uso da plataforma em troca de validação humana
das correções. Pendente: validação com 1-2 cursinhos parceiros pra
entender qual workflow de revisão eles querem antes de desenhar UI.

## Decisões de produto recentes

- **Modo cego é prioritário sobre HITL.** A infra de revisão humana (T11)
  está pronta mas é rede de segurança em simulados de alto stake — não é
  o caminho principal. Foco operacional é manter calibração limpa via
  audit-first + two-stage + ensemble.
- **Não usar correções de outros cursinhos como dataset.** LGPD + IP do
  parceiro. Calibração deriva apenas de canários internos + validação
  pedagógica do cursinho parceiro sobre correções da Redato.
- **Não ampliar calibration set sintético até cursinhos validarem.**
  Adicionar canários sintéticos sem ground truth pedagógico real arrisca
  ossificar o sistema em viés do autor dos canários. Aguardar feedback
  estruturado de cursinho parceiro antes de expandir.
- **2026-04-25 — OCR usa Opus 4.7.** Migrado de Sonnet 4.6 → Opus 4.7
  (`ANTHROPIC_CLAUDE_MODEL` em `shared/constants.py`) baseado em A/B com
  5 redações reais: ganho de 3.2 pts absolutos em palavras incertas
  (Sonnet PT-BR 6.6% → Opus PT-BR 3.4%). Custo 5x aceito porque não há
  produção em volume ainda. Reavaliar quando volume real chegar via
  parceria com cursinhos. Resultados em
  `backend/notamil-backend/scripts/ab_tests/results/ocr_model_ab_results.json`.
- **2026-04-25 — Mudança 4 do OCR (tool_use estruturado) revertida.**
  A/B com n=3 mostrou hipersensibilidade real (Δ=+5.1 pts, Δ/SE=4.5),
  não correlacionada com qualidade da letra — não era information gain
  legítimo. Solução pragmática adotada: `JSONProcessor.extract_json` agora
  usa `json.loads(strict=False)` (aceita control chars não-escapados em
  strings), o que resolve as falhas de parser sem mudar arquitetura.
  Infra do tool preservada em `transcription_blocks.py` + 9 testes
  round-trip — reabrir quando tiver dataset real de cursinhos pra
  re-validar.
- **2026-04-25 — Mudança 5 do OCR fechada. Cloud Vision desligada por
  default.** A/B com 5 redações × 3 configs × n=2 (30 chamadas) mostrou
  que Cloud Vision adicionava +4.3 pts de % uncertain (7.8% pipeline vs
  3.5% solo orig), dobrava variância (σ=5.2 vs 2.0) e triplicava latência
  (~50s vs ~17s). Hipótese: transcripts errados de Cloud Vision injetavam
  ruído no contexto do Claude. Achado adicional: prompt comparativo
  (`VISION_USER_PROMPT`) venceu prompt limpo (`VISION_USER_PROMPT_SOLO`)
  por -1.6 pts em 4/5 redações mesmo sem transcripts reais — mantemos o
  prompt orig. Flag `OCR_USE_CLOUD_VISION=1` reverte ao comportamento
  anterior. Resultados em
  `backend/notamil-backend/scripts/ab_tests/results/ocr_change5_ab.json`.
- **2026-04-25 — Mudança 6 do OCR fechada. Mantém pipeline com 3 versões
  da imagem** (original + pencil-enhanced + pen-enhanced). A/B com 5
  redações × 2 configs × n=3 (30 chamadas) mostrou: 3 imagens ganha +1.7 a
  +2.0 pts uncertain em redações de letra difícil (Carlos 02_08, 05_12-1)
  e empata em letra limpa (Aluna Júlia, Arthur José). Custo $40/mês em
  10k correções e +3.7s latência por correção são proporcionais ao ganho.
  Flag `OCR_USE_ENHANCED_IMAGES=0` reverte se o trade-off mudar.
  Resultados em
  `backend/notamil-backend/scripts/ab_tests/results/ocr_change6_ab.json`.
- **2026-04-26 — Validação estatística da v2 + tentativa frustrada da v3.**
  Eval contra gabarito INEP em 200 redações AES-ENEM revelou v2 com
  **22.8% concordância ±40** e viés sistemático de regressão à média
  (+116 pts em baixas, -150 pts em altas). v3 redesenhada com paradigma
  holístico (Cartilha INEP 2025 + 38 comentários banca, detectores
  binários, 2-layer output). **v3 falhou estruturalmente: ±40 12.0%, MAE
  +79, ME -193 — pior que v2.** Mecanismo: detector
  `argumentacao_previsivel` disparou em 94.5% das redações; flags
  binárias produziram rebaixamento universal. Decisão: v3 revertida,
  artefatos preservados em `docs/redato/v3/_failed/` com
  `README_FAILURE.md` documentando. v2 segue como baseline operacional.
  Código de pipeline v3 mantido como andaime pra v4 (paradigma diferente
  a desenhar).

## Pendências conhecidas

- Endpoint HTTP que expõe `list_pending_reviews()` (função existe, falta route).
- Validação com cursinhos antes de desenhar fluxo de co-correção.
- Atividades não-redação (paragraph_short/full/dense — 33 itens nos livros)
  postergadas até pós-validação com cursinhos.
- Tarefa 10 (two-stage Opus) **congelada**. Reativar somente se A/B
  Sonnet 3.7 vs 4.6 vs Opus 4.7 do plano de OCR mostrar valor que
  justifique custo do Opus em produção (ver
  `docs/redato/v2/OCR_IMPROVEMENT_PLAN.md`).

## Onde encontrar mais contexto

- `docs/redato/MEMORY/MEMORY.md` — índice da memória persistente
  (autoritativo no repo; auto-load do Claude Code lê de
  `~/.claude/projects/.../memory/` via `scripts/sync_memory.sh`).
- `docs/redato/MEMORY/project_redato.md` — contexto profundo do projeto,
  evolução, decisões de arquitetura.
- `docs/redato/IMPLEMENTATION_GUIDE.md` — guia original (algumas tarefas
  desatualizadas, mas filosofia de implementação ainda vale).
- `docs/redato/v2/IMPLEMENTATION_GUIDE_NEXT.md` — Tarefas 9-12 (T9 e T11
  com status atualizado nos comentários do código).
- `docs/redato/v2/OCR_IMPROVEMENT_PLAN.md` — plano de melhorias do
  pipeline OCR (Tier 1 em execução, ver checkpoints).
- `DEV.md` — fluxo completo de rodar local + roteiros de validação.

## Convenções

- Python 3.12. Sem mypy estrito; alguns `# type: ignore` aceitos.
- Testes em `redato_backend/tests/`, rodar com `pytest -o addopts=""`
  (o `setup.cfg` tem opts de coverage de outro projeto).
- Não fazer commit a menos que peçam explicitamente.
- Mexer em `dev_offline.py` exige rodar `scripts/run_calibration_eval.py`
  pra confirmar que não regrediu canários (use `--parallel 2` ou `3`).
- Após editar arquivos em `docs/redato/MEMORY/`, rodar
  `bash scripts/sync_memory.sh` pra atualizar auto-load do Claude Code
  local. Direção sempre repo → local.
