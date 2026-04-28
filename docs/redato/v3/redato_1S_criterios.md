# Redato no Livro 1S — Critérios de Avaliação por Missão

**Escopo:** as 5 missões marcadas com `mf-header-redato` no `LIVRO_1S_PROF` + Chat Redator (tutoria sob demanda).
**Não cobre:** demais atividades do livro, fichas de auto-avaliação, exercícios não marcados.

**Referências canônicas:**
- **Cartilha do Participante INEP 2025** — referência oficial para todas as 5 competências ENEM.
- **Cunha & Cintra** (Nova Gramática do Português Contemporâneo) — gramática primária, apoio em decisões normativas.
- **Bechara** (Moderna Gramática Portuguesa) — árbitro em casos disputados.
- **Material do livro REJ 1S** — terminologia e abordagem pedagógica do programa.

**Princípio de mapeamento REJ → ENEM:**
Cada Modo Foco traduz um recorte específico da competência ENEM. A rubrica REJ não substitui a Cartilha — é uma **lente de calibração** sobre o que a oficina trabalhou. O LLM avalia usando a Cartilha como base e a rubrica REJ como peso adicional sobre os aspectos enfatizados.

---

## Missão 1 — OF10 · Modo Foco C3

**Código:** `RJ1·OF10·MF·Foco C3`
**Competência avaliada:** apenas C3 (escala 0-200).
**Outras competências:** registradas para diagnóstico futuro, mas não pontuadas.

### Enunciado da missão
Aluno escreve **um parágrafo argumentativo** com 3 elementos: conclusão (tese) + premissa (por quê) + exemplo (evidência). Primeiro com andaime visível, depois reescrito em prosa contínua.

### Rubrica REJ (do livro)

| Critério   | Insuficiente            | Adequado              | Excelente                   |
|------------|-------------------------|-----------------------|-----------------------------|
| Conclusão  | Ausente ou vaga         | Clara e específica    | Defendível e precisa        |
| Premissa   | Ausente                 | Presente, genérica    | Dado ou razão verificável   |
| Exemplo    | Ausente                 | Presente              | Concreto e relevante        |
| Fluência   | Copiou o andaime        | Reescreveu parcialmente| Flui sem as marcações      |

### Mapeamento REJ → C3 ENEM

| Critério REJ | Cartilha INEP (C3) | Peso |
|--------------|---------------------|------|
| Conclusão    | "defesa do ponto de vista" — descritor 200 exige tese clara | alto |
| Premissa     | "informações organizadas em defesa do ponto de vista" — substância argumentativa | alto |
| Exemplo      | "informações, fatos e opiniões relacionados ao tema" | médio |
| Fluência     | "configurando autoria" — descritor 200 exige texto que não dependa de andaime | alto (na faixa superior) |

### Tradução de nota REJ (0-12) para C3 ENEM (0-200)

A rubrica REJ pontua 4 critérios × 3 níveis (0-3 cada) = 0-12.
A escala C3 ENEM usa 6 níveis discretos: 0, 40, 80, 120, 160, 200.

**Tabela de tradução proposta:**

| Total REJ (0-12) | Faixa qualitativa | C3 ENEM |
|------------------|--------------------|---------|
| 0-1              | Sem produção válida | 0     |
| 2-3              | Apenas tentativa, elementos majoritariamente ausentes | 40 |
| 4-5              | Estrutura mínima, mas fragmentada | 80 |
| 6-7              | Estrutura presente, mas previsível ou genérica | 120 |
| 8-9              | Estrutura completa com adequação | 160 |
| 10-12            | Estrutura completa com autoria | 200 |

**Nota:** essa tradução não é mecânica — o LLM deve **aplicar julgamento qualitativo** sobre qual faixa C3 melhor descreve o desempenho integrado, usando a tabela como referência.

### Casos críticos (atenção do LLM)

1. **Aluno escreve só o andaime sem reescrever.** Mesmo se cada peça estiver excelente, a Fluência cai pra "copiou andaime" → cap em 120 (porque falta autoria/fluência argumentativa).

2. **Aluno escreve fluido mas sem distinguir conclusão/premissa/exemplo.** Pode ter texto bonito mas sem estrutura argumentativa. Avaliar como C3 baixo se as três peças não forem identificáveis.

3. **Aluno usa "exemplo" que é repetição da premissa.** Premissa: "trabalhar em equipe é importante". Exemplo: "porque sozinho ninguém faz nada". Não é exemplo, é redundância. Critério Exemplo cai pra Insuficiente.

4. **Tese genérica disfarçada ("a educação é fundamental"):** Conclusão = Adequado no máximo. Cartilha rebaixa "argumentação previsível" pra 120, mesmo com estrutura completa.

### Detectores específicos a aplicar

- `andaime_copiado`: se as palavras "Conclusão:", "Premissa:", "Exemplo:" aparecem no texto reescrito → flag positiva.
- `tese_generica`: se a conclusão é frase clichê genérica aplicável a qualquer tema → flag positiva.
- `exemplo_redundante`: se o exemplo paráfraseia a premissa → flag positiva.

### Output esperado da Redato (Modo Foco C3)

```json
{
  "modo": "foco_c3",
  "missao_id": "RJ1_OF10_MF",
  "rubrica_rej": {
    "conclusao": "",
    "premissa": "",
    "exemplo": "",
    "fluencia": ""
  },
  "nota_rej_total": ,
  "nota_c3_enem": ,
  "flags": {
    "andaime_copiado": ,
    "tese_generica": ,
    "exemplo_redundante": 
  },
  "feedback_aluno": {
    "acertos": [],
    "ajustes": []
  },
  "feedback_professor": {
    "padrao_falha": "",
    "transferencia_c1": "",
    "audit_completo": ""
  }
}
```

---

## Missão 2 — OF11 · Modo Foco C4

**Código:** `RJ1·OF11·MF·Foco C4`
**Competência avaliada:** apenas C4 (escala 0-200).

### Enunciado da missão
Aluno escreve **um parágrafo argumentativo** sobre cenário "entrevista de emprego", com 4 peças (conclusão + premissa pragmática + premissa principiológica + exemplo) ligadas por conectivos. Inclui exercício de cadeia lógica (palavras-chave que conectam premissa a conclusão).

### Critério REJ implícito (extraído do material)

A oficina não tem rubrica de 4×3 explícita como OF10/OF12. Os critérios estão dispersos no checklist:

- **Estrutura** (4 peças presentes): conclusão + premissa pragmática + premissa principiológica + exemplo
- **Conectivos** (variedade e adequação): pelo menos 3 conectivos diferentes
- **Cadeia lógica** (sem saltos): elo explícito entre cada par de ideias
- **Palavra do Dia** (uso correto): premissa, mitigar ou exacerbar usadas com sentido adequado

### Rubrica derivada para C4 (proposta)

| Critério            | Insuficiente              | Adequado                  | Excelente                       |
|---------------------|---------------------------|---------------------------|----------------------------------|
| Estrutura           | <3 peças identificáveis   | 4 peças presentes         | 4 peças com encadeamento claro   |
| Conectivos          | Repetição (3× "além disso")| 3+ conectivos variados    | Variedade + relação lógica precisa|
| Cadeia lógica       | Salto entre premissa e conclusão | Cadeia explícita      | Cadeia com elos verificáveis     |
| Palavra do Dia      | Ausente ou uso errado     | Uso correto              | Uso preciso com efeito argumentativo|

### Mapeamento REJ → C4 ENEM

A Cartilha INEP define C4 em três níveis:
- **Estruturação de parágrafos:** articulação explícita entre peças do parágrafo.
- **Estruturação de períodos:** períodos complexos sem truncamento.
- **Referenciação:** retomadas adequadas por pronomes, sinônimos, expressões resumitivas.

| Critério REJ | Nível C4 ENEM |
|--------------|---------------|
| Estrutura    | Estruturação de parágrafos |
| Conectivos   | Articulação entre peças (eixo central de C4) |
| Cadeia lógica| Estruturação de períodos + adequação semântica do conectivo |
| Palavra do Dia | Repertório lexical (apoia C4 indiretamente, principal em C1) |

**Critério INEP central a respeitar (Cartilha p.33):**
> "Boa coesão não depende da mera presença de conectivos no texto, muito menos de serem utilizados em grande quantidade — é preciso que esses recursos estabeleçam relações lógicas adequadas."

**Implicação:** o LLM **não conta conectivos**. Avalia adequação semântica de cada um. Conectivo errado é mais grave que ausente.

### Tradução de nota REJ (0-12) para C4 ENEM (0-200)

| Total REJ | Faixa qualitativa | C4 ENEM |
|-----------|--------------------|---------|
| 0-1       | Sem articulação     | 0       |
| 2-3       | Articulação precária | 40     |
| 4-5       | Articulação insuficiente, conectivos repetidos ou inadequados | 80 |
| 6-7       | Articulação mediana com inadequações pontuais | 120 |
| 8-9       | Articulação boa, repertório diversificado | 160 |
| 10-12     | Articulação excelente, repertório variado e preciso | 200 |

### Casos críticos

1. **Conectivo com relação lógica errada** (ex.: "portanto" introduzindo causa). Mais grave que ausência. Critério Conectivos cai pra Insuficiente mesmo se houver variedade.

2. **Conectivos formalmente variados mas sem função clara** ("ademais", "outrossim", "destarte" amontoados). Disparador para "argumentação previsível" da Cartilha — cap em 120.

3. **Cadeia lógica com salto não declarado** (premissa "sou organizado" → conclusão "sou ideal" sem o elo "organização gera valor pra empresa"). Critério Cadeia lógica = Insuficiente.

4. **Palavra do Dia usada como sinônimo errado** ("mitigar" como "resolver"). Marca em C1 (escolha vocabular) também, registrar como flag.

### Detectores específicos

- `conectivo_relacao_errada`: pelo menos 1 conectivo com função lógica errada → flag positiva.
- `conectivo_repetido`: mesmo conectivo 3+ vezes → flag positiva.
- `salto_logico`: cadeia tem elos faltantes entre premissa e conclusão → flag positiva.
- `palavra_dia_uso_errado`: premissa/mitigar/exacerbar com sentido inadequado → flag positiva.

### Output esperado: mesmo formato da Missão 1, com `modo: "foco_c4"`.

---

## Missão 3 — OF12 · Modo Foco C5

**Código:** `RJ1·OF12·MF·Foco C5`
**Competência avaliada:** apenas C5 (escala 0-200).

### ⚠️ ATENÇÃO PEDAGÓGICA — Ponto de risco da rubrica

OF12 trabalha "5 elementos da C5" (AGENTE, AÇÃO, MEIO, FINALIDADE, DETALHAMENTO). **Esta é exatamente a estrutura que, mal interpretada, gerou o viés mecânico da v2 da Redato em produção** (corretora-parceira ensinou "5 elementos = 200, 4 = 160, 3 = 120, etc." — contagem aritmética que não está na Cartilha).

**O livro REJ usa os 5 elementos corretamente como ferramenta pedagógica.** O aluno os usa para *construir* uma boa proposta. Mas a Redato **não pode** contar os 5 elementos como régua mecânica.

### Critério INEP correto (Cartilha 2025, pp.33-37)

Descritores oficiais holísticos:

- **200** — Proposta detalhada, relacionada ao tema **e articulada à discussão** desenvolvida no texto.
- **160** — Bem elaborada, relacionada ao tema **e articulada**.
- **120** — Mediana, relacionada ao tema e articulada.
- **80** — Insuficiente OU **não articulada à discussão**.
- **40** — Vaga, precária, OU relacionada apenas ao assunto.
- **0** — Sem proposta OU desrespeito aos direitos humanos.

**Os 4 atributos canônicos da banca INEP (extraídos de 38 comentários oficiais):** concreta + detalhada + articulada à discussão + respeita direitos humanos.

### Rubrica REJ (do livro)

| Critério         | Insuficiente              | Adequado                | Excelente                       |
|------------------|---------------------------|--------------------------|----------------------------------|
| Agente           | Genérico ("o governo")    | Institucional ("MEC")    | Específico + parceria           |
| Ação + Verbo     | Verbo fraco ("fazer")     | Verbo forte              | Verbo forte + Palavra do Dia    |
| Meio             | Ausente                   | Presente, genérico       | Específico e viável             |
| Finalidade       | Ausente                   | Presente, vaga           | Clara e mensurável              |
| Detalhamento     | Ausente                   | Público OU região        | Público + região + meta         |
| Direitos humanos | Viola                     | Não viola                | Respeita e explicita            |

### Como traduzir REJ → C5 ENEM SEM cair no viés mecânico

**Regra primária — articulação à discussão.** A pergunta-chave que o LLM deve responder antes de qualquer contagem: **"a proposta responde aos problemas que o texto discutiu, ou é uma solução genérica colada no fim?"**

- Se a proposta é desarticulada da discussão (mesmo com 5 elementos formais perfeitos) → **cap em 80**.
- Se a proposta é apenas constatatória ("é preciso que algo seja feito") → cap em 40.
- Se a proposta é apenas ao assunto (trata o assunto amplo, não o recorte específico) → cap em 40.

**Regra secundária — qualidade integrada.** Aplicada **depois** de confirmada a articulação:

| Faixa REJ                                  | Articulação à discussão | C5 ENEM |
|--------------------------------------------|--------------------------|---------|
| Maioria Insuficiente                       | Vaga ou ausente         | 40      |
| Mistura de Insuficiente e Adequado          | Presente mas frágil     | 80      |
| Maioria Adequado, alguns Excelente          | Clara                   | 120     |
| Maioria Excelente, todos os 5 elementos     | Clara e bem desenvolvida | 160     |
| Todos Excelente, articulação explícita à discussão | Articulação tematizada | 200     |

**O número de elementos presentes não basta.** Proposta com 5 elementos formais mas desarticulada da discussão = 80 (descritor literal Cartilha: "não articulada"). Proposta com 4 elementos bem articulados, com detalhamento substancial = pode ser 200.

### Casos críticos

1. **Proposta vaga com agente nomeado e verbo de ação** ("Ministério atua, Congresso age, autoridades dão atenção"). Pela contagem da v2 antiga: 80 (2 elementos). Pelo critério INEP correto: **40** ("vaga, precária, ou apenas ao assunto"). **Não cair no erro da v2.**

2. **Proposta detalhadíssima que ignora o problema discutido.** Aluno escreveu redação sobre evasão escolar e propõe "investimento em segurança pública". Mesmo com 5 elementos perfeitos: **80** (não articulada).

3. **"Detalhamento" preenchido com clichê** ("para garantir um futuro melhor"). Não conta como detalhamento — é finalidade vaga. Critério Detalhamento = Insuficiente.

4. **Proposta que viola direitos humanos** ("desabrigados devem ser removidos do centro"): **C5 = 0**, independente do resto.

### Detectores específicos

- `proposta_vaga_constatatoria`: proposta limita-se a constatar problema sem indicar solução concreta → flag positiva → cap 40.
- `proposta_desarticulada`: solução não responde aos problemas específicos discutidos → flag positiva → cap 80.
- `agente_generico`: "o governo", "a sociedade", "as pessoas" sem especificação → critério Agente = Insuficiente.
- `verbo_fraco`: "fazer", "ter", "ser" como verbo principal da ação → critério Ação = Insuficiente.
- `desrespeito_direitos_humanos`: violação detectada → C5 = 0.

### Output esperado: mesmo formato da Missão 1, com `modo: "foco_c5"`.

---

## Missão 4 — OF13 · Modo Completo

**Código:** `RJ1·OF13·MF·Correção 5 comp.`
**Competência avaliada:** todas as 5 competências ENEM (escala 0-200 cada → total 0-1000).

### Enunciado da missão
Aluno escreve **um parágrafo argumentativo completo** (6-9 linhas) com Tópico Frasal + Argumento + Repertório + Coesão. Primeira vez no ano que recebe nota nas 5 competências juntas.

### Particularidade desta missão
**Não é redação completa**, é um parágrafo. A Redato avalia 5 competências ENEM aplicadas a um parágrafo único.

Isso exige adaptação:
- C1 (norma culta): aplica integralmente.
- C2 (compreensão do tema, dissertativo-argumentativo): aplica, mas avaliação do "tipo dissertativo-argumentativo" se restringe ao parágrafo (tem tese + desenvolvimento + fechamento internamente).
- C3 (organização): aplica, com escala adaptada — projeto de texto **dentro do parágrafo**.
- C4 (coesão): aplica integralmente.
- C5 (proposta): **não se aplica** — parágrafo argumentativo ≠ redação dissertativa-argumentativa com proposta. **Solução:** Redato Modo Completo OF13 reporta apenas C1+C2+C3+C4 (escala 0-800), com C5 marcado como `não_aplicável`.

### Rubrica REJ (do livro)

| Critério       | 0 (ausente)                 | 1                            | 2                                   | 3                                       |
|----------------|------------------------------|-------------------------------|--------------------------------------|------------------------------------------|
| Tópico Frasal  | Ausente ou pergunta          | Presente mas vago             | Assertiva clara mas genérica         | Assertiva específica com recorte temático |
| Argumento      | Ausente                      | Frase solta sem desenvolvimento | Análise presente mas superficial    | Mecanismo causal claro                   |
| Repertório     | Ausente                      | Menção vaga                  | Identificável mas pouco integrado   | Produtivo, comprova o argumento          |
| Coesão         | Frases soltas                | Conectivos repetidos         | Conectivos variados                  | Fluxo natural com progressão temática    |

### Mapeamento REJ → competências ENEM

| Critério REJ      | Competência ENEM principal | Peso |
|-------------------|----------------------------|------|
| Tópico Frasal     | C2 (proposição) + C3 (defesa do PDV) | alto em ambas |
| Argumento         | C3 (desenvolvimento + interpretação) | alto |
| Repertório        | C2 (informações e conhecimentos)     | alto |
| Coesão            | C4 (integral)                        | alto |

**C1 não está coberta pela rubrica REJ** — avaliada pela Cartilha INEP padrão (norma culta + estrutura sintática + escolha vocabular + registro), com referência às gramáticas Cunha & Cintra e Bechara.

### Tradução de nota

Cada competência avaliada em escala ENEM 0-200 independentemente, usando:
- **C1:** Cartilha INEP integralmente (excepcionalidade + reincidência + impacto sobre compreensão).
- **C2:** rubrica REJ (Tópico + Repertório) + Cartilha INEP. Argumentação previsível → cap 120.
- **C3:** rubrica REJ (Argumento) + Cartilha INEP. Limitação aos motivadores → cap 120.
- **C4:** rubrica REJ (Coesão) + Cartilha INEP integralmente.
- **C5:** `não_aplicável` — parágrafo não tem proposta de intervenção.

**Nota total:** soma de C1+C2+C3+C4 (escala 0-800), apresentada também como média (0-200) para comparação com Modos Foco anteriores.

### Casos críticos

1. **Parágrafo é uma redação dissertativa em miniatura mas sem proposta clara.** É o que se espera — não rebaixar por ausência de proposta nesta missão. C5 = `não_aplicável`.

2. **Tópico frasal é pergunta** ("Por que a educação é importante?"). Cartilha INEP rebaixa C2 — não é proposição assertiva. Critério Tópico Frasal = 0.

3. **Repertório legítimo mas desarticulado** ("Como dizia Aristóteles, o homem é um animal político. A educação pública é precária"). Repertório de bolso → C2 cap 120. Critério Repertório = 1 ou 2.

4. **Coesão excelente em parágrafo sem progressão temática real.** Conectivos perfeitos, mas o parágrafo gira em torno da mesma ideia. C4 alto, C3 baixo — possível dissociação de notas.

### Output esperado

```json
{
  "modo": "completo",
  "missao_id": "RJ1_OF13_MF",
  "rubrica_rej": {
    "topico_frasal": ,
    "argumento": ,
    "repertorio": ,
    "coesao": 
  },
  "nota_rej_total": ,
  "notas_enem": {
    "c1": ,
    "c2": ,
    "c3": ,
    "c4": ,
    "c5": "não_aplicável"
  },
  "nota_total_parcial": ,
  "flags": { ... },
  "feedback_aluno": { ... },
  "feedback_professor": { ... }
}
```

---

## Missão 5 — OF14 · Modo Completo (redação completa)

**Código:** `RJ1·OF14·MF·Correção 5 comp.`
**Competência avaliada:** todas as 5 competências ENEM (escala 0-200 cada → total 0-1000).

### Enunciado da missão
Aluno escreve **redação completa** de 3 parágrafos (introdução + desenvolvimento + conclusão com proposta), 18-22 linhas. **Primeira redação completa do ano.**

### Sistema de avaliação
**Esta é a Redato padrão.** Todo o sistema atual da Redato (Opus + flat schema + caps cirúrgicos) se aplica integralmente, com único acréscimo: **contexto da oficina** no system prompt.

### Adaptações específicas pra OF14

1. **Vocabulário REJ no feedback:** o LLM usa termos do programa que o aluno reconhece — "tópico frasal", "argumento", "repertório", "coesão" — mapeados pra terminologia INEP no relatório do professor.

2. **Calibração para "primeira redação completa do ano":** linguagem do feedback ao aluno deve reconhecer o estágio inicial. Não é avaliação certificatória, é formativa. Termos como "neste primeiro contato com a redação completa" + "para o próximo simulado" são apropriados.

3. **Contraste com Modos Foco anteriores:** o app deve mostrar "evolução de C3 (desde OF10), C4 (desde OF11), C5 (desde OF12)". O LLM produz o audit pleno; o app monta a comparação com runs anteriores.

### Rubrica REJ (do livro)

| Critério                                | 0   | 1   | 2   | 3   |
|-----------------------------------------|-----|-----|-----|-----|
| Introdução (abertura + tese)            |     |     |     |     |
| Desenvolvimento (tópico + argumento + repertório) | | | | |
| Conclusão (retomada + proposta)         |     |     |     |     |
| Coesão (conectivos entre parágrafos)    |     |     |     |     |

A rubrica REJ aqui mapeia **estrutura macro da redação**. Já a avaliação por competência ENEM é da Cartilha INEP.

### Mapeamento REJ → ENEM

| Critério REJ                  | Competência ENEM principal     |
|-------------------------------|--------------------------------|
| Introdução                    | C2 (proposição + tema) + C3 (tese) |
| Desenvolvimento               | C2 (repertório) + C3 (organização) |
| Conclusão                     | C5 (proposta) + C3 (fechamento)|
| Coesão entre parágrafos       | C4 (estruturação de parágrafos)|

**C1 e detalhamento de C2/C3/C4/C5 internos** são avaliados pela Cartilha INEP padrão.

### Saída

Mesmo formato da Redato em produção (5 competências, nota 0-1000, audit em prosa + JSON estruturado), com adicional `vocabulario_rej: true` para sinalizar que o feedback usa terminologia do programa.

---

## Chat Redator — escopo separado

**Não é avaliação.** É tutoria sob demanda.

### Onde o livro ativa o Chat Redator

Marcações `selo-redato chat` aparecem em:
- Painel introdutório das três camadas (descrição inicial)
- Pontes em oficinas: "abra o Chat Redator e peça um exemplo novo"
- Fim de OF14: "abre o Chat Redator para você melhorar o texto"

### Funcionalidades pedidas (do livro)

1. Pedir exemplo de uso de uma classe gramatical em contexto novo (Ponte OF02).
2. Pedir exemplos de conectivos em diferentes contextos (Ponte OF11).
3. Analisar concordância/regência em frase específica do aluno (Ponte OF11).
4. Tirar dúvida sobre conceito da oficina.
5. Ajudar a melhorar o texto após receber correção da Redato (OF14).

### Característica central
**Chat Redator não corrige redação. Não dá nota.** Responde dúvida, dá exemplo, explica conceito. Sempre **contextualizado pela oficina onde o aluno está**.

### Implementação técnica (referência)

Sistema separado da Redato Modo Foco/Completo. Chat conversacional com:
- **Contexto base:** Cartilha INEP + gramáticas (Cunha & Cintra, Bechara) + conteúdo da oficina ativa.
- **Memória curta:** últimas 5-10 mensagens do aluno na sessão.
- **Disclaimer:** "Não substituo o professor. Em dúvidas pedagógicas mais profundas, consulte seu professor."

**Trabalho conceitual de Chat Redator:** **separado, depois das 5 missões consolidadas.** Não desenhar agora.

---

## Resumo executivo

| Missão | Oficina | Modo | Competência(s) | Nota | Schema |
|--------|---------|------|----------------|------|--------|
| 1 | OF10 | Foco | C3 | 0-200 | foco |
| 2 | OF11 | Foco | C4 | 0-200 | foco |
| 3 | OF12 | Foco | C5 | 0-200 | foco |
| 4 | OF13 | Completo (parcial) | C1, C2, C3, C4 | 0-800 | completo_parcial |
| 5 | OF14 | Completo (integral) | C1-C5 | 0-1000 | completo |
| Chat | qualquer | Tutoria | n/a | n/a | chat |

### Princípios transversais

1. **Cartilha INEP é base canônica.** Sempre. Rubrica REJ é peso adicional, não substituição.
2. **Articulação > contagem.** Em todas as competências, especialmente C5.
3. **Vocabulário REJ no feedback ao aluno**, terminologia INEP no relatório do professor.
4. **Excelência admite imperfeição pontual.** Descritor 200 da Cartilha aceita "excepcionalidade e ausência de reincidência".
5. **Detectores de rebaixamento explícitos** para os casos críticos identificados em cada missão.
