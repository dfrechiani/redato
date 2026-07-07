"""Billing B2C — integração com o gateway de pagamento (Asaas).

Split nativo em assinatura recorrente: o parceiro (PF) tem conta Asaas
própria e fornece o `walletId`; a cada cobrança, o percentual do
parceiro é repassado automaticamente pelo Asaas. Nenhum secret vive no
código — `ASAAS_API_KEY`/`ASAAS_BASE_URL`/`ASAAS_WEBHOOK_TOKEN` são env.

Sandbox/mock por padrão: sem `ASAAS_API_KEY` (ou com REDATO_DEV_OFFLINE),
`get_asaas_client()` devolve o `MockAsaasClient` — nada de rede.
"""
