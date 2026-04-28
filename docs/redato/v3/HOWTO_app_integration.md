# Como o app integra com a Redato — modos REJ 1S

**Spec:** [redato_1S_criterios.md](redato_1S_criterios.md)
**Smoke test:** [REPORT_smoke_missions.md](REPORT_smoke_missions.md)

## Visão geral

A Redato expõe **um único entry point** —
[`_claude_grade_essay(data)`](../../../backend/notamil-backend/redato_backend/dev_offline.py)
— que recebe um dict com `activity_id` e roteia internamente para o pipeline
correto.

O app não precisa saber qual schema vai voltar; basta enviar o
`activity_id` correto. O `tool_args` retornado tem `modo` no top-level pra
o app fazer dispatch de UI.

## Mapeamento activity_id → modo

| activity_id (canônico) | Modo retornado | Schema |
|---|---|---|
| `RJ1·OF10·MF·Foco C3` | `foco_c3` | `submit_foco_c3` |
| `RJ1·OF11·MF·Foco C4` | `foco_c4` | `submit_foco_c4` |
| `RJ1·OF12·MF·Foco C5` | `foco_c5` | `submit_foco_c5` |
| `RJ1·OF13·MF·Correção 5 comp.` | `completo_parcial` | `submit_completo_parcial` |
| `RJ1·OF14·MF·Correção 5 comp.` | `completo_integral` | `submit_correction_flat` (v2 atual) |

**Variantes de separador aceitas** pelo `resolve_mode()`:

- `·` (U+00B7 MIDDLE DOT) — preferido
- `_` (underline)
- `-` (hyphen)
- `.` (dot)
- ` ` (espaço)

Todos resolvem para o mesmo prefixo canônico `RJ1_OFXX_MF`. O app pode
escolher o que for mais conveniente — o mapeamento é case-insensitive.

## Payload de chamada

```python
data = {
    "request_id": "essay_<uuid>",          # ID único da submissão
    "user_id": "<student_id>",
    "activity_id": "RJ1·OF10·MF·Foco C3",  # define o modo
    "theme": "Trabalho em equipe...",       # contexto do exercício
    "content": "<texto do aluno>",          # parágrafo ou redação
}
result = _claude_grade_essay(data)  # tool_args dict
```

## Schemas de retorno por modo

### `foco_c3` / `foco_c4` / `foco_c5`

Estrutura comum (variações nos campos de rubrica e flags):

```json
{
  "modo": "foco_c3",
  "missao_id": "RJ1_OF10_MF",
  "rubrica_rej": {
    "<criterio_1>": "insuficiente|adequado|excelente",
    ...
  },
  "nota_rej_total": <int 0-12>,
  "nota_c3_enem": <0|40|80|120|160|200>,
  "flags": {
    "<flag_1>": <bool>,
    ...
  },
  "feedback_aluno": {
    "acertos": ["..."],
    "ajustes": ["..."]
  },
  "feedback_professor": {
    "padrao_falha": "...",
    "transferencia_c1": "...",
    "audit_completo": "..."
  },
  "_mission": {
    "mode": "foco_c3",
    "missao_id": "RJ1_OF10_MF",
    "activity_id": "<original>",
    "pre_flags": {"andaime_copiado": false},
    "model": "claude-opus-4-7"
  }
}
```

**Variações por modo:**

- **`foco_c3`** rubrica: `conclusao | premissa | exemplo | fluencia` (3 níveis cada). Flags: `andaime_copiado | tese_generica | exemplo_redundante`.
- **`foco_c4`** rubrica: `estrutura | conectivos | cadeia_logica | palavra_dia` (3 níveis cada). Flags: `conectivo_relacao_errada | conectivo_repetido | salto_logico | palavra_dia_uso_errado`.
- **`foco_c5`** rubrica: `agente | acao_verbo | meio | finalidade | detalhamento | direitos_humanos` (3 níveis cada) + campo extra `articulacao_a_discussao` (`ausente | fragil | clara | tematizada`). Flags: `proposta_vaga_constatatoria | proposta_desarticulada | agente_generico | verbo_fraco | desrespeito_direitos_humanos`.

### `completo_parcial` (OF13)

Parágrafo único — C5 marcado como string `"não_aplicável"` (importante: o
app deve tratar essa string específica).

```json
{
  "modo": "completo_parcial",
  "missao_id": "RJ1_OF13_MF",
  "rubrica_rej": {
    "topico_frasal": <0-3>,
    "argumento": <0-3>,
    "repertorio": <0-3>,
    "coesao": <0-3>
  },
  "nota_rej_total": <0-12>,
  "notas_enem": {
    "c1": <0|40|80|120|160|200>,
    "c2": <0|40|80|120|160|200>,
    "c3": <0|40|80|120|160|200>,
    "c4": <0|40|80|120|160|200>,
    "c5": "não_aplicável"
  },
  "nota_total_parcial": <0-800>,
  "flags": {
    "topico_e_pergunta": <bool>,
    "repertorio_de_bolso": <bool>,
    "argumento_superficial": <bool>,
    "coesao_perfeita_sem_progressao": <bool>
  },
  "feedback_aluno": {...},
  "feedback_professor": {...}
}
```

### `completo_integral` (OF14)

**Schema é o mesmo do pipeline v2 da Redato em produção** — `tool_args` tem
`essay_analysis`, `preanulation_checks`, `c1_audit`...`c5_audit`,
`priorization` (com `priority_1`/`priority_2`/`priority_3`), `meta_checks` e
`feedback_text`. Preâmbulo REJ é injetado no `user_msg` mas não muda o
schema — o app reusa toda a UI atual da redação completa.

A única adaptação visível ao app é que o `feedback_text` agora começa com
linguagem de "primeira redação completa do ano" (vocabulário REJ + tom
formativo). É decisão de redação do LLM — o app não precisa fazer nada.

## Modelo e custo

- **Modelo:** `claude-opus-4-7` (mesmo da Redato em produção). Override
  via `REDATO_CLAUDE_MODEL`.
- **`max_tokens`:** 8000 nos modos foco/parcial, 8000 no completo
  integral (já é o default v2).
- **Cache:** ativo em todos os modos. TTL=1h.
  - Modos foco/parcial: ~1k tokens cacheados (system prompt persona).
  - Completo integral: ~21k tokens (rubrica v2 + few-shots + tail).
- **Latência típica (cache warmed):** ~20s nos modos foco/parcial,
  ~50s no completo integral (com self-critique).

## Erros possíveis

| Sintoma | Causa | Mitigação |
|---|---|---|
| `ValueError: grade_mission não aceita activity_id=...` | App enviou activity_id de OF14 pro `grade_mission()` direto | Sempre passar pelo `_claude_grade_essay`; o roteamento decide. |
| `RuntimeError: Claude não invocou submit_foco_*` | Tool_choice falhou (raro, ~<0.5% das chamadas) | Cliente deve fazer 1 retry; falha persistente sinaliza problema de prompt. |
| `feedback_aluno` truncado (campos ausentes) | `max_tokens` muito baixo | Já elevado pra 8000 — se voltar a acontecer, investigar prompts do app. |

## Detecção de foto duplicada (Fase A — bot WhatsApp)

A partir de 2026-04-27, o bot calcula SHA256 da foto e busca interação
anterior do mesmo aluno + missão + hash dentro de 30 dias. Se encontrar:

```
Recebi essa mesma redação em DD/MM às HH:MM. O que você quer?

1️⃣ Reenviar o feedback que já te dei
2️⃣ Reavaliar como nova tentativa (a IA pode dar outra nota)

Responde *1* ou *2*.
```

- Resposta `1` → re-renderiza o feedback do JSON anterior. Custo zero
  em API. Resposta idêntica garantida.
- Resposta `2` → roda o pipeline normal (OCR + grade_mission + render).
  Pode dar nota diferente.
- Resposta inválida → pede de novo, mantém estado.

Estado FSM: `AWAITING_DUP|<dup_id>|<missao_canon>|<foto_path>`.

Implementação: [`bot.py:_handle_duplicate_choice`](../../../backend/notamil-backend/redato_backend/whatsapp/bot.py),
[`persistence.py:find_duplicate_interaction`](../../../backend/notamil-backend/redato_backend/whatsapp/persistence.py).

## Estabilidade de nota (FIX 2 — escala 0-100)

A partir de 2026-04-27, cada critério da `rubrica_rej` é **integer 0-100**
em vez de string `"insuficiente|adequado|excelente"`. Bandas:

| Score   | Banda                |
|---------|----------------------|
| 0-49    | insuficiente         |
| 50-79   | adequado             |
| 80-100  | excelente            |

Função `discretize.discretiza_score(int)` faz a conversão pra string.

A nota INEP (`nota_cN_enem`) deriva da média dos scores via tabela
**determinística** no system prompt:

| Média scores | Nota INEP |
|---|---|
| 0-29   | 0 |
| 30-49  | 40 |
| 50-64  | 80 |
| 65-79  | 120 |
| 80-89  | 160 |
| 90-100 | 200 |

Caps semânticos sobrescrevem (DH, articulação à discussão, tese genérica).

**Variância medida (smoke 3 runs / mesma redação, 2026-04-27):**

| Modo | Notas | Variância | OK? |
|---|---|---:|:-:|
| foco_c3 | [120, 120, 120] | 0 | ✓ |
| foco_c4 | [200, 200, 200] | 0 | ✓ |
| foco_c5 | [200, 200, 200] | 0 | ✓ |
| completo_parcial | [680, 760, 800] | 120 | ✗ (limite 80) |

**Completo parcial:** scores REJ similares mas as 4 notas INEP
individuais (C1-C4) oscilam entre 160 e 200, somando até 120 pts de
variação no total. C1 não está coberto pela rubrica REJ (avaliado só
pela Cartilha INEP), o que aumenta variabilidade. Fix futuro: schema
poderia exigir nota INEP única coerente com média de scores.

**Confidences (campo opcional):** o LLM pode preencher
`confidences.<criterio>` com 0-100 quando estiver em zona de fronteira.
Não exibido ao aluno. Útil pra revisão pedagógica humana posterior.

## Pré-flags Python (`_mission.pre_flags`)

Cada chamada retorna em `_mission.pre_flags` o resultado dos detectores
heurísticos rodados no texto **antes** do LLM. São advisory — o LLM pode
discordar e marcar a flag oficial como False mesmo com o detector
disparando. O app **não** deve usar `_mission.pre_flags` no UI do aluno;
serve para:

1. Auditoria offline (qual % de discordância LLM × Python por flag).
2. Debugging (entender quando o LLM ignora um sinal óbvio).
3. Validação empírica em Fase 2 (calibrar detectores com base em
   julgamento pedagógico real).

## Exemplo end-to-end (foco_c3)

Request:
```python
data = {
    "request_id": "essay_abc123",
    "user_id": "aluno_42",
    "activity_id": "RJ1·OF10·MF·Foco C3",
    "theme": "Trabalho em equipe",
    "content": "O trabalho em equipe é fundamental..."
}
```

Response (top-level fields):
```json
{
  "modo": "foco_c3",
  "missao_id": "RJ1_OF10_MF",
  "rubrica_rej": {"conclusao": "excelente", "premissa": "excelente",
                  "exemplo": "excelente", "fluencia": "excelente"},
  "nota_rej_total": 8,
  "nota_c3_enem": 200,
  "flags": {"andaime_copiado": false, "tese_generica": false,
            "exemplo_redundante": false},
  "feedback_aluno": {"acertos": [...], "ajustes": [...]},
  "feedback_professor": {"padrao_falha": "...", "transferencia_c1": "...",
                         "audit_completo": "..."},
  "_mission": {...}
}
```

UI sugerida pro aluno:
- Card grande com `nota_c3_enem` em destaque + tradução qualitativa
  ("excelente", "bom", "em desenvolvimento", "insuficiente" — derivar
  da faixa).
- Bullets de `feedback_aluno.acertos` em verde.
- Bullets de `feedback_aluno.ajustes` em laranja.
- Não mostrar `feedback_professor` no app do aluno.

UI sugerida pro professor:
- Mesma card + `feedback_professor.padrao_falha` como tag.
- `feedback_professor.audit_completo` em texto longo.
- `flags` ativas como pills.
- `_mission.pre_flags` em modo debug (oculto por padrão).
