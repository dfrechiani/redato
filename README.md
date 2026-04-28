# Redato — corretora ENEM do Projeto ATO

Plataforma de correção automática de redações ENEM via WhatsApp +
portal do professor com dashboards agregados. Avalia textos pelas 5
competências oficiais do INEP usando Claude (Anthropic).

- **App**: Redato (corretora).
- **Programa pedagógico**: Projeto ATO — Agência Textual de Operação
  (sucessor do nome técnico antigo "Redação em Jogo").

## Status

Fase B+ entregue (M1-M8): bot WhatsApp, importação SEDUC, auth +
primeiro acesso, frontend Next.js, gestão de turmas/atividades,
dashboards de turma + escola + evolução do aluno, geração de PDF e
emails transacionais. Validação local end-to-end via `make demo` em
~15 min.

```
M1 modelo de dados (Postgres) ────── 7/7 testes
M3 auth (JWT + 1º acesso + reset) ── 13/13
M4 bot WhatsApp + atividades ─────── 12/12
M5 frontend Next.js (login + reset)  16/16 E2E
M6 gestão (turmas, atividades) ───── 14/14
M7 dashboards + detectores ────────  10/10 + 7/7
M8 PDF + email + triggers ────────── 11/11

Total: 74 backend + 44 E2E = 118 testes verdes
```

Próximo: deploy em Railway (artefatos prontos em
[docs/redato/v3/DEPLOY_RAILWAY.md](docs/redato/v3/DEPLOY_RAILWAY.md)).

## Estrutura

```
redato_hash/
├── backend/notamil-backend/      # Backend Python (FastAPI)
│   ├── redato_backend/
│   │   ├── unified_app.py        # M8+ — portal + bot na mesma porta
│   │   ├── portal/               # auth, gestão, dashboards, PDF, emails
│   │   │   ├── models.py         # SQLAlchemy 2.0 (Postgres)
│   │   │   ├── auth/             # JWT + bcrypt + middleware
│   │   │   ├── portal_api.py     # endpoints /portal/*
│   │   │   ├── pdf_generator.py  # ReportLab (M8)
│   │   │   ├── triggers.py       # email transacional (M8)
│   │   │   ├── detectores.py     # catálogo canônico (M7)
│   │   │   ├── formatters.py     # série/missão humanizadas
│   │   │   ├── seed_missoes.py   # 5 missões REJ 1S
│   │   │   ├── migrations/       # Alembic
│   │   │   └── email_templates/
│   │   └── whatsapp/             # bot Twilio (Fase A + M4)
│   ├── scripts/
│   │   ├── setup_demo.py         # popula DB + cria usuários demo
│   │   ├── backup_postgres.sh    # pg_dump manual
│   │   └── test_m{1,3,4,6,7,8}_*.py  # smoke tests por milestone
│   ├── nixpacks.toml             # config Railway
│   ├── railway.toml
│   └── requirements.txt
│
├── redato_frontend/              # Frontend Next.js 14 (App Router)
│   ├── app/
│   │   ├── (app)/                # rotas autenticadas
│   │   │   ├── page.tsx          # home com lista de turmas
│   │   │   ├── turma/[turma_id]/
│   │   │   ├── atividade/[atividade_id]/
│   │   │   ├── escola/dashboard/ # coord apenas
│   │   │   └── perfil/
│   │   ├── login/, primeiro-acesso/, reset-password/
│   │   └── api/                  # proxy /api/auth/* + /api/portal/*
│   ├── components/portal/        # TurmaCard, AtividadeCard, charts...
│   ├── lib/{format,api,auth-*}.ts
│   ├── tests-e2e/                # Playwright + mock-backend
│   └── nixpacks.toml
│
├── frontend/notamil-frontend/    # Frontend legado (M0 - pré-M5)
│                                 # Mantido pra histórico. Não usado.
│
├── docs/redato/v3/
│   ├── DEPLOY_RAILWAY.md         # roteiro de deploy passo-a-passo
│   ├── series_oficinas_canonico.md  # declaração canônica série→missão
│   ├── REPORT_caminho2_realuse.md   # spec da Fase B+
│   └── ...
│
├── scripts/
│   └── demo_up.py                # orquestrador que sobe 3 servidores
│
├── Makefile                      # `make demo` / `make stop` / etc.
└── DEV.md                        # roteiro de dev (Fase A + Fase B)
```

## Rodar local em 15 min

Pré-requisitos: Python 3.12+, Node 20+, Postgres 14+, `make`.

```bash
# Postgres rodando (Homebrew):
brew services start postgresql@16

# Setup + sobe 3 servidores em background:
make demo

# →  http://localhost:3010   (frontend)
# →  prof@demo.redato / demo123  ou  coord@demo.redato / demo123
```

Roteiro completo:
[backend/notamil-backend/redato_backend/portal/RUN_LOCAL.md](backend/notamil-backend/redato_backend/portal/RUN_LOCAL.md).

```bash
make help        # comandos disponíveis
make whoami      # creds + códigos de turma
make health      # /admin/health/full
make stop        # derruba tudo
make reset-db    # DROP + CREATE database (dev only)
```

## Stack

- **Backend**: Python 3.12 · FastAPI · SQLAlchemy 2.0 · Alembic ·
  Postgres · bcrypt · PyJWT · ReportLab · SendGrid REST · Twilio.
- **Frontend**: Next.js 14 (App Router) · TypeScript · Tailwind CSS ·
  zustand · sonner · Playwright (E2E).
- **AI**: Anthropic SDK (Claude Sonnet 4.6 / Opus 4.7 conforme tarefa)
  com prompt caching + tool use estruturado.
- **Storage local**: Postgres (domínio) + SQLite (FSM do bot, legado
  da Fase A) + filesystem (PDFs em volume).

## Variáveis de ambiente

Não vão pro Git. Use `.env.example` como base:

```
# Backend (backend/notamil-backend/.env)
DATABASE_URL=postgresql://user@localhost:5432/redato_portal_dev
JWT_SECRET_KEY=<32+ chars random — gere com `openssl rand -hex 32`>
ADMIN_TOKEN=<random>
PORTAL_URL=http://localhost:3010
ANTHROPIC_API_KEY=sk-ant-...        # opcional em dev (cai em stub)
SENDGRID_API_KEY=SG...               # opcional (dry-run jsonl)
TWILIO_ACCOUNT_SID=AC...             # opcional (dry-run)
TWILIO_AUTH_TOKEN=...
TWILIO_WHATSAPP_NUMBER=whatsapp:+...
TWILIO_VALIDATE_SIGNATURE=0          # 1 em prod
REDATO_DEV_OFFLINE=1                 # 0 em prod
```

```
# Frontend (redato_frontend/.env.local)
NEXT_PUBLIC_API_URL=http://localhost:8091
REDATO_SESSION_COOKIE=redato_session
```

Lista completa em
[docs/redato/v3/DEPLOY_RAILWAY.md](docs/redato/v3/DEPLOY_RAILWAY.md#env-vars).

## Deploy

Roteiro Railway: [docs/redato/v3/DEPLOY_RAILWAY.md](docs/redato/v3/DEPLOY_RAILWAY.md).

Arquitetura: 1 serviço backend (portal+bot unificados via
`unified_app.py`) + 1 serviço frontend + Postgres provisionado pelo
Railway. Volume persistente em `/app/data` pra PDFs e SQLite legado.

## Testes

```bash
# Backend (cada milestone tem seu smoke):
cd backend/notamil-backend
python redato_backend/portal/test_detectores.py        # 7 unit
python scripts/test_m{1,3,4,6,7,8}_*.py               # smoke E2E

# Frontend:
cd redato_frontend
npm run lint
npm run build
npm run test:e2e        # Playwright + mock-backend
```

## Documentação

- [DEV.md](DEV.md) — roteiro de dev local
- [CLAUDE.md](CLAUDE.md) — guia rápido pra sessões com Claude Code
- [docs/redato/v3/](docs/redato/v3/) — spec, decisões, roteiros
- [docs/redato/v3/series_oficinas_canonico.md](docs/redato/v3/series_oficinas_canonico.md) — séries × missões
- [docs/redato/MEMORY/](docs/redato/MEMORY/) — memória persistente
  (decisões de arquitetura, evolução)

## Licença

Privado. Todos os direitos reservados — Projeto ATO.
