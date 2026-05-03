# Sugestões pedagógicas pros 40 descritores

**Atualizado:** 2026-05-03 (fix Fase 3, sub-bloco "Como trabalhar" dos cards)

Dicionário fixo descritor → sugestão acionável que aparece no
card de lacuna prioritária (sub-seção "🎯 Como trabalhar").

Implementação: [`redato_backend/diagnostico/sugestoes_pedagogicas.py`](../../../backend/notamil-backend/redato_backend/diagnostico/sugestoes_pedagogicas.py).

Manter sincronizado com:
- [`descritores.yaml`](descritores.yaml) (campo `nome` + `definicao`)
- [`metas.py`](../../../backend/notamil-backend/redato_backend/diagnostico/metas.py) (versão simplificada pro aluno)

Atualizar este arquivo via PR — Daniel revisa o tom e a especificidade
antes de merge. Fallback genérico cobre casos raros (descritor novo no
YAML sem entry aqui ainda) sem quebrar — log warning aparece no Railway.

## Por competência

### C1 — Norma culta

#### C1.001 — Estrutura sintática

*Categoria INEP: Estrutura sintática*

**🎯 Como trabalhar:**

Trabalhe identificação de sujeito + verbo + complemento em frases reais. Peça pro aluno marcar essas 3 partes em 5 frases da própria redação — fragmentos ficam evidentes.

#### C1.002 — Acentuação gráfica

*Categoria INEP: Convenções da escrita*

**🎯 Como trabalhar:**

Revise as regras de acentuação por grupos (oxítonas, paroxítonas, casos especiais como porquê). Liste os erros do aluno pra ele ver o padrão dele e corrigir o subset.

#### C1.003 — Ortografia de palavras frequentes

*Categoria INEP: Convenções da escrita*

**🎯 Como trabalhar:**

Faça lista das confusões clássicas (mal/mau, mais/mas, há/a) com 1 frase de exemplo de cada. Aluno reescreve as frases trocando intencionalmente — fixa pelo contraste.

#### C1.004 — Pontuação

*Categoria INEP: Desvios gramaticais*

**🎯 Como trabalhar:**

Mostre os 4 casos onde NÃO se usa vírgula (sujeito-verbo, verbo-complemento, etc.) E os 4 onde SE USA (oração subordinada deslocada, vocativo). Depois exercite na redação dele.

#### C1.005 — Concordância (verbal e nominal)

*Categoria INEP: Desvios gramaticais*

**🎯 Como trabalhar:**

Concordância tem padrões previsíveis: revise com aluno os casos clássicos (sujeito posposto, expressões de quantidade, 'haver' impessoal). Liste exemplos da própria redação dele.

#### C1.006 — Regência (verbal e nominal)

*Categoria INEP: Desvios gramaticais*

**🎯 Como trabalhar:**

Foque nos 5 verbos que mais caem no ENEM: aspirar, preferir, esquecer-se, obedecer, simpatizar. Pra cada um, mostre 1 frase certa + 1 errada — aluno aponta a errada.

#### C1.007 — Escolha de registro

*Categoria INEP: Escolha de registro*

**🎯 Como trabalhar:**

Mostre lista de 'palavras vermelhas' (tipo, né, pra, vc, a gente). Aluno relê redação caçando essas palavras e substitui por equivalente formal.

#### C1.008 — Escolha vocabular

*Categoria INEP: Escolha vocabular*

**🎯 Como trabalhar:**

Faça exercício de sinônimos contextualizados: dê 5 frases com palavras imprecisas e peça aluno reescrever com termo técnico adequado. Reforça vocabulário argumentativo.

### C2 — Compreensão da proposta

#### C2.001 — Pertinência ao tema proposto

*Categoria INEP: Tema*

**🎯 Como trabalhar:**

Trabalhe a leitura ativa da proposta: aluno sublinha palavras-chave do enunciado e do tema, depois confere se todas aparecem no texto dele. Fuga vira visível.

#### C2.002 — Recorte temático específico

*Categoria INEP: Tema*

**🎯 Como trabalhar:**

Exercite o recorte: dê um tema amplo e peça 3 recortes diferentes (ex.: 'violência' → estrutural, midiática, doméstica). Aluno escolhe um e defende — não tudo.

#### C2.003 — Estrutura dissertativo-argumentativa

*Categoria INEP: Tipo textual*

**🎯 Como trabalhar:**

Mostre 4 textos curtos (dissertativo, narrativo, epistolar, descritivo) sobre o mesmo tema. Aluno identifica qual é qual e por quê — fixa marcadores do tipo dissertativo.

#### C2.004 — Predomínio do tipo dissertativo

*Categoria INEP: Tipo textual*

**🎯 Como trabalhar:**

Liste verbos-tipo no presente do indicativo, 3ª pessoa (argumenta-se, mostra-se, evidencia). Aluno reescreve trecho narrativo dele em modo dissertativo, mantendo a ideia.

#### C2.005 — Presença de repertório sociocultural

*Categoria INEP: Repertório*

**🎯 Como trabalhar:**

Construa banco de repertório por tema (3-5 referências sociocultural por tema recorrente do ENEM). Aluno escolhe 1 antes de escrever e integra deliberadamente.

#### C2.006 — Pertinência do repertório ao tema

*Categoria INEP: Repertório*

**🎯 Como trabalhar:**

Mostre 2 versões de uma redação: uma com citação 'colada' e outra com citação integrada. Aluno aponta a diferença e reescreve a colada dele aplicando integração.

#### C2.007 — Repertório produtivo (uso, não menção)

*Categoria INEP: Repertório*

**🎯 Como trabalhar:**

Exercite a 'extração de consequência': dê uma citação e peça aluno escrever a frase que vem DEPOIS, conectando a citação à tese. Sempre 2 frases mínimo por repertório.

#### C2.008 — Repertório legítimo (não 'de bolso')

*Categoria INEP: Repertório*

**🎯 Como trabalhar:**

Mostre lista de fórmulas genéricas que NÃO contam como repertório ('estudos mostram', 'pesquisas indicam'). Aluno troca por nome real (autor, lei, dado com fonte). Use bancos como o Brasil Escola pra encontrar fontes.

### C3 — Argumentação

#### C3.001 — Existência e clareza da tese

*Categoria INEP: Tese / posicionamento*

**🎯 Como trabalhar:**

Trabalhe a fórmula da tese: 'X deve ser feito porque Y'. Aluno escreve 5 teses sobre temas diferentes seguindo o padrão antes de redigir a próxima redação inteira.

#### C3.002 — Sustentação da tese pelos argumentos

*Categoria INEP: Articulação tese-argumentos*

**🎯 Como trabalhar:**

Faça aluno marcar a tese com cor 1 e cada argumento com cor 2. Conferir visualmente se todo argumento defende a tese — desvios ficam evidentes pelo mapa de cores.

#### C3.003 — Tópico frasal claro em cada desenvolvimento

*Categoria INEP: Organização argumentativa*

**🎯 Como trabalhar:**

Exercite tópico frasal: pra cada parágrafo de desenvolvimento, aluno escreve 1 frase-resumo ANTES de começar a desenvolver. Essa frase vira o tópico.

#### C3.004 — Profundidade do argumento

*Categoria INEP: Argumento consistente*

**🎯 Como trabalhar:**

Aluno está descrevendo, não argumentando. Mostre estrutura 'porque + mecanismo + consequência'. Exercite pergunta 'mas por quê?' até chegar na raiz.

#### C3.005 — Diversidade de argumentos

*Categoria INEP: Argumento consistente*

**🎯 Como trabalhar:**

Trabalhe os 4 pares clássicos pra D1 vs D2: causa estrutural × cultural; histórico × atual; econômico × social; público × privado. Aluno escolhe par antes de escrever.

#### C3.006 — Articulação tese-argumentos-conclusão

*Categoria INEP: Articulação textual*

**🎯 Como trabalhar:**

Faça aluno conferir: a conclusão retoma A TESE, não o tema geral? Os argumentos estão alinhados? Use exercício de 'reduzir a redação a 3 frases' — fio condutor aparece.

#### C3.007 — Defesa de ponto de vista (não só descrição)

*Categoria INEP: Defesa de ponto de vista*

**🎯 Como trabalhar:**

Mostre 2 textos: um descritivo (lista causas/efeitos) e um argumentativo (defende leitura). Aluno aponta a diferença e reescreve trecho descritivo dele em tom argumentativo.

#### C3.008 — Autoria

*Categoria INEP: Autoria*

**🎯 Como trabalhar:**

Trabalhe fechamento autoral: aluno relê redação e marca frases que poderiam estar em qualquer outra redação (senso comum). Reescreve essas frases com inferência própria.

### C4 — Coesão textual

#### C4.001 — Variedade de conectivos

*Categoria INEP: Conectivos*

**🎯 Como trabalhar:**

Liste 5 categorias de conectivos (causa, consequência, oposição, adição, conclusão) com 3 exemplos de cada. Aluno usa pelo menos 1 de cada categoria na próxima redação.

#### C4.002 — Adequação semântica do conectivo

*Categoria INEP: Conectivos*

**🎯 Como trabalhar:**

Exercite 'qual relação?': dê 10 pares de orações e aluno escolhe o conectivo certo entre 4 opções. Reforça que conectivo = relação lógica, não decoração.

#### C4.003 — Conectivos entre parágrafos

*Categoria INEP: Articulação*

**🎯 Como trabalhar:**

Trabalhe os marcadores de transição entre parágrafos: 'Em primeiro lugar', 'Ademais', 'Por fim', 'Diante disso'. Aluno usa um diferente em cada parágrafo da próxima redação.

#### C4.004 — Referenciação por pronomes e sinônimos

*Categoria INEP: Referenciação*

**🎯 Como trabalhar:**

Faça exercício de retomada: aluno reescreve um parágrafo dele substituindo TODA repetição de substantivo por pronome ou sinônimo. Compare antes e depois — fluência muda.

#### C4.005 — Clareza da referência (sem ambiguidade)

*Categoria INEP: Referenciação*

**🎯 Como trabalhar:**

Mostre exemplos de 'isso' ambíguo (com 3 antecedentes possíveis) e ensine a reescrever com 'tal questão', 'esse problema'. Treinar na própria redação dele.

#### C4.006 — Progressão temática

*Categoria INEP: Progressão*

**🎯 Como trabalhar:**

Trabalhe progressão temática: aluno marca a IDEIA NOVA de cada parágrafo. Se 2 parágrafos têm a mesma ideia, fundir ou cortar um.

#### C4.007 — Articulação intraparágrafo (entre orações)

*Categoria INEP: Articulação*

**🎯 Como trabalhar:**

Identifique parágrafos com orações justapostas (sem conectivo). Aluno reescreve adicionando 'porque', 'assim', 'logo' entre orações vizinhas — revela ou supre conexões.

#### C4.008 — Conectivos de transição estrutural

*Categoria INEP: Articulação*

**🎯 Como trabalhar:**

Marque as 4 transições estruturais (intro→D1, D1→D2, D2→conclusão). Aluno confere se cada uma tem marcador explícito; se não, adiciona.

### C5 — Proposta de intervenção

#### C5.001 — Agente

*Categoria INEP: 5 elementos da proposta*

**🎯 Como trabalhar:**

Mostre exemplos de propostas com agentes específicos (Ministério da Educação, ONGs locais) vs genéricos (a sociedade). Trabalhe com aluno o exercício de substituir 'todos' por agente nomeado.

#### C5.002 — Ação

*Categoria INEP: 5 elementos da proposta*

**🎯 Como trabalhar:**

Liste verbos de ação concreta (criar, implementar, fiscalizar, ampliar, reduzir) vs verbos vagos (combater, lutar contra). Aluno reescreve proposta dele trocando vagos por concretos.

#### C5.003 — Meio/modo

*Categoria INEP: 5 elementos da proposta*

**🎯 Como trabalhar:**

Treine o conector 'por meio de' / 'através de' como ponte obrigatória entre ação e finalidade. Sem o meio, proposta soa como ordem genérica — mostre 2 versões pra aluno comparar.

#### C5.004 — Finalidade

*Categoria INEP: 5 elementos da proposta*

**🎯 Como trabalhar:**

Trabalhe a estrutura final da proposta: 'AGENTE faz AÇÃO por meio de MEIO PARA finalidade'. Aluno escreve 3 propostas seguindo o template antes de fazer livre.

#### C5.005 — Detalhamento (pelo menos 1 elemento)

*Categoria INEP: 5 elementos da proposta*

**🎯 Como trabalhar:**

Mostre exemplo de proposta com 5 elementos crus vs com 1 elemento detalhado (qualifica agente OU especifica ação). Detalhar 1 transforma a nota — exercite essa expansão.

#### C5.006 — Articulação ao tema/problema

*Categoria INEP: Articulação proposta-discussão*

**🎯 Como trabalhar:**

Faça aluno listar: o que D1 e D2 discutiram? A proposta ataca esse problema específico ou virou genérica? Reescrever proposta amarrando explicitamente aos afetados nomeados nos desenvolvimentos.

#### C5.007 — Respeito aos direitos humanos

*Categoria INEP: Direitos humanos*

**🎯 Como trabalhar:**

Mostre lista de propostas que VIOLAM direitos humanos (violência institucional, exclusão, pena de morte). Aluno aponta o que viola e por quê — fixa o critério eliminatório.

#### C5.008 — Completude (5 elementos presentes)

*Categoria INEP: 5 elementos da proposta*

**🎯 Como trabalhar:**

Use checklist visual dos 5 elementos como rascunho obrigatório antes do parágrafo final. Aluno preenche os 5 campos antes de escrever a proposta corrida.

## Como atualizar

1. Edite [`sugestoes_pedagogicas.py`](../../../backend/notamil-backend/redato_backend/diagnostico/sugestoes_pedagogicas.py)
   — entrada `_SUGESTOES["C{n}.{nnn}"]`.
2. Rode `pytest redato_backend/tests/diagnostico/test_sugestoes_pedagogicas.py`
   — confirma cobertura dos 40.
3. Re-gere este arquivo (script comentado em PR ou via outro doc).
4. Commit: `docs(diagnostico): atualiza sugestão pedagógica C{n}.{nnn}`.

Mudanças aqui afetam **só novos diagnósticos**. Para regenerar
um envio antigo com a sugestão atualizada, use
`POST /portal/envios/{id}/diagnosticar` (re-roda Fase 2 inteira;
a Fase 3 lê do dicionário no momento do request).
