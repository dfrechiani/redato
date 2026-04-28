# GABARITO — REDAÇÕES-TESTE V2

**Use este arquivo APÓS rodar as 10 redações na Redato e salvar os outputs.**
Cada redação abaixo está mapeada a um canário do golden set, com a nota esperada, a justificativa pela rubrica v2 e os erros plantados. Compare campo a campo.

**Critério de sucesso global:** pelo menos 8/10 redações devem ter nota total dentro de ±40 pontos do gabarito, e as notas por competência devem respeitar a tolerância de ±40 por competência.

---

## REDAÇÃO TESTE 1 — Canário "control_nota_1000"

**Esperado:** C1=200, C2=200, C3=200, C4=200, C5=200 → **Total 1000**

**Função:** texto bem calibrado em todas as competências. Testa se a LLM consegue atribuir nota máxima sem "inventar defeitos".

**Por que é 1000:**
- **C1:** ausência de desvios gramaticais. Registro formal impecável. Verificar apenas se "a juventude" no trecho "à infância e a juventude" foi percebido como desvio ou não — é um único deslize possível. Se a LLM identificar, aceita-se C1=180. Nunca abaixo de 180.
- **C2:** repertório diversificado (Adam McKay, Maria Rita Kehl, Datafolha, The Social Dilemma, art. 227). Palavras-chave ("redes sociais", "saúde mental", "juventude"/"jovens") presentes em todos os parágrafos. Repertório no D1 (Kehl) e D2 (McKay na intro, The Social Dilemma no D2). Abordagem completa, sem partes embrionárias.
- **C3:** tese clara na introdução anunciando dois eixos (ansiedade + autoexposição). Eixos desenvolvidos em ordem. Autoria nas articulações ("Nas redes, essa exigência opera 24 horas por dia").
- **C4:** conectivos variados (Em primeiro lugar, Isso porque, Ademais, Dessa forma, Portanto, Complementarmente). Sem repetição mecânica.
- **C5:** agente (MEC + MS + Congresso), ação (implementar/aprovar), meio (oficinas mensais / legislação), finalidade (fortalecer autonomia / romper lógica), detalhamento (conduzidas por psicólogos e educadores treinados + auditoria pública independente). **5 elementos.**

**Bandeira vermelha:** se a LLM pontuar abaixo de 920, tem viés de criticismo obrigatório.

---

## REDAÇÃO TESTE 2 — Canário "c2_false_repertoire"

**Esperado:** C1=200, C2=**120**, C3=160, C4=200, C5=160 → **Total 840**

**Função:** testa detecção de repertório não legitimado / falso.

**Erros plantados em C2:**
- **Chavão de abertura:** "Aristóteles já afirmava que o homem é um ser social por natureza" — atribuição real mas clichê genérico, repertório decorativo.
- **Falsa atribuição 1:** "'a melhor maneira de prever o futuro é criá-lo' — Abraham Lincoln" — **frase apócrifa**. Lincoln nunca disse isso. A atribuição real (ainda incerta) costuma ser a Peter Drucker ou Alan Kay.
- **Dado sem fonte:** "Estudos recentes apontam que a maioria esmagadora dos adolescentes apresentam algum sintoma..." — sem fonte específica.
- **Artigo constitucional errado:** "art. 5º da Constituição Federal, que garante direitos invioláveis à vida, privacidade e dignidade" — o art. 5º realmente trata de direitos fundamentais gerais, mas **não é o artigo pertinente à proteção específica da infância e juventude** (que é o 227). A LLM deve sinalizar como "repertório legitimado mas não pertinente ao tema" — o que pelo PDF puxa para nota 3.
- **Menção vaga:** "Pesquisadores de diversas universidades do mundo" — sem nomear pesquisadores ou instituições.
- **Machado de Assis:** legítimo, mas a conexão com "comparação em redes" é forçada — repertório decorativo.

**Por que C2=120 (e não 80):** abordagem completa das 3 partes + repertório não legitimado/não pertinente = perfil exato da nota 3 pelo PDF.

**C1 em 200:** há 1 desvio de concordância ("a maioria esmagadora dos adolescentes apresentam" — deveria ser "apresenta") + 1 ortográfico. Dentro da tolerância do nível 5 pelo PDF (max 2 desvios + 1 erro ortográfico).

**C3 em 160:** organização clara, mas autoria fraca porque a argumentação apoia-se em referências problemáticas. Indícios de autoria presentes.

**C5 em 160:** agente (MEC + Congresso), ação (criar programas / aprovar leis), meio (campanhas permanentes / leis mais rígidas), finalidade (ensinar uso responsável / respeitar direitos). **4 elementos presentes**, detalhamento ausente ("campanhas permanentes" é muito genérico para contar como detalhamento). Fechamento com chavão "Somente assim" — não afeta a nota mas deve aparecer no feedback.

**Bandeiras vermelhas:**
- Se C2 >= 160: LLM não detectou a falsa atribuição a Lincoln. Viés crítico.
- Se C2 <= 80: LLM puniu demais — abordagem completa garante nota mínima 3 pelo PDF.

---

## REDAÇÃO TESTE 3 — Canário "c3_no_project"

**Esperado:** C1=200, C2=160, C3=**80**, C4=160, C5=200 → **Total 800**

**Função:** testa se a LLM detecta ausência de projeto de texto mesmo com repertório legítimo.

**Erros plantados em C3:**
- **Introdução sem tese:** cita Han, depois "As redes sociais têm diversas facetas e afetam os jovens de muitas maneiras distintas. Este é um tema que merece ser debatido com profundidade" — metalinguagem vazia.
- **D1 contraditório:** começa elogiando ("trazem benefícios inegáveis") com repertório pró (Instituto Alana / LGBTQIAP+), depois vira para crítica (Ana Beatriz Barbosa, OMS) sem articular a virada.
- **D2 justaposição:** cyberbullying → Molly Russell → Zuboff → art. 227 → vício → oito horas. Tópicos empilhados sem hierarquia.
- **Tópicos frasais ausentes:** nenhum parágrafo de desenvolvimento abre com argumento claro.

**Por que C3=80 (não 120):** pelo PDF, "informações desorganizadas OU contraditórias, limitadas aos motivadores, argumentos inconsistentes" = nota 2. O D1 é **contraditório** (pró + contra sem síntese), o que enquadra diretamente.

**C2=160 (não 200):** repertório diverso e legítimo (Instituto Alana, Ana Beatriz Barbosa, OMS, *O Dilema das Redes*, Molly Russell, Zuboff, art. 227), mas **decorativo** — cada referência aparece isolada sem sustentar argumentação. Pelo PDF: "repertório legitimado mas não bem articulado" puxa para nota 4. Não cai para 120 porque há referência no D1 e D2, abordagem completa.

**C5=200:** proposta completa, 5 elementos (MEC + secretarias / programa de educação midiática / oficinas quinzenais com profissionais qualificados / desenvolver leitura crítica / auditoria independente).

**Bandeiras vermelhas:**
- Se C3 >= 160: LLM confundiu "parágrafos sobre o tema" com "projeto argumentativo".
- Se C2 >= 180: LLM não penalizou o uso decorativo do repertório denso.

---

## REDAÇÃO TESTE 4 — Canário "c4_mechanical_cohesion"

**Esperado:** C1=200, C2=200, C3=200, C4=**120**, C5=200 → **Total 920**

**Função:** testa detecção de coesão mecânica com "além disso" repetido + repetição lexical + frases curtas justapostas.

**Erros plantados em C4:**
- **"Além disso" repetido 5 vezes** como conectivo mecânico.
- **Repetição lexical gritante:** "saúde mental dos jovens" 3x em sequência no P1; "Os algoritmos" 2x em sequência no P3; "O artigo 227 da Constituição Federal" repetido integralmente 3x em vez de retomado.
- **Pronome "Isso" em cadeia** no P3: "Isso fragiliza... Isso altera... Isso compromete..." — pronome vago sem retomada precisa.
- **Frases curtas justapostas:** o P1 inteiro é composto de sentenças simples que deveriam estar em períodos compostos.
- **Ausência de coesão referencial:** falta uso de pronomes e sinônimos.

**Por que C4=120 (nota 3 pelo PDF):** "repete várias vezes o mesmo conectivo ao longo do parágrafo" + "repertório pouco diversificado de recursos coesivos" + "uso repetitivo de pronomes" + "transições previsíveis" — casa exatamente com a descrição da nota 3.

**Não é C4=80 (nota 2):** a articulação existe (as ideias se conectam logicamente), só é mecânica. Nota 2 exigiria "conexões falhas, transições abruptas, orações desconectadas ou confusas" — aqui as conexões funcionam, só são pobres.

**Bandeiras vermelhas:**
- Se C4 >= 160: LLM não penalizou "além disso" 5x. Provavelmente está contando conectivos sem avaliar variedade.
- Se C4 <= 80: LLM puniu demais — a coerência está preservada.

---

## REDAÇÃO TESTE 5 — Canário "c5_vague_intervention" (equivalente ao 5 do golden set)

**Esperado:** C1=200, C2=200, C3=200, C4=200, C5=**120** → **Total 920**

**Função:** testa contagem correta em C5 quando a proposta é vaga mas tem presença nominal de elementos.

**Proposta do P4:**
> "Algo precisa ser feito sobre esse problema. A sociedade deve se conscientizar da gravidade da situação. As famílias precisam monitorar o uso de telas por seus filhos. As escolas também têm um papel importante a desempenhar. Apenas com a participação de todos os atores envolvidos será possível construir uma juventude mais saudável..."

**Contagem pelo PDF:**
- **Agente:** "sociedade", "famílias", "escolas" — todos PRESENTES, mas todos genéricos.
- **Ação:** "se conscientizar", "monitorar", "desempenhar papel" — PRESENTES, verbos de ação.
- **Modo/Meio:** AUSENTE. Não há "por meio de", instrumento ou canal.
- **Finalidade:** "construir uma juventude mais saudável" — PRESENTE, embora genérica.
- **Detalhamento:** AUSENTE. Nenhuma informação adicional concreta.

**3 elementos presentes → C5 nota 3 (120 pontos) pelo PDF.**

**Observação crítica:** a redação tem o restante (C1-C4) **idêntico** ao controle nota 1000 da Redação 6. Só o P4 é diferente. Teste perfeito de isolamento: se a LLM puxar alguma das outras competências para baixo por "contaminação", há viés de propagação.

**Bandeiras vermelhas:**
- Se C5 >= 160: LLM contou elementos fantasma (meio implícito). Contagem frouxa.
- Se C5 <= 80: LLM puniu qualitativamente em vez de contar elementos.
- Se C1, C2, C3 ou C4 ficarem abaixo de 180: propagação indevida.

---

## REDAÇÃO TESTE 6 — Canário "control_nota_1000" (segundo controle)

**Esperado:** C1=200, C2=200, C3=200, C4=200, C5=200 → **Total 1000**

**Função:** segundo texto-controle para confirmar que a LLM consegue reatribuir nota máxima em redação diferente da primeira.

**Por que é 1000:** estrutura impecável, repertório produtivo e diversificado, coesão variada, proposta completa com todos os 5 elementos bem articulados e detalhamento específico ("psicólogos escolares e professores capacitados em educação midiática").

**Bandeira vermelha:** se C1 ou C4 ficarem em 180, tudo bem (leitura rigorosa é aceitável). Se duas ou mais competências abaixo de 200, há viés.

---

## REDAÇÃO TESTE 7 — Caso-limite: C1 frequente + C5 incompleta

**Esperado:** C1=**40**, C2=200, C3=180, C4=160, C5=**80** → **Total 660**

**Função:** casos-limite simultâneos. Testa isolamento entre competências.

**Erros plantados em C1 (8 desvios):**
1. "se aplica as redes sociais" (crase)
2. "os jovens brasileiro se expõe" (concordância nominal + verbal)
3. "Isso por que" (confusão por que / porque)
4. "Instagram privilegia" + "os adolescente medem" (concordância)
5. "os jovem" (concordância nominal)
6. "algoritmos... potencializa" (concordância verbal)
7. "recorrendo à estímulos" (crase indevida)
8. "preso à um ciclo" (crase indevida)
9. "mau respeita" (mau/mal)

Na verdade são **9+ desvios** — pelo PDF, "diversificados e frequentes" → nota 1 (40).

**Erros em C5 — proposta vaga final:**
- Agente: "sociedade", "famílias", "escolas" — presentes mas genéricos.
- Ação: "se mobilizar", "assumir papel", "ter responsabilidade" — verbos de ação mínimos.
- Modo/Meio: AUSENTE.
- Finalidade: "construir um futuro mais saudável" — genérica, presente.
- Detalhamento: AUSENTE.

3 elementos mas todos genéricos e mal articulados → aplica critério "mal articulada ao tema" do PDF → nota 2 (80).

**Verificações críticas:**
- **C2 deve ficar em 200:** repertório legítimo (Han, Bauman, IBGE, *O Dilema das Redes*, art. 227), palavras-chave presentes, abordagem completa. Se cair abaixo de 180, há propagação.
- **C3 em 180:** tese presente e eixos anunciados, mas o fechamento fraco quebra levemente a progressão. Aceita-se 200 ou 180.
- **C4 em 160:** coesão funcional mas a proposta vaga prejudica a coesão macroestrutural.

**Bandeiras vermelhas:**
- Se C1 >= 80: LLM não percebeu a densidade dos desvios.
- Se C2 ou C3 abaixo de 160: propagação indevida.
- Se C5 >= 120: contagem frouxa.

---

## REDAÇÃO TESTE 8 — Canário "c3_weak_project_strong_repertoire"

**Esperado:** C1=200, C2=200, C3=**80**, C4=160, C5=200 → **Total 840**

**Função:** testa a distinção C2/C3 — repertório denso mas sem projeto.

**O texto contém 9 referências legítimas:** Han, Bauman, OMS, Orlowski, Kehl, UNICEF, Zuboff, Turkle, PNAD, Foucault. Todas corretamente atribuídas.

**Problemas de C3:**
- **Sem tese na introdução:** cita Han e diz "As redes sociais são um fenômeno amplo da contemporaneidade e merecem atenção cuidadosa" — metalinguagem.
- **Parágrafos são listas:** cada parágrafo de desenvolvimento empilha referências sem argumentação própria.
- **Sem ponto de vista claro:** o texto apenas reporta o que autores dizem, sem posicionamento.
- **Sem autoria:** toda afirmação é "segundo X", "conforme Y" — não há operação analítica.

Pelo PDF, C3 nota 2: "argumentos inconsistentes, ideias mal conectadas, desorganizadas" — o texto **é** organizado, mas o problema é que não há argumentos, só menções. Pode-se ler como nota 2 por ausência efetiva de defesa de ponto de vista. Gabarito: **80**, aceitando 120 com leitura generosa.

**C2 em 200:** repertório excepcional, produtivo no sentido de que cada referência é aplicável ao tema, abordagem completa, fontes citadas, palavras-chave em todos os parágrafos.

**Bandeira vermelha crítica:**
- Se C3 >= 160: LLM confundiu densidade de repertório com qualidade argumentativa. Este é o **viés mais perigoso** de detectar.

---

## REDAÇÃO TESTE 9 — Canário "c5_two_elements_only"

**Esperado:** C1=200, C2=200, C3=200, C4=180, C5=**80** → **Total 860**

**Função:** testa contagem mínima em C5.

**Proposta do P4 (integral):**
> "O Ministério da Educação deve atuar nesse problema. O Congresso Nacional também tem responsabilidade. Esse é um tema que exige a atenção das autoridades competentes do país."

**Contagem pelo PDF:**
- **Agente:** "Ministério da Educação", "Congresso Nacional" — PRESENTES (específicos, não genéricos).
- **Ação:** "atuar", "ter responsabilidade" — PRESENTES (verbos de ação mínimos).
- **Modo/Meio:** AUSENTE.
- **Finalidade:** AUSENTE (nenhum "a fim de", "para", objetivo declarado).
- **Detalhamento:** AUSENTE.

**2 elementos → C5 nota 2 (80 pontos) pelo PDF.**

**Observação:** o restante do texto (P1-P3) é idêntico ao controle nota 1000 (Redação 6). O único defeito é a proposta truncada no P4. Isso também derruba C4 levemente (180, aceitável 200) porque a conclusão fica desproporcional ao desenvolvimento.

**Bandeiras vermelhas:**
- Se C5 >= 120: LLM contou elementos inexistentes.
- Se C1, C2, C3 abaixo de 200: propagação indevida.

---

## REDAÇÃO TESTE 10 — Canário "c2_tangenciamento"

**Esperado:** C1=200, C2=**40**, C3=160, C4=200, C5=200 → **Total 800**

**Função:** testa detecção de tangenciamento por omissão de palavras-chave do tema.

**Problema central:** o texto fala sobre **"tecnologia"**, **"ambientes digitais"**, **"plataformas contemporâneas"**, **"sistemas algorítmicos"** — mas **NUNCA** usa literalmente "redes sociais" nem "saúde mental".

**Verificação parágrafo por parágrafo:**
- **P1:** "tecnologia digital", "novas gerações", "processos cognitivos". Nenhuma palavra-chave.
- **P2:** "ambientes digitais", "plataformas contemporâneas", "adolescentes", "problemas emocionais". Ausente "redes sociais" e "saúde mental".
- **P3:** "ambientes digitais", "sistemas algorítmicos", "usuário", "concentração". Ausente.
- **P4:** "tecnologia", "ambientes digitais", "plataformas digitais", "menores de idade". Ausente.

**Sinônimos muito amplos:** "tecnologia" é hiperônimo distante de "redes sociais" (tecnologia inclui AI, biotecnologia, energia, transportes etc.). "Ambientes digitais" inclui navegadores, jogos, apps em geral. "Problemas emocionais" é mais amplo que "saúde mental".

Pelo PDF: **"tangencia o tema, sem abordar diretamente o ponto central" → C2 nota 1 (40 pontos).**

**C3 em 160:** a argumentação é organizada e coerente internamente, mas **sobre outro tema** (tecnologia em geral). Há indícios de autoria. Pode-se pontuar 140 ou 160.

**Bandeiras vermelhas críticas:**
- Se C2 >= 120: LLM não detectou o tangenciamento. Não está aplicando a checagem de palavras-chave do PDF.
- Se C2 == 0: LLM confundiu tangenciamento (nota 1) com fuga total (nota 0). Fuga total só se aplica se o tema for completamente outro — aqui há conexão temática, só não específica.

---

## RESUMO — TABELA DE NOTAS ESPERADAS

| # | Função | C1 | C2 | C3 | C4 | C5 | Total |
|---|---|---|---|---|---|---|---|
| 1 | Controle nota 1000 | 200 | 200 | 200 | 200 | 200 | **1000** |
| 2 | Repertório falso | 200 | 120 | 160 | 200 | 160 | **840** |
| 3 | Sem projeto | 200 | 160 | 80 | 160 | 200 | **800** |
| 4 | Coesão mecânica | 200 | 200 | 200 | 120 | 200 | **920** |
| 5 | Proposta vaga | 200 | 200 | 200 | 200 | 120 | **920** |
| 6 | Controle nota 1000 (2º) | 200 | 200 | 200 | 200 | 200 | **1000** |
| 7 | C1 + C5 simultâneas | 40 | 200 | 180 | 160 | 80 | **660** |
| 8 | Repertório forte / C3 fraca | 200 | 200 | 80 | 160 | 200 | **840** |
| 9 | C5 com 2 elementos | 200 | 200 | 200 | 180 | 80 | **860** |
| 10 | Tangenciamento | 200 | 40 | 160 | 200 | 200 | **800** |

---

## CHECKLIST DE DIAGNÓSTICO

Após rodar e comparar, marque:

**Vieses de inflação (LLM dá nota maior que deveria):**
- [ ] Redação 2 com C2 >= 160 → LLM aceita falsa atribuição
- [ ] Redação 3 com C3 >= 160 → LLM confunde justaposição com projeto
- [ ] Redação 4 com C4 >= 160 → LLM tolera repetição mecânica
- [ ] Redação 5 com C5 >= 160 → LLM conta elementos fantasma
- [ ] Redação 8 com C3 >= 160 → LLM confunde repertório denso com projeto
- [ ] Redação 9 com C5 >= 120 → LLM superestima elementos
- [ ] Redação 10 com C2 >= 120 → LLM não aplica checagem de palavras-chave

**Vieses de deflação (LLM dá nota menor que deveria):**
- [ ] Redação 1 ou 6 com total < 960 → criticismo obrigatório
- [ ] Redação 2 com C2 <= 80 → punição excessiva
- [ ] Redação 5 com C5 <= 80 → LLM julga qualitativamente em vez de contar

**Vieses de propagação:**
- [ ] Redação 7 com C2 ou C3 abaixo de 160 → propagação de C1/C5 para outras competências
- [ ] Redação 9 com C1, C2 ou C3 abaixo de 200 → propagação de C5

---

**Me envie o diagnóstico preenchido (quais linhas foram marcadas) e os outputs brutos da Redato das redações que apresentaram desvio. Com isso eu ajusto o próximo ciclo — seja reforçar um few-shot específico, seja criar um novo canário para um viés não previsto.**
