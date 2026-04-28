# Rodando a Redato localmente (modo dev-offline)

Este modo sobe backend e frontend **sem nenhuma dependência externa**
(Firebase, BigQuery, Firestore, Cloud Functions) — tudo é stubbed em memória
com dados semeados. Serve pra validar o fluxo de correção (submit → polling
→ exibição de resultado → feedback do professor → tutor) sem custo e sem
credenciais.

## O que funciona nesse modo

- Login dos 3 perfis (aluno, professor, admin)
- Submissão de redação em texto + **correção real via Claude** (com
  `ANTHROPIC_API_KEY`) ou stub determinístico (sem a key)
- Submissão de redação via OCR (imagem) + transcrição com trechos `<uncertain>`
- Dashboards do aluno e do professor
- Professor abrir redação de aluno, escrever feedback, salvar, aluno ver
- **Tutor chat real** via Claude (mesma key) ou respostas canônicas
- Gestão admin (criar turma, professor, tema)

## O que NÃO funciona

- OCR real (sempre devolve o mesmo parágrafo demo — usar o campo de texto)
- Envio de emails
- Persistência entre reinícios do backend (tudo volta ao estado de seed)

---

## 1. Backend

```bash
cd backend/notamil-backend

# Instale apenas as deps mínimas — não precisa de poetry nem das deps GCP
pip install -r requirements-dev.txt

# Suba com a flag de offline
REDATO_DEV_OFFLINE=1 uvicorn main:app --reload --port 8080
```

Teste: `curl http://localhost:8080/health` → `{"status":"healthy"}`

Ver a doc interativa do FastAPI em `http://localhost:8080/docs`.

### Correção real via Claude (opcional, mas é o que valida a correção de verdade)

1. Pegue uma API key da Anthropic em https://console.anthropic.com/settings/keys
   (precisa cadastrar um cartão; conta nova vem com US$ 5 de crédito).
2. Coloque a key em `backend/notamil-backend/.env` (já coberto pelo `.gitignore`):

   ```
   ANTHROPIC_API_KEY=sk-ant-...
   ```

3. Suba o backend normal:

   ```bash
   REDATO_DEV_OFFLINE=1 uvicorn main:app --reload --port 8080
   ```

Cada submissão chama `claude-sonnet-4-6` com:
- **Parte A do system prompt canônico da Redato** (carregado de
  `docs/redato/redato_system_prompt.md` em module-load, ~11k tokens com a
  rubrica ENEM completa + calibração v1.3 da Seção 6)
- **Prompt caching** — 1ª chamada custa o preço cheio, chamadas seguintes
  (dentro de 5 min) pagam 10% e economizam alguns segundos
- **Tool use** com schema estrito — Claude emite JSON garantido: notas
  INEP discretas, feedback por competência com pontos_fortes e
  pontos_atencao (trecho literal + problema + sugestão), 3 próximos
  movimentos, observações gerais
- **Submit assíncrono** — o `/essays/submit` retorna em ~0ms com status
  `processing`. A correção roda em background. Frontend faz polling a cada
  3s mostrando progresso fluido

### Flags de performance / qualidade

| Env var | Efeito |
|---|---|
| `REDATO_CLAUDE_MODEL=claude-opus-4-7` | Usa Opus em vez de Sonnet para a correção principal. **Atenção:** Opus tem comportamento inconsistente com o schema v2 atual (retorna `{"$PARAMETER_NAME": ...}` como placeholder). Use só com `REDATO_ENSEMBLE >= 3` para mascarar via majority vote. Custa ~5x mais. |
| `REDATO_ENSEMBLE=3` | Ativa ensemble de N runs paralelos com majority vote nos booleanos do audit, mediana nos counts, união deduplicada nas listas. Detecta e descarta placeholders do Opus automaticamente. Custo: N× tempo e dinheiro. Recomendado para simulados. |
| `REDATO_PREVIEW_MODEL=claude-haiku-4-5` | Modelo usado para o preview streaming (default Haiku, rápido e barato). |
| `REDATO_EXTENDED_THINKING=1` | Ativa extended thinking na correção principal (Claude raciocina antes de emitir o JSON). Adiciona ~20-30s, melhora calibração em casos ambíguos. Use para simulados. |
| `REDATO_SELF_CRITIQUE=1` | Ativa um 2º pass que reavalia a correção contra a rubrica e o adendo 6.5.1 de C5. Adiciona ~30s e ~2x de custo, pega falsos-negativos em C5/C3. Use em simulados finais. |

Custo estimado com a configuração padrão (Sonnet 4.6 + preview Haiku):
- Base: ~US$ 0,03 por correção
- Com extended thinking: ~US$ 0,05
- Com self-critique: ~US$ 0,06
- Com ambos: ~US$ 0,08
- Opus 4.7 + thinking + critique: ~US$ 0,30

Latência típica (após o cache de system prompt ficar quente):
- Preview (primeira impressão no modal): **2-4s**
- Correção completa visível:
  - Sonnet sem flags: **30-45s**
  - Sonnet + extended thinking: 50-70s
  - Sonnet + self-critique: 60-80s
  - Opus + thinking + critique: 90-120s

Se a key não estiver setada, o sistema cai automaticamente no stub determinístico
(notas fixas 760/1000) sem quebrar o fluxo.

### Como a arquitetura otimizada funciona

O backend executa DUAS chamadas concorrentes ao Claude quando a key está setada:

1. **Preview streaming** (Haiku 4.5) — ~2s para começar a emitir; ~4s total.
   Produz um parágrafo curto de "primeira impressão" que o frontend exibe
   no modal enquanto a correção principal ainda roda. Escreve no Firestore
   conforme os tokens chegam.
2. **Correção completa** (Sonnet 4.6 + tool_use + prompt caching) — ~30-45s.
   Retorna o JSON estruturado com notas, feedback por competência, 3
   próximos movimentos.

O frontend faz polling a cada 3s e renderiza o preview assim que ele chega.
Quando a correção completa termina, redireciona pra `/correcao` com os dados
estruturados. O aluno SENTE que a correção é quase instantânea (2s pra ver
algo) mesmo que o total seja 30-45s.

## 2. Frontend

```bash
cd frontend/notamil-frontend

npm install

# .env.local — duas linhas, o resto não é usado em offline
cat > .env.local <<'EOF'
NEXT_PUBLIC_API_BASE_URL=http://localhost:8080
NEXT_PUBLIC_DEV_OFFLINE=1
EOF

npm run dev
```

Acesse `http://localhost:3000`.

## 3. Usuários demo (senha `redato123` para todos)

| Perfil | Email | Login em |
|---|---|---|
| Aluno | `aluno@demo.redato` | `/login` |
| Professor | `professor@demo.redato` | `/professor-login` |
| Admin da escola | `admin@demo.redato` | `/admin-interno-login` |

A seed vem com:
- Escola Demo, Turma "Demo — 3º ano", Admin demo dono da escola
- Professor demo atribuído à turma
- Aluno demo matriculado na turma
- Tema "O impacto das redes sociais na saúde mental dos jovens"

## 4. Roteiro de validação da correção (5 min)

### Parte A — aluno submete e vê a correção

1. Vá em `/login` → `aluno@demo.redato` / `redato123` → redireciona pra `/select`
2. Clique em "Escrever texto" → `/submit-essay/text`
3. Tema: escolha "O impacto das redes sociais na saúde mental dos jovens"
4. Cole uma redação qualquer (precisa ≥ 100 chars) e clique "Enviar Redação"
5. Modal "Processando..." → depois de ~20s (1 ciclo de polling) mostra
   "Redação corrigida!" com botões **Dashboard** e **Ver Correção**
6. Clique "Ver Correção" → vê nota, 5 competências, barras de progresso.
   - **Com `ANTHROPIC_API_KEY`:** correção real do Claude sobre a sua redação.
     Textos diferentes devolvem notas e feedback diferentes.
   - **Sem a key:** notas fixas 760/1000 em toda submissão (stub).
   Se houver feedback do professor (Parte B abaixo), aparece no card azul

### Parte B — professor deixa feedback

1. Nova aba/sessão: `/professor-login` → `professor@demo.redato` / `redato123`
2. Vai pra `/professor` → lista a turma demo
3. Clique na turma → vê o aluno demo → clique no aluno → modal da redação
4. Role até o bloco **"Feedback do Professor"** (abaixo da nota)
5. Escreva um comentário e clique "Salvar feedback" → confirmação "Salvo em..."
6. Volte pra aba do aluno, recarregue `/correcao` — o card azul com o
   feedback aparece logo abaixo da nota

### Parte C — OCR com aviso de baixa confiança

1. Como aluno: `/select` → "Enviar foto" → faça upload de qualquer imagem
   (o OCR stub não olha o conteúdo — devolve texto fixo com accuracy 86%)
2. Redireciona pra `/submit-essay/text` com o texto pre-preenchido
3. Como 86% > 80%, o banner amarelo NÃO aparece. Pra testar o banner,
   edite `redato_backend/dev_offline.py` e troque `accuracy: 0.86` → `0.65`

### Parte D — tutor

1. Na tela de correção (`/study-plan`), clique numa competência → lista de erros
2. Clique no erro destacado → chat widget abre com mensagem inicial
3. Envie uma pergunta → o tutor responde com template canônico

### Parte E — admin cria turma/tema

1. `/admin-interno-login` → `admin@demo.redato` / `redato123` → `/admin-interno`
2. Crie uma turma nova → aparece na lista
3. Crie um tema vinculado à turma nova

## 5. Debug

- **Backend não sobe**: olhe os logs. Se for erro de import, falta dep em
  `requirements-dev.txt`. Se for erro de stub, imprima a query que não
  casou (o stub já faz `print("[dev_offline] unmatched SELECT: ...")`)
- **Login dá 401**: o token dev tem que começar com `dev:`. Cheque no
  devtools Network o header `Authorization` da chamada pra `/auth/login`
- **Correção fica em polling eterno**: o `/essays/submit` precisa retornar
  `status: "completed"` imediatamente. Se estiver em `processing`, o stub
  de Cloud Function não rodou — confira se `REDATO_DEV_OFFLINE=1` está
  setado
- **CORS em dev**: o backend loga um warning sobre wildcard. Ignore em dev

## 6. Voltar pro modo real (GCP)

Remova `REDATO_DEV_OFFLINE=1` do ambiente do backend e
`NEXT_PUBLIC_DEV_OFFLINE=1` do `.env.local` do frontend. Configure as
credenciais reais conforme a seção "Credenciais obrigatórias" na
conversa anterior.
