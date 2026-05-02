# HOWTO — Dashboard professor via WhatsApp

**Status:** PROMPT 1/2 (esta entrega) — infra de auth + aviso LGPD.
**PROMPT 2 (futuro):** comandos `/turma`, `/aluno`, `/atividade`,
`/ajuda`.

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

6. **PROMPT 2:** após aceite, qualquer mensagem cai num dispatcher
   de comandos (`/turma 1A`, `/aluno <nome>`, `/atividade`, `/ajuda`).
   Esta entrega tem só placeholder no lugar.

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
