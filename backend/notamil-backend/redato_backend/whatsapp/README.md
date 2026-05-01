# WhatsApp — Bot Redato (Fase B+, M4)

Bot WhatsApp do **Redato** (corretora) operando dentro do programa
**Projeto ATO** (Agência Textual de Operação). Webhook Twilio +
máquina de estados + correção via Claude (`dev_offline._claude_grade_essay`).

**Spec M4:** [docs/redato/v3/REPORT_caminho2_realuse.md](../../../../docs/redato/v3/REPORT_caminho2_realuse.md)
seção 5.4 (M4 — Bot adaptado: missões, atividades, vínculo aluno).

## Mudança fundamental no M4

**Fase A (sandbox livre, descontinuada):** qualquer telefone podia
mandar uma foto + código da missão e receber correção. Cadastro era
nome livre + turma livre, sem validação. Não havia conceito de
"atividade" — toda missão estava sempre disponível.

**Fase B+ (M4 em diante):** aluno **só consegue mandar redação se**:
1. Estiver vinculado a uma turma ativa (cadastrado pela
   coordenação/professor via importador M2 ou via fluxo de cadastro
   por código).
2. A turma tiver uma **atividade** aberta (`data_inicio <= agora <= data_fim`)
   pra missão que ele está mandando.

O fluxo "livre" da Fase A foi **descontinuado** — não é mais possível
mandar redação sem atividade vinculada.

## Estados do bot (FSM)

Persistidos em SQLite (`data/whatsapp/redato.db`, tabela `alunos`,
coluna `estado`). Codificação composta para passar contexto:
`AWAITING_FOTO|<missao>` ou `AWAITING_NOME_ALUNO|<turma_id>`.

```
NEW
 │
 │ qualquer mensagem
 ▼
AWAITING_CODIGO_TURMA  ◄────────────┐
 │                                  │
 │ usuário manda TURMA-XXXXX-1A-2026 │ READY recebe codigo de turma
 │ válido + ativo                   │ (re-cadastro em outra turma)
 ▼                                  │
AWAITING_NOME_ALUNO|<turma_id>      │
 │                                  │
 │ usuário manda nome completo      │
 ▼                                  │
READY ──────────────────────────────┘
 │
 │ recebe foto + código missão (RJ1OF10MF)
 ▼
[valida vínculo aluno→turma + atividade ativa]
 │
 ├─ vínculo OK + atividade ativa → corrige + cria envio em Postgres
 ├─ vínculo OK + múltiplas turmas → AWAITING_TURMA_CHOICE
 ├─ não cadastrado → MSG_ALUNO_NAO_CADASTRADO + volta a AWAITING_CODIGO_TURMA
 ├─ atividade agendada → MSG_ATIVIDADE_AGENDADA (sem corrigir)
 ├─ atividade encerrada → MSG_ATIVIDADE_ENCERRADA (sem corrigir)
 └─ sem atividade pra essa missão → MSG_SEM_ATIVIDADE_ATIVA
```

Estados intermediários (preservados de M0):
- `AWAITING_FOTO|<missao>`: usuário mandou só o código da missão,
  bot espera foto.
- `AWAITING_CODIGO`: usuário mandou só foto, bot espera código.
- `AWAITING_DUP`: foto duplicada (mesma dHash), espera escolha 1/2.

Estados legados de Fase A (mantidos pra backcompat de testes antigos,
**não atingíveis em produção**): `AWAITING_NOME`, `AWAITING_TURMA`.

## Mensagens (centralizadas em [messages.py](messages.py))

Tom: "professora explicando regra" — claro, firme, sem sermão.
Sem emoji decorativo. Vocativo direto ("você"). Foco no próximo
passo concreto pro aluno.

### Mensagens de cadastro

| Constante | Quando aparece |
|---|---|
| `MSG_BEM_VINDO_NOVO_ALUNO` | Primeira mensagem de telefone novo (NEW → AWAITING_CODIGO_TURMA). |
| `MSG_PEDE_NOME_ALUNO` | Código de turma válido — pede nome completo. |
| `MSG_CADASTRO_COMPLETO` | Cadastro finalizado, aluno entra em READY. |
| `MSG_CODIGO_TURMA_INVALIDO` | Código não bate com nenhuma turma ativa. |
| `MSG_TURMA_INATIVA` | Turma encontrada mas com `deleted_at` ou suspensa. |
| `MSG_JA_CADASTRADO_NESSA_TURMA` | Re-cadastro na mesma turma onde já está ativo. |

### Mensagens de envio de redação

| Constante | Quando aparece |
|---|---|
| `MSG_ALUNO_NAO_CADASTRADO` | READY/AWAITING_FOTO sem `aluno_turma_id` ativo no Postgres. |
| `MSG_SEM_ATIVIDADE_ATIVA` | Aluno está em turma X mas turma X não tem atividade pra missão Y. |
| `MSG_ATIVIDADE_AGENDADA` | Atividade existe mas `agora < data_inicio`. |
| `MSG_ATIVIDADE_ENCERRADA` | Atividade existe mas `agora > data_fim`. |
| `MSG_ESCOLHE_TURMA` | Aluno em ≥2 turmas — pede pra escolher qual. |
| `MSG_TURMA_ESCOLHA_INVALIDA` | Resposta numérica inválida no AWAITING_TURMA_CHOICE. |

### Notificação push

| Constante | Quando aparece |
|---|---|
| `MSG_NOTIFICACAO_NOVA_ATIVIDADE` | Disparada por `POST /portal/atividades/{id}/notificar`. |

## Validação de atividade

Lógica em [portal_link.py](portal_link.py):

```python
find_atividade_para_missao(turma_id, missao_codigo) -> Optional[AtividadeAtivaInfo]
```

Retorna a atividade mais recente (`ORDER BY data_inicio DESC`) cuja
missão.codigo bate. O `.status` é uma `@property` calculada na hora:

- `agendada`  → `agora < data_inicio`
- `ativa`     → `data_inicio <= agora <= data_fim`
- `encerrada` → `agora > data_fim`

Bot só processa OCR + correção se `status == "ativa"`. Status agendada/
encerrada respondem com mensagem específica e **não consomem** chamada
do Claude.

## Persistência dual: SQLite + Postgres

Bot mantém **estado da FSM em SQLite** (`alunos.estado`) — ágil, local,
sem dependência de network. Mas a partir do M4, **dados de domínio**
vão pra Postgres:

| Entidade | Onde mora |
|---|---|
| Estado FSM (`AWAITING_*`, `READY`) | SQLite (`alunos.estado`) |
| Histórico de FSM transitions | SQLite (`fsm_log`) |
| Cadastro permanente (Aluno em turma) | Postgres (`alunos_turma`) |
| Atividade aberta + janela de tempo | Postgres (`atividades`) |
| Envio de redação (1 por aluno/atividade) | Postgres (`envios`) |
| Resultado da correção | Postgres (`interactions`, com FK `envio_id`) |

A função `criar_interaction_e_envio_postgres()` em `portal_link.py`
faz a escrita atômica de Interaction + Envio dentro de uma transação.

## Fluxo completo (exemplo)

```
# 1. Coordenadora importa turma + alunos via portal (M2)
#    Resultado: turma TURMA-ABC12-1A-2026 com 30 alunos cadastrados,
#    incluindo "+5511999999999" como Maria Silva.

# 2. Professora cria atividade RJ1OF10MF na turma (M4 portal API,
#    ainda não implementada — por ora via INSERT direto):
INSERT INTO atividades (id, turma_id, missao_id, data_inicio, data_fim, ...)
VALUES (..., 'turma_abc_id', 'missao_rj1of10mf_id', '2026-04-27', '2026-05-04', ...);

# 3. Professora chama notificar:
curl -X POST http://localhost:8080/portal/atividades/<atividade_id>/notificar \
  -H "Authorization: Bearer <jwt>"
# → Twilio dispara MSG_NOTIFICACAO_NOVA_ATIVIDADE pra todos os
#   30 alunos. Marca atividades.notificacao_enviada_em.

# 4. Maria recebe a notificação no WhatsApp. Tira foto da redação,
#    manda com o código:
[Maria → Twilio]: foto + texto "RJ1OF10MF"

# 5. Webhook /twilio/webhook recebe form-data, dispara handle_inbound:
#    - lookup aluno_turma por telefone → encontra Maria/Turma ABC
#    - lookup atividade pra (turma_abc_id, RJ1OF10MF) → encontra ativa
#    - OCR → correção via Claude → 720 pontos
#    - cria Interaction + Envio em Postgres (UNIQUE (atividade_id,
#      aluno_turma_id) — garante 1 envio por aluno/atividade)
#    - manda render_full_feedback() pro Maria

# 6. Maria tenta mandar de novo a mesma redação:
[Maria → Twilio]: foto (mesma dHash) + "RJ1OF10MF"
# → AWAITING_DUP → escolhe 1 (reenvio) ou 2 (reavaliar)
```

## Re-cadastro / mudança de turma

Aluno em READY que mande um código de turma `TURMA-XXXXX-...` é
interceptado em `handle_inbound` e roteado pra `_handle_codigo_turma`.
Cenários:

- Código bate com turma onde aluno **já está ativo**: responde
  `MSG_JA_CADASTRADO_NESSA_TURMA` e não muda estado.
- Código bate com turma **diferente**: aluno passa pra
  `AWAITING_NOME_ALUNO|<turma_id>` e o cadastro segue normal — fica
  vinculado às duas turmas (UNIQUE é por `(turma_id, telefone)`).
- Código inválido/turma inativa: `MSG_CODIGO_TURMA_INVALIDO` /
  `MSG_TURMA_INATIVA`. Estado **não muda** — aluno continua READY.

## Aluno em múltiplas turmas

Aluno com 2+ vínculos ativos no portal (ex.: estuda em duas séries
no mesmo telefone, ou ano letivo de transição) precisa desambiguar
qual turma a redação refere antes da correção. O caso real que
motivou (30/04/2026): telefone em turmas 1A (1S) + 2A (2S), aluno
manda foto+OF14, bot tinha que rotear pra 1A onde OF14 existe.

### Fluxo

Quando `list_alunos_ativos_por_telefone` retorna ≥2 vínculos:

1. **Primeira foto da sessão** (sem turma persistida): bot entra em
   `AWAITING_TURMA_CHOICE|<missao>|<foto_path>` e responde
   `MSG_ESCOLHE_TURMA` com lista numerada das turmas.
2. **Aluno responde número** (1, 2, ...): bot persiste a escolha em
   `alunos.turma_ativa_id` (TTL de **2h** — `P.TURMA_ATIVA_TTL_HOURS`)
   e reprocessa a foto via `_process_photo_after_validations`.
3. **Próximas fotos dentro do TTL**: bot atalha — lê `turma_ativa_id`,
   confere se ainda bate com algum vínculo ativo do portal, e segue
   sem perguntar. Se vínculo foi desativado entre escolha e agora,
   limpa e abre nova pergunta (fail-safe).

### Comando "trocar turma"

Em qualquer estado pós-cadastro, aluno pode mandar `trocar turma`
(ou `mudar turma`, `trocar de turma`, `outra turma`) pra:
- Limpar a escolha persistida (`P.clear_turma_ativa`)
- Reabrir a desambiguação (se 2+ vínculos)
- Receber `MSG_TROCAR_TURMA_UNICA` se só tem 1 vínculo (não dá pra trocar)

### Guard-rail: foto durante AWAITING_TURMA_CHOICE

Se aluno está em `AWAITING_TURMA_CHOICE` e manda **foto** em vez de
responder o número, o bot **não processa** a foto silenciosamente
(podia rotear pra turma errada). Em vez disso reenvia
`MSG_FOTO_DURANTE_ESCOLHA` mantendo o estado — aluno precisa responder
com o número primeiro.

### Persistência (`alunos.turma_ativa_id` + `turma_ativa_em`)

Colunas adicionadas via migration ALTER em `init_db()` (idempotente
— `PRAGMA table_info` checa antes). Helpers em `persistence.py`:
- `set_turma_ativa(phone, turma_id)`: persiste com timestamp now.
- `get_turma_ativa(phone, ttl_hours=2)`: retorna turma_id se ainda
  dentro do TTL, senão None.
- `clear_turma_ativa(phone)`: zera. Usado pelo comando "trocar turma"
  e pelo fail-safe quando vínculo persistido foi desativado.

### Mensagens novas (`messages.py`)

- `MSG_TURMA_ATIVA_CONFIRMADA` — confirma escolha + lembra TTL + dica do comando.
- `MSG_FOTO_DURANTE_ESCOLHA` — guard-rail.
- `MSG_TROCAR_TURMA_INICIO` — abertura da nova escolha.
- `MSG_TROCAR_TURMA_UNICA` — aluno só tem 1 vínculo, não dá pra trocar.

## Migração de dados antigos (Fase A → M4)

A tabela `interactions` tem registros legados da Fase A onde:
- `aluno_turma_id IS NULL` (não havia cadastro estruturado)
- `envio_id IS NULL` (não havia conceito de envio)
- `source = "whatsapp_v1"` (distingue de registros pós-M4 que têm
  `source = "whatsapp_m4"`)

Esses registros **continuam consultáveis** pelo dashboard agregado
(M5+) via match de `aluno_phone`, mas **não aparecem** em listagens
por turma/atividade — não há vínculo. M4 não tenta popular esses
campos retroativamente; isso é débito técnico documentado em
[../portal/README.md](../portal/README.md) seção "aluno_phone é
fallback transitório".

## Smoke test

```bash
cd backend/notamil-backend
python scripts/test_m4_bot_atividades.py   # 12 testes
```

Cobre: aluno não cadastrado, código inválido, cadastro completo,
re-cadastro, sem atividade ativa, atividade agendada, atividade
encerrada, endpoint texto-notificacao, endpoint notificar (idempotente
+ permissões 401/403), filter_pending_users compartilhado.

Roda também os testes de regressão do webhook offline:

```bash
python scripts/validation/test_webhook_offline.py    # 6 testes Fase A
```

## Variáveis de ambiente relevantes

| Variável | Default | O que faz |
|---|---|---|
| `DATABASE_URL` | — | Postgres do portal. Sem isso, validação de vínculo falha. |
| `REDATO_WHATSAPP_DB` | `data/whatsapp/redato.db` | SQLite com FSM state. |
| `TWILIO_ACCOUNT_SID` | — | Sem isso, `notificar` opera em dry-run. |
| `TWILIO_AUTH_TOKEN` | — | Idem. |
| `TWILIO_VALIDATE_SIGNATURE` | `1` | `0` desliga checagem HMAC (dev). |
| `REDATO_DEV_OFFLINE` | `0` | `1` stuba Anthropic e devolve correção determinística. |

## Arquivos

- [bot.py](bot.py) — FSM + handlers (`handle_inbound`, `_handle_codigo_turma`, `_handle_nome_aluno`, `_handle_turma_choice`, `_process_photo`).
- [messages.py](messages.py) — todas as strings de resposta.
- [portal_link.py](portal_link.py) — ponte SQLite-bot ↔ Postgres-portal (lookup turma/aluno/atividade, criação atômica de Interaction+Envio).
- [persistence.py](persistence.py) — CRUD do SQLite (alunos, fsm_log, interactions legacy).
- [twilio_provider.py](twilio_provider.py) — parse_inbound, send_replies, signature validation.
- [webhook.py](webhook.py) / [app.py](app.py) — FastAPI app + rotas.
- [ocr.py](ocr.py) / [render.py](render.py) — pipeline de OCR e renderização do feedback.
