# HOWTO — Visualização do diagnóstico cognitivo (Fase 3)

**Atualizado:** 2026-05-03 (fix Fase 3: heatmap + diversidade + cards)

## O que é

A Fase 3 transforma o JSON cru de `envios.diagnostico` (Fase 2) em
duas visualizações distintas, cada uma adequada a quem vê:

- **Aluno**: 3-5 metas em linguagem motivacional, entregues como
  mensagem extra do WhatsApp logo após a correção.
- **Professor**: heatmap 5×8 dos 40 descritores + lacunas
  prioritárias com evidência + resumo qualitativo + recomendação +
  oficinas sugeridas, no perfil do aluno
  (`/turma/{turma_id}/aluno/{aluno_id}`).

Implementação:
- Backend: `redato_backend/diagnostico/metas.py` (geração de metas) +
  `redato_backend/diagnostico/sugestoes.py` (oficinas sugeridas)
- Endpoint: `GET /portal/turmas/{turma_id}/alunos/{aluno_turma_id}/perfil`
  agora inclui campo `diagnostico_recente`
- Bot: `whatsapp/bot.py` anexa metas como mensagem extra ao retornar
  do pipeline de correção
- Frontend: componente `MapaCognitivo` em
  `redato_frontend/components/portal/MapaCognitivo.tsx`

## Como o aluno vê (metas via WhatsApp)

Após mandar a foto da redação, o aluno recebe:

1. Feedback INEP (renderizado por `render_aluno_whatsapp`, igual
   pré-Fase 3) — pode vir em vários chunks pela API do Twilio
2. **Mensagem extra** com as metas, formato:

   ```
   🎯 *Suas metas pra próxima redação*

   *1. Construa propostas com agente nomeado*
   Quem vai executar? Ministério da Educação, ONGs, escolas. Não
   'a sociedade' nem 'todos nós'.

   *2. Aprofunde os argumentos*
   Não basta 'isso é grave'. Explique a causa, a consequência, o
   mecanismo de funcionamento.

   ...
   ```

Princípios:

- **Linguagem positiva**: "Construa", "Aprofunde", "Use" — voz de
  professor encorajando, sem expor lacunas/notas baixas.
- **Máximo 5 metas**: saturação cognitiva acima disso. Se LLM gerou
  10 lacunas, cap em 5.
- **Dedup por competência**: 3 lacunas em C5 viram 1 meta de C5 (a
  primeira em prioridade). Evita 3 frases redundantes.
- **Falha não bloqueia**: se diagnóstico falhou (timeout, key, etc.),
  metas não vão — mas correção principal vai normal.

Dicionário descritor → meta está em `redato_backend/diagnostico/metas.py`.
40 entries. Atualização exige PR + revisão pedagógica.

## Como o professor vê (Mapa Cognitivo)

Acessa pela navegação:
1. `/turma/{turma_id}` → "Alunos cadastrados" → clica no aluno
2. Página `/turma/{turma_id}/aluno/{aluno_id}` mostra perfil completo
3. Bloco "Mapa cognitivo" entre Stats e Gráfico de evolução

Quatro sub-blocos:

### 1. Mapa dos 40 descritores observáveis (heatmap reformatado)

> **Fix Fase 3 #1**: o draft anterior era grid 5×8 só com IDs
> (`1.5`, `2.7`...). IDs sozinhos não comunicam. Reformatado pra
> 5 colunas com **nome legível** ao lado de cada descritor.

**Desktop**: 5 colunas lado a lado (C1, C2, C3, C4, C5). Cada
coluna tem header com nome curto da competência + mini-resumo
(`X/8 em domínio · Y em lacuna`). Dentro da coluna, lista vertical
de 8 itens, cada um com:
- Quadrado colorido pequeno (16×16 px) à esquerda
- Nome do descritor (ex.: "Concordância (verbal e nominal)") em 13px
- ID em cinza pequeno embaixo (`C1.005`)
- ★ amarelo se for lacuna prioritária (clicável — scrolla pro card)

**Mobile**: 5 colunas viram acordeão (`<details>`). Tap no header
da competência expande/colapsa a lista de 8 descritores.

| Cor | Status | Significado |
|---|---|---|
| Verde (`#10B981`) | `dominio` | Aluno demonstra controle do descritor |
| Amarelo (`#F59E0B`) | `incerto` | Sinal ambíguo ou texto curto demais |
| Vermelho (`#EF4444`) | `lacuna` | Erro/ausência clara |
| Cinza (`#9CA3AF`) | sem dado | Descritor não classificado (raro) |

Click em descritor com ★ (lacuna prioritária) faz scroll suave até
o card detalhado correspondente em "Lacunas prioritárias", com
highlight visual de 1.5s.

Backend: payload `descritores` é enriquecido com `nome`,
`competencia` e `categoria_inep` lidos do YAML
(`docs/redato/v3/diagnostico/descritores.yaml`) por
`_build_diagnostico_recente`. Frontend consome direto, sem precisar
fetch separado do YAML.

### 2. Lacunas prioritárias (cards 3 seções)

> **Fix Fase 3 #2** (diversidade): top 5 antes podia vir 4 da mesma
> competência (caso real envio af8556f6 = `[C5.001, C5.002, C5.003,
> C5.004, C3.001]`). Pós-processamento agora força **max 2 por
> competência**, completa com lacunas de outras Cs ordenadas por
> confiança alta→baixa. Implementação: `diversificar_lacunas_prioritarias`
> em `redato_backend/diagnostico/inferencia.py`, aplicada DENTRO de
> `inferir_diagnostico` antes de salvar — já vai diversificado pro
> banco.

> **Fix Fase 3 #3** (cards enriquecidos): cards antigos tinham só
> evidência. Agora cada card tem **3 seções**:

```
┌─ Card lacuna prioritária ──────────────────┐
│ [C5]  Agente                                │
│ C5.001 · Confiança Alta                     │
│                                             │
│ 📌 O QUE É                                  │
│ A proposta nomeia QUEM vai executar — inst- │
│ ituição, órgão, ministério, ONG.            │
│                                             │
│ 🔍 EVIDÊNCIA NO TEXTO                       │
│ "Não há proposta de intervenção..."         │
│                                             │
│ 🎯 COMO TRABALHAR                           │
│ Mostre exemplos de propostas com agentes    │
│ específicos. Trabalhe substituir 'todos'    │
│ por agente nomeado.                         │
└─────────────────────────────────────────────┘
```

Backend pré-resolve `lacunas_enriquecidas` com:
- `definicao_curta`: 1-2 frases iniciais do YAML campo `definicao`
  (truncado a ~150 chars em ponto-final)
- `sugestao_pedagogica`: vem do dicionário fixo
  `redato_backend/diagnostico/sugestoes_pedagogicas.py` (40 entries
  com 1-2 frases acionáveis cada)

Ordem dos cards = ordem de `lacunas_prioritarias` (o LLM priorizou
por impacto pedagógico, e a diversificação preservou essa ordem
dentro do cap).

### 3. Resumo + Recomendação

Dois painéis lado a lado:
- **📊 Análise** — texto livre do `resumo_qualitativo` (3-5 linhas
  do LLM, voz de professor pra outro professor)
- **🎯 Recomendação** — texto do `recomendacao_breve` (2-3 linhas
  apontando reforço prioritário)

### 4. Oficinas sugeridas

Cards das missões da MESMA SÉRIE do aluno que trabalham as
competências em lacuna:

- Código + título da missão (ex.: "RJ2·OF12·MF Leilão de Soluções")
- Tag do modo de correção (`foco_c5`, `completo`, etc.)
- Razão: "Trabalha proposta de intervenção (C5)"
- Link "Criar atividade →" deeplinka pra
  `/turma/{turma_id}?aba=atividades&missao={codigo}` (modal de
  ativar missão pré-seleciona)

Ranking interno:
1. Foco específico antes (`foco_c5` antes de `completo`)
2. Por número da oficina ascendente
3. Dedup global (mesma oficina aparece 1x mesmo cobrindo várias
   lacunas)
4. Máximo 2 oficinas por competência

## Estado vazio

Se aluno NÃO tem nenhum envio com `diagnostico IS NOT NULL`, o bloco
mostra:

> Diagnóstico cognitivo aparece aqui após o aluno enviar uma redação.
> Última correção sem diagnóstico significa que não foi possível
> processar — clique em **Reprocessar avaliação** na tabela abaixo.

Ações disponíveis pro professor nesse caso:
1. Esperar próximo envio do aluno (diagnóstico roda automaticamente)
2. Reprocessar envio existente: chamar `POST /portal/envios/{id}/reprocessar`
   pelo botão na tabela de envios — gera novo redato_output e dispara
   diagnóstico novamente

## Limitações conhecidas

- **Sugestão por COMPETÊNCIA, não por descritor.** Mapeamos `C1.005`
  → competência C1 → modos `foco_c1, completo_parcial, completo`.
  Granularidade fina (descritor → exercício específico) exige um
  catálogo que ainda não existe — fica pra Fase 4 ou 5.

- **Filtro por série fixo.** Aluno 2S só vê oficinas RJ2·*. Não
  mostramos oficinas de outras séries mesmo que pedagogicamente
  cabíveis. Decisão: melhor falsa-restrição que cross-série
  acidental.

- **Só último envio diagnosticado.** Não comparamos diagnósticos
  entre envios (não dá pra ver "lacuna em C5.001 melhorou ou piorou
  desde a última redação"). Comparação longitudinal entra na Fase 4.

- **Sem agregação de turma.** Professor não vê "quantos % da turma
  têm lacuna em C5.001". Heatmap da turma (média/contagem por
  descritor) é o entregável principal da Fase 4.

- **Metas determinísticas (não personalizadas).** Dicionário fixo
  descritor → frase. Aluno A e Aluno B com lacuna em C5.001 recebem
  a mesma meta. Personalização (LLM gera meta sob medida) custaria
  +$0.01-0.02 por redação e tem ROI duvidoso enquanto não validamos
  o impacto das metas determinísticas com cursinhos parceiros.

- **Sugestão pedagógica também é determinística** (mesmo descritor →
  mesma frase pra qualquer aluno). Pra primeiro draft é OK — meta-
  análise pedagógica pode personalizar depois quando tivermos
  dataset de validação humana.

## Pendências futuras (sub-meta C do Daniel)

Cards de lacuna podem ganhar ainda:

- **Link pra material de estudo específico do descritor** — capítulo
  do livro 1S/2S/3S, vídeo, exercício. Hoje só apontamos OFICINAS
  no sub-bloco 4 (granularidade competência); link granular por
  descritor exige catálogo de material que ainda não existe.

Fica registrado pra Fase 4 ou 5 — quando tiver catálogo de material
estudo mapeado por descritor, frontend renderiza chip clicável "📖
Ver material" no rodapé de cada card de lacuna.

## Tests

Backend (em `redato_backend/tests/diagnostico/`):

- `test_metas.py` (8): cobertura dicionário 40, estado vazio, cap
  MAX_METAS, dedup competência, render WhatsApp
- `test_sugestoes.py` (7): filtro série, dedup, max por lacuna,
  série sem oficinas (3S), ranking foco-antes
- `test_perfil_diagnostico_recente.py` (10): schema Pydantic,
  estrutura crítica do `_build_diagnostico_recente`, integração bot
  → metas_msg → `_build_messages_pos_correcao`

Total: 46 cenários no módulo diagnóstico (Fase 1+2+3 acumulado).
Suite global vai de 503 → 528.

Frontend: typecheck via `tsc --noEmit` limpo.

## Deploy checklist

Sem migration nova — Fase 3 é puramente leitura + render. O endpoint
`/perfil` continua compatível: campo `diagnostico_recente` é
opcional (default null).

1. Push aciona deploy automático Railway (backend) + Vercel/Railway
   (frontend)
2. Não precisa rodar `alembic upgrade head` (não há migration nova)
3. Não precisa setar nenhuma env var nova
4. Smoke após deploy:
   - Envio de teste no WhatsApp → aluno recebe correção + chunk
     extra com metas
   - Acessar `/turma/{id}/aluno/{id}` no portal → bloco Mapa
     Cognitivo aparece com heatmap colorido

Em caso de problema na Fase 3 especificamente:
- Diagnóstico continua sendo gerado (Fase 2 intacta)
- Pra desligar render de metas no WhatsApp: bug fix, não há flag
  específica (metas só aparecem se diagnóstico Fase 2 retornou OK,
  então rollback de Fase 2 desliga as duas)
- Pra esconder Mapa Cognitivo do professor: hot fix no frontend
  (passar `diagnostico_recente: null` no view component) ou
  desabilitar Fase 2 com `REDATO_DIAGNOSTICO_HABILITADO=false`
  (não persiste mais, próximos envios não terão Mapa)
