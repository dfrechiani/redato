# Diagnóstico — aesenem_sourceAWithGraders_train_000694

**Fonte:** `aes-enem`

**Tema:** Educação brasileira: conhecimento já!

**Tamanho do texto:** 1357 chars · **Latência Redato:** 70.7s

**Padrão:** INFLAÇÃO · Δ = `+240` (Redato 600 vs Gabarito 360)

---

## Notas comparadas

| | C1 | C2 | C3 | C4 | C5 | TOTAL |
|---|---:|---:|---:|---:|---:|---:|
| **Gabarito INEP** | 120 | 0 | 80 | 80 | 80 | **360** |
| Redato derivacao (Python) | 120 | 160 | 120 | 80 | 120 | 600 |
| Redato final (após two-stage) | 120 | 160 | 120 | 80 | 120 | **600** |

## Drift por competência (Redato_final − Gabarito)

| | C1 | C2 | C3 | C4 | C5 |
|---|---:|---:|---:|---:|---:|
| Drift | +0 | +160 | +40 | +0 | +40 |

## Audit do LLM (resumido por competência)

### C1 — gabarito 120 · derivação 120 · final 120

- nota emitida pelo LLM: **120**
- desvios_gramaticais: list[7]
- desvios_gramaticais_count: 7
- erros_ortograficos_count: 1
- desvios_crase_count: 1
- desvios_regencia_count: 1
- falhas_estrutura_sintatica_count: 1
- marcas_oralidade: []
- reincidencia_de_erro: False
- reading_fluency_compromised: False
- threshold_check: {applies_nota_5=False, applies_nota_4=False, applies_nota_3=True, applies_nota_2=False, applies_nota_1=False, applies_nota_0=False}

### C2 — gabarito 0 · derivação 160 · final 160

- nota emitida pelo LLM: **160**
- theme_keywords_by_paragraph: list[4]
- tangenciamento_detected: False
- fuga_total_detected: False
- repertoire_references: []
- has_reference_in_d1: False
- has_reference_in_d2: False
- tres_partes_completas: True
- partes_embrionarias_count: 1
- conclusao_com_frase_incompleta: False
- copia_motivadores_sem_aspas: False

### C3 — gabarito 80 · derivação 120 · final 120

- nota emitida pelo LLM: **120**
- has_explicit_thesis: False
- thesis_quote: o sistema educacional brasileiro está corrompido há muito tempo, e cada vez mais, estamos caminhando para uma verdadeira concepção da ignorância
- ponto_de_vista_claro: False
- ideias_progressivas: False
- planejamento_evidente: False
- autoria_markers: []
- encadeamento_sem_saltos: False
- saltos_tematicos: ["P2 discute corte de recursos para formação superior, mas P3 salta abruptamente para 'representatividade', 'emancipação' e jovens desinformados sem articular o argumento anterior", 'P4 (conclusão) propõe manifestações cidadãs sem retomar ou sintetizar os argumentos dos parágrafos anteriores']
- argumentos_contraditorios: False
- informacoes_irrelevantes_ou_repetidas: True
- limitado_aos_motivadores: False

### C4 — gabarito 80 · derivação 80 · final 80

- nota emitida pelo LLM: **80**
- connectors_used: list[4]
- connector_variety_count: 4
- most_used_connector: Além disso
- most_used_connector_count: 2
- has_mechanical_repetition: True
- referential_cohesion_examples: ["'esta é o maior investimento' — retoma 'educação' por pronome demonstrativo", "'aqueles que deveriam ser os responsáveis' — retoma os gestores do MEC por pronome"]
- ambiguous_pronouns: list[2]
- paragraph_transitions: list[3]
- complex_periods_well_structured: False
- coloquialism_excessive: False

### C5 — gabarito 80 · derivação 120 · final 120

- nota emitida pelo LLM: **120**
- elements_present: {}
- elements_count: 3
- proposta_articulada_ao_tema: True
- respeita_direitos_humanos: True

## Redação (texto_original)

```
É indiscutível que o sistema educacional brasileiro está corrompido há muito tempo, e cada vez mais, estamos caminhando para uma verdadeira concepção da ignorância.
A polêmica relacionada ao corte de recursos para formação superior, evidência-se como uma comprovação de que aqueles que deveriam ser os responsáveis pela administração de um Ministério da Educação de fato preocupado em garantir a fomentação do saber e o cultivo do aprendizado da população, não cumprem com suas respectivas funções.
Cada vez mais a sociedade se vê a mercê de não somente representatividade, mas também de voz, além da emancipação da falta de conhecimento. Prova disso, está no número demasiado de jovens que são prejudicados com as diversas negligências educacionais, e simplesmente não se dão conta da proporção do problema, já que, na maioria das vezes, se quer buscam compreender o que se passa no âmbito político, socioeducativo, e dos direitos fundamentais dos indivíduos.
Portanto, mostra-se de extrema importância que nós, enquanto cidadãos desta nação, devemos promover manifestações para reivindicação do alicerce da humanidade; a educação, visto que esta é o maior investimento para um futuro próspero. Além disso, ao passo que a manipulação de pessoas se torna algo comum, é necessário que sejamos um país crítico, lutando contra a obscuridade do desconhecimento.
```