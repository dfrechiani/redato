# Adendo G — Decisões pedagógicas consolidadas

**Status:** APROVADO. Decisões fechadas com Daniel em 29/04/2026 após revisão das Seções A–F do doc original.

**Escopo deste adendo:** substitui a Seção F (que listava 7 perguntas abertas) e introduz ajustes pontuais nas Seções B, C, D e E. As Seções A (Entendimento do jogo) e G.1 abaixo passam a ser as referências canônicas para a Fase 2.

**Próximo passo:** Fase 2 desbloqueada (migration + seed das 63 estruturais + endpoints REST do portal, sem bot ainda).

---

## G.1 — As 7 decisões consolidadas

### G.1.1 — Mínimo obrigatório de cartas por partida

As 10 cartas estruturais (E##) são sempre obrigatórias — o tabuleiro tem 10 posições e o esqueleto da redação não pode ter buraco. As lacunas P/R/K nas seções de desenvolvimento (PROBLEMA, REPERTORIO, PALAVRA_CHAVE) são obrigatórias sempre que a estrutural escolhida pede.

Exceção — proposta: das 4 lacunas da proposta (AGENTE, AÇÃO, MEIO, FIM), até 2 podem faltar por motivo de tempo de jogo. O bot aceita a partida com proposta incompleta, avisa o aluno, e segue. Mínimo aceito: 2 lacunas entre A/AC/ME/F.

### G.1.2 — Grupos múltiplos por atividade

Modelagem 1:N atividade↔partidas. Vários grupos da mesma turma podem jogar simultaneamente, cada um com sua redação cooperativa. partidas_jogo.atividade_id é FK não-única; o que distingue partidas da mesma atividade é o grupo_codigo.

### G.1.3 — Troca de carta na reescrita individual

Não permitida. A reescrita individual é puramente textual. As cartas registradas no momento da partida ficam imutáveis como decisão do grupo.

### G.1.4 — Submissão sem partida

Bloqueada. Aluno não consegue submeter reescrita se não houver partida ativa cadastrada pelo professor. Sem partida, o aluno pode usar o fluxo M9.2 (foto normal) — mas isso vira correção comum, fora do contexto do jogo.

### G.1.5 — Tema do minideck vs tema da atividade

Tema do minideck domina e deve coincidir com tema da atividade. Validação no portal ao cadastrar partida.

### G.1.6 — transformacao_cartas e nota ENEM

Score independente, escala 0–100. Não compõe a nota total das 5 competências. Aparece no dashboard como métrica complementar.

### G.1.7 — Quantidade de sugestões de cartas alternativas

Lista dinâmica, 0 a 2 itens. Lista vazia é feedback positivo legítimo.

---

## G.2 — Ajustes nas seções existentes

### G.2.1 — Seção B (Fluxo aluno ↔ bot)

B.1 passo 3 (Bot valida): refletir as regras de obrigatoriedade da G.1.1 (10 estruturais sempre + P/R/K em desenvolvimento + A/AC/ME/F com tolerância de 2 faltantes na proposta).

B.1 passo 4 (Bot monta texto-base): quando lacunas A/AC/ME/F estiverem ausentes, expansão da estrutural deixa o trecho como marcador "[a definir]" na redação cooperativa.

B.3 (tabela de erros): incluir mensagem específica para "Falta 1-2 lacunas da proposta" como warning (não bloqueia), e "Falta 3+ lacunas da proposta" como erro.

### G.2.2 — Seção C (Arquitetura técnica)

C.1 schema: sem alteração. partidas_jogo.atividade_id como FK não-única já suporta 1:N.

C.3 validar_partida: retornar (ok, warnings, mensagem_erro) — warnings vazias se proposta completa; com itens se incompleta.

C.5 JOGO_REDACAO_TOOL: ajustar sugestoes_cartas_alternativas com minItems=0, maxItems=2.

### G.2.3 — Seção D (Comparação original vs reescrita)

UI: badge transformacao_cartas visualmente separado da nota ENEM (decisão G.1.6).

### G.2.4 — Seção E (Escopo de fases)

Fase 1: CONCLUÍDA em 29/04/2026.
Fase 2: DESBLOQUEADA. Migration + seed + endpoints sem bot ainda.

---

## G.3 — Resumo executivo

Decisões cobertas — total 12:
- E.1 a E.5 (entrada original)
- G.1.1 a G.1.7 (consolidação 29/04/2026)

Estimativa: 52h ≈ 7 dias úteis para o jogo funcionando ponta-a-ponta com 1 minideck (Saúde Mental).

Pendências futuras (não bloqueiam Fase 2):
- Calibração do score transformacao_cartas com canários
- Visualização do score na analítica do dashboard
- Volumetria do log

---

Fim do adendo G.
