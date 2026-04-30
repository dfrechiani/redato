# MIGRATION_FT_OF14_AUDIT — análise de regressão antes de migrar OF14 pro FT

**Data:** 2026-04-30
**Status:** investigação concluída, decisão pendente.
**Pré-leitura:** [`scripts/ab_models/results/REPORT_FT_AUDIT_20260430_163823.md`](../../../scripts/ab_models/results/REPORT_FT_AUDIT_20260430_163823.md) (experimento prompt-enriched 30/abr).

## TL;DR

- **22 campos** do schema OF14 v2 foram analisados (12 por `cN_audit` × 5 + 4 top-level únicos).
- **Migração para FT-with-audit subset não regride o frontend primário em prod (`redato_frontend`).**
  Apenas `cN_audit.nota` é consumido por essa stack; o FT retorna esse campo. Os outros 21 campos
  já renderizam vazios ou inexistem na UI atual de OF14.
- **Migração regride frontend legacy (`frontend/notamil-frontend`)**, que consome
  `competencies[].{justification, errors, detailed_analysis}` da rota `/essays/result/...`.
  Esses campos são gerados por `_build_competency_justification` + `_errors_from_audit`
  consumindo ~25 campos detalhados de `cN_audit` que o FT subset não retorna.
- **`frontend/notamil-frontend` está sem commits desde o initial commit `aa8fb20`** —
  presumivelmente legacy não-mantido, mas pode estar deployado em algum ambiente.
- **Recomendação principal: MIGRAR DIRETO**, condicionada a confirmação de que
  `frontend/notamil-frontend` não está em produção viva.
  - Se confirmado: gap = 0 campos ativos perdidos. Migrar e opcionalmente adicionar render
    de `cN_audit.feedback_text` + `cN_audit.evidencias` no portal pra ganhar info nova.
  - Se notamil-frontend ainda for usado por algum aluno/professor: **RE-TREINAR** o FT
    pra retornar schema v2 completo (gap > 7 campos críticos), ou manter Claude pra
    OF14 enquanto desativa legacy.

---

## Contexto

Experimento `run_ft_with_audit.py` (timestamp 20260430_163823) confirmou que o
FT BTBOS5VF, com prompt enriquecido pedindo audit estruturado, gera:

```jsonc
{
  "c1_audit": {"nota": 0|40|80|120|160|200, "feedback_text": str, "evidencias": [{"trecho": str, "comentario": str}]},
  "c2_audit": { ... mesmo schema ... },
  "c3_audit": { ... },
  "c4_audit": { ... },
  "c5_audit": { ... }
}
```

Métricas:

- **±40%:** 28.5% (vs 21.5% do baseline FT só notas, vs 19.3% do Claude prod no A/B 30/abr).
- **parse_status=ok:** 100%.
- **Custo:** $0.05/redação. **Latência:** 13.8s.
- 5 amostras qualitativas julgadas "audit útil" por leitura humana.

Schema OF14 v2 atual (Claude prod via `_SUBMIT_CORRECTION_FLAT_TOOL` em
`backend/notamil-backend/redato_backend/dev_offline.py:2218-2367`) é **muito mais rico**:
12+ campos por `cN_audit` + 4 blocos top-level (`essay_analysis`, `preanulation_checks`,
`priorization`, `meta_checks`) + `feedback_text` solto.

A pergunta deste documento: **o que se perde se OF14 passar a retornar apenas o
subset do FT?** Ou seja: cada um dos 22 campos do schema v2 é realmente consumido?

---

## Mapa de consumo: 2 stacks consumindo 2 rotas diferentes

```
                                            ┌─────────────────────────────────────────┐
backend/notamil-backend/                    │  Stack PRIMÁRIA (prod ativo)            │
redato_backend/portal/portal_api.py         │  redato_frontend/                       │
┌─────────────────────────────┐             │  Server Components Next.js (App Router) │
│ GET /portal/atividades/.../ │ ───────────▶│                                         │
│      envios/{id}            │             │  Renderiza:                             │
│                             │             │   - nota_total                          │
│ Helpers extraem do tool_args:│             │   - faixas[] (cN_audit.nota)            │
│  • _competencias_de         │             │   - analise_da_redacao (vazio em OF14)  │
│    └─ cN_audit.nota         │             │   - detectores (vazio em OF14)          │
│  • _analise_da_redacao_de   │             │   - raw_output (passthrough, INERTE)    │
│    └─ feedback_professor    │             │                                         │
│       (não existe em OF14!) │             │  0 referências a c[1-5]_audit           │
│  • _detectores_acionados_de │             │  em qualquer .tsx do prod ativo.        │
│    └─ flags (não existe!)   │             └─────────────────────────────────────────┘
└─────────────────────────────┘
                                            ┌─────────────────────────────────────────┐
backend/notamil-backend/                    │  Stack LEGACY (status: incerto)         │
redato_backend/                             │  frontend/notamil-frontend/             │
┌─────────────────────────────┐             │  último commit: aa8fb20 (initial)       │
│ GET /essays/result/essay/   │ ───────────▶│                                         │
│       {id}                  │             │  Páginas que consomem:                  │
│                             │             │   - /correcao/page.tsx                  │
│ get_analysis_from_bq() lê   │             │   - /professor/correcao-professor/      │
│ tabelas projetadas por:     │             │   - /components/CorrecaoProfessorModal  │
│  • _build_competency_       │             │   - /study-plan/                        │
│    justification            │             │   - /submit-essay/text/                 │
│    └─ desvios_count, ...    │             │   - /submit-essay/ocr/                  │
│  • _errors_from_audit       │             │                                         │
│    └─ desvios array, ...    │             │  Renderiza:                             │
│                             │             │   - competencies[].grade                │
│ Output:                     │             │   - competencies[].justification        │
│  competencies: [{           │             │   - competencies[].errors[]             │
│    grade,                   │             │   - detailed_analysis                   │
│    justification,           │             │                                         │
│    errors: [...],           │             │  Esses 4 campos vêm do BQ via helpers   │
│  }]                         │             │  que LEEM ~25 campos detalhados de      │
│  detailed_analysis          │             │  cN_audit v2.                           │
└─────────────────────────────┘             └─────────────────────────────────────────┘
```

**Achado central:** as duas stacks consomem rotas diferentes com formatos diferentes.

- `redato_frontend` (prod) usa `_competencias_de`, `_analise_da_redacao_de`,
  `_detectores_acionados_de` — todos ignoram quase tudo do schema v2 detalhado.
- `frontend/notamil-frontend` (legacy) usa `_build_competency_justification`,
  `_errors_from_audit` — esses sim leem dezenas de campos do schema v2.

---

## Tabela 1 — Campos `cN_audit` (12 por competência × 5)

Cada linha é um campo individual de `cN_audit` (replica nos 5 blocos C1-C5).

| Campo | redato_frontend (prod) | notamil-frontend (legacy) | Backend `_derive_notas_mechanically` | Backend `_build_justif`/`_errors_from_audit` | Status |
|---|---|---|---|---|---|
| `nota` | ✅ Renderiza badges | ✅ `competencies[].grade` | ✅ Output da derivação | ✅ Persiste em BQ | **UI ATIVA — crítico** |
| `desvios_gramaticais` (array) | ❌ | ✅ via `errors[]` | ❌ | ✅ `_errors_from_audit:3109` | **UI ATIVA (legacy)** |
| `desvios_gramaticais_count` | ❌ | ✅ via `justification` | ✅ C1 fallback `dev_offline.py:3215` | ✅ `_build_justif:3054` | **UI ATIVA (legacy) + lógica backend** |
| `erros_ortograficos_count` | ❌ | ✅ via `justification` | ✅ C1 fallback | ✅ `_build_justif:3056` | **UI ATIVA (legacy) + lógica backend** |
| `desvios_crase_count` | ❌ | ✅ via `justification` | ✅ C1 fallback | ✅ `_build_justif:3057` | **UI ATIVA (legacy) + lógica backend** |
| `desvios_regencia_count` | ❌ | ✅ via `justification` | ❌ | ✅ `_build_justif` | **UI ATIVA (legacy)** |
| `falhas_estrutura_sintatica_count` | ❌ | ✅ via `justification` | ❌ | ✅ `_build_justif` | **UI ATIVA (legacy)** |
| `marcas_oralidade` (array) | ❌ | ✅ via `errors[]` | ✅ C1 `dev_offline.py:3218` | ✅ `_errors_from_audit:3120` | **UI ATIVA (legacy) + lógica backend** |
| `reincidencia_de_erro` (bool) | ❌ | ❌ | ❌ | ❌ | **Schema-only — código morto** |
| `reading_fluency_compromised` (bool) | ❌ | ❌ | ❌ | ❌ | **Schema-only — código morto** |
| `threshold_check.applies_nota_0..5` | ❌ | ✅ via `justification` (lista chaves true) | ✅ C1 primary `dev_offline.py:3201-3212` | ✅ `_build_justif:3060-3063` | **UI ATIVA (legacy) + lógica backend crítica (capping)** |

**Repete pra C2-C5 com campos análogos.** Cada competência tem campos próprios:

- **C2:** `repertoire_references[]` (legitimacy, productivity), `fuga_total_detected`, `tangenciamento_detected`, `tres_partes_completas`, `partes_embrionarias_count`, `has_reference_in_d1/d2`, `copia_motivadores_sem_aspas`, `conclusao_com_frase_incompleta`, `has_false_attribution`, `has_unsourced_data`, `has_wrong_legal_article`. **Todos lidos por `_derive_c2_nota` (3236-3270) + `_build_justif` (3065-3076) + `_errors_from_audit` (3127-3136).**
- **C3:** `has_explicit_thesis`, `ponto_de_vista_claro`, `ideias_progressivas`, `planejamento_evidente`, `autoria_markers[]`, `encadeamento_sem_saltos`, `argumentos_contraditorios`, `informacoes_irrelevantes_ou_repetidas`, `limitado_aos_motivadores`, `conclusion_retakes_thesis`. **Todos lidos por `_derive_c3_nota` (3294-3304) + `_build_justif` (3078-3082).**
- **C4:** `most_used_connector_count`, `connector_variety_count`, `has_mechanical_repetition`, `complex_periods_well_structured`, `coloquialism_excessive`, `ambiguous_pronouns[]`, `paragraph_transitions[]`. **Todos lidos por `_derive_c4_nota` (3376-3387) + `_build_justif` (3085-3088) + `_errors_from_audit` (3138-3157).**
- **C5:** `respeita_direitos_humanos`, `elements_present` (agente/acao/modo_meio/finalidade/detalhamento), `proposta_articulada_ao_tema`. **Todos lidos por `_derive_c5_nota` (3432-3449) + `_build_justif` (3094-3097) + `_errors_from_audit` (3158-3175).**

---

## Tabela 2 — Campos top-level

| Campo | redato_frontend (prod) | notamil-frontend (legacy) | Backend | Status |
|---|---|---|---|---|
| `feedback_text` (string única OF14) | ❌ | ✅ via `detailed_analysis` (concatenado) | ✅ `_persist_grading_to_bq:2964-2965` | **UI ATIVA (legacy)** |
| `essay_analysis` (theme_keywords, word_count, paragraph_count, title_*) | ❌ | ❌ | ❌ apenas persistido em BQ | **Schema-only — código morto** |
| `preanulation_checks.should_annul` | ❌ | indireto (zera notas) | ✅ `_persist_grading_to_bq:2941-2942` | **Lógica backend** |
| `preanulation_checks.motivo_anulacao` | ❌ | ❌ | ❌ não-lido | **Schema-only — código morto** |
| `priorization.priority_1/2/3` (entrada/impacto/diagnostico) | ❌ | ✅ via `detailed_analysis` (renderizado em texto) | ✅ `_persist_grading_to_bq:2967-2983` | **UI ATIVA (legacy)** |
| `meta_checks` (total_calculated, no_competency_bleeding, etc.) | ❌ | ❌ | ❌ apenas persistido em BQ | **Schema-only — código morto** |

---

## Tabela 3 — Gap entre FT subset e v2 completo (por consumidor)

### Para `redato_frontend` (stack primária prod)

| Campo v2 | FT subset entrega? | UI consome? | Impacto da migração |
|---|---|---|---|
| `cN_audit.nota` | ✅ sim | ✅ sim | ✅ Sem regressão |
| `cN_audit.feedback_text` | ✅ sim (NOVO) | ❌ não consome | 🆕 Info nova disponível pra adicionar render no futuro |
| `cN_audit.evidencias` | ✅ sim (NOVO) | ❌ não consome | 🆕 Info nova disponível pra adicionar render no futuro |
| Todos os 12+ campos detalhados de `cN_audit` (desvios, threshold_check, etc.) | ❌ não | ❌ não consome | ✅ Sem regressão (já não renderiza) |
| `feedback_professor` (M9.4 estruturado) | ❌ não (FT também não tem) | ✅ procura mas não acha | ⚖️ Igual ao atual (já vazio em OF14 hoje) |
| `flags` | ❌ não (FT também não tem) | ✅ procura mas não acha | ⚖️ Igual ao atual (já vazio em OF14 hoje) |
| `essay_analysis`, `preanulation_checks`, `priorization`, `meta_checks` | ❌ não | ❌ não consome | ✅ Sem regressão |

**Conclusão pra redato_frontend:** **gap = 0 campos ativos perdidos**.
A migração mantém tudo que o portal renderiza hoje pra OF14 e adiciona 2 campos
novos (`feedback_text` por competência, `evidencias` por competência) que poderiam
ser usados no futuro.

### Para `frontend/notamil-frontend` (stack legacy)

| Campo v2 | FT subset entrega? | UI consome? | Impacto da migração |
|---|---|---|---|
| `cN_audit.nota` | ✅ sim | ✅ via `competencies[].grade` | ✅ Sem regressão |
| `desvios_gramaticais` array | ❌ | ✅ via `competencies[].errors[]` | ❌ Erros viram lista vazia |
| `desvios_gramaticais_count`, `erros_ortograficos_count`, ... | ❌ | ✅ via `justification` (texto sintetizado) | ❌ Justification fica genérica |
| `marcas_oralidade`, `repertoire_references`, `ambiguous_pronouns`, `paragraph_transitions`, `elements_present` | ❌ | ✅ via `errors` + `justification` | ❌ Mesma regressão |
| `threshold_check` | ❌ | ✅ indireto via `justification` (lista chaves true) | ❌ Justification perde a "razão da nota" |
| Todos os outros 25+ campos de `cN_audit` lidos pelo backend | ❌ | ✅ indireto via texts gerados | ❌ Geração de texts vira degradada |
| `feedback_text` solto | ✅ sim (mas POR competência, não top-level) | ✅ via `detailed_analysis` | ⚠️ Schema diferente — precisaria mapper |
| `priorization` | ❌ | ✅ via `detailed_analysis` | ❌ Sem priorities |

**Conclusão pra notamil-frontend:** **gap > 25 campos ativos perdidos**, incluindo
threshold_check (crítico — explica por que a nota é o que é). Migrar sem retreino
**regride severamente** essa stack.

---

## Tabela 4 — Status mecânico por critério do briefing

Critérios definidos no briefing original:

- gap < 3 campos ativos → **MIGRAR direto**
- gap 3-7 campos → **MIGRAR + abrir pendência pra recuperar**
- gap > 7 campos OU campo crítico → **RE-TREINO**

| Stack | Gap (UI ativa) | Recomendação mecânica |
|---|---|---|
| `redato_frontend` (prod ativo) | **0** campos | **MIGRAR direto** |
| `frontend/notamil-frontend` (legacy) | **>25** campos (incl. threshold_check crítico) | **RE-TREINO ou descontinuar legacy** |

---

## Decisão sugerida

A decisão depende de uma pergunta operacional: **`frontend/notamil-frontend` está
em produção viva pra algum usuário?**

### Cenário A — `frontend/notamil-frontend` é legado morto (provável)

**Indicadores:**
- Último commit: `aa8fb20` (Initial commit). 0 commits subsequentes em `frontend/notamil-frontend/`.
- `redato_frontend/` recebe commits frequentes (e1ffc8d, b999332, 32d7162 — última semana).
- CLAUDE.md descreve a stack frontend principal como Next.js em `frontend/notamil-frontend`,
  mas o código de produção real (com Server Components, App Router moderno, integração
  com `/portal/...`, suporte a M9.4 e jogo da redação) está em `redato_frontend/`.

**Decisão:** **MIGRAR DIRETO PRO FT-WITH-AUDIT.**

- Gap = 0 campos ativos perdidos pra prod.
- Vantagens: ±40 sobe de 19.3% → 28.5%, latência cai de 65s → 13.8s, custo cai
  de $0.030 → $0.05 (FT) ou $0.025 (FT só notas; mas o subset enriquecido custa
  $0.05 — ainda menor que rodar Sonnet 4.6).
- **Pré-condição:** Daniel confirma que `frontend/notamil-frontend` não está deployado
  em nenhum ambiente acessível por usuário real.

**Próximos passos sugeridos (separados da migração):**
- Adicionar render de `cN_audit.feedback_text` no `redato_frontend` (info pedagógica
  pré-pronta por competência — hoje seria jogada fora).
- Adicionar render de `cN_audit.evidencias` (lista de citações + comentário) — análoga
  aos detectores de Foco/Parcial mas pra OF14.
- Limpar campos schema-only (`reincidencia_de_erro`, `reading_fluency_compromised`,
  `essay_analysis`, `meta_checks`, `motivo_anulacao`) do `_SUBMIT_CORRECTION_TOOL` —
  reduz prompt, melhora cache hit ratio. **Não bloqueia a migração**, mas é uma
  follow-up natural depois.

### Cenário B — `frontend/notamil-frontend` ainda é usado em prod

**Indicadores:**
- Algum cliente/escola ainda acessa `/correcao/page` ou `/professor/correcao-professor/page`.
- Endpoint `/essays/result/essay/{id}` recebe tráfego real (verificar logs Railway).
- `professor-feedback` workflow ainda ativo.

**Decisão:** **NÃO MIGRAR ainda.** Duas opções:

1. **RE-TREINAR o FT** com dataset que inclua audit estruturado completo (12+ campos
   por competência). Custo estimado: $50-150 pra 200-500 redações de exemplo + tempo
   de treino. Resultado esperado: FT volta a competir com Claude prod e pode até
   superar mantendo ±40 28.5%, mas com schema completo.

2. **Manter Claude prod pra OF14** enquanto desativa `frontend/notamil-frontend`.
   Custo: 0. Latência: 65s. ±40: 19.3%. Aceitável se o legacy estiver com volume
   baixo de essays e a desativação for rápida.

### Cenário C — incerto

Se Daniel não tiver certeza se notamil-frontend está em prod, **rodar uma sondagem
operacional antes de decidir**:

```bash
# 1. Logs Railway nos últimos 7 dias filtrando por hits em /essays/result/
# 2. Logs Railway de 7 dias filtrando por hits em /portal/atividades/.../envios/
# 3. Comparar volumes — se /essays/result/* tem 0 hits, é fluxo morto.
```

Resultado da sondagem decide entre A e B.

---

## Apêndice: arquivos de referência

| Componente | Path | Linhas-chave |
|---|---|---|
| Schema OF14 v2 | `backend/notamil-backend/redato_backend/dev_offline.py` | 2218-2367 (`_SUBMIT_CORRECTION_TOOL`) |
| Sub-schemas cN_audit | mesmo arquivo | 1743 (C1), 1849 (C2), 1943 (C3), 1976 (C4), 2082 (C5) |
| `_derive_notas_mechanically` | mesmo arquivo | 3466 (entry), 3195/3234/3292/3374/3430 (C1-C5) |
| `_build_competency_justification` | mesmo arquivo | 3050-3098 |
| `_errors_from_audit` | mesmo arquivo | 3101-3175 |
| `_persist_grading_to_bq` | mesmo arquivo | 2912-3046 |
| Portal helpers (stack primária) | `redato_backend/portal/portal_api.py` | 803 (`_competencias_de`), 875 (`_analise_da_redacao_de`), 975 (`_detectores_acionados_de`) |
| Rota legacy `/essays/result/` | `redato_backend/base_api/api_routes/essay_routes.py` | 327-419 |
| `get_analysis_from_bq` | `redato_backend/shared/utils.py` | 15 |
| Frontend prod (consome /portal) | `redato_frontend/app/(app)/atividade/.../aluno/.../page.tsx` | 41 (fetch), 180-219 (faixas) |
| Frontend legacy (consome /essays/result/) | `frontend/notamil-frontend/app/correcao/page.tsx` | 314 (fetch), 365 (justification), 441 (errors) |
| Experimento FT-with-audit | `scripts/ab_models/run_ft_with_audit.py` | — |
| Resultado experimento | `scripts/ab_models/results/REPORT_FT_AUDIT_20260430_163823.md` | — (gitignored) |

---

_Investigação realizada em 2026-04-30. Sem mudanças em código de produção._
