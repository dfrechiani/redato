# Diagnóstico — aesenem_sourceAWithGraders_validation_000068

**Fonte:** `aes-enem`

**Tema:** Evitando o acidente

**Tamanho do texto:** 2124 chars · **Latência Redato:** 58.6s

**Padrão:** DEFLAÇÃO · Δ = `-400` (Redato 600 vs Gabarito 1000)

---

## Notas comparadas

| | C1 | C2 | C3 | C4 | C5 | TOTAL |
|---|---:|---:|---:|---:|---:|---:|
| **Gabarito INEP** | 200 | 200 | 200 | 200 | 200 | **1000** |
| Redato derivacao (Python) | 200 | 0 | 200 | 200 | 0 | 600 |
| Redato final (após two-stage) | 200 | 0 | 200 | 200 | 0 | **600** |

## Drift por competência (Redato_final − Gabarito)

| | C1 | C2 | C3 | C4 | C5 |
|---|---:|---:|---:|---:|---:|
| Drift | +0 | -200 | +0 | +0 | -200 |

## Audit do LLM (resumido por competência)

### C1 — gabarito 200 · derivação 200 · final 200

- nota emitida pelo LLM: **200**
- desvios_gramaticais: []
- desvios_gramaticais_count: 0
- erros_ortograficos_count: 0
- desvios_crase_count: 0
- desvios_regencia_count: 0
- falhas_estrutura_sintatica_count: 0
- marcas_oralidade: []
- reincidencia_de_erro: False
- reading_fluency_compromised: False
- threshold_check: {applies_nota_5=False, applies_nota_4=False, applies_nota_3=False, applies_nota_2=False, applies_nota_1=False, applies_nota_0=False}

### C2 — gabarito 200 · derivação 0 · final 0

- nota emitida pelo LLM: **0**
- theme_keywords_by_paragraph: list[5]
- tangenciamento_detected: False
- fuga_total_detected: True
- repertoire_references: list[1]
- has_reference_in_d1: False
- has_reference_in_d2: False
- tres_partes_completas: True
- partes_embrionarias_count: 0
- conclusao_com_frase_incompleta: False
- copia_motivadores_sem_aspas: False

### C3 — gabarito 200 · derivação 200 · final 200

- nota emitida pelo LLM: **200**
- has_explicit_thesis: True
- thesis_quote: a greve foi uma surpresa ou uma crise anunciada?
- ponto_de_vista_claro: True
- ideias_progressivas: True
- planejamento_evidente: True
- autoria_markers: ['Ora, todos os cidadãos podem e devem parar uma nação que trafega rumo ao abismo.', 'Paralisemos o país antes que ele capote.']
- encadeamento_sem_saltos: True
- saltos_tematicos: []
- argumentos_contraditorios: False
- informacoes_irrelevantes_ou_repetidas: False
- limitado_aos_motivadores: False

### C4 — gabarito 200 · derivação 200 · final 200

- nota emitida pelo LLM: **200**
- connectors_used: list[5]
- connector_variety_count: 5
- most_used_connector: Afinal
- most_used_connector_count: 1
- has_mechanical_repetition: False
- referential_cohesion_examples: ["Ele sente na pele (e no bolso) os impactos — retomada anafórica de 'o caminhoneiro'", "Tal grito veio tarde — retomada catafórica do 'grito de basta' do parágrafo anterior"]
- ambiguous_pronouns: []
- paragraph_transitions: list[4]
- complex_periods_well_structured: True
- coloquialism_excessive: False

### C5 — gabarito 200 · derivação 0 · final 0

- nota emitida pelo LLM: **0**
- elements_present: {}
- elements_count: 0
- proposta_articulada_ao_tema: False
- respeita_direitos_humanos: True

## Redação (texto_original)

```
Ruas vazias, carência de produtos, filas nos postos de combustíveis, temor e incerteza. O roteiro de futuros distópicos foi encenado, recentemente, no Brasil, durante a paralisação dos caminhoneiros. A greve expôs o resultado de sucessivas políticas públicas que priorizaram o transporte rodoviário, tornando a população refém das estradas e do diesel. Afinal, a greve foi uma surpresa ou uma crise anunciada?
O capitalismo de compadrio, praticado não apenas no Brasil, corresponde à aliança entre o Poder Público e os interesses privados. O lobby das concessionárias automotivas atuou – e atua – fortemente em Brasília, influenciando (ou mandando) no planejamento dos governos. Em nome do “desenvolvimento”, o país escolheu o sistema rodoviário em detrimento do transporte ferroviário e hidroviário. Sob o asfalto, mesmo o esburacado, movimenta-se o Brasil.
Esse movimento tem um expoente: o caminhoneiro. Ele sente na pele (e no bolso) os impactos dos impostos abusivos, seja nos pedágios, seja nos postos de combustíveis. Como qualquer classe trabalhadora, a carga tributária onera a apertada renda mensal, fazendo com que a base da pirâmide social assista, do acostamento, a muitos enriquecerem com a exploração alheia. Sem dúvida, a greve surgiu como um grito de basta, transbordando toda a frustração acumulada de anos de descaso e incompetência.
Tal grito veio tarde, mas assustou os incautos. Assustou quem não acreditava que uma classe trabalhadora pudesse exercer seu direito à greve; assustou quem imaginava um povo omisso e resignado. Os grevistas perceberam que tem poder de parar uma nação. Ora, todos os cidadãos podem e devem parar uma nação que trafega rumo ao abismo. Resta a dúvida: qual caminho será trilhado? Quem escolherá a nova rota?
Certamente, apenas a população consciente poderá responder tais questões. Até então, a rota era guiada por quem sempre se manteve no poder, sucessivos políticos e empresários perpetuadores um Brasil asfaltado e atrasado. A greve dos caminhoneiros deve ser um alerta aos cidadãos de que o poder da mudança reside em suas mãos. Paralisemos o país antes que ele capote.
```