# v3 — Tentativa frustrada (2026-04-26)

> Documento de aprendizado. v3 foi revertida após falha estrutural no eval
> contra gabarito INEP. Preservada como referência pra v4.

## Hipótese de design original

A v2 tinha **22.8% de concordância ±40** contra gabarito INEP em 200
redações AES-ENEM, com viés sistemático severo de regressão à média
(+116 pts nas baixas, -150 pts nas altas). Diagnóstico cirúrgico
(`scripts/validation/diagnostic/SUMMARY.md`) apontou que o problema era
**mecanização da rubrica** — thresholds numéricos absolutos onde INEP usa
critério holístico.

A v3 foi desenhada pra atacar isso:

1. **Substituir gradação mecânica por holística** — em vez de "≥10 desvios
   = C1=40", usar "excepcionalidade + reincidência + impacto sobre
   compreensão" (linguagem direta da Cartilha INEP 2025).
2. **Calibrar pela voz da banca real** — 38 comentários oficiais INEP em
   redações nota 1000 (anos 2017-2024) usados como referência operacional.
3. **Detectores explícitos** pra disparadores de rebaixamento:
   `tangenciamento`, `repertorio_de_bolso`, `argumentacao_previsivel`,
   `proposta_vaga_ou_constatatoria`, `proposta_desarticulada`,
   `desrespeito_direitos_humanos`, `limitacao_aos_motivadores`,
   `copia_motivadores_recorrente`.
4. **Output em duas camadas:** audit em prosa (voz INEP) + JSON
   estruturado (`notas`/`flags`/`evidencias`/`audit_prose`).
5. **Skip do two-stage** mecânico — notas vêm direto do juízo qualitativo
   do LLM, sem `_derive_cN_nota` Python.

Estimativa de impacto otimista (pré-eval): mover concordância ±40 de
22.8% para 50-65% em uma iteração.

## Resultado do eval (200 redações AES-ENEM, n=1)

Detalhes em [`REPORT_v2_vs_v3.md`](REPORT_v2_vs_v3.md).

| Métrica | v2 baseline | v3 | Δ |
|---|---:|---:|---:|
| Concordância ±40 | 22.8% | **12.0%** | **-10.8 pts** |
| Concordância ±80 | 37.8% | 19.0% | -18.8 pts |
| MAE total | 137.8 | **216.8** | **+79** |
| ME total (viés) | -62 | **-193** | -131 |
| Latência média/redação | 74.3s | 61.9s | -12.4s |

**v3 piorou em quase todas as métricas globais.** ±80 também caiu, então
não é só calibração de escala — é erro estrutural.

### Onde v3 melhorou (parcial)

- **C1**: ±40 saltou 30.6% → 57.5% (+27 pts). Substituir contagem
  absoluta por "excepcionalidade + reincidência" funcionou.
- **Faixa baixas (≤400)**: ME corrigiu de +116 → -20. O viés de
  inflação foi neutralizado.

### Onde v3 quebrou

- **Faixa 401-799**: ±40 caiu de 25.5% pra 8.1%. ME piorou de -85 → -202.
- **Faixa ≥800**: ±40 caiu de 14.5% pra 1.7%. ME piorou de -150 → -296.
  Catastrófico — Redato v3 dá ~504 em redação nota 800 média.
- **C4**: ±40 caiu 80.3% → 51.0% (-29 pts).
- **Mesma direção do viés que v2 nas altas, magnitude amplificada.**

## Mecanismo do fracasso identificado

A tabela 5b do REPORT_v2_vs_v3.md revela: **TODOS os 7 detectores binários
ativos têm "rebaixa demais quando dispara"** (ME_with entre -167 e -210).
Pior caso:

- **`argumentacao_previsivel` disparou em 94.5% das redações** (189/200),
  incluindo gabarito 1000.

### Hipótese causal

A v3 instrumentou detectores binários com critérios genéricos que **casam
com qualquer redação ENEM real**. A rubrica v3 lista, como indicadores de
"argumentação previsível":

> - Estrutura argumentativa clichê (causa-consequência sem aprofundamento)
> - Argumentos genéricos ("a sociedade precisa mudar", "a educação é a
>   chave", "o governo precisa agir")

Quase TODA redação ENEM passa por algum desses indicadores em algum
parágrafo. O LLM (Sonnet 4.6), com voz de banca operativa instruída a
"identificar disparadores", acha pelo menos um e marca a flag. **Flag
binária + crítica posterior na rubrica = rebaixamento mecânico.**

A v3 quis substituir mecânica por holística mas reintroduziu mecânica via
flags. As flags se comportam como os thresholds da v2, só que em outra
camada — e mais agressivas porque não há contrapeso quantitativo.

Adicional: os 38 comentários INEP usados como calibração são **posteriores
ao gabarito**, não preditivos. O LLM aprendeu o vocabulário e tom da
banca, mas não a calibração da nota — gabarito 1000 não significa
"sem nada a apontar", e o LLM-instruído-a-criticar encontra problemas
e rebaixa, mesmo sem saber que aquela redação é gabarito 1000.

## Decisão: não iterar v3.x

Reverter para v2 (default operacional) e preservar v3 como aprendizado.
**Razão pra não iterar v3.1:**

- O viés ainda é na **mesma direção** que a v2 (deflate em altas), só
  amplificado. Falha estrutural detectada pelo critério do
  README_AB_TEST.md.
- Recalibrar 7 detectores individualmente é trabalho indefinido — e cada
  ajuste corre risco de criar overfit no gabarito de 200 redações.
- Paradigma "detectores binários + voz de banca crítica" parece
  intrinsecamente conflitante com gradação holística. **Mudar paradigma
  é mais barato que iterar dentro dele.**

## Lições pra v4 (paradigma diferente)

1. **Sem flags binárias de rebaixamento.** Gradação INEP é qualitativa
   contínua; flag binária é mecânica disfarçada.
2. **Few-shot positivo > critério estrito.** Em vez de listar
   "indicadores de argumentação previsível", mostrar 3-5 redações nota
   1000 com audit em prosa demonstrando o que **NÃO** rebaixar mesmo
   quando seria possível.
3. **Validar contra gabarito conhecido.** A calibração só pelos
   comentários INEP perdeu o ground truth da nota — incluir redações
   nota 400/600/800/1000 com gabarito explícito como exemplo no prompt.
4. **Não substituir mecânica por nada.** A v2 errava na calibração mas
   tinha previsibilidade. A v3 perdeu previsibilidade e calibrou pra
   pior. Talvez o caminho seja v2 com regras de calibração ajustadas
   (ex: tolerâncias diferentes em faixa alta vs baixa).
5. **Investigar pipeline antes da próxima rubrica.** A latência v3 caiu
   12s — sinal de que self-critique e two-stage não estavam rodando.
   Verificar se o LLM consegue absorver rubricas longas (rubrica_v3.md
   tem ~24KB) ou se há truncamento silencioso.

## Artefatos preservados

```
docs/redato/v3/_failed/
├── README_FAILURE.md          (este arquivo)
├── README_AB_TEST.md          (spec original do experimento)
├── rubrica_v3.md              (rubrica que falhou)
├── system_prompt_v3.md        (system prompt que falhou)
├── REPORT_v2_vs_v3.md         (relatório executivo do eval)
└── runs/
    └── eval_gold_v3_run_20260426_141244.jsonl   (200 resultados crus)
```

Código de pipeline da v3 **mantido intacto** em:
- `backend/notamil-backend/redato_backend/dev_offline.py` — branches
  `REDATO_RUBRICA == "v3"` em `_call_claude_with_tool_inner` e
  `_claude_grade_essay`, `_SYSTEM_PROMPT_V3`, `_SUBMIT_CORRECTION_V3_TOOL`
- `backend/notamil-backend/scripts/validation/run_validation_eval.py` —
  `extract_notas` auto-detecta schema (top-level `notas` vs `cN_audit.nota`)
- `backend/notamil-backend/scripts/validation/compare_v2_v3.py` — relatório
  com tabela 5b (correlação flag × erro) e quarta categoria de verdict
  ("falha estrutural")

Esse código serve de andaime pra v4: trocar `_SYSTEM_PROMPT_V3` e
`_SUBMIT_CORRECTION_V3_TOOL` por versões v4 com paradigma novo, manter
infraestrutura.

## Estado pós-reversão (2026-04-26)

- `REDATO_RUBRICA` não-setado ou `=v2` → pipeline usa rubrica v2 (default seguro).
- Smoke test 5 redações v2 confirmou pipeline operacional sem regressões
  (variância ±40 entre runs é noise floor conhecido do Sonnet 4.6 a temp=0).
- v2 segue como baseline operacional com 22.8% concordância ±40 — não é
  bom o suficiente, mas é melhor que v3 e melhor que rebaixar produção.

---

*Versão 1.0 · 2026-04-26 · Daniel Frechiani (autor pedagógico) + Claude (execução)*
