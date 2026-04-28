# Setup técnico — Bot WhatsApp da Redato (Fase A)

**Status:** sandbox/dev. Fase A roda em ambiente local sem provedor real.
**Spec do escopo:** Fase A do plano de produção, sessão 2026-04-27.

## Estrutura do código

```
backend/notamil-backend/redato_backend/whatsapp/
├── __init__.py            # exports públicos
├── persistence.py         # SQLite (alunos, turmas, interactions)
├── ocr.py                 # Claude Sonnet multimodal + quality checks
├── render.py              # tool_args → mensagem WhatsApp (≤800 chars)
├── bot.py                 # FSM por phone, dispatch
└── api_simulator.py       # WhatsAppSimulator (dev local sem provedor)
```

```
backend/notamil-backend/scripts/validation/
└── smoke_test_whatsapp.py # 5 fluxos end-to-end com fotos sintéticas
```

```
backend/notamil-backend/data/whatsapp/
├── redato.db              # SQLite produção (criado on demand)
├── redato_smoke.db        # SQLite usado pelo smoke (recriado a cada run)
└── smoke_photos/          # PNGs sintéticos do smoke
```

## Pipeline operacional

```
[aluno: foto + missao_code via WhatsApp]
        ↓ webhook do provedor
[InboundMessage(phone, text, image_path)]
        ↓
bot.handle_inbound  ──── persistence: alunos.estado FSM
        ↓
ocr.transcribe_with_quality_check  ──── quality checks (brilho, blur, n_chars)
        ↓ texto transcrito + qualidade OK
missions.grade_mission(data)  ──── Sonnet (foco) ou Opus (parcial/integral)
        ↓ tool_args estruturado
render.render_aluno_whatsapp  ──── ≤800 chars, *negrito*, listas
        ↓
[OutboundMessage(text)]
        ↓ provedor: Twilio/Meta
[aluno: recebe resposta]
```

A interação é totalmente persistida em `interactions` da SQLite —
permite agregação por turma na Fase B (PDF pro professor).

## Estados do bot (FSM por phone)

| Estado | O que aceita | Próximo estado |
|---|---|---|
| `NEW` | qualquer mensagem | `AWAITING_NOME` (depois de mandar boas-vindas) |
| `AWAITING_NOME` | texto com nome ≥3 chars | `AWAITING_TURMA` |
| `AWAITING_TURMA` | "TURMA — ESCOLA" | `READY` |
| `READY` | foto + código missão (juntos ou separados) | `AWAITING_FOTO\|<missao>` se faltar foto |
| `AWAITING_FOTO\|<missao>` | foto | `READY` (após processamento) |

Ver [bot.py:NEW..AWAITING_FOTO](../../../backend/notamil-backend/redato_backend/whatsapp/bot.py).

## Activity ID — formatos aceitos

O regex aceita `RJ\d+` + `OF\d{2}` + `MF` separados por qualquer
combinação de espaços, pontos, hifens ou underscores.

| Formato do aluno | Canonical |
|---|---|
| `RJ1OF10MF` | `RJ1·OF10·MF` |
| `rj1.of10.mf` | `RJ1·OF10·MF` |
| `RJ1_OF13_MF` | `RJ1·OF13·MF` |
| `manda RJ1OF11MF aí` | `RJ1·OF11·MF` |
| `oi tudo bem` | `None` (rejeita) |

## Quality checks da foto

Executam **antes** da chamada de OCR pra evitar gasto desnecessário.

| Check | Métrica | Threshold | Mensagem |
|---|---|---|---|
| Foto escura | brilho médio < `MIN_BRIGHTNESS` | 60 | "tira outra foto, boa luz" |
| Foto borrada | variance Laplaciano < `MIN_LAPLACIAN_VAR` | 100 | "celular firme" |
| Foto sem redação | LLM detecta SEM_REDACAO | — | "não consegui ver a redação" |
| Texto curto | transcrição < `MIN_TRANSCRIBED_CHARS` | 50 | "foto não pegou todo o texto" |

Override via env: `REDATO_OCR_MIN_BRIGHTNESS`, `REDATO_OCR_MIN_LAPLACIAN_VAR`,
`REDATO_OCR_MIN_CHARS`.

## Modelos por etapa

| Etapa | Modelo | Por quê |
|---|---|---|
| OCR | `claude-sonnet-4-6` | Texto manuscrito de aluno + transcrição literal — Opus não justifica custo. |
| Foco C3/C4/C5 | `claude-sonnet-4-6` | Default em [`_DEFAULT_MODEL_BY_MODE`](../../../backend/notamil-backend/redato_backend/missions/router.py). |
| Completo Parcial OF13 | `claude-opus-4-7` | 4 competências, mais perto de redação completa. |
| Completo Integral OF14 | `claude-opus-4-7` (pipeline v2) | Redação completa com self-critique + ensemble. |

Override:
- `REDATO_WHATSAPP_OCR_MODEL` — modelo do OCR (default Sonnet).
- `REDATO_MISSION_MODEL` — override pros modos foco/parcial.
- `REDATO_CLAUDE_MODEL` — override pro pipeline v2 (OF14).

## Resultados do smoke 5 modos (2026-04-27)

| Modo | Latência | Reply chars | Transcript chars | OCR issues | Custo aprox. |
|---|---:|---:|---:|---|---:|
| `foco_c3` | 22.9s | 541 | 297 | nenhum | ~$0.03 |
| `foco_c4` | 23.3s | 653 | 381 | nenhum | ~$0.03 |
| `foco_c5` | 25.0s | 648 | 451 | nenhum | ~$0.03 |
| `completo_parcial` | 34.5s | 635 | 487 | nenhum | ~$0.20 |
| `completo_integral` | 124.8s¹ | 793 | 809 | nenhum | ~$0.86 (cache hit) |

¹ OF14 inclui self-critique (2 passes) — excede o critério <90s. **OF14
via WhatsApp:** considerar enviar ack imediato ("tô lendo, dá uns 2
minutos") + resposta final assíncrona, ou desligar self-critique via
`REDATO_SELF_CRITIQUE=0` (corta latência ~50%, mas reduz qualidade
pedagógica medida em [REPORT_smoke_missions.md](REPORT_smoke_missions.md)).

**Custo total smoke:** ~$1.15 (5 OCRs Sonnet + 4 grade Sonnet + 1 grade
Opus com cache hit).

**Persistência verificada:**
- 5 turmas criadas (uma por modo).
- 5 alunos cadastrados.
- 5 interações registradas (uma por turma).
- `list_interactions_by_turma()` retornou as interações esperadas.

## Endpoints e webhooks (Fase B — quando contratar provedor)

A interface está pronta. Quando contratar Twilio, criar:

```python
# backend/notamil-backend/redato_backend/whatsapp/twilio_webhook.py
from fastapi import APIRouter, Request
from redato_backend.whatsapp.bot import handle_inbound, InboundMessage

router = APIRouter()

@router.post("/twilio/webhook")
async def twilio_webhook(req: Request):
    form = await req.form()
    phone = form.get("From", "").replace("whatsapp:", "")
    text = form.get("Body")
    media_url = form.get("MediaUrl0")
    image_path = await _download_media(media_url) if media_url else None

    msg = InboundMessage(phone=phone, text=text, image_path=image_path)
    responses = handle_inbound(msg)

    # Resposta inline (Twilio TwiML) ou via API client
    return _format_twiml(responses)
```

Spec do contrato `InboundMessage` está estável — provedor é só
adaptador.

## Variáveis de ambiente

| Var | Default | Quando usar |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | obrigatória |
| `REDATO_WHATSAPP_DB` | `data/whatsapp/redato.db` | trocar pra Postgres em produção (TODO Fase B) |
| `REDATO_WHATSAPP_OCR_MODEL` | `claude-sonnet-4-6` | override do modelo OCR |
| `REDATO_OCR_MIN_BRIGHTNESS` | `60` | calibrar threshold de foto escura |
| `REDATO_OCR_MIN_LAPLACIAN_VAR` | `100` | calibrar threshold de blur |
| `REDATO_OCR_MIN_CHARS` | `50` | mínimo de chars transcritos pra aceitar |
| `REDATO_MISSION_MODEL` | (default por modo) | override modos foco/parcial |
| `REDATO_SELF_CRITIQUE` | `1` | desligar pra acelerar OF14 (perde qualidade) |

## Como rodar localmente

```bash
cd backend/notamil-backend

# 1) Smoke 5 modos (~$1, ~4-5 min)
python scripts/validation/smoke_test_whatsapp.py

# 2) Smoke 1 modo
python scripts/validation/smoke_test_whatsapp.py --only foco_c3

# 3) Smoke sem OF14 (mais rápido, ~$0.30)
python scripts/validation/smoke_test_whatsapp.py --skip-of14

# 4) Inspecionar DB
sqlite3 data/whatsapp/redato_smoke.db
> SELECT phone, nome, turma_id, estado FROM alunos;
> SELECT id, missao_id, elapsed_ms, length(redato_output) FROM interactions;
```

## O que NÃO foi feito (declarado fora de escopo)

- WhatsApp real em produção (só sandbox simulator).
- Provedor contratado (Twilio ou Meta) — só avaliação em
  [whatsapp_provider_eval.md](whatsapp_provider_eval.md).
- Geração de PDF agregado pro professor (Fase B).
- Onboarding completo: matrícula em massa, convites pro aluno, dashboard
  do professor (Fase C).
- Postgres em produção (Fase B — SQLite por enquanto).
- Resposta assíncrona pro OF14 (ack + resultado em 2 mensagens) — TODO
  documentado em [smoke results](#resultados-do-smoke-5-modos-2026-04-27).
- Webhook receiver real — só interface contractual em `bot.py`.

## Próximos passos (Fase B)

1. Decidir provedor (recomendação: **Twilio Sandbox → Twilio produção**).
2. Implementar `twilio_webhook.py` adaptador.
3. Migrar SQLite → Postgres.
4. Implementar geração de PDF agregado por turma (consumir
   `list_interactions_by_turma()`).
5. Resposta assíncrona pro OF14 (ack imediato + resultado final).
6. Cadastro em massa de alunos via planilha do professor.
