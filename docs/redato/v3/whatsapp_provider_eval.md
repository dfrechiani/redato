# WhatsApp Business API — avaliação de provedores

**Status:** comparação técnica + recomendação. NÃO contratar até decisão
de produto.
**Data:** 2026-04-27.
**Escopo:** Fase A (sandbox/dev) e Fase B (produção piloto com 1-2
cursinhos parceiros).

## Cenário operacional

- Volume estimado: 5000 correções/ano (ver projeção em
  [REPORT_smoke_missions.md](REPORT_smoke_missions.md)).
- Sazonalidade: rajadas durante aulas (50min) e simulados.
- Mensagens por correção: ~3 (ack de recepção + resultado; cadastro
  inicial é 1 vez por aluno).
- Volume bruto estimado: ~15.000 mensagens iniciadas pelo
  bot/ano + ~5.000 mensagens recebidas = ~20.000 msgs/ano.

## Twilio WhatsApp Business API

### Setup
- Sandbox imediato (não precisa aprovação Meta) — útil pra Fase A.
- Para produção, ainda precisa **aprovar templates** com Twilio + Meta
  (1-3 dias úteis, geralmente).
- Webhook HTTPS público + assinatura HMAC.
- SDK Python (`twilio`) maduro, docs claras.

### Custo (referência pública 2025-2026, sujeito a ajuste)
- **Conversation initiated by user (recebida):** Twilio cobra $0.005/msg
  + custo Meta da conversa.
- **Service conversation (24h após user msg):** Meta tem janela de 24h
  grátis (até 1000 conversas/mês), depois $0.005-0.012 por conversa.
- **Marketing/utility conversation iniciada pelo bot:** $0.025-0.05/msg
  (depende da categoria + país).

Estimativa anual no nosso uso (assumindo ~20k msgs e maioria dentro de
janela de 24h):
- Twilio fee: ~20k × $0.005 = $100
- Meta WABA fee: 1k conversas grátis + ~4k conversas a $0.005 = ~$20
- **Total Twilio: ~$120/ano**

### Vantagens
- Setup mais rápido (sandbox em horas).
- Suporte: documentação, fóruns, status page.
- Recursos extras úteis (Twilio Studio pra fluxos visuais, Verify
  para 2FA — nada que precisamos agora, mas opção).
- Migrar de sandbox → produção é mudança de número, não de stack.

### Desvantagens
- Markup ~5-10x sobre o custo Meta direto (acima do volume de 1k
  conversas).
- Lock-in moderado: códigos de envio usam SDK Twilio.

## Meta WhatsApp Cloud API (direto)

### Setup
- Cadastro Meta Business Manager + verificação da empresa (2-7 dias
  úteis dependendo de documento).
- Telefone dedicado + número WABA aprovado (um único número por conta
  no Cloud API; pra Fase A com sandbox é mais difícil).
- Webhook HTTPS público + verificação de token.
- SDK Python não-oficial (`whatsapp-cloud-api-python`, etc.) ou HTTP
  direto.

### Custo (referência pública 2025-2026)
- **Service conversations (após user msg, 24h):** **grátis até 1000
  conversas/mês** + $0.005-0.012/conversa após.
- **Marketing/utility conversations:** $0.025-0.05/conversa
  (Brasil ~$0.045 marketing, ~$0.014 utility em 2025).

Estimativa anual:
- 5k correções/ano = ~5k conversas user-initiated
- Dentro do free tier (1k/mês × 12 = 12k conversas grátis) → **$0/ano em
  conversas user-initiated**
- Mensagens de ack proativas (se houver) entrariam como utility — ~$70

### Vantagens
- Custo: ~5x mais barato em escala.
- Sem markup de intermediário.
- Acesso direto à API oficial (features novas chegam primeiro).

### Desvantagens
- Setup mais demorado (precisa aprovação Meta Business + número
  dedicado verificado).
- SDK Python não-oficial — qualidade variável.
- Documentação Meta é menos didática que Twilio.
- Sem sandbox-style (precisa mesmo passar pela verificação).
- Suporte direto Meta é caótico.

## Comparativo resumido

| Aspecto | Twilio | Meta direto |
|---|---|---|
| Custo/ano (~20k msgs) | ~$120 | ~$70 (1k user-initiated grátis/mês) |
| Setup time (Fase A) | < 1 dia (sandbox) | 2-7 dias (verificação) |
| Setup time (produção) | 1-3 dias (templates) | 1-2 dias (após verificação) |
| Documentação | ✓✓✓ | ✓ |
| SDK Python oficial | ✓ | ✗ |
| Suporte | Twilio | Meta (lento) |
| Lock-in | Moderado | Baixo |
| Migração entre eles | Fácil (interface comum) | — |

## Recomendação

**Fase A (sandbox/dev):** **Twilio Sandbox** —
- Setup imediato, zero burocracia, ideal pra testar o fluxo bot.
- Custo desprezível em volume de testes (~$0.01-0.05 total no piloto).
- Permite iterar UX do bot antes de comprometer com tooling de produção.

**Fase B (piloto produção, 1-2 cursinhos parceiros):** **Twilio
produção** —
- Setup +rápido que Meta direto, time não trava em verificação Business.
- Custo $120/ano absorvível no orçamento do piloto.
- Permite focar em validação pedagógica, não em integração.

**Fase C (escala, múltiplos cursinhos, >50k msgs/ano):** **Migrar pra
Meta direto.** —
- Quando volume justificar a economia: $50-100/ano de diferença vira
  $500-1000+/ano em escala maior.
- Migração é abstraída se mantermos a interface `InboundMessage` /
  `OutboundMessage` agnóstica de provedor (já está assim no
  [`bot.py`](../../../backend/notamil-backend/redato_backend/whatsapp/bot.py)).

### Disposição arquitetural

O bot atual (`bot.py`) já está desacoplado do provedor. O webhook
receiver fica em arquivo separado (`twilio_webhook.py` ou
`meta_webhook.py`, a criar quando contratar) e traduz o payload do
provedor pro shape `InboundMessage`. Trocar provedor = trocar 1 arquivo
+ template de mensagens proativas.

## Decisão pendente

| Item | Quem decide | Quando |
|---|---|---|
| Contratar Twilio Sandbox | Operador do projeto | Quando iniciar Fase A real (com aluno real) |
| Contratar Twilio produção | Daniel + cursinho parceiro | Quando piloto fechado |
| Migrar pra Meta direto | Daniel + finance | Quando volume > 50k msgs/ano |

**Não contratar nada agora** — esta é apenas a avaliação técnica
solicitada.
