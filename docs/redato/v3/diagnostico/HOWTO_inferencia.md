# HOWTO — Pipeline de inferência de diagnóstico cognitivo (Fase 2)

**Atualizado:** 2026-05-03

## O que é

Pipeline que recebe redação corrigida (texto + `redato_output`) e gera
um diagnóstico cognitivo estruturado: pra cada um dos 40 descritores
observáveis (Fase 1), classifica `dominio` / `lacuna` / `incerto` com
evidência textual + identifica top-5 lacunas prioritárias + resumo
qualitativo + recomendação breve.

Implementação:
- **Backend:** `redato_backend/diagnostico/` (loader, inferencia,
  persistencia)
- **Storage:** coluna JSONB `envios.diagnostico`
- **Endpoint retry:** `POST /portal/envios/{envio_id}/diagnosticar`
- **Modelo:** GPT-4.1 base (`gpt-4.1-2025-04-14`)
- **Custo típico:** ~$0.04 por redação (3000 input + 5000 output tokens)
- **Latência típica:** 10-15s

## Como o pipeline funciona

```
┌──────────────────┐
│  Bot WhatsApp    │  recebe foto + missão
│  (whatsapp/bot)  │
└─────────┬────────┘
          │
          ▼
   ┌──────────────┐    ┌────────────────────┐
   │ OCR (Claude) │ → │ Pipeline correção   │
   └──────────────┘    │ (FT ou Claude)      │
                       └─────────┬──────────┘
                                 │ tool_args (redato_output)
                                 ▼
                      ┌──────────────────────┐
                      │ render_aluno + envia │  ← aluno recebe correção
                      └──────────┬───────────┘
                                 │
                                 ▼
                      ┌──────────────────────┐
                      │ INSERT Envio (Pg)    │
                      │ + redato_output       │
                      └──────────┬───────────┘
                                 │ envio_id
                                 ▼
                      ┌─────────────────────────────────┐
                      │ Diagnóstico (Fase 2)            │
                      │ inferir_diagnostico()           │
                      │   → GPT-4.1 + 40 descritores    │
                      │   → tool_use schema validado    │
                      │ persistir_diagnostico_envio()   │
                      │   → UPDATE envios.diagnostico   │
                      └─────────────────────────────────┘
                              ↑
                              │ falha aqui NÃO bloqueia entrega
                              │ (correção já foi enviada ao aluno)
```

Pontos importantes:

1. **Não-bloqueante**: o aluno já recebeu a correção quando o
   diagnóstico começa a rodar. Falha do pipeline OpenAI (timeout,
   key inválida, parser falha) é logada via `logger.exception` e
   `envios.diagnostico` fica NULL — sem impacto no UX do aluno.

2. **Dois caminhos**: pipeline normal (bot) + endpoint de retry. O
   endpoint serve pra envios pré-Fase 2 (NULL), envios cuja
   inferência falhou na primeira vez, ou refresh quando
   `descritores.yaml` ganha versão nova.

3. **Tool calling forçado**: o prompt obriga o LLM a chamar a tool
   `registrar_diagnostico` com schema estrito (40 itens, IDs
   válidos, status enum, etc.). OpenAI valida antes de devolver —
   reduz schema drift que pegaríamos com JSON cru. Validação
   adicional em Python (defesa em profundidade).

## Schema do `envios.diagnostico`

```json
{
  "schema_version": "1.0",
  "modelo_usado": "gpt-4.1-2025-04-14",
  "descritores_versao": "1.0",
  "gerado_em": "2026-05-03T12:34:56.789012+00:00",
  "latencia_ms": 12450,
  "custo_estimado_usd": 0.041,
  "input_tokens": 2950,
  "output_tokens": 5100,
  "descritores": [
    {
      "id": "C1.005",
      "status": "lacuna",
      "evidencias": [
        "Existe muitos problemas (linha 04)",
        "a maioria das pessoas sentem (linha 12)"
      ],
      "confianca": "alta"
    },
    ... 40 entries (uma por descritor do YAML)
  ],
  "lacunas_prioritarias": [
    "C5.003", "C5.005", "C3.004", "C1.005", "C4.001"
  ],
  "resumo_qualitativo": "Aluno demonstra compreensão do tema (C2) e ...",
  "recomendacao_breve": "Reforço prioritário em proposta de intervenção (C5) ..."
}
```

Campos importantes:

- `schema_version`: incrementar quando o schema mudar (rastreia
  rows persistidas em formato antigo).
- `modelo_usado`: pra comparar custo/qualidade entre modelos no
  futuro.
- `descritores_versao`: versão do `descritores.yaml` usada — se
  o YAML ganhar versão 1.1 (mais descritores, ex.), rows antigas
  ficam visivelmente em 1.0.
- `latencia_ms` + `custo_estimado_usd`: pra dashboard de SLO/custo
  quando volume crescer.
- `evidencias`: trechos LITERAIS do texto da redação (LLM cita
  copy/paste, idealmente com indicação de linha).
- `confianca`: `alta` (2+ evidências), `media` (1 ou padrão sutil),
  `baixa` (texto curto demais).

## Como rodar localmente

Env vars necessárias (em `backend/notamil-backend/.env`):

```bash
# Obrigatório
OPENAI_API_KEY=sk-proj-...

# Opcionais (defaults sensatos)
REDATO_DIAGNOSTICO_HABILITADO=true             # default true
REDATO_DIAGNOSTICO_MODELO=gpt-4.1-2025-04-14   # default
# REDATO_DIAGNOSTICO_YAML=...                  # só se path custom
```

Rollback rápido (sem deploy):
```bash
REDATO_DIAGNOSTICO_HABILITADO=false
```

Setando isso no Railway → restart → pipeline pula a inferência. Erros
existentes em logs param de aparecer.

Smoke local:

```bash
cd backend/notamil-backend
python -c "
from redato_backend.diagnostico.inferencia import inferir_diagnostico

resultado = inferir_diagnostico(
    texto_redacao='Texto da redação aqui...',
    redato_output={'modo': 'completo', 'nota_total_enem': 720},
    tema='Tema da proposta',
)
import json; print(json.dumps(resultado, indent=2, ensure_ascii=False)[:500])
"
```

## Como reprocessar diagnóstico de envio antigo

Endpoint:
```
POST /portal/envios/{envio_id}/diagnosticar
Authorization: Bearer <jwt do professor da turma>
```

Resposta esperada (sucesso):
```json
{
  "ok": true,
  "diagnostico": { ... payload completo ... }
}
```

Resposta em falha (status HTTP 200 — não é erro do endpoint):
```json
{
  "ok": false,
  "error": "inferência retornou None — ver logs"
}
```

Casos que retornam HTTP 4xx (erro de pré-condição):
- `404`: envio não existe
- `400`: envio sem `interaction_id` (pré-M4) ou `texto_transcrito` vazio
- `403`: caller não é professor da turma nem coordenador da escola

## Custos estimados

GPT-4.1 (pricing 2026-05): $2/MM input, $8/MM output.

Caso típico (1 redação ENEM ~30 linhas):
- Input: ~3000 tokens (system prompt + 40 descritores + texto + redato_output)
- Output: ~5000 tokens (40 entries + lacunas + resumo + recomendação)
- **Custo ≈ $0.046 por redação**

Custo mensal estimado:
- 100 redações/mês: $4.60
- 1000 redações/mês: $46
- 10000 redações/mês: $460

Daniel aceitou o trade-off ($0.04/redação) na decisão da Fase 2
(2026-05-03). Reavaliação quando volume real subir — modelos
menores (gpt-4.1-mini) podem ser viáveis se a precisão se mantiver.

## Reprodutibilidade do diagnóstico

`temperature=0` (determinístico) — mesma redação + mesmo redato_output
+ mesmo prompt → mesmo diagnóstico, na maioria dos casos. Não é
100% pq a OpenAI ainda tem fontes não-determinísticas em pipelines
de tool_use, mas variação esperada é < 5% dos descritores.

## Limitações conhecidas

- **Sem validação humana ainda.** Métricas de precisão
  (concordância com avaliador humano) só vão existir na Fase 5,
  com cursinhos parceiros validando lacunas inferidas. Hoje
  confiamos no prompt + schema + intuição pedagógica.

- **Latência adiciona ~12s ao pipeline.** Aluno NÃO vê esse delay
  (correção é entregue antes), mas o envio só fica "completo" no
  Postgres ~12s depois. Dashboard professor mostra envio sem
  diagnóstico durante essa janela.

- **Custo escala com volume.** A $0.04/redação, 10k redações/mês
  custam $460. Se Redato atingir 100k+/mês com cursinhos, repensar
  modelo (mini) ou cache (mesmo redato_output → mesmo diagnóstico).

- **Texto curto pode forçar 'incerto'.** Redação fragmentada (< 10
  linhas) tem sinal insuficiente pra muitos descritores. Esperado:
  metade ou mais ficarem `incerto`. Não é bug, é honestidade do
  modelo.

- **Modelo em foco mode pode classificar competências não focadas
  com baixa confiança.** Foco_c2 só dá nota pra C2 — mas o
  diagnóstico tem 40 descritores cobrindo todas C1-C5. Pra C1,
  C3, C4, C5 nesse caso, LLM analisa o texto sem o "ground truth"
  do redato_output → fica mais cauteloso (mais `incerto`).

## Tests

`backend/notamil-backend/redato_backend/tests/diagnostico/`:

- `test_descritores_loader.py` (5 testes): carrega 40, cache,
  YAML inválido, sincronia entre PACKAGE e REPO YAML
- `test_inferencia.py` (7 testes): schema válido (mock OpenAI),
  validação de schema (falta descritor, ID inválido, status
  inválido), cálculo de custo, timeout, texto vazio
- `test_persistencia_e_endpoint.py` (9 testes): persistir
  não-levanta, flag respeitada, pipeline correção não bloqueia,
  schema response, endpoint auth/404/400

Total: 21 cenários novos. Suite vai de 482 → 503.

## Deploy checklist

Antes de testar em prod:

1. Commit + push (deploy automático Railway)
2. **Rodar migration**:
   ```bash
   # Railway shell do serviço backend
   cd backend/notamil-backend/redato_backend/portal
   alembic upgrade head
   ```
   Esperado: aplicar `k0a1b2c3d4e5_envios_diagnostico`. Sem migration,
   `UPDATE envios SET diagnostico = ...` falha com `column "diagnostico"
   does not exist`.

3. Verificar `OPENAI_API_KEY` setada (provavelmente já está, é a
   mesma do FT grader OF14).

4. Smoke: aluno manda foto ENEM (OF14) → bot responde correção em
   ~30-60s → ~12s depois, `envios.diagnostico` é populado:
   ```bash
   psql "$DATABASE_URL" -c "
     SELECT id, diagnostico->>'modelo_usado',
            diagnostico->>'latencia_ms',
            jsonb_array_length(diagnostico->'descritores')
     FROM envios
     WHERE diagnostico IS NOT NULL
     ORDER BY created_at DESC LIMIT 1;
   "
   ```
   Esperado: modelo `gpt-4.1-2025-04-14`, latência ~12000ms, 40
   descritores.

Em caso de problema, rollback rápido:
```bash
# Railway dashboard → backend → variables
REDATO_DIAGNOSTICO_HABILITADO=false
```
Restart → pipeline volta a entregar correções sem rodar diagnóstico.
Migration NÃO precisa ser desfeita (coluna nullable, dados antigos
ficam intactos).
