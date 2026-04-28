# Diagnóstico — aesenem_sourceB_full_001122

**Fonte:** `aes-enem`

**Tema:** Marco temporal

**Tamanho do texto:** 1969 chars · **Latência Redato:** 73.7s

**Padrão:** DEFLAÇÃO · Δ = `-200` (Redato 600 vs Gabarito 800)

---

## Notas comparadas

| | C1 | C2 | C3 | C4 | C5 | TOTAL |
|---|---:|---:|---:|---:|---:|---:|
| **Gabarito INEP** | 160 | 160 | 120 | 200 | 160 | **800** |
| Redato derivacao (Python) | 80 | 160 | 160 | 120 | 80 | 600 |
| Redato final (após two-stage) | 80 | 160 | 160 | 120 | 80 | **600** |

## Drift por competência (Redato_final − Gabarito)

| | C1 | C2 | C3 | C4 | C5 |
|---|---:|---:|---:|---:|---:|
| Drift | -80 | +0 | +40 | -80 | -80 |

## Audit do LLM (resumido por competência)

### C1 — gabarito 160 · derivação 80 · final 80

- nota emitida pelo LLM: **80**
- desvios_gramaticais: list[7]
- desvios_gramaticais_count: 7
- erros_ortograficos_count: 3
- desvios_crase_count: 1
- desvios_regencia_count: 2
- falhas_estrutura_sintatica_count: 0
- marcas_oralidade: []
- reincidencia_de_erro: True
- reading_fluency_compromised: False
- threshold_check: {applies_nota_5=False, applies_nota_4=False, applies_nota_3=False, applies_nota_2=True, applies_nota_1=False, applies_nota_0=False}

### C2 — gabarito 160 · derivação 160 · final 160

- nota emitida pelo LLM: **160**
- theme_keywords_by_paragraph: list[4]
- tangenciamento_detected: False
- fuga_total_detected: False
- repertoire_references: list[2]
- has_reference_in_d1: True
- has_reference_in_d2: False
- tres_partes_completas: True
- partes_embrionarias_count: 0
- conclusao_com_frase_incompleta: False
- copia_motivadores_sem_aspas: False

### C3 — gabarito 120 · derivação 160 · final 160

- nota emitida pelo LLM: **160**
- has_explicit_thesis: True
- thesis_quote: O marco temporal ignora a luta indígena e revela a ausência de medidas efetivas para a garantia dos direitos desse povo.
- ponto_de_vista_claro: True
- ideias_progressivas: False
- planejamento_evidente: True
- autoria_markers: ['a limitação a uma data inibe a análise do contexto subjetivo de cada povo e pode suprimir os seus direitos', 'o marco temporal resume e limita a história indígena em uma data']
- encadeamento_sem_saltos: True
- saltos_tematicos: []
- argumentos_contraditorios: False
- informacoes_irrelevantes_ou_repetidas: True
- limitado_aos_motivadores: False

### C4 — gabarito 200 · derivação 120 · final 120

- nota emitida pelo LLM: **120**
- connectors_used: list[8]
- connector_variety_count: 8
- most_used_connector: Além disso / Além do mais
- most_used_connector_count: 1
- has_mechanical_repetition: True
- referential_cohesion_examples: ["'desse povo' retomando 'povo indígena'", "'esse povo' retomando 'indígenas' no P3", "'a eles' retomando 'Funai e os povos indígenas'"]
- ambiguous_pronouns: list[1]
- paragraph_transitions: list[3]
- complex_periods_well_structured: False
- coloquialism_excessive: False

### C5 — gabarito 160 · derivação 80 · final 80

- nota emitida pelo LLM: **80**
- elements_present: {}
- elements_count: 2
- proposta_articulada_ao_tema: True
- respeita_direitos_humanos: True

## Redação (texto_original)

```
O marco temporal defende a tese de que o povo indgena teria direito sob as terras ocupadas até a data da promulgação da Constituição de 1988. O debate é levantado em um cenário de disputas judiciais entre ruralistas e indígenas e evidencia a problemática da divisão das terras brasileiras, na qual o povo indgena após 521 anos da colonização portuguesa ainda não tm o seu direito à terra garantido. O marco temporal ignora a luta indgena e revela a ausência de medidas efetivas para a garantia dos direitos desse povo. Inicialmente cabe ressaltar que o marco temporal resume e limita a história indgena em uma data. Porém, a trajetória do povo originário do rasil é atemporal e subjetiva. Devido a sua cultura e contexto social, os indígenas não tiveram voz no período da colonização, sofreram desapropriações, violência e estavam sujeitos a barganhas diversas. Não existem registros suficientes para comprovar com exatidão as áreas de ocupação indgena desde o seu princípio. Além do mais, a limitação a uma data inibe a análise do contexto subjetivo de cada povo e pode suprimir os seus direitos. Outro ponto a ser ressaltado é a ausência de soluções definitivas para a demarcação das terras indígenas. Cinco séculos após a colonização e esse povo que já residia nas terras brasileiras ainda não tem garantia sobre o seu espaço legal e enfrenta constantes disputas de terras frente  extrativistas e ruralistas. O marco temporal mostra mais uma vez que a resposta tardia a essa temática tende a contribuir para a supressão dos direitos dos indígenas, sendo mais uma demonstração de cancelamento da história, cultura e da presença desse povo no país. Diante do exposto, cabe ao Supremo Tribunal Federal defender o direito originário dos indígenas  terra diante da proposta do marco temporal. Além disso, é necessário que a Funai e os povos indígenas atuem fortemente no sentido de garantir legalmente de modo definitivo a área que pertence a eles por direito originário.
```