# SPEC — Redato B2C "Correção [Parceiro]" (influencers)
> Para o Claude Code, na raiz do repo `redato_hash`. Autor: Daniel + Claude (Cowork), 07/07/2026.
> Missão: adicionar o modo B2C por assinatura ao Redato SEM quebrar o fluxo escola (B2G) que está em produção.

## 0. Contexto do repo (o que já existe — use, não reinvente)
- Backend FastAPI unificado: `backend/notamil-backend/redato_backend/unified_app.py` monta `admin_router`, `auth_router`, `portal_router`, `jogo_router` e `twilio_router` (`redato_backend/whatsapp/webhook.py` → `POST /twilio/webhook`).
- Bot WhatsApp: Twilio; roteamento atual é **por atividade ativa** de turma (ver `missions/router.py`, testes em `tests/whatsapp/test_bot_routing.py`). Formatação WhatsApp em `portal/formatters.py` + formatadores das missions.
- Correção: pipeline missions (`missions/scoring.py`, `missions/prompts.py`, `missions/openai_ft_grader.py`, `ensemble/`), diagnóstico com **40 descritores** (`diagnostico/descritores.py` + `docs/redato/v3/diagnostico/descritores.yaml`), OCR já resolvido no fluxo de envio por foto.
- Dados: Postgres (Railway), SQLAlchemy em `portal/models.py` (Escola, Coordenador, Professor, Turma, AlunoTurma, Missao, Atividade, Envio, Interaction, Jogo*), migrações Alembic em `portal/migrations/versions/`.
- Deploy: Railway com auto-deploy do GitHub (`dfrechiani/redato`, branch main). `dev_offline.py` permite rodar sem APIs externas. Testes: pytest (`tests/whatsapp/`, `tests/portal/`, `tests/missions/`).
- Produção: backend `backend-production-3bd7.up.railway.app` (M8), frontend "Portal do Professor" `frontend-production-74ab7.up.railway.app`.

## 1. Objetivo
Aluno chega pelo link de um professor-influencer, assina "Correção {{Parceiro}}" (R$ 39–49/mês) e manda foto de redação manuscrita no WhatsApp; recebe em minutos nota nas 5 competências + diagnóstico + histórico. O parceiro recebe % automático via **split do Asaas**. O Redato é motor invisível ("powered by Redato").

**Princípios:** (a) fluxo escola intocado — B2C atrás de feature flag `REDATO_B2C_ENABLED`; (b) nenhum termo comercial hardcoded — % e preço são config por parceiro; (c) nenhum secret commitado; (d) tudo testável offline (mock Asaas + dev_offline).

## 2. Decisões de produto (defaults — Daniel pode alterar)
- **D1 Identificação do parceiro:** 1 número Twilio compartilhado + **código de entrada no deep link** (`wa.me/<numero>?text=QUERO+LUMA`). Sender dedicado por parceiro fica para Fase 2 se o piloto pedir.
- **D2 Degustação:** **1 correção grátis** antes do paywall (mostra o valor antes de pedir cartão).
- **D3 Fair use do "ilimitado":** 10 correções/dia por aluno (config `B2C_FAIR_USE_DIA`). Mensagem simpática ao atingir.
- **D4 Preço:** config por parceiro (`preco_centavos`, default 3990). Não exibir % de share em NENHUMA mensagem ao aluno.
- **D5 Gateway:** Asaas (split nativo em assinatura; parceiro PF abre conta própria e fornece `walletId`). Backup: Pagar.me Flex.
- **D6 Rubrica:** motor de correção idêntico para todos no MVP; camada do parceiro = branding/copy (nome, saudação, assinatura das mensagens). Rubrica custom por parceiro = Fase 2.

## 3. Modelo de dados (novas tabelas — Alembic migration nova)
```
ParceiroB2C:  id, slug (ex. "luma"), codigo_entrada (ex. "LUMA"), nome_publico ("Correção Luma"),
              nome_professor, wallet_id_asaas, share_pct (Numeric), preco_centavos (int, default 3990),
              ativo (bool), branding JSON (saudacao, emoji, assinatura, cor), created_at
AlunoB2C:     id, telefone_e164 UNIQUE, nome, parceiro_id FK, estado ENUM(novo, aguardando_nome,
              degustacao, aguardando_pagamento, ativo, inadimplente, bloqueado, cancelado),
              correcoes_gratis_usadas int default 0, consent_lgpd_at timestamp, created_at
AssinaturaB2C: id, aluno_id FK, asaas_customer_id, asaas_subscription_id, status ENUM(pendente, ativa,
              atrasada, cancelada), valor_centavos, ciclo ("MONTHLY"), proximo_vencimento, created_at, updated_at
EnvioB2C:     id, aluno_id FK, parceiro_id FK, imagem_url/texto_ocr/texto_final, nota_total,
              notas_competencias JSON (c1..c5), diagnostico JSON (descritores), tempo_processamento_ms,
              custo_estimado_centavos, created_at
EventoBilling: id, aluno_id, tipo (webhook event), payload JSON, processado bool, created_at  # idempotência
```
Não acoplar em `Envio` (ele referencia Atividade/Turma). Reutilizar as FUNÇÕES do pipeline de correção, não as tabelas do B2G.

## 4. Fluxos (F1–F10) — mensagens prontas na seção 6
- **F1 Entrada/onboarding:** webhook Twilio recebe msg de telefone desconhecido pelas tabelas B2G → se `REDATO_B2C_ENABLED` e a msg contém código de parceiro válido (ou o aluno já é AlunoB2C) → fluxo B2C. Cria AlunoB2C(estado=novo) → M1 boas-vindas com a marca + consentimento LGPD (obrigatório: público inclui menores; link da política; prosseguir = aceite, gravar `consent_lgpd_at`) → pede nome → estado=degustacao → M2 convida a mandar a 1ª foto grátis.
  - Telefone desconhecido SEM código: M0 (pergunta de qual professor veio, lista nenhuma — pede o código/link; se nada, orienta procurar o link na bio do professor).
- **F2 Correção de degustação:** foto → pipeline OCR+grader completo (nota total + C1–C5 + top descritores + 1 orientação de reescrita) → entrega M3 (com marca) → paywall M4 com link de checkout Asaas → estado=aguardando_pagamento.
- **F3 Assinatura (Asaas):** criar `customer` (nome, CPF opcional no MVP — [Daniel decide: Asaas aceita customer sem CPF? validar no sandbox; se exigir, pedir CPF no chat antes do link]), criar `subscription` MONTHLY com `value` do parceiro e `"splits":[{"walletId": parceiro.wallet_id_asaas, "percentualValue": parceiro.share_pct}]` → enviar `invoiceUrl`. Webhook `POST /billing/asaas/webhook` (router novo `redato_backend/billing/`): `PAYMENT_CONFIRMED|RECEIVED` → assinatura ativa, aluno.estado=ativo, M5 liberado; `PAYMENT_OVERDUE` → F6; `SUBSCRIPTION_DELETED`/cancelamento → F7. Proteger com token de webhook (header) + idempotência via EventoBilling.
- **F4 Correção do assinante:** foto → valida estado=ativo → contador fair use → pipeline → M6 entrega (nota + C1–C5 + 2 destaques + 1 foco de melhoria + evolução "800 → 840 → 880") → grava EnvioB2C. Texto digitado (sem foto) também aceito.
- **F5 Fair use:** ao exceder `B2C_FAIR_USE_DIA` → M7 (volta amanhã, sem tom punitivo).
- **F6 Inadimplência:** OVERDUE D0 → M8 aviso; D+3 → M9; D+5 → estado=inadimplente (recebe foto, NÃO corrige, responde M10 com link de regularização). Pagou → reativa + M5.
- **F7 Cancelamento:** aluno manda "cancelar" → M11 confirma → chama DELETE subscription no Asaas → mantém ativo até fim do ciclo pago → depois estado=cancelado. Win-back fora de escopo.
- **F8 Comandos:** "evolução"/"histórico" → M12 (últimas 5 notas + gráfico textual); "ajuda" → M13; "tema" → M14 (sorteia proposta de um banco simples — usar temas já existentes no repo se houver); fallback → M15.
- **F9 Onboarding de parceiro (admin):** endpoint `POST /admin/b2c/parceiros` (auth admin existente) com validação do walletId (GET na API Asaas) + gera deep link e QR (lib `qrcode`) → retorna kit técnico do parceiro. CLI/script `scripts/seed_parceiro.py` alternativo.
- **F10 Métricas:** `GET /admin/b2c/metricas?parceiro=luma` → funil (entradas → cadastros → degustações → assinantes ativos → inadimplentes → cancelados), correções/dia, tempo médio de correção, custo estimado, MRR e parte do parceiro. É a fonte do dashboard do parceiro (Fase 2: recorte visual no portal).

## 5. Integração Asaas — referência rápida
- Docs: docs.asaas.com → "Split em assinaturas", "Checkout com assinatura recorrente", "Webhooks", "Sandbox". Sandbox: `sandbox.asaas.com` (simula pagamento).
- Env novas: `ASAAS_API_KEY`, `ASAAS_BASE_URL` (sandbox/prod), `ASAAS_WEBHOOK_TOKEN`, `REDATO_B2C_ENABLED`, `B2C_FAIR_USE_DIA=10`, `B2C_FREE_CORRECTIONS=1`, `B2C_NUMERO_WHATSAPP`.
- Letras miúdas que o código DEVE respeitar: split % incide sobre o **líquido** (taxa sai do Redato); divergência de split **bloqueia a assinatura** (tratar webhook de aviso); atualização de % só afeta cobranças futuras; **estorno/chargeback reverte o split**; cartão liquida D+32 (não prometer repasse imediato em nenhuma copy).

## 6. Mensagens do bot (copies prontas — placeholders `{{...}}`)
- **M0 sem código:** "Oi! 👋 Aqui é a correção de redação por WhatsApp. Você chegou pelo link de qual professor(a)? Me manda o código que aparece na bio dele(a) (ex.: LUMA) que eu te coloco na turma certa."
- **M1 boas-vindas:** "Bem-vindo(a) à **{{nome_publico}}**! ✍️ Aqui você manda a FOTO da sua redação manuscrita e recebe em minutos a correção nas 5 competências do ENEM, no padrão do(a) prof. {{nome_professor}}. Antes de começar: seus textos e dados são usados só para a sua correção e evolução (política: {{link_politica}}). Ao continuar, você concorda. Como você se chama?"
- **M2 convite grátis:** "Prazer, {{nome}}! 🎁 Sua primeira correção é por nossa conta. Fotografa sua redação (folha inteira, boa luz) e manda aqui."
- **M3 entrega degustação:** "✅ Correção pronta! Nota: **{{nota_total}}/1000** — C1 {{c1}} · C2 {{c2}} · C3 {{c3}} · C4 {{c4}} · C5 {{c5}}. 💪 Destaque: {{ponto_forte}}. 🎯 Para subir: {{foco_melhoria}}. Essa foi sua correção gratuita da {{nome_publico}}!"
- **M4 paywall:** "Quer treinar TODOS os dias até o ENEM? A assinatura {{nome_publico}} te dá correção ilimitada, em minutos, aqui no WhatsApp, por R$ {{preco}}/mês. 👉 {{link_checkout}} (cancela quando quiser)"
- **M5 liberado:** "🎉 Assinatura ativa! Pode mandar redação sem limite, {{nome}}. Dica: escreve → recebe o diagnóstico → reescreve em cima do erro → manda de novo. É assim que se chega no 900+."
- **M6 entrega assinante:** "✅ **{{nota_total}}/1000** — C1 {{c1}} · C2 {{c2}} · C3 {{c3}} · C4 {{c4}} · C5 {{c5}}. 💪 {{ponto_forte}}. 🎯 {{foco_melhoria}}. 📈 Sua evolução: {{ultimas_notas}}. Manda a próxima quando quiser!"
- **M7 fair use:** "Você treinou MUITO hoje ({{n}} redações!) 🔥 Pra correção manter a qualidade, seguimos amanhã. Que tal reescrever a de hoje aplicando o diagnóstico?"
- **M8 overdue D0:** "Oi {{nome}}! Não conseguimos renovar sua assinatura {{nome_publico}}. Pra não parar seu treino: {{link_fatura}}"
- **M9 overdue D+3:** "Seu acesso vence em 2 dias, {{nome}}. Renova aqui pra não perder o ritmo (e o histórico da sua evolução): {{link_fatura}}"
- **M10 bloqueado:** "Recebi sua redação e guardei aqui! 📥 Ela será corrigida assim que sua assinatura for regularizada: {{link_fatura}}"
- **M11 cancelar:** "Sem problema, {{nome}}. Confirma o cancelamento respondendo SIM. Seu acesso continua até {{fim_ciclo}} e seu histórico fica guardado se voltar. 💙"
- **M12 evolução:** "📈 Suas últimas notas: {{lista}}. Média C1–C5: {{medias}}. Competência pra focar: {{pior_comp}}."
- **M13 ajuda:** "Comandos: manda uma FOTO da redação pra corrigir · 'evolução' pra ver seu histórico · 'tema' pra receber uma proposta de treino · 'cancelar' pra encerrar."
- **M14 tema:** "🎯 Tema de treino: '{{tema}}'. 30 linhas, caneta preta, foto ao terminar. Bora!"
- **M15 fallback:** "Não entendi 🤔 Manda uma FOTO da redação pra eu corrigir, ou 'ajuda' pra ver o que sei fazer."
- **Foto ilegível:** "Não consegui ler bem sua letra nessa foto 😅 Tenta de novo: folha inteira no quadro, luz de frente, sem sombra. Se preferir, digita o texto."

## 7. Critérios de aceite (testes obrigatórios, padrão pytest do repo)
1. Telefone de aluno de TURMA (B2G) continua roteando pro fluxo escola — regressão zero (`test_bot_routing.py` estendido).
2. Telefone novo + "QUERO LUMA" → cria AlunoB2C do parceiro certo → M1.
3. Degustação: 1 foto grátis corrige e entrega; 2ª foto sem pagar → M4 (paywall), não corrige.
4. Webhook Asaas PAYMENT_CONFIRMED (payload sandbox real) → ativa e manda M5; evento duplicado não reprocessa (idempotência).
5. OVERDUE → régua M8/M9/M10; pagamento posterior reativa.
6. Fair use: 11ª correção do dia → M7.
7. Split: assinatura criada no sandbox contém `splits` com walletId e % do parceiro (assert no payload enviado).
8. `REDATO_B2C_ENABLED=false` → comportamento atual intacto.
9. Nenhuma mensagem contém % de share ou termos comerciais.
10. `GET /admin/b2c/metricas` retorna funil correto com dados seed.

## 8. Fases
- **Fase 1 (MVP, ~1 semana):** migration + F1–F4 + F6 básico + webhook Asaas sandbox + testes 1–8. Deploy atrás de flag.
- **Fase 2:** F5 refinado, F7–F10, QR/kit do parceiro, recorte de dashboard por parceiro no portal, sender Twilio dedicado por parceiro, rubrica custom, win-back.

## 9. Não fazer
- Não alterar fluxo/tabelas B2G (Envio, Atividade, missions do jogo).
- Não hardcodar preço/percentual — tudo em ParceiroB2C/env.
- Não commitar secrets (`.env` fora do git; conferir `.gitignore`).
- Não trocar o motor de correção — reutilizar grader/descritores existentes.
- Não criar conta/checkout real em produção — sandbox até Daniel autorizar.

## 10. Pendências do Daniel (responder antes/durante)
1. Confirmar D1–D6 (defaults acima).
2. Criar conta Asaas PJ + sandbox e colocar `ASAAS_API_KEY` no Railway/env local (NUNCA no chat/git).
3. Validar E2E atual do bot (foto → correção) e os bugs de 29/abr (foto no portal, análise sem estrutura) — ver `diagnostico_redato.md` no Cowork.
4. Números reais dos 3 parceiros-piloto (slug, nome_publico, share_pct, preco) quando fecharem contrato — até lá, usar parceiro fake "DEMO" no seed.
```

---

## Prompt inicial sugerido (colar no Claude Code, na raiz do repo)
"Leia SPEC_B2C_REDATO.md na raiz. Antes de codar: (1) confirme que entendeu o roteamento atual do webhook Twilio e me mostre em 10 linhas como vai encaixar o desvio B2C sem afetar o B2G; (2) proponha a migration; (3) liste dúvidas. Depois implemente a Fase 1 na ordem da seção 8, com os testes da seção 7 passando. Trabalhe em branch `feat/b2c-mvp`, commits pequenos, e NÃO commite nenhum secret."
