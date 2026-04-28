PROMPT_ANALYSIS_COMPETENCY_1 = """
    <knowledge foundation>
    <analysis rules>
    Aqui estão algumas sessões detalhadas:

    <ortography>
    1. Ortografia:
        Analise o texto linha por linha quanto à ortografia, identificando APENAS ERROS REAIS em:
            1. Palavras escritas incorretamente
            2. Problemas de acentuação
            3. Uso incorreto de maiúsculas/minúsculas
            4. Grafia de estrangeirismos
            5. Abreviações inadequadas

        Importante: NÃO inclua sugestões de melhoria ou preferências estilísticas.
        Você deverá incluir apenas desvios claros da norma culta.

        Exemplos:
        errado: "a verificar às informações" -> correção: "a verificar as informações"
    </ortography>

    <punctuation>
    2. Pontuação:
        Analise o texto linha por linha quanto à pontuação, identificando APENAS ERROS REAIS em:
            1. Uso incorreto de vírgulas em:
               - Enumerações
               - Orações coordenadas
               - Orações subordinadas
               - Apostos e vocativos
               - Adjuntos adverbiais deslocados
            2. Uso inadequado de ponto e vírgula
            3. Uso incorreto de dois pontos
            4. Problemas com pontos finais
            5. Uso inadequado de reticências
            6. Problemas com travessões e parênteses

        NÃO inclua sugestões de melhoria ou pontuação opcional.
        Inclua apenas desvios claros das regras de pontuação.
    </punctuation>

    <agreement>
    3. Concordância:
        Analise o texto linha por linha quanto à concordância, identificando APENAS ERROS REAIS em:
            1. Concordância verbal
               - Sujeito e verbo
               - Casos especiais (coletivos, expressões partitivas)
            2. Concordância nominal
               - Substantivo e adjetivo
               - Casos especiais (é necessário, é proibido)
            3. Concordância ideológica
            4. Silepse (de gênero, número e pessoa)

        NÃO inclua sugestões de melhoria ou preferências de concordância.
        Inclua apenas desvios claros das regras de concordância.
    </agreement>

    <regency>
    4. Regência:
        Analise o texto linha por linha quanto à regência, identificando APENAS ERROS REAIS em:
            1. Regência verbal
               - Uso inadequado de preposições com verbos
               - Ausência de preposição necessária
            2. Regência nominal
               - Uso inadequado de preposições com nomes
            3. Uso da crase: Verifique CUIDADOSAMENTE se há:
               - Junção de preposição 'a' com artigo definido feminino 'a'
               - Palavra feminina usada em sentido definido
               - Locuções adverbiais femininas

        IMPORTANTE: Analise cada caso considerando:
        - O contexto completo da frase
        - A função sintática das palavras
        - O sentido pretendido (definido/indefinido)
        - A regência dos verbos e nomes envolvidos

        NÃO marque como erro casos onde:
        - Não há artigo definido feminino
        - A palavra está sendo usada em sentido indefinido
        - Há apenas preposição 'a' sem artigo
    </regency>
    </analysis rules>
    </knowledge foundation>

    <task instructions>
    Agora você deverá realizar uma análise para a competência 1 (Domínio da Norma Culta) considerando apenas:
    <awaited analysis>
    -- Análise esperada (competência 1):
        Observação: Analisar apenas os erros reais que prejudicam a nota, ignorando sugestões de melhoria.

        Forneça uma análise que:
        1. Avalie o domínio geral da norma culta considerando apenas erros confirmados
        2. Destaque os tipos de erros mais frequentes e sua gravidade
        3. Analise o impacto dos erros na compreensão do texto
        4. Avalie a consistência no uso da norma culta
        5. Forneça uma visão geral da qualidade técnica do texto
    </awaited analysis>
    </task instructions>

    <context>
    Contexto para a sua análise:
    Texto da redação: {essay_text}
    Tema: {essay_theme}
    Métricas textuais:
    - Número de palavras: {word_count}
    - Número de sentenças: {sentence_count}
    - Comprimento médio das palavras: {average_word_length}
    - Diversidade lexical: {lexical_diversity}
    </context>

    <important rule>
    O número de erros citado dentro da análise deve ser exatamente o número de erros dentro da lista "errors".
    Caso não haja erros, mas haja sugestões de melhoras, insira essas sugestões em "errors" o tipo de erro deve ser "sugestão de melhoria".
    </important rule>

    <output rules>
    Retorne um JSON no seguinte formato:
    {{
      "analysis": "Texto detalhado da análise da competência",
      "errors": [
         {{
            "description": "Breve descrição do erro",
            "snippet": "Trecho exato do texto",
            "error_type": "Tipo de erro escrito em português"
            "suggestion": "Sugestão de correção"
         }}
      ]
    }}

    Se não houver erros, retorne uma lista vazia em "errors".
    </output rules>
"""  # noqa: E501

PROMPT_ANALYSIS_COMPETENCY_2 = """
    <task instructions>
    Agora você deverá realizar uma análise para a competência 2 (Compreensão do Tema). Objetivos específicos:
        1. Avaliação do domínio do tema proposto.
        2. Análise da presença das palavras principais do tema ou seus sinônimos em cada parágrafo.
        3. Avaliação da argumentação e uso de repertório sociocultural.
        4. Análise da clareza do ponto de vista adotado.
        5. Avaliação do vínculo entre o repertório e a discussão proposta.
        6. Verificação de cópia de trechos dos textos motivadores.
        7. Análise da citação de fontes do repertório utilizado.

    Objetivo geral: Mostrar compreensão do tema, utilizando ao longo do texto as palavras chaves ou sinônimos da temática central, identificar a adequação à tipologia exigida ou a presença de traços constantes de outros tipos textuais, bem como a proporção entre as partes do texto dissertativo-argumentativo, ou seja, se há partes embrionárias. A tangência é observada naqueles textos que apenas resvalam no tema. Voltada para a seleção dos argumentos.

    Faça a análise dos objetivos específicos levando em consideração o ponto de vista geral.
    </task instructions>

    <context>
    Contexto para a sua análise:
    Texto da redação: {essay_text}
    Tema: {essay_theme}
    Métricas:
    - Palavras: {word_count}
    - Sentenças: {sentence_count}
    - Palavras únicas: {unique_words}
    - Diversidade lexical: {lexical_diversity}
    </context>

    <analysis made before>
    Essas são as análises realizadas até agora (apenas para o seu raciocínio):
    {retroactive_analysis}
    </analysis made before>

    <important rule>
    O número de erros citado dentro da análise deve ser exatamente o número de erros dentro da lista "errors".
    Caso não haja erros, mas haja sugestões de melhoras, insira essas sugestões em "errors" o tipo de erro deve ser "sugestão de melhoria".
    </important rule>

    <output rules>
    Retorne um JSON no formato:
    {{
      "analysis": "Texto detalhado da análise da competência",
      "errors": [
         {{
            "description": "Breve descrição do erro",
            "snippet": "Trecho exato do texto",
            "error_type": "Tipo de erro escrito em português"
            "suggestion": "Sugestão de correção"
         }}
      ]
    }}

    Se não houver erros, retorne uma lista vazia em "errors".
    </output rules>
"""  # noqa: E501

PROMPT_ANALYSIS_COMPETENCY_3 = """
    <task instructions>
    Agora você deverá realizar uma análise. Objetivos específicos:
        1. Avaliação da progressão das ideias e seleção de argumentos.
        2. Análise da organização das informações e fatos relacionados ao tema.
        3. Comentários sobre a defesa do ponto de vista e consistência argumentativa.
        4. Avaliação da autoria e originalidade das informações apresentadas.
        5. Análise do encadeamento das ideias entre parágrafos.
        6. Verificação de repetições desnecessárias ou saltos temáticos.
        7. Avaliação da estrutura de cada parágrafo (argumento, justificativa, repertório, justificativa, frase de finalização).

    Objetivo geral: Avaliar a sequência textual, é interessante analisar a relação entre o argumento levantado, o tema principal e como o reportório comprova o ponto de vista, analisando a profundidade da justificativa do repertório utilizado.
    IMPORTANTE para se ter em mente durante a sua análise: Caso o texto seja relacionado à um desafio a ideia argumentativa tem que ser de causa e efeito. Caso o argumento seja uma solução, o foco seria uma ideia de solução vs. problema, ou seja a causalidade.
    </task instructions>

    <context>
    Faça a análise dos objetivos específicos levando em consideração o ponto de vista geral.

    Contexto para a sua análise:
    Texto: {essay_text}
    Tema: {essay_theme}
    Métricas:
    - Parágrafos: {paragraph_count}
    - Sentenças/Parágrafo: {sentences_per_paragraph}
    - Conectivos: {connectives}
    - Frases nominais: {noun_phrases}
    - Frases verbais: {verb_phrases}
    </context>

    <analysis made before>
    Essas são as análises realizadas até agora (apenas para o seu raciocínio):
    {retroactive_analysis}
    </analysis made before>

    <important rule>
    O número de erros citado dentro da análise deve ser exatamente o número de erros dentro da lista "errors".
    Caso não haja erros, mas haja sugestões de melhoras, insira essas sugestões em "errors" o tipo de erro deve ser "sugestão de melhoria".
    </important rule>

    <output rules>
    Retorne um JSON:
    {{
      "analysis": "Texto detalhado da análise da competência",
      "errors": [
         {{
            "description": "Breve descrição do erro",
            "snippet": "Trecho exato do texto",
            "error_type": "Tipo de erro escrito em português"
            "suggestion": "Sugestão de correção"
         }}
      ]
    }}

    Se não houver erros, retorne uma lista vazia em "errors".
    </output rules>
"""  # noqa: E501

PROMPT_ANALYSIS_COMPETENCY_4 = """
    <task instructions>
    Agora você deverá realizar uma análise para a competência 4 (Conhecimento dos Mecanismos Linguísticos) considerando apenas:
        1. Avaliação do uso de conectivos no início de cada período.
        2. Análise da articulação entre as partes do texto.
        3. Avaliação do repertório de recursos coesivos.
        4. Análise do uso de referenciação (pronomes, sinônimos, advérbios).
        5. Avaliação das transições entre ideias (causa/consequência, comparação, conclusão).
        6. Análise da organização de períodos complexos.
        7. Verificação da repetição de conectivos ao longo do texto.
    </task instructions>

    <context>
    Contexto para a sua análise:
    Texto: {essay_text}
    Tema: {essay_theme}
    Métricas:
    - Conectivos: {connectives}
    - Palavras/Sentença: {words_per_sentence}
    - Frases nominais: {noun_phrases}
    - Frases verbais: {verb_phrases}
    <context>

    <analysis made before>
    Essas são as análises realizadas até agora (apenas para o seu raciocínio):
    {retroactive_analysis}
    </analysis made before>

    <important rule>
    O número de erros citado dentro da análise deve ser exatamente o número de erros dentro da lista "errors".
    Caso não haja erros, mas haja sugestões de melhoras, insira essas sugestões em "errors" o tipo de erro deve ser "sugestão de melhoria".
    </important rule>

    <output rules>
    Retorne um JSON:
    {{
      "analysis": "Texto detalhado da análise da competência",
      "errors": [
         {{
            "description": "Breve descrição do erro",
            "snippet": "Trecho exato do texto",
            "error_type": "Tipo de erro escrito em português"
            "suggestion": "Sugestão de correção"
         }}
      ]
    }}

    Se não houver erros, retorne uma lista vazia em "errors".
    </output rules>
"""  # noqa: E501


PROMPT_ANALYSIS_COMPETENCY_5 = """
    <task instructions>
    Agora você deverá realizar uma análise para a competência 5 (Proposta de Intervenção) considerando apenas:
        1. Avaliação da presença dos cinco elementos obrigatórios: agente, ação, modo/meio, detalhamento e finalidade.
            1.1 Aqui não é necessário avaliar a profundidade de cada um dos cinco elementos, apenas sua presença.
            1.2 O detalhamento é opcional, não é necessário avaliar a profundidade dele, apenas sua presença.
        2. Análise do nível de detalhamento e articulação da proposta com a discussão do texto.
        3. Avaliação da viabilidade e respeito aos direitos humanos na proposta.
        4. Verificação da retomada do contexto inicial (se houver).
        5. Análise da coerência entre a proposta e o tema discutido.
        6. Se a proposta de intervenção possuir os 5 elementos, você não precisa identificar nenhum erro.
    </task instructions>

    <context>
    Contexto para a sua análise:
    Texto: {essay_text}
    Tema: {essay_theme}
    Métricas:
    - Sentenças: {sentence_count}
    - Palavras: {word_count}
    - Parágrafos: {paragraph_count}
    </context>

    <analysis made before>
    Essas são as análises que temos até agora (apenas para o seu raciocínio):
    {retroactive_analysis}
    </analysis made before>

    <important rule>
    O número de erros citado dentro da análise deve ser exatamente o número de erros dentro da lista "errors".
    Se a proposta de intervenção possuir os 5 elementos, você não precisa identificar nenhum erro.
    Caso não haja erros, mas haja sugestões de melhoras, insira essas sugestões em "errors" o tipo de erro deve ser "sugestão de melhoria".
    </important rule>

    <output rules>
    Retorne um JSON:
    {{
      "analysis": "Texto detalhado da análise da competência",
      "errors": [
         {{
            "description": "Breve descrição do erro ou elemento faltante",
            "snippet": "Trecho do texto",
            "error_type": "Tipo de erro escrito em português"
            "suggestion": "Sugestão de correção"
         }}
      ]
    }}

    Se não houver erros, retorne uma lista vazia em "errors".
    </output rules>
"""  # noqa: E501

GRADING_CRITERIA = {
    "d7d30def-7f7f-4cc4-ae92-b41228a9855e": """
        <important>
        COMPETÊNCIA 1: Domínio da Norma Culta
        </important>

        Nota 200:
        - No máximo uma falha de estrutura sintática
        - No máximo dois desvios gramaticais
        - Nenhum uso de linguagem informal/coloquial
        - No máximo um erro ortográfico
        - Coerência e coesão impecáveis
        - Sem repetição de erros

        Nota 160:
        - Até três desvios gramaticais que não comprometem a compreensão
        - Poucos erros de pontuação/acentuação
        - No máximo três erros ortográficos
        - Bom domínio geral da norma culta

        Nota 120:
        - Até cinco desvios gramaticais
        - Domínio mediano da norma culta
        - Alguns problemas de coesão pontuais
        - Erros não sistemáticos

        Nota 80:
        - Estrutura sintática deficitária
        - Erros frequentes de concordância
        - Uso ocasional de registro inadequado
        - Muitos erros de pontuação/ortografia

        Nota 40:
        - Domínio precário da norma culta
        - Diversos desvios gramaticais frequentes
        - Problemas graves de coesão
        - Registro frequentemente inadequado

        Nota 0:
        - Desconhecimento total da norma culta
        - Erros graves e sistemáticos
        - Texto incompreensível
    """,
    "a7c812b2-fefd-4757-8774-e08bcdba82cc": """
        <important>
        COMPETÊNCIA 2: Compreensão do Tema
        </important>

        Nota 200:
        - Excelente domínio do tema proposto.
        - Citação das palavras principais do tema ou sinônimos em cada parágrafo.
        - Argumentação consistente com repertório sociocultural produtivo.
        - Uso de exemplos históricos, frases, músicas, textos, autores famosos, filósofos, estudos, artigos ou publicações como repertório.
        - Excelente domínio do texto dissertativo-argumentativo, incluindo proposição, argumentação e conclusão.
        - Não copia trechos dos textos motivadores e demonstra clareza no ponto de vista adotado.
        - Estabelece vínculo de ideias entre a referência ao repertório e a discussão proposta.
        - Cita a fonte do repertório (autor, obra, data de criação, etc.).
        - Inclui pelo menos um repertório no segundo e terceiro parágrafo.

        Nota 160:
        - Bom desenvolvimento do tema com argumentação consistente, mas sem repertório sociocultural tão produtivo.
        - Completa as 3 partes do texto dissertativo-argumentativo (nenhuma delas é embrionária).
        - Bom domínio do texto dissertativo-argumentativo, com proposição, argumentação e conclusão claras, mas sem aprofundamento.
        - Utiliza informações pertinentes, mas sem extrapolar significativamente sua justificativa.

        Nota 120:
        - Abordagem completa do tema, com as 3 partes do texto dissertativo-argumentativo (podendo 1 delas ser embrionária).
        - Repertório baseado nos textos motivadores e/ou repertório não legitimado e/ou repertório legitimado, mas não pertinente ao tema.
        - Desenvolvimento do tema de forma previsível, com argumentação mediana, sem grandes inovações.
        - Domínio mediano do texto dissertativo-argumentativo, com proposição, argumentação e conclusão, mas de forma superficial.

        Nota 80:
        - Abordagem completa do tema, mas com problemas relacionados ao tipo textual e presença de muitos trechos de cópia sem aspas.
        - Domínio insuficiente do texto dissertativo-argumentativo, faltando a estrutura completa de proposição, argumentação e conclusão.
        - Não desenvolve um ponto de vista claro e não consegue conectar as ideias argumentativas adequadamente.
        - Duas partes embrionárias ou com conclusão finalizada por frase incompleta.

        Nota 40:
        - Tangencia o tema, sem abordar diretamente o ponto central proposto.
        - Domínio precário do texto dissertativo-argumentativo, com traços de outros tipos textuais.
        - Não constrói uma argumentação clara e objetiva, resultando em confusão ou desvio do gênero textual.

        Nota 0:
        - Fuga completa do tema proposto, abordando um assunto irrelevante ou não relacionado.
        - Não atende à estrutura dissertativo-argumentativa, sendo classificado como outro gênero textual.
        - Não apresenta proposição, argumentação e conclusão, ou o texto é anulado por não atender aos critérios básicos de desenvolvimento textual.
    """,  # noqa: E501
    "3334fd6a-adf0-4c43-8e83-630270c17f86": """
        <important>
        COMPETÊNCIA 3: Seleção e Organização das Informações
        </important>

        Nota 200:
        - Ideias progressivas e argumentos bem selecionados, revelando um planejamento claro do texto.
        - Apresenta informações, fatos e opiniões relacionados ao tema proposto e aos seus argumentos, de forma consistente e organizada, em defesa de um ponto de vista.
        - Demonstra autoria, com informações e argumentos originais que reforçam o ponto de vista do aluno.
        - Mantém o encadeamento das ideias, com cada parágrafo apresentando informações coerentes com o anterior, sem repetições desnecessárias ou saltos temáticos.
        - Apresenta poucas falhas, e essas falhas não prejudicam a progressão do texto.

        Nota 160:
        - Apresenta informações, fatos e opiniões relacionados ao tema, de forma organizada, com indícios de autoria em defesa de um ponto de vista.
        - Ideias claramente organizadas, mas não tão consistentes quanto o esperado para uma argumentação mais sólida.
        - Organização geral das ideias é boa, mas algumas informações e opiniões não estão bem desenvolvidas.

        Nota 120:
        - Apresenta informações, fatos e opiniões relacionados ao tema, mas limitados aos argumentos dos textos motivadores e pouco organizados, em defesa de um ponto de vista.
        - Ideias previsíveis, sem desenvolvimento profundo ou originalidade, com pouca evidência de autoria.
        - Argumentos simples, sem clara progressão de ideias, e baseado principalmente nas sugestões dos textos motivadores.

        Nota 80:
        - Apresenta informações, fatos e opiniões relacionados ao tema, mas de forma desorganizada ou contraditória, e limitados aos argumentos dos textos motivadores.
        - Ideias não estão bem conectadas, demonstrando falta de coerência e organização no desenvolvimento do texto.
        - Argumentos inconsistentes ou contraditórios, prejudicando a defesa do ponto de vista.
        - Perde linhas com informações irrelevantes, repetidas ou excessivas.

        Nota 40:
        - Apresenta informações, fatos e opiniões pouco relacionados ao tema, com incoerências, e sem defesa clara de um ponto de vista.
        - Falta de organização e ideias dispersas, sem desenvolvimento coerente.
        - Não apresenta um ponto de vista claro, e os argumentos são fracos ou desconexos.

        Nota 0:
        - Apresenta informações, fatos e opiniões não relacionados ao tema, sem coerência, e sem defesa de um ponto de vista.
        - Ideias totalmente desconexas, sem organização ou relação com o tema proposto.
        - Não desenvolve qualquer argumento relevante ou coerente, demonstrando falta de planejamento.
    """,  # noqa: E501
    "5467abb2-bd17-44be-90bd-a5065d1e6ee0": """
        <important>
        COMPETÊNCIA 4: Conhecimento dos Mecanismos Linguísticos
        </important>

        Nota 200:
        - Utiliza conectivos em todo início de período.
        - Articula bem as partes do texto e apresenta um repertório diversificado de recursos coesivos, conectando parágrafos e períodos de forma fluida.
        - Utiliza referenciação adequada, com pronomes, sinônimos e advérbios, garantindo coesão e clareza.
        - Apresenta transições claras e bem estruturadas entre as ideias de causa/consequência, comparação e conclusão, sem falhas.
        - Demonstra excelente organização de períodos complexos, com uma articulação eficiente entre orações.
        - Não repete muitos conectivos ao longo do texto.

        Nota 160:
        - Deixa de usar uma ou duas vezes conectivos ao longo do texto.
        - Articula as partes do texto, mas com poucas inadequações ou problemas pontuais na conexão de ideias.
        - Apresenta um repertório diversificado de recursos coesivos, mas com algumas falhas no uso de pronomes, advérbios ou sinônimos.
        - As transições entre parágrafos e ideias são adequadas, mas com pequenos deslizes na estruturação dos períodos complexos.
        - Mantém boa coesão e coerência, mas com algumas falhas na articulação entre causas, consequências e exemplos.

        Nota 120:
        - Não usa muitos conectivos ao longo dos parágrafos.
        - Repete várias vezes o mesmo conectivo ao longo do parágrafo.
        - Articula as partes do texto de forma mediana, apresentando inadequações frequentes na conexão de ideias.
        - O repertório de recursos coesivos é pouco diversificado, com uso repetitivo de pronomes.
        - Apresenta transições previsíveis e pouco elaboradas, prejudicando o encadeamento lógico das ideias.
        - A organização dos períodos é mediana, com algumas orações mal articuladas, comprometendo a fluidez do texto.

        Nota 80:
        - Articula as partes do texto de forma insuficiente, com muitas inadequações no uso de conectivos e outros recursos coesivos.
        - O repertório de recursos coesivos é limitado, resultando em repetição excessiva ou uso inadequado de pronomes e advérbios.
        - Apresenta conexões falhas entre os parágrafos, com transições abruptas e pouco claras entre as ideias.
        - Os períodos complexos estão mal estruturados, com orações desconectadas ou confusas.

        Nota 40:
        - Articula as partes do texto de forma precária, com sérias falhas na conexão de ideias.
        - O repertório de recursos coesivos é praticamente inexistente, sem o uso adequado de pronomes, conectivos ou advérbios.
        - Apresenta parágrafos desarticulados, sem relação clara entre as ideias.
        - Os períodos são curtos e desconectados, sem estruturação adequada ou progressão de ideias.

        Nota 0:
        - Não articula as informações e as ideias parecem desconexas e sem coesão.
        - O texto não apresenta recursos coesivos, resultando em total falta de conexão entre as partes.
        - Os parágrafos e períodos são desorganizados, sem qualquer lógica na apresentação das ideias.
        - O texto não utiliza mecanismos de coesão (pronomes, conectivos, advérbios), tornando-o incompreensível.
    """,  # noqa: E501
    "fd207ce5-b400-475b-a136-ce9c4d5cd00d": """
        <important>
        COMPETÊNCIA 5: Proposta de Intervenção
        Aqui não é necessário avaliar a profundidade dos 5 elementos e argumentos nem a profundidade do detalhamento, apenas a presença de cada um deles. Se todos estiverem presentes, a nota deverá ser 200.
        </important>

        Nota 200:
        - Elabora proposta de intervenção completa com todos os 5 elementos (agente, ação, modo/meio, detalhamento e finalidade).

        Nota 160:
        - Elabora bem a proposta de intervenção, mas com apenas 4 elementos presentes.

        Nota 120:
        - Elabora uma proposta de intervenção mediana, com apenas 3 elementos presentes.

        Nota 80:
        - Elabora uma proposta de intervenção insuficiente, com apenas 2 elementos presentes, ou se a proposta for mal articulada ao tema.

        Nota 40:
        - Apresenta uma proposta de intervenção vaga ou precária, apresentando apenas 1 de todos os elementos exigidos.

        Nota 0:
        - Não apresenta nenhum dos 5 elementos e não apresenta proposta de intervenção ou a proposta é completamente desconectada do tema.

        <example>
        Último parágrafo do texto:
        Compete ao ministério do meio ambiente financiar diretamente a criação de pontos de coleta de lixo eletrônico em áreas estratégicas,
        Por meio de parcerias público-privadas para financiar e operar centros de descarte — Publicando relatórios trimestrais sobre o progresso das iniciativas de descarte de lixo — com a finalidade de garantir que o lixo eletrônico seja descartado no local adequado,
        tornando o ambiente mais sustentável. Além disso, concerne ao Ministério da Educação promover campanhas de conscientização sobre o descarte correto de lixo eletrônico, mediante meios de comunicação tradicionais e digitais para alcançar uma ampla audiência — motivando-as a adotar práticas de descarte de lixo mais seguras — com o objetivo de educar e sensibilizar as pessoas sobre determinados problemas,
        incentivando atitudes e comportamentos que contribuam para soluções sustentáveis.
        Seu pensamento deve ser:
        - O texto apresenta uma proposta de intervenção completa com todos os 5 elementos (agente, ação, modo/meio, detalhamento e finalidade), mesmo que os argumentos não sejam profundos ou detalhados. Nota: 200
        </example>
    """,  # noqa: E501
}


PROMPT_CRITERIA_GRADES = """
    <analysis>
    A seguir está a análise detalhada para a competência {competency_name}:
    {competency_analysis}
    </analysis>

    <evaluation criteria>
    Critérios para avaliação:
    {grading_criteria}
    </evaluation criteria>

    <task at hand>
    Sua tarefa é agora fornecer uma análise detalhada, listando e analisando separadamente cada critério de avaliação. Para cada critério, explique como o texto se comporta em relação a esse critério, indicando se o desempenho do texto atende ou não a esse ponto.
    </task at hand>

    <important rules>
    IMPORTANTE:
        - Antes de fornecer a análise final, liste e analise separadamente cada critério de avaliação e indique como o texto se comporta em relação a cada um.
    </important rules>

    <output rules>
    Com base nessa análise, forneça um output no formato JSON, com as seguintes chaves:
    {{
        "grade_200": "Sua análise detalhada sobre por que o texto se encaixa ou não nos critérios para a nota 200.",
        "grade_160": "Sua análise detalhada sobre por que o texto se encaixa ou não nos critérios para a nota 160.",
        "grade_120": "Sua análise detalhada sobre por que o texto se encaixa ou não nos critérios para a nota 120.",
        "grade_80": "Sua análise detalhada sobre por que o texto se encaixa ou não nos critérios para a nota 80.",
        "grade_40": "Sua análise detalhada sobre por que o texto se encaixa ou não nos critérios para a nota 40.",
        "grade_0": "Sua análise detalhada sobre por que o texto se encaixa ou não nos critérios para a nota 0."
    }}

    IMPORTANTE:
    - A resposta deve estar estritamente no formato JSON, sem informações adicionais.
    </output rules>
"""  # noqa: E501

PROMPT_GRADES = """
    <background>
    Sua tarefa é olhar a análise fornecida e, com base nela, pontuar a competência.
    </background>

    <analysis>
    Esta é a análise detalhada realizada para a competência {competency_name}:
    {competency_analysis}
    <analysis>

    <grading criteria>
    Análise de critérios e notas da competência:
    {grading_criteria_analysis}
    </grading criteria>

    <task at hand>
    Agora, atribua uma nota final para a competência, escolhendo um valor entre 0, 40, 80, 120, 160 e 200, e forneça uma justificativa detalhada de como os critérios foram considerados na decisão.
    </task at hand>

    <output rules>
    O output final deve estar estritamente no formato JSON:
    {{
        "grade": 0|40|80|120|160|200,
        "justification": "Justificativa detalhada explicando por que esta nota foi atribuída com base na análise e nos critérios acima."
    }}

    IMPORTANTE:
    - A resposta deve conter apenas as chaves "grade" e "justification" no formato JSON, sem informações adicionais.
    </output rules>
"""  # noqa: E501


PROMPT_FEEDBACK_GENERATOR = """
    <analysis>
    A seguir está uma análise detalhada de uma redação:
    {detailed_analysis}
    </analysis>

    <grades>
    As notas atribuídas:
    {grades}
    </grades>

    <essay>
    A redação completa:
    {essay}
    </essay>

    <task at hand>
    Baseado nisso, produza um breve feedback (máximo 5 linhas) sobre a redação.
    </task at hand>
"""  # noqa: E501
