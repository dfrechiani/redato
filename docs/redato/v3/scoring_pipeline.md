# Scoring pipeline — override determinístico de nota ENEM

**Status:** em produção desde 2026-04-27 (Fase A).
**Código:** [`redato_backend/missions/scoring.py`](../../../backend/notamil-backend/redato_backend/missions/scoring.py).
**Aplicação:** [`router.py:grade_mission`](../../../backend/notamil-backend/redato_backend/missions/router.py)
chama `apply_override(mode, tool_args)` após receber a resposta do LLM.

## Por que existe

O LLM oscilava na tradução **rubrica REJ → nota ENEM final** mesmo
quando os scores 0-100 individuais batiam entre runs.

**Caso real (2026-04-27):**

| ID | rubrica REJ | Média | nota emitida pelo LLM |
|---|---|---|---|
| 9  | `{conclusao: 42, premissa: 38, exemplo: 15, fluencia: 68}` | 40.75 | **80** |
| 10 | `{conclusao: 38, premissa: 32, exemplo: 15, fluencia: 72}` | 39.25 | **40** |

Mesma redação, scores quase idênticos (banda "insuficiente"), notas
80 vs 40. A heurística no system prompt era ignorada quando o LLM
preenchia o campo `nota_c3_enem`.

**Fix arquitetural:** a tradução final é Python puro. O LLM ainda
emite `nota_cN_enem`, mas o router sobrescreve com o cálculo
determinístico antes de retornar pro caller.

## Pipeline

```
[texto transcrito]
        ↓
[Sonnet/Opus emite tool_args com:
  - rubrica_rej (scores 0-100 por critério)
  - flags (booleanos por padrão crítico)
  - nota_cN_enem (palpite do LLM, será sobrescrito)
  - feedback_aluno + feedback_professor]
        ↓
[router.apply_override(mode, tool_args):
  1. nota_python = rej_to_<modo>_score(rubrica, flags, articulacao)
  2. compara com nota_emitida_llm
  3. se divergiu, log em divergences.jsonl
  4. tool_args[nota_cN_enem] = nota_python  (override)]
        ↓
[caller recebe tool_args com nota determinística]
```

## Tabela média → ENEM (idêntica em todos os modos foco/parcial)

```python
# scoring.media_to_inep(media: float) -> int
def media_to_inep(media):
    if media < 30:  return 0
    if media < 50:  return 40
    if media < 65:  return 80
    if media < 80:  return 120
    if media < 90:  return 160
    return 200
```

Sem sobreposição entre faixas. Determinístico.

## Funções por modo

### `rej_to_c3_score(rubrica, flags) -> int`

OF10 — Foco C3.

```
1. base = media_to_inep(media(conclusao, premissa, exemplo, fluencia))
2. tese_generica → cap 120
3. andaime_copiado → cap 120
4. exemplo_redundante → cap 160
```

### `rej_to_c4_score(rubrica, flags) -> int`

OF11 — Foco C4.

```
1. base = media_to_inep(media(estrutura, conectivos, cadeia_logica, palavra_dia))
2. conectivo_relacao_errada → cap 120
3. salto_logico → cap 120
4. palavra_dia_uso_errado → cap 160
5. conectivo_repetido → cap 160
```

### `rej_to_c5_score(rubrica, flags, articulacao) -> int`

OF12 — Foco C5. Caps semânticos sobrescrevem média.

```
1. desrespeito_direitos_humanos → 0  (Cartilha INEP)
2. base = media_to_inep(media dos 6 critérios)
3. proposta_vaga_constatatoria → cap 40
4. articulacao == "ausente"   → cap 40
5. proposta_desarticulada     → cap 80
6. articulacao == "fragil"    → cap 80
7. agente_generico            → cap 120
8. verbo_fraco                → cap 160
```

### `rej_to_partial_scores(rubrica, flags, llm_c1) -> dict`

OF13 — Completo Parcial. Mapeia 4 critérios REJ → C2/C3/C4. C1 vem do
LLM (rubrica REJ não cobre norma culta).

```
C2 = media_to_inep((topico_frasal + repertorio) / 2)
C3 = media_to_inep((topico_frasal + argumento) / 2)
C4 = media_to_inep(coesao)
C1 = llm_c1 (preservado)

Caps:
- topico_e_pergunta       → C2 e C3 cap 80
- repertorio_de_bolso     → C2 cap 120
- argumento_superficial   → C3 cap 120
- coesao_perfeita_sem_progressao → diagnóstico, sem cap
```

`nota_total_parcial` = soma C1+C2+C3+C4.

### Modo Completo Integral (OF14)

**Não passa pelo override do `apply_override`.** OF14 tem caminho próprio,
selecionado via env var `REDATO_OF14_BACKEND`:

#### Backend `ft` (default desde 2026-04-30 — commit feat(of14))

GPT fine-tuned `ft:gpt-4.1-2025-04-14:redato:redato-enem:BTBOS5VF` com
prompt audit-enriched. Implementado em
[`redato_backend/missions/openai_ft_grader.py`](../../../backend/notamil-backend/redato_backend/missions/openai_ft_grader.py)
e roteado em
[`dev_offline.py:_claude_grade_essay`](../../../backend/notamil-backend/redato_backend/dev_offline.py)
(linha ~2814 em diante).

**Decisão da migração:**

- A/B 30/abr (commit `174ceab`): FT 21.5% ±40 vs Sonnet 4.6 v2 19.3%
  vs Opus 4.7 + fewshot 14.0%. Ver
  `scripts/ab_models/results/REPORT_AB_20260430_*.md` (gitignored).
- Experimento prompt-enriched (commit `6080d4d`): FT com prompt pedindo
  audit estruturado deu 28.5% ±40, 100% parse_ok, $0.05/redação,
  13.8s latência. 5 amostras qualitativas julgadas úteis.
- Investigação [`MIGRATION_FT_OF14_AUDIT.md`](MIGRATION_FT_OF14_AUDIT.md):
  gap = **0 campos ativos perdidos** no `redato_frontend` prod (consome
  apenas `cN_audit.nota`). Frontend legacy `frontend/notamil-frontend`
  é morto (sem commits desde initial).

**Schema retornado pelo FT:**

```json
{
  "c1_audit": {
    "nota": 0|40|80|120|160|200,
    "feedback_text": "<2-3 parágrafos>",
    "evidencias": [{"trecho": "<literal>", "comentario": "<por quê>"}]
  },
  "c2_audit": {...}, "c3_audit": {...}, "c4_audit": {...}, "c5_audit": {...}
}
```

Compatível com `_persist_grading_to_bq` (defensive contra schema parcial
— campos `priorization`, `essay_analysis`, `meta_checks`, `feedback_text`
solto não vêm do FT e não são consumidos pelo frontend prod).

**Performance esperada em prod:**

| Métrica | Antes (Sonnet 4.6 v2) | Depois (FT BTBOS5VF) |
|---|---|---|
| ±40% (concordância INEP) | 19.3% | **28.5%** (+9.2pp) |
| Custo/redação | $0.030 | **$0.05** (1.7×, ainda 6× menor que Opus tuned) |
| Latência média | 65s | **13.8s** (-79%) |
| Schema retornado | v2 completo (12+ campos por cN) | v2 reduzido (3 campos por cN) |

**Fallback graceful:** se o FT falhar (timeout, OPENAI_API_KEY missing,
parser não casa), `_claude_grade_essay` captura a `OpenAIFTGradingError`,
loga o motivo e cai pro path Claude Sonnet original. A correção sempre
termina — apenas com latência/custo do fallback. Logs:

```
[dev_offline] FT path failed for <id>: <ErrorType>: <message>
[dev_offline] falling back to Claude Sonnet 4.6 v2 (graceful degradation;
              set REDATO_OF14_BACKEND=claude to silence this fallback)
```

#### Backend `claude` (rollback)

Setar `REDATO_OF14_BACKEND=claude` desativa o ramo FT — `_claude_grade_essay`
segue direto pro path Sonnet 4.6 v2 (audit-first, two-stage, ensemble).
Rollback rápido sem deploy: editar env var no Railway dashboard +
restart. Útil pra investigar incidentes ou comparar com baseline.

A derivação Python (`_derive_cN_nota` em `dev_offline.py`) só roda no
path Claude — o FT path retorna notas direto do modelo sem passar por
two-stage (FT não emite os campos auditoriais que a derivação consome).

#### Pendência conhecida

`cN_audit.feedback_text` e `cN_audit.evidencias` vêm do FT mas o
`redato_frontend` ainda não os renderiza. São info pedagógica
pré-pronta por competência que hoje viaja pelo backend mas é jogada
fora pelos helpers do portal (`_analise_da_redacao_de` procura
`feedback_professor` que OF14 não tem). Render dessas duas chaves no
portal está em backlog — ver `MIGRATION_FT_OF14_AUDIT.md` cenário A
"próximos passos".

## Logger de divergências

Cada vez que `nota_emitida_llm != nota_final_python`, o router persiste
um registro em `data/whatsapp/divergences.jsonl` (override via
`REDATO_DIVERGENCES_FILE`):

```json
{
  "ts": "2026-04-27T14:12:51+00:00",
  "mode": "foco_c3",
  "activity_id": "RJ1·OF10·MF·Foco C3",
  "nota_emitida_llm": 80,
  "nota_final_python": 40,
  "rubrica_rej": {"conclusao": 42, "premissa": 38, "exemplo": 15, "fluencia": 68},
  "flags": {"andaime_copiado": false, "tese_generica": false, "exemplo_redundante": false}
}
```

Campos extras pra `completo_parcial`:
- `detalhe_notas_emitidas`: `{c1, c2, c3, c4}` do LLM
- `detalhe_notas_python`: `{c1, c2, c3, c4}` calculados

**Pra que serve:** análise offline do quanto o LLM diverge da regra
determinística. Se >20% das chamadas divergirem por >1 banda, o prompt
precisa ser revisitado. Se divergir só nas faixas-fronteira, é
comportamento esperado.

## Variância antes vs depois (smoke 3 runs / mesma redação)

| Modo | Antes do override | Depois |
|---|---|---|
| foco_c3 | [120, 120, 120] var=0 | [120, 120, 120] var=0 |
| foco_c4 | [200, 200, 200] var=0 | [160, 160, 160] var=0 |
| foco_c5 | [200, 200, 200] var=0 | [200, 200, 200] var=0 |
| completo_parcial | **[680, 760, 800] var=120** | **[720, 720, 720] var=0** |

`completo_parcial` saiu de variância 120 (acima do limite 80) pra **0**.

Notar: `foco_c4` caiu de 200 → 160 porque a média dos scores ficou em
88.75 (banda 80-89 → 160), não atingiu 90. **Isso é correto** — pra
sair de 160 a redação precisa ter média ≥90 nos critérios. Antes o
LLM dava 200 sem essa coerência.

## Quando mexer nessas funções

**Apropriado:**
- Mudança oficial nos descritores INEP (Cartilha 2026, etc.).
- Adição de novo critério REJ que precisa entrar na média.
- Novo flag de cap descoberto em validação pedagógica (ex.: cursinho
  parceiro reportar padrão consistente).
- Reordenação de hierarquia de caps após análise de divergences.jsonl.

**Não apropriado:**
- "A nota X ficou baixa numa redação específica" — investigar a
  rubrica primeiro. Se a rubrica está alta, divergence existe; se a
  rubrica está baixa, a função fez o trabalho.
- "Quero forçar a nota desta correção" — não é o lugar. Rota
  apropriada é re-grade ou revisão humana via HITL.

A função é a **régua institucional**. Mudar a régua afeta todas as
correções daqui pra frente. Trate como mudança de spec ENEM, não como
patch.

## Smoke de regressão

Antes de qualquer mudança em `scoring.py`:

```bash
cd backend/notamil-backend
python scripts/validation/smoke_variance_missions.py --runs 3 \
    --only foco_c3,foco_c4,foco_c5,completo_parcial
```

Critério: variância em todos os 4 modos = 0. Se algum > 0 sem mudança
intencional, **regrediu**.
