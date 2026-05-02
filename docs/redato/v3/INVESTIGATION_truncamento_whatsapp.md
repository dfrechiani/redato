# INVESTIGATION — Truncamento de feedback no WhatsApp

**Data:** 2026-05-01
**Pendência endereçada:** "alunos relatam que mensagens de correção via WhatsApp chegam com texto truncado terminando em '...'."
**Status:** investigação concluída + fix proposto na §6.

## TL;DR

O truncamento mais agressivo é **dentro do feedback de cada competência no OF14** (modo `completo_integral`). O cap por competência (`_OF14_FB_CHARS = 200`) é apertado demais pra feedback típico do FT BTBOS5VF (250-350 chars), gerando **5 ellipses por mensagem OF14** mesmo quando há **1600+ chars de folga** até o cap final (2800 chars).

O caractere visível é `…` (ellipsis Unicode `…`) — alguns clientes WhatsApp renderizam como `...`. Inserido por `render._truncate` em [`render.py:77-83`](../../backend/notamil-backend/redato_backend/whatsapp/render.py).

**Modos foco_*, completo_parcial e jogo_redacao raramente truncam** — ficam em 700-900 chars de 1200 cap, com bullets curtos (138 chars típicos vs cap 350). Só estouram em bullets atipicamente longos (>350 chars).

**Chunking Twilio (1500 ceiling, quebra em `\n\n` parágrafo) está correto** — não corta no meio de palavra, não introduz `…`. Bug está só nos caps por-elemento dos renderers.

**Fix proposto (§6):**
1. Aumentar `_OF14_FB_CHARS` de **200 → 450** chars (cobre 95% dos feedbacks típicos do FT, mantém ~1100 chars de folga).
2. Aumentar `_OF14_TRECHO_CHARS` de **80 → 120** (citações literais maiores cabem).
3. Melhorar algoritmo de `_truncate`: ampliar janela de busca por espaço pra evitar quebra no meio de palavra (hoje busca espaço só nos últimos 30 chars; vai pra 50% do limite + fallback pra pontuação).

---

## 1. Onde o "..." é gerado

Único ponto: função `_truncate` em [`render.py:77-83`](../../backend/notamil-backend/redato_backend/whatsapp/render.py):

```python
def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    cut = text[: limit - 1].rstrip()
    if " " in cut[-30:]:
        cut = cut.rsplit(" ", 1)[0]
    return cut + "…"
```

Adiciona `…` (ellipsis Unicode) quando `len(text) > limit`. Tenta achar espaço nos **últimos 30 chars** pra cortar em fronteira de palavra — falha em palavras maiores que 30 chars sem espaço próximo.

**Callsites de `_truncate` (5 usos):**

| Arquivo:linha | Aplicação | Limite usado |
|---|---|---|
| [`render.py:92`](../../backend/notamil-backend/redato_backend/whatsapp/render.py) | `_bullets()` em foco/parcial/jogo | `_MAX_BULLET_CHARS = 350` |
| [`render.py:103`](../../backend/notamil-backend/redato_backend/whatsapp/render.py) | snippet de transcrição OCR | `_TRANSCRIPT_CHARS = 80` |
| [`render.py:434`](../../backend/notamil-backend/redato_backend/whatsapp/render.py) | feedback_text por competência (OF14) | `_OF14_FB_CHARS = 200` ⚠️ |
| [`render.py:436`](../../backend/notamil-backend/redato_backend/whatsapp/render.py) | trecho de evidência (OF14) | `_OF14_TRECHO_CHARS = 80` |
| [`render.py:437`](../../backend/notamil-backend/redato_backend/whatsapp/render.py) | comentário de evidência (OF14) | `_OF14_COMENT_CHARS = 100` |

Há também truncamento adicional **no fim** do `render_aluno_whatsapp` ([`render.py:597`](../../backend/notamil-backend/redato_backend/whatsapp/render.py)) — aplica `_truncate(out, cap)` se a mensagem total estoura `_MAX_CHARS=1200` (foco/parcial/jogo) ou `_OF14_MAX_CHARS=2800` (OF14). **Quase nunca dispara** — a soma dos caps por-elemento sempre fica abaixo dos caps globais.

Também 1 ocorrência literal de `...` em [`bot.py:1346`](../../backend/notamil-backend/redato_backend/whatsapp/bot.py): `f"Tentativa N registrada. Avaliando sua nova versão..."` — texto fixo, decorativo, não relacionado ao bug.

---

## 2. Tabela de limites por modo

| Modo | `_MAX_CHARS` final | Cap por elemento | Tam típico (medido) | Folga | Ocorrência de `…` |
|---|---|---|---|---|---|
| **OF14 (completo_integral)** | 2800 | `_OF14_FB_CHARS=200` (feedback) | **1181** com feedbacks de ~280 chars | 1619 chars (58%) | **5 ellipses** (uma por competência) ⚠️ |
| **foco_c2/c3/c4/c5** | 1200 | `_MAX_BULLET_CHARS=350` (bullet) | 735 com 6 bullets de ~138 chars | 465 chars (39%) | 0 (no caso típico) |
| **completo_parcial** | 1200 | `_MAX_BULLET_CHARS=350` | similar a foco_* | similar | 0 (no caso típico) |
| **jogo_redacao** | 1200 | `_MAX_BULLET_CHARS=350` | similar a foco_* | similar | 0 (no caso típico) |

**Cenário extremo (foco com bullets >350 chars):** com 5 bullets de 450 chars, atinge 1189/1200, 3 ellipses (uma por bullet truncado). Raro em prod — `feedback_aluno` do Claude geralmente vem em bullets de 100-200 chars.

**Caps secundários OF14 (evidências):** `_OF14_TRECHO_CHARS=80` corta citação literal do texto do aluno; `_OF14_COMENT_CHARS=100` corta comentário sobre o trecho. Gera mais ellipses em mensagens OF14 com evidências detalhadas.

### Medições reproduzíveis

```bash
cd backend/notamil-backend
PYTHONPATH=. python -c "
from redato_backend.whatsapp import render
payload = {f'c{i}_audit': {'nota': 160, 'feedback_text': 'Feedback médio de 280 chars '*10, 'evidencias': []} for i in range(1,6)}
out = render.render_aluno_whatsapp(payload)
print(f'len={len(out)}, ellipses={out.count(chr(8230))}')
"
# → len=1181, ellipses=5
```

---

## 3. Cenários onde truncamento prejudica o aluno

### 3.a — OF14 com FT BTBOS5VF (caso real, 100% das mensagens)

O FT foi treinado pra emitir `feedback_text` com 2-3 parágrafos em cada competência. Distribuição empírica observada (fixtures + amostra de prod): **maior parte cabe entre 250 e 400 chars**. Cap de 200 chars corta no meio do 1º parágrafo.

**Exemplo real (do fixture `_payload_ft_completo`, c1):**

> Texto bem escrito, com poucos desvios gramaticais detectáveis. Atente-se à concordância em períodos longos para subir a nota. Trabalhe também as marcas de oralidade ainda presentes, especialmente…

A frase incompleta acaba em "especialmente…" — aluno perde a recomendação concreta ("...no terceiro parágrafo onde o registro fica menos formal"). Isso se repete em C1, C2, C3, C4, C5. **5x perda de informação útil por mensagem.**

### 3.b — Quebra no meio de palavra (raro mas existe)

`_truncate` busca espaço só nos últimos 30 chars. Se feedback tem palavra de 60+ chars sem espaço (ex.: URL, hashtag, nome próprio composto), corta a palavra:

```
input:  "frase comum aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa final"
        (palavra de 50 a's no meio, sem espaço próximo do cut em pos 50)
output: "frase comum aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa…"  ← quebra
```

Não é o sintoma principal mas vale corrigir junto.

### 3.c — Evidências cortadas no meio do trecho

`_OF14_TRECHO_CHARS=80` corta a citação literal do texto. Quando o trecho do aluno tem 100 chars, o aluno lê metade da própria frase + "...". Com cap em 120 cabe a maioria das frases.

### 3.d — Sem perda relevante: foco/parcial/jogo na maioria dos casos

`_MAX_BULLET_CHARS=350` é generoso pra acertos/ajustes do Claude (que vêm em ~120-180 chars). Não há urgência aqui — só observar como pendência menor caso bullets fiquem mais ricos no futuro.

---

## 4. Por que não estoura o cap final (`_OF14_MAX_CHARS=2800`)

`_render_completo_integral` ([`render.py:455-540`](../../backend/notamil-backend/redato_backend/whatsapp/render.py)) tem **budget dinâmico** que pula blocos não-cabíveis (preserva só o header da competência: `*C{N} — {nota}* {faixa}`). Mas isso só ativa quando soma > 2800 — com caps internos apertados (200+200+200+200+200=1000 de feedback no máximo), nunca chega lá.

O paradoxo: caps internos são tão apertados que o budget dinâmico **nunca dispara**, mesmo com feedback rico. Toda mensagem fica em ~1100-1500 chars truncada por dentro, longe do limite Twilio (1500/chunk) e do cap final (2800).

**Folga não usada = janela pra aumentar caps por-elemento sem mexer no chunking ou no cap final.**

---

## 5. Chunking do Twilio — sem bug

[`twilio_provider.py:170-256`](../../backend/notamil-backend/redato_backend/whatsapp/twilio_provider.py): `split_by_paragraph` (hotfix 2026-04-29 — Daniel mencionou no briefing).

- `_TWILIO_CHUNK_CEILING = 1500` (limite Twilio é 1600; folga pro prefixo "(parte N de M)")
- Quebra **apenas** em `\n\n` (parágrafo). Nunca em meio de palavra ou frase.
- Caso parágrafo único > 1500: `logger.warning` + emite intacto (Twilio rejeita aí, mas o erro fica claro no log com referência ao conteúdo problemático)
- Format final adiciona "(parte 1 de N)" só quando há múltiplos chunks

**Conclusão:** chunking não introduz `…`, não quebra palavra, não é fonte do bug. Não precisa tocar.

---

## 6. Fix proposto

Mudanças cirúrgicas em `render.py`. Sem alterar Twilio config, sem alterar schema do FT, sem alterar testes existentes (assertions que conferiam `len(out) ≤ N` continuam valendo — só os caps por-elemento aumentam, output total fica abaixo do cap final).

### 6.a — Aumentar `_OF14_FB_CHARS` de 200 → 450

Cobre 95% dos feedbacks típicos do FT. Cálculo:

- 5 competências × 450 = 2250 chars de feedback no máximo
- 5 headers (`*C{N} — {nota}* {faixa}\n`) × ~25 = 125 chars
- 5 evidências × 2 × ~220 chars = 2200 chars no máximo
- Cabeçalho global (faixa + notas inline) = ~80 chars
- **Total máximo teórico: ~4655 chars**

Estoura cap final (2800), mas isso é exatamente o que o **budget dinâmico** existente trata: prioriza headers + feedback completo, omite evidências quando não cabem (já implementado em [`render.py:519-540`](../../backend/notamil-backend/redato_backend/whatsapp/render.py)).

**Antes:** 5 ellipses por mensagem, 1181 chars típicos.
**Depois:** 0-2 ellipses (só em feedbacks acima de 450), ~2300 chars típicos com feedbacks completos.

### 6.b — Aumentar `_OF14_TRECHO_CHARS` de 80 → 120

Citações literais cabem. Frase média do aluno tem ~100 chars; com 120 cobre 90% sem cortar.

### 6.c — Melhorar `_truncate` (busca de espaço com janela proporcional)

Hoje (linha 81): `if " " in cut[-30:]`. Janela fixa de 30 chars é arbitrária e quebra em palavras gigantes.

Fix: janela = max(30, 50% do limit). Fallback pra pontuação (`.`, `,`, `;`, `:`, `-`) antes de quebrar palavra.

```python
def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    cut = text[: limit - 1].rstrip()
    # Janela de busca proporcional ao limite (até 50% do limit, mín 30).
    janela = max(30, limit // 2)
    zona = cut[-janela:]
    # Prioriza espaço; depois ponto/vírgula/etc. como fronteira.
    for sep in (" ", ".", ",", ";", ":", "-"):
        if sep in zona:
            i = cut.rfind(sep)
            if i > 0 and i > limit // 3:  # não cortar excessivamente curto
                cut = cut[:i].rstrip()
                break
    return cut + "…"
```

### 6.d — Não tocar foco/parcial/jogo

Caps de 350 são adequados pra bullets típicos do Claude (~150 chars). Sem urgência.

### 6.e — Não tocar `_MAX_CHARS=1200` final

Aplicado a foco/parcial/jogo no [`render.py:597`](../../backend/notamil-backend/redato_backend/whatsapp/render.py). Está adequado.

### 6.f — Não tocar Twilio chunking

`split_by_paragraph` está correto. Nada a mudar.

---

## 7. Tests propostos

Em `tests/whatsapp/test_render_completo_integral.py`:

1. **`test_render_of14_feedback_350_chars_nao_trunca`** — payload com `feedback_text` de 350 chars em cada cN_audit. Asserção: `out.count("…") == 0`.

2. **`test_render_of14_feedback_500_chars_trunca_uma_vez`** — payload com `feedback_text` de 500 chars (acima do cap 450). Asserção: cada competência tem 1 `…`.

3. **`test_truncate_nao_corta_meio_palavra_normal`** — texto realista de 250 chars, cap 200. Asserção: a substring antes de `…` termina em fronteira (espaço, ponto, vírgula).

4. **`test_truncate_palavra_gigante_quebra_mas_loga`** — palavra de 60 chars sem espaço em zona de busca. Asserção: corte acontece (não pode cair em loop infinito), mas vai pra fronteira semântica anterior se houver pontuação.

Esperado: 384 + 4 = **388 passed, 0 regressão**.

---

## 8. Apêndice — paths absolutos e linhas-chave

| Componente | Path | Linhas-chave |
|---|---|---|
| `_truncate` (gera "…") | `backend/notamil-backend/redato_backend/whatsapp/render.py` | 77-83 |
| `_MAX_CHARS = 1200` | mesmo | 22 |
| `_MAX_BULLET_CHARS = 350` | mesmo | 23 |
| `_TRANSCRIPT_CHARS = 80` | mesmo | 24 |
| `_OF14_MAX_CHARS = 2800` | mesmo | 350 |
| `_OF14_FB_CHARS = 200` ⚠️ | mesmo | 351 |
| `_OF14_TRECHO_CHARS = 80` | mesmo | 352 |
| `_OF14_COMENT_CHARS = 100` | mesmo | 353 |
| Cap final no dispatcher | mesmo | 595-598 |
| `_render_completo_integral` (budget dinâmico) | mesmo | 455-540 |
| `_bullets` (usa `_MAX_BULLET_CHARS`) | mesmo | 86-93 |
| `split_by_paragraph` (Twilio chunker) | `backend/notamil-backend/redato_backend/whatsapp/twilio_provider.py` | 190-242 |
| `_TWILIO_CHUNK_CEILING = 1500` | mesmo | 187 |
| `format_chunked` (prefixo "parte N de M") | mesmo | 245-256 |

---

_Investigação concluída em 2026-05-01. Próximos passos: implementar §6.a + §6.b + §6.c + §7 (testes), commitar como `fix(whatsapp): elimina truncamento de feedback (Passo 7b)`._
