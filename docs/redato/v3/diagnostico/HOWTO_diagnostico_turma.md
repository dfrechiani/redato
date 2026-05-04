# HOWTO — Diagnóstico cognitivo agregado da turma (Fase 4 + UX D)

**Atualizado:** 2026-05-04 (fix UX proposta D — storytelling)

## O que é

Fase 4 entrega visão **coletiva** do diagnóstico cognitivo: pra cada
turma, mostra quais lacunas são mais frequentes entre os alunos
ativos. Útil pro professor planejar mini-aulas dirigidas que valem
pra turma toda — não só intervenção individual (Fase 3).

Implementação:
- Backend: `redato_backend/diagnostico/agregacao.py` +
  endpoint `GET /portal/turmas/{turma_id}/diagnostico-agregado`
- Frontend: componente `DiagnosticoTurma`
  (`redato_frontend/components/portal/DiagnosticoTurma.tsx`)
  renderizado dentro do `DashboardTurma` (aba "Dashboard" da página
  da turma)

Visibilidade:
- **Professor responsável pela turma**: vê tudo
- **Coordenador da escola**: vê tudo (mesma permissão Fase 3)
- **Outros professores**: 403
- **Aluno**: não tem surface (não há rota aluno-side pra esse bloco)

## Como acessar

1. Login como professor responsável
2. Navega pra `/turma/{id}` da turma desejada
3. Clica na aba **Dashboard** (ao lado de "Atividades")
4. Bloco "Diagnóstico cognitivo da turma" aparece abaixo do
   evolução-da-turma chart

## Layout (proposta D, 2026-05-04 — atualizado)

> **Fix UX**: Daniel reportou que o layout original (4 sub-blocos
> com heatmap dos 40 descritores em destaque) era pesado visualmente
> — information overload, professor não sabia o que fazer primeiro.
> Reorganizado em **storytelling acionável**: narrativa curta + 3
> categorias temporais de ações. Heatmap detalhado vai pra
> accordion expansível (não some, só fica em segundo plano).

Layout atual (top-down):

1. **Header compacto**: título + cobertura + barrinha + aviso opcional
2. **Narrativa principal** ("🎯 O que sua turma precisa agora"):
   1 frase curta com top lacuna + percentual + esclarecimento
3. **3 categorias temporais de cards de ação**:
   - 🔴 **TRABALHAR AGORA** — descritores ≥50% lacuna (max 2 cards
     com botão "Criar atividade" se houver oficina catalogada)
   - 🟡 **ESTA SEMANA** — descritores 30-49% lacuna (max 3 cards
     consultivos sem CTA forte)
   - 🟢 **ESTE MÊS** — competências com ≥2 descritores em alerta
     (max 2 cards de monitoramento)
4. **▼ Ver mapa completo dos 40 descritores** — accordion fechado
   por default, expande pro layout antigo (heatmap 5 colunas + top
   lacunas detalhadas)

Cada card de ação tem borda colorida pela urgência (vermelho/amarelo/
verde) e fundo sutil correspondente — sinaliza temporalidade sem
precisar reler.

### (legacy) Layout original — sub-blocos da Fase 4 inicial

Os 4 sub-blocos originais (Visão geral, Resumo executivo, Heatmap,
Top lacunas) ficam disponíveis no accordion. Endpoint preserva o
campo `resumo_executivo` pra retro-compat — qualquer cliente antigo
não regride.

### Sub-bloco 1 — Visão geral

Card grande com:
- Quantos alunos diagnosticados (X de Y)
- Barra de progresso da cobertura (% diagnosticados)
- Data do diagnóstico mais recente da turma
- **Avisos automáticos**:
  - Cobertura < 50% → "diagnóstico pode não refletir a turma
    completa, estimule mais alunos a enviar redações"
  - Cobertura < 3 alunos → "diagnóstico em formação, análise
    estatística fica confiável a partir de 3+"

### Sub-bloco 2 — Heatmap coletivo dos 40 descritores

Grid 5 colunas (C1-C5) × 8 descritores cada. Cada item mostra:
- Quadrado colorido pequeno
- Nome do descritor (ex.: "Concordância (verbal e nominal)")
- ID em cinza
- % alunos com lacuna no canto direito (quando > 0)

**Cores são DIFERENTES da Fase 3** — refletem percentual coletivo,
não status individual:

| Cor | % alunos com lacuna | Significado |
|---|---|---|
| Verde (`#10B981`) | < 30% | Turma majoritariamente OK nesse descritor |
| Amarelo (`#F59E0B`) | 30-50% | Atenção — começando a virar lacuna coletiva |
| Vermelho (`#EF4444`) | > 50% | Lacuna coletiva clara — mini-aula recomendada |
| Cinza (`#9CA3AF`) | sem dado | 0 alunos diagnosticados ainda |

Mobile: 5 colunas viram acordeão (`<details>`). Tap no header da
competência expande/colapsa lista.

Headers de coluna mostram mini-resumo: "X descritores ≥50% lacuna"
(ou "Sem alerta crítico").

### Sub-bloco 3 — Top lacunas coletivas

Cards horizontais (até 5) com descritores que têm **≥30% alunos
em lacuna** (threshold pra filtrar ruído de turma pequena —
1 aluno em 3 dá 33%, entra; 1 em 10 dá 10%, fica fora).

Cada card mostra:
- Badge da competência (vermelha se ≥50%, amarela 30-50%)
- Nome do descritor + ID
- Barra de progresso "X de Y alunos com lacuna (Z%)"
- 🎯 **Como trabalhar com a turma** — sugestão pedagógica do
  dicionário Fase 3 (`sugestoes_pedagogicas.py`)
- **Oficinas pra mini-aula coletiva** — 1-2 oficinas da SÉRIE da
  turma que trabalham aquela competência. Click vai pro modal de
  ativar missão pré-selecionado

### Sub-bloco 4 — Resumo executivo

Callout com 3-5 frases gerado por **template estático** (Fase 4 não
usa LLM aqui — Daniel decidiu, barato e previsível). Estrutura:

1. Visão geral (X de Y alunos diagnosticados, % cobertura, aviso
   se < 50%)
2. Ponto forte coletivo (competência com mais domínio se ≥50%)
3. Top 3 lacunas mencionadas por nome
4. Recomendação acionável (trabalhar a top lacuna #1 antes da
   próxima atividade)

Exemplo real:

> A turma 1A tem diagnóstico de 18 de 25 alunos (72%). Forte
> domínio coletivo em norma culta (C1, 65% médio em domínio).
> Lacunas coletivas mais frequentes: 'Agente' (C5.001, 67%);
> 'Ação' (C5.002, 56%); 'Profundidade do argumento' (C3.004, 50%).
> Recomenda-se trabalhar agente com a turma toda antes da próxima
> atividade — ver sugestão pedagógica detalhada no card abaixo.

LLM dinâmico fica pra Fase 5/6 (geração contextualizada por turma
+ história).

## Como interpretar

### Threshold do top lacunas (30%)

Por que 30% e não 0%?
- Turma de 30 alunos, 1 aluno com lacuna em descritor X = 3.3%.
  Não é problema da TURMA, é desse aluno (cobertura individual via
  Fase 3).
- Turma de 5 alunos, 1 com lacuna = 20%. Ainda é problema individual.
- 30%+ = pelo menos 1 em cada 3 alunos. Sinaliza que vale a pena
  parar, fazer mini-aula coletiva, voltar.

Lacunas <30% ainda aparecem no heatmap (verde/amarelo) — só não
viram card individual.

### Cores do heatmap (30% / 50%)

Mesmo princípio:
- < 30% verde: dispersão. Cada aluno com lacuna lida individualmente.
- 30-50% amarelo: começando. Valeria já mencionar em 1 aula.
- > 50% vermelho: maioria. Mini-aula coletiva PRIORITÁRIA antes da
  próxima atividade da turma.

### Aluno sem diagnóstico

Não conta no denominador. Se turma tem 25 alunos mas só 18 com
diagnóstico, todos os % são calculados sobre 18 (não 25). Os 7 sem
diagnóstico aparecem em "alunos_sem_diagnostico" pro professor
saber que precisa estimular envios.

Estados possíveis:
- 0 alunos diagnosticados → bloco mostra "Aguardando primeira
  redação corrigida" e nada mais
- 1-2 alunos → mostra dados parciais com aviso "diagnóstico em
  formação"
- 3+ alunos → análise estatisticamente útil

### Limitação: 1 envio por aluno

Aluno com 5 envios diagnosticados aparece no agregado pelo **último
envio**. Não pondera por antiguidade nem média histórica — assume
que o último reflete o estado atual.

Implicação: se aluno melhora entre envio 1 e 5, agregado mostra a
foto melhor. Se piora, mostra a foto pior.

## Como usar pra planejar mini-aulas

Caso típico: turma 1A com top 3 lacunas em C5 (proposta de
intervenção).

1. **Confirma**: clica nos cards de top lacunas pra ver a sugestão
   pedagógica de cada (`🎯 Como trabalhar com a turma`).
2. **Cruza com oficinas**: cada card lista 1-2 oficinas da série
   1S que trabalham C5. Foco_c5 vem antes de completo no ranking.
3. **Cria atividade pra turma**: clica no link da oficina → modal
   "Ativar missão" abre com a missão pré-selecionada.
4. **Valida em 1-2 semanas**: depois que turma fizer a nova
   atividade e diagnóstico rodar, volta no Dashboard. % alunos
   com lacuna naqueles descritores deve ter caído.

## Como interpretar urgência (proposta D)

- **🔴 Trabalhar agora**: lacunas em ≥50% dos alunos diagnosticados.
  Mini-aula coletiva ANTES da próxima atividade — senão a turma
  inteira repete o mesmo erro. Card traz oficina sugerida + botão
  "Criar atividade" pra ativar imediatamente.
- **🟡 Esta semana**: 30-49% lacuna. Não é catastrófico mas merece
  revisão dirigida em algum momento da semana — pode ser exercício
  rápido, exemplo no quadro, comentário recorrente em devolutivas.
  Sem CTA forte de oficina (pra não saturar com criação de atividades).
- **🟢 Este mês**: competência inteira com ≥2 descritores críticos.
  Visão de longo prazo — reavaliar após 2-3 redações. Foco em
  monitorar evolução, não em ação imediata.

## Limitações conhecidas

- **Cobertura insuficiente** distorce agregado. Turma com 5 alunos
  diagnosticados em 25 ativos (20% cobertura) ainda mostra
  agregados, mas com aviso. Dificulta separar problema-da-turma de
  problema-dos-5-que-enviaram.

- **Sugestão de oficina por competência, não por descritor.**
  C5.001 (Agente) e C5.005 (Detalhamento) compartilham as mesmas
  oficinas sugeridas (todas que trabalham C5). Granularidade fina
  exige catálogo descritor → oficina que ainda não existe (Fase
  5A.1 do roadmap).

- **Resumo executivo template-based.** Não personaliza por
  história da turma ("essa turma melhorou C3 desde a OF14"). LLM
  dinâmico só na Fase 5+ quando volume justificar custo extra.

- **Sem comparação cross-turma.** Coordenador da escola não tem
  view tipo "qual turma está pior em C5?". Cada turma é uma
  consulta separada. Agregação cross-turma pra dashboard de escola
  fica fora do escopo Fase 4.

- **Sem histórico longitudinal.** Não dá pra ver "% lacuna em
  C5.001 caiu de 80% pra 30% nos últimos 30 dias". Cada chamada do
  endpoint é snapshot. Knowledge tracing entra na Fase 6.

## Tests

`backend/notamil-backend/redato_backend/tests/diagnostico/test_agregacao.py`
(14 cenários):

- `calcular_top_lacunas` (3): threshold 30%, cap 10, ordenação desc
- `agregar_diagnosticos_turma` (3): zero alunos, 25 alunos, metade
  diagnosticada (cobertura 40%)
- `_gerar_resumo_executivo` (3): 3 alertas, sem lacunas, 0 diagnosticados
- Endpoint estrutural (4): auth via `_check_view_turma`, sem
  bypass, 404 turma inexistente, filtro `Envio.diagnostico.isnot(None)`
- Schema (1): `DiagnosticoAgregadoResponse` aceita payload completo

Frontend: `tsc --noEmit` clean.

## Deploy checklist

Sem migration nova — Fase 4 é puramente leitura agregada.

1. Push aciona deploy automático Railway (backend + frontend)
2. Não precisa rodar `alembic upgrade head`
3. Não precisa setar env var nova
4. Smoke pós-deploy:
   - Acessa `/turma/{id}` de uma turma com pelo menos 1 envio
     diagnosticado
   - Clica aba "Dashboard"
   - Bloco "Diagnóstico cognitivo da turma" aparece com:
     - Visão geral com % cobertura
     - Resumo executivo coerente
     - Heatmap colorido (verde/amarelo/vermelho conforme dados)
     - Top lacunas se há descritor ≥30%

Em caso de problema na Fase 4 especificamente (heatmap não
aparece, agregado vazio inesperadamente):
- Endpoint funciona? `curl GET .../diagnostico-agregado` deve
  retornar JSON válido
- Tem alunos diagnosticados? `psql -c "SELECT COUNT(*) FROM
  envios WHERE diagnostico IS NOT NULL AND aluno_turma_id IN (...)"`
- Logs Railway pra erros do helper de agregação
