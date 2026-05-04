# HOWTO — Mapeamento livros → descritores (Fase 5A.1)

**Atualizado:** 2026-05-04

## O que é

Fase 5A.1 expande a sugestão de oficinas pro professor. Antes (Fase 3),
sugestões vinham só do banco — limitadas às ~23 oficinas avaliáveis
pelo Redato. Agora os 3 livros (1S, 2S, 3S) inteiros — 42 oficinas
totais, incluindo conceituais, jogos e diagnósticos — são mapeados
pra os 40 descritores observáveis.

Output: [`mapeamento_livro_descritores.json`](mapeamento_livro_descritores.json),
arquivo estático committed no repo. Endpoint `/perfil` lê esse JSON
em request-time com cache mtime e enriquece a resposta com
`oficinas_livro_sugeridas`.

**Status atual: rascunho heurístico em revisão.** O JSON commited
foi gerado pelo modo `--heuristic` (keyword matching, sem LLM).
Daniel deve re-rodar com `OPENAI_API_KEY` pra upgradear pra
GPT-4.1 quando tiver tempo + crédito.

## Por que rascunho heurístico

A sessão de implementação rodou sem `OPENAI_API_KEY` disponível.
Ao invés de bloquear, o script ganhou modo `--heuristic` (regex
keyword-match) que gera baseline funcionable:

- ✅ UI funciona end-to-end (não fica em estado vazio)
- ✅ Validação ponta-a-ponta da arquitetura possível
- ⚠️ Qualidade pedagógica do mapeamento é INFERIOR ao LLM
  (perde nuance, falsos positivos quando palavra-chave aparece
  só de passagem)
- ⚠️ Rótulo `gerador: "heuristico"` deixa explícito que precisa
  upgrade

UI mostra aviso "Sugestões automáticas em revisão pedagógica —
confirme antes de aplicar" sempre que `status_revisao = em_revisao`.

## Arquitetura

```
┌──────────────────────────┐
│ 3 HTMLs dos livros       │
│ (LIVRO_ATO_1S/2S/3S_PROF)│
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────────┐
│ parser_livros.py         │
│ - extrai oficinas        │
│ - identifica .mf-redato  │
│ - quebra em seções       │
└──────────┬───────────────┘
           │ List[OficinaLivro]
           ▼
┌──────────────────────────────────┐
│ Mapeador (escolha)               │
│ ┌──────────────┐  ┌─────────────┐│
│ │ mapeador.py  │  │ mapeador_   ││
│ │ (GPT-4.1)    │  │ heuristico  ││
│ │ ~$0.85 total │  │ (keyword)   ││
│ │ ~12s/oficina │  │ ~0s grátis  ││
│ └──────────────┘  └─────────────┘│
└──────────┬───────────────────────┘
           │ MapeamentoOficina
           ▼
┌──────────────────────────────────┐
│ scripts/gerar_mapeamento_livros  │
│ - acumula 42 mapeamentos         │
│ - persiste em JSON               │
└──────────┬───────────────────────┘
           │
           ▼
docs/redato/v3/diagnostico/
mapeamento_livro_descritores.json
           │
           │ lido em runtime (cache mtime)
           ▼
┌──────────────────────────┐
│ oficinas_livro.py        │
│ - sugerir_oficinas_livro │
│   (filtro série + lacuna │
│    + intensidade)        │
└──────────┬───────────────┘
           │
           ▼
GET /portal/turmas/{id}/alunos/{aluno_id}/perfil
  → diagnostico_recente.professor.oficinas_livro_sugeridas
```

## Como rodar o pipeline

### Modo LLM (preferido — produção)

```bash
cd backend/notamil-backend
export OPENAI_API_KEY=sk-...
python -m redato_backend.diagnostico.scripts.gerar_mapeamento_livros
```

Custo estimado: **~$0.85** (42 oficinas × ~$0.02 cada).
Tempo: **~10 min** (latência ~14s por oficina).

Output:
```
docs/redato/v3/diagnostico/mapeamento_livro_descritores.json
```

Sai com:
- `gerador: "llm"`
- `modelo_usado: "gpt-4.1-2025-04-14"`
- `status: "em_revisao"` (até Daniel revisar)
- Cada oficina com `descritores_trabalhados`, `competencias_principais`,
  `tipo_atividade`

### Modo heurístico (baseline — usado hoje)

```bash
cd backend/notamil-backend
python -m redato_backend.diagnostico.scripts.gerar_mapeamento_livros --heuristic
```

Custo: **$0**. Tempo: **<5s** total. Útil pra:
- Bootstrap quando OPENAI_API_KEY não disponível
- Ambientes de teste
- Validar arquitetura ponta a ponta

Output marca `gerador: "heuristico"`, `modelo_usado: "heuristico-v1"`.

### Sincronização do JSON pro container Docker

Após gerar o JSON, copiar pra dentro do package pra Dockerfile copiar
no build:

```bash
cp docs/redato/v3/diagnostico/mapeamento_livro_descritores.json \
   backend/notamil-backend/redato_backend/diagnostico/mapeamento_livro_descritores.json
```

Mesma estratégia do `descritores.yaml` (Fase 1). O `oficinas_livro.py`
prefere o path bundled (sempre presente em prod) e cai no path docs/
em dev local.

Em CI/build pipeline futuro, automatizar essa cópia OU mover o
canônico pra dentro do package e deletar a duplicação.

## Schema do JSON

```json
{
  "versao": "1.0",
  "gerado_em": "2026-05-04T...",
  "gerador": "llm" | "heuristico",
  "modelo_usado": "gpt-4.1-2025-04-14" | "heuristico-v1",
  "status": "em_revisao",
  "descricao": "...",
  "estatisticas": {
    "total_oficinas": 42,
    "mapeamentos_ok": 42,
    "mapeamentos_falhos": 0,
    "total_descritores_atribuidos": 94,
    "custo_total_usd": 0.85,
    "latencia_total_min": 9.8
  },
  "oficinas": [
    {
      "codigo": "RJ1·OF11·MF",
      "serie": "1S",
      "oficina_numero": 11,
      "titulo": "CONECTIVOS ARGUMENTATIVOS",
      "tem_redato_avaliavel": false,
      "descritores_trabalhados": [
        {
          "id": "C4.001",
          "intensidade": "alta",
          "razao": "Oficina inteira sobre variedade de conectivos..."
        },
        ...
      ],
      "competencias_principais": ["C4", "C3"],
      "tipo_atividade": "jogo",
      "modelo_usado": "gpt-4.1-2025-04-14",
      "latencia_ms": 14201,
      "custo_estimado_usd": 0.0212,
      "input_tokens": 4521,
      "output_tokens": 612,
      "mapeamento_falhou": false
    },
    ... 42 entries
  ]
}
```

## Como Daniel revisa (sessão futura — Fase 5A.1.review)

Workflow proposto pra revisão pedagógica:

1. **Inspeção do JSON**: rodar script que imprime, pra cada oficina,
   `codigo + titulo + top 3 descritores`. Daniel passa olho na lista.
2. **Substituições manuais**: editar entries individuais no JSON
   diretamente quando LLM errou. Comentário explicando o erro.
3. **Re-rodar pipeline em oficinas problemáticas**: se mais de
   ~5 oficinas estiveram erradas, ajustar prompt do `mapeador.py`
   e re-rodar só nas problemáticas.
4. **Mudar status**: quando satisfeito, mudar `status: "revisado"`
   no JSON. UI deixa de mostrar aviso de revisão.
5. **Commit + push**: PR dedicado `docs(diagnostico): Fase 5A.1.review`.

## Como o frontend consome

Endpoint `GET /portal/turmas/{turma_id}/alunos/{aluno_turma_id}/perfil`
retorna em `diagnostico_recente.professor`:

- `oficinas_sugeridas` (Fase 3) — vêm do BANCO, só Redato-avaliáveis
- `oficinas_livro_sugeridas` (Fase 5A.1) — vêm do JSON do livro
- `mapeamento_livros_status` — `"em_revisao"` | `"revisado"` | `null`

Frontend (componente `MapaCognitivo`) mostra dois sub-blocos
distintos:

- **✅ Atividades no Redato** — Fase 3, sem aviso (já é catálogo confiável)
- **📖 Oficinas no livro** — Fase 5A.1, com aviso "em revisão" quando
  status indica isso. Mostra também:
  - 📚 Conceitual / ✏️ Prática / 🎯 Avaliativa / 🎲 Jogo / 🩺 Diagnóstico
    (do `tipo_atividade`)
  - ★★★ alta / ★★ média / ★ baixa intensidade
  - Razão do mapeamento

## Limitações conhecidas

### Heurístico vs LLM

O baseline heurístico (versão atual em prod) tem limitações:
- **Falsos positivos** quando keyword aparece de passagem (oficina
  menciona "tese" 1 vez na ponte mas não trabalha tese)
- **Falsos negativos** quando oficina trabalha competência sem usar
  exatamente as palavras-chave catalogadas
- **Sem nuance contextual** — não pondera se o foco da oficina é
  realmente aquele descritor ou se só é tangencial

LLM (modo padrão quando OPENAI_API_KEY disponível) reduz drasticamente
esses problemas mas custa $0.85/run.

### Ainda manual

- Re-rodar pipeline é manual via script — não há trigger automático
- Bundle pro Docker exige `cp` manual após gerar (duplicação no
  repo até automatizarmos)
- Revisão pedagógica é manual, sem ferramenta dedicada

### Cobertura por descritor

O baseline heurístico atribuiu **94 descritores** pras 42 oficinas
(média ~2.2 descritores/oficina). LLM tende a atribuir mais (~5/oficina)
mas com filtro de intensidade. RJ2·OF05·MF ficou sem descritores
(0 matches) — esperar LLM cobrir, ou keyword extra na heurística.

## Tests

`backend/notamil-backend/redato_backend/tests/diagnostico/`:

- `test_parser_livros.py` (4): comments, mf-redato-page detection,
  H2/H3 sections, smoke nos 3 livros reais
- `test_mapeador.py` (5): LLM válido, max 8 descritores, ID inválido,
  intensidade inválida, heurístico keyword-match
- `test_oficinas_livro.py` (6): filtro série, threshold intensidade,
  inclusão baixa, JSON ausente, schema endpoint, smoke estrutural

Total: 18 cenários novos. Suite global vai de 554 → 572.

## Deploy checklist

Sem migration nova — Fase 5A.1 é puramente leitura + JSON estático.

1. Push aciona deploy automático Railway
2. JSON bundled em `redato_backend/diagnostico/` é copiado pelo
   Dockerfile (`COPY . .`)
3. Smoke pós-deploy: `/turma/{id}/aluno/{id}` mostra sub-bloco
   "📖 Oficinas no livro" com cards e aviso "em revisão"
4. Pra upgradear pra LLM:
   ```bash
   # Local, com OPENAI_API_KEY:
   cd backend/notamil-backend
   python -m redato_backend.diagnostico.scripts.gerar_mapeamento_livros
   cp docs/redato/v3/diagnostico/mapeamento_livro_descritores.json \
      backend/notamil-backend/redato_backend/diagnostico/mapeamento_livro_descritores.json
   git add ... && git commit -m "chore(diagnostico): regenera mapeamento livros via LLM"
   git push
   ```

Em caso de problema (JSON corrompido, oficinas sumiram):
- Endpoint cai graciosamente pra `oficinas_livro_sugeridas: []`
- UI esconde sub-bloco quando lista vazia (não quebra)
- Re-rodar `--heuristic` é seguro pra restaurar baseline
