# Diagnóstico — aesenem_sourceB_full_001441

**Fonte:** `aes-enem`

**Tema:** homofobia um debate contemporaneo importante

**Tamanho do texto:** 913 chars · **Latência Redato:** 67.3s

**Padrão:** INFLAÇÃO · Δ = `+240` (Redato 440 vs Gabarito 200)

---

## Notas comparadas

| | C1 | C2 | C3 | C4 | C5 | TOTAL |
|---|---:|---:|---:|---:|---:|---:|
| **Gabarito INEP** | 40 | 40 | 40 | 40 | 40 | **200** |
| Redato derivacao (Python) | 40 | 80 | 120 | 80 | 120 | 440 |
| Redato final (após two-stage) | 40 | 80 | 120 | 80 | 120 | **440** |

## Drift por competência (Redato_final − Gabarito)

| | C1 | C2 | C3 | C4 | C5 |
|---|---:|---:|---:|---:|---:|
| Drift | +0 | +40 | +80 | +40 | +80 |

## Audit do LLM (resumido por competência)

### C1 — gabarito 40 · derivação 40 · final 40

- nota emitida pelo LLM: **40**
- desvios_gramaticais: list[18]
- desvios_gramaticais_count: 18
- erros_ortograficos_count: 13
- desvios_crase_count: 0
- desvios_regencia_count: 1
- falhas_estrutura_sintatica_count: 2
- marcas_oralidade: []
- reincidencia_de_erro: True
- reading_fluency_compromised: True
- threshold_check: {applies_nota_5=False, applies_nota_4=False, applies_nota_3=False, applies_nota_2=False, applies_nota_1=True, applies_nota_0=False}

### C2 — gabarito 40 · derivação 80 · final 80

- nota emitida pelo LLM: **80**
- theme_keywords_by_paragraph: list[3]
- tangenciamento_detected: False
- fuga_total_detected: False
- repertoire_references: list[1]
- has_reference_in_d1: True
- has_reference_in_d2: False
- tres_partes_completas: True
- partes_embrionarias_count: 2
- conclusao_com_frase_incompleta: False
- copia_motivadores_sem_aspas: False

### C3 — gabarito 40 · derivação 120 · final 120

- nota emitida pelo LLM: **120**
- has_explicit_thesis: False
- thesis_quote: None
- ponto_de_vista_claro: False
- ideias_progressivas: False
- planejamento_evidente: False
- autoria_markers: []
- encadeamento_sem_saltos: False
- saltos_tematicos: ['O parágrafo 1 apresenta um caso factual sem conectar à tese ou argumento central.', 'O parágrafo 2 define homofobia e apresenta dados gerais sem progressão argumentativa do parágrafo anterior.', 'O parágrafo 3 muda abruptamente para soluções sem ter desenvolvido análise de causas ou consequências.']
- argumentos_contraditorios: False
- informacoes_irrelevantes_ou_repetidas: False
- limitado_aos_motivadores: False

### C4 — gabarito 40 · derivação 80 · final 80

- nota emitida pelo LLM: **80**
- connectors_used: list[5]
- connector_variety_count: 4
- most_used_connector: Um exemplo disso
- most_used_connector_count: 2
- has_mechanical_repetition: True
- referential_cohesion_examples: ["'sendo essa em agressão' — retomada anafórica ambígua de 'homofobia'", "'cada um' — referente vago"]
- ambiguous_pronouns: list[2]
- paragraph_transitions: list[2]
- complex_periods_well_structured: False
- coloquialism_excessive: False

### C5 — gabarito 40 · derivação 120 · final 120

- nota emitida pelo LLM: **120**
- elements_present: {}
- elements_count: 3
- proposta_articulada_ao_tema: True
- respeita_direitos_humanos: True

## Redação (texto_original)

```
Brasil so registrados diariamente centena de casos de homofobia. sendo essa em agresso fisca ou verbal. Um exemplo disso aconteceu no interior da ahia, tendo como vitima uma travesti. Dandara -como era chamada, foi levada para um terreno baldio onde foi apedrejada e espancada ata morte.


A palavra homofobia  sinnimo de dio e/ou repulsa contra homossexuais. Embora muitos pases tenha dado e assegurado mais direitos para a comunidade LGBT o preconceito e a violncia continua sendo um problema . Um exemplo disso  o Brasil, que estno ranking de pases onde prticas homofbicas so mais comuns, mesmo sendo tratada como crime.

. No Brasil existem leis que visam amparar a comunidade gay o que falta  coloc-las em prtica e torn-las mais eficazes. A mdia tem um papel importante abrindo espaço para dilogos desse assunto. Quanto aos LGBTs, cabe a cada um lutar por mais igualdade pois ainda h muito a ser conquistado.
```