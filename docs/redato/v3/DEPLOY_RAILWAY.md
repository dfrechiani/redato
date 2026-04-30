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

## Frontend — Nixpacks e devDependencies

**Armadilha conhecida.** Railway/Nixpacks roda o build do frontend
com `NODE_ENV=production` injetado automaticamente. Esse env var faz
o `npm ci` **pular `devDependencies`** (comportamento padrão do npm,
ver [npm-ci docs](https://docs.npmjs.com/cli/v10/commands/npm-ci)).
Resultado: qualquer pacote necessário pro `next build` que esteja em
`devDependencies` não é instalado, e o build aborta.

**Regra dura:** todo pacote necessário em build-time vai em
`dependencies`, NÃO em `devDependencies`. Inclui:

- Compilador TypeScript (`typescript`).
- TODOS os `@types/*` que aparecem no código TS (não só os do
  Next/React — `@types/diff-match-patch`, `@types/lodash`, etc.).
- Compiladores/loaders do CSS (`tailwindcss`, `postcss`, `autoprefixer`).
- Plugins de lint/build necessários se `next build` rodar lint
  (default em produção).

**`devDependencies` legítimas** são as que rodam só localmente: test
runners (`@playwright/test`, `vitest`), formatters/lint puros
(`eslint`, `prettier`, `eslint-config-next` quando usado só em
`next lint` separado).

### Strikes históricos

| Commit | Pacote | Sintoma do build |
|---|---|---|
| `d98432b` | `typescript` | Cannot find module 'typescript' |
| `e1ffc8d` | `@types/diff-match-patch` | Could not find a declaration file for module 'diff-match-patch' |

### Validação local antes de push

Reproduzir a condição exata do Railway antes de commitar adições no
`package.json` do frontend:

```bash
cd redato_frontend
rm -rf node_modules .next
NODE_ENV=production npm ci      # pula devDependencies
NODE_ENV=production npm run build
```

Resultado esperado:

```
✓ Compiled successfully
✓ Generating static pages (XX/XX)
```

Se ver `Cannot find module ...` ou `Could not find a declaration
file for module ...`, o pacote em questão está em `devDependencies`
e precisa ir pra `dependencies`. Mover via:

```bash
npm uninstall <pkg> && npm install --save <pkg>
```

(ou edição direta no `package.json` + `npm install` pra recalcular o
lock file.)

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
| `TWILIO_VALIDATE_SIGNATURE` | `0` no boot, depois `1` | Inicia em `0` pra debugar webhook com `curl`. **Promove pra `1` só após smoke E2E passar** — ver [Sequência Twilio](#sequência-twilio--de-0-pra-1). |
| `ANTHROPIC_API_KEY` | console.anthropic.com → API Keys | Pro grading real. |
| `REDATO_DEV_OFFLINE` | `0` | **0 em prod**. 1 em dev local. |
| `LOG_LEVEL` | `INFO` | `DEBUG` se precisar diagnosticar. `WARNING` em prod estável reduz volume de logs. |

> **Não setar `ALEMBIC_AUTO_UPGRADE` em produção.** Manter a variável
> ausente. Migrations rodam **sempre manualmente** via shell do
> Railway — auto-upgrade no boot causa race condition em deploys
> simultâneos (2 dynos tentando aplicar a mesma migration → lock no
> Postgres → 1 deploy fica preso). Comando manual em
> [Sequência de migration](#sequência-de-migration-manual).

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

### Sequência Twilio — de 0 pra 1

Subimos `TWILIO_VALIDATE_SIGNATURE=0` no primeiro deploy. Sem isso,
você não consegue testar o webhook com `curl` — Twilio assina cada
request com HMAC e o handler rejeita 403 qualquer coisa que não vem
do Twilio real.

```
1. Deploy backend com TWILIO_VALIDATE_SIGNATURE=0
2. Smoke E2E (sandbox real do celular):
   a. Manda "join <duas-palavras>" pro número Twilio sandbox.
   b. Aguarda confirmação do Twilio.
   c. Manda código de turma → bot pede nome.
   d. Manda nome → bot confirma cadastro.
   e. Manda foto + número da missão → bot processa via Claude e
      responde nota.
3. Confere que cadastro chegou em `alunos_turma` (Postgres) e que
   `interactions` + `envios` tem o envio com nota.
4. Confere logs do backend pra ver se webhook foi chamado pelo
   Twilio real (não apenas por curls de teste).
5. Promove a variável: TWILIO_VALIDATE_SIGNATURE=1.
6. Re-deploy (Railway redeploya automaticamente ao mudar env).
7. Smoke novamente — passos 2.c-e. Se passar, prod travado contra
   spoof de webhook.
8. Se passo 7 falhar com 403:
   - Confere TWILIO_AUTH_TOKEN bate com o auth token do Twilio Console
     (não o "Account SID").
   - Confere que o webhook URL configurado no Twilio é HTTPS exato
     (com slash final ou sem — bate com o que o Railway expõe).
   - Volta TWILIO_VALIDATE_SIGNATURE=0, debuga, repete.
```

⚠️ Não deixe `TWILIO_VALIDATE_SIGNATURE=0` permanente. Janela de
exposição: minutos durante setup. Promove pra 1 assim que o smoke
passar.

### Sequência de migration manual

Migrations Alembic rodam **sempre manualmente** no shell do Railway —
nunca no boot do app. Razão: 2 dynos subindo simultaneamente (deploy
gémeo durante rolling restart) tentariam `alembic upgrade head` em
paralelo e um trava no `pg_advisory_lock` do outro.

Sequência por deploy de schema:

```bash
# 1. Conecta no shell do serviço backend (Railway UI → backend → "..."
#    → "Open Shell"). Ou via Railway CLI:
railway shell --service redato-backend

# 2. Confere a revisão atual e o que falta aplicar:
cd /app
alembic -c redato_backend/portal/alembic.ini current
alembic -c redato_backend/portal/alembic.ini history --verbose | head -20

# 3. Antes de upgrade em prod com dados reais: BACKUP.
bash scripts/backup_postgres.sh
# Salva em data/portal/backups/{ano}/{mes}/redato_<ts>.dump

# 4. Aplica:
alembic -c redato_backend/portal/alembic.ini upgrade head

# 5. Smoke imediato:
curl -fsS "$RAILWAY_PUBLIC_DOMAIN/admin/health/full" | jq

# 6. Se algo deu errado, reverte 1 step:
alembic -c redato_backend/portal/alembic.ini downgrade -1
# (cuidado: schema downgrade pode perder dados)
```

Se você precisar mesmo de migration automática (CI/CD em deploy
zero-touch), prefere lock externo (Redis SETNX, ou primeiro-a-bootar
mete `current_setting('cluster.is_master')`). Mas pra MVP single-tenant,
manual via shell é suficiente.

### Seed das 63 cartas estruturais (jogo "Redação em Jogo", Fase 2)

A migration `h0a1b2c3d4e5_jogo_redacao_em_jogo.py` cria as 5 tabelas
do jogo (`jogos_minideck`, `cartas_estruturais`, `cartas_lacuna`,
`partidas_jogo`, `reescritas_individuais`) mas **deixa
`cartas_estruturais` vazia**. Popular o catálogo é um passo separado:

```bash
# Pré-condição: alembic upgrade head já passou e h0a1b2c3d4e5 está
# em current. Confirmar:
alembic -c redato_backend/portal/alembic.ini current
# → expected: h0a1b2c3d4e5 (head)

# 1. Dry-run primeiro — script lê
#    backend/notamil-backend/data/seeds/cartas_redacao_em_jogo.xlsx
#    (commitado no repo) e relata o que seria feito.
cd /app   # ou repo root, depende do shell
python scripts/seed_cartas_estruturais.py
# Saída esperada: 63 cartas distribuídas em 10 seções,
#                 "DRY-RUN — would insert=63 update=0".

# 2. Apply
python scripts/seed_cartas_estruturais.py --apply

# 3. Verificação no Postgres:
psql "$DATABASE_URL" -c "SELECT count(*) FROM cartas_estruturais;"
# expected: 63

psql "$DATABASE_URL" -c "
  SELECT secao, count(*) FROM cartas_estruturais
  GROUP BY secao ORDER BY secao;
"
# expected:
#   ABERTURA          | 9
#   ARGUMENTO_DEV1    | 7
#   ARGUMENTO_DEV2    | 5
#   PROPOSTA          | 11
#   REPERTORIO_DEV1   | 5
#   REPERTORIO_DEV2   | 4
#   RETOMADA          | 4
#   TESE              | 7
#   TOPICO_DEV1       | 4
#   TOPICO_DEV2       | 7
```

O script é **idempotente**: re-rodar `--apply` é seguro. Match por
`codigo` (E01-E66 — 63 com gaps). Se o texto da carta mudar no xlsx
(Daniel reescreveu uma frase), `--apply` atualiza. Se nada mudou, é
no-op (`updated=0`).

### Seed dos 7 minidecks temáticos (Passo 2 da Fase 2)

A migration `h0a1b2c3d4e5` cria as tabelas `jogos_minideck` e
`cartas_lacuna` mas as deixa vazias. Cada minideck temático (Saúde
Mental, Inclusão Digital, Violência contra a Mulher, Educação
Financeira, Gênero e Diversidade, Meio Ambiente, Família e Sociedade)
tem ~104 cartas que substituem os placeholders das estruturais
(`[PROBLEMA]`, `[REPERTORIO]`, `[PALAVRA_CHAVE]`, `[AGENTE]`,
`[ACAO_MEIO]`).

Sequência recomendada — seedar Saúde Mental primeiro pra validar
end-to-end, depois os 6 restantes via `--all`:

```bash
# Pré-condição: migration h0a1b2c3d4e5 aplicada e seed das 63
# cartas_estruturais já feito (passo anterior).
cd /app

# 1. Listar temas disponíveis (sanity)
python scripts/seed_minideck.py --list

# 2. Saúde Mental — primeiro tema (validação focada)
python scripts/seed_minideck.py saude_mental
# expected: TOTAL = 104 distribuído como 15 P + 15 R + 30 K + 10 A
#                                       + 12 AC + 12 ME + 10 F

bash scripts/backup_postgres.sh
python scripts/seed_minideck.py saude_mental --apply

# 3. Verificação no Postgres
psql "$DATABASE_URL" -c "
  SELECT m.tema, m.nome_humano, COUNT(c.*) AS qtd_cartas
  FROM jogos_minideck m
  LEFT JOIN cartas_lacuna c ON c.minideck_id = m.id
  GROUP BY m.id, m.tema, m.nome_humano
  ORDER BY m.tema;
"
# expected (depois de saude_mental):
#   saude_mental | Saúde Mental | 104

# 4. Demais 6 temas — primeiro dry-run pra revisar antes de commitar
python scripts/seed_minideck.py --all
# Atenção: 'meio_ambiente' VAI FALHAR com erro semântico — o xlsx
# atual tem MEIO + FIM ausentes (gap conhecido). Se Daniel completou
# o xlsx desde o último report, o tema passa; senão, fica bloqueado
# no validador (decisão consciente: não seedar minideck quebrado em
# prod).
python scripts/seed_minideck.py --all --apply
# expected resumo: 6 temas OK · 1 com erro (meio_ambiente)

# 5. Verificação final
psql "$DATABASE_URL" -c "
  SELECT m.tema, COUNT(c.*) AS qtd_cartas
  FROM jogos_minideck m
  LEFT JOIN cartas_lacuna c ON c.minideck_id = m.id
  GROUP BY m.id, m.tema
  ORDER BY m.tema;
"
# expected: 6 rows, cada uma com qtd_cartas entre 100-108.
```

**Idempotência:** `--apply` é seguro de re-rodar. Match por
`(minideck_id, codigo)`. Editar o conteúdo de uma carta no xlsx e
re-rodar atualiza só ela (`cartas_updated=1`).

**Wrapping transacional:** cada tema roda na própria transação. Em
`--all`, falha de um tema (ex.: meio_ambiente bloqueado pelo
validador) NÃO bloqueia os outros — script reporta no resumo final.
Dentro de UM tema, falha em qualquer carta dispara rollback do tema
inteiro (não deixa minideck órfão sem cartas).

**Gap conhecido — Meio Ambiente:** ~~108 cartas em 5 tipos~~ **Resolvido em
`5d2f831`**: deck completo com 104 cartas (15 P + 15 R + 30 K + 10 A +
12 AC + 12 ME + 10 F). Ver `data/seeds/cartas_redacao_em_jogo.bak_pre_meioambiente.xlsx`
pra histórico pré-mudança.

## Smoke E2E — partidas (Passo 3 da Fase 2)

Os endpoints REST de partidas (POST/GET/PATCH/DELETE) estão registrados
no `unified_app` automaticamente. Smoke pós-deploy via curl:

```bash
# Pré-requisitos: ambiente local rodando OU prod com tabelas do jogo
# (migration h0a1b2c3d4e5 + seed dos minidecks). Você precisa de:
#   - PORTAL_URL: ex. https://redato-backend.up.railway.app
#   - JWT_TOKEN: token de professor responsável por uma turma com
#                ao menos 1 atividade ativa e ≥ 1 aluno.
#                (gere via POST /auth/login)
#   - ATIV_ID: UUID da atividade
#   - ALUNO_A, ALUNO_B: UUIDs de aluno_turma da turma da atividade

# 1. Lista minidecks ativos (popular dropdown UI)
curl -fsS "$PORTAL_URL/portal/jogos/minidecks" \
  -H "Authorization: Bearer $JWT_TOKEN" | jq '.[].tema'
# expected: ["saude_mental", "inclusao_digital", ..., "familia_sociedade"]

# 2. Cria partida
curl -fsS -X POST "$PORTAL_URL/portal/partidas" \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"atividade_id\": \"$ATIV_ID\",
    \"tema\": \"saude_mental\",
    \"grupo_codigo\": \"Grupo Smoke\",
    \"alunos_turma_ids\": [\"$ALUNO_A\", \"$ALUNO_B\"],
    \"prazo_reescrita\": \"2026-05-06T22:00:00-03:00\"
  }" | jq '.id'
# expected: UUID da partida criada — guarda em $PARTIDA_ID

# 3. Lista partidas da atividade (1:N decisão G.1.2)
curl -fsS "$PORTAL_URL/portal/atividades/$ATIV_ID/partidas" \
  -H "Authorization: Bearer $JWT_TOKEN" | jq '.[].grupo_codigo'
# expected: ["Grupo Smoke"]

# 4. Edita prazo
curl -fsS -X PATCH "$PORTAL_URL/portal/partidas/$PARTIDA_ID" \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"prazo_reescrita": "2026-05-13T22:00:00-03:00"}' | jq '.prazo_reescrita'

# 5. Apaga (só se não houver reescritas)
curl -fsS -X DELETE "$PORTAL_URL/portal/partidas/$PARTIDA_ID" \
  -H "Authorization: Bearer $JWT_TOKEN"
# expected: {"deleted_id": "<uuid>"}
```

Erros comuns:
- **403** "professor responsável" → seu JWT não é do professor dono
  da turma. Coordenador também recebe 403 em POST/PATCH/DELETE
  (visualiza dashboards mas não opera partidas).
- **400** "minideck ativo" → `tema` não bate com slug. Use o GET
  /portal/jogos/minidecks pra ver os disponíveis.
- **409** "Já existe" → tentativa de criar 2ª partida com mesmo
  `grupo_codigo` na mesma atividade. UI deve mostrar isso.
- **409** "reescritas de alunos" no DELETE → partida tem trabalho
  do aluno. Use PATCH pra ajustar prazo.

Tela do professor: `https://<frontend>/atividade/<atividade_id>/partidas`
— botão "Cadastrar partida", modal com tema/grupo/alunos/prazo,
edit/delete inline.

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
