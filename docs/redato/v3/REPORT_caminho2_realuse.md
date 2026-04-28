# Caminho 2 — Relatório de uso real (Twilio Sandbox)

**Status:** Fase A concluída em sandbox. Fase B+ iniciada nesta sessão.
**Data:** 2026-04-27.
**Aparelho:** iPhone do Daniel.
**Operadora / rede:** 4G/Wi-Fi alternados.
**Phone do tester:** `+556196668856`.

## Índice

- [1. Setup](#1-setup)
- [2. Bugs descobertos em uso real](#2-bugs-descobertos-em-uso-real)
- [3. Métricas observadas em uso real](#3-métricas-observadas-em-uso-real)
- [4. Achados que NÃO foram corrigidos (Fase B+)](#4-achados-que-não-foram-corrigidos-fase-b)
- [5. Decisões tomadas pra Fase B+](#5-decisões-tomadas-pra-fase-b)
- [6. Recomendações pra produção](#6-recomendações-pra-produção)
- [7. Próximo passo](#7-próximo-passo)
- [Apêndice — checklist do que NÃO foi testado](#apêndice--checklist-do-que-não-foi-testado)

---

## 1. Setup

### Twilio Sandbox
- **Account SID** + **Auth Token** copiados do console Twilio para
  `backend/notamil-backend/.env`.
- Número Sandbox público da Twilio: `+1 415 523 8886`.
- Código de ativação enviado do celular: `join organized-enjoy`.
- Account confirmado como `Trial`, `active` via API.

### Webhook receiver
- FastAPI standalone em
  [`redato_backend/whatsapp/app.py`](../../backend/notamil-backend/redato_backend/whatsapp/app.py)
  + router em
  [`webhook.py`](../../backend/notamil-backend/redato_backend/whatsapp/webhook.py).
- Validação `X-Twilio-Signature` ON em produção (configurable via
  `TWILIO_VALIDATE_SIGNATURE`).
- Pipeline em background thread → libera o 200 do POST antes do
  timeout de 15s da Twilio.

### Túnel público
- ngrok `3.38.0` rodando local em `:8090`.
- Ngrok exigiu account auth no plano gratuito (instalado via Homebrew).
- URL pública apontada no console Twilio (`/twilio/webhook`).

### Variáveis de ambiente operacionais
```
ANTHROPIC_API_KEY=sk-ant-...
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...                      # rotacionar pós-teste!
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886
TWILIO_VALIDATE_SIGNATURE=1
REDATO_DEV_OFFLINE=1
REDATO_SCHEMA_FLAT=1
REDATO_CLAUDE_MODEL=claude-opus-4-7        # OF14 only
REDATO_MISSION_MODEL=                      # vazio = default por modo
```

### Tempo total de setup
- Código pré-pronto (sessão anterior): instantâneo.
- Setup Twilio + ngrok + webhook: **~25 minutos** (incluindo update
  do ngrok 3.14 → 3.38, que estava deprecated).
- Primeira mensagem de cadastro chegou no celular em ~2 min após
  o `join organized-enjoy`.

---

## 2. Bugs descobertos em uso real

Cada bug aqui foi descoberto **enviando mensagens reais do celular** —
nenhum apareceu nos smoke tests sintéticos. Todos resolvidos durante a
sessão.

### Bug 1 — FSM loop quando o aluno manda código primeiro

**Sintoma:** aluno mandava `RJ1OF10MF` → bot pedia foto. Aluno mandava
foto → bot pedia código de novo. Loop infinito.

**Causa raiz:**
[`bot.py:_handle_ready_or_awaiting`](../../backend/notamil-backend/redato_backend/whatsapp/bot.py)
estava comparando `estado == AWAITING_FOTO` com **igualdade exata**.
Mas `_set_pending_missao` salvava `f"{AWAITING_FOTO}|{missao_canon}"`
(ex.: `"AWAITING_FOTO|RJ1·OF10·MF"`). A comparação falhava, e a foto
caía no fluxo "sem missão pendente" → pedia código.

**Fix:** trocar `estado == AWAITING_FOTO` por
`estado.startswith(AWAITING_FOTO)`.

**Validação:** smoke offline com payload Twilio fake;
`test_webhook_routing_first_message` passa.

---

### Bug 2 — Autocorretor iPhone troca `O` por `0`

**Sintoma:** aluno digitava `RJ1OF10MF` no WhatsApp do iPhone. O
autocorretor convertia silenciosamente pra `RJ10F10MF` (a letra `O`
virava o número `0`). Bot rejeitava como código inválido.

**Causa raiz:** regex `_MISSAO_RE` exigia `OF\s*\d{2}`. Com `0F`, não
casava.

**Fix:** adicionado padrão alternativo `_MISSAO_RE_AUTOCORRECT`
em [`bot.py`](../../backend/notamil-backend/redato_backend/whatsapp/bot.py):
`RJ(\d)0F(\d{2})\s*[\W_]*\s*MF`. Trata o `0F` como se fosse `OF`.

**Validação:**
```
'RJ1OF10MF'   → RJ1·OF10·MF
'RJ10F10MF'   → RJ1·OF10·MF  (autocorretor, agora aceito)
'RJOF10MF'    → None         (faltou dígito, rejeita)
```

---

### Bug 3 — Foto chega rotacionada (WhatsApp remove EXIF)

**Sintoma:** redação fotografada com a folha em paisagem chegava
"deitada" pro Claude, e a transcrição saía corrompida (palavras
inventadas, alucinação grave).

**Causa raiz:** WhatsApp e Twilio removem tag EXIF Orientation por
privacidade. `ImageOps.exif_transpose` não tem o que normalizar.

**Fix em camadas:**
1. **Detector de rotação via Claude.** Inicialmente Haiku 4.5 (que
   errou na 1ª foto real, dizendo 90° quando era 270°). Trocado por
   **Sonnet 4.6** (mais confiável; user pediu explicitamente).
2. **Fallback de rotação oposta.** Se a transcrição depois da rotação
   detectada tem >3 `[ilegível]`, testa `rot+180°` (oposta) e `0°`,
   pega a com menos `[ilegível]`. Custo: 1-3 chamadas Sonnet vs 1 no
   caso feliz.
3. **EXIF transpose preservado** caso tag exista (fotos de outros apps).

**Validação:** foto que falhou (`20260427_140709_*.jpg`) —
detecção+fallback transcreveu 0 `[ilegível]`, texto coerente "Diante
da fome no Brasil…".

---

### Bug 4 — Threshold de blur calibrado em laboratório

**Sintoma:** foto HD válida sendo rejeitada como "borrada". Métrica
real: brightness 150 (OK), `laplacian_var=71`, threshold era 100.

**Causa raiz:** threshold `MIN_LAPLACIAN_VAR=100` veio de bibliografia
(pyimagesearch). Em uso real (papel pautado + caneta + compressão
WhatsApp) a variance fica ~70-90.

**Fix:** baixado pra `40`
em [`ocr.py`](../../backend/notamil-backend/redato_backend/whatsapp/ocr.py).
Foto borrada de verdade (mão tremida) cai abaixo de 30, então 40 é piso
seguro. Override via env `REDATO_OCR_MIN_LAPLACIAN_VAR`.

---

### Bug 5 — Foto antes do código (foto órfã)

**Sintoma:** aluno mandava foto sem caption, depois mandava código
solto. Bot ignorava a foto e pedia foto de novo.

**Causa raiz:** o branch "foto sem missão sem pending" descartava a
foto silenciosamente.

**Fix:** novo estado `AWAITING_CODIGO|<foto_path>` que guarda a foto.
Quando o código chega, bot pega a foto pendente e processa.

**Validação:** fluxos suportados:
- foto + código (mesma msg) ✓
- código → foto ✓
- foto → código ✓ (novo)

---

### Bug 6 — Faixas qualitativas informais demais

**Sintoma:** user reclamou de tom ("ok, dá pra subir" soava debochado).

**Fix:** em [`render.py`](../../backend/notamil-backend/redato_backend/whatsapp/render.py),
trocadas as faixas por terminologia formal:

| Nota | Antes | Agora |
|---|---|---|
| 200 | excelente | excelente |
| 160 | muito boa | muito boa |
| 120 | ok, dá pra subir | regular |
| 80 | em desenvolvimento | em desenvolvimento |
| 40 | precisa atenção | insuficiente |
| 0 | ainda não pegou a estrutura | abaixo do esperado |

---

### Bug 7 — Foto duplicada não detectada

**Sintoma:** mesma foto enviada 2× → notas diferentes (80 vs 40), bot
processava ambas como novas redações.

**Causa raiz:** detector usava SHA256 dos bytes. WhatsApp/Twilio
**re-encoda** a imagem em cada upload (mesmo conteúdo visual, bytes
diferentes). SHA256 detectava 0 duplicatas em uso real. Confirmado nos
hashes de id=9 e id=10 (mesma foto pra mim, SHA256 distintos).

**Fix:** trocado por **dHash perceptual** (8x8 = 64 bits hex).
Comparação por Hamming distance ≤ 5. Validei em laboratório:

| Variante | Hamming |
|---|---:|
| Mesma foto, JPEG q=90 | 0 |
| Mesma foto, JPEG q=70 | 0 |
| Mesma foto, JPEG q=50 | 0 |
| Mesma foto, brilho +5% | 1 |
| Foto diferente | 42 |

**Resultado em uso real:** depois do fix, reenvio da mesma foto cai no
prompt interativo `1️⃣ Reenviar feedback / 2️⃣ Reavaliar`. Custo zero
em API quando aluno escolhe `1`.

---

### Bug 8 — Variância de nota entre runs (mesma redação)

Este foi o bug de maior impacto estrutural da sessão. Vale registrar a
narrativa completa, não só o fix, porque a **lição que ele entrega
orienta arquitetura futura**.

#### Como descobrimos
Não apareceu em smoke sintético. Apareceu quando o user (Daniel)
mandou a mesma redação duas vezes do celular dele e recebeu nota 80
na primeira e 40 na segunda. Caso documentado:

| ID | rubrica REJ scores | Média | LLM emitiu |
|---|---|---|---|
| 9  | `{conclusao:42, premissa:38, exemplo:15, fluencia:68}` | 40.75 | **80** |
| 10 | `{conclusao:38, premissa:32, exemplo:15, fluencia:72}` | 39.25 | **40** |

Os scores granulares 0-100 estavam **muito próximos** (diferença
máxima 6 pts em qualquer critério). Mas a nota ENEM final mudou de
faixa.

#### Hipótese inicial (errada)
Primeira reação foi achar que o prompt do system não era explícito o
bastante na heurística banda → ENEM. Atualizei pra tabela
determinística sem sobreposição (`média 30-49 → 40`, `50-64 → 80`,
etc.). Smoke deu var=0 nos 3 modos foco. Achei que tinha resolvido.

#### Investigação real
Mas no `completo_parcial`, smoke deu var=120 (limite era 80). Olhando
os 3 runs, scores REJ estavam quase idênticos — o LLM oscilava na
emissão da nota ENEM individual de cada competência (C1/C2/C3/C4),
mesmo a tabela estando explícita no prompt.

Conclusão: **o LLM lê a tabela como sugestão, não como regra dura.**
Mesmo com `temperature=0` (depois deprecada no Opus 4.7), zero shot
em fronteira de banda gerava amostragem variável.

#### Fix
[`scoring.py`](../../backend/notamil-backend/redato_backend/missions/scoring.py):
override determinístico em Python. O LLM ainda emite `nota_cN_enem`,
mas o router sobrescreve com o cálculo Python (média de scores +
tabela inequívoca + caps semânticos das flags). Log de divergência
em `data/whatsapp/divergences.jsonl`.

**Smoke variância 4 modos × 3 runs (depois do fix):**

| Modo | Antes | Depois |
|---|---|---|
| foco_c3 | var=0 | **var=0** |
| foco_c4 | var=0 | **var=0** (LLM emitia 200, Python força 160 — coerente com média 88.75) |
| foco_c5 | var=0 | **var=0** |
| completo_parcial | **var=120** ❌ | **var=0** ✓ |

**Divergências reais coletadas em uso (n=8 em 13 interações = 62%):**

| Modo | LLM | Python | Δ |
|---|---|---|---|
| foco_c4 (×3) | 200 | 160 | 40 |
| foco_c3 (×2) | 80 | 40 | 40 |
| completo_parcial (×2) | 800 | 720 | 80 |
| completo_parcial (×1) | 760 | 720 | 40 |

Média `|Δ|`: 50 pts. **O LLM tende a inflacionar** sistematicamente
acima do que a média dos scores granulares justifica.

#### Lição estrutural

> **Onde houver função pura, deixa em Python. LLM fica com juízo,
> não com aritmética.**

A tradução média-de-scores → nota INEP discreta é função pura: dado
input, output único. Não exige criatividade, contexto cultural ou
nuance pedagógica. Pedir isso ao LLM é gastar tokens em algo que ele
não faz bem (hesita em fronteira) quando Python faz determinístico.

A divisão de trabalho que emergiu:

| Em Python (determinístico) | No LLM (juízo) |
|---|---|
| média de scores → nota ENEM | scores 0-100 por critério |
| caps semânticos sobre flags | flags booleanas (tese genérica? proposta vaga?) |
| soma das competências | feedback aluno + feedback professor |
| discretização banda | qualquer texto em prosa |

Essa fronteira deve guiar **decisões futuras de arquitetura**: ao
adicionar um cálculo, perguntar "isto é função pura ou exige
juízo?". Se pura, Python; se juízo, LLM.

#### Implicação operacional (62% divergência)

8/13 interações divergiram. Em escala, isso vira ruído nos logs. Não
afeta a nota que o aluno vê (Python é a fonte de verdade), mas:

- `divergences.jsonl` cresce rápido em produção
- Cognitive load do LLM emitir um campo que vai ser sobrescrito é
  desperdício de tokens

**Recomendação pra fase futura** (registrada na seção 6 abaixo):
**simplificar o schema** removendo `nota_cN_enem` do tool — o LLM emite
só rubrica + flags, Python deriva tudo. Reduz divergence rate pra 0%
estrutural (não há mais o que divergir) e corta tokens de output.

Doc completa do scoring: [scoring_pipeline.md](scoring_pipeline.md).

---

### Outros polimentos durante a sessão

- **Códigos curtos**: bot aceita `10`, `M1`, `OF10`, `RJ1OF10MF`,
  com ou sem pontuação. Mensagem padrão pede só `10/11/12/13/14`.
- **Truncamento de bullets**: `_MAX_BULLET_CHARS` 220 → 350,
  `_MAX_CHARS` 800 → 1200. Bullets longos cabem inteiros.
- **Vocabulário pedagógico** + sem condescendência + sem diminutivos
  já vinham da sessão anterior, validados em uso.

---

## 3. Métricas observadas em uso real

(n=13 interações de pipeline completo, todas no `RJ1·OF10·MF` do tester
no celular; smokes sintéticos não contam.)

| Métrica | Valor |
|---|---|
| Modo testado | `foco_c3` (OF10) |
| Latência média | **22.9s** (min 0s¹, max 32s) |
| Avg chars do texto transcrito | 490 |
| Avg chars da resposta WhatsApp | 582 |
| Quality issues (foto rejeitada) | 2 (foto borrada/escura) |
| Foto invalidada via "ocr errado" | 0 |
| Divergências LLM × Python | 8 (logged) |

¹ `min 0s` = duplicata detectada → resposta cacheada (sem chamar API).

### Latência decomposta (estimativa, foco_c3)

| Etapa | Tempo |
|---|---|
| Twilio webhook + download mídia | ~1s |
| Quality check local (PIL) | <0.1s |
| Detector rotação (Sonnet) | ~3-4s |
| OCR (Sonnet, 1ª tentativa) | ~5-7s |
| Fallback rotação oposta (se dispara) | +5-7s |
| Grade mission (Sonnet 4.6, foco) | ~10-12s |
| Override Python + render | <0.1s |
| Twilio send_text | ~0.5s |
| **Total típico** | **22-25s** |

### Custo por interação (estimativa)

| Componente | Custo |
|---|---|
| Detector rotação (1 Sonnet ~600 tokens) | ~$0.005 |
| OCR (1 Sonnet, ~3k input + ~600 output) | ~$0.015 |
| Grade mission foco (Sonnet) | ~$0.018 |
| Override + persist | $0 |
| **Foco / interação típica** | **~$0.04** |
| **Foco com fallback de rotação (3 OCR)** | **~$0.07** |
| **Completo parcial (Opus)** | ~$0.20 |
| **Completo integral (Opus + self-critique)** | ~$0.86 |

### Latência sentida vs medida

A 22-25s de pipeline foi sentida como **aceitável em sala**: aluno
manda foto, professor pode dar 1 instrução à classe enquanto espera. O
WhatsApp não mostra "digitando…" durante o processamento (limitação
do Sandbox); aluno vê "✓✓" do Twilio e espera.

OF14 (124s no smoke) foi sentido como **longo demais** mesmo sabendo
que era pipeline pesado — sugere ack imediato ("tô lendo, dá uns
2 minutos") + resposta final assíncrona pra Fase B.

### Custo real da sessão (n=13 interações reais + smokes)

| Item | Estimativa |
|---|---|
| 13 interações reais (foco_c3, com fallback de rotação algumas vezes) | ~$0.55 |
| Smoke `smoke_test_missions.py` (1 run × 5 modos) | ~$1.15 |
| Smoke `smoke_variance_missions.py` (3 runs × 4 modos × 2 rodadas) | ~$1.50 |
| Smoke `smoke_render_features.py` (offline, sem API) | $0 |
| Detector de rotação (cliques extras durante debug) | ~$0.10 |
| **Total estimado da sessão** | **~$3.30** |

**Custo unitário real medido (foco_c3 sandbox)**: ~$0.04/interação
(bateu com a estimativa anterior do
[REPORT_smoke_missions.md](REPORT_smoke_missions.md): ~$0.04 + ~$0.005
do detector de rotação).

**Projeção 5000 calls/ano** (50% foco / 30% parcial / 20% integral) —
revisada com dados reais:

| Modo | Calls/ano | $/call | $/ano |
|---|---:|---:|---:|
| Foco (3 modos) | 2500 | $0.04-0.07 | $100-175 |
| Completo Parcial | 1500 | $0.20 | $300 |
| Completo Integral | 1000 | $0.86 | $860 |
| **Total** | **5000** | — | **~$1260-1335/ano** |

Acima da estimativa original de ~$1110 porque o detector de rotação
adicionou ~$0.005/interação (não estava na projeção do smoke
sintético, onde fotos eram sempre na orientação certa).

Em escala 20k alunos × 5 missões/aluno/ano = 100k calls:
- Mantendo proporção: **~$25k-27k/ano**
- Em maior parte do OF14 (Opus + self-critique): viável ativar OF14
  só quando aluno paga e tirar do free tier do app.

---

## 4. Achados que NÃO foram corrigidos (Fase B+)

### OCR de letra cursiva pequena → erros C1 falsos

**Sintoma:** mesmo com rotação correta, o Sonnet erra palavras em
letra cursiva (ex.: "fome" virou "forma" em uma transcrição), o que
introduz "erros gramaticais" inexistentes na redação real. Em modo
foco_c3 isso pesa pouco (não avalia C1), mas em foco_c4/parcial/integral
puxa C1 pra baixo injustamente.

**Mitigação possível:** OCR via Opus 4.7 (5× mais caro mas mais
preciso); pipeline OCR em produção da Redato já usa Opus. Reativar
quando OF13/OF14 forem priorizados em uso real.

### dHash não invariante a rotação ≥ 90°

**Sintoma:** mesma redação fotografada em retrato e depois em paisagem
gera dHashes diferentes → bot trata como redações distintas.

**Mitigação possível:** computar dHash em **8 versões** (4 rotações ×
2 espelhamentos) e pegar a mínima. Cost: insignificante (operação
local). Não foi feito porque o caso "mesma foto em rotações diferentes"
é raro — o caso comum é o aluno reenviar a mesma imagem.

### Sistema avalia mismatch de modo silenciosamente

**Sintoma:** se o aluno manda redação OF12 (proposta) com código `10`
(OF10/foco_c3), o pipeline avalia como C3 — sem alertar o aluno que
mandou pro modo errado.

**Mitigação possível:** detector de mismatch via Sonnet (uma chamada
extra: "este texto é proposta de intervenção? introdução? parágrafo
único?"). Custo ~$0.005/interação. Provavelmente vale ativar pra
turmas piloto onde aluno está aprendendo a usar.

---

## 5. Decisões tomadas pra Fase B+

Esta sessão fechou 6 decisões operacionais. Nenhuma fica em aberto pra
B+. Mudanças posteriores exigem revisão consciente, não default.

### 5.1 PDF do professor — sob demanda via endpoint HTTP

Endpoint `/turma/<id>/pdf?from=...&to=...` consome
[`list_interactions_by_turma()`](../../backend/notamil-backend/redato_backend/whatsapp/persistence.py)
e gera PDF com `reportlab` (ou similar). Conteúdo: nota total + rubrica
REJ por critério + transcrição + feedback completo (não a versão
WhatsApp resumida).

**Não automatizado** (sem PDF semanal automático): professor pede
quando quiser. Painel web só na Fase C.

### 5.2 Onboarding — planilha CSV + confirmação no 1º contato

Professor fornece planilha `(phone, nome, turma)` antes da turma
começar. Bot pré-cadastra com estado `AWAITING_CONFIRM`. No primeiro
"Oi" do aluno, bot pergunta:

> "Oi João, você é da turma 1A do Cursinho X?"

Aluno responde sim/não. Fail-safe se phone errou na planilha.

Descartado: cadastro interativo individual (lento), link convite
(perde fail-safe).

### 5.3 Limite do Chat Redator — 5/dia por aluno

Mantido em 5/dia. Limita custo (sandbox tem 50 msgs/dia total) e
empurra aluno a usar com intenção. Reavaliar com dado real de uso
por aluno **só depois de 1 mês de produção**.

Implementação fica pra Fase C (Chat Redator é módulo separado).

### 5.4 Self-critique — só OF14, só fora de aula

- **Aula:** `REDATO_SELF_CRITIQUE=0` (resposta em ~50s, suficiente).
- **Auditoria noturna:** job cron com `REDATO_SELF_CRITIQUE=1`
  re-corre as redações OF14 do dia, registra divergências numa tabela
  de revisão. Professor acessa pela manhã se quiser hand-review.

OF10/11/12/13 nunca rodam self-critique — latência inaceitável e
ganho marginal pra modos de competência única ou parcial.

### 5.5 Migração de provedor — Twilio prod, depois Meta

| Fase | Provedor | Volume | Custo/ano |
|---|---|---|---|
| A (atual) | Twilio Sandbox | 50 msgs/dia (limite) | $0 |
| **B+ (próxima)** | **Twilio produção** | ~1k msgs/mês | ~$60 |
| C (escala) | Meta WhatsApp Cloud API | ~10k msgs/mês | ~$70 (free tier ajuda) |

A migração Twilio→Meta é abstraída pelo
[`InboundMessage`](../../backend/notamil-backend/redato_backend/whatsapp/bot.py)
e
[`OutboundMessage`](../../backend/notamil-backend/redato_backend/whatsapp/bot.py).
Trocar = substituir 1 arquivo (`twilio_provider.py` → `meta_provider.py`).

Spec original: [whatsapp_provider_eval.md](whatsapp_provider_eval.md).

### 5.6 Simplificar schema — executar em M3 ou M4 da Fase B+

Remover `nota_c3_enem`, `nota_c4_enem`, `nota_c5_enem`, `notas_enem` e
`nota_total_parcial` do tool_use. LLM emite só:
- `rubrica_rej` (scores 0-100 por critério)
- `articulacao_a_discussao` (foco_c5)
- `flags`
- `feedback_aluno` + `feedback_professor`

Python deriva o resto via [`scoring.py`](../../backend/notamil-backend/redato_backend/missions/scoring.py).

**Por quê:** 62% de divergência LLM × Python observada (Bug 8). LLM
desperdiça tokens emitindo campo que sempre é sobrescrito.

**Impactos esperados:**
- divergence rate cai de 62% pra 0% (não há mais o que divergir)
- output tokens caem ~10-15%
- prompt do system encurta (a tabela média→ENEM pode sair)

**Quando:** M3 ou M4 da Fase B+ (não M1/M2 — não ataca regressão
funcional, e mudança de schema exige re-validação completa do smoke
de variância). Vale fazer em janela de manutenção planejada, junto
com outra mudança grande de prompt se houver.

---

## 6. Recomendações pra produção

Decisões operacionais já fechadas estão na seção 5. Esta seção registra
**rotinas de auditoria** que dependem de comportamento ao longo do tempo.

### Auditar `divergences.jsonl` mensalmente

- **Fonte primária**: cada vez que LLM diverge do override Python,
  fica registrado em `data/whatsapp/divergences.jsonl`.
- **Análise mensal**:
  - se >20% das chamadas divergem por >1 banda → revisar prompt do
    system (heurística inequívoca não está sendo seguida)
  - se divergências concentram em 1 modo → revisar caps daquele modo
    em [`scoring.py`](../../backend/notamil-backend/redato_backend/missions/scoring.py)
  - se divergem só em zona de fronteira (média ≈ threshold) →
    comportamento esperado, **não tocar**

Após executar 5.6 (simplificar schema), divergence rate cai pra 0%
estrutural — esta auditoria perde objeto e pode ser desativada.

### Smoke de regressão antes de tocar em `scoring.py`

```bash
python scripts/validation/smoke_variance_missions.py --runs 3 \
    --only foco_c3,foco_c4,foco_c5,completo_parcial
```

**Critério**: variância em todos os 4 modos = 0. Se algum >0 sem
mudança intencional, **regrediu**.

Aplicar antes de qualquer alteração em:
- thresholds de banda em `media_to_inep`
- ordem de aplicação dos caps semânticos
- adição/remoção de critérios da rubrica REJ
- mudança de modelo (Sonnet 4.6 → Opus, etc.)

---

## 7. Próximo passo

**Fase B+ inicia agora.** Esta sessão fechou as 6 decisões operacionais
necessárias (seção 5), validou estabilidade do pipeline em uso pessoal
(seção 3) e mapeou os achados que ficam pra resolver durante a fase
(seção 4). O trabalho de B+ — portal web do professor, importação por
planilha, agendamento de atividades, dashboard agregado, email
transacional — começa imediatamente.

### Inputs desejáveis (não bloqueadores)

Os 3 inputs abaixo **melhoram** B+ se aparecerem mas não atrasam o
trabalho técnico:

- **Cursinho parceiro confirmando interesse.** Permite calibrar
  prioridades de M1-M8 com necessidades reais. Sem isso, B+ desenvolve
  contra um persona genérico (cursinho de ensino médio brasileiro,
  turma de 20-30 alunos, 1-2 professores).
- **Validação pedagógica de 1-2 professores.** Mostrar saída do bot
  lado-a-lado com avaliação humana antes de expor a turma. Pode ser
  feita em paralelo a M1-M3 (banco + portal + auth) sem bloqueio
  mútuo.
- **Daniel acompanhando uso real em sala** quando piloto começar.
  Fase A teve 1 tester (Daniel via celular) — Fase B+ piloto vai ter
  20-30 alunos simultâneos, e atritos de UX que não aparecem em
  logs precisam observação direta.

### O que NÃO esperar em B+

- Chat Redator (separado, Fase C).
- Dashboard web do professor (parte de B+, M7).
- Múltiplos cursinhos / multi-tenancy (Fase C).
- Suporte a Livro 2S (Fase C).
- App próprio em vez de WhatsApp (não planejado).

---

## Apêndice — checklist do que NÃO foi testado

Pra deixar claro o gap entre Caminho 2 e produção:

- [ ] Volume real: 30 alunos da mesma turma simultaneamente
- [ ] Carteira sem cobertura 4G boa (latência variável)
- [ ] Aluno troca de celular (mesmo phone, novo dispositivo)
- [ ] Aluno bloqueia o número
- [ ] Bot fica offline durante interação (uvicorn cai)
- [ ] DB cresce até 10k registros (queries lentas?)
- [ ] OF13 e OF14 em uso real (só foco_c3 foi testado pelo phone)
- [ ] Letra cursiva difícil em luz ruim (smoke testou letra de
      imprensa em foto controlada)
- [ ] Aluno manda áudio em vez de foto
- [ ] Aluno tenta fazer outra coisa (chat livre, dúvida) durante o fluxo

Tudo isso é **Fase B**.
