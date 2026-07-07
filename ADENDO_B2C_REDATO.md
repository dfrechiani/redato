# ADENDO 01 — SPEC B2C Redato (decisões D7–D14, pós-implementação Fase 1)
> Para o Claude Code, na raiz do repo redato_hash. Complementa SPEC_B2C_REDATO.md — onde conflitar, ESTE documento vale.
> Autor: Daniel + Claude (Chat), 07/07/2026.
> Contexto: a Fase 1 da SPEC já foi implementada na branch **feat/b2c-mvp** (6 commits, +32 testes, zero regressão sobre o B2G). Este adendo fecha as decisões de produto que ficaram abertas e corrige furos identificados na revisão, ANTES do piloto.

## 0. Estado atual da branch feat/b2c-mvp (o que já existe — trabalhar EM CIMA)
- Modelos + migration `l0a1b2c3d4e5` (parceiros_b2c, alunos_b2c, assinaturas_b2c, envios_b2c, eventos_billing). **A migration nunca foi aplicada em nenhum ambiente** — emendas vão direto no arquivo existente, sem migration nova.
- Desvio B2C em `bot.py handle_inbound` (hook único guardado por REDATO_B2C_ENABLED, depois do lookup de professor). `redato_backend/b2c/` (config, messages, repo, correction, router), `redato_backend/billing/` (Asaas client real + mock, webhook com idempotência), admin metrics, seed DEMO.
- Correção reutiliza OCR existente + `_claude_grade_essay` (grader completo 5 competências) com `activity_id=None`.
- Testes: 30 B2C + 2 de regressão B2G, todos verdes. Baseline pré-existente da suíte completa: 28 failed / 23 errors **ambientais** (openpyxl ausente, data files, testes jogo que exigem Postgres) — não são regressão, não tentar consertar.
- Env: venv Python 3.11 em `backend/notamil-backend/.venv` (criado via uv). Rodar testes com override de addopts se o setup.cfg forçar --cov.

## 1. D7 — Tema OBRIGATÓRIO na legenda da foto (decisão de produto, muda o fluxo)
Toda correção é corrigida CONTRA um tema. Não existe correção tema-agnóstica ("LIVRE" está morto). C2 sempre avaliável.

### 1.1 Cascata de resolução do tema (ordem exata)
1. **Foto com legenda ≥ 15 caracteres** → legenda = tema. Corrige direto. (Twilio entrega caption como Body junto do MediaUrl.)
2. **Foto com legenda de 1–14 caracteres** (dúbia: pode ser tema curto ou lixo tipo "segue") → **M16b** confirma: "o tema é '{{caption}}'?". Resposta SIM → usa a caption; qualquer outro texto → vira o tema.
3. **Foto sem legenda + tema sorteado via comando 'tema' há menos de 48h** → **M16a** oferece atalho: "foi o tema que te mandei?". SIM → usa o tema sorteado; outro texto → vira o tema.
4. **Foto sem legenda, sem tema recente** → **M16** pergunta o tema.
Em 2–4: o OCR RODA ANTES de perguntar (se a letra estiver ilegível, devolve o aviso de foto ruim imediatamente — não faz o aluno digitar tema pra depois descobrir que a foto não serve). O envio fica pendente aguardando só o tema.

### 1.2 Estado "aguardando tema" — implementação (refinamento sobre a discussão)
NÃO criar estado `aguardando_tema` no AlunoB2C: um aluno em `degustacao` E um aluno `ativo` podem ambos estar aguardando tema, e sobrescrever o estado principal perderia essa informação. Em vez disso:
- `envios_b2c` ganha coluna **`status`**: `aguardando_tema` | `corrigido` | `bloqueado` (default `corrigido`).
- Regra: **no máximo 1 envio `aguardando_tema` por aluno** — nova foto substitui a pendência anterior (com a legenda da nova, se tiver).
- Router: se existe envio pendente do aluno, a próxima mensagem de TEXTO resolve o tema — EXCETO comandos conhecidos ("ajuda", "evolução", "tema", "cancelar"), que executam normal e mantêm a pendência. "SIM" só é especial quando M16a/M16b ofereceu atalho.
- Anti-loop: resposta de texto < 15 chars sem atalho oferecido → pede o enunciado completo UMA vez; se a segunda resposta também for curta, aceita como tema assim mesmo (o aluno sabe o que escreveu).
- Redação DIGITADA (F4 aceita texto): texto longo sem tema identificável → mesmo fluxo M16.
- Fair use e `correcoes_gratis_usadas` contam APENAS envios que viraram `corrigido`.

### 1.3 Injeção do tema no grader (ponto técnico crítico)
Localizar como o B2G injeta a proposta/tema da Atividade no prompt de `_claude_grade_essay` e passar o tema B2C **pelo MESMO campo**. Tema nunca é campo vazio silencioso. Antes de codar, apontar no brief o campo exato (arquivo + linha).

### 1.4 Entrega
M3 e M6 abrem com linha `📝 Tema: {{tema}}` — reforça que a C2 foi avaliada contra aquele tema.

## 2. D8 — Régua de inadimplência: daily tick (a régua hoje NÃO tem gatilho)
M9 (D+3) e a virada pra `inadimplente` (D+5) precisam de um job diário — o webhook OVERDUE só cobre a M8 (D0).
- **Endpoint interno** `POST /internal/b2c/daily-tick`, protegido por token próprio (env `B2C_TICK_TOKEN`, header). Chamado por **Railway cron diário às 10h de Brasília** (config no Railway, não no código; documentar no runbook).
- O tick varre assinaturas em atraso e promove: `overdue_desde` + 3 dias → envia M9; + 5 dias → `aluno.estado = inadimplente` (e envia M10 se o aluno mandar foto).
- **Idempotente**: rodar o tick 2× no mesmo dia não duplica mensagem. Implementar com `assinaturas_b2c.regua_estagio` (int: 0=nada, 1=M8 enviada, 2=M9 enviada, 3=bloqueado) — o tick só avança estágio, nunca repete.
- Pagamento confirmado em qualquer ponto → zera `regua_estagio` e `overdue_desde`, reativa, manda M5 (já implementado no webhook — conferir o zeramento).
- NÃO usar APScheduler in-process (restart/réplica do Railway bagunça).

## 3. D9 — Janela de 24h do WhatsApp / templates (sem isso a régua falha em silêncio)
M5, M8 e M9 são mensagens iniciadas pelo negócio e podem cair FORA da janela de 24h desde a última mensagem do aluno — aí o Twilio só entrega **template pré-aprovado** (Content API); freeform falha silenciosamente.
- **Primeiro: verificar como o B2G envia mensagens hoje** (freeform via webhook reply? Content API? Messaging Service?). Se o B2G já resolve janela, reusar o mecanismo.
- Implementar na função de envio B2C: `alunos_b2c.ultima_inbound_at` (atualizada a cada mensagem recebida) → se `now - ultima_inbound_at < 24h`, freeform; senão, template com Content SID + variáveis.
- Content SIDs por env: `TWILIO_CONTENT_SID_M5`, `_M8`, `_M9`. Templates genéricos com variáveis ({{1}}=nome, {{2}}=nome_publico, {{3}}=link) pra servirem todos os parceiros.
- No MVP/testes: mock que registra qual caminho foi usado (freeform vs content_sid). Submissão dos templates no console Twilio = gate do Daniel (§15).
- M3/M6/M16 são sempre resposta imediata a mensagem do aluno (dentro da janela) — freeform ok.

## 4. D10 — M10 SEM fila de correção pendente (decisão: copy honesta, fila só se o dado pedir)
Não construir fila de "corrigir depois da regularização" no MVP (exigiria retenção de mídia do Twilio + entrega fora da janela via template gigante). Em vez disso:
- **Copy nova da M10** (§10) promete só o que o sistema faz: regularizou → reenvia a foto → corrige na hora.
- Foto de aluno `inadimplente`/`bloqueado` → grava `envios_b2c` com `status='bloqueado'` **sem rodar OCR nem grader** (custo zero) → responde M10.
- Métricas ganham contador `fotos_bloqueadas` por parceiro. Se o piloto mostrar volume ali, fila vira candidata de Fase 2 com dado.

## 5. D11 — Fair use mantido em 10/dia, mas INSTRUMENTADO
- Garantir que `envios_b2c.custo_estimado_centavos` é preenchido de verdade (custo OCR + custo grader por correção; estimativa por tokens é aceitável, documentar a fórmula em comentário).
- `GET /admin/b2c/metricas` ganha, por parceiro: **custo médio por correção**, **correções por assinante ativo (P50/P95)**, **margem estimada** (MRR líquido − share do parceiro − custo estimado do período), além de `fotos_bloqueadas` (§4) e `eventos_pendentes` (§7).
- Meta: 2 semanas de piloto → revisitar o teto de 10/dia com número real.

## 6. D12 — Extrair o grader AGORA (primeiro passo da ordem de trabalho)
`_claude_grade_essay` é função privada do bot.py; refactor futuro do bot quebraria o B2C em silêncio.
- Criar `redato_backend/grading/` com função pública (ex.: `grade_essay_completo(texto, tema, ...)`) — mover a lógica, não duplicar.
- `bot.py` (B2G) e `b2c/correction.py` passam a importar DO MESMO módulo.
- Teste de identidade: assert de que os dois fluxos referenciam a mesma função.
- Regressão zero no B2G é critério de aceite deste passo (rodar a suíte whatsapp+missions antes/depois).

## 7. D13 — Eventos Asaas desconhecidos + divergência de split
- Evento de webhook não reconhecido → `eventos_billing.processado=false` (já grava tudo; garantir a flag) + contador `eventos_pendentes` nas métricas. Nada é descartado em silêncio.
- Divergência de split (Asaas BLOQUEIA a assinatura nesse caso — SPEC §5): tratar o webhook de aviso → registrar em eventos_billing, marcar a assinatura com status de atenção (`status='atencao_split'` ou campo próprio), NÃO quebrar o fluxo. Aparece nas métricas.

## 8. D14 — LGPD: versionar o consentimento
- Constante `CONSENT_VERSION` (string, ex. `"2026-07-v1"`) em `b2c/config.py`, gravada em `alunos_b2c.consent_version` no momento do aceite (junto do `consent_lgpd_at` já existente). Prova qual texto o aluno aceitou.
- Validação jurídica do modelo "continuar = aceite" com público que inclui menores = pendência do Daniel (§15), fora do repo. Não escalar sem isso.

## 9. Correções de execução direta (sem decisão, só fazer)
1. **Negrito WhatsApp é asterisco SIMPLES.** Revisar TODAS as copies em `b2c/messages.py`: nenhum `**` markdown pode sobrar (as copies da SPEC §6 vieram com `**`).
2. **M6 condicional:** bloco `📈 Sua evolução` só aparece com ≥ 2 envios corrigidos no histórico; com 1, omitir a linha inteira.
3. **Migration:** todas as colunas novas (§11) entram por EDIÇÃO da `l0a1b2c3d4e5` existente (nunca aplicada). Manter head único.

## 10. Copies novas e revisadas (substituem/estendem SPEC §6; negrito = *asterisco simples*)
- **M2 (rev.):** "Prazer, {{nome}}! 🎁 Sua primeira correção é por nossa conta. Fotografa sua redação (folha inteira, boa luz) e manda aqui *com o tema na legenda da foto*."
- **M3 (rev.):** abre com "📝 Tema: {{tema}}" antes da linha da nota. Resto igual (com negritos convertidos pra `*`).
- **M6 (rev.):** abre com "📝 Tema: {{tema}}"; bloco de evolução condicional (§9.2). Resto igual.
- **M10 (rev.):** "Recebi sua redação! 📥 Pra eu corrigir, regulariza sua assinatura aqui: {{link_fatura}}. Assim que ativar, me manda a foto de novo que a correção sai na hora."
- **M13 (rev.):** "Comandos: manda uma FOTO da redação *com o tema na legenda* pra corrigir · 'evolução' pra ver seu histórico · 'tema' pra receber uma proposta de treino · 'cancelar' pra encerrar."
- **M14 (rev.):** "🎯 Tema de treino: '{{tema}}'. 30 linhas, caneta preta, e me manda a foto *com o tema na legenda* ao terminar. Bora!"
- **M16 (nova — foto sem legenda):** "Recebi sua redação! ✍️ Sobre qual tema você escreveu? Me manda o enunciado que a correção sai em seguida."
- **M16a (nova — atalho tema sorteado <48h):** "Recebi sua redação! Foi sobre o tema que te mandei — '{{ultimo_tema}}'? Responde SIM ou me manda o enunciado certo."
- **M16b (nova — legenda curta/dúbia):** "Recebi! Só confirmando: o tema é '{{caption}}'? Responde SIM ou me manda o enunciado completo."
- **M17 (nova — anti-loop, resposta curta sem atalho):** "Me manda o enunciado completo do tema, vai ser rapidinho 🙂"

## 11. Emendas na migration l0a1b2c3d4e5 (editar o arquivo existente + models.py)
- `envios_b2c`: **`tema`** (Text, nullable — nullable só por causa dos `bloqueado`; envio corrigido SEMPRE tem tema), **`status`** (String, default `'corrigido'`; valores `aguardando_tema|corrigido|bloqueado`).
- `alunos_b2c`: **`consent_version`** (String, nullable), **`ultima_inbound_at`** (timestamp tz, nullable), **`ultimo_tema_sorteado`** (Text, nullable), **`ultimo_tema_sorteado_at`** (timestamp tz, nullable).
- `assinaturas_b2c`: **`overdue_desde`** (timestamp tz, nullable), **`regua_estagio`** (int, default 0).
- Seguir as convenções já usadas no arquivo (UUID PK, JSONB, timestamps tz-aware). Downgrade coerente.

## 12. Critérios de aceite novos (continuam a numeração da SPEC §7; padrão pytest do repo)
11. Foto + legenda ≥15 chars → corrige; **assert de que o tema chegou no payload do grader NO MESMO CAMPO que o B2G usa** (grader mockado).
12. Foto sem legenda → OCR roda, envio fica `aguardando_tema`, bot manda M16; texto seguinte vira tema → corrige e entrega com "📝 Tema:".
13. Legenda de 1–14 chars → M16b; "SIM" usa a caption; texto diferente vira o tema.
14. Tema sorteado <48h + foto sem legenda → M16a; "SIM" usa o tema sorteado.
15. Comando ("ajuda"/"evolução"/"cancelar") durante pendência de tema → executa o comando e MANTÉM a pendência.
16. Daily tick idempotente: 2 execuções no mesmo dia → M9 no máximo 1×; D+5 → `inadimplente`. Pagamento → zera régua e reativa.
17. Fora da janela de 24h → envio via template (mock registra content_sid); dentro → freeform.
18. M6 sem bloco de evolução quando histórico de corrigidos < 2.
19. Nenhuma copy em messages.py contém `**`.
20. Evento Asaas desconhecido → `processado=false` + entra em `eventos_pendentes` nas métricas.
21. bot.py (B2G) e B2C importam o grader do MESMO módulo público (assert de identidade).
22. Aceite LGPD grava `consent_version == CONSENT_VERSION`.
23. Foto de inadimplente → envio `status='bloqueado'` SEM chamar OCR/grader (assert de não-chamada) + contador `fotos_bloqueadas`.
24. Suíte completa: mesmos 28 failed / 23 errors ambientais do baseline — zero regressão nova.

## 13. Ordem de trabalho (mesma branch feat/b2c-mvp, commits pequenos)
1. **D12** — extrair grader pra `redato_backend/grading/` (critério 21 + regressão B2G verde).
2. **§11** — emendas na migration + models (uma vez só, com TODAS as colunas).
3. **D7** — fluxo do tema completo + copies novas + critérios 11–15, 19.
4. **D8 + D13** — daily tick + régua + eventos pendentes/split (critérios 16, 20).
5. **D9** — janela 24h/templates com mock (critério 17).
6. **D10 + D11** — M10 nova, envio bloqueado, métricas de custo/margem (critérios 18, 23).
7. **§9** — varredura final de copies + M6 condicional + critério 24 (suíte completa vs baseline).
8. Testar a migration num Postgres descartável local: `upgrade head` → `downgrade -1` → `upgrade head` de novo. Verificar como o Railway aplica migrations hoje (release command? manual?) e documentar no runbook.

## 14. Runbook de deploy (Fase 1 completa; nenhum passo antes do gate correspondente)
1. Merge feat/b2c-mvp → main com `REDATO_B2C_ENABLED=false` (deploy inerte).
2. `alembic upgrade head` no Postgres do Railway (pelo mecanismo confirmado no §13.8).
3. `scripts/seed_parceiro.py` → parceiro DEMO.
4. Envs no Railway: ASAAS_* (sandbox), B2C_*, TWILIO_CONTENT_SID_* (após aprovação dos templates).
5. `REDATO_B2C_ENABLED=true` → teste manual com o telefone do Daniel + código DEMO: onboarding → foto com legenda → correção → paywall sandbox → pagamento simulado → M5 → correção de assinante.
6. Só depois: parceiros reais no seed + divulgação.

## 15. Pendências do Daniel (gates externos, podem correr em paralelo ao código)
1. **Templates Twilio**: submeter M5/M8/M9 pra aprovação no console (lead time de horas a dias — quanto antes, melhor).
2. **Conta Asaas PJ + sandbox**: ASAAS_API_KEY/WEBHOOK_TOKEN nos envs (nunca no chat/git). Validar no sandbox: exige CPF? (se sim, `B2C_EXIGE_CPF=1`) + eco do split na assinatura criada.
3. **Jurídico LGPD**: validar "continuar = aceite" com público que inclui menores, antes de escalar.
4. **ANTHROPIC_API_KEY** pro E2E real de foto → correção.
5. **Dados dos 3 parceiros-piloto** quando os contratos fecharem.

---

## Prompt inicial sugerido (colar no Claude Code, aberto na raiz do redato_hash)
"Leia SPEC_B2C_REDATO.md e ADENDO_B2C_REDATO.md na raiz — o adendo prevalece. A Fase 1 já existe na branch feat/b2c-mvp: faça checkout e trabalhe em cima dela (commits pequenos, nenhum secret). Antes de codar: (1) me mostre em até 10 linhas como vai implementar o fluxo do tema (D7/§1), apontando o ARQUIVO e CAMPO exatos onde o B2G injeta a proposta no prompt do grader; (2) confirme o desenho do daily-tick (D8) e da janela de 24h (D9), dizendo como o B2G envia mensagens hoje; (3) liste dúvidas. Depois implemente na ordem da seção 13, com os critérios 11–24 passando e a suíte completa igual ao baseline (28 failed / 23 errors ambientais, zero regressão nova)."
