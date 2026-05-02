# Wireframes dos livros — sistema visual `mf-redato-page`

**Última atualização:** 2026-05-02 (3S migrado)

## TL;DR

Sistema visual padronizado pras Missões Finais avaliáveis pelo Redato.
Cada MF ocupa 1 página A4 dedicada (`.mf-redato-page`) com:

- **4 marcas fiduciais** nos cantos (`.mf-redato-fiducial.tl/.tr/.bl/.br`)
  — quadrados pretos de 10pt que o OCR usa pra detectar enquadramento
  e correção de perspectiva
- **Cards estruturais** opcionais (`.mf-redato-card` com `.lines-N`)
  — andaime que aluno preenche por etapa antes de escrever o texto
  corrido. Cada card tem `.tab` (rótulo numerado), `.hint` (instrução
  curta) e `.lines` (pauta)
- **Rodapé Redato** (`.mf-redato-bottom`) com selo + código da missão
  + instrução de foto. Variantes: `.foco`, `.completo`, `.diag`
- **Sem QR code** — placeholder xadrez foi descartado no design final
  (Daniel, 2026-05-02). CSS `.mf-redato-bottom-qr` não vai pro 2S.

## Status por livro

| Livro | Sistema | Status |
|---|---|---|
| `LIVRO_1S_PROF_v3_COMPLETO-checkpoints.html` | `mf-redato-page` completo (com QR) | ✅ Padrão de referência |
| `LIVRO_ATO_2S_PROF.html` | `mf-redato-page` completo (sem QR) | ✅ **Migrado em 2026-05-02 (commit feat(livros))** |
| `LIVRO_ATO_3S_PROF.html` | `mf-redato-page` completo (sem QR) | ✅ **Migrado em 2026-05-02** |

## Migração 2S → `mf-redato-page` (2026-05-02)

### CSS adicionado

Bloco `.mf-redato-bottom*` copiado do 1S em `LIVRO_ATO_2S_PROF.html:1457-1546`
(após as regras `.mf-redato-card.lines-N`, antes de `.mf-redato-step-marker`).
**Sem `.mf-redato-bottom-qr`.**

### 7 MFs avaliáveis migradas (mapping definitivo)

| Código | Modo (banco) | Cards estruturais | Texto corrido |
|---|---|---|---|
| **ATO2·OF01·MF** Diagnóstico | `completo_parcial` | Sem cards (texto autoavaliativo livre) | 8 `missao-writing-line` |
| **ATO2·OF04·MF** Citação (Foco C2) | `foco_c2` | 1·TESE (lines-2), 2·CITAÇÃO (lines-3), 3·ANÁLISE (lines-4) | 5 write-line |
| **ATO2·OF06·MF** Notícia→Artigo (Foco C2·C3) | `foco_c2` | 1·NOTÍCIA-BASE (lines-3), 2·TESE (lines-2), 3·ARGUMENTO (lines-4) | 5 write-line |
| **ATO2·OF07·MF** Tese e Argumentos (Foco C3) | `foco_c3` | 1·TESE (lines-2), 2·ARG 1 (lines-4), 3·ARG 2 (lines-4) | 5 write-line |
| **ATO2·OF09·MF** Expedição (Foco C3·C4) | `foco_c3` | 1·PROBLEMA (lines-3), 2·CAUSA (lines-3), 3·RAIZ (lines-3) | 5 write-line |
| **ATO2·OF12·MF** Leilão (Foco C5) | `foco_c5` | 1·PROBLEMA (lines-2), 2·PROPOSTA C/ 5 ELEMENTOS (lines-7) | 4 write-line |
| **ATO2·OF13·MF** Jogo Completo (5 comp) | `completo` | Sem cards (redação completa, texto corrido) | 17 write-line (D1+Conclusão consolidados) |

### Por que cards estruturais

O OCR + LLM precisam de **andaime visual** pra reconhecer estrutura
do texto manuscrito do aluno. Sem cards, o aluno pode:
- Pular partes da rubrica (ex.: escrever só argumento sem tese)
- Misturar elementos (citação no meio do argumento, sem separação)

Cards forçam o preenchimento por etapa + dão contexto visual pro
LLM que vai avaliar (cada card tem rótulo do que esperar).

### Por que sem cards em OF01 (Diagnóstico) e OF13 (Completo)

- **OF01 Diagnóstico:** texto autoavaliativo livre é parte do design
  pedagógico (não há "estrutura certa" pra autoavaliação). Manter
  formato aberto preserva a natureza diagnóstica.
- **OF13 Jogo Completo:** redação dissertativa completa não admite
  andaime — o aluno precisa decidir as quebras de parágrafo, a
  introdução não está num "card" separado. Cards quebrariam a fluência.
  Mantém-se como texto corrido em 17 linhas (D1 + Conclusão), com
  quebra indicada por pulo de linha.

### Por que fiduciais

`.mf-redato-fiducial` são quadrados pretos de 10pt nos 4 cantos da
página A4. Servem 2 propósitos no pipeline OCR:

1. **Detecção de enquadramento:** OCR reconhece os 4 cantos e calcula
   se a foto está reta ou inclinada. Se algum fiducial sumir do frame,
   pipeline rejeita e pede foto melhor (`quality_issues="foto_cortada"`).
2. **Correção de perspectiva:** mesmo com foto inclinada, dá pra
   computar transformação afim (4 pontos definem retângulo) e
   "endireitar" a imagem antes do OCR de texto.

Sem fiduciais, OCR depende de heurísticas frágeis (densidade de pixels
escuros nos cantos, detecção de bordas) que falham em fotos de baixa
qualidade.

### Por que sem QR

QR foi considerado mas descartado:

- Aluno já digita o código da missão (ex.: `ATO2·OF12·MF`) na hora
  de mandar a foto via WhatsApp. QR seria redundante.
- Layout fica mais limpo sem QR (rodapé compacto).
- O aluno não tem leitor de QR ativo no fluxo — câmera é só pra
  fotografar a redação dele, não pra escanear.

CSS `.mf-redato-bottom-qr` ainda existe no 1S (placeholder xadrez)
mas foi **omitido** ao migrar pro 2S.

## Migração 3S → `mf-redato-page` (2026-05-02)

### CSS adicionado

Bloco `.mf-redato-bottom*` copiado do 2S em
`LIVRO_ATO_3S_v8_PROF (1).html:~3345-3445` (após as regras
`.mf-redato-card.lines-N`, antes de `.mf-redato-step-marker`).
**Sem `.mf-redato-bottom-qr`.** Page-break preventivo aplicado:
`.mf-redato-page` recebeu `page-break-before: always`,
`page-break-after: avoid` e `page-break-inside: avoid`; `min-height: 277mm`
removido em `@media print`.

### 11 MFs avaliáveis migradas (mapping definitivo)

| Código | Modo (banco) | Cards estruturais | Texto corrido |
|---|---|---|---|
| **ATO3·OF01·MF** Diagnóstico | `completo_parcial` | 1 card único `lines-9` (autoavaliação metacognitiva) | — |
| **ATO3·OF03·MF** Dossiê: Repertório + Análise | `foco_c2` | 1·CONTEXTUALIZAÇÃO (lines-2), 2·DADO+REPERTÓRIO (lines-3), 3·AFETADOS (lines-2), 4·TESE (lines-2) | 5 write-line |
| **ATO3·OF04·MF** Dossiê: Tema + Problemática | `foco_c2` | 1·INTRODUÇÃO 4 elementos (lines-4), 2·ARGUMENTO 1 (lines-4) | 5 write-line |
| **ATO3·OF05·MF** Dossiê: Agentes + Proposta | `foco_c5` | 1·AGENTE+AÇÃO (lines-2), 2·MEIO (lines-2), 3·FINALIDADE (lines-2) | 5 write-line |
| **ATO3·OF06·MF** Dossiê: Proposta Completa | `foco_c5` | 1·PROBLEMA (lines-2), 2·PROPOSTA C/ 5 ELEMENTOS (lines-7) | 4 write-line |
| **ATO3·OF07·MF** Jogo do Corretor | `completo_parcial` | 1·ERROS PEGOS (lines-3), 2·CORREÇÕES APLICADAS (lines-4), 3·CHECKLIST PESSOAL (lines-3) | 4 write-line |
| **ATO3·OF09·MF** Simulado 1 (Saúde Mental) | `completo` | Sem cards (redação completa) | `redacao-sheet` 30 linhas numeradas |
| **ATO3·OF10·MF** Revisão pós-protocolo solo | `completo_parcial` | 1·SCANNER+DIAGNÓSTICO (lines-3), 2·SOLUÇÃO (lines-2), 3·REESCRITA (lines-5) | 4 write-line |
| **ATO3·OF11·MF** Simulado 2 + IA (Inclusão Digital, V2) | `completo` | Sem cards (V2 é a avaliada — V1 fica como rascunho fora do `.mf-redato-page`) | `redacao-sheet` 30 linhas numeradas |
| **ATO3·OF14·MF** Simulado Final 1 (Igualdade de Gênero) | `completo` | Sem cards | `redacao-sheet` 30 linhas numeradas |
| **ATO3·OF15·MF** Simulado Final 2 + Fechamento (Preservação Ambiental) | `completo` | Sem cards | `redacao-sheet` 30 linhas numeradas |

### Por que cards no Dossiê (OF03–OF06) e na revisão solo (OF10)

Mesma lógica do 2S — andaime visual + pedagógico que força preenchimento
por etapa antes do texto corrido:
- **OF03** força explorar contextualização → repertório → afetados → tese
  separadamente (4 cards = 4 elementos canônicos da introdução ENEM)
- **OF04** consolida em 2 cards (introdução completa + 1º desenvolvimento)
- **OF05** decompõe a proposta em AGENTE+AÇÃO / MEIO / FINALIDADE (3
  cards = núcleos da C5)
- **OF06** valida proposta completa com 5 elementos num único card grande
  `lines-7` (1·PROBLEMA + 2·PROPOSTA)
- **OF10** consolida os 5 passos do protocolo de revisão solo em 3 cards
  (SCANNER+DIAG / SOLUÇÃO / REESCRITA) + texto corrido pra continuar
  reescrita e validar resultado

### Por que sem cards em OF01 (Diagnóstico) e nos 4 Simulados (OF09, OF11, OF14, OF15)

- **OF01 Diagnóstico:** mesmo argumento do 2S. Mas no 3S optou-se por 1
  card único `lines-9` (em vez de 8 missao-writing-line do 2S) com hint
  metacognitivo explícito ("onde estou hoje, qual competência é minha
  maior lacuna, qual meta concreta pra o ano"). Mantém abertura
  pedagógica + dá enquadramento visual.
- **OF09/OF11/OF14/OF15 Simulados:** redação dissertativa completa
  (formato ENEM, 30 linhas numeradas) não admite andaime — aluno
  decide quebras de parágrafo, e o `redacao-sheet` com `rl-num` dá a
  estrutura visual já consagrada. `mf-redato-page` envolve o
  `redacao-sheet` adicionando fiduciais + rodapé `.completo`. **OF11
  exceção:** tem V1 (rascunho) + V2 (após análise IA); só V2 vira
  `mf-redato-page` (V2 é a avaliada por OCR; V1 fica fora como folha
  de rascunho).

### Por que sem migração em OF02, OF08, OF12, OF13

Mantidos com sistema legacy `.redato-bottom`:
- **OF02** Conectivos + Coesão — chat-only sem produção avaliável
- **OF08** Análise de Erros Comuns — depende do modo `foco_c1` (adiado)
- **OF12, OF13** Jogos de Redação Completo — usam sistema de cartas
  argumentativas 3S (slots A/AÇ/ME/F) ainda não modelado no banco

Ver `oficinas_3s_status.md` pras pendências detalhadas.

### Pequenas variações vs 2S

- **`redacao-sheet` dentro de `.mf-redato-page`** (Simulados): 3S
  preserva a folha ENEM canônica (30 linhas numeradas com `rl-num`)
  envolvida pela página fiducial. 2S não tinha simulados — foi a
  primeira vez que essa combinação apareceu.
- **OF01 com 1 card lines-9** (em vez de 8 missao-writing-line do 2S
  Diagnóstico): mantém abertura mas acrescenta um único card-âncora
  com hint metacognitivo pra ajudar OCR a delimitar o texto.
