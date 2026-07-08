# Backlog B2C · 01 — Gate tema→C2 v2 com o corpus de 18k

**Status:** pós-piloto · **Gatilho de dados:** piloto rodando + acesso ao corpus de ~18 mil redações validadas.

## Contexto (pra sessão fria)
O gate atual `scripts/validar_tema_c2.py` (ADENDO §D7) provou que o motor de correção penaliza a C2 quando a redação **foge totalmente** do tema: nos 3 pares de teste, a C2 caiu de ~80 pra 0 no par off-topic. Isso valida o EXTREMO (fuga total), com 3 redações sintéticas curtas.

O que ele **não** mediu: o **meio** — tangenciamento genuíno (a redação toca o tema mas escorrega), e o comportamento com redações reais nota-alta (onde a C2 aderente deveria ser 160–200, não 80). A zona cinzenta é onde a calibração fina importa pro produto.

## Tarefa
1. Do corpus de 18k (redações reais já validadas por nota humana), amostrar:
   - N redações **nota-alta on-topic** (C2 real ≥ 160) — o motor deve manter C2 alta com o tema correto.
   - N casos de **tangenciamento genuíno** (redação toca mas escorrega do tema) — o motor deve dar C2 **intermediária** (não 0, não cheia).
   - N casos de **fuga total** reais — C2 deve zerar (confirma o extremo com dado real).
2. Rodar o mesmo protocolo do `validar_tema_c2.py` (corrigir com tema aderente vs. deslocado) e comparar a C2 do motor com a nota humana do corpus.
3. Medir: correlação motor↔humano na C2, e a curva na zona de tangenciamento.

## Critério de pronto
- Relatório com a distribuição de ΔC2 nas 3 faixas (on-topic / tangenciamento / fuga total) vs. nota humana.
- Recomendação: o motor calibra bem o meio, ou precisa de ajuste no prompt de C2? (Se precisar, a mudança é no system prompt compartilhado com o B2G → decisão do Daniel, teste de igualdade do prompt B2G antes/depois.)
- Script reutilizável `scripts/validar_tema_c2_corpus.py` que lê amostras do corpus (não redações hardcoded).

## Não fazer
- Não mexer no motor/prompt sem aprovação do Daniel (compartilhado com a escola).
- Não virar teste automatizado de CI (LLM real, flaky, custa por chamada) — é gate manual/offline.
