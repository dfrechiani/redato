# Diagnóstico — aesenem_sourceB_full_000756

**Fonte:** `aes-enem`

**Tema:** A sobrevivência coletiv

**Tamanho do texto:** 2387 chars · **Latência Redato:** 89.8s

**Padrão:** DEFLAÇÃO · Δ = `-200` (Redato 720 vs Gabarito 920)

---

## Notas comparadas

| | C1 | C2 | C3 | C4 | C5 | TOTAL |
|---|---:|---:|---:|---:|---:|---:|
| **Gabarito INEP** | 160 | 200 | 160 | 200 | 200 | **920** |
| Redato derivacao (Python) | 40 | 160 | 200 | 120 | 200 | 720 |
| Redato final (após two-stage) | 40 | 160 | 200 | 120 | 200 | **720** |

## Drift por competência (Redato_final − Gabarito)

| | C1 | C2 | C3 | C4 | C5 |
|---|---:|---:|---:|---:|---:|
| Drift | -120 | -40 | +40 | -80 | +0 |

## Audit do LLM (resumido por competência)

### C1 — gabarito 160 · derivação 40 · final 40

- nota emitida pelo LLM: **40**
- desvios_gramaticais: list[13]
- desvios_gramaticais_count: 13
- erros_ortograficos_count: 2
- desvios_crase_count: 4
- desvios_regencia_count: 2
- falhas_estrutura_sintatica_count: 2
- marcas_oralidade: []
- reincidencia_de_erro: True
- reading_fluency_compromised: True
- threshold_check: {applies_nota_5=False, applies_nota_4=False, applies_nota_3=False, applies_nota_2=False, applies_nota_1=True, applies_nota_0=False}

### C2 — gabarito 200 · derivação 160 · final 160

- nota emitida pelo LLM: **160**
- theme_keywords_by_paragraph: list[4]
- tangenciamento_detected: False
- fuga_total_detected: False
- repertoire_references: list[3]
- has_reference_in_d1: True
- has_reference_in_d2: True
- tres_partes_completas: True
- partes_embrionarias_count: 0
- conclusao_com_frase_incompleta: False
- copia_motivadores_sem_aspas: False

### C3 — gabarito 160 · derivação 200 · final 200

- nota emitida pelo LLM: **200**
- has_explicit_thesis: True
- thesis_quote: a negligência estatal e a falta de amparo social dificultam que haja a conscientização da população acerca do isolamento em meio a crise econômica
- ponto_de_vista_claro: True
- ideias_progressivas: True
- planejamento_evidente: True
- autoria_markers: ['Diante disso, é fulcral pontuar a desigualdade social como impulsionadora do imbróglio', 'a negligência estatal contribui para a perpetuação desse quadro deletério']
- encadeamento_sem_saltos: True
- saltos_tematicos: []
- argumentos_contraditorios: False
- informacoes_irrelevantes_ou_repetidas: False
- limitado_aos_motivadores: False

### C4 — gabarito 200 · derivação 120 · final 120

- nota emitida pelo LLM: **120**
- connectors_used: list[17]
- connector_variety_count: 17
- most_used_connector: Contudo/No entanto/Todavia/Entretanto (todos de contraste — uso repetitivo do mesmo valor semântico)
- most_used_connector_count: 4
- has_mechanical_repetition: False
- referential_cohesion_examples: ["'esse quadro deletério' retoma a situação de negligência estatal descrita no parágrafo 3", "'Tudo isso' retoma os argumentos do eixo 2", "'diante do problema exposto' retoma a tese central na conclusão"]
- ambiguous_pronouns: list[2]
- paragraph_transitions: list[3]
- complex_periods_well_structured: False
- coloquialism_excessive: False

### C5 — gabarito 200 · derivação 200 · final 200

- nota emitida pelo LLM: **200**
- elements_present: {}
- elements_count: 5
- proposta_articulada_ao_tema: True
- respeita_direitos_humanos: True

## Redação (texto_original)

```
Consoante a Constituição federal de 1988- lei de maior hierarquia jurídica do país- garante a todos os cidadãos brasileiros o direito de ir e vir. Contudo, hodiernamente, a pandemia vivenciada pelo mundo vai de encontro com a Constituição, uma vez que, parabemestar coletivo, a população necessite ficar em isolamento social. No entanto, a negligência estatal e a falta de amparo social dificultam que haja a conscientização da população acerca do isolamento em meio a crise econômica. Diante disso, é fulcral pontuar a desigualdade social como impulsionadora do imbróglio. Nesse sentido, segundo o sociólogo Émille Durkhein, o fato social é a maneira coletiva de agir e pensar. Entretanto, é fato que isso não ocorre no Brasil, visto que muitos indivíduos não estão cumprindo devidamente o isolamento social, pois devido a vulnerabilidade financeira, não conseguem exercer seu trabalho em casa e, dessa forma, são obrigados a saírem de seus lares para conseguirem uma fonte de renda. Consequentemente, em meio a gravidade do Covid-19, colocam não só suas vidas, mas também as das pessoas do próprio convívio . Outrossim, é imperativo ressaltar a negligência estatal como barreira para obter a conscientização do isolamento social. De acordo o filósofo Friedrich Hegel, o Estado deve cuidar dos seus "filhos". Todavia, na sociedade atual, é o oposto do que o autor prega, dado que a falta de assistência com a população é alarmante, por exemplo, o negligenciamento com a parcela da população que está em estado de carência. Tudo isso retarda a resolução do empecilho, já que a negligência estatal contribui para a perpetuação desse quadro deletério. Portanto, diante do problema exposto, medidas são necessárias para haver a conscientização da população acerca do isolamento social em meio a crise econômica no cenário brasileiro. Por isso, o Estado, no papel do Ministério da Cidadania, responsável pela elaboração de programas de auxílio aos brasileiros, a fim de ajudar a população, para se conscientizem sobre o isolamento social, deve criar projetos de amparo as famílias de baixa renda, como a entregar de cestas básicas em sua moradias, para não haver a necessidade de sair de suas residências. Ademais, deve ser reduzida os valores das contas de utilidades para as pessoas de baixa renda. Destarte, a população estará em isolamento social e o Brasil conseguirá conter a pandemia.
```