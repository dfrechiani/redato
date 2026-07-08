# Runbook de deploy — Correção {Parceiro} (B2C)

> Operacional. Complementa SPEC_B2C_REDATO.md §8 e ADENDO_B2C_REDATO.md §14.
> Nada avança antes do gate correspondente. Sandbox até o Daniel autorizar produção.

## Registro de deploy (estado atual — memória durável)
- **2026-07-08** · `feat/b2c-mvp` mergeada em `main` (fast-forward, commit `c691750`) e empurrada → deploy Railway **inerte** (`REDATO_B2C_ENABLED` ausente = false).
- **2026-07-08** · Migration aplicada em PRODUÇÃO via Railway Shell: `k0a1b2c3d4e5 → l0a1b2c3d4e5`. `alembic current` = **`l0a1b2c3d4e5 (head)`**. 6 tabelas B2C criadas (vazias) + `notificacoes_degradadas`.
- **2026-07-08** · `seed_parceiro.py` rodado → parceiro **DEMO** criado (código de entrada `QUERO DEMO`).
- **Estado:** software 100% armado e DORMENTE. Flag off, rotas respondendo `disabled`/401. **A migration NÃO está pendente.** Falta só env externa (ver §0 e "🔴 esperando env externa").

## 0. Pré-requisitos (gates do Daniel — §15 do adendo, podem correr em paralelo)
1. **Templates Twilio M5/M8/M9** submetidos e aprovados na Meta (lead time de horas a dias). Sem eles a régua de cobrança fora da janela de 24h não entrega. Content SIDs vão para `TWILIO_CONTENT_SID_M5/_M8/_M9`.
2. **Conta Asaas PJ + sandbox** → `ASAAS_API_KEY`, `ASAAS_WEBHOOK_TOKEN` nos envs (NUNCA no chat/git). Validar no sandbox: exige CPF? (se sim, `B2C_EXIGE_CPF=1`) + eco do split na assinatura criada.
3. **Jurídico LGPD**: validar "continuar = aceite" com público que inclui menores, antes de escalar.
4. **ANTHROPIC_API_KEY** para o E2E real e para o gate de C2 (passo 5 abaixo).

## 1. Envs no Railway (deploy inerte primeiro)
```
REDATO_B2C_ENABLED=false        # deploy inerte — fluxo escola intocado
B2C_NUMERO_WHATSAPP=<numero>
B2C_FAIR_USE_DIA=10
B2C_FREE_CORRECTIONS=1
B2C_EXIGE_CPF=0                  # 1 se o sandbox Asaas exigir CPF
B2C_POLITICA_URL=<url politica>
B2C_TICK_TOKEN=<segredo forte>   # protege POST /internal/b2c/daily-tick
ASAAS_API_KEY=<sandbox>          # secret
ASAAS_BASE_URL=https://sandbox.asaas.com/api/v3
ASAAS_WEBHOOK_TOKEN=<segredo>    # secret; header asaas-access-token
TWILIO_CONTENT_SID_M5=<HX...>    # após aprovação dos templates
TWILIO_CONTENT_SID_M8=<HX...>
TWILIO_CONTENT_SID_M9=<HX...>
```

## 2. Migration
**Mecanismo do Railway (confirmado — §13.8):** migrations rodam **SEMPRE manualmente via Railway Shell**, NUNCA no boot. Motivo documentado em `docs/redato/v3/DEPLOY_RAILWAY.md` (§"Sequência de migration manual"): o serviço sobe com 2 dynos em rolling restart e ambos tentariam `alembic upgrade head` → lock no Postgres. Não existe release command; `startCommand` (railway.toml) é só o uvicorn. **Não setar `ALEMBIC_AUTO_UPGRADE`.**

Sequência (uma vez por deploy de schema):
```
railway shell --service redato-backend        # ou UI → backend → Open Shell
alembic -c redato_backend/portal/alembic.ini current      # deve mostrar k0a1b2c3d4e5
alembic -c redato_backend/portal/alembic.ini upgrade head # aplica l0a1b2c3d4e5
alembic -c redato_backend/portal/alembic.ini current      # confirma l0a1b2c3d4e5 (head)
```

**Ciclo validado localmente (feito):** contra um Postgres efêmero real (via `pgserver`), a cadeia inteira rodou `upgrade head → downgrade -1 (l→k) → upgrade head (k→l)` sem erro; as 6 tabelas B2C (parceiros_b2c, alunos_b2c, assinaturas_b2c, envios_b2c, eventos_billing, notificacoes_degradadas) e as colunas novas (`envios_b2c.tema/status` etc.) presentes ao fim. A migration `l0a1b2c3d4e5` (head único) é reversível nos dois sentidos. Rerodar antes do deploy: `pip install pgserver && python scripts/test_migration_cycle.py`.

## 3. Seed do parceiro
- `python scripts/seed_parceiro.py` → parceiro DEMO (idempotente). Parceiros reais só depois do piloto validado.

## 4. Webhook Asaas
- Cadastrar a URL `POST https://<backend>/billing/asaas/webhook` no painel Asaas sandbox, com o token (`asaas-access-token: $ASAAS_WEBHOOK_TOKEN`).
- Cron diário no Railway (10h BRT): `POST https://<backend>/internal/b2c/daily-tick` com header `x-b2c-tick-token: $B2C_TICK_TOKEN`. Régua de inadimplência (M9/D+3, bloqueio/D+5). Idempotente.

## 5. GATE OBRIGATÓRIO — tema penaliza a C2 (ADENDO §D7)
> Prova de comportamento (não só plumbing). NÃO ligar a flag sem isto verde.
```
ANTHROPIC_API_KEY=sk-... python scripts/validar_tema_c2.py
```
- Corrige a mesma redação com tema aderente vs. off-topic e imprime C1–C5 lado a lado.
- **Passa** se a C2 cai no par off-topic (diagnóstico de tangenciamento) em todos os pares → exit 0.
- **Falha** (exit 2) → o grader está ignorando o tema; o produto voltaria a ser tema-agnóstico prometendo o contrário. Investigar o prompt do grader ANTES de prosseguir.

## 5.5 Dia D do sender (checklist técnico — quando o número existir)
O piloto depende de um número WhatsApp (sender) registrado. No dia em que ele existir, ANTES de ligar a flag:

1. **Webhook do sender → produção.** No provedor do sender (Twilio console → o número/Messaging Service), aponta o webhook de mensagens recebidas para `POST https://<backend-prod>/twilio/webhook` (o MESMO endpoint do B2G — o desvio B2C é interno, decidido no `handle_inbound`). Método POST, validação de assinatura ligada (`TWILIO_VALIDATE_SIGNATURE=1` + `TWILIO_PUBLIC_URL` da prod).
2. **Envs no Railway:**
   - `B2C_NUMERO_WHATSAPP=<numero E.164 do sender>` (ex.: `5511999999999`) — usado no deep link e no kit do parceiro.
   - `TWILIO_CONTENT_SID_M5`, `TWILIO_CONTENT_SID_M8`, `TWILIO_CONTENT_SID_M9` — os Content SIDs dos templates aprovados (§0.1). Os nomes na Meta e a ordem exata das variáveis são a fonte de verdade em `redato_backend/b2c/templates.py`; submeta os corpos de lá literais. Sem esses SIDs, M5/M8/M9 fora da janela 24h degradam (visível em `envios_degradados`).
3. **Confere o deep link do DEMO com o número real:** monta `https://wa.me/<B2C_NUMERO_WHATSAPP>?text=QUERO+DEMO` e abre no teu celular — deve abrir a conversa com o sender já com "QUERO DEMO" digitado. O código `QUERO DEMO` já está gravado no banco desde o seed; só o número faltava.
4. **Cadastra o webhook do Asaas** (se ainda não): `POST https://<backend-prod>/billing/asaas/webhook` com `asaas-access-token: $ASAAS_WEBHOOK_TOKEN`.
5. **Cadastra o cron do daily-tick** (10h BRT) batendo em `POST https://<backend-prod>/internal/b2c/daily-tick` com `x-b2c-tick-token: $B2C_TICK_TOKEN`.
6. **E2E do telefone do Daniel — a TRAVA FINAL antes do flag on** (ver §6). Só liga `REDATO_B2C_ENABLED=true` depois deste E2E passar ponta a ponta.

## 6. Ligar a flag + teste manual
- `REDATO_B2C_ENABLED=true`.
- Teste com o telefone do Daniel + código DEMO: onboarding → **foto com o tema na legenda** → correção (abre com "📝 Tema:") → paywall sandbox → pagamento simulado → M5 → correção de assinante. Testar também: foto sem legenda → M16 → responder tema.

## 7. Só então
- Parceiros reais no seed + divulgação.

---
## Notas de arquitetura (o que já está pronto no código)
- Motor de correção único e público: `redato_backend/grading/grade_essay_completo`. B2C usa `force_claude=True` — o FT (OF14) não foi treinado pra usar tema e é evitado por pino explícito.
- Tema é injetado no campo `theme` do grader (`TEMA: {theme}` no prompt) — o mesmo campo do B2G.
- Pendência de tema vive em `envios_b2c.status='aguardando_tema'` (não no estado do aluno) → degustação e assinante podem ambos ter pendência sem perder o paywall. Fair use e correção grátis contam SÓ envio `corrigido`.
- Janela de 24h: mensagens de negócio (M5/M8/M9) via `b2c/notify.enviar_negocio` → freeform dentro da janela, Content template fora. Sem template aprovado → **freeform degradado** (provavelmente NÃO entregue) → registrado em `notificacoes_degradadas` e visível como `operacao.envios_degradados` no `/admin/b2c/metricas`; o retorno do daily-tick lista quais M9 saíram degradadas (`degradado: true`) + `degradados: N`. A régua avança mesmo assim (reflete o pagamento, não a entrega). **Enquanto `envios_degradados > 0`, há aluno sendo cobrado/avisado sem receber — submeter os templates é o fix.**
- Eventos Asaas desconhecidos → `eventos_billing.processado=false` + contador `eventos_pendentes` nas métricas. Divergência de split → `status='atencao_split'` (não quebra o fluxo).
