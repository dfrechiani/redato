# Wireframes dos livros — sistema visual `mf-redato-page`

**Última atualização:** 2026-05-02

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
| `LIVRO_ATO_3S_v8_PROF (1).html` | Sistema antigo `.redato-bottom` | ⏳ **Pendente** — próxima sessão |

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

## Próxima sessão (3S)

Aplicar mesmo sistema no `LIVRO_ATO_3S_v8_PROF (1).html`. Considerar:

- 11 oficinas seedadas em `migrations/versions/j0a1b2c3d4e5_seed_missoes_3s`
  (ver `oficinas_3s_status.md`)
- 4 simulados (OF09, OF11, OF14, OF15) usam modo `completo` — sem
  cards, igual OF13 do 2S
- Dossiê (OF03, OF04, OF05, OF06) provavelmente leva 3 cards cada
  (similar ao Foco C2 do 2S)
- Jogo do Corretor (OF07) — depende do conteúdo pedagógico do livro
- Revisão Cooperativa (OF10) — definir cards baseado no fluxo
- OF02 (chat-only), OF08 (foco_c1 adiado), OF12/OF13 (cartas
  argumentativas pendentes) — fora do escopo de cards
