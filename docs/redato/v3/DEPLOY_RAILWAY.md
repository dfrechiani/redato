# Deploy em Railway — Redato/Projeto ATO (M8+)

Roteiro pra ir do estado atual (sistema rodando local via `make demo`)
pra um deploy real em Railway com URL pública.

> **Você roda os comandos.** Esse documento é o roteiro — não automatize
> ainda. Em caso de erro, diagnóstico humano evita estrago.

## Arquitetura (Opção A — confirmada)

```
                ┌─────────────────┐
                │  Postgres       │  Railway-managed (free tier)
                │  (volume nativo)│
                └────────┬────────┘
                         │
        ┌────────────────┼────────────────┐
        ▼                                 ▼
┌───────────────────┐           ┌──────────────────┐
│ backend           │           │ frontend         │
│ unified_app.py    │           │ Next.js standalone│
│ FastAPI           │           │                  │
│ /admin /auth      │ ◄──────── │  /api/* proxy    │
│ /portal /twilio   │           │  → backend       │
│                   │           │                  │
│ Volume:           │           │ Sem volume.      │
│ /app/data         │           │                  │
└───────────────────┘           └──────────────────┘
        ▲
        │
        │ Twilio webhook (público)
        │ POST <BACKEND_URL>/twilio/webhook
        │
   ┌────────────┐
   │ WhatsApp   │
   │ Sandbox    │
   └────────────┘
```

**Por que Opção A** (portal + bot no mesmo container):

- Bot e portal compartilham o mesmo banco (Postgres) e o mesmo modelo de
  domínio. Separar em 2 dynos ≠ separação real.
- 1 serviço a menos = 1 cobrança a menos no Railway pago (cada serviço
  custa o tier mínimo individualmente).
- Deploy atômico: coordenação de versão entre portal e bot fica trivial
  (mesmo commit, mesmo dyno).
- Como portal e bot usam paths não-conflitantes (`/portal/*` vs
  `/twilio/*`), zero refactoring pra unificar — feito em
  [`redato_backend/unified_app.py`](../../backend/notamil-backend/redato_backend/unified_app.py).

Trade-offs aceitos:
- Restart do portal derruba o bot temporariamente (e vice-versa). OK
  porque restart ~10s; Twilio retenta webhook 3× automaticamente.
- Escalonamento horizontal teria que duplicar tudo. Aceitável até ~1k
  alunos ativos. Quando passar disso, dá pra separar (refactor pequeno).

## Pré-requisitos

- Conta no Railway (https://railway.app). Plano gratuito serve pra
  piloto, mas Hobby ($5/mês) recomendado pra Postgres com snapshots.
- GitHub conectado ao Railway.
- Repositório `redato_hash` push'ado pro GitHub (branch `main`).
- Domínios — opcional. Railway dá `*.up.railway.app` grátis.
- Conta SendGrid (free tier de 100 emails/dia serve pra piloto).
- Conta Twilio (sandbox grátis até 500 conversas/mês).
- Anthropic API Key (ANTHROPIC_API_KEY).

## Passo-a-passo

### 1. Criar projeto no Railway

1. Login Railway → "New Project" → "Deploy from GitHub repo".
2. Selecione o repo `redato_hash`. Railway clona.
3. Vai pedir pra escolher um serviço inicial — escolha "Empty Service"
   (vamos criar 3 serviços diferentes).

### 2. Provisionar Postgres

1. No projeto: "+ New" → "Database" → "Add PostgreSQL".
2. Railway provisiona. Anote `DATABASE_URL` em "Connect" → "Postgres
   Connection URL" (formato: `postgresql://user:pass@host:port/db`).
3. Vai aparecer também `PGHOST`, `PGPORT`, `PGUSER`, `PGPASSWORD`,
   `PGDATABASE`. Não precisa copiar — Railway expõe pra outros serviços
   via referência.

### 3. Provisionar serviço **backend** (portal + bot unificados)

1. "+ New" → "GitHub Repo" → mesmo repo.
2. Settings → **Root Directory**: `backend/notamil-backend`
3. Settings → **Volumes**: criar volume novo.
   - Mount Path: `/app/data`
   - Tamanho: 5 GB (suficiente pra ~10k PDFs em 1 ano).
4. Settings → **Variables**: adicionar (ver tabela [Env vars](#env-vars)
   abaixo).
5. Em particular, referenciar o Postgres: na variável `DATABASE_URL`,
   clicar "Add reference" → selecionar o serviço Postgres → variável
   `DATABASE_URL`. Railway resolve em runtime.
6. Save → Railway dispara deploy.
7. Após sucesso: anote a URL pública (Settings → Networking → Public
   Networking → "Generate Domain"). Vai ser algo tipo
   `https://redato-backend-production.up.railway.app`. Use isso como
   `PORTAL_URL` (do email) e `NEXT_PUBLIC_API_URL` (do front).

### 4. Aplicar migrations + seed (uma vez por deploy de schema)

Depois do deploy, abre o "Shell" do serviço backend (Railway UI →
backend → "..." → "Open Shell") e roda:

```bash
cd /app
alembic -c redato_backend/portal/alembic.ini upgrade head
python -m redato_backend.portal.seed_missoes
```

Saída esperada:
```
INFO  [alembic.runtime.migration] Running upgrade ...  → e9f1c8a2b4d5
seed_missoes (commit):
  novas: 5
  atualizadas: 0
  inalteradas: 0
  total catálogo: 5
```

### 5. Provisionar serviço **frontend** (Next.js)

1. "+ New" → "GitHub Repo" → mesmo repo.
2. Settings → **Root Directory**: `redato_frontend`
3. Settings → **Variables**:
   - `NEXT_PUBLIC_API_URL`: URL pública do backend (passo 3.7).
   - `REDATO_SESSION_COOKIE`: `redato_session` (default).
4. Save → deploy.
5. Anote a URL pública do front (Settings → Networking → Generate
   Domain). Volta no backend e atualiza `PORTAL_URL` pra essa URL —
   é o link que vai nos emails.

### 6. Configurar Twilio webhook

1. Twilio Console → Messaging → Try It Out → Send a WhatsApp Message →
   Sandbox Settings.
2. **When a message comes in**: `<BACKEND_URL>/twilio/webhook` (POST).
3. Status callback URL: deixa vazio ou aponta pro mesmo backend.
4. Save.
5. No número do sandbox Twilio, mande "join <duas-palavras>" pra opt-in
   no celular de teste.

### 7. Cron diário pros triggers automáticos

Railway tem [cron jobs nativos](https://docs.railway.app/reference/cron-jobs):

1. Backend service → Settings → "Cron Schedule": `0 8 * * *` (08:00 UTC
   = 05:00 BRT, antes do horário de aula).
2. **Restart Policy** durante o cron: deixa o serviço rodando — não é
   pra rodar como tarefa one-shot.
3. **Cron Command** (Railway aceita CLI):
   ```bash
   curl -fsS -X POST "$RAILWAY_PUBLIC_DOMAIN/admin/triggers/run" \
     -H "X-Admin-Token: $ADMIN_TOKEN"
   ```

Alternativa fora do Railway: GitHub Actions com `schedule: cron: '0 8 * * *'`,
ou cron-job.org grátis. Documentado em [README.md](../../backend/notamil-backend/redato_backend/portal/README.md#triggers-autom%C3%A1ticos-m8).

### 8. Smoke pós-deploy

Roteiro de validação (anote o que falhar):

```bash
# 1. Health
curl -fsS "$BACKEND_URL/admin/health/full" | jq
# → status: ok, db_ping: true, storage_pdfs_writable: true

# 2. Importa planilha de teste (1 escola: você)
# Crie arquivo planilha.csv com 1 linha sua + cole no shell do Railway:
echo "escola_id,escola_nome,..." > /tmp/planilha.csv
python -m redato_backend.portal.import_planilha /tmp/planilha.csv --commit

# 3. Define senha via API (ou use fluxo de email se SendGrid OK)
psql "$DATABASE_URL" -c "UPDATE professores SET senha_hash = ..."
# (use redato_backend.portal.auth.password.hash_senha pra gerar)

# 4. Login pelo frontend
# Abre <FRONTEND_URL> → login → vê dashboard

# 5. Cria atividade via UI
# Click em turma → Ativar missão → preencha → confirma

# 6. Manda WhatsApp do celular de teste pro número Twilio sandbox:
# "TURMA-XXXXX-1A-2026"
# → Bot responde pedindo nome

# 7. Manda nome → bot confirma cadastro

# 8. Manda foto + "10" → bot processa via Claude → grade real

# 9. Vê no dashboard que envio aparece com nota

# 10. Exporta PDF
curl -fsS -X POST "$BACKEND_URL/portal/pdfs/dashboard-turma/<id>" \
  -H "Authorization: Bearer $TOKEN" -d '{}'
# → pdf_id retornado, download funciona

# 11. Email transacional foi enviado (SendGrid dashboard)
# Confere em SendGrid → Activity
```

Checklist:
- [ ] `/admin/health/full` retorna `ok`.
- [ ] Login com usuário de teste funciona via frontend.
- [ ] Importar planilha pelo shell ou via UI.
- [ ] Definir senha via primeiro acesso (com SendGrid) ou hash direto.
- [ ] Login real via UI.
- [ ] Criar atividade de teste no portal.
- [ ] Disparar webhook Twilio do celular.
- [ ] Bot processa foto via Claude (não dev offline).
- [ ] Dashboard mostra envio com nota.
- [ ] Gerar PDF com sucesso.
- [ ] Email enviado via SendGrid (não jsonl dry-run).

## Env vars

### Postgres (auto-injetado pelo serviço Postgres)
- `DATABASE_URL` — referência ao serviço Postgres do projeto.

### Backend (todas obrigatórias salvo nota)

| Variável | Como obter | Notas |
|---|---|---|
| `JWT_SECRET_KEY` | `openssl rand -hex 32` | Mín. 32 chars. **Gere uma nova** — não use a do dev. |
| `ADMIN_TOKEN` | `openssl rand -hex 16` | Pra `/admin/*` e cron. **Gere uma nova**. |
| `PORTAL_URL` | URL pública do front | Usado nos links de email. |
| `STORAGE_PDFS_PATH` | `/app/data/portal/pdfs` | Aponta pro volume montado. |
| `REDATO_WHATSAPP_DB` | `/app/data/whatsapp/redato.db` | SQLite legado do bot. |
| `SENDGRID_API_KEY` | SendGrid → API Keys | Sem isso, modo dry-run jsonl. |
| `SENDGRID_FROM_EMAIL` | Email do domínio verificado | Ex.: `noreply@redato.app`. |
| `SENDGRID_FROM_NAME` | "Redato" | Nome no remetente. |
| `TWILIO_ACCOUNT_SID` | Twilio Console → Account | `AC...`. |
| `TWILIO_AUTH_TOKEN` | Twilio Console → Account | Esconda — nunca commit. |
| `TWILIO_WHATSAPP_NUMBER` | Sandbox: `whatsapp:+14155238886` | Sem o "whatsapp:" pra alguns helpers. |
| `TWILIO_VALIDATE_SIGNATURE` | `1` | **Crucial em prod**. Valida HMAC do webhook. |
| `ANTHROPIC_API_KEY` | console.anthropic.com → API Keys | Pro grading real. |
| `REDATO_DEV_OFFLINE` | `0` | **0 em prod**. 1 em dev local. |

### Frontend

| Variável | Valor |
|---|---|
| `NEXT_PUBLIC_API_URL` | URL pública do backend |
| `REDATO_SESSION_COOKIE` | `redato_session` |

### Como gerar segredos rapidamente

```bash
# JWT (mín 32 hex chars)
openssl rand -hex 32

# ADMIN_TOKEN (~32 chars hex)
openssl rand -hex 16

# Senha de teste (bcrypt)
python -c 'from redato_backend.portal.auth.password import hash_senha; print(hash_senha("teste123"))'
```

## Rollback

Railway mantém histórico de deploys. Pra reverter:

1. Service → Deployments → escolha um deploy anterior verde.
2. "..." → "Redeploy".

Pra reverter migration:

1. Identifica revision atual: `alembic -c redato_backend/portal/alembic.ini current`
2. Lista revisions: `alembic -c redato_backend/portal/alembic.ini history`
3. Down: `alembic -c redato_backend/portal/alembic.ini downgrade -1`
4. Cuidado: schema downgrade **pode perder dados** (DROP COLUMN). Faça
   backup antes (`scripts/backup_postgres.sh`).

Pra recuperar de snapshot Postgres do Railway:

1. Postgres service → "Snapshots" → escolha snapshot.
2. Click "Restore" → confirma.
3. Restore SOBRESCREVE banco corrente. Faça backup do estado atual antes
   se quiser ter recurso de fallback.

## Backup automatizado

- **Postgres**: snapshot diário automático no plano pago do Railway.
  Snapshots ficam por 30 dias. Configurar em Postgres → Backups.
- **Volume `/app/data`**: snapshot semanal manual via Railway UI →
  Volumes → "Snapshot now". Ou rsync programado pra S3 (futuro).
- **Manual local**: `bash scripts/backup_postgres.sh` (precisa de
  `DATABASE_URL` apontando pro Railway no env). Salva em
  `data/portal/backups/{ano}/{mes}/redato_<timestamp>.dump`.

## Logs e observabilidade

Railway → cada serviço → "Logs":
- Backend: stdout/stderr do uvicorn + tracebacks Python.
- Frontend: logs do Next.js (compilação + runtime).
- Postgres: logs do pg.

Filtros úteis:
- `level=error` — só erros.
- `audit-log` — eventos de domínio (criar atividade, encerrar, etc.).
- Painel custom dá pra fazer com Logflare ou Datadog (futuro).

## Deploys subsequentes

Push pra branch `main` → Railway detecta → faz auto-deploy.

Ordem segura:
1. Backend primeiro (especialmente se mudou contrato API).
2. Esperar `/admin/health/full` voltar `ok`.
3. Frontend.
4. Se mudou schema: rodar `alembic upgrade head` no shell do backend
   ANTES de subir (ou logo após, com app aceitando latência).

Pra deploy seguro, branch separada + PR review + merge:
```bash
git checkout -b feat/whatever
# ... muda ...
git push -u origin feat/whatever
# PR no GitHub. Após review:
git checkout main && git merge feat/whatever && git push
# → Railway faz deploy.
```

## Decisões implícitas

1. **Single-service backend** (Opção A, confirmada). Portal + bot
   compartilham banco e ciclo de vida. Refactor pra Opção B/C é fácil
   se virar gargalo.
2. **Volume `/app/data`** acomoda PDFs + JSONLs + SQLite legado.
   Railway é único single-source-of-truth — sem S3 ainda. PDFs duplicáveis
   a partir do banco (re-render).
3. **Cron externo via Railway cron** chama `/admin/triggers/run`. Mais
   simples que rodar scheduler interno (single-leader, sem race).
4. **Healthcheck em `/admin/health/full`** — não `/admin/health`. O full
   testa db_ping + storage write, dá sinal mais útil.
5. **`REDATO_DEV_OFFLINE=0` em prod** — bot chama Anthropic real.
   Anthropic key obrigatória.
6. **`TWILIO_VALIDATE_SIGNATURE=1` em prod** — sem isso, qualquer um
   pode fingir webhook do Twilio e cadastrar alunos falsos.
7. **Não usei Dockerfile** — Nixpacks resolve setup Python + Node sem
   precisar Dockerfile manual. Builds rápidos, cache nativo do Railway.
8. **Sem rate limiting agora** — Cloudflare na frente vem em Fase C.
9. **SSL automático** via Railway. Domínio customizado fica pra depois
   (registrar `redato.app` ou `projetoato.app` e apontar CNAME).
10. **Plano free vs pago**: piloto pode rodar no free tier ($5/mês de
    créditos), mas Postgres com snapshots automáticos exige Hobby
    ($5/mês). Pra MVP com 1 escola: ~$10/mês total.

## Não fazer ainda

- Domínio customizado — depois do MVP validado.
- SSL config manual — Railway provê.
- Rate limiting via Cloudflare — Fase C.
- Multi-region — não relevante (1 escola pra começar).
- Auto-scaling horizontal — Railway free tier não suporta; quando
  passar pra pago, decidir se precisa.
- Migration automática no boot — preferimos manual via shell pra evitar
  lock concorrente em deploys gémeos.

## Artefatos de deploy gerados (M8+)

```
backend/notamil-backend/
├── nixpacks.toml             # config Railway pra backend
├── railway.toml              # restart policy + healthcheck
├── Procfile                  # fallback se Railway não usar nixpacks
├── requirements.txt          # incluindo reportlab + bcrypt + pyjwt
├── redato_backend/
│   └── unified_app.py        # FastAPI portal + bot na mesma porta
└── scripts/
    └── backup_postgres.sh    # pg_dump + pg_restore manual

redato_frontend/
├── nixpacks.toml             # config Railway pro Next.js
└── railway.toml              # healthcheck em /login
```
