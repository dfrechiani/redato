# IMPLEMENTATION_GUIDE_NEXT.md · Redato — Próximas 4 frentes

> Continuação do trabalho pós-plateau identificado em abril 2026.
> Estado de partida:
> - INEP pass rate: 8-9/10 (oscila por rodada)
> - STRICT pass rate: 6-8/10
> - Plateau identificado em prompt + few-shots + derivação mecânica com Sonnet 4.6
> - Ensemble (`REDATO_ENSEMBLE=N`) já implementado em `_call_claude_with_tool`
> - 7 estáveis, 1 falha consistente (teste_04), 2 oscilantes
> - Bug do Opus com `$PARAMETER_NAME` bloqueia upgrade direto
> 
> **Arquitetura de partida:**
> - Backend Python em `backend/notamil-backend/redato_backend/`
> - Pipeline central em `dev_offline.py` (~3.300 linhas, com docstring "Dev offline mode")
> - Calibration set em `docs/redato/v2/canarios.yaml` (11 canários, schema v2)
> - Audits estruturados via tool calls Anthropic (schemas em `_c1_audit_schema` … `_c5_audit_schema`)

Este documento descreve **4 tarefas** que atacam frentes complementares para sair do plateau sem fine-tuning. Cada uma é independente — podem ser feitas em qualquer ordem, ou em paralelo por desenvolvedores diferentes.

| Tarefa | O que resolve | Custo de implementação | Impacto esperado |
|---|---|---|---|
| 9 — Pré-flag mecânico de repetição | Bias C3↔C4 que faz teste_04 falhar | Baixo (1-2 dias) | Resolve teste_04 sem retreinar |
| 10 — Two-stage Opus | Bug do Opus `$PARAMETER_NAME` | Médio (3-4 dias) | Desbloqueia uso de Opus 4.7 |
| 11 — Confidence metadata + HITL | Casos oscilantes vão para revisão humana | Médio (3-5 dias) | Reduz erro em produção sem mexer no modelo |
| 12 — Prompt caching | Custo de ensemble | Baixo (1 dia) | -90% custo de input em runs cacheadas |

---

## Tarefa 9 — Pré-flag mecânico de repetição lexical

**Prioridade:** Alta — resolve a falha sistemática do teste_04 sem retreinamento.

### Contexto técnico

Sonnet 4.6 confunde **repetição lexical** (problema de C4 — coesão) com **falta de progressão semântica** (problema de C3 — argumentação). Em texto onde os dois co-ocorrem (caso comum), o modelo marca `c3_audit.progressivas = false` mesmo quando os argumentos progridem semanticamente. Esse bias é sistemático: ensemble N=3 não resolve porque os 3 runs erram juntos.

A solução é **mudar o framing antes do raciocínio do Claude**, não depois. Em vez de instruir "não confunda repetição com falta de progressão" (instrução negativa, ignorada por LLMs), executamos uma **detecção determinística de repetição** ANTES da chamada e injetamos no prompt um aviso afirmativo: "este texto tem as seguintes repetições lexicais (lista). Estas são problema de C4. Avalie C3 desconsiderando essa lista — foque em progressão **semântica** dos argumentos."

### Arquivos a criar

```
backend/notamil-backend/redato_backend/
├── audits/
│   ├── __init__.py
│   └── lexical_repetition_detector.py    ← NOVO (já fornecido)
└── tests/
    └── audits/
        └── test_lexical_repetition_detector.py
scripts/
├── calibrate_repetition_threshold.py      ← NOVO (já fornecido)
└── ab_tests/
    └── threshold_calibration.json         ← gerado pelo calibrador
```

### Detector — `lexical_repetition_detector.py`

**Fornecido pronto** no pacote desta entrega. Características principais:

- Stopwords PT-BR enxutas (~80 termos: artigos, preposições, pronomes)
- Pseudo-lemmatization heurística (plurais, gênero) — agrupa "exclusão/exclusões/excluídas" sob mesma chave
- Configuração via 3 constantes no topo do módulo:
  - `DEFAULT_MIN_OCCURRENCES = 4` — limiar inicial, **a calibrar antes de implementar**
  - `MIN_SPAN_FOR_TRIPLE = 50` — count == 3 só qualifica se espalhado pelo texto
  - `SUPPRESS_FLAG_IF_TTR_ABOVE = None` — anti-falso-positivo em texto longo+diverso
- Helper `maybe_inject_repetition_addendum(activity_context, student_text)` para integração one-call

### Integração em `dev_offline.py`

**Local exato (linha aproximada 1500):** dentro de `_call_claude_with_tool_inner`, no ponto onde `activity_context` é montado, ANTES da chamada à API.

```python
# No topo do arquivo, junto com os outros imports do módulo:
from redato_backend.audits.lexical_repetition_detector import (
    maybe_inject_repetition_addendum,
)

# Dentro de _call_claude_with_tool_inner, logo após montar activity_context
# e ANTES de qualquer chamada à API:
if os.environ.get("REDATO_REPETITION_FLAG", "1") == "1":
    activity_context = maybe_inject_repetition_addendum(
        activity_context, essay_text
    )
```

**Variável de ambiente para A/B controlado:**
- `REDATO_REPETITION_FLAG=0` → desliga, comportamento atual (baseline)
- `REDATO_REPETITION_FLAG=1` → liga (default), aplica detector
- Permite rodar A/B sem precisar reverter código

### Antes de implementar — calibrar limiar

A constante `DEFAULT_MIN_OCCURRENCES = 4` é chute. Rodar o calibrador primeiro:

```bash
cd backend/notamil-backend
python -m redato_backend.scripts.calibrate_repetition_threshold \
    --canarios docs/redato/v2/canarios.yaml \
    --output scripts/ab_tests/threshold_calibration.json
```

O script:
1. Roda o detector contra os 11 canários v2 + 5 textos sintéticos com ground truth
2. Faz grid search no espaço (`min_occurrences` ∈ {3,4,5,6}) × (`ttr_max_for_suppress` ∈ {None, 0.55, 0.50, 0.45, 0.40})
3. Recomenda config ótima por F1
4. Lista falsos-positivos e falsos-negativos remanescentes

**Heurística de ground truth** para os canários: o calibrador infere "expected_repetition_flag" automaticamente quando:
- Canário tem `gabarito.c4 ≤ 120` (coesão baixa indica repetição)
- OU tem `structural_check.kind` mencionando `mechanical_repetition` ou `most_used_connector`
- OU canário tem campo opcional `expected_repetition_flag` (override manual)

Se quiser overrides, adicione no canários.yaml:
```yaml
canarios:
- id: c4_mechanical_cohesion
  expected_repetition_flag: true   # override manual
  # ... resto do canário
```

Aplicar a config recomendada ajustando as constantes em `lexical_repetition_detector.py`.

### Critérios de aceitação

- [ ] Calibrador roda e recomenda configuração com F1 ≥ 0.85 no test set combinado
- [ ] Detector unitário tem testes em `tests/audits/test_lexical_repetition_detector.py` cobrindo:
  - Texto sem repetição → `has_significant_repetition = False`
  - Texto com repetição óbvia (ex: "violência" 6×) → `True`
  - Texto borderline (3 ocorrências espalhadas) → comportamento consistente com config calibrada
  - Texto longo com TTR alto → suprime flag se `SUPPRESS_FLAG_IF_TTR_ABOVE` configurado
- [ ] **Teste_04 (`c4_mechanical_cohesion`) passa STRICT** após integração — critério primário de sucesso
- [ ] Os 7 canários estáveis continuam passando (sem regressão) — rodar `run_calibration_eval.py`
- [ ] Performance: detector roda em < 50ms para texto de 30 linhas
- [ ] Variável `REDATO_REPETITION_FLAG` documentada no DEV.md

### Plano de validação A/B

Ver documento separado **`AB_TEST_TASK9.md`** com metodologia experimental, scripts de execução e critérios de decisão automatizados.

---

## Tarefa 10 — Two-stage Opus (resolver bug do `$PARAMETER_NAME`)

**Prioridade:** Média-alta — desbloqueia upgrade para Opus 4.7 sem refazer schema.

### Contexto técnico

Opus 4.7 às vezes emite literalmente o template de parâmetro (`$PARAMETER_NAME`) em vez do valor, especialmente em schemas complexos com muitos campos required aninhados (caso dos schemas `_c1_audit_schema` ... `_c5_audit_schema` em `dev_offline.py`).

Workarounds tradicionais:
1. **Flatten do schema** — perde estrutura útil
2. **`max_tokens=12000+`** — paliativo caro

A solução **two-stage** divide o trabalho:

- **Stage 1 (Opus 4.7):** raciocínio textual estruturado — Opus produz análise por competência em prosa estruturada (markdown), sem schema rígido. Aqui Opus brilha (raciocínio sofisticado, identificação de problemas sutis).
- **Stage 2 (Sonnet 4.6 ou Haiku 4.5):** conversão texto → JSON — modelo menor, com schema estrito via tool, apenas extrai valores e formata.

Trade-offs:
- **Mais lenta:** 2 chamadas em série (~10-15s adicionais)
- **Mais barata que Opus + max_tokens=12000:** Haiku 4.5 a $1/MTok input vs Opus a $15/MTok
- **Mais robusta:** Opus não precisa preencher 50 campos required — só raciocinar

### Onde integrar em `dev_offline.py`

A função existente `_call_claude_with_tool_inner` (linha ~1700-2000 estimada, dentro do bloco "Pipeline Claude") faz **chamada única** com tool. A nova função `_call_claude_two_stage` deve ser implementada **lado a lado**, e `_claude_grade_essay` decide qual usar via env var.

```python
# Em dev_offline.py, próximo a _call_claude_with_tool:

REDATO_OUTPUT_MODE = os.environ.get("REDATO_OUTPUT_MODE", "single")
REDATO_REASONING_MODEL = os.environ.get("REDATO_REASONING_MODEL", "claude-opus-4-7")
REDATO_EXTRACTION_MODEL = os.environ.get("REDATO_EXTRACTION_MODEL", "claude-haiku-4-5")

STAGE1_REASONING_TEMPLATE = """## Modo de saída: análise estruturada em prosa

Você produzirá uma análise por competência em **prosa estruturada**, NÃO em JSON.

Use exatamente este formato (markdown), sem desviar:

# Análise da redação

## Identificação
- Tema detectado: [tema em uma frase]
- Linhas estimadas: [número]
- Palavras: [número]

## Competência 1 — Norma culta
- Nota: [40|80|120|160|200]
- Desvios graves identificados:
  - "[trecho exato]" — [categoria] — correção: [forma correta]
  - (continue para cada desvio)
- Desvios médios:
  - (similar)
- Justificativa da nota: [3-5 linhas]

## Competência 2 — Tema e repertório
- Nota: [40|80|120|160|200]
- Tema atendido: [sim/parcial/não]
- Repertórios identificados:
  - "[trecho]" — [categoria: filosofico|sociologico|...] — [legitimidade] — [produtividade]
- Justificativa: [3-5 linhas]

## Competência 3 — Argumentação
- Nota: [40|80|120|160|200]
- Tese identificável: [sim/não — se sim, transcreva]
- Argumentos progridem semanticamente: [sim/não]
- Contradições: [nenhuma | descreva]
- Autoria: [configurada/indícios/ausente]
- Justificativa: [3-5 linhas]

## Competência 4 — Coesão
- Nota: [40|80|120|160|200]
- Diversidade de recursos coesivos: [pontual|regular|constante|expressiva]
- Conector mais usado: [conector] — [N] vezes
- Repetição mecânica detectada: [sim/não]
- Justificativa: [3-5 linhas]

## Competência 5 — Proposta
- Nota: [40|80|120|160|200]
- Elementos identificados: [agente, ação, meio, finalidade, detalhamento — quais presentes]
- Ação concreta presente: [sim/não — transcreva se sim]
- Justificativa: [3-5 linhas]

## Total
- Nota: [soma das 5]

[FIM_DA_ANALISE]
"""

STAGE2_EXTRACTION_PROMPT = """Você é um conversor de análises textuais para JSON estruturado.

Receberá uma análise de redação em prosa markdown e deve extrair os campos
para o schema da Redato usando a tool fornecida.

REGRAS:
- Apenas EXTRAIA valores do texto fornecido. Não interprete, não infira.
- Se um campo está ausente no texto, use o valor default do schema (null/0/false).
- Notas devem ser uma das 6 oficiais: 0, 40, 80, 120, 160, 200.
- O total deve ser a soma exata das 5 notas individuais.
"""


def _call_claude_two_stage(
    rubric: str,
    essay_text: str,
    activity_context: str,
    tool_schema: dict,
) -> dict:
    """
    Pipeline de duas chamadas:
    Stage 1 (Opus): raciocínio em prosa
    Stage 2 (Haiku): extração para JSON via tool
    """
    import anthropic
    client = anthropic.Anthropic()

    # STAGE 1: raciocínio com Opus
    stage1_system = f"{rubric}\n\n{STAGE1_REASONING_TEMPLATE}"
    stage1_user = f"{activity_context}\n\nRedação do aluno:\n\n{essay_text}"

    stage1_response = client.messages.create(
        model=REDATO_REASONING_MODEL,
        max_tokens=4096,
        system=stage1_system,
        messages=[{"role": "user", "content": stage1_user}],
    )

    stage1_text = "".join(
        b.text for b in stage1_response.content if b.type == "text"
    )

    # Validação rápida — Stage 1 truncou?
    if "[FIM_DA_ANALISE]" not in stage1_text:
        raise RuntimeError(
            "Stage 1 truncated: missing [FIM_DA_ANALISE] marker. "
            f"Output ended with: ...{stage1_text[-200:]}"
        )

    # STAGE 2: extração com Haiku
    stage2_response = client.messages.create(
        model=REDATO_EXTRACTION_MODEL,
        max_tokens=2048,
        system=STAGE2_EXTRACTION_PROMPT,
        tools=[tool_schema],
        tool_choice={"type": "tool", "name": tool_schema["name"]},
        messages=[
            {
                "role": "user",
                "content": f"Converta esta análise para JSON usando a tool:\n\n{stage1_text}",
            }
        ],
    )

    tool_use = next(
        (b for b in stage2_response.content if b.type == "tool_use"),
        None,
    )
    if tool_use is None:
        raise RuntimeError("Stage 2 did not produce tool_use block")

    return {
        "audit": tool_use.input,
        "stage1_text": stage1_text,
        "stage1_usage": dict(stage1_response.usage),
        "stage2_usage": dict(stage2_response.usage),
    }
```

Em `_claude_grade_essay`, adicionar branch:

```python
if REDATO_OUTPUT_MODE == "two_stage":
    result = _call_claude_two_stage(rubric, essay_text, activity_context, tool_schema)
else:
    result = _call_claude_with_tool(...)  # fluxo atual
```

### Interação com ensemble

Two-stage é **ortogonal a ensemble**. Pode rodar:
- Two-stage solo (`REDATO_OUTPUT_MODE=two_stage`, `REDATO_ENSEMBLE` não setado)
- Two-stage com ensemble (`REDATO_OUTPUT_MODE=two_stage`, `REDATO_ENSEMBLE=3`) — N runs do pipeline two-stage

A função `_merge_ensemble_results` opera em cima do JSON final, então não precisa mudar.

### Critérios de aceitação

- [ ] `_call_claude_two_stage` produz JSON válido contra `_c1_audit_schema` ... `_c5_audit_schema` em 100% das execuções nos 11 canários
- [ ] **Zero ocorrências de `$PARAMETER_NAME`** no output, mesmo com Opus reasoning
- [ ] Pass rate INEP igual ou superior ao single-call com Sonnet (≥ 8/10)
- [ ] Latência total < 25s para redação completa
- [ ] Custo por correção logado e comparável: Sonnet single ~$0.05 vs two-stage ~$0.20-0.30
- [ ] Erro de truncamento `[FIM_DA_ANALISE]` ausente é capturado e relançado claramente

### Notas

- O Stage 1 não usa tool — Opus produz texto livre estruturado, onde é mais confiável
- O Stage 2 usa Haiku com tarefa simples (extração) — onde Haiku é suficiente
- Validação `[FIM_DA_ANALISE]` é canário rápido para detectar truncamento antes de gastar Stage 2
- Se Stage 1 trunca, retornar erro claro — não silenciosamente partir para Stage 2 com texto incompleto

---

## Tarefa 11 — Confidence metadata + Human-in-the-loop

**Prioridade:** Alta para produção — protege qualidade entregue ao aluno em casos oscilantes.

### Contexto pedagógico

Os 2 canários oscilantes representam casos onde mesmo avaliadores humanos do INEP discordam. Em produção, nem toda correção precisa ir direto ao aluno — correções de **alta variância** entre runs do ensemble podem ser segregadas para revisão do professor antes de chegar ao estudante.

Isso transforma a Redato de "corretor automático" em "corretor automático com triagem de incerteza" — alinhado com o posicionamento pedagógico do produto (assistente do professor, não substituta).

### Arquivos a modificar/criar

```
backend/notamil-backend/redato_backend/
├── ensemble/
│   ├── __init__.py
│   └── confidence.py                    ← NOVO
└── routing/
    ├── __init__.py
    └── correction_router.py             ← NOVO
```

E modificar `dev_offline.py`:
- `_merge_ensemble_results` precisa anexar `_confidence` ao output
- `_persist_grading_to_bq` precisa persistir o estado de revisão (campo novo na tabela `essay_analysis`)

### Cálculo de confidence — `confidence.py`

```python
"""Confidence metadata calculator for ensemble runs."""
from dataclasses import dataclass, field, asdict
from typing import Literal


@dataclass
class CompetencyAgreement:
    competency: Literal["c1", "c2", "c3", "c4", "c5"]
    notes_per_run: list[int]
    agreement: float           # 0-1: % de runs que concordam com a moda
    spread: int                 # diferença max-min em pontos
    modal_note: int
    is_unanimous: bool

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ConfidenceMetadata:
    ensemble_n: int
    per_competency: list[CompetencyAgreement]
    overall_agreement: float
    total_spread: int
    confidence_level: Literal["high", "medium", "low"]
    flags: list[str] = field(default_factory=list)
    needs_human_review: bool = False

    def to_dict(self) -> dict:
        return {
            "ensemble_n": self.ensemble_n,
            "per_competency": [c.to_dict() for c in self.per_competency],
            "overall_agreement": self.overall_agreement,
            "total_spread": self.total_spread,
            "confidence_level": self.confidence_level,
            "flags": self.flags,
            "needs_human_review": self.needs_human_review,
        }


def calculate_confidence(ensemble_results: list[dict]) -> ConfidenceMetadata:
    """
    Recebe lista de results de runs do ensemble (cada um com `notas: {c1..c5, total}`)
    e retorna metadata de confidence.
    """
    if len(ensemble_results) < 2:
        return ConfidenceMetadata(
            ensemble_n=len(ensemble_results),
            per_competency=[],
            overall_agreement=1.0,
            total_spread=0,
            confidence_level="high",
            flags=["single_run"],
            needs_human_review=False,
        )

    competencias = ["c1", "c2", "c3", "c4", "c5"]
    per_comp = []

    for comp in competencias:
        notes = [r["notas"][comp] for r in ensemble_results]
        counts: dict[int, int] = {}
        for n in notes:
            counts[n] = counts.get(n, 0) + 1
        modal_note, modal_count = max(counts.items(), key=lambda kv: kv[1])

        per_comp.append(CompetencyAgreement(
            competency=comp,
            notes_per_run=notes,
            agreement=modal_count / len(notes),
            spread=max(notes) - min(notes),
            modal_note=modal_note,
            is_unanimous=(modal_count == len(notes)),
        ))

    overall_agreement = sum(c.agreement for c in per_comp) / len(per_comp)
    totals = [r["notas"]["total"] for r in ensemble_results]
    total_spread = max(totals) - min(totals)

    flags: list[str] = []
    for c in per_comp:
        if c.spread >= 80:
            flags.append(f"high_spread_{c.competency}")
        if c.agreement < 0.5:
            flags.append(f"disagreement_{c.competency}")
    if total_spread >= 200:
        flags.append("high_total_spread")
    if overall_agreement < 0.6:
        flags.append("low_overall_agreement")

    if overall_agreement >= 0.85 and total_spread <= 80:
        confidence_level = "high"
    elif overall_agreement >= 0.65 and total_spread <= 160:
        confidence_level = "medium"
    else:
        confidence_level = "low"

    return ConfidenceMetadata(
        ensemble_n=len(ensemble_results),
        per_competency=per_comp,
        overall_agreement=round(overall_agreement, 3),
        total_spread=total_spread,
        confidence_level=confidence_level,
        flags=flags,
        needs_human_review=(confidence_level == "low"),
    )
```

### Modificar `_merge_ensemble_results` em `dev_offline.py`

Adicionar no final da função, após produzir o resultado mesclado:

```python
# Existing: produce merged result via majority/median
merged_result = ...  # current logic

# NEW: anexa metadata de confidence
from redato_backend.ensemble.confidence import calculate_confidence
confidence = calculate_confidence(individual_results)
merged_result["_confidence"] = confidence.to_dict()

return merged_result
```

### Roteador — `correction_router.py`

```python
"""Routes corrections based on ensemble confidence."""
from typing import Literal

ReviewState = Literal[
    "auto_delivered",
    "pending_review",
    "reviewed_approved",
    "reviewed_rejected",
]

# Atividades de alto stake que sempre acionam revisão em confidence média ou baixa
HIGH_STAKES_ACTIVITIES = {
    "RJ2_SIM1", "RJ2_SIM2",
    "RJ3_OF09_MF", "RJ3_OF11_MF",
    "RJ3_OF14_MF", "RJ3_OF15_MF",
}


def route_correction(
    correction: dict,
    *,
    student_id: str,
    activity_id: str,
) -> dict:
    """
    Decide se a correção vai direto pro aluno ou para fila de revisão.
    
    Returns:
        dict com keys:
        - state: ReviewState
        - visible_to_student: bool
        - review_record: dict (a persistir em correction_review se pending)
    """
    conf = correction.get("_confidence")

    # Sem ensemble (N=1) → sem trigger automático
    if not conf or conf.get("ensemble_n", 1) < 2:
        return {
            "state": "auto_delivered",
            "visible_to_student": True,
            "review_record": None,
        }

    is_high_stakes = activity_id in HIGH_STAKES_ACTIVITIES
    level = conf["confidence_level"]

    if level == "high":
        return {
            "state": "auto_delivered",
            "visible_to_student": True,
            "review_record": None,
        }

    if level == "medium" and not is_high_stakes:
        return {
            "state": "auto_delivered",
            "visible_to_student": True,
            "review_record": None,
        }

    return {
        "state": "pending_review",
        "visible_to_student": False,
        "review_record": {
            "student_id": student_id,
            "activity_id": activity_id,
            "state": "pending_review",
            "flags": conf["flags"],
            "confidence_level": level,
        },
    }
```

### Persistência

Adicionar campo `review_state` à tabela `essay_analysis` (no schema BigQuery — atualmente fake em `dev_offline.py`). Em produção, criar tabela `correction_review` correlacionada.

Migration sketch (em `_seed` ou em SQL real):
```sql
ALTER TABLE essay_analysis ADD COLUMN review_state STRING DEFAULT 'auto_delivered';
ALTER TABLE essay_analysis ADD COLUMN confidence_metadata JSON;
```

### UI do professor

Mockup visual em **`teacher_dashboard_mockup.html`** (artefato fornecido). Renderiza com paleta dark da Redato (#0f1117 + lime #b9f01c). Estrutura mínima do componente:

- Topbar com brand + contexto (turma, simulado)
- 4 metric cards: Pendentes, Aprovadas hoje, Tempo médio, Concordância 3/3
- Lista de cards `pending_review`, em ordem de prioridade (low confidence primeiro)
- Para cada card: scores em grid de 5 com runs do ensemble visíveis (`160·120·80`), bloco diagnóstico com flags em código, ações (Ver completa / Aprovar / Editar / Rejeitar)

### Critérios de aceitação

- [ ] `calculate_confidence` retorna metadata correto para os 11 canários
- [ ] Os 7 canários estáveis recebem `confidence_level = 'high'` em ≥ 80% dos ensembles
- [ ] Os 2 oscilantes recebem `confidence_level = 'medium' ou 'low'` em ≥ 70% dos ensembles
- [ ] Roteador encaminha corretamente para `pending_review` quando aplicável
- [ ] Campo `review_state` persiste corretamente
- [ ] Endpoint `/professor/revisao` lista correções `pending_review` (UI fica para sprint seguinte)

### Notas pedagógicas

- **Latência:** correções em `pending_review` ficam invisíveis para o aluno. UX no app deve mostrar mensagem honesta: "Sua correção está em revisão pelo professor — você será notificado quando estiver pronta".
- **Tempo de revisão:** monitorar tempo médio entre `pending_review` e `reviewed_approved`. Se > 24h, sistema está sobrecarregando o professor — relaxar critérios (subir limiar de spread).

---

## Tarefa 12 — Prompt caching

**Prioridade:** Alta — barato de implementar, retorno imediato em ensemble e simulados.

### Contexto técnico

A rubrica + few-shots + schema descrito em `_load_rubric` e nos schemas dos audits totaliza ~12-15k tokens estáveis em cada chamada à API. Em ensemble N=3, sem caching, paga-se 3× esses tokens em cada correção. Com caching, paga-se 1× cache write + 2× cache reads (10% do custo).

Cálculo aproximado:
- **Sem cache:** 3 × 13.000 × $3/MTok = $0.117 só de input
- **Com cache:** 1 × 13.000 × $3.75/MTok (cache write 1.25×) + 2 × 13.000 × $0.30/MTok = $0.057
- **Economia:** ~50% em ensemble N=3

Em 10.000 correções/mês com ensemble: ~$600/mês economizados.

### Onde mexer em `dev_offline.py`

Função `_call_claude_with_tool_inner`. A SDK Anthropic aceita `cache_control` em blocos do `system` e `messages`. A rubrica e os schemas são candidatos óbvios.

```python
# Em vez de:
response = client.messages.create(
    model=model,
    max_tokens=max_tokens,
    system=full_system_prompt,  # string única
    messages=[...],
    tools=[tool],
)

# Usar blocos com cache_control:
response = client.messages.create(
    model=model,
    max_tokens=max_tokens,
    system=[
        {
            "type": "text",
            "text": full_system_prompt,  # rubrica + schemas estáveis
            "cache_control": {"type": "ephemeral", "ttl": "1h"},
        },
    ],
    messages=[
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": f"{activity_context}\n\nRedação:\n{essay_text}",
                    # NÃO cachear — muda a cada redação
                },
            ],
        },
    ],
    tools=[tool],
)
```

**TTL de 1 hora** é mais adequado que 5min default:
- Aulas duram tipicamente 50min. Simulado de 30 alunos pode levar 1-2h
- TTL 1h custa 2× cache write (vs 1.25× no de 5min), mas evita re-cache no meio da aula

### Métricas a logar

```python
usage = response.usage
log_entry = {
    "request_id": request_id,
    "cache_creation_input_tokens": getattr(usage, "cache_creation_input_tokens", 0),
    "cache_read_input_tokens": getattr(usage, "cache_read_input_tokens", 0),
    "input_tokens": usage.input_tokens,
    "output_tokens": usage.output_tokens,
}
cache_total = log_entry["cache_creation_input_tokens"] + log_entry["cache_read_input_tokens"]
log_entry["cache_hit_ratio"] = (
    log_entry["cache_read_input_tokens"] / cache_total if cache_total else 0
)
```

Acompanhar:
- **Cache hit ratio** — alvo > 70% em produção estável
- **Custo real por correção** — comparar pre/post cache
- **Latência** — esperado: 60-85% redução em hits

### Critérios de aceitação

- [ ] Cliente envia `cache_control` em todas as chamadas
- [ ] Logs de uso mostram `cache_creation_input_tokens` na 1ª chamada e `cache_read_input_tokens` nas seguintes
- [ ] Cache hit ratio > 70% em ensemble N=3
- [ ] Custo médio por correção em ensemble cai pelo menos 40% (medido via Anthropic Console)
- [ ] Versão do prompt logada (cache invalida em mudanças)

### Notas

- **Não cachear `essay_text`.** Cada redação é única.
- **Não cachear `activity_context`** se atividade muda entre correções. Só vale se múltiplos alunos da mesma turma corrigem simultaneamente — nesse caso, segundo bloco de cache.
- **Cache invalida em mudanças de prompt.** Sempre que rubrica é atualizada, primeira chamada paga write rate. Considerar versão do prompt em logs para tracking.

---

## Resumo: matriz de impacto

| Tarefa | Resolve | Custo dev | Custo runtime | Risco |
|---|---|---|---|---|
| 9 — Repetition flag | Bias C3↔C4 (teste_04) | 1-2 dias | Quase zero | Baixo |
| 10 — Two-stage Opus | Bug Opus, qualidade | 3-4 dias | +1 chamada Haiku | Médio |
| 11 — Confidence + HITL | Casos oscilantes | 3-5 dias | Carga professor | Médio |
| 12 — Prompt caching | Custo de ensemble | 1 dia | -50%+ em input | Baixo |

## Ordem sugerida

```
Sprint 1 (semana 1-2):
  ├── Tarefa 12 (prompt caching) — 1 dia, ROI imediato
  └── Tarefa 9 (repetition flag) — 1-2 dias, resolve teste_04

Sprint 2 (semana 3-4):
  ├── Tarefa 11 (confidence + HITL) — 3-5 dias
  └── Tarefa 10 (two-stage) — 3-4 dias, em paralelo
```

## O que NÃO está aqui

- Fine-tuning de Claude — fora do escopo de prompt engineering, depende de evolução da oferta da Anthropic
- Mudança da rubrica/calibração — assume rubrica v2 + canarios.yaml v2 como dados
- Reescrita do schema — schema atual funciona; tarefas 10-11 estendem sem refazer

---

*Versão 1.1 · abril de 2026 (corrigida para alinhar com arquitetura real do repo)*
