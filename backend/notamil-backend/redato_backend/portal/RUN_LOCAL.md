# Rodar Redato local — end-to-end em 15 minutos

Roteiro pra subir o sistema completo (portal API + bot WhatsApp +
frontend Next.js) com dados sintéticos, sem precisar de SendGrid,
Twilio ou ngrok.

## Pré-requisitos

| Software | Versão mínima | Como instalar |
|---|---|---|
| Python | 3.12+ | `brew install python@3.12` |
| Node | 20+ | `brew install node` |
| Postgres | 14+ | `brew install postgresql@16` |
| `make` | qualquer | já vem no macOS |

Postgres precisa estar rodando antes do setup:

```bash
brew services start postgresql@16
```

Não precisa criar database manualmente — o Makefile faz.

## Sequência de comandos (15 minutos do zero)

### 1. Configurar `.env` do backend

```bash
cd backend/notamil-backend
cp .env.example .env  # se ainda não existe; senão edita o existente
```

Garanta que tem (substitua `$USER` pelo seu username):

```
DATABASE_URL=postgresql://YOUR_USER@localhost:5432/redato_portal_dev
JWT_SECRET_KEY=qualquer_string_de_32_chars_ou_mais_pra_dev_local_aqui
ADMIN_TOKEN=demo-admin-token
PORTAL_URL=http://localhost:3010
```

### 2. Instalar dependências

```bash
# Backend (na raiz de backend/notamil-backend/)
pip install -r requirements.txt

# Frontend (na raiz de redato_frontend/)
cd ../../redato_frontend
npm install
```

### 3. Subir tudo (a partir da raiz do repo)

```bash
cd /caminho/do/redato_hash    # raiz, onde está o Makefile
make demo
```

Esse comando único:

1. Cria `redato_portal_dev` no Postgres se não existir.
2. Roda `alembic upgrade head` (M1-M8 + extensão de modos).
3. Popula `missoes` (seed das 5 oficinas REJ 1S).
4. Importa `data/seeds/planilha_demo.csv` (1 escola, 1 coord, 1 prof,
   2 turmas).
5. Define senha `demo123` para coord e prof — bypass do email.
6. Cria 3 alunos sintéticos por turma + 1 atividade ativa
   (RJ1·OF10·MF na turma 1A) + 2 envios sintéticos com nota processada
   (Ana 720 = Bom, Bruno 320 = Insuficiente).
7. Sobe portal API, bot WhatsApp e frontend em background.
8. Imprime URLs + credenciais + códigos de turma.

Saída esperada:

```
Portal (frontend):   http://localhost:3010
Backend API:         http://localhost:8091
Bot WhatsApp:        http://localhost:8090/twilio/webhook
Health:              http://localhost:8091/admin/health/full

Credenciais (senha = demo123):
  Professora:   prof@demo.redato
  Coordenadora: coord@demo.redato

Códigos de turma (pra simular cadastro de aluno):
  1A: TURMA-CE001-1A-2026
  1B: TURMA-CE001-1B-2026
```

### 4. Stop quando terminar

```bash
make stop
```

## Outros comandos do Makefile

```bash
make help               # lista targets disponíveis
make whoami             # mostra creds e códigos sem reimportar
make health             # checa /admin/health/full
make logs-portal        # tail nos logs do portal
make logs-bot           # tail nos logs do bot
make logs-frontend      # tail nos logs do Next.js
make reset-db           # DROP + CREATE database (perde tudo)
make setup-demo         # só popula DB, sem subir servers
make run-portal         # sobe só portal (foreground)
make run-bot            # sobe só bot (foreground)
make run-frontend       # sobe só Next.js (foreground)
```

Pra desenvolver com hot-reload, geralmente é melhor abrir 3
terminais e rodar cada `make run-*` em foreground — você vê os logs
direto sem `tail`.

## Roteiro de validação visual

Depois de `make demo` rodar com sucesso, abre no browser:

### a. Login da professora

1. http://localhost:3010 → redirect pra `/login`
2. Email `prof@demo.redato`, senha `demo123`, "Entrar".
3. Cai em `/` com "Olá, Maria." e card da turma "1A" (a 1B existe
   mas pertence ao mesmo professor — vê as duas).

### b. Detalhe da turma + dashboard

1. Clica no card "1A".
2. Vê código de turma `TURMA-CE001-1A-2026` (botão Copiar funciona
   com toast).
3. Atividade `RJ1·OF10·MF Foco C3` aparece no card de Atividades com
   2 envios.
4. Clique na aba "Dashboard" — vê:
   - Distribuição: Foco mostra Ana em 161-200 (160) e Bruno em
     41-80 (64) — escala foco_c3 normaliza nota total / 5.
   - Top detectores: "Proposta de intervenção vaga" + "Repetição
     lexical" (das flags do redato_output sintético).
   - Alunos em risco: vazio (Bruno só tem 1 missão baixa, precisa ≥2).
   - Evolução: vazio ("Histórico aparece após 3 missões").
5. Clique na atividade → vê tabela de envios com Ana 720 + Bruno
   320 + Carla pendente.
6. Clique "Ver feedback →" da Ana → tela de feedback com nota,
   competências, audit pedagógico.

### c. Login da coordenadora + dashboard escola

1. Logout (dropdown do usuário).
2. Login como `coord@demo.redato`, senha `demo123`.
3. Home agrupa turmas por professor — só Maria com 2 turmas.
4. Dropdown do user → "Dashboard escola" → `/escola/dashboard`.
5. Vê:
   - Comparação entre turmas: vazia ("aparece com ≥ 2 turmas com
     dados") porque turma 1B não tem envios.
   - Distribuição da escola: igual à turma A (única com envios).
   - Resumo de turmas: 1A com média 520, 1B sem média.
6. Coord NÃO vê botão "+ Ativar missão" nas turmas (só prof cria).

### d. Exportar PDF

1. Voltar a `/escola/dashboard` (ou turma com dados).
2. Clicar "Exportar PDF da escola" → modal com período opcional.
3. "Gerar PDF" → toast "PDF gerado (5 KB)" + browser baixa
   `redato_dashboard_escola_20260427.pdf`.
4. PDF tem header Redato + Projeto ATO + data, distribuição, top
   detectores, alunos em risco, comparação de turmas, resumo, footer
   com paginação + LGPD.
5. Em `/escola/historico-pdfs` aparece o PDF recém gerado com botão
   baixar.

### e. Mudar senha + sair de todas

1. Dropdown → "Perfil".
2. "Mudar senha" → senha atual `demo123`, nova `demo456789`,
   confirmar → toast "Senha alterada".
3. "Sair de todas as sessões" → confirma → redirect /login.

## Simular bot via curl (sem Twilio real)

`make setup-demo` força `TWILIO_VALIDATE_SIGNATURE=0` no `.env`
porque `_bootstrap()` do bot recarrega `.env` com `override=True`,
sobrescrevendo qualquer variável de subprocess. Bot aceita POST puro
no webhook.

> ⚠️ **O bot tenta enviar resposta via Twilio mesmo em dev.** Se o
> número da curl não for aprovado no sandbox Twilio, o handler loga
> `HTTP 400 21211 ('To' number ... is not a valid phone number)` —
> esperado. **O cadastro/processamento acontece antes do send**, então
> AlunoTurma fica salvo no Postgres mesmo com Twilio falhando. Pra
> silenciar o erro de send: comente `TWILIO_ACCOUNT_SID` no `.env`.

### Cenário 1: aluno novo se cadastra

```bash
# Phone novo manda "oi" → bot pede código de turma
curl -s -X POST http://localhost:8090/twilio/webhook \
  -d "From=whatsapp:+5511555000111" \
  -d "Body=oi" \
  -d "NumMedia=0"

# Aluno manda código de turma
curl -s -X POST http://localhost:8090/twilio/webhook \
  -d "From=whatsapp:+5511555000111" \
  -d "Body=TURMA-CE001-1A-2026" \
  -d "NumMedia=0"

# Bot pede nome — manda nome completo
curl -s -X POST http://localhost:8090/twilio/webhook \
  -d "From=whatsapp:+5511555000111" \
  -d "Body=João da Silva Demo" \
  -d "NumMedia=0"
```

Cada chamada retorna `200 OK` (resposta TwiML vazia — bot envia via
Twilio em background). Pra ver as **respostas** que ele teria mandado,
acompanhe `make logs-bot` ou veja a tabela `alunos` no SQLite:

```bash
sqlite3 backend/notamil-backend/data/whatsapp/redato.db \
  "SELECT phone, nome, estado FROM alunos ORDER BY rowid DESC LIMIT 5;"
```

Esperado: `+5511555000111 | João da Silva Demo | READY`.

E em `alunos_turma` no Postgres:

```bash
psql -d redato_portal_dev -c \
  "SELECT nome, telefone FROM alunos_turma \
   WHERE telefone='+5511555000111';"
```

### Cenário 2: aluno cadastrado tenta missão sem atividade ativa

A turma 1A só tem RJ1·OF10·MF aberta. Tentar mandar missão 11:

```bash
curl -s -X POST http://localhost:8090/twilio/webhook \
  -d "From=whatsapp:+5511555000111" \
  -d "Body=11" \
  -d "NumMedia=0"
```

Bot responde com `MSG_SEM_ATIVIDADE_ATIVA` (vê logs).

### Cenário 3: dispara triggers automáticos manualmente

```bash
curl -s -X POST http://localhost:8091/admin/triggers/run \
  -H "X-Admin-Token: demo-admin-token" | jq
```

Saída:

```json
{
  "encerradas_avisadas": 0,
  "risco_avisados": 0,
  "skipped": 1
}
```

Pra ver email gerado em modo dry-run:

```bash
tail -n 1 backend/notamil-backend/data/portal/emails_pendentes.jsonl \
  | jq
```

## Onde estão os arquivos importantes

```
data/portal/
├── pdfs/<ano>/<mes>/         # PDFs gerados (storage local)
├── audit_log.jsonl           # auditoria de criar atividade, encerrar etc.
├── triggers_log.jsonl        # dedup dos triggers automáticos
├── emails_pendentes.jsonl    # dry-run de emails (sem SENDGRID_API_KEY)
└── imports/                  # relatórios JSON de cada importação

data/whatsapp/
└── redato.db                 # SQLite do bot (FSM state, sessions)
```

## Troubleshooting

### "psql: error: ... does not exist"
DB ainda não foi criado. `make db-create` ou só rode `make demo` que
inclui isso.

### "address already in use" nas portas 3010/8090/8091
Outra instância já rodando. `make stop` derruba.

### "alembic.util.exc.CommandError: Can't locate revision identified by ..."
DB tem migration history corrompida (provavelmente de testes que
deixaram resíduo). `make reset-db && make setup-demo` resolve em dev.
**Não rode `make reset-db` em prod — apaga tudo.**

### "ANTHROPIC_API_KEY não setada" no bot
Sem a key, o bot **não chama o Claude** em respostas reais — usa stub
determinístico (em `dev_offline.py`). OCR também é stubado. Suficiente
pro fluxo end-to-end de FSM e cadastro; pra correção real em demo,
configure ANTHROPIC_API_KEY no `.env`.

### Frontend mostra "Erro 500"
Provavelmente backend caiu. `make logs-portal` mostra o stack trace.
Comum: `DATABASE_URL` errada ou Postgres offline (`brew services
start postgresql@16`).

### `make demo` finaliza antes do Next.js terminar de compilar
Next.js dev mode compila on-demand. Primeiro acesso a `/login`
demora ~5s. Subsequentes < 1s. Acompanhe `make logs-frontend` —
quando aparecer "✓ Compiled /login", está pronto.

## Limites do setup local vs produção

| Aspecto | Local (este roteiro) | Produção (Railway) |
|---|---|---|
| Email | dry-run em jsonl | SendGrid REST |
| WhatsApp | curl no webhook | Twilio Sandbox/API |
| Storage de PDFs | `data/portal/pdfs/` (efêmero entre `reset-db`) | Volume persistente |
| HTTPS | ❌ http puro | TLS via Railway |
| Credenciais demo | senha fixa "demo123", token JWT random | env vars seguros |
| Triggers | `curl /admin/triggers/run` manual | Cron diário |

Pra deploy em Railway, ver
[../portal/README.md](README.md#deploy-em-produção-railway).
