# Redato — Front-end Next.js (M5 + M6)

Portal web do **Redato** (corretora) — turmas, atividades e dashboard
do programa **Projeto ATO**.

- **M5** entregou o esqueleto de auth: login, primeiro acesso, reset de
  senha, middleware, header.
- **M6** adiciona gestão: home com lista de turmas, detalhe da turma,
  modal "ativar missão", detalhe da atividade com agregados, tela de
  feedback do aluno, perfil do user (mudar senha, sair de todas as
  sessões).
- Dashboard agregado escola, geração de PDF e demais relatórios ficam
  em M7+.

**Spec:** [docs/redato/v3/REPORT_caminho2_realuse.md](../docs/redato/v3/REPORT_caminho2_realuse.md)
seção 5.5 (M5).

## Stack

- Next.js 14 (App Router) + TypeScript
- Tailwind CSS 3
- zustand (auth store)
- sonner (toasts)
- Playwright (smoke tests)
- Fontes Google: DM Serif Display (display), Source Sans 3 (body),
  JetBrains Mono (labels/code)

## Setup local

### Pré-requisitos

- Node 20+ (testado com 20 e 24)
- Backend M3 rodando em `http://localhost:8091`
  ([../backend/notamil-backend/redato_backend/portal/portal_app.py](../backend/notamil-backend/redato_backend/portal/portal_app.py))

### Rodar

```bash
cd redato_frontend
cp .env.local.example .env.local   # ajusta NEXT_PUBLIC_API_URL se precisar
npm install
npm run dev                        # http://localhost:3000
```

### Subir backend pra testar contra dados reais

Em outro terminal:

```bash
cd backend/notamil-backend
uvicorn redato_backend.portal.portal_app:app --port 8091 --reload
```

Pra criar usuários de teste, use o importador M2 (planilha) — ver
[../backend/notamil-backend/redato_backend/portal/IMPORT_GUIDE.md](../backend/notamil-backend/redato_backend/portal/IMPORT_GUIDE.md).

### Build de produção

```bash
npm run build
npm run start                      # serve build na 3000
```

## Smoke test (Playwright)

Os testes não dependem do backend real. Um mock em
`tests-e2e/mock-backend.mjs` sobe junto com o `next dev` via
`webServer` do Playwright.

```bash
npx playwright install chromium    # 1ª vez, baixa o browser
npm run test:e2e
```

Cobre:
- Renderização do `/login`
- Submit vazio / credenciais erradas / usuário inativo
- Login OK → redirect pra `/`
- Middleware redireciona não autenticado de rota privada pra `/login`
- Logout limpa sessão e volta pra `/login`
- `/primeiro-acesso`: sem token, token expirado, token inválido,
  validação local de senha (fraca, divergente), fluxo OK
- `/reset-password`: solicitar (sem token), confirmar (com token),
  token expirado

## Estrutura

```
redato_frontend/
├── app/
│   ├── (app)/                 # grupo de rotas autenticadas
│   │   ├── layout.tsx         # carrega user via cookie + Header
│   │   └── page.tsx           # home autenticada
│   ├── login/                 # /login (público)
│   ├── primeiro-acesso/       # /primeiro-acesso?token=...
│   ├── reset-password/        # /reset-password[?token=...]
│   ├── api/auth/              # proxy local que cuida do cookie httpOnly
│   ├── error.tsx              # boundary de erro 500
│   ├── not-found.tsx          # 404
│   ├── globals.css
│   └── layout.tsx             # root layout com fontes + Toaster
├── components/
│   ├── layout/
│   │   ├── AuthHydrator.tsx   # injeta user no zustand
│   │   └── Header.tsx
│   └── ui/
│       ├── Button.tsx
│       ├── Card.tsx
│       ├── EmptyState.tsx
│       ├── FormField.tsx
│       ├── Input.tsx
│       ├── LoadingSpinner.tsx
│       ├── Logo.tsx
│       └── PasswordInput.tsx
├── hooks/
│   └── useAuth.ts             # store zustand
├── lib/
│   ├── api.ts                 # fetch backend (server-side only)
│   ├── auth-client.ts         # wrapper /api/auth/* (browser)
│   ├── auth-server.ts         # cookies + session helpers (server)
│   ├── cn.ts                  # className helper
│   └── env.ts
├── tests-e2e/
│   ├── auth.spec.ts
│   └── mock-backend.mjs       # backend mock pro Playwright
├── types/
│   └── api.ts                 # tipos compartilhados com FastAPI
├── middleware.ts              # proteção de rotas
├── tailwind.config.ts
├── next.config.mjs
└── tsconfig.json
```

## Fluxo de auth

```
Browser              Next.js app (proxy)         Backend FastAPI
─────────────────────────────────────────────────────────────────
POST /api/auth/login
   email/senha   ───►
                     POST /auth/login         ───►  valida + JWT
                  ◄────────────────────────────────  retorna token
                     GET /auth/me Bearer <jwt>───►
                  ◄────────────────────────────────  user info
   ◄ Set-Cookie: redato_session=<jwt> HttpOnly
   ◄ body: AuthenticatedUser

GET /api/auth/me
   Cookie: ...     ───►
                     GET /auth/me Bearer <jwt>───►
                  ◄────────────────────────────────  user info
   ◄ body: AuthenticatedUser
```

O JWT **nunca** é exposto pra JavaScript do browser — fica em cookie
`HttpOnly`. Caches XSS não conseguem exfiltrar a sessão.

## Padrões de componentes

- Componentes UI vivem em `components/ui/`. Tailwind direto, sem
  styled-components ou CSS modules.
- Forms usam `FormField` envolvendo `Input` ou `PasswordInput`. O
  `FormField` injeta `id`, `aria-invalid` e `aria-describedby`.
- Erros de submit ficam num `<div role="alert">` dentro do form.
- Loading nos botões: prop `loading` mostra spinner + desabilita.
- Telas públicas (login, reset, primeiro-acesso) são `'use client'`
  inteiras — pequenas, com estado local.
- Telas autenticadas preferem Server Components quando possível
  (`(app)/page.tsx` busca user server-side).
- Toasts: `import { toast } from 'sonner'`. Sucesso, erro e info.

## Tokens de design

- `--redato-ink: #0f1117` — preto principal (texto, botão primário)
- `--redato-lime: #b9f01c` — accent de marca (link "Projeto ATO" no
  logo, ring de focus, botão secundário)
- Fontes: `font-display` (DM Serif), `font-body` (Source Sans),
  `font-mono` (JetBrains Mono)
- Tailwind expõe escalas de `ink-*` (50/100/200/400/600/800/900)
  pra cinza tonalizado e classes utilitárias `bg-muted`, `text-danger`,
  `border-border`.

## Decisões técnicas

| Decisão | Justificativa |
|---|---|
| **App Router** (não Pages) | Server Components reduzem JS no client; rotas + layouts compostos são naturais pra `(app)/layout.tsx` autenticado. |
| **JWT em cookie httpOnly via proxy** | Browser nunca vê o token. Mais seguro contra XSS que `localStorage` ou cookie legível. |
| **zustand** (não Context) | Boilerplate mínimo; o store é só um cache UI — fonte de verdade é o cookie + `/auth/me`. |
| **sonner pra toasts** | Mais leve que `react-hot-toast`, integra bem com Tailwind. |
| **Mock backend pro Playwright** | Testes ficam determinísticos, sem dependência do Postgres. Cobertura de happy path + ramos de erro. |
| **Validação de senha local** | Espelha `validate_senha` do backend (8+ chars, 1 letra, 1 número). UX: erro imediato sem round-trip. |
| **Lembrar de mim = 30d / default = 8h** | Casado com expiração JWT do backend. |

## Rotas autenticadas

```
/                                                Home — turmas do user
/turma/[turma_id]                                Detalhe + abas Atividades/Dashboard
/turma/[turma_id]/aluno/[aluno_id]/evolucao      Evolução do aluno (M7)
/atividade/[atividade_id]                        Detalhe da atividade
/atividade/[id]/aluno/[aluno_id]                 Feedback completo do aluno
/escola/dashboard                                Dashboard agregado da escola (coord, M7)
/perfil                                          Perfil + mudar senha + sair de todas
```

Todas dentro do route group `(app)/` — server fetch de `/auth/me` no
layout, `Header` sticky, redirect /login em 401.

## Componentes M6 reutilizáveis

- `TurmaCard`, `AtividadeCard` — cards de listagem
- `CodigoTurmaBox` — caixa preta com código + botão copiar (toast)
- `AlunoListItem` — linha de aluno + remover (modal de confirmação)
- `DistribuicaoNotasChart` — barras horizontais (sem dependência)
- `TopDetectoresBadges` — badges com contagem
- `ModalConfirm` — wrapper genérico de confirmação
- `AtivarMissaoModal` — fluxo de criar atividade com aviso de duplicata
- `Badge` — variantes ativa/agendada/encerrada/warning/lime

## O que NÃO está aqui (M7+)

- Dashboard agregado por escola
- Geração de PDF do professor
- WebSocket / Realtime (se necessário)
- Email transacional via portal (admin já tem via M3)

## Endpoints do backend que esse front consome

### M5 — auth

```
POST /auth/login
POST /auth/logout
GET  /auth/me
POST /auth/primeiro-acesso/validar
POST /auth/primeiro-acesso/definir-senha
POST /auth/reset-password/solicitar
POST /auth/reset-password/confirmar
```

### M6 — perfil + portal

```
POST /auth/perfil/mudar-senha
POST /auth/perfil/sair-todas-sessoes

GET   /portal/missoes
GET   /portal/turmas
GET   /portal/turmas/{turma_id}
PATCH /portal/turmas/{turma_id}/alunos/{aluno_turma_id}

POST  /portal/atividades
GET   /portal/atividades/{atividade_id}
PATCH /portal/atividades/{atividade_id}
POST  /portal/atividades/{atividade_id}/encerrar
GET   /portal/atividades/{atividade_id}/envios/{aluno_turma_id}
POST  /portal/atividades/{atividade_id}/notificar
GET   /portal/atividades/{atividade_id}/texto-notificacao
```

### M7 — dashboards

```
GET   /portal/turmas/{turma_id}/dashboard
GET   /portal/escolas/{escola_id}/dashboard
GET   /portal/turmas/{turma_id}/alunos/{aluno_turma_id}/evolucao
```

Catálogo canônico de detectores em
[backend/notamil-backend/redato_backend/portal/detectores.py](../backend/notamil-backend/redato_backend/portal/detectores.py)
— 26 detectores (estrutural, argumentativo, linguistico, ortografico,
forma) com `nome_humano`, `categoria`, `severidade`. Detectores fora do
catálogo são humanizados graciosamente (`flag_proposta_irregular` →
"Proposta irregular") e contados em `outros` no top-N.

Auth em
[backend/notamil-backend/redato_backend/portal/auth/api.py](../backend/notamil-backend/redato_backend/portal/auth/api.py),
portal em
[backend/notamil-backend/redato_backend/portal/portal_api.py](../backend/notamil-backend/redato_backend/portal/portal_api.py).
