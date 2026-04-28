# Diagnóstico — aesenem_sourceB_full_002422

**Fonte:** `aes-enem`

**Tema:** FBS #2

**Tamanho do texto:** 2293 chars · **Latência Redato:** 68.2s

**Padrão:** DEFLAÇÃO · Δ = `-240` (Redato 680 vs Gabarito 920)

---

## Notas comparadas

| | C1 | C2 | C3 | C4 | C5 | TOTAL |
|---|---:|---:|---:|---:|---:|---:|
| **Gabarito INEP** | 200 | 200 | 160 | 200 | 160 | **920** |
| Redato derivacao (Python) | 40 | 80 | 200 | 160 | 200 | 680 |
| Redato final (após two-stage) | 40 | 80 | 200 | 160 | 200 | **680** |

## Drift por competência (Redato_final − Gabarito)

| | C1 | C2 | C3 | C4 | C5 |
|---|---:|---:|---:|---:|---:|
| Drift | -160 | -120 | +40 | -40 | +40 |

## Audit do LLM (resumido por competência)

### C1 — gabarito 200 · derivação 40 · final 40

- nota emitida pelo LLM: **40**
- desvios_gramaticais: list[11]
- desvios_gramaticais_count: 11
- erros_ortograficos_count: 0
- desvios_crase_count: 1
- desvios_regencia_count: 4
- falhas_estrutura_sintatica_count: 2
- marcas_oralidade: []
- reincidencia_de_erro: True
- reading_fluency_compromised: True
- threshold_check: {applies_nota_5=False, applies_nota_4=False, applies_nota_3=False, applies_nota_2=False, applies_nota_1=True, applies_nota_0=False}

### C2 — gabarito 200 · derivação 80 · final 80

- nota emitida pelo LLM: **80**
- theme_keywords_by_paragraph: list[5]
- tangenciamento_detected: False
- fuga_total_detected: False
- repertoire_references: list[2]
- has_reference_in_d1: True
- has_reference_in_d2: False
- tres_partes_completas: True
- partes_embrionarias_count: 0
- conclusao_com_frase_incompleta: True
- copia_motivadores_sem_aspas: False

### C3 — gabarito 160 · derivação 200 · final 200

- nota emitida pelo LLM: **200**
- has_explicit_thesis: True
- thesis_quote: o parto humanizado apresenta barreiras, as quais dificultam a concretização dos planos de More. Esse cenário antagônico é fruto tanto da violência obstétrica, quanto do excesso de parto cesáreo sem necessidade.
- ponto_de_vista_claro: True
- ideias_progressivas: True
- planejamento_evidente: True
- autoria_markers: ['a violência obstétrica retrocede o desenvolvimento do parto humanizado que, por sua vez, empodera a mulher, prioriza e promove à saúde, e garante o livre exercício dos direitos sexuais e reprodutivos da mulher', 'o excesso de parto cesáreo sem necessidade faz com que a recuperação da mulher seja mais demorada e podendo desenvolver no bebê possíveis problemas respiratórios']
- encadeamento_sem_saltos: True
- saltos_tematicos: []
- argumentos_contraditorios: False
- informacoes_irrelevantes_ou_repetidas: False
- limitado_aos_motivadores: False

### C4 — gabarito 200 · derivação 160 · final 160

- nota emitida pelo LLM: **160**
- connectors_used: list[15]
- connector_variety_count: 14
- most_used_connector: Desse modo / por sua vez
- most_used_connector_count: 2
- has_mechanical_repetition: False
- referential_cohesion_examples: ["'tais recorrências' retoma 'violência obstétrica' (P2)", "'isso' retoma 'garantir o bem-estar da população' (P2)", "'desse quadro deletério' retoma a situação do excesso de cesáreas (P3)"]
- ambiguous_pronouns: list[1]
- paragraph_transitions: list[4]
- complex_periods_well_structured: False
- coloquialism_excessive: False

### C5 — gabarito 160 · derivação 200 · final 200

- nota emitida pelo LLM: **200**
- elements_present: {}
- elements_count: 5
- proposta_articulada_ao_tema: True
- respeita_direitos_humanos: True

## Redação (texto_original)

```
Na obra "Utopia", do escritor inglês Thomas More, é retratada uma sociedade perfeita, na qual o corpo social padroniza-se pela ausência de conflitos e problemas. No entanto, o que se observa na realidade contemporânea é o oposto do que o autor prega, uma vez que o parto humanizado apresenta barreiras, as quais dificultam a concretização dos planos de More. Esse cenário antagônico é fruto tanto da violência obstétrica, quanto do excesso de parto cesáreo sem necessidade. Diante disso, torna-se fundamental a discussão desses aspectos, a fim do pleno funcionamento da sociedade. Primeiramente, é fulcral pontuar que a violência obstétrica deriva da baixa atuação do setores governamentais, no que concerne à criação de mecanismos que coíbam tais recorrências. Segundo o pensador Thomas Hobbes, o Estado é responsável por garantir o bem-estar da população, entretanto, isso não ocorre no Brasil. Devido à falta de atuação das autoridades, a violência obstétrica retrocede o desenvolvimento do parto humanizado que, por sua vez, empodera a mulher, prioriza e promove à saúde, e garante o livre exercício dos direitos sexuais e reprodutivos da mulher. Desse modo, faz-se mister a reformulação dessa postura estatal de forma urgente. Ademais, imperativo ressaltar que o excesso de parto cesáreo sem necessidade com promotor do problema. Partindo desse pressuposto, muitos partos que poderiam ser realizados de forma natural, acabam sendo induzidos a cesariana sem necessidade que, por sua vez, faz com que a recuperação da mulher seja mais demorada e podendo desenvolver no bebê possíveis problemas respiratórios. Tudo isso retarda a resolução do empecilho, já que o excesso de parto cesáreo sem necessidade contribui para a perpetuação desse quadro deletério. Assim, uma intervenção faz-se necessário. Dessarte, com o intuito de militar o parto humanizado, necessita-se, urgentemente, que o Tribunal de Contas da União direcione capital que, por intermédio do Ministério da Saúde, será revestida em projetos que priorizam o parto humanizado e que tais eventos darão mais autoridade de escolha para a mulher durante o parto. Desse modo, , em médio e longo prazo, o impacto nocivo do parto humanizado, e a coletividade alcançará a Utopia de More, construindo uma sociedade mais tolerante e justa.
```