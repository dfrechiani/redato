# Roadmap do diagnóstico cognitivo + pendências gerais

**Atualizado:** 2026-05-04 (após Fase 4)

Este doc complementa o [`README.md`](README.md) com o roadmap detalhado
das próximas fases + pendências fora do escopo do diagnóstico que
foram registradas durante a sessão de implementação.

## Fases do diagnóstico cognitivo

### ✅ Fase 1 — Descritores observáveis

YAML com 40 descritores INEP-aligned (`descritores.yaml`).
Commit `010686c` (2026-05-03).

### ✅ Fase 2 — Inferência LLM

Pipeline GPT-4.1 base lê redação + redato_output e gera 40 status +
top 5 lacunas. Persiste em `envios.diagnostico` JSONB. Commits
`d1fed81` e `2fe6185` (2026-05-03).

### ✅ Fase 3 — Visualização individual

Aluno: 3-5 metas via WhatsApp. Professor: heatmap 5 colunas com
nomes + lacunas com 3 seções (o que é + evidência + como trabalhar)
+ oficinas sugeridas por série. Commits `75edfcc` e `5db3cc6`
(2026-05-03).

### ✅ Fase 4 — Agregação por turma

Endpoint `GET /portal/turmas/{id}/diagnostico-agregado` + bloco
"Diagnóstico cognitivo da turma" no Dashboard. Heatmap coletivo,
top lacunas com oficinas, resumo executivo template. Sem agregação
cross-turma. Commit pendente (2026-05-04).

### ⏳ Fase 5A.1 — Mapeamento livros → 40 descritores

LLM parseia os 3 HTMLs (`LIVRO_ATO_1S/2S/3S_PROF`), extrai seções
e oficinas, mapeia cada uma → descritores que trabalha.

- Output: `docs/redato/v3/diagnostico/mapeamento_livro_descritores.json`
- Aviso "sugestão automática, em revisão" no portal
- Daniel revisa em sessão futura
- **Estimativa**: 1.5h Claude Code

Substitui o atual mapping competência→oficina (Fase 3) por
descritor→oficina, ganhando granularidade.

### ⏳ Fase 5A.2 — Mapeamento descritores → BNCC

Cruza os 40 descritores com habilidades BNCC do Ensino Médio
(EM13LP01, EM13LP02, ...).

- Output: `docs/redato/v3/diagnostico/descritores_bncc.json`
- Uso: justificativa pedagógica pra coordenação/escola
- **Estimativa**: 30min Claude Code

### ⏳ Fase 5B — Geração dinâmica de exercícios

LLM gera exercício novo baseado na lacuna específica do aluno (ex.:
"Aluno X tem lacuna em C5.001 — gere 3 frases pra ele praticar
substituir agente genérico").

**Adiada** até Fase 5A rodar e gerar dados de uso real (saber qual
oficina cobriu qual descritor, se o aluno melhorou depois).

### ⏳ Fase 6 — Knowledge Tracing (longitudinal)

Métrica: aluno fechou lacuna X após N redações? Visão de progresso
ao longo do ano com curva por descritor.

**Adiada** até ter dados acumulados de prod (precisa de pelo menos
3-5 envios por aluno em janelas separadas pra gerar curva). Hoje
volume de prod é muito baixo pra Knowledge Tracing dar sinal útil.

### ⏳ Fase 7 — Validação humana

Métricas de precisão (concordância com avaliador humano) + ajustes
de prompt baseados em divergências sistemáticas.

**Bloqueada** por falta de dataset de validação. Espera cursinhos
parceiros validarem manualmente um sample (~50-100 redações) antes
de poder calibrar.

## Pendências gerais (fora do diagnóstico)

Registradas durante as sessões de Fase 1-4. Vão pra próxima sessão
ou pro backlog.

### Críticas (resolver na próxima sessão)

- **`nota_total` vazio no portal quando OF14 cai no fallback Sonnet**
  (schema v2 antigo). Sintoma: turma 3S OF14 mostra envio sem nota
  no dashboard porque o FT BTBOS5VF não está disponível na conta
  OpenAI nova → fallback pro Sonnet 4.6 v2 retorna schema antigo
  que `_nota_total_de` não bate.

- **Migrar OF14 de volta pro FT** quando a conta OpenAI nova ganhar
  acesso ao modelo `BTBOS5VF` (ou treinar FT novo nessa conta).
  Custo: 2.348M tokens × $$ pra retreino + 1 dia A/B. Hoje fallback
  Claude funciona mas com schema mais pobre.

### Médio prazo

- **Permissão coordenador operar partidas** (#9). Hoje só professor
  pode criar partida do Jogo de Redação. Coordenador deveria poder
  pelo menos visualizar.

- **OF12/OF13 da 3S — sistema cartas argumentativas.** 3S tem
  sistema diferente do 1S (slots A/AÇ/ME/F vs classes gramaticais).
  Modelagem nova de banco + parser + handler bot. ~1-2 semanas
  trabalho focado.

- **OF02 e OF08 da 3S.** OF02 é chat-only (sem produção avaliável
  pelo Redato). OF08 pediria modo `foco_c1` que está adiado em
  código. Habilitar foco_c1 envolve enum + tool schema + scoring
  branch + DEFAULT_MODEL.

- **Wireframes guia foto pra aluno** (cartilha + bot). Aluno hoje
  não tem orientação visual de como tirar foto da redação manuscrita
  (posicionamento, iluminação, enquadramento). Produzir cartilha
  PDF + texto do bot quando OCR rejeitar foto.

- **Normalização telefone Twilio** (com 9 vs E.164). Sintoma: dois
  alunos com mesmo número (`+5511999998888` vs `+551199998888`) não
  são deduplicados, FK cross-turma falha.

### Roadmap maior (fora do escopo técnico)

- **Briefing corretora ENEM** (Fase 3 do roadmap original do produto,
  R$25k). Validação pedagógica da rubrica v2 com corretor INEP-
  certificado, calibrando o prompt da Fase 2.

- **Calibração v4 prompt** (Fase 2 original, depende de dados de
  prod). Próxima iteração do prompt do GPT-4.1 baseada em divergências
  observadas em prod. Espera Fase 7 do diagnóstico (validação
  humana) pra ter dataset.

## Ordem sugerida pra próximas sessões

1. **Resolver crítica**: `nota_total` vazio no fallback Sonnet
   (afeta UX do dashboard hoje). Sessão curta.
2. **Fase 5A.1**: mapeamento livros → descritores (1.5h). Desbloqueia
   sugestões granulares.
3. **Fase 5A.2**: descritores → BNCC (30min). Material pra
   coordenação.
4. **OF12/OF13 3S** OU normalização telefone Twilio. Sessão dedicada.
5. **Fase 5B**: exercícios dinâmicos (espera 5A.1).

Fases 6 e 7 ficam paradas até volume de prod justificar (Knowledge
Tracing) ou cursinhos parceiros validarem (Validação humana).
