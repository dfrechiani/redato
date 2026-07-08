# Backlog B2C · 03 — Fila de correção pendente (gatilhada por fotos bloqueadas)

**Status:** pós-piloto · **Gatilho de dados:** `contar_fotos_bloqueadas(parceiro)` mostrando volume relevante no piloto (aluno inadimplente mandando redação e esperando).

## Contexto (pra sessão fria)
Decisão de MVP (ADENDO §D10): quando um aluno **inadimplente** manda uma redação, o sistema **NÃO** guarda pra corrigir depois — grava um `EnvioB2C(status='bloqueado')` SEM rodar OCR/grader (custo zero) e responde a M10 ("regulariza aqui, e me manda a foto de novo que corrijo na hora"). Copy honesta: promete só o que o sistema faz hoje.

Construir a fila de verdade (guardar a mídia, corrigir automaticamente quando o pagamento cair) foi adiado de propósito: exigiria **retenção da mídia do Twilio** (URLs expiram) + **entrega fora da janela de 24h via template**. Só vale o custo se o dado do piloto mostrar volume.

A instrumentação pra decidir JÁ EXISTE: `EnvioB2C.status='bloqueado'` + a métrica `fotos_bloqueadas` no `/admin/b2c/metricas`.

## Tarefa (só se o volume justificar)
1. Ler `fotos_bloqueadas` por parceiro no período. Se for baixo, **fechar este backlog** (a copy honesta basta). Se for alto (muitos alunos mandando redação enquanto inadimplentes), seguir.
2. Projetar a fila:
   - Retenção da mídia: baixar a foto do Twilio no momento do recebimento (a URL expira) e guardar (Railway volume `/app/data` ou storage). Reusar o OCR do fluxo normal, mas SÓ transcrever (não corrigir) enquanto bloqueado.
   - Ao `PAYMENT_CONFIRMED` (webhook): pegar os envios `bloqueado` do aluno, rodar o grader, e ENTREGAR — provavelmente fora da janela de 24h → template Content API (M6 vira template, ou um template novo "sua redação guardada foi corrigida").
   - Retenção/LGPD: definir por quanto tempo a mídia bloqueada fica guardada (e apagar após corrigir/expirar).
3. Trocar a M10 pela versão que promete a fila (a copy antiga da SPEC §6 M10 fazia isso).

## Critério de pronto
- Decisão registrada: fila SIM (com volume que justifica) ou NÃO (fecha o backlog com o número).
- Se SIM: retenção de mídia + reprocessamento no pagamento + entrega via template, com teste; e retenção LGPD definida.

## Não fazer
- Não construir a fila sem o dado de volume — o ponto todo é decidir com `fotos_bloqueadas`, não por antecipação.
