# Runbook de deploy — Correção {Parceiro} (B2C)

> Operacional. Complementa SPEC_B2C_REDATO.md §8 e ADENDO_B2C_REDATO.md §14.
> Nada avança antes do gate correspondente. Sandbox até o Daniel autorizar produção.

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
- `alembic upgrade head` no Postgres do Railway (revision `l0a1b2c3d4e5`, head único).
- **Antes**, num Postgres descartável local, validar o ciclo: `upgrade head` → `downgrade -1` → `upgrade head`. Confirmar como o Railway aplica migrations hoje (release command? manual?) e registrar aqui.

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
- Janela de 24h: mensagens de negócio (M5/M8/M9) via `b2c/notify.enviar_negocio` → freeform dentro da janela, Content template fora. Sem template aprovado → freeform degradado + warning (submeter templates).
- Eventos Asaas desconhecidos → `eventos_billing.processado=false` + contador `eventos_pendentes` nas métricas. Divergência de split → `status='atencao_split'` (não quebra o fluxo).
