# HOWTO — Dashboard professor via WhatsApp

**Status:** completo (M10 PROMPT 1 + 2).
- PROMPT 1 (commit `160fb5c`): infra de auth + aviso LGPD.
- PROMPT 2 (commit atual): 4 comandos MVP (`/turma`, `/aluno`,
  `/atividade`, `/ajuda`).

## Fluxo do professor

1. **No portal:** professor abre `Perfil` → preenche campo
   "Telefone WhatsApp" no formato E.164 (ex: `+5561912345678`) →
   clica "Salvar".
   - Backend: `PATCH /auth/perfil/telefone` valida formato + unicidade
     (índice único parcial em `professores.telefone`) e grava
     `telefone` + `telefone_verificado_em=NOW()`. `lgpd_aceito_em`
     fica `NULL` (será preenchido só após aceite no WhatsApp).

2. **No WhatsApp:** professor manda qualquer mensagem ao bot do
   Redato (mesmo número que alunos usam pra fotos).
   - Bot detecta via `find_professor_por_telefone(phone)` que esse
     telefone é de Professor antes de cair no fluxo de aluno.

3. **Aviso LGPD (1ª mensagem):** bot responde com
   `AVISO_LGPD_PROFESSOR` explicando que dashboards têm dados
   pessoais (nome de alunos, notas, trechos de redações) e pede
   `sim` pra confirmar.

4. **Aceite:** professor responde `sim` (ou variações: `concordo`,
   `aceito`, `ok`, `tudo bem`).
   - Bot chama `marcar_lgpd_aceito_professor(prof.id)` →
     `UPDATE professores SET lgpd_aceito_em=NOW()` no Postgres.
   - Bot envia confirmação + placeholder `MSG_DASHBOARD_PLACEHOLDER`
     ("Dashboard em construção. Em breve...").

5. **Negação:** professor responde `não` (ou `não concordo`, `recuso`).
   - Bot limpa os 3 campos (`telefone`, `telefone_verificado_em`,
     `lgpd_aceito_em`) — telefone fica desvinculado.
   - Bot envia `MSG_LGPD_NEGADO` orientando a re-vincular no portal
     se mudar de ideia.

6. **Após aceite:** qualquer mensagem cai num dispatcher de comandos
   estruturados (PROMPT 2). Lista completa abaixo.

## Comandos disponíveis

Implementados em
[`redato_backend/whatsapp/dashboard_commands.py`](../../backend/notamil-backend/redato_backend/whatsapp/dashboard_commands.py).
Dispatcher é parser-tolerante: aceita variações `/turma 1A`,
`turma 1A`, `/Turma 1A`, `TURMA 1A` (case-insensitive, com ou sem
barra inicial, espaços extras).

### `/turma <codigo>`

Resumo da turma. Ex: `/turma 1A`.

Retorna:
- Cabeçalho: nome + série
- Total de alunos cadastrados
- Atividades ativas (códigos)
- Médias C1-C5 dos últimos 30 dias (se houver envios)
- Top 3 alunos por melhor nota
- Alertas: envios com correção falha, alunos sem envio

LGPD: filtra por `escola_id` do professor — turma de outra escola
retorna "não encontrada".

### `/aluno <nome>`

Histórico de aluno. Ex: `/aluno maria silva`.

Busca **fuzzy** com `ILIKE %nome%` na escola do professor:
- 0 matches → "Nenhum aluno encontrado..."
- 1 match → mostra histórico (5 últimos envios + tendência + pontos
  fortes/fracos por C1-C5)
- 2+ matches → lista os candidatos numerados; bot persiste FSM
  efêmera (TTL 5 min) e aguarda resposta numérica:
  - `1`, `2`, etc. → escolhe e mostra histórico
  - `cancelar` (ou variações: `nao`, `sair`) → limpa estado, volta
    pro fluxo normal
  - Texto inválido → pede pra responder número/cancelar (mantém FSM)
  - Sem resposta em 5 min → FSM expira automaticamente

Tendência calculada por média das 2 mais recentes vs anteriores
(diferença ≥30 pontos = subindo/caindo, senão estável).

### `/atividade <codigo>`

Status de uma atividade. Ex: `/atividade OF14`.

Aceita código curto (`OF14`) — busca via `ILIKE %codigo%` em
`missoes.codigo`. Múltiplos matches (mesmo código em turmas
diferentes) → lista numerada com FSM `AWAITING_ATIVIDADE_CHOICE`.
Mesma UX do `/aluno`: responder `1`/`2`/etc escolhe, `cancelar` sai.

Retorna:
- Cabeçalho: código + título + turma + prazo
- N envios / N alunos cadastrados (com %)
- Distribuição em buckets `<400 / 400-599 / 600-799 / 800-1000`
- Médias C1-C5
- Lista de pendentes (até 10 nomes, conta os demais)
- Lista de envios com problema (sugere "use o portal pra reprocessar")

### `/ajuda`

Lista os 4 comandos com exemplos. Disparado automaticamente quando
o professor manda texto que não bate em nenhum comando reconhecido —
é o "menu padrão" da experiência.

## Limitações conhecidas

- **Busca por nome é fuzzy ILIKE** — não tolera typos significativos
  (ex.: "joão" ≠ "joao"; "joão" ≠ "joao silva" se o cadastro tem o
  acento). Se aluno não aparece, é provável diferença de acentuação
  com o cadastro.
- **Comando aceita só argumento simples** — `/aluno maria silva pereira`
  procura "maria silva pereira" como substring única. Sem operadores
  booleanos.
- **Notas calculadas em tempo real** (sem cache) — escala atual
  (<100 prof, <1k msgs/dia) tolera bem. Quando volume crescer, vale
  cachear médias por turma com TTL curto.
- **Linguagem natural não suportada** — só comandos estruturados.
  "Como tá a turma 1A?" cai no /ajuda.
- **Reprocessar de fora do portal** — quando dashboard mostra "envios
  com problema", professor precisa abrir o portal pra clicar em
  "Reprocessar avaliação". Não há `/reprocessar <id>` via WhatsApp.

## Defensiva

- Se Postgres está indisponível, dispatcher retorna
  `MSG_DASHBOARD_DB_INDISPONIVEL`. Fluxo aluno via SQLite continua.
- Se algum handler levanta exception, captura em `try/except` e
  retorna `MSG_DASHBOARD_ERRO_GENERICO`. Stack vai pro Railway via
  `logger.exception`.
- Schemas parciais de `redato_output` (FT omitiu campo, parser
  falhou, etc.) são tratados como "sem nota" via `_redato_tem_erro`
  — não derruba agregações.

## Fluxo do coordenador

Não tem dashboard via WhatsApp por enquanto. PATCH `/auth/perfil/telefone`
retorna **403** se `auth.papel != "professor"`. Decisão de escopo do
M10: só professor recebe esse acesso.

## Telefone vs alunos_turma

Coexistência sem conflito:

- `alunos_turma.telefone` continua sendo o lookup pra fluxo de aluno
  (envio de redação, atividade, jogo).
- `professores.telefone` é tabela separada — `find_professor_por_telefone`
  é checado **antes** do `get_aluno` em `bot.py:handle_inbound`.
- Índice único parcial em `professores.telefone WHERE telefone IS NOT NULL`
  garante que dois professores não compartilham número.
- Se um professor por engano vincular um telefone que já está em
  `alunos_turma`: ambos os lookups vão dar match. **Professor ganha
  prioridade** (lookup primeiro). Aluno órfão precisa atualizar o
  cadastro manualmente.

## Troubleshooting

- **"Coordenador não vê o card de telefone":** correto — `MeResponse`
  só retorna `telefone`/`lgpd_aceito_em` pra `papel="professor"`,
  e `PerfilView` só renderiza o card pra esse papel.
- **"Vinculei telefone mas bot não responde como professor":**
  - Confere que o `phone` recebido pelo Twilio bate exatamente com o
    que está no banco (sem espaços, com `+`, com DDI).
  - Confere `professores.ativo = TRUE`. Telefone de prof inativo é
    ignorado por design (find_professor_por_telefone filtra).
  - Confere logs Railway: `find_professor_por_telefone` é defensivo
    contra falha de DB — se Postgres está inacessível, retorna `None`
    silenciosamente, mas loga em DEBUG.
- **"Redes inutilizadas / DATABASE_URL ausente":** em test ou dev
  sem Postgres, lookup retorna `None` automaticamente (try/except).
  Bot continua funcionando pra aluno via SQLite local.

## Migration

`i0a1b2c3d4e5_professor_telefone` (após `h0a1b2c3d4e5_jogo_redacao`).
Adiciona em `professores`:
- `telefone VARCHAR(20)` nullable
- `telefone_verificado_em TIMESTAMPTZ` nullable
- `lgpd_aceito_em TIMESTAMPTZ` nullable
- Índice único parcial `uq_professor_telefone_quando_setado`
  (`WHERE telefone IS NOT NULL`)

Aplicar via `alembic upgrade head` no shell do Railway antes do
deploy do código novo (ou no boot, se o entrypoint roda upgrade
automaticamente — verificar `Procfile` ou docker entrypoint).

`downgrade()` aborta com `RuntimeError` se houver professor com
`lgpd_aceito_em != NULL` — preserva audit trail. Limpe manualmente
antes de reverter se realmente precisar.
