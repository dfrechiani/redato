# Caminho 2 — Setup passo a passo (Twilio Sandbox real)

**Objetivo:** colocar o bot WhatsApp no ar em sandbox para testar com o
celular pessoal, sem ainda contratar produção.

**Referência arquitetural:** [whatsapp_setup.md](whatsapp_setup.md).
**Eval providers:** [whatsapp_provider_eval.md](whatsapp_provider_eval.md).

## O que esta sessão entregou de código

| Arquivo | Função |
|---|---|
| [`redato_backend/whatsapp/twilio_provider.py`](../../../backend/notamil-backend/redato_backend/whatsapp/twilio_provider.py) | parse_inbound, download_media, send_text, validate_signature |
| [`redato_backend/whatsapp/webhook.py`](../../../backend/notamil-backend/redato_backend/whatsapp/webhook.py) | FastAPI router `POST /twilio/webhook` + signature check |
| [`redato_backend/whatsapp/app.py`](../../../backend/notamil-backend/redato_backend/whatsapp/app.py) | App standalone uvicorn pro sandbox |
| [`scripts/validation/test_webhook_offline.py`](../../../backend/notamil-backend/scripts/validation/test_webhook_offline.py) | 6 testes offline (sem Twilio nem Anthropic real) |

Smoke offline já passou 6/6. O que falta é setup de provedor + ngrok +
celular real.

---

## Passo a passo (você executa)

### 1. Console Twilio — pegar credenciais

1. Abra https://console.twilio.com.
2. Na **dashboard inicial**, copie:
   - `Account SID` (começa com `AC...`)
   - `Auth Token` (clique em "Show" pra revelar)
3. **Sandbox WhatsApp:** já está ativado (você compartilhou
   `+1 415 523 8886` + código `join organized-enjoy`).

### 2. Configurar `.env`

Adicione ao `backend/notamil-backend/.env`:

```bash
# Twilio Sandbox (Caminho 2)
TWILIO_ACCOUNT_SID=AC...     # cole o SID do passo 1
TWILIO_AUTH_TOKEN=...        # cole o token do passo 1
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886

# Validação de assinatura: ligue (1) quando ngrok estiver de pé.
# Pra teste rapidíssimo, pode deixar 0, MAS:
# atenção, com 0 qualquer um pode bater no webhook.
TWILIO_VALIDATE_SIGNATURE=1
```

O `.env` já está no `.gitignore` — não há risco de vazar.

### 3. Ativar Sandbox do seu celular

No WhatsApp do **seu celular pessoal**:

1. Adicione o contato **+1 415 523 8886** (chamado "Twilio Sandbox").
2. Mande a mensagem exata: `join organized-enjoy`
3. Twilio responde algo como: *"Connected to sandbox. Reply 'stop' to leave."*

A partir desse momento, **as mensagens que você mandar pra esse número
caem no seu webhook**.

### 4. Subir o bot localmente

Em um terminal:

```bash
cd backend/notamil-backend

# Rodar o app FastAPI
uvicorn redato_backend.whatsapp.app:app --reload --port 8090
```

Você deve ver:
```
INFO:     Started server process
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8090
```

Verifique health:
```bash
curl http://localhost:8090/twilio/health
# Deve retornar: {"status":"ok","env":{...},"validate_signature":true}
```

### 5. Expor publicamente via ngrok

Em **outro terminal**:

```bash
# Instalar ngrok se ainda não tem:
# brew install ngrok    (macOS)
# OU baixar de https://ngrok.com/download

# Rodar ngrok apontando pra porta do uvicorn
ngrok http 8090
```

ngrok mostra algo como:
```
Forwarding  https://abc123.ngrok-free.app -> http://localhost:8090
```

**Anote a URL https** (não a http). Essa é a URL pública.

### 6. Configurar webhook no console Twilio

1. Vá em https://console.twilio.com/us1/develop/sms/try-it-out/whatsapp-learn
2. No bloco **Sandbox Configuration**:
   - **WHEN A MESSAGE COMES IN:** cole `https://abc123.ngrok-free.app/twilio/webhook`
   - Method: `POST`
3. Salve.

Pra que a validação de assinatura funcione, **a URL aqui no console
precisa ser idêntica à que o ngrok expõe**. Se trocar de subdomínio
ngrok, atualize aqui.

(Opcional) Se a URL pública atrás do ngrok não corresponde 1:1 com a
URL interna que o FastAPI vê, exporte:
```bash
export TWILIO_PUBLIC_URL=https://abc123.ngrok-free.app
```

### 7. Smoke real do seu celular

Mande mensagens nessa ordem **do seu celular** (que ativou o sandbox no
passo 3) **pro número Sandbox**:

| Você manda | Resposta esperada |
|---|---|
| `oi` | "Olá! Eu sou a *Redato*..." pedindo nome |
| `Daniel Frechiani` | "Prazer, Daniel..." pedindo turma |
| `Teste 1A — Cursinho Smoke` | "Beleza, Daniel! Cadastro feito..." |
| `RJ1OF10MF` + foto da redação | (~20-30s) Avaliação C3 formatada |

**Foto da redação:** escreva à mão um parágrafo argumentativo (3-5 linhas)
em folha pautada, fotografe com luz natural e enquadre o parágrafo todo.

Repita o último passo trocando o código pra cada modo:

| Código | Modo | Latência típica | Tipo de redação |
|---|---|---|---|
| `RJ1OF10MF` | Foco C3 | ~25s | Parágrafo com tese + premissa + exemplo |
| `RJ1OF11MF` | Foco C4 | ~25s | Parágrafo com 4 peças e conectivos |
| `RJ1OF12MF` | Foco C5 | ~25s | Proposta de intervenção |
| `RJ1OF13MF` | Completo Parcial | ~35s | Parágrafo argumentativo completo |
| `RJ1OF14MF` | Completo Integral | ~120s | Redação completa de 3 parágrafos |

OF14 demora ~2min porque inclui self-critique + ensemble. **Considere o
que sentir nesse tempo de espera** e anote no REPORT.

### 8. Inspecionar persistência

Cada interação fica salva em SQLite:

```bash
sqlite3 backend/notamil-backend/data/whatsapp/redato.db

> .tables
alunos  interactions  turmas

> SELECT phone, nome, turma_id, estado FROM alunos;
> SELECT id, missao_id, length(texto_transcrito), elapsed_ms FROM interactions ORDER BY id DESC;
> SELECT * FROM interactions WHERE missao_id = 'RJ1_OF10_MF';
```

---

## Checklist de validação UX (anote no REPORT enquanto testa)

Marque cada item com ✓ ou ✗ enquanto testa do seu celular:

- [ ] **Tempo de resposta sentido aceitável?** Foco/Parcial 20-35s,
      Integral ~2min. Compare com a expectativa do aluno na sala.
- [ ] **Formatação WhatsApp:** *negrito* renderiza, listas com `-`
      ficam visíveis, emoji ausente é OK?
- [ ] **OCR aguenta caneta esferográfica em papel pautado** comum?
      A transcrição fica fiel ao que você escreveu?
- [ ] **Quality checks disparam quando deveriam:**
  - foto_escura: tire uma foto com a redação no escuro
  - foto_borrada: tire foto com mão tremida
  - sem_redacao: tire foto da capa do livro
  - texto_curto: tire foto de 1 linha só
- [ ] **FSM se recupera fora de ordem?**
  - Mande foto antes de cadastrar (deve pedir cadastro)
  - Mande código sem foto (deve pedir foto)
  - Mande foto sem código (deve pedir código)
  - Mande "stop" e depois "join organized-enjoy" de novo

Resultados desses 5 itens vão pro
[REPORT_caminho2_realuse.md](REPORT_caminho2_realuse.md).

### Variantes de teste interessantes

- **OF14 sem self-critique:** `REDATO_SELF_CRITIQUE=0 uvicorn ...` —
  compara latência (~50s vs 120s) e qualidade pedagógica.
- **Foto de canto distante** com redação pequena no enquadramento —
  testa se OCR pega ou cai em quality_check.
- **Letra cursiva exagerada** vs letra de imprensa — calibragem do OCR.

---

## Troubleshooting

### "Invalid signature" no log do uvicorn

A URL no console Twilio precisa bater **exatamente** com a URL que o
FastAPI vê. Se ngrok fez nova conexão (subdomínio mudou):

1. Atualize URL no console Twilio.
2. OU exporte `TWILIO_PUBLIC_URL=https://novo.ngrok-free.app` e reinicie
   uvicorn.
3. Em **último caso**, desligue: `TWILIO_VALIDATE_SIGNATURE=0` e
   reinicie. **Não usar em produção.**

### Twilio não chega no webhook

- Confira que ngrok está rodando (`http://localhost:4040` mostra
  requests).
- Confira que a URL no console termina com `/twilio/webhook` e usa
  https.
- Mande mensagem do celular que ativou o sandbox — outro número não
  funciona.

### "Authentication Error - invalid username" ao tentar enviar

`TWILIO_ACCOUNT_SID` ou `TWILIO_AUTH_TOKEN` errados. Recopie do
console.

### "OCR não consegue transcrever" — foto rejeita sempre

Provavelmente foto muito escura ou borrada. Calibre thresholds via
`.env`:

```bash
REDATO_OCR_MIN_BRIGHTNESS=40       # mais permissivo (default 60)
REDATO_OCR_MIN_LAPLACIAN_VAR=50    # mais permissivo (default 100)
```

### Sandbox parou de responder

Sandbox tem **24h de janela** depois da última msg do usuário. Se
demorar mais, mande "join organized-enjoy" de novo.

Limite gratuito: **50 msgs/dia**. Pra teste pessoal, mais que
suficiente.

---

## Custo esperado nos testes

- Twilio Sandbox: **gratuito** (limite 50 msgs/dia).
- Anthropic API por interação:
  - OCR Sonnet: ~$0.005-0.01 (depende do tamanho da foto)
  - Foco (Sonnet): ~$0.02
  - Parcial (Opus): ~$0.19
  - Integral (Opus + self-critique): ~$0.86 cold / ~$0.30 cache hit
- Estimativa: **~$5 em 1-2 dias de teste pessoal** (50-100 interações).

---

## Próximo passo

Depois de rodar pelo menos 1 fluxo de cada modo do seu celular,
preencha [REPORT_caminho2_realuse.md](REPORT_caminho2_realuse.md) com
os achados. Esse relatório guia decisões de Fase B.
