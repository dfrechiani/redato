# Backlog B2C · 02 — Calibrar o teto de fair use com tráfego real

**Status:** pós-piloto · **Gatilho de dados:** ~2 semanas de piloto com assinantes ativos gerando volume real de correções.

## Contexto (pra sessão fria)
O fair use está em **10 correções/dia por aluno** (`B2C_FAIR_USE_DIA`, default 10), escolhido a dedo antes de qualquer dado. Ao exceder, o aluno recebe a M7 ("volta amanhã"). O contador conta SÓ envio `corrigido` (foto pendente de tema não queima o dia — ADENDO §D7).

O número 10 é um chute. Com tráfego real dá pra saber se é frouxo (ninguém chega perto → poderia baixar pra cortar custo) ou apertado (aluno engajado bate no teto e fica frustrado → subir).

## Tarefa
1. Do `/admin/b2c/metricas?parceiro=<slug>`, puxar por parceiro: `correcoes_por_assinante_p50`, `correcoes_por_assinante_p95`, `custo_medio_centavos`, `margem_estimada_centavos`, e quantos alunos bateram na M7 (fair use) no período.
   - Se faltar o contador de "quantos bateram no teto", adicionar métrica `fair_use_atingido` (contar envios que resultaram em M7, ou um log dedicado).
2. Cruzar P95 de uso com o teto: se P95 << 10, o teto está frouxo; se muitos alunos batem em 10, está apertado.
3. Cruzar com margem: cada correção tem custo (`custo_medio_centavos`); teto alto + preço fixo comprime margem.

## Critério de pronto
- Relatório com P50/P95 de correções/dia por assinante, % de alunos que bateram no teto, e o impacto na margem.
- Recomendação de novo valor pra `B2C_FAIR_USE_DIA` (é só env, não precisa deploy de código) OU confirmação de que 10 está certo.
- Se faltava o contador de teto-atingido, entra como pequena adição instrumentada (sem tocar o fluxo).

## Não fazer
- Não mudar o teto sem o dado (o ponto é calibrar com número, não com palpite 2).
