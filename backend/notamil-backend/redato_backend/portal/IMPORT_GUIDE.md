# Guia de importação de planilha (M2 — Redato / Projeto ATO)

> **Nota de nomenclatura:** o app/sistema continua sendo **Redato**.
> O programa pedagógico que rodava sob o nome "Redação em Jogo" passou
> a se chamar **Projeto ATO** (Agência Textual de Operação). Templates
> de email, UI e copy externa devem citar "Redato (Projeto ATO)".
> Nomes de pacote, módulo e domínio técnico permanecem `redato_*`.

Onboarding em massa de escolas, coordenadores, professores e turmas via
planilha. **Não inclui alunos** — eles entram pelo bot WhatsApp em M4
usando `codigo_join` da turma.

## Estrutura da planilha

8 colunas, headers obrigatórios na 1ª linha. XLSX (1ª aba) ou CSV.

| coluna | tipo | exemplo | obs |
|---|---|---|---|
| `escola_id` | string | `SEDUC-CE-001` | regex default `^[A-Z]+-[A-Z]{2}-\d{3,}$` (configurável via env `PORTAL_ESCOLA_ID_REGEX`) |
| `escola_nome` | string | `Escola Estadual Boa Vista` | livre |
| `coordenador_email` | string | `coord@escola.br` | validado por `email-validator` |
| `coordenador_nome` | string | `Maria Silva` | livre |
| `professor_email` | string | `prof@escola.br` | validado |
| `professor_nome` | string | `João Souza` | livre |
| `turma_codigo` | string | `1A` ou `2B` | alfanumérico ≤ 8 chars |
| `turma_serie` | string | `1S`, `2S` ou `3S` | enum estrito |

**Uma linha = uma turma.** Múltiplas turmas da mesma escola repetem
`escola_id` e `escola_nome`. Múltiplas turmas do mesmo professor
repetem `professor_email`.

### Exemplo (CSV)

```csv
escola_id,escola_nome,coordenador_email,coordenador_nome,professor_email,professor_nome,turma_codigo,turma_serie
SEDUC-CE-001,Escola Boa Vista,coord1@teste.br,Maria Coord,prof1@teste.br,João Prof,1A,1S
SEDUC-CE-001,Escola Boa Vista,coord1@teste.br,Maria Coord,prof1@teste.br,João Prof,1B,1S
SEDUC-CE-001,Escola Boa Vista,coord1@teste.br,Maria Coord,prof2@teste.br,Ana Prof,2A,2S
SEDUC-CE-002,Escola Caridade,coord2@teste.br,Carlos Coord,prof3@teste.br,Pedro Prof,1A,1S
```

## Comportamento

### Idempotência

Re-import da mesma planilha **não duplica**. Chaves naturais:

| Entidade | Chave |
|---|---|
| Escola | `codigo` |
| Coordenador | `email` |
| Professor | `email` |
| Turma | `(escola_id, codigo, ano_letivo)` |

Re-import detecta existentes via SELECT, atualiza nome se mudou,
incrementa contador `*_atualizados` em vez de `*_novos`.

### Geração de `codigo_join`

Pra cada turma nova, gera código que o aluno usa pra entrar no bot
(M4):

```
TURMA-{escola_codigo_curto}-{turma_codigo}-{ano_letivo}
```

`escola_codigo_curto` = últimos 5 chars de `escola.codigo` sem hífens.

Ex.: `SEDUC-CE-001` + turma `1A` + 2026 → **`TURMA-CE001-1A-2026`**

Se houver colisão (raro): adiciona sufixo `-2`, `-3`...

### Validações

**Por linha:**
- Campos obrigatórios não vazios
- `escola_id` casa com regex
- `turma_codigo` alfanumérico ≤8 chars
- `turma_serie ∈ ('1S','2S','3S')`
- Emails válidos (RFC + domínio com DNS check desabilitado)

**Globais:**
- Mesmo `escola_id` sempre tem mesmo `escola_nome` → erro se inconsistente
- Mesmo `coordenador_email` sempre tem mesmo nome e mesma escola → erro
- Mesmo `professor_email` sempre tem mesmo nome → erro
- Professor em múltiplas escolas → **warning** (caso legítimo)
- Turma duplicada (mesmo `(escola_id, codigo, ano_letivo)` em 2 linhas)
  → erro

## Como rodar

### CLI local

Pré-requisitos:
1. Postgres rodando (`docker compose up` ou Homebrew).
2. `alembic upgrade head` aplicado (schema do M1).
3. `DATABASE_URL` no `.env`.

```bash
cd backend/notamil-backend

# Dry-run (lê, valida, simula, NÃO persiste)
python -m redato_backend.portal.import_planilha planilha.xlsx

# Commit (persiste se sem erros)
python -m redato_backend.portal.import_planilha planilha.xlsx --commit

# Forçar commit mesmo com erros (perigoso)
python -m redato_backend.portal.import_planilha planilha.xlsx --commit \
    --no-rollback-on-error

# Ano letivo customizado
python -m redato_backend.portal.import_planilha planilha.xlsx --ano 2027

# JSON puro pra pipes
python -m redato_backend.portal.import_planilha planilha.xlsx --json-only \
    | jq '.linhas_lidas'
```

Cada execução salva o relatório em
`data/portal/imports/{timestamp}_{nome_arquivo}.json`.

### Endpoint HTTP

Rodar app (porta 8091, separada do bot WhatsApp em 8090):

```bash
uvicorn redato_backend.portal.portal_app:app --port 8091 --reload
```

Pré-requisito adicional: `ADMIN_TOKEN` no `.env` (qualquer string secreta).

```bash
# Health check
curl http://localhost:8091/admin/health

# Import — dry-run
curl -X POST http://localhost:8091/admin/import-planilha \
    -H "X-Admin-Token: $ADMIN_TOKEN" \
    -F "file=@planilha.xlsx" \
    -F "dry_run=true"

# Import — commit
curl -X POST http://localhost:8091/admin/import-planilha \
    -H "X-Admin-Token: $ADMIN_TOKEN" \
    -F "file=@planilha.xlsx" \
    -F "dry_run=false"
```

## Disparar emails de boas-vindas

Depois do commit, dispara emails com link de primeiro acesso (token
único, válido 7 dias).

### Sem SendGrid configurado (modo dry-run)

Sem `SENDGRID_API_KEY` no env, o serviço **não envia nada** — só
registra o que enviaria em `data/portal/emails_pendentes.jsonl`.
Útil pra inspecionar conteúdo + verificar tokens antes de configurar
SendGrid.

```bash
curl -X POST http://localhost:8091/admin/send-welcome-emails \
    -H "X-Admin-Token: $ADMIN_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{}'   # vazio = todos sem senha em todas as escolas
```

Resposta:
```json
{
  "enviados": 8,
  "falhados": 0,
  "ja_tinham_senha": 0,
  "erros": []
}
```

### Filtros

```jsonc
// Só de uma escola
{"escola_id": "<UUID-da-escola>"}

// Só professores específicos
{"professor_emails": ["prof1@teste.br", "prof2@teste.br"]}

// Só coordenadores específicos
{"coordenador_emails": ["coord1@teste.br"]}

// Forçar regeração de token mesmo pra users que já têm senha
{"overwrite_existing_token": true}
```

### Com SendGrid (produção)

Setar no `.env`:
```
SENDGRID_API_KEY=SG.xxx...
SENDGRID_FROM_EMAIL=noreply@dominio.br
SENDGRID_FROM_NAME=Projeto ATO
PORTAL_URL=https://portal.dominio.br
```

A partir daí, a mesma chamada envia email real via SendGrid.

## Troubleshooting

### "headers_invalidos"

A 1ª linha não bate com os 8 headers esperados. Confira ortografia,
case, presença de coluna extra. Headers são case-insensitive (todos
são lowercased ao parser).

### "escola_id_formato"

Default regex: `^[A-Z]+-[A-Z]{2}-\d{3,}$`. Se sua planilha usa formato
diferente (ex.: `12345`, `IFCE-001`), exporte:

```bash
export PORTAL_ESCOLA_ID_REGEX='^IFCE-\d{3,}$'
```

### "turma_duplicada"

Duas linhas com mesma `(escola_id, turma_codigo)` no mesmo ano.
Geralmente duplicata acidental — confira se uma das duas era pra ser
turma diferente.

### "prof_em_multiplas_escolas" (warning)

Professor com mesmo email em 2+ escolas. **Não bloqueia** import — é
caso legítimo. Mas confira se não foi typo do email.

### Re-import depois de mexer manualmente no DB

Idempotência usa SELECT por chave natural — se você editou direto no
DB, re-import vai ver o registro existente e atualizar conforme
planilha. Não há "merge inteligente": planilha sobrescreve nome se
diferente.

### "Cleanup" dos dados de teste M1

O M1 tinha um `test_migration_sqlite_to_postgres` que populava 5
linhas sintéticas no schema `public.interactions`. Em DB de
desenvolvimento isso é inofensivo. Pra remover:

```sql
DELETE FROM public.interactions
WHERE source = 'whatsapp_v1' AND aluno_phone LIKE '+5511990%';
```

Ou rodar o smoke M1 de novo, que limpa o próprio schema temp ao final.

## Estrutura de arquivos M2

```
backend/notamil-backend/redato_backend/portal/
├── importer.py              parser XLSX/CSV + validate + sync ORM
├── import_planilha.py       CLI (entry-point dry-run/commit)
├── admin_api.py             FastAPI router /admin/*
├── portal_app.py            FastAPI app standalone (porta 8091)
├── email_service.py         envio SendGrid + dry-run jsonl
├── email_templates/
│   ├── welcome_coordenador.html
│   └── welcome_professor.html
└── IMPORT_GUIDE.md          este arquivo
```

## Limites conhecidos (resolvidos em milestones futuros)

| Limite | Resolve em |
|---|---|
| Auth via header simples (sem JWT) | M3 |
| Sem reenvio automático de tokens expirados | M3 (rota /admin/regenerate-token) |
| Sem UI web pra import | M5 |
| Sem fallback de retry quando SendGrid falha | M8 |
| Sem queue assíncrona pra envio em massa (>1k emails síncrono pode dar timeout) | M8 |
