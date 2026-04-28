# Auth do portal — M3

Autenticação JWT pro portal web (coordenador + professor). Sem UI nesta
fase — só endpoints HTTP. Front-end de login entra em M5.

## Fluxos

### 1. Primeiro acesso (após M2 importar planilha)

```
[Coordenador faz import via M2] → token primeiro_acesso gerado por usuário
                                ↓
[Email enviado via SendGrid (ou dry-run jsonl)]
                                ↓
[Aluno clica no link com ?token=<...>]
                                ↓
POST /auth/primeiro-acesso/validar  { token }
   → 200 { valido: true, email, nome, papel, escola_nome }
   → 410 token expirado
   → 404 token não encontrado
                                ↓
POST /auth/primeiro-acesso/definir-senha  { token, senha }
   → 200 { sucesso, redirect_to: "/auth/login" }
   → 400 senha fraca
   → 410 token expirado
                                ↓
POST /auth/login  { email, senha, lembrar_de_mim? }
   → 200 { access_token, expires_in, papel, nome, escola_id }
```

Token de primeiro acesso é consumido na definição de senha (NULA no DB).

### 2. Login normal

```
POST /auth/login { email, senha, lembrar_de_mim }
   - lembrar_de_mim=false → exp=8h
   - lembrar_de_mim=true  → exp=30d

GET /auth/me  Authorization: Bearer <token>
   → 200 { id, nome, email, papel, escola_id, escola_nome }
   → 401 se token inválido/expirado/blocklisted
   → 403 se user inativo
```

### 3. Reset de senha

```
POST /auth/reset-password/solicitar  { email }
   → 200 sempre (anti-enumeração — mesma resposta exista ou não)

[Email com link reset-password?token=...]

POST /auth/reset-password/confirmar  { token, senha_nova }
   → 200 { sucesso }
   → 400 senha fraca
   → 410 token expirado
   → 404 token não encontrado
```

Validade do reset token: **2 horas**.

### 4. Logout

```
POST /auth/logout  Authorization: Bearer <token>
   → 200 { sucesso }
   → JTI do token vai pra TokenBlocklist até exp natural
   → /auth/me com mesmo token: 401 a partir desse ponto
```

## JWT — Configuração

**Secret obrigatório** no `.env`:
```bash
# Gerar:
python -c "import secrets; print(secrets.token_hex(32))"

# Setar:
JWT_SECRET_KEY=<64+ chars hex>
```

Fail loud no startup se ausente ou < 32 chars.

**Claims fixos:**
- `aud = "redato-portal"`
- `iss = "redato-backend"`
- `alg = HS256` (suficiente pra Fase B+ single-tenant)

**Claims dinâmicos:**
- `sub`: UUID do user
- `papel`: `"coordenador" | "professor"`
- `escola_id`: UUID
- `jti`: UUID v4 (único por token, base da blocklist)
- `iat`, `exp`: timestamps Unix

## Senhas

- Hash bcrypt cost 12 (default da lib).
- Validação mínima: ≥8 chars, ≥1 letra, ≥1 número.
- Sem regras teatrais (caractere especial obrigatório, etc.) — UX > segurança teatral.

## Permissões — matriz

Funções em [`permissions.py`](permissions.py). Todas puras, sem queries
embutidas. Caller passa `AuthenticatedUser` + objetos relevantes.

| Operação | Coordenador (escola própria) | Coord (outra escola) | Professor (turma própria) | Prof (outra turma) |
|---|---|---|---|---|
| `can_view_escola(escola_id)` | ✓ | ✗ | ✓ (própria) | ✗ |
| `can_view_turma(turma)` | ✓ (qualquer da escola) | ✗ | ✓ | ✗ |
| `can_create_atividade(turma)` | ✗ | ✗ | ✓ | ✗ |
| `can_view_dashboard_turma(turma)` | ✓ (qualquer da escola) | ✗ | ✓ | ✗ |
| `can_view_dashboard_escola(escola_id)` | ✓ | ✗ | ✗ | ✗ |

**Regra:** coordenador é leitor/auditor da escola; professor é o ator
(cria atividades). Nenhum vê dado de outra escola.

## Cleanup periódico

Tokens expirados ficam no DB até serem limpos. Não causa bug funcional
(check `expira_em > now()` em cada uso), mas inflaciona a tabela.

```bash
python -m redato_backend.portal.auth.cleanup
```

3 limpezas idempotentes:
- `cleanup_primeiro_acesso_expirados`: NULA tokens vencidos
  (não deleta o user)
- `cleanup_reset_tokens_expirados`: idem pra reset
- `cleanup_blocklist_expirada`: DELETE `token_blocklist` onde
  `exp_original < now()`

**Em produção:** rodar via cron daily, ex.:
```cron
0 3 * * * cd /app && python -m redato_backend.portal.auth.cleanup
```

## Como testar localmente

```bash
cd backend/notamil-backend

# 1. Postgres rodando + alembic upgrade head já aplicado
# 2. .env com JWT_SECRET_KEY (≥32 chars) + ADMIN_TOKEN

# 3. Subir o app
uvicorn redato_backend.portal.portal_app:app --port 8091 --reload

# 4. Smoke test programático (em schema isolado)
python scripts/test_m3_auth.py
```

### Exemplo de fluxo via curl

```bash
# 0. Importar planilha (M2)
curl -X POST http://localhost:8091/admin/import-planilha \
    -H "X-Admin-Token: $ADMIN_TOKEN" \
    -F "file=@planilha.xlsx" -F "dry_run=false"

# 1. Disparar emails de boas-vindas (M2 + proteções de M3)
curl -X POST http://localhost:8091/admin/send-welcome-emails \
    -H "X-Admin-Token: $ADMIN_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"confirmar_envio": true}'

# 2. Pegar token do email (ou de data/portal/emails_pendentes.jsonl em
#    modo dry-run sem SendGrid)
TOKEN_PA=$(jq -r 'select(.subject | contains("primeiro login")) | .html' \
    data/portal/emails_pendentes.jsonl | grep -oE 'token=[a-f0-9]+' | head -1 | cut -d= -f2)

# 3. Validar token
curl -X POST http://localhost:8091/auth/primeiro-acesso/validar \
    -H "Content-Type: application/json" \
    -d "{\"token\": \"$TOKEN_PA\"}"

# 4. Definir senha
curl -X POST http://localhost:8091/auth/primeiro-acesso/definir-senha \
    -H "Content-Type: application/json" \
    -d "{\"token\": \"$TOKEN_PA\", \"senha\": \"MinhaSenha123\"}"

# 5. Login
TOKEN_JWT=$(curl -sX POST http://localhost:8091/auth/login \
    -H "Content-Type: application/json" \
    -d '{"email":"prof@escola.br","senha":"MinhaSenha123"}' \
    | jq -r .access_token)

# 6. Me
curl http://localhost:8091/auth/me \
    -H "Authorization: Bearer $TOKEN_JWT"

# 7. Logout
curl -X POST http://localhost:8091/auth/logout \
    -H "Authorization: Bearer $TOKEN_JWT"

# 8. Me agora dá 401
curl -i http://localhost:8091/auth/me \
    -H "Authorization: Bearer $TOKEN_JWT"
```

## Decisões registradas

- **HS256 e não RS256**: portal é single-consumer (front-end web). RS256
  só faz sentido se virar B2B com múltiplos consumidores em chaves
  separadas.
- **Blocklist em DB, não Redis**: volume esperado de logout é baixo
  (centenas/dia), e Redis adicionaria infraestrutura. Cleanup mantém a
  tabela enxuta.
- **Reset = 2h, primeiro acesso = 7d**: primeiro acesso é menos
  sensível (link novo via professor); reset é incidente recente do
  user (mais urgência, menos exposição).
- **Coordenador NÃO cria atividade**: coordenação é supervisão. Se virar
  necessário (ex.: simulado da escola toda agendado pela coord), abrir
  endpoint específico em vez de mexer em `can_create_atividade`.
- **Anti-enumeração no reset**: endpoint sempre retorna 200, mesmo pra
  email inexistente. Atacante não descobre quais emails estão cadastrados.
