# REDATO — RUBRICA V2 (AUTORITATIVA)

**Base:** PDFs institucionais da corretora-parceira ("Relatório de Competências" e "Comando das Competências"), com treinamento INEP.
**Correções aplicadas:** Tensão 3 — embaralhamento entre competências.
**Data:** 2026-04-24

---

## 0. CHECAGENS PRÉ-CORREÇÃO (ZERAM A REDAÇÃO)

Antes de avaliar por competência, a LLM deve verificar:

### 0.1 — Anulação imediata (nota 0 em todas as competências)

A redação recebe **0 em todas as competências** se:

- Fuga total ao tema
- Não obediência ao tipo dissertativo-argumentativo (narrativo, descritivo, expositivo puro)
- Extensão ≤ 7 linhas manuscritas (≤ 10 em braille)
- Cópia de textos da prova sem pelo menos 8 linhas de produção própria
- Desenhos ou sinais gráficos sem função evidente
- Parte deliberadamente desconectada do tema
- Impropérios ou termos ofensivos
- Assinatura fora do local designado
- Texto predominantemente em língua estrangeira
- Folha de redação em branco
- Texto ilegível

### 0.2 — Regras de contagem de linhas

- O título (se houver) **conta** como linha escrita pelo aluno e deve ser coerente com o tema.
- Trechos copiados dos textos motivadores **não contam** na extensão — só conta produção própria.
- Mínimo de 8 linhas de produção própria para não ser anulado por cópia.

### 0.3 — Coloquialismo × metáfora

- Coloquialismo excessivo impacta **C4** (coesão/coerência), não C1 (gramática).
- Metáforas são permitidas se adequadas ao contexto e não comprometem clareza/formalidade.

---

## 1. COMPETÊNCIA I — DOMÍNIO DA NORMA CULTA

**Base contábil:** contagem de desvios gramaticais, ortográficos e de convenções da escrita.

### Rubrica (thresholds numéricos do PDF)

- **Nota 5 (200 pts).** No máximo 2 desvios totais. Apenas 1 palavra com erro ortográfico. No máximo 1 desvio de crase. Registro formal sem coloquialismos. No máximo 1 falha de estrutura sintática.
- **Nota 4 (160 pts).** Até 3 desvios gramaticais sem prejuízo de compreensão. Até 3 erros ortográficos. Até 2 desvios de regência. Desvios esporádicos de crase. Reincidência de um erro gramatical isolado aceitável.
- **Nota 3 (120 pts).** Até 5 desvios gramaticais. Estrutura sintática regular com falhas que não afetam fluidez. Erros pontuais de ortografia e pontuação. Sentido geral mantido.
- **Nota 2 (80 pts).** Estrutura sintática deficitária, OU estrutura regular com muitos desvios (aplica-se o nível inferior). Erros frequentes de concordância. Muitos erros de pontuação/ortografia dificultando leitura. Registro inadequado com gírias/regionalismos.
- **Nota 1 (40 pts).** Desvios diversificados e frequentes. Domínio precário sistemático. Frequentes falhas de regência e escolha vocabular.
- **Nota 0 (0 pts).** Estrutura sintática inexistente. Desconhecimento da norma. Erros em todas as convenções.

### Critérios do PDF mantidos, critérios de C4 REMOVIDOS

**MANTIDO em C1:**
- Convenções da escrita (acentuação, ortografia, hífen, maiúsculas, translineação)
- Gramática (regência, concordância, tempos/modos verbais, pontuação, paralelismo, pronomes, crase)
- Escolha de registro (formal × informal/oralidade)
- Escolha vocabular (precisão de sentido)

**REMOVIDO de C1 (foi realocado para C4):**
- ~~"coerência e coesão impecáveis, com uso correto de conectores e pronemos"~~ — isso é C4
- ~~"boa coesão e coerência, mas erros mínimos de ortografia"~~ — metade é C4

### Feedback pedagógico (não afeta a nota)

Para o feedback ao aluno, a LLM **pode** classificar desvios por gravidade (grave/médio/leve) como ferramenta didática, mas **a nota é calculada pela contagem numérica do PDF**, sem ponderação por gravidade. Um erro é um erro na soma.

---

## 2. COMPETÊNCIA II — COMPREENSÃO DO TEMA E REPERTÓRIO

### Rubrica (PDF, integralmente adotada)

- **Nota 5 (200 pts).**
  - Bom domínio do tema.
  - Citação das palavras-chave do tema (ou sinônimos) em pelo menos a maioria dos parágrafos.
  - Argumentação consistente com repertório sociocultural **produtivo** e **legitimado**.
  - Repertório = exemplos históricos, frases, músicas, textos, autores famosos, filósofos, estudos, artigos, publicações.
  - Excelente domínio do dissertativo-argumentativo: proposição, argumentação, conclusão.
  - Não copia textos motivadores.
  - **Vínculo explícito** entre repertório e discussão.
  - **Fonte citada** (autor, obra, música, série, pesquisa, data).
  - **Ao menos um repertório no D1 e outro no D2.**
- **Nota 4 (160 pts).** Argumentação consistente, mas repertório menos produtivo. 3 partes completas, nenhuma embrionária. Informações pertinentes sem aprofundamento.
- **Nota 3 (120 pts).** Abordagem completa, mas 1 das 3 partes pode ser embrionária. Repertório baseado nos textos motivadores OU não legitimado OU legitimado mas não pertinente. Argumentação previsível, superficial.
- **Nota 2 (80 pts).** Abordagem completa obrigatória, mas problemas de tipo textual e/ou muitos trechos de cópia sem aspas. 2 partes embrionárias OU conclusão com frase incompleta.
- **Nota 1 (40 pts).** Tangenciamento ao tema. Traços de outros tipos textuais. Sem argumentação clara.
- **Nota 0 (0 pts).** Fuga total. Não é dissertativo-argumentativo. Anulada.

### Regra de palavras-chave (crítica para C2)

A LLM deve:
1. Decompor o tema em palavras principais.
2. Verificar se cada parágrafo cita a maioria dessas palavras ou sinônimos diretos.
3. Sinalizar tangenciamento se um ou mais parágrafos omitirem as palavras-chave.
4. Sinalizar fuga total se nenhum parágrafo citar as palavras-chave.

**Exemplo aplicado ao tema "Democratização do acesso ao cinema no Brasil":**
- Palavras-chave: democratização, cinema, acesso, Brasil.
- Cada parágrafo deve conter a maioria dessas palavras (ou sinônimos: "ampliação", "sétima arte", "democratizar o ingresso", "país", "território nacional").

### Detecção RIGOROSA de tangenciamento

O critério de "palavras-chave ou sinônimos diretos" é **estrito**. Generalização
temática **não é sinônimo direto**:

- Tema: *"Impactos das redes sociais na saúde mental dos jovens"*
  - Palavras-chave: `redes sociais`, `saúde mental`, `jovens/juventude`.
  - Sinônimos aceitos: `mídias sociais`, `Instagram`, `TikTok`, `plataformas digitais` (= redes sociais); `bem-estar psíquico`, `ansiedade`, `depressão` (= saúde mental); `adolescentes`, `estudantes`, `geração Z` (= jovens).
  - **NÃO** são sinônimos diretos: `tecnologia`, `ambiente digital`, `sistemas digitais`, `novas gerações`, `contemporaneidade`. São generalizações temáticas mais amplas.

**Regra operacional:**
- Se o aluno discute *"tecnologia"* quando o tema é *"redes sociais"* → tangenciamento. Marque `tangenciamento_detected = true`, C2 = 40.
- Ter um ou dois parágrafos com sinônimos diretos NÃO salva o conjunto. Cada parágrafo deve ter a maioria das palavras-chave (ou sinônimos diretos — não generalizações).
- Quando `tangenciamento_detected = true`, a nota máxima de C2 é 40 (PDF nota 1). Não suba por qualidade argumentativa — isso é C3, não C2.

### Regra rígida de isolamento de C2 (anti-propagação)

Quando você classifica uma referência como `legitimacy: "legitimated"` e `productivity: "productive"`, ela CONTA integralmente para C2 — independentemente de como o texto está estruturado em C3.

**Exemplo concreto.** Texto com 7 referências legitimadas (Han, Bauman, OMS, Orlowski, Zuboff, Turkle, IBGE) mas sem tese clara e argumentação fragmentada:
- C2 = 200 — o repertório está lá, verificável, contextualizado.
- C3 = 80 — ausência de projeto de texto.
- NÃO rebaixe C2 para 120 ou 160 "porque o projeto é fraco". Isso é confundir competências.

Classifique `productivity` com base em como a referência dialoga com o argumento **dela própria** (frase/parágrafo), não com a qualidade global do texto. Uma referência bem ancorada ao seu próprio enunciado é `productive` mesmo que o texto como um todo seja desarticulado.

---

## 3. COMPETÊNCIA III — SELEÇÃO E ORGANIZAÇÃO DAS INFORMAÇÕES

### Rubrica (PDF, com correção da Tensão 3)

- **Nota 5 (200 pts).** Ideias progressivas e bem selecionadas. Planejamento claro. Informações relacionadas ao tema, consistentes e organizadas. Autoria: argumentos originais que reforçam o ponto de vista. Encadeamento entre parágrafos sem saltos temáticos. Poucas falhas que não prejudicam a progressão.
- **Nota 4 (160 pts).** Informações organizadas com indícios de autoria. Organização clara, mas argumentação não tão sólida. Algumas informações pouco desenvolvidas.
- **Nota 3 (120 pts).** Ideias previsíveis, limitadas aos textos motivadores. Pouca evidência de autoria. Argumentos simples sem progressão clara.
- **Nota 2 (80 pts).** Informações desorganizadas ou contraditórias. Limitado aos motivadores. Argumentos inconsistentes. Ideias mal conectadas.
- **Nota 1 (40 pts).** Informações pouco relacionadas ao tema. Ideias dispersas. Sem ponto de vista claro.
- **Nota 0 (0 pts).** Informações não relacionadas ao tema. Totalmente desconexas. Sem planejamento.

### Correção da Tensão 3

**REMOVIDO de C3 (foi realocado para C4):**
- ~~"perdeu linhas com informações irrelevantes, repetidas ou excessivas"~~ — é C4 (coesão)

---

## 4. COMPETÊNCIA IV — MECANISMOS LINGUÍSTICOS

### Rubrica (PDF, com correção da Tensão 3)

- **Nota 5 (200 pts).** Articulação entre partes do texto. Repertório diversificado de recursos coesivos. Referenciação adequada (pronomes, sinônimos, advérbios). Transições claras (causa/consequência, comparação, conclusão). Períodos complexos bem organizados. Sem repetição excessiva de conectivos.
- **Nota 4 (160 pts).** Articulação com poucas inadequações. Repertório diversificado com falhas pontuais. Transições adequadas com pequenos deslizes. Boa coesão e coerência com falhas pontuais.
- **Nota 3 (120 pts).** Articulação mediana com inadequações frequentes. Repertório pouco diversificado. Uso repetitivo de conectivos ou pronomes. Transições previsíveis. Organização mediana dos períodos.
- **Nota 2 (80 pts).** Articulação insuficiente com muitas inadequações. Repertório limitado. Repetição excessiva ou uso inadequado. Conexões falhas entre parágrafos. Períodos mal estruturados.
- **Nota 1 (40 pts).** Articulação precária. Recursos coesivos praticamente inexistentes. Parágrafos desarticulados. Períodos curtos desconectados.
- **Nota 0 (0 pts).** Informações desarticuladas. Sem recursos coesivos. Total falta de conexão.

### Correção da Tensão 3

**MANTIDO em C4:**
- Articulação entre parágrafos e dentro deles
- Repertório de recursos coesivos (conectivos, pronomes, advérbios, sinônimos)
- Estruturação de períodos complexos
- Referenciação (pessoas, coisas, lugares retomados)
- Impacto de coloquialismo excessivo

**REMOVIDO de C4:**
- ~~"utilizou conectivos em todo início de período"~~ — prescrição discutível, não matricial, pode levar a texto mecânico. Substituído por: "transições claras entre períodos, com ou sem conectivo inicial explícito."

---

## 5. COMPETÊNCIA V — PROPOSTA DE INTERVENÇÃO

### Rubrica (PDF, contagem de elementos)

**Os 5 elementos exigidos:**
1. **Agente** — quem executa.
2. **Ação** — o que é feito.
3. **Modo/Meio** — como é feito.
4. **Finalidade** — qual efeito se alcança.
5. **Detalhamento** — informação adicional que aprofunda um dos elementos anteriores.

### Rubrica por contagem

- **Nota 5 (200 pts).** 5 elementos presentes, bem detalhados e articulados à discussão.
- **Nota 4 (160 pts).** 4 elementos presentes.
- **Nota 3 (120 pts).** 3 elementos presentes.
- **Nota 2 (80 pts).** 2 elementos presentes OU proposta mal articulada ao tema.
- **Nota 1 (40 pts).** 1 elemento presente.
- **Nota 0 (0 pts).** Sem proposta OU proposta desconectada do tema.

### Como identificar cada elemento

**Regra geral:** para cada elemento marcar `present: true`, você precisa
fornecer um `quote` **literal** (não inferido) extraído da proposta. Se não
consegue citar um trecho literal que contenha o elemento, `present: false`.
Não conte "implícito".

- **Agente presente:** há um sujeito nomeado da ação (governo, Ministério X, Congresso, ONGs, escolas, mídia). Agentes muito genéricos ("a sociedade", "todos") contam como presentes pelo PDF, mas devem ser sinalizados com `generic: true`.
- **Ação presente:** há um verbo de ação concreto **literal** no texto (criar, implementar, regulamentar, promover, atuar, agir). Se só há intenção ("é preciso fazer algo"), marque `present: false`.
- **Modo/Meio presente:** há instrumento ou canal **explícito** no texto ("por meio de", "através de", "utilizando", "com campanhas", "via lei"). *Criar políticas públicas* não é meio — é ação repetida. *Implícito não conta.*
- **Finalidade presente:** há objetivo **declarado** via marcador ("a fim de", "para que", "com o objetivo de", "para"). *"Precisa de atenção"* ou *"tema que exige atenção"* não é finalidade.
- **Detalhamento presente:** há informação adicional no texto que aprofunda qualquer dos quatro elementos acima. Pode ser: detalhar quem dentro do órgão atua, especificar periodicidade/duração/formato da ação, explicar instrumento concreto, articular a finalidade à tese, ou dar exemplo concreto. **Basta uma dessas formas estar presente literalmente para o elemento contar.**

**Exemplo de contagem estrita.** Proposta *"O Ministério da Educação deve
atuar contra esse problema. O Congresso Nacional também precisa agir. Esse
é um tema que exige atenção das autoridades competentes."*

- `agente.present = true` (Ministério / Congresso nomeados)
- `acao.present = true` (*"atuar"*, *"agir"* são verbos de ação mínimos)
- `modo_meio.present = **false**` — nenhum "por meio de", "através de", instrumento ou canal literal
- `finalidade.present = **false**` — *"tema que exige atenção"* não é finalidade declarada
- `detalhamento.present = **false**` — nenhuma especificação adicional
- `elements_count = 2` → PDF nota 2 → **C5 = 80**

Não infira meio ou finalidade quando não há marcador literal. "Deve atuar
contra esse problema" não contém finalidade — contém ação.

### Nota sobre o adendo de detalhamento (preservado do trabalho anterior)

As cinco modalidades de detalhamento que mapeamos (agente, ação, modo, finalidade, exemplo) **continuam válidas como critérios para identificar se o elemento está presente**. A mudança frente ao trabalho v1 é que essas modalidades não são mais "níveis de qualidade" — qualquer uma delas, bem executada, faz o elemento "detalhamento" contar como presente.

---

## Síntese das mudanças v1 → v2

| Competência | Mudança |
|---|---|
| C1 | Adotada contagem numérica do PDF. Classificação por gravidade (grave/médio/leve) fica só no feedback pedagógico, não na nota. Removidos critérios de C4. |
| C2 | Adicionada checagem de palavras-chave por parágrafo. Repertório baseado em motivadores = nota 3, não nota 4. |
| C3 | Integralmente mantida do PDF. Removido critério de "linhas perdidas" (era C4). |
| C4 | Integralmente mantida do PDF. Removido "conectivo em todo início de período". |
| C5 | Adotada contagem de elementos do PDF. As 5 modalidades de detalhamento viram critérios de identificação do elemento, não hierarquia de qualidade. |
| Pré-correção | Nova seção: 12 critérios de anulação, regras de contagem de linhas, tratamento de coloquialismo/metáfora. |
