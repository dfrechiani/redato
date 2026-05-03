# HOWTO — Perfil do aluno na turma

**Atualizado:** 2026-05-03 · M9.7

## O que é

Página de drill-down do aluno dentro da turma. Permite ao professor
(ou coordenador da escola) ver, num só lugar, o histórico completo de
envios de um aluno + métricas agregadas (nota média, tendência,
competência forte/fraca, envios com problema).

URL no portal:
`/turma/{turma_id}/aluno/{aluno_id}`

Endpoint backend:
`GET /portal/turmas/{turma_id}/alunos/{aluno_turma_id}/perfil`

## Como acessar

1. Entre numa turma pelo portal (`/turma/{turma_id}`).
2. Expanda a seção **"Alunos cadastrados ({N})"**.
3. Clique no nome do aluno (ou no chevron `›` à direita do nome).

O botão **"Remover"** continua à direita, separado, não abre o perfil.

Quem tem acesso (mesma regra do detalhe da turma):
- Professor responsável pela turma.
- Coordenador da escola da turma.

Outro professor da mesma escola: **403 Forbidden**.

## Layout

A página tem 4 blocos top-down:

### 1. Identificação

- Nome do aluno + badge `ATIVO`/`DESVINCULADO`.
- Telefone (mascarado: últimos 3 dígitos viram `***`).
- Data em que o aluno entrou na turma (campo `vinculado_em`).

### 2. Stats em cards

Quatro cards (grid 4 colunas no desktop, 2 no mobile):

| Card | Conteúdo |
|---|---|
| **Envios** | Total + breakdown ("X com nota · Y com problema") |
| **Nota média** | Valor + tendência (↑/↓/= com cor) |
| **Ponto forte** | Competência (C1..C5) + média (verde) |
| **Ponto fraco** | Competência + média (laranja) |

Abaixo: barras compactas C1-C5 com valores absolutos
(escala 0–200 ENEM por competência).

### 3. Gráfico de evolução

Line chart SVG (componente `EvolucaoChart`, sem dependência externa):
X = data, Y = nota total. Hover mostra data + atividade + nota.

- yMax = 200 se TODO envio com nota é foco_*; senão 1000.
- Mostra TODOS os envios (sem filtro por período no MVP).
- Substituído por mensagem **"Precisa de pelo menos 2 envios pra ver
  evolução"** se há menos de 2 pontos plotáveis.

### 4. Tabela de envios

Lista ordenada **desc** (mais recente em cima). Cada linha:
- Atividade (código `RJ#·OF##·MF` + título + modo)
- Data
- Nota total (com flag `problema` se o pipeline falhou)
- "Ver feedback" — abre detalhe individual existente
  (`/atividade/{id}/aluno/{aluno_id}`)
- "Reprocessar avaliação" — só aparece se `tem_problema=true`.
  Chama `POST /portal/envios/{id}/reprocessar` (endpoint M9.6).

## Como interpretar a tendência

Calculada comparando média das **últimas 3 notas** com média das **3
anteriores**:

| Diferença | Tendência | Cor |
|---|---|---|
| > +30 | `subindo` ↑ | verde (lime) |
| < -30 | `caindo` ↓ | vermelho (danger) |
| entre -30 e +30 | `estavel` = | cinza |

**Limitação importante:** se o aluno tem **menos de 6 envios com nota
válida**, retorna `dados_insuficientes`. Motivo: ruído inerente da
correção (variação ±20-30 pts por redação) domina diferenças reais
em amostras pequenas. 6 envios = mínimo pra ter prev3 + last3 sem
overlap.

Envios sem nota (problema de pipeline, não corrigidos ainda) são
ignorados no cálculo.

## Como interpretar ponto forte / fraco

São as competências com **maior** e **menor média** entre as cinco
(C1 a C5), considerando apenas competências que foram avaliadas em
pelo menos um envio.

Cobertura por modo:
- **Foco_c{N}** (foco_c2, foco_c3, etc.): contribui apenas pra C{N}.
  Aluno que só fez foco_c2 → médias_cN tem só `c2`; outras = null.
- **Completo** (OF14): contribui pras 5 competências.
- **Completo_parcial** (OF13): pras competências preenchidas
  (c5 pode vir como `"não_aplicável"` e é pulado).

Se nenhuma competência tem dados → `ponto_forte=null` e
`ponto_fraco=null`.

## Quando o card "Ponto forte" e "Ponto fraco" mostram a MESMA competência

Quando o aluno tem todas as suas notas em uma única competência (ex.: 3
envios foco_c2). Nesse caso, c2 é simultaneamente max e min entre as
competências preenchidas. Não é bug — é falta de variação.

## Detecção de envios com problema

Um envio é flagado `tem_problema=true` se:
1. `redato_output` é null (interaction sem output gravado), **ou**
2. `redato_output` contém a key `error` (caminho oficial do
   reprocessar quando pipeline falha — preserva a mensagem de erro
   em vez de jogar fora), **ou**
3. `redato_output` existe mas `nota_total` é None (parser não
   conseguiu extrair — reprocessar pode ressuscitar).

Esses são candidatos pro botão **Reprocessar avaliação** que aparece
inline na linha do envio. Reprocessar usa o texto OCR persistido —
não pede foto nova ao aluno.

Se o problema for no texto OCR (inelegível, fora de quadro,
borradíssimo), reprocessar não resolve — peça pro aluno reenviar via
WhatsApp.

## Limitações conhecidas

- **Tendência precisa de 6+ envios.** Não dá pra evitar — minimum
  meaningful sample. Aluno com 3-5 envios verá `dados_insuficientes`.
- **Sem filtro por período.** Mostra todos os envios. Pra recortes
  (ex.: só 1º bimestre), use o PDF de evolução exportado em
  `/turma/{turma_id}/aluno/{aluno_id}/evolucao` (botão "Exportar
  evolução PDF" tem campos de período).
- **Tentativas múltiplas** (M9.6): só a tentativa de maior `tentativa_n`
  por (atividade, aluno) entra nas stats. Tentativas anteriores são
  acessíveis na tela individual (`/atividade/{id}/aluno/{aluno_id}`).
- **Modo de competências mistos:** se o aluno fez algumas missões em
  foco e outras em completo, médias_cN agrega TUDO (foco_c2 + completo
  ambos contribuem pra c2). É a interpretação mais útil pra o
  professor — comparar a evolução da competência entre formatos.

## Tests

Backend: `redato_backend/tests/portal/test_perfil_aluno.py` — 16
cenários (schemas + helpers de tendência/médias/problema/feedback +
estrutura crítica do endpoint via `inspect.getsource`).

Frontend: typecheck via `tsc --noEmit` no CI; sem testes unitários
de componente (alinhado com convenção do `redato_frontend` —
testes E2E ficam em `tests-e2e/` quando vier o fluxo completo).
