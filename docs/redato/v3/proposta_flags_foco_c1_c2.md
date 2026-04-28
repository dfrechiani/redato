# Proposta — Flags para Modos `foco_c1` e `foco_c2`

**Status:** Decisões pedagógicas tomadas em 2026-04-28 — ver bloco abaixo. `foco_c2` aprovado para implementação; `foco_c1` adiado.
**Data:** 2026-04-28
**Autor da proposta:** Claude (técnico). Daniel revisa, ajusta e decide pedagogicamente.
**Objetivo:** Definir flags candidatas para destravar o bloqueio temporário do portal nos modos `foco_c1` (norma culta) e `foco_c2` (compreensão da proposta), permitindo que `FOCO_C1_TOOL` e `FOCO_C2_TOOL` sejam adicionados a `redato_backend/missions/schemas.py`.

---

## STATUS — DECISÕES DANIEL 2026-04-28

### `foco_c2`: APROVADO PARA IMPLEMENTAÇÃO
- 5 flags conforme Seção D
- Caps com defesa em profundidade (tool emite, Python aplica)
- Missões: `RJ2·OF04·MF`, `RJ2·OF06·MF`

### `foco_c1`: ADIADO
- 6 flags propostas mantidas como referência (Seção B)
- `FOCO_C1_TOOL` não será implementado nesta fase
- Razão: nenhuma missão atual usa modo `foco_c1`
- Reativar quando: oficina de revisão gramatical for criada (provavelmente 3ª série ou volume futuro)

### Decisões pontuais (Seção G respondidas)
- **G.1** Granularidade C1: consolidada por dimensão (proposta atual). Aprovado.
- **G.2** `repertorio_de_bolso`: compartilhar nome com `completo_parcial`. Aprovado.
- **G.3** Ordem de implementação: somente `foco_c2` agora. `foco_c1` adiado.
- **G.4** Caps duros: tool reporta a flag, Python aplica o cap em camada superior. Defesa em profundidade.
- **G.5** Missão para `foco_c1`: adiar tool. Manter só proposta documentada.

**Bases consultadas:**

- Cartilha INEP do(a) Participante — A Redação do ENEM 2025 (`inep_cartilhas/cartilha_enem_2025.pdf`, seções 1.1 e 1.2).
- Rubrica v2 autoritativa do projeto (`docs/redato/v2/rubrica_v2.md`, seções 1 e 2).
- Schemas existentes (`redato_backend/missions/schemas.py` — `FOCO_C3_TOOL`, `FOCO_C4_TOOL`, `FOCO_C5_TOOL`, `COMPLETO_PARCIAL_TOOL`).
- Catálogo canônico de detectores (`redato_backend/portal/detectores.py`).

**Decisões pedagógicas registradas (entrada):**

- `foco_c2` é **C2 PURO**: cobre apenas (a) compreensão da proposta — não fugiu/tangenciou; (b) tipo textual dissertativo-argumentativo; (c) repertório articulado. Não inclui aspectos de C3 (argumentação, autoria, projeto de texto).
- `foco_c1` é **norma culta**: granularidade (erros graves/leves separados ou unificados) é decisão pedagógica do Daniel. A proposta abaixo recomenda dimensão (consolidada) com justificativa, e oferece alternativa por gravidade.

---

## Sumário

- [A. Análise de C1 (norma culta) na rubrica oficial](#a-análise-de-c1-norma-culta-na-rubrica-oficial)
- [B. Flags candidatas para `foco_c1`](#b-flags-candidatas-para-foco_c1)
- [C. Análise de C2 (compreensão da proposta)](#c-análise-de-c2-compreensão-da-proposta)
- [D. Flags candidatas para `foco_c2`](#d-flags-candidatas-para-foco_c2)
- [E. Tabela comparativa — overlaps com flags existentes](#e-tabela-comparativa--overlaps-com-flags-existentes)
- [F. Rascunho do bloco `TOOLS_BY_MODE`](#f-rascunho-do-bloco-tools_by_mode)
- [G. Pontos abertos para decisão do Daniel](#g-pontos-abertos-para-decisão-do-daniel)

---

## A. Análise de C1 (norma culta) na rubrica oficial

### A.1 — O que C1 avalia exatamente (Cartilha INEP 2025)

Trecho oficial: *"A Competência I avalia se o(a) participante domina a modalidade escrita formal da língua portuguesa"*. Quatro dimensões avaliadas (lista canônica do INEP, em ordem):

1. **Convenções da escrita** — acentuação, ortografia, uso de hífen, emprego de letras maiúsculas e minúsculas, separação silábica (translineação).
2. **Gramaticais** — regência verbal e nominal, concordância verbal e nominal, tempos e modos verbais, pontuação, paralelismos sintático/morfológico/semântico, emprego de pronomes, crase.
3. **Escolha de registro** — ausência de uso de registro informal e/ou marcas de oralidade.
4. **Escolha vocabular** — emprego de vocabulário preciso (palavras usadas em sentido correto e apropriado ao contexto).

Avaliada em paralelo, **estrutura sintática**: períodos truncados (ponto onde deveria haver vírgula), justaposição (vírgula onde deveria haver ponto), ausência ou excesso de elementos sintáticos.

### A.2 — Tipos de erro mais comuns (das amostras INEP)

| Erro típico | Dimensão INEP | Frequência observada | Gravidade pedagógica |
|---|---|---|---|
| Concordância verbal (3ª pessoa do plural) | Gramatical | Muito alta | Média |
| Crase indevida ou ausente | Gramatical | Muito alta | Média |
| Acentuação gráfica (proparoxítona, hiato) | Convenções | Alta | Baixa |
| Pontuação (vírgula entre sujeito-verbo) | Gramatical | Alta | Média |
| Coloquialismo ("a gente", "tipo assim") | Registro | Alta | Média |
| Palavra com sentido errado | Vocabular | Média | Alta |
| Período truncado / justaposição | Estrutura sintática | Alta | Alta |
| Regência ("preferir do que") | Gramatical | Média | Média |
| Paralelismo quebrado em listas | Gramatical | Baixa | Baixa |
| Pronome "lhe/o/a" em uso oblíquo errado | Gramatical | Baixa | Baixa |

### A.3 — Granularidade adequada para detecção automatizada

**Decisão de design proposta:** flags **por dimensão**, não por tipo de erro individual. Justificativas:

1. A rubrica oficial INEP **conta desvios totais**, sem ponderar por tipo de erro (ver `rubrica_v2.md` seção 1: *"a nota é calculada pela contagem numérica do PDF, sem ponderação por gravidade. Um erro é um erro na soma."*).
2. Flags qualitativas (booleanas no schema do tool) servem para sinalizar **padrões pedagógicos** — não substituem a contagem. Padrão = aluno tem dificuldade com X dimensão, ou texto tem problema sistemático em Y. Flag por tipo individual (ex.: `crase_errada`, `concordancia_3pp_errada`) explode a complexidade do schema sem ganho proporcional.
3. Os outros modos (`foco_c3`, `foco_c4`, `foco_c5`) têm 3-5 flags qualitativas. Manter consistência facilita feedback uniforme ao professor.
4. Pedagogicamente, o aluno se beneficia mais de *"você tem desvio gramatical recorrente"* (com 3 exemplos no feedback_professor) que de *"você errou crase 4 vezes, concordância 2 vezes, regência 1 vez"* — o segundo informa o professor, o primeiro instiga revisão estrutural.

**Decisão alternativa (caso Daniel prefira granular):** seção F traz `FOCO_C1_TOOL_GRANULAR` como anexo opcional, com 8 flags por tipo de erro.

### A.4 — Diferença entre "muito graves", "graves" e "leves"

Hierarquia inferida da rubrica + amostras INEP:

- **Muito graves** (sinalizam domínio precário sistemático — Nota 0 ou 1):
  - Estrutura sintática inexistente (período sem sentido, palavras justapostas)
  - Erros em todas as convenções (ortografia + acentuação + pontuação simultaneamente)
  - Registro completamente inadequado (texto inteiro em coloquial)
- **Graves** (afetam a compreensão — Nota 2):
  - Concordância sistemática quebrada (3+ ocorrências do mesmo erro)
  - Regência sistemática quebrada
  - Coloquialismo recorrente sem ironia/citação
  - Pontuação que prejudica fluidez
- **Leves** (não afetam compreensão — Nota 3-4):
  - Acentuação esporádica (sem reincidência)
  - Crase pontual
  - Reincidência isolada de um único erro gramatical

A proposta de flags abaixo separa **graves** (severidade `alta` = `critical`) de **leves** (severidade `media` = `warning`). Não inclui flag específica para "muito graves" porque, segundo a rubrica v2, esses casos rebaixam C1 inteira para 40 ou 0 — o cap pela contagem já cobre.

---

## B. Flags candidatas para `foco_c1`

**6 flags propostas** (entre o mínimo de 4 e o máximo de 8 do brief). Severidade default = `media` (warning); flags `alta` = `critical` reservadas para problemas que sinalizam domínio precário sistemático.

### B.1 — `registro_informal_excessivo`

- **Descrição (1 linha):** Marcas de oralidade ou coloquialismo recorrentes prejudicam a formalidade exigida pelo gênero dissertativo-argumentativo.
- **Severidade:** `media` (warning)
- **Dispara quando:** ≥ 3 ocorrências de coloquialismos ("a gente", "tipo assim", "né", "daí"), gírias, ou abreviações tipo internet ("vc", "pq").
- **Exemplo de redação que dispara:**
  > *"A gente sabe que tipo, o desmatamento é um problema sério no Brasil, né? Daí o governo precisa fazer alguma coisa pra parar com isso."*
- **Justificativa:** A Cartilha INEP 2025 lista *"escolha de registro"* como uma das quatro dimensões de C1. Coloquialismos isolados não derrubam C1, mas recorrência sim — daí o threshold de 3 ocorrências.

### B.2 — `estrutura_sintatica_falha`

- **Descrição (1 linha):** Períodos truncados ou justapostos em frequência que prejudica a compreensão do texto.
- **Severidade:** `alta` (critical)
- **Dispara quando:** ≥ 2 períodos truncados (ponto final separando o que deveria ser uma única oração) ou ≥ 2 justaposições (vírgula no lugar de ponto final), causando ambiguidade ou quebra de raciocínio.
- **Exemplo de redação que dispara:**
  > *"O desmatamento avança. Pelas florestas brasileiras. Causando perda de biodiversidade, isso é um problema, devemos resolver, antes que seja tarde."*
- **Justificativa:** Cartilha INEP destaca explicitamente truncamento e justaposição como problemas de estrutura sintática. Severidade `alta` porque a rubrica v2 considera "estrutura sintática deficitária" como nota 2 (80) e "estrutura sintática inexistente" como nota 0.

### B.3 — `desvio_ortografico_grave`

- **Descrição (1 linha):** Erros ortográficos que descaracterizam palavras conhecidas ou mostram desconhecimento das convenções da escrita.
- **Severidade:** `alta` (critical)
- **Dispara quando:** ≥ 4 erros ortográficos em palavras de uso comum (não inclui acentuação esporádica em proparoxítonas raras), OU 1 erro que descaracteriza palavra ("xuva" para "chuva", "egzemplo" para "exemplo").
- **Exemplo de redação que dispara:**
  > *"A excola brasileira presisa de mais investimentu, pois o ensinu fundamental ainda não atingiu sua eccelência. Esse facto demonstra a desigualdade."*
- **Justificativa:** Cartilha INEP lista ortografia como primeira dimensão de C1. A rubrica v2 separa "1 palavra com erro ortográfico" (nota 5) de "muitos erros de ortografia dificultando leitura" (nota 2) — esta flag captura o segundo caso.

### B.4 — `desvio_gramatical_recorrente`

- **Descrição (1 linha):** Mesmo erro de concordância, regência ou crase aparece em 3 ou mais ocorrências, indicando padrão de domínio gramatical falho.
- **Severidade:** `media` (warning)
- **Dispara quando:** Mesma classe de erro gramatical (concordância OU regência OU crase) em ≥ 3 ocorrências distintas. Exemplos do mesmo aluno: três frases com concordância de 3ª pessoa do plural quebrada; ou três casos de crase faltando antes de palavra feminina.
- **Exemplo de redação que dispara:**
  > *"Os alunos brasileiro **enfrentam** dificuldades. As escolas pública **precisa** de reforma. Os pais **fica** preocupado com o futuro."* (concordância quebrada três vezes)
- **Justificativa:** A rubrica oficial admite "reincidência de um erro gramatical isolado aceitável" para nota 4, mas três ocorrências viram padrão. Esta flag distingue erro pontual de problema sistemático.

### B.5 — `vocabulario_impreciso`

- **Descrição (1 linha):** Palavras usadas com sentido inadequado ao contexto — escolha vocabular que distorce a intenção comunicativa.
- **Severidade:** `media` (warning)
- **Dispara quando:** ≥ 2 ocorrências de palavras usadas em sentido errado (não cabe no contexto), incluindo confusões frequentes ("infringir/infligir", "ratificar/retificar", "mal/mau", "à medida que/na medida em que").
- **Exemplo de redação que dispara:**
  > *"O governo deve **infligir** as leis ambientais para **ratificar** os erros do passado. Essa medida é fundamental ao **mau** funcionamento do país."*
- **Justificativa:** Cartilha INEP 2025: *"emprego de vocabulário preciso, o que significa que as palavras selecionadas são usadas em seu sentido correto e são apropriadas ao contexto"*. Esta flag captura o oposto operacional.

### B.6 — `paralelismo_quebrado`

- **Descrição (1 linha):** Listas, comparações ou enumerações com paralelismo sintático ou semântico violado.
- **Severidade:** `media` (warning)
- **Dispara quando:** Lista com itens em classes gramaticais diferentes ("estudar, leitura e escrever"), ou enumeração com mistura de tempos verbais ("educar, formaria e protege"), ou comparação sem termos paralelos ("é melhor estudar do que a ignorância").
- **Exemplo de redação que dispara:**
  > *"O Estado deve garantir educação, saúde e a proteção dos jovens. Quem estuda, lê e a leitura crítica desenvolve cidadania."*
- **Justificativa:** Cartilha INEP 2025 lista paralelismo (sintático, morfológico e semântico) como subitem da dimensão gramatical de C1. Erro relativamente raro mas decisivo no nível 200.

---

## C. Análise de C2 (compreensão da proposta)

### C.1 — O que C2 avalia exatamente (Cartilha INEP 2025)

Trecho oficial: *"Compreender a proposta de redação e aplicar conceitos das várias áreas de conhecimento para desenvolver o tema dentro dos limites estruturais do texto dissertativo-argumentativo em prosa"*.

Três dimensões (operacionais, na ordem da Cartilha):

1. **Compreensão da proposta** — atender ao recorte temático específico definido na proposta (não fugir, não tangenciar).
2. **Tipo textual** — produzir texto dissertativo-argumentativo em prosa (não narrativo, não descritivo, não expositivo puro), o que implica defender um ponto de vista, e não apenas expor ideias.
3. **Repertório sociocultural** — informações, fatos, citações ou experiências relacionadas ao tema, articuladas como argumento (não decorativas, não "de bolso").

### C.2 — Decisão registrada: C2 PURO

Por decisão pedagógica do Daniel, `foco_c2` cobre **somente** essas 3 dimensões. **Não inclui:**

- Aspectos de C3 (autoria, projeto de texto, encadeamento, profundidade argumentativa)
- Aspectos de C4 (coesão entre parágrafos, conectivos, articulação entre partes)
- Aspectos de C5 (proposta de intervenção)

Na rubrica v2 (seção 2, "Regra rígida de isolamento de C2 — anti-propagação"), está documentado: *"Quando você classifica uma referência como `productive`, ela CONTA integralmente para C2 — independentemente de como o texto está estruturado em C3"*. Esta proposta segue a mesma filosofia: as flags de `foco_c2` não devem rebaixar a nota por problemas que pertencem a outras competências.

### C.3 — Por que C2 é diferente das outras competências para detecção

C2 tem uma característica peculiar: dois dos seus problemas mais frequentes (**fuga ao tema** e **tipo textual inadequado**) são **caps duros**, não graduações. A Cartilha INEP define explicitamente:

- *"Considera-se que uma redação tenha fugido ao tema quando nem o assunto mais amplo nem o tema específico proposto são desenvolvidos"* → ANULAÇÃO (nota 0 em todas as competências, conforme rubrica v2 seção 0.1).
- Tangenciamento (abordou parte do tema, mas não o recorte específico) → cap C2 ≤ 80.
- Tipo textual completamente errado (narrativo puro) → ANULAÇÃO.

Isso significa que as flags de `foco_c2` precisam **incluir caps explícitos** no comportamento (campo `description` da flag descreve o cap), o que não acontece nas outras competências. A nota emitida pelo modelo deve respeitar o cap quando a flag é positiva.

---

## D. Flags candidatas para `foco_c2`

**5 flags propostas** (entre o mínimo de 3 e o máximo de 6 do brief). Severidade `alta` = `critical` para flags que disparam cap; `media` = `warning` para problemas graduais.

### D.1 — `tangenciamento_tema`

- **Descrição (1 linha):** Aborda assunto amplo do tema mas não o recorte específico definido na proposta — cap C2 ≤ 80.
- **Severidade:** `alta` (critical)
- **Dispara quando:** Aluno discute tema amplo (ex.: "tecnologia") quando o recorte específico é "redes sociais e saúde mental dos jovens"; ou cita palavras-chave do tema em zero ou apenas um parágrafo dentre os quatro; ou desloca a discussão para área correlata sem amarrar de volta ao recorte.
- **Exemplo de redação que dispara:**
  > Tema: *"Impactos das redes sociais na saúde mental dos jovens"*
  > Texto do aluno: *"A tecnologia transformou a sociedade contemporânea. Os meios de comunicação se diversificaram com a internet. As novas gerações vivem imersas em ambientes digitais cada vez mais sofisticados. É preciso refletir sobre os efeitos dessa transformação."*
  > → Discute tecnologia/internet em geral, não menciona "redes sociais" nem "saúde mental" nem "jovens" especificamente. Tangenciamento puro.
- **Justificativa:** Cartilha INEP 2025: *"é preciso atender ao recorte temático definido para evitar tangenciá-lo (abordar parcialmente o tema)"*. Rubrica v2: *"Sinalizar tangenciamento se um ou mais parágrafos omitirem as palavras-chave"* (e cap C2 ≤ 40 quando confirmado).

### D.2 — `fuga_tema`

- **Descrição (1 linha):** Não aborda nem o assunto amplo nem o recorte específico do tema — anula a redação inteira (nota 0 em todas as competências).
- **Severidade:** `alta` (critical)
- **Dispara quando:** Nenhum parágrafo cita palavras-chave do tema nem sinônimos diretos; aluno escreve sobre tema completamente diferente (escolheu outro tema, ou não compreendeu).
- **Exemplo de redação que dispara:**
  > Tema: *"Desafios para a valorização da herança africana no Brasil"*
  > Texto do aluno: *"A Revolução Industrial transformou a Europa no século XIX. As máquinas substituíram o trabalho artesanal e geraram novas dinâmicas sociais. O capitalismo se consolidou como sistema dominante."*
  > → Tema completamente fora do escopo. Fuga total.
- **Justificativa:** Cartilha INEP 2025: *"Considera-se que uma redação tenha fugido ao tema quando nem o assunto mais amplo nem o tema específico proposto são desenvolvidos"*. Rubrica v2 seção 0.1 lista fuga total como anulação imediata.

### D.3 — `tipo_textual_inadequado`

- **Descrição (1 linha):** Texto não é dissertativo-argumentativo — predominam marcas de narrativo, descritivo ou expositivo puro.
- **Severidade:** `alta` (critical)
- **Dispara quando:** Texto não defende ponto de vista (apenas expõe ou narra); estrutura organizada em sequência temporal ("primeiro... depois... finalmente") sem tese; ausência de tese explícita ou implícita; predominância de verbos no pretérito perfeito narrativo; descrição estática sem articulação argumentativa.
- **Exemplo de redação que dispara:**
  > Tema: *"Desafios para a valorização da herança africana no Brasil"*
  > Texto do aluno: *"Em 1500, os portugueses chegaram ao Brasil. Em seguida, vieram os africanos escravizados. Eles trouxeram suas tradições. Depois, a Lei Áurea foi assinada em 1888. Hoje em dia, o Brasil tem muitas culturas misturadas. As pessoas dançam capoeira e comem feijoada."*
  > → Sequência temporal narrativa, sem tese, sem ponto de vista, sem argumentação. Texto expositivo-narrativo.
- **Justificativa:** Cartilha INEP 2025: *"a proposta exige que o(a) participante escreva um texto dissertativo-argumentativo, que é um texto em que, por meio de argumentação, defende-se um ponto de vista. É mais do que uma simples exposição de ideias; por isso, você deve evitar elaborar um texto de caráter apenas expositivo, devendo assumir claramente um ponto de vista"*. Cap conforme rubrica v2 seção 0.1: *"Não obediência ao tipo dissertativo-argumentativo (narrativo, descritivo, expositivo puro)"* → ANULAÇÃO.

### D.4 — `repertorio_de_bolso`

- **Descrição (1 linha):** Repertório citado é genérico/decorado, aplicável a qualquer tema, sem articulação ao recorte proposto.
- **Severidade:** `media` (warning)
- **Dispara quando:** Cita autor/obra/conceito famoso ("Utopia de Thomas More", "instituições zumbis de Bauman", "alegoria da caverna de Platão", "todo cidadão tem direitos" de Constituição) sem aprofundar a conexão com o tema; menciona repertório como impacto retórico mas não como sustentação argumentativa; usa repertório que serviria igualmente bem a qualquer outro tema (= "guardado no bolso").
- **Exemplo de redação que dispara:**
  > Tema: *"Desafios para a valorização da herança africana no Brasil"*
  > Texto do aluno (parágrafo de introdução): *"'Utopia', a famosa obra do escritor britânico Thomas More, retrata uma cidade perfeita, livre de mazelas sociais. No entanto, a realidade brasileira é adversa à idealizada na obra, pois os desafios para valorização da herança africana do Brasil são uma problemática existente."*
  > → *Utopia* é repertório de bolso típico: aparece em redações de qualquer tema sem conexão genuína. (Exemplo extraído da Cartilha INEP 2025.)
- **Justificativa:** Cartilha INEP 2025 dedica seção inteira a "CUIDADO COM O REPERTÓRIO DE BOLSO!" — *"referências prontas, memorizadas e frequentemente utilizadas pelos(as) participantes, de forma genérica e pouco aprofundada, sem uma conexão genuína com o tema"*. Rubrica v2 seção 2 nota 3 caracteriza isso como "repertório baseado nos textos motivadores OU não legitimado OU legitimado mas não pertinente".
- **Cap aplicado:** quando `repertorio_de_bolso=true`, `nota_c2_enem ≤ 120` (rubrica oficial PDF nível 3 — repertório legitimado mas não pertinente). Cap declarado tanto na descrição da flag (Seção F.2) quanto no campo `description` de `nota_c2_enem` no `FOCO_C2_TOOL`. Aplicação em camada Python upstream (defesa em profundidade — decisão Daniel G.4).
- **Overlap:** Esta flag **já existe no `completo_parcial`** com mesmo nome. Ver tabela E para decisão de compartilhamento (Daniel aprovou compartilhar — G.2).

### D.5 — `copia_motivadores_recorrente`

- **Descrição (1 linha):** Trechos copiados literalmente dos textos motivadores (sem aspas) compõem porção significativa do texto, indicando ausência de produção autoral.
- **Severidade:** `media` (warning)
- **Dispara quando:** ≥ 2 sentenças completas reproduzidas literalmente dos textos motivadores sem marcação de citação, ou ≥ 25% do texto produzido constituído de cópia. (Cópia parcial com pelo menos 8 linhas de produção própria evita anulação por cópia integral, mas ainda merece flag.)
- **Exemplo de redação que dispara:**
  > Tema: *"Desafios para a valorização da herança africana no Brasil"*
  > Texto motivador I (Houaiss): *"Herança — o legado de crenças, conhecimentos, técnicas, costumes, tradições, transmitidos por um grupo social de geração para geração; cultura."*
  > Texto do aluno: *"A herança é o legado de crenças, conhecimentos, técnicas, costumes, tradições, transmitidos por um grupo social de geração para geração; cultura. Esse conceito é importante para entender o tema."*
  > → Primeira frase é cópia literal sem aspas.
- **Justificativa:** Cartilha INEP 2025: *"Não copie trechos dos textos motivadores. A recorrência de cópia é avaliada negativamente e fará com que sua redação tenha uma pontuação mais baixa ou, até mesmo, seja anulada como cópia"*. Rubrica v2 seção 0.1 lista anulação por cópia como caso extremo (≤ 8 linhas de produção própria); esta flag captura o caso intermediário (cópia parcial recorrente).
- **Nota técnica (Daniel, 2026-04-28):** a detecção desta flag depende dos textos motivadores estarem no contexto do LLM. Hoje o sistema passa apenas o tema da missão. Flag fica documentada mas não terá detecção efetiva até o pipeline de textos motivadores existir. Sugestão: implementar pipeline de motivadores como tarefa separada futura. Enquanto não houver pipeline, a flag pode ser emitida apenas em casos óbvios de cópia detectável sem comparação direta (ex.: aluno menciona "conforme o texto motivador" sem produção autoral subsequente).

---

## E. Tabela comparativa — overlaps com flags existentes

Inventário de todas as flags atualmente nos schemas (após M9, com 15 detectores adicionados ao catálogo):

| Modo | Flag existente | Domínio |
|---|---|---|
| `foco_c3` | `andaime_copiado` | Estrutura argumentativa |
| `foco_c3` | `tese_generica` | Argumentativo |
| `foco_c3` | `exemplo_redundante` | Argumentativo |
| `foco_c4` | `conectivo_relacao_errada` | Coesão |
| `foco_c4` | `conectivo_repetido` | Coesão |
| `foco_c4` | `salto_logico` | Argumentativo |
| `foco_c4` | `palavra_dia_uso_errado` | Vocabular específico |
| `foco_c5` | `proposta_vaga_constatatoria` | Proposta |
| `foco_c5` | `proposta_desarticulada` | Proposta |
| `foco_c5` | `agente_generico` | Proposta |
| `foco_c5` | `verbo_fraco` | Proposta |
| `foco_c5` | `desrespeito_direitos_humanos` | Proposta (cap) |
| `completo_parcial` | `topico_e_pergunta` | Tópico frasal |
| `completo_parcial` | `repertorio_de_bolso` | **Repertório** |
| `completo_parcial` | `argumento_superficial` | Argumentativo |
| `completo_parcial` | `coesao_perfeita_sem_progressao` | Coesão+progressão |

### E.1 — Overlaps detectados nas propostas

| Flag proposta | Já existe? | Onde | Decisão recomendada |
|---|---|---|---|
| `registro_informal_excessivo` | NÃO | — | Criar. Domínio C1 ainda não coberto. |
| `estrutura_sintatica_falha` | NÃO | — | Criar. Domínio C1 ainda não coberto. |
| `desvio_ortografico_grave` | NÃO | — | Criar. Domínio C1 ainda não coberto. |
| `desvio_gramatical_recorrente` | NÃO | — | Criar. Domínio C1 ainda não coberto. |
| `vocabulario_impreciso` | NÃO | — | Criar. Domínio C1 ainda não coberto. |
| `paralelismo_quebrado` | NÃO | — | Criar. Domínio C1 ainda não coberto. |
| `tangenciamento_tema` | NÃO | — | Criar. Específico de C2. |
| `fuga_tema` | NÃO | — | Criar. Específico de C2 (cap anulação). |
| `tipo_textual_inadequado` | NÃO | — | Criar. Específico de C2 (cap anulação). |
| `repertorio_de_bolso` | **SIM** | `completo_parcial` | **Compartilhar** (mesmo nome, mesma definição). |
| `copia_motivadores_recorrente` | NÃO | — | Criar. Específico de C2. |

### E.2 — Decisão sobre `repertorio_de_bolso` compartilhado

**Recomendação: compartilhar.** Mesmo nome em `foco_c2` e `completo_parcial`, mesma definição operacional. Justificativas:

1. **Conceito é único** — a Cartilha INEP define "repertório de bolso" de forma geral; não muda o significado conforme o escopo da avaliação.
2. **Catálogo de detectores já contém** — em `redato_backend/portal/detectores.py:447` (após M9) o detector `repertorio_de_bolso` está cadastrado uma vez, com categoria `argumentativo`, severidade `media`, descrição *"Repertório clichê reutilizável (ex.: Allan Kardec) sem encaixe específico no tema"*. Múltiplos modos podem emitir o mesmo detector — a UI desambigua pelo contexto da missão.
3. **Consistência pedagógica** — professor lê *"repertório de bolso detectado"* no dashboard com o mesmo significado, independentemente da missão. Trocar nome (`repertorio_decorativo`, `repertorio_clichê`) gera fragmentação semântica.

**Nota técnica:** se a decisão for compartilhar, o tool `FOCO_C2_TOOL` declara `repertorio_de_bolso` no enum de flags, e a contagem agregada no dashboard somar emissões dos dois modos. A entrada no catálogo de detectores **não muda** (não duplicar).

### E.3 — Não há overlaps em C1 com modos existentes

C1 trata norma culta — domínio que **nenhum outro modo** cobre. As 6 flags propostas para `foco_c1` são todas inéditas no catálogo. Se aprovadas, todas precisam ser adicionadas a `redato_backend/portal/detectores.py` no padrão M9 (severidade + descrição + categoria; categoria sugerida: `linguistico` para todas exceto `desvio_ortografico_grave` que vai em `ortografico`).

---

## F. Rascunho do bloco `TOOLS_BY_MODE`

Padrão segue exatamente os schemas existentes em `redato_backend/missions/schemas.py`. Os tools abaixo **não substituem o que está lá** — adicionam-se ao mesmo dict.

### F.1 — `FOCO_C1_TOOL`

```python
# ──────────────────────────────────────────────────────────────────────
# Modo Foco C1 (norma culta) — modo novo, missao_id pendente de
# atribuição pedagógica (atualmente nenhuma missão da 1S/2S usa C1
# isolado). Reservado para futura oficina de revisão gramatical.
# ──────────────────────────────────────────────────────────────────────

FOCO_C1_TOOL: Dict[str, Any] = {
    "name": "submit_foco_c1",
    "description": (
        "Avaliação Modo Foco C1 (norma culta). Aluno escreveu UM "
        "parágrafo (~100-200 palavras) com objetivo de demonstrar "
        "domínio da modalidade escrita formal. Avalie cada critério "
        "da rubrica REJ em score 0-100 (continuum granular dentro das "
        "bandas insuficiente/adequado/excelente), traduza para C1 ENEM "
        "0-200 considerando contagem de desvios, e produza feedback "
        "aluno + professor. NÃO conte erros sem contexto — analise "
        "cada desvio considerando se afeta a compreensão."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "modo": {"type": "string", "enum": ["foco_c1"]},
            # PENDENTE: missao_id depende de qual oficina vai ativar
            # foco_c1. Sem missão atribuída no seed atual. Quando
            # houver, atualizar enum.
            "missao_id": {"type": "string", "enum": ["TBD_FOCO_C1_MISSAO"]},
            "rubrica_rej": {
                "type": "object",
                "properties": {
                    "convencoes_escrita": _score_0_100(),
                    "gramatica": _score_0_100(),
                    "registro": _score_0_100(),
                    "vocabulario": _score_0_100(),
                },
                "required": [
                    "convencoes_escrita", "gramatica",
                    "registro", "vocabulario",
                ],
            },
            "confidences": {
                "type": "object",
                "description": "Opcional. Confiança 0-100 por critério.",
                "properties": {
                    "convencoes_escrita": _confidence_0_100(),
                    "gramatica": _confidence_0_100(),
                    "registro": _confidence_0_100(),
                    "vocabulario": _confidence_0_100(),
                },
            },
            "nota_rej_total": {
                "type": "integer",
                "minimum": 0,
                "maximum": 400,
                "description": (
                    "Soma dos 4 critérios (cada 0-100). Range 0-400."
                ),
            },
            "nota_c1_enem": {
                "type": "integer",
                "enum": _NOTA_ENEM,
                "description": (
                    "C1 ENEM 0-200 derivada da contagem de desvios + "
                    "rubrica v2. Caps: estrutura_sintatica_falha → ≤ 80; "
                    "desvio_ortografico_grave → ≤ 80; "
                    "outros desvios pontuais → ajuste fino dentro da banda."
                ),
            },
            "flags": {
                "type": "object",
                "properties": {
                    "registro_informal_excessivo": {
                        "type": "boolean",
                        "description": (
                            "true se há ≥ 3 ocorrências de coloquialismos, "
                            "gírias ou marcas de oralidade que prejudicam "
                            "a formalidade exigida pelo gênero "
                            "dissertativo-argumentativo."
                        ),
                    },
                    "estrutura_sintatica_falha": {
                        "type": "boolean",
                        "description": (
                            "true se há ≥ 2 períodos truncados ou "
                            "≥ 2 justaposições que prejudicam a "
                            "compreensão do texto. Cap C1 ≤ 80 quando "
                            "true."
                        ),
                    },
                    "desvio_ortografico_grave": {
                        "type": "boolean",
                        "description": (
                            "true se há ≥ 4 erros ortográficos em "
                            "palavras de uso comum, ou 1+ erro que "
                            "descaracteriza palavra. Cap C1 ≤ 80 "
                            "quando true."
                        ),
                    },
                    "desvio_gramatical_recorrente": {
                        "type": "boolean",
                        "description": (
                            "true se a mesma classe de erro gramatical "
                            "(concordância, regência ou crase) aparece "
                            "em ≥ 3 ocorrências distintas, indicando "
                            "padrão de domínio falho."
                        ),
                    },
                    "vocabulario_impreciso": {
                        "type": "boolean",
                        "description": (
                            "true se ≥ 2 palavras são usadas em sentido "
                            "errado para o contexto (ex.: infringir/infligir, "
                            "ratificar/retificar, mal/mau)."
                        ),
                    },
                    "paralelismo_quebrado": {
                        "type": "boolean",
                        "description": (
                            "true se há lista, comparação ou enumeração "
                            "com paralelismo sintático ou semântico "
                            "violado (ex.: 'estudar, leitura e escrever')."
                        ),
                    },
                },
                "required": [
                    "registro_informal_excessivo",
                    "estrutura_sintatica_falha",
                    "desvio_ortografico_grave",
                    "desvio_gramatical_recorrente",
                    "vocabulario_impreciso",
                    "paralelismo_quebrado",
                ],
            },
            "feedback_aluno": _feedback_aluno_schema(),
            "feedback_professor": _feedback_professor_schema(
                "100-200 palavras"
            ),
        },
        "required": [
            "modo",
            "missao_id",
            "rubrica_rej",
            "nota_rej_total",
            "nota_c1_enem",
            "flags",
            "feedback_aluno",
            "feedback_professor",
        ],
    },
}
```

### F.2 — `FOCO_C2_TOOL`

```python
# ──────────────────────────────────────────────────────────────────────
# Modo Foco C2 (compreensão da proposta) — modo novo. Decisão
# pedagógica registrada (Daniel, 2026-04-28): C2 PURO. Cobre apenas
# (a) compreensão da proposta, (b) tipo textual dissertativo-
# argumentativo, (c) repertório articulado. NÃO inclui aspectos de C3.
# Missões 2S que usam: RJ2·OF04·MF (Fontes e Citações),
# RJ2·OF06·MF (Da Notícia ao Artigo).
# ──────────────────────────────────────────────────────────────────────

FOCO_C2_TOOL: Dict[str, Any] = {
    "name": "submit_foco_c2",
    "description": (
        "Avaliação Modo Foco C2 (compreensão da proposta + tipo textual "
        "+ repertório). Aluno escreveu introdução dissertativa OU "
        "parágrafo com citação articulada (~80-150 palavras). Avalie "
        "APENAS C2 — não rebaixe por problemas de C3 (autoria, projeto "
        "de texto, profundidade argumentativa). Caps: fuga ao tema → 0; "
        "tipo textual inadequado → 0; tangenciamento → ≤ 80; "
        "repertório de bolso → ≤ 120."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "modo": {"type": "string", "enum": ["foco_c2"]},
            # 2 missões 2S usam foco_c2. Lista no enum.
            "missao_id": {
                "type": "string",
                "enum": ["RJ2_OF04_MF", "RJ2_OF06_MF"],
            },
            "rubrica_rej": {
                "type": "object",
                "properties": {
                    "compreensao_tema": _score_0_100(),
                    "tipo_textual": _score_0_100(),
                    "repertorio": _score_0_100(),
                },
                "required": [
                    "compreensao_tema", "tipo_textual", "repertorio",
                ],
            },
            "confidences": {
                "type": "object",
                "description": "Opcional. Confiança 0-100 por critério.",
                "properties": {
                    "compreensao_tema": _confidence_0_100(),
                    "tipo_textual": _confidence_0_100(),
                    "repertorio": _confidence_0_100(),
                },
            },
            "nota_rej_total": {
                "type": "integer",
                "minimum": 0,
                "maximum": 300,
                "description": (
                    "Soma dos 3 critérios (cada 0-100). Range 0-300."
                ),
            },
            "nota_c2_enem": {
                "type": "integer",
                "enum": _NOTA_ENEM,
                "description": (
                    "C2 ENEM 0-200. Caps obrigatórios: "
                    "fuga_tema=true → 0; "
                    "tipo_textual_inadequado=true → 0; "
                    "tangenciamento_tema=true → ≤ 80; "
                    "repertorio_de_bolso=true → ≤ 120."
                ),
            },
            "flags": {
                "type": "object",
                "properties": {
                    "tangenciamento_tema": {
                        "type": "boolean",
                        "description": (
                            "true se aborda assunto amplo do tema mas "
                            "não o recorte específico definido na "
                            "proposta. Cap C2 ≤ 80 quando true."
                        ),
                    },
                    "fuga_tema": {
                        "type": "boolean",
                        "description": (
                            "true se não aborda nem o assunto amplo nem "
                            "o recorte específico — anula a redação "
                            "(C2 = 0; rubrica oficial). Mutuamente "
                            "exclusiva com tangenciamento_tema."
                        ),
                    },
                    "tipo_textual_inadequado": {
                        "type": "boolean",
                        "description": (
                            "true se predominam marcas de narrativo, "
                            "descritivo ou expositivo puro em vez de "
                            "dissertativo-argumentativo. Anula a "
                            "redação (C2 = 0). Mutuamente exclusiva "
                            "com tangenciamento e fuga."
                        ),
                    },
                    "repertorio_de_bolso": {
                        "type": "boolean",
                        "description": (
                            "true se referência citada é genérica/"
                            "decorada, aplicável a qualquer tema, sem "
                            "articulação específica ao recorte (ex.: "
                            "Utopia de More, alegoria da caverna, "
                            "instituições zumbis de Bauman sem "
                            "aprofundamento). Cap C2 ≤ 120 quando true. "
                            "Compartilhada com modo completo_parcial."
                        ),
                    },
                    "copia_motivadores_recorrente": {
                        "type": "boolean",
                        "description": (
                            "true se ≥ 2 sentenças completas são "
                            "reproduzidas literalmente dos textos "
                            "motivadores sem marcação de citação, "
                            "indicando ausência de produção autoral."
                        ),
                    },
                },
                "required": [
                    "tangenciamento_tema",
                    "fuga_tema",
                    "tipo_textual_inadequado",
                    "repertorio_de_bolso",
                    "copia_motivadores_recorrente",
                ],
            },
            "feedback_aluno": _feedback_aluno_schema(),
            "feedback_professor": _feedback_professor_schema(
                "100-180 palavras"
            ),
        },
        "required": [
            "modo",
            "missao_id",
            "rubrica_rej",
            "nota_rej_total",
            "nota_c2_enem",
            "flags",
            "feedback_aluno",
            "feedback_professor",
        ],
    },
}
```

### F.3 — Atualização do `TOOLS_BY_MODE`

Conforme decisão G.3 (somente `foco_c2` é implementado nesta fase). `foco_c1` fica como referência documental — entrada no dict permanece comentada.

```python
TOOLS_BY_MODE: Dict[str, Dict[str, Any]] = {
    # foco_c1 ADIADO — sem missão atual.
    # Quando ativar: descomentar e adicionar FOCO_C1_TOOL.
    # "foco_c1": FOCO_C1_TOOL,
    "foco_c2": FOCO_C2_TOOL,            # NOVO (M9+)
    "foco_c3": FOCO_C3_TOOL,
    "foco_c4": FOCO_C4_TOOL,
    "foco_c5": FOCO_C5_TOOL,
    "completo_parcial": COMPLETO_PARCIAL_TOOL,
}
```

### F.4 — Bloqueio do portal: `foco_c2` destrava nesta fase, `foco_c1` permanece bloqueado

`portal_api.py` define `_MODOS_COM_PROMPT = set(TOOLS_BY_MODE.keys()) | {"completo"}`. Adicionar **apenas** `foco_c2` ao `TOOLS_BY_MODE` faz o helper `_modo_disponivel("foco_c2")` retornar `True` automaticamente, e o frontend para de desabilitar as 2 missões 2S (`RJ2·OF04·MF`, `RJ2·OF06·MF`) no dropdown sem mais nenhuma mudança.

`foco_c1` continua bloqueado pelo helper porque não entra em `TOOLS_BY_MODE` (decisão G.5). Isso **não causa problema operacional** — atualmente nenhuma missão (1S ou 2S) usa modo `foco_c1`, então não há atividade ativa que precise do bloqueio cair. Quando uma futura oficina (3S ou volume seguinte) atribuir `foco_c1`, basta:

1. Implementar `FOCO_C1_TOOL` conforme Seção F.1 desta proposta.
2. Descomentar a linha `"foco_c1": FOCO_C1_TOOL` em `TOOLS_BY_MODE`.
3. Adicionar `MissionMode.FOCO_C1` em `redato_backend/missions/router.py`.
4. Cadastrar as 6 flags de C1 em `redato_backend/portal/detectores.py`.
5. Bloqueio do portal cai sem mais código novo.

Tarefa de cleanup paralela à implementação de `foco_c2` (não bloqueia este merge):
- Atualizar `redato_backend/portal/detectores.py` com as 4 flags **novas** de C2: `tangenciamento_tema`, `fuga_tema`, `tipo_textual_inadequado`, `copia_motivadores_recorrente`. (`repertorio_de_bolso` já está cadastrado — decisão G.2 confirma compartilhamento). Categorias sugeridas: `argumentativo` para tangenciamento/fuga/tipo, `forma` para copia_motivadores_recorrente.
- Atualizar `redato_backend/missions/router.py` com `MissionMode.FOCO_C2` e mapeamento de `RJ2_OF04_MF` e `RJ2_OF06_MF` para `MissionMode.FOCO_C2`.
- Atualizar `_DEFAULT_MODEL_BY_MODE` (sugestão: Sonnet 4.6, mesmo padrão dos outros foco).
- Adicionar guard upstream em `_claude_grade_essay` (ou camada equivalente) para aplicar caps duros das flags de C2 em código Python — defesa em profundidade conforme decisão G.4. Tool emite a flag (informativa); Python aplica o cap final na nota.
- Documentar em `docs/redato/v3/series_oficinas_canonico.md` e em `docs/redato/v3/ATO2S_arvore_objetivos_v2.md` (Apêndice C/P5) que `foco_c2` foi destravado e que `foco_c1` permanece adiado por design.

---

## G. Pontos abertos para decisão do Daniel

### G.1 — Granularidade de C1 (consolidada por dimensão vs. por tipo de erro)

A proposta atual usa **6 flags por dimensão** (registro, estrutura sintática, ortografia, gramática, vocabulário, paralelismo). Alternativa rejeitada (por consistência com outros modos) seria **8+ flags por tipo de erro individual** (ex.: `crase_indevida`, `concordancia_3pp_quebrada`, `regencia_preferir_a`).

**Pergunta:** aprovar consolidação por dimensão, ou prefere granularidade fina?

### G.2 — `repertorio_de_bolso` compartilhada vs. renomeada

Proposta atual recomenda **compartilhar** o nome com `completo_parcial` (mesmo conceito INEP). Alternativa: renomear em `foco_c2` (ex.: `repertorio_clichê`, `repertorio_decorativo`) para evitar confusão sobre escopo de avaliação.

**Pergunta:** compartilhar, ou prefere renomear?

### G.3 — Ordem de implementação

Duas frentes podem rodar em paralelo ou em sequência:

- **Frente A:** implementar `FOCO_C2_TOOL` primeiro (destrava 2 missões 2S — OF04 e OF06).
- **Frente B:** implementar `FOCO_C1_TOOL` depois (não destrava nenhuma missão atual — é trabalho preparatório para futuras oficinas de revisão gramatical).

**Pergunta:** prioriza C2 (impacto imediato no portal) ou faz ambos juntos (entrega completa)?

### G.4 — Caps duros nas flags `fuga_tema` e `tipo_textual_inadequado`

A proposta declara que essas flags zeram C2. Pela rubrica oficial INEP, isso na verdade **anula a redação inteira** (todas as 5 competências = 0). Tecnicamente, esse comportamento de anulação acontece em camada superior à do tool — provavelmente em `_claude_grade_essay` ou em pré-validação por `compute_pre_flags`.

**Pergunta:** aceitar que o `FOCO_C2_TOOL` reporte essas flags como "informativas" (modelo emite a flag, mas a aplicação do cap de anulação é feita em código Python upstream), ou prefere que o tool não emita essas flags (deixa anulação 100% para validação prévia)?

### G.5 — Tema da missão para `foco_c1`

Atualmente nenhuma missão (1S ou 2S) usa modo `foco_c1`. As séries do livro 2S (OF01 = `completo_parcial`, OF04/OF06 = `foco_c2`, OF07/OF09 = `foco_c3`, OF12 = `foco_c5`, OF13 = `completo`) não cobrem norma culta isoladamente.

**Pergunta:** adiar `FOCO_C1_TOOL` até existir oficina pedagogicamente alocada (talvez 3ª série), ou implementar agora como infraestrutura preparatória?

---

## Anexo opcional — `FOCO_C1_TOOL_GRANULAR` (rejeitado por padrão)

Mantido aqui só para comparação. Caso Daniel responda G.1 com "prefere granular", esta versão substitui F.1.

```python
# Versão granular — 8 flags por tipo de erro individual.
# NÃO recomendada. Mantida só como referência caso a decisão
# pedagógica priorize feedback fino sobre consistência com outros modos.

FOCO_C1_TOOL_GRANULAR_FLAGS = {
    "concordancia_quebrada": "≥ 3 erros de concordância verbal ou nominal.",
    "regencia_inadequada": "≥ 2 erros de regência verbal ou nominal.",
    "crase_indevida": "≥ 2 erros de crase (uso ou ausência).",
    "ortografia_grave": "≥ 4 erros ortográficos OU 1 que descaracteriza.",
    "acentuacao_falha": "≥ 3 erros de acentuação gráfica (proparoxítona, hiato).",
    "pontuacao_problematica": "≥ 2 vírgulas mal usadas afetando fluência.",
    "registro_informal": "≥ 3 coloquialismos.",
    "estrutura_truncada": "≥ 2 períodos truncados/justapostos.",
}
```

---

**Fim da proposta.** Aguardando revisão do Daniel antes de qualquer implementação técnica.
