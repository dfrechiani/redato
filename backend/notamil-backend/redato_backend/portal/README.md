# Portal — Backend (Fase B+, M1-M8)

Camada de persistência SQLAlchemy + Postgres + endpoints HTTP do portal
do professor e dashboards agregados.

**Spec:** [docs/redato/v3/REPORT_caminho2_realuse.md](../../../../docs/redato/v3/REPORT_caminho2_realuse.md)
seção 5.

## Mapa dos milestones (Fase B+ completa)

| Milestone | Entregue | Smoke tests |
|---|---|---|
| **M1** modelo de dados + migração SQLite→Postgres | [models.py](models.py) + Alembic | 7/7 |
| **M2** importação SEDUC + welcome emails | [importer.py](importer.py) + [admin_api.py](admin_api.py) | (em M3) |
| **M3** auth (JWT + 1º acesso + reset) | [auth/](auth/) | 13/13 |
| **M4** bot WhatsApp adaptado (atividades, missões) | [whatsapp/portal_link.py](../whatsapp/portal_link.py) | 12/12 |
| **M5** front-end Next.js (login + reset) | [redato_frontend/](../../../../redato_frontend/) | 16/16 (E2E) |
| **M6** gestão (turmas, atividades, perfil) | [portal_api.py](portal_api.py) M6 | 14/14 |
| **M7** dashboards (turma, escola, evolução) | [portal_api.py](portal_api.py) M7 + [detectores.py](detectores.py) | 10/10 + 7/7 |
| **M8** PDF + email transacional + triggers | [pdf_generator.py](pdf_generator.py) + [triggers.py](triggers.py) | 11/11 |

Total: **74 backend tests** + **44 frontend E2E** = **118 testes verdes**.

## Arquitetura (visão geral)

```
                 ┌─────────────────┐
                 │  redato_frontend │  Next.js 14 (App Router)
                 │  (port 3000)    │  + cookies httpOnly + Tailwind
                 └────────┬────────┘
                          │ /api/* proxy (anexa Bearer)
                          ▼
                 ┌─────────────────┐
   admin token →│  /admin         │  (importer + triggers/run + health)
   bearer JWT  →│  /auth          │  (login/me/perfil + reset)
   bearer JWT  →│  /portal        │  (turmas/atividades/dashboards/pdfs)
   HMAC Twilio →│  /twilio        │  (webhook bot WhatsApp)
                 └────────┬────────┘
                          │
       ┌──────────────────┼──────────────────┐
       ▼                  ▼                  ▼
  ┌─────────┐      ┌─────────────┐    ┌──────────────┐
  │Postgres │      │SendGrid REST │    │Twilio (Whats)│
  │(domain  │      │(transacional)│    │(bot)          │
  │ + audit │      │+ dry-run JSONL    │+ dry-run JSONL│
  │ + PDFs  │      └─────────────┘    └──────────────┘
  │  meta)  │      ┌─────────────┐
  └────┬────┘      │ Filesystem  │
       │           │ /data/portal/  storage de PDFs (volume Railway)
       │           │   pdfs/        emails_pendentes.jsonl
       │           │   triggers_log.jsonl
       │           │   audit_log.jsonl
       └──── 1 ────┘
       ▲
       │ SQLite legacy
       │ data/whatsapp/redato.db (FSM bot)
```

## Schema

```
escolas (UUID)
 ├── coordenadores (UUID, ativo flag)
 ├── professores   (UUID, ativo flag)
 │    └── turmas (UUID, soft delete)
 │         ├── alunos_turma (UUID, ativo flag, UNIQUE(turma_id, telefone))
 │         └── atividades  (UUID, soft delete, status property)
 │              └── envios (UUID, UNIQUE(atividade_id, aluno_turma_id))
 │                   └── interactions (INTEGER) ← legado da Fase A
 │                         (FK envio_id, source, aluno_turma_id nullable)
```

8 tabelas no total (mais `alembic_version`):

| Tabela | PK | Soft delete? | Notas |
|---|---|---|---|
| `escolas` | UUID | sim (`deleted_at`) | CHECK `length(estado) = 2` |
| `coordenadores` | UUID | flag `ativo` | UNIQUE email; senha_hash nullable até 1º acesso |
| `professores` | UUID | flag `ativo` | idem coordenadores |
| `turmas` | UUID | sim (`deleted_at`) | CHECK serie ∈ ('1S','2S','3S'), UNIQUE codigo_join |
| `alunos_turma` | UUID | flag `ativo` | UNIQUE (turma_id, telefone) |
| `atividades` | UUID | sim (`deleted_at`) | CHECK missao_id ∈ whitelist, CHECK data_fim>data_inicio, status calculado |
| `envios` | UUID | não | UNIQUE (atividade_id, aluno_turma_id) — 1 envio por aluno/atividade |
| `interactions` | INTEGER | não | tabela legada da Fase A; agora com `aluno_turma_id`/`envio_id`/`source` |

### Por que `interactions` mantém ID inteiro

Compat com a tabela do SQLite legada (Fase A) que usa
`AUTOINCREMENT INTEGER`. Migração SQLite→Postgres preserva os IDs
existentes. Quando M4 migrar o bot WhatsApp pra Postgres, novos
registros continuarão usando o sequence `interactions_id_seq`.

### Status da `Atividade` (calculado, não armazenado)

`Atividade.status` é uma `@property` Python:

```python
agora = datetime.now(UTC)
if agora < data_inicio:    return "agendada"
if agora <= data_fim:      return "ativa"
return "encerrada"
```

Não persistido — sem necessidade de cron pra atualizar. Filtros por
status no SQL usam `data_inicio`/`data_fim` diretamente (índice composto
`ix_atividade_turma_missao_inicio` cobre).

## Setup local

### Pré-requisitos

- Python 3.12+
- Postgres 14+ (Homebrew ou Docker)
- Deps: `pip install sqlalchemy alembic psycopg2-binary`

### Opção A — Postgres via Docker Compose (recomendado)

```bash
cd backend/notamil-backend
docker compose up -d                      # sobe postgres na porta 5433
# Configurar .env:
echo "DATABASE_URL=postgresql://redato:redato@localhost:5433/redato_portal_dev" >> .env

cd redato_backend/portal
alembic upgrade head                       # cria schema
```

### Opção B — Postgres via Homebrew (já rodando)

```bash
brew install postgresql@16
brew services start postgresql@16
psql -U $USER -d postgres -c 'CREATE DATABASE redato_portal_dev;'

# Configurar .env:
echo "DATABASE_URL=postgresql://$USER@localhost:5432/redato_portal_dev" >> .env

cd backend/notamil-backend/redato_backend/portal
alembic upgrade head
```

### Validar

```bash
cd backend/notamil-backend
python scripts/test_m1_persistence.py   # 7 testes, devem todos passar
```

## Migração SQLite → Postgres

Pra trazer dados legados da Fase A (bot WhatsApp em sandbox) pro Postgres:

```bash
cd backend/notamil-backend

# Dry run primeiro (não escreve nada, só conta)
python -m redato_backend.portal.migrate_sqlite_to_postgres --dry-run

# Real
python -m redato_backend.portal.migrate_sqlite_to_postgres
```

**Idempotente:** rodar 2× não duplica. Detecta dados já migrados via
`(aluno_phone, missao_id, created_at)`.

**O que migra:** somente a tabela `interactions`. Migra com:
- `aluno_turma_id = NULL` (M4 popula retroativamente)
- `envio_id = NULL` (M4 popula retroativamente)
- `source = "whatsapp_v1"` (distingue de registros pós-M4)

**O que NÃO migra:** tabelas `alunos` e `turmas` da Fase A. Modelo de
portal (Coordenador, Professor, Escola) é diferente — coordenador
cadastra escolas/turmas via M2 (importação por planilha).

## Setup pós-migração (M4)

A partir de M4, há catálogo `missoes` (5 entradas) que precisa ser
populado antes de criar atividades:

```bash
cd backend/notamil-backend
alembic upgrade head                # roda M1+M3+M4
python -m redato_backend.portal.seed_missoes   # popula 5 missões REJ 1S
```

`seed_missoes` é idempotente — rodar 2× não duplica.

## Endpoints do portal (M4+)

```
POST /portal/atividades/{id}/notificar
GET  /portal/atividades/{id}/texto-notificacao
```

Auth: Bearer JWT (M3). Permission: professor responsável pela turma
OU coordenador da escola.

`/notificar` é idempotente — 2ª chamada responde com
`ja_notificada_em` sem reenviar. Sem `TWILIO_ACCOUNT_SID` no env,
opera em modo dry-run e registra em `data/portal/audit_log.jsonl`.

## Política de soft delete

Tabelas com `deleted_at TIMESTAMPTZ NULLABLE`:
- `escolas`
- `turmas`
- `atividades`

**Nunca executar `DELETE` físico** nessas tabelas. Use:

```python
escola.deleted_at = datetime.now(timezone.utc)
session.commit()
```

E nas queries (até implementarmos um `Query` interceptor):

```python
session.execute(select(Escola).where(Escola.deleted_at.is_(None)))
```

Por que: dashboards e relatórios históricos precisam de turmas/atividades
extintas. Apagar fisicamente quebra agregações.

Tabelas com flag `ativo`:
- `coordenadores`
- `professores`
- `alunos_turma`

Aqui o uso é mais simples (acesso ON/OFF). Não precisa preservar
auditoria histórica completa — basta marcar inativo.

## Backward compat com Fase A

A tabela legada `data/whatsapp/redato.db` (SQLite) **continua sendo
escrita pelo bot atual**. M1 não muda isso. M4 migrará o bot pra
Postgres.

Coexistência durante M2/M3:
- Bot WhatsApp (Fase A) escreve no SQLite legado.
- Portal web lê do Postgres.
- Migração `migrate_sqlite_to_postgres.py` deve ser rodada antes de
  cada release de portal pra atualizar o Postgres com dados novos do
  bot. (Idempotência garante segurança.)
- Em M4, bot passa a escrever direto no Postgres; SQLite vira
  read-only e é arquivado.

## Débito técnico (NÃO executar agora)

Anotado pra resolver depois de M4 estar estável:

### `aluno_phone` é fallback transitório

A coluna `interactions.aluno_phone` continua sendo gravada pelo bot
mesmo após o bot popular `aluno_turma_id`. Fica como **redundância
até validação**:
- Garante que registros pré-portal continuam consultáveis.
- Fail-safe se `aluno_turma_id` for NULL por bug.

**Cleanup futuro** (depois de pelo menos 1 mês com M4 estável):
1. Popular `aluno_turma_id` retroativamente em registros antigos via
   matching de `(telefone, ano, missao)`. Algum critério humano em
   casos ambíguos.
2. Validar que 100% dos `interactions` recentes têm `aluno_turma_id`
   preenchido.
3. Tornar `aluno_turma_id` NOT NULL (em registros novos).
4. Remover `aluno_phone` (DROP COLUMN via Alembic).

Não executar antes disso. O custo de manter a coluna por 6+ meses é
desprezível; o risco de remover prematuramente é perder dados.

### Outros itens

- `Query` interceptor pra filtrar `deleted_at IS NULL` automaticamente
  (evita esquecer no app code).
- Particionamento de `interactions` por mês quando ultrapassar 1M
  registros.
- Vacuum scheduling no Postgres de produção.

## Detectores canônicos (M7)

Catálogo de 26 detectores pedagógicos com `codigo`, `nome_humano`,
`categoria` (estrutural/argumentativo/linguistico/ortografico/forma)
e `severidade` (alta/media/baixa). Fonte da verdade:
[detectores.py](detectores.py).

Detectores fora do catálogo são humanizados graciosamente
(`flag_proposta_irregular` → "Proposta irregular") e contados em
`outros` no top-N.

## PDF (M8) — geração + storage + retenção

- **Engine**: ReportLab (puro Python). WeasyPrint foi avaliado mas
  segfaultava em alguns setups macOS+conda; ReportLab é portável e
  zero deps de sistema.
- **Storage**: `data/portal/pdfs/{ano}/{mes}/{tipo}_{escopo}_{ts}.pdf`.
  Configurável via env `STORAGE_PDFS_PATH`.
- **Em Railway**: configurar **volume persistente** apontado pra
  `/app/data/portal/pdfs/` — sem isso, PDFs somem a cada deploy.
- **Política de retenção**: 365 dias. Implementação do cleanup é
  débito técnico — script seria `DELETE FROM pdfs_gerados WHERE
  gerado_em < now() - interval '365 days'` + remover arquivo do disco.
  Não executado automaticamente.
- **Histórico em tabela**: [models.py — PdfGerado](models.py). Cada
  geração registra tipo, escopo_id, escola_id, gerado_por_user_id,
  arquivo_path, tamanho, parametros (JSON com período).
- **Email não anexa PDF** — só link. Browser baixa autenticado via
  cookie httpOnly.

## Email transacional (M8)

Templates em [email_templates/](email_templates/):
- `welcome_coordenador.html` / `welcome_professor.html` (M2)
- `reset_password.html` (M3)
- `pdf_disponivel.html` (M8)
- `atividade_encerrada.html` (M8)
- `alunos_risco.html` (M8)

**Modo dry-run** (sem `SENDGRID_API_KEY`): emails escritos em
`data/portal/emails_pendentes.jsonl` pra inspeção offline. Útil em
dev e em testes de smoke.

**Configurar SendGrid em produção:**
```bash
SENDGRID_API_KEY=SG.xxx                    # SendGrid → API Keys
SENDGRID_FROM_EMAIL=noreply@redato.app     # domínio verificado
SENDGRID_FROM_NAME=Redato
PORTAL_URL=https://portal.redato.app       # usado nos links
```

## Triggers automáticos (M8)

[triggers.py](triggers.py) com 2 triggers:

1. **`trigger_atividade_encerrada(atividade_id)`** — avisa professor
   se atividade encerrou e ainda há alunos pendentes. Idempotente:
   1× por atividade.
2. **`trigger_alunos_em_risco(turma_id)`** — alerta professor sobre
   alunos com ≥ 3 missões na faixa "Insuficiente". Rate limit:
   1× por semana por turma.

Estado de dedupe em `data/portal/triggers_log.jsonl` (não tem tabela
dedicada — pragmatismo).

**Cron externo** (Railway cron job, GitHub Actions, ou cron de outro
servidor) deve fazer `POST /admin/triggers/run` com header
`X-Admin-Token` 1× por dia. O endpoint varre todas as
turmas/atividades e dispara o que faltou.

```bash
# Exemplo de cron no Railway (config UI):
# Schedule: 0 8 * * *  (08:00 UTC = 05:00 BRT)
# Command:
curl -fsS -X POST "$PORTAL_URL/admin/triggers/run" \
  -H "X-Admin-Token: $ADMIN_TOKEN"
```

## Deploy em produção (Railway)

### Setup inicial

1. **Provisionar Postgres** no Railway (free tier serve pra piloto).
2. **Provisionar volume persistente** montado em `/app/data/portal/`
   pra storage de PDFs + JSONLs.
3. **Configurar env vars** (Railway → Variables):

   ```
   DATABASE_URL=postgresql://...      (Railway provisiona)
   JWT_SECRET_KEY=<32+ chars random>  (gere com `secrets.token_hex(32)`)
   ADMIN_TOKEN=<random secret>        (pra /admin/* e cron)
   PORTAL_URL=https://portal.redato.app
   SENDGRID_API_KEY=SG.xxx            (opcional — sem = dry-run)
   SENDGRID_FROM_EMAIL=noreply@redato.app
   TWILIO_ACCOUNT_SID=AC...           (opcional — sem = dry-run)
   TWILIO_AUTH_TOKEN=...
   TWILIO_WHATSAPP_NUMBER=whatsapp:+...
   STORAGE_PDFS_PATH=/app/data/portal/pdfs
   ```

4. **Migrar schema**: rodar `alembic upgrade head` via Railway shell
   ou hook de deploy.
5. **Migrar dados legados** (Fase A → B+): rodar uma vez:
   `python -m redato_backend.portal.migrate_sqlite_to_postgres`
   (com backup do SQLite antes).
6. **Seed de missões**: `python -m redato_backend.portal.seed_missoes`.

### Healthcheck

Railway pode pollar `GET /admin/health/full` (não exige token).
Resposta inclui `db_ping`, `storage_pdfs_writable`, e flags de
configs presentes. Status `ok` ou `degraded`.

### Smoke pós-deploy

```bash
# 1. Health geral
curl -fsS "$PORTAL_URL/admin/health/full" | jq

# 2. Gera token de prof de teste e baixa PDF
curl -X POST "$PORTAL_URL/auth/login" \
  -d '{"email":"prof@escola.br","senha":"...","lembrar_de_mim":false}' \
  -H "Content-Type: application/json" | jq -r .access_token

curl -X POST "$PORTAL_URL/portal/pdfs/dashboard-turma/<turma_id>" \
  -H "Authorization: Bearer $TOKEN" -d '{}' \
  -H "Content-Type: application/json"
# → { pdf_id, download_url, tamanho_bytes }

curl -OJ "$PORTAL_URL$DOWNLOAD_URL" \
  -H "Authorization: Bearer $TOKEN"
# → arquivo.pdf no disco
```

### Política de backup

- **Postgres**: backup automático do Railway (incluído no plano pago).
- **Volume de PDFs**: snapshot semanal do volume (Railway UI ou
  rsync programado pra S3). PDFs são reconstrutíveis a partir do DB
  re-rodando geração, mas a snapshot economiza CPU/tempo.
- **JSONLs de audit/triggers/emails**: backup junto com o volume.

## Frontend e SQLite legado

**Frontend** ([redato_frontend/](../../../../redato_frontend/)) é um
Next.js 14 separado em deploy independente. Comunica com este backend
via `NEXT_PUBLIC_API_URL` + cookies httpOnly. Em deploy: Vercel, ou
serviço Railway separado, ou subdomínio.

**SQLite legado** (`data/whatsapp/redato.db`) ainda é usado pelo bot
WhatsApp pra estado FSM (M4 não migrou isso pra Postgres — feature
flag-only). Deploy do bot pode ser:
- mesmo serviço Railway (single dyno) — usa volume pro SQLite +
  Postgres
- bot dedicado, separado do portal — Postgres compartilhado
