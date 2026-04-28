# REDATO V2 — SCHEMA, FEW-SHOTS E INTEGRAÇÃO

**Base:** Rubrica v2 (PDF da corretora + correção da Tensão 3)
**Data:** 2026-04-24

---

## 1. SCHEMA AUDITADO V2

### Filosofia da v2

O schema força a **contagem explícita** exigida pelo PDF. C1 por número de desvios, C5 por número de elementos, C2 por palavras-chave por parágrafo. A LLM não pode mais "estimar" — precisa listar e contar.

### Schema completo

```json
{
  "essay_analysis": {
    "theme": "string",
    "theme_keywords": ["string"],
    "word_count": "integer",
    "paragraph_count": "integer",
    "title_present": "boolean",
    "title_coherent_with_theme": "boolean or null"
  },

  "preanulation_checks": {
    "fuga_total_ao_tema": "boolean",
    "nao_dissertativo_argumentativo": "boolean",
    "linhas_proprias_count": "integer",
    "abaixo_de_8_linhas_proprias": "boolean",
    "copia_excessiva_sem_producao_propria": "boolean",
    "desenhos_ou_sinais_sem_funcao": "boolean",
    "improperiosopresentes": "boolean",
    "lingua_estrangeira_predominante": "boolean",
    "texto_ilegivel": "boolean",
    "should_annul": "boolean",
    "annul_reason": "string or null"
  },

  "c1_audit": {
    "desvios_gramaticais": [
      {
        "quote": "string (trecho exato)",
        "type": "enum: concordancia_verbal | concordancia_nominal | crase | regencia | mau_mal | ortografia | acentuacao | pontuacao | conjugacao | colocacao_pronominal",
        "correction": "string"
      }
    ],
    "desvios_gramaticais_count": "integer",
    "erros_ortograficos_count": "integer",
    "desvios_crase_count": "integer",
    "desvios_regencia_count": "integer",
    "falhas_estrutura_sintatica_count": "integer",
    "marcas_oralidade": ["string"],
    "reincidencia_de_erro": "boolean",
    "reading_fluency_compromised": "boolean",
    "threshold_check": {
      "applies_nota_5": "boolean (max 2 desvios, max 1 ortográfico, max 1 crase, max 1 falha sintática)",
      "applies_nota_4": "boolean (até 3 gramaticais, até 3 ortográficos, até 2 regência)",
      "applies_nota_3": "boolean (até 5 gramaticais)",
      "applies_nota_2": "boolean (estrutura deficitária OU regular + muitos desvios)",
      "applies_nota_1": "boolean (diversificados e frequentes)",
      "applies_nota_0": "boolean (desconhecimento sistemático)"
    },
    "nota": "integer (40|80|120|160|200)"
  },

  "c2_audit": {
    "theme_keywords_by_paragraph": [
      {
        "paragraph_index": "integer",
        "keywords_found": ["string"],
        "synonyms_found": ["string"],
        "majority_keywords_present": "boolean"
      }
    ],
    "tangenciamento_detected": "boolean",
    "fuga_total_detected": "boolean",
    "repertoire_references": [
      {
        "quote": "string",
        "category": "enum: filosofico | sociologico | historico | juridico | literario | cientifico | cinematografico | midiatico | artistico",
        "source_cited": "boolean (autor, obra, data, fonte nomeada)",
        "legitimacy": "enum: legitimated | not_legitimated | false_attribution",
        "productivity": "enum: productive | decorative | copied_from_motivator",
        "paragraph_located": "integer (1=intro, 2=D1, 3=D2, 4=conclusão)",
        "legitimacy_reason": "string"
      }
    ],
    "has_reference_in_d1": "boolean",
    "has_reference_in_d2": "boolean",
    "tres_partes_completas": "boolean",
    "partes_embrionarias_count": "integer",
    "conclusao_com_frase_incompleta": "boolean",
    "copia_motivadores_sem_aspas": "boolean",
    "nota": "integer"
  },

  "c3_audit": {
    "has_explicit_thesis": "boolean",
    "thesis_quote": "string or null",
    "ponto_de_vista_claro": "boolean",
    "ideias_progressivas": "boolean",
    "planejamento_evidente": "boolean",
    "autoria_markers": ["string (trechos originais)"],
    "encadeamento_sem_saltos": "boolean",
    "saltos_tematicos": ["string"],
    "argumentos_contraditorios": "boolean",
    "informacoes_irrelevantes_ou_repetidas": "boolean",
    "limitado_aos_motivadores": "boolean",
    "nota": "integer"
  },

  "c4_audit": {
    "connectors_used": [
      {"connector": "string", "count": "integer", "positions": ["string"]}
    ],
    "connector_variety_count": "integer",
    "most_used_connector": "string",
    "most_used_connector_count": "integer",
    "has_mechanical_repetition": "boolean",
    "referential_cohesion_examples": ["string"],
    "ambiguous_pronouns": [{"quote": "string", "issue": "string"}],
    "paragraph_transitions": [
      {"from_paragraph": "integer", "to_paragraph": "integer", "quality": "enum: clear | adequate | abrupt | absent"}
    ],
    "complex_periods_well_structured": "boolean",
    "coloquialism_excessive": "boolean",
    "nota": "integer"
  },

  "c5_audit": {
    "elements_present": {
      "agente": {
        "present": "boolean",
        "quote": "string or null",
        "generic": "boolean (true se 'sociedade', 'todos', 'governo' sem especificação)"
      },
      "acao": {
        "present": "boolean",
        "quote": "string or null",
        "generic": "boolean"
      },
      "modo_meio": {
        "present": "boolean",
        "quote": "string or null"
      },
      "finalidade": {
        "present": "boolean",
        "quote": "string or null",
        "articulated_with_thesis": "boolean"
      },
      "detalhamento": {
        "present": "boolean",
        "quote": "string or null",
        "type": "enum: agent | action | means | purpose | example | absent"
      }
    },
    "elements_count": "integer (0-5)",
    "proposta_articulada_ao_tema": "boolean",
    "respeita_direitos_humanos": "boolean",
    "nota": "integer"
  },

  "priorization": {
    "priority_1": {
      "target_competency": "string",
      "current_nota": "integer",
      "potential_nota": "integer",
      "potential_gain": "integer",
      "actions_required": ["string"]
    },
    "priority_2": "object (optional, same structure)",
    "priority_3": "object (optional, same structure)"
  },

  "meta_checks": {
    "total_calculated": "integer",
    "total_matches_sum": "boolean",
    "no_competency_bleeding": "boolean",
    "preanulation_verified": "boolean",
    "keywords_verified_per_paragraph": "boolean",
    "c5_counted_elements": "boolean"
  },

  "feedback_text": "string (síntese final em tom pedagógico)"
}
```

### Campos críticos — não negociáveis

- `preanulation_checks.should_annul` — DEVE ser avaliado antes de qualquer competência.
- `c1_audit.desvios_gramaticais[]` — lista obrigatória, não contagem estimada.
- `c1_audit.threshold_check` — força checagem contra a tabela do PDF.
- `c2_audit.theme_keywords_by_paragraph[]` — força checagem parágrafo por parágrafo.
- `c2_audit.repertoire_references[].legitimacy` — força verificação factual.
- `c5_audit.elements_present` — estrutura explícita dos 5 elementos, booleana.
- `c5_audit.elements_count` — calculado pela soma dos booleanos, sem estimativa.

---

## 2. FEW-SHOTS TRABALHADOS

### Few-shot 1 — C1 com desvios frequentes (Canário 1)

**INPUT:** [texto do Canário 1]

**OUTPUT:**

```json
{
  "preanulation_checks": {
    "fuga_total_ao_tema": false,
    "nao_dissertativo_argumentativo": false,
    "linhas_proprias_count": 30,
    "abaixo_de_8_linhas_proprias": false,
    "should_annul": false,
    "annul_reason": null
  },

  "c1_audit": {
    "desvios_gramaticais": [
      {"quote": "se aplica as redes sociais", "type": "crase", "correction": "se aplica às redes sociais"},
      {"quote": "os jovens brasileiro expõe", "type": "concordancia_nominal", "correction": "os jovens brasileiros expõem"},
      {"quote": "Isso por que", "type": "pontuacao", "correction": "Isso porque"},
      {"quote": "os jovem", "type": "concordancia_nominal", "correction": "os jovens"},
      {"quote": "os mecanismos... potencializa", "type": "concordancia_verbal", "correction": "os mecanismos... potencializam"},
      {"quote": "recorrendo à estímulos", "type": "crase", "correction": "recorrendo a estímulos"},
      {"quote": "exposto à um ciclo", "type": "crase", "correction": "exposto a um ciclo"},
      {"quote": "à longo prazo", "type": "crase", "correction": "a longo prazo"},
      {"quote": "mau respeita", "type": "mau_mal", "correction": "mal respeita"},
      {"quote": "pra menores", "type": "concordancia_verbal", "correction": "para menores"}
    ],
    "desvios_gramaticais_count": 10,
    "erros_ortograficos_count": 1,
    "desvios_crase_count": 4,
    "marcas_oralidade": ["Tipo assim, a gente vê isso claramente no dia a dia escolar", "pra menores"],
    "threshold_check": {
      "applies_nota_5": false,
      "applies_nota_4": false,
      "applies_nota_3": false,
      "applies_nota_2": false,
      "applies_nota_1": true,
      "applies_nota_0": false
    },
    "nota": 40
  },

  "c2_audit": {
    "theme_keywords_by_paragraph": [
      {"paragraph_index": 1, "keywords_found": ["redes sociais", "saúde mental", "juventude"], "majority_keywords_present": true},
      {"paragraph_index": 2, "keywords_found": ["redes sociais", "jovem"], "majority_keywords_present": true},
      {"paragraph_index": 3, "keywords_found": ["redes", "sofrimento psíquico", "jovem"], "majority_keywords_present": true},
      {"paragraph_index": 4, "keywords_found": ["redes sociais", "juventude"], "majority_keywords_present": true}
    ],
    "tangenciamento_detected": false,
    "repertoire_references": [
      {"quote": "Byung-Chul Han, Sociedade do Cansaço", "category": "filosofico", "source_cited": true, "legitimacy": "legitimated", "productivity": "productive", "paragraph_located": 1},
      {"quote": "Zygmunt Bauman, modernidade líquida", "category": "sociologico", "source_cited": true, "legitimacy": "legitimated", "productivity": "productive", "paragraph_located": 2},
      {"quote": "Pesquisas da OMS", "category": "cientifico", "source_cited": true, "legitimacy": "legitimated", "productivity": "productive", "paragraph_located": 2},
      {"quote": "O Dilema das Redes", "category": "cinematografico", "source_cited": true, "legitimacy": "legitimated", "productivity": "productive", "paragraph_located": 3},
      {"quote": "artigo 227 da Constituição Federal", "category": "juridico", "source_cited": true, "legitimacy": "legitimated", "productivity": "productive", "paragraph_located": 3}
    ],
    "has_reference_in_d1": true,
    "has_reference_in_d2": true,
    "tres_partes_completas": true,
    "nota": 200
  },

  "c5_audit": {
    "elements_present": {
      "agente": {"present": true, "quote": "Ministério da Educação + Congresso Nacional", "generic": false},
      "acao": {"present": true, "quote": "implementar programa / regulamentar algoritmos", "generic": false},
      "modo_meio": {"present": true, "quote": "por meio de oficinas quinzenais / exigindo transparência", "generic": false},
      "finalidade": {"present": true, "quote": "a fim de romper o ciclo entre lucro digital e adoecimento juvenil", "articulated_with_thesis": true},
      "detalhamento": {"present": true, "quote": "conduzidas por psicólogos e professores capacitados", "type": "action"}
    },
    "elements_count": 5,
    "nota": 200
  },

  "priorization": {
    "priority_1": {
      "target_competency": "c1",
      "current_nota": 40,
      "potential_nota": 200,
      "potential_gain": 160,
      "actions_required": [
        "Corrigir as 10 ocorrências listadas em desvios_gramaticais",
        "Remover 'Tipo assim, a gente vê' (oralidade)",
        "Substituir 'pra' por 'para'"
      ]
    }
  },

  "feedback_text": "Redação com repertório excelente, projeto de texto sólido, coesão variada e proposta de intervenção completa com os 5 elementos — quatro competências em 200. O único obstáculo à nota máxima é C1: 10 desvios gramaticais + 4 desvios de crase + 1 erro de mau/mal + marcas de oralidade. Pela tabela de competência, 'desvios diversificados e frequentes' caracteriza nota 1 (40 pontos). Corrigir todos os desvios listados acima pode elevar C1 para 200, o que representa ganho potencial de até 160 pontos na nota total."
}
```

### Few-shot 2 — Repertório não legitimado (Canário 2)

**OUTPUT trecho crítico:**

```json
{
  "c2_audit": {
    "repertoire_references": [
      {"quote": "Einstein já dizia que 'a tecnologia superou nossa humanidade'", "category": "cientifico", "source_cited": true, "legitimacy": "false_attribution", "productivity": "decorative", "legitimacy_reason": "Citação apócrifa. Einstein não escreveu nem disse essa frase em nenhum registro verificável."},
      {"quote": "Segundo pesquisas recentes", "category": "cientifico", "source_cited": false, "legitimacy": "not_legitimated", "productivity": "decorative", "legitimacy_reason": "Dado sem fonte específica."},
      {"quote": "artigo 5º da Constituição Federal, que trata da proteção à infância", "category": "juridico", "source_cited": true, "legitimacy": "false_attribution", "productivity": "decorative", "legitimacy_reason": "O art. 5º trata de direitos e garantias fundamentais gerais. A proteção à infância está no art. 227."},
      {"quote": "Filósofos antigos já discutiam...", "category": "filosofico", "source_cited": false, "legitimacy": "not_legitimated", "productivity": "decorative", "legitimacy_reason": "Menção vaga sem nomear autor ou obra."}
    ],
    "tres_partes_completas": true,
    "nota": 120
  }
}
```

### Few-shot 3 — Contagem de elementos em C5 (Canário 5)

**OUTPUT trecho crítico:**

```json
{
  "c5_audit": {
    "elements_present": {
      "agente": {"present": true, "quote": "o governo", "generic": true},
      "acao": {"present": true, "quote": "tome providências, criando políticas públicas", "generic": true},
      "modo_meio": {"present": true, "quote": "criando políticas públicas eficientes", "generic": true},
      "finalidade": {"present": true, "quote": "garantindo um futuro melhor para a juventude brasileira", "articulated_with_thesis": false},
      "detalhamento": {"present": false, "quote": null, "type": "absent"}
    },
    "elements_count": 4,
    "proposta_articulada_ao_tema": false,
    "nota": 120,
    "observacao": "4 elementos presentes mas todos genéricos. Proposta mal articulada ao tema específico. PDF aceita 'mal articulada' como critério para nota 2, mas a presença de 4 elementos nominais normalmente leva a nota 3. Adotada nota 3 (120) com sinalização da fraqueza no feedback."
  }
}
```

---

## 3. REGRAS DE VALIDAÇÃO NO SCRIPT DE EVAL

### 3.1 Drift numérico

`abs(nota_predicted - nota_gabarito) <= 40` por competência.

### 3.2 Checagens estruturais (por canário)

**Canário 1:**
- `c1_audit.desvios_gramaticais_count >= 8`
- `c1_audit.nota == 40`

**Canário 2:**
- Pelo menos uma referência com `legitimacy == "false_attribution"`
- Pelo menos uma referência com `legitimacy == "not_legitimated"`
- `c2_audit.nota == 120`

**Canário 3:**
- `c3_audit.has_explicit_thesis == false`
- `c3_audit.argumentos_contraditorios == true`
- `c3_audit.nota <= 120`

**Canário 4:**
- `c4_audit.most_used_connector_count >= 4`
- `c4_audit.has_mechanical_repetition == true`
- `c4_audit.nota == 120`

**Canário 5:**
- `c5_audit.elements_count >= 3` AND `c5_audit.elements_count <= 4`
- `c5_audit.nota == 120`

**Canário 6:**
- `total >= 960`
- Máximo 1 competência abaixo de 200

**Canário 7:**
- `c1_audit.nota == 40` AND `c5_audit.nota <= 120`
- `c2_audit.nota >= 180` AND `c3_audit.nota >= 180` (não-propagação)

**Canário 8:**
- `c2_audit.repertoire_references.length >= 7`
- `c2_audit.nota == 200`
- `c3_audit.has_explicit_thesis == false`
- `c3_audit.nota <= 120`

**Canário 9:**
- `c5_audit.elements_count == 2`
- `c5_audit.nota == 80`

**Canário 10:**
- `c2_audit.tangenciamento_detected == true`
- `c2_audit.nota <= 80`

**Canário 11:**
- `preanulation_checks.copia_excessiva == true` OU `c2_audit.copia_motivadores_sem_aspas == true`
- Se not annulada: `c2_audit.nota <= 120`

### 3.3 Política de deploy

```python
FAIL_THRESHOLD = 2
if failures >= FAIL_THRESHOLD:
    sys.exit(1)  # bloqueia deploy
```

---

## 4. INSTRUÇÕES PARA CLAUDE CODE

```
CONTEXTO: Sistema de calibração por eval da LLM da Redato, v2.
Arquivos-fonte em /home/claude/:
- rubrica_v2.md (rubrica autoritativa)
- calibration_set_v2.yaml (11 canários)
- redato_v2_schema_and_fewshots.md (este arquivo)

TAREFAS:

1. CRIAR estrutura no repo:
   docs/redato/v2/
   ├── rubrica_v2.md
   ├── calibration_set.yaml
   └── schema_and_fewshots.md

2. CRIAR scripts/run_calibration_eval.py:
   - Carrega calibration_set.yaml
   - Para cada canário: chama Redato com essay
   - Valida contra gabarito + regras 3.2
   - Reporta pass/fail por canário e competência
   - Exit 1 se >= 2 canários falharem

3. EXPANDIR system prompt da Redato:
   - Incluir rubrica_v2.md como contexto principal
   - Adicionar os 3 few-shots ANTES da instrução principal
   - Garantir cache de prompt (estrutura estável)

4. EXPANDIR schema do tool call:
   - Usar estrutura completa da seção 1
   - Campos críticos marcados como required
   - Adicionar validação: preanulation_checks PRIMEIRO

5. RODAR baseline:
   - python scripts/run_calibration_eval.py --baseline
   - Salvar baseline_YYYY-MM-DD.json

6. RODAR pós-mudanças:
   - Comparar contra baseline, reportar delta

CRITÉRIO DE SUCESSO: >= 9/11 canários passam.
```
