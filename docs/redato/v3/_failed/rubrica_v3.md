# REDATO — RUBRICA V3 (HOLÍSTICA)

**Base:** Cartilha do Participante INEP 2025 (fonte canônica) + análise de 38 comentários oficiais INEP em redações nota 1000 (corpus inep.jsonl, anos 2017-2024).
**Filosofia:** gradação por domínio (qualitativa), não contagem (quantitativa).
**Diverge de v2 em:** C1 (substitui thresholds por critério de excepcionalidade), C2 (remove palavras-chave por parágrafo + adiciona detector de repertório de bolso), C5 (substitui contagem aritmética de elementos por critério de articulação à discussão), 0.2 (remove coerência temática do título), 0.3 (coloquialismo volta para C1).
**Data:** 2026-04-26
**Para A/B test contra:** rubrica_v2.md

---

## 0. PRÉ-CORREÇÃO

### 0.1 Anulação imediata (nota 0 em todas as competências)

Conforme Cartilha 2025 (p.9):

- Fuga total ao tema
- Não atendimento ao tipo dissertativo-argumentativo
- Folha em branco
- Extensão ≤ 7 linhas manuscritas (≤ 10 em braille)
- Impropérios, desenhos ou outras formas propositais de anulação
- Parte deliberadamente desconectada do tema
- Identificação fora do espaço destinado
- Texto predominantemente em língua estrangeira
- Texto ilegível
- Cópia integral dos textos motivadores (linhas copiadas são desconsideradas; se restarem ≤ 7, cai em "texto insuficiente")

### 0.2 Tratamento do título

Conforme Cartilha 2025 (p.9): o título não é avaliado em qualquer aspecto das competências. **Pode** levar a anulação apenas se contiver desenho, sinal sem função, impropério. **Coerência temática do título não é critério INEP** — não rebaixa C1 nem qualquer outra competência.

### 0.3 Tratamento de coloquialismo, oralidade e registro

Conforme Cartilha 2025 (p.13): "escolha de registro" é um dos quatro aspectos avaliados em **C1** (junto com convenções da escrita, gramaticais, escolha vocabular). Coloquialismo, marcas de oralidade e registro inadequado afetam C1, **não C4**.

### 0.4 Linhas perdidas com informações irrelevantes

Conforme Cartilha 2025 (p.29, "Atenção" da seção C3): linhas com informações irrelevantes, repetidas ou excessivas afetam C3 (seleção de informações em defesa do ponto de vista). Não realocar para C4.

---

## 1. COMPETÊNCIA I — DOMÍNIO DA MODALIDADE ESCRITA FORMAL

### Objeto avaliado (Cartilha 2025, pp.12-14)

Quatro frentes:
- **Convenções da escrita:** acentuação, ortografia, hífen, maiúsculas/minúsculas, translineação.
- **Gramaticais:** regência verbal/nominal, concordância verbal/nominal, tempos/modos verbais, pontuação, paralelismo, pronomes, crase.
- **Escolha de registro:** adequação à modalidade formal (ausência de informalidade e oralidade).
- **Escolha vocabular:** precisão de sentido, adequação ao contexto.

Avaliada também a **estrutura sintática**: períodos truncados, justaposição (vírgula no lugar de ponto), excesso/ausência de termos.

### Critério de gradação INEP (literal)

> "A frequência com que essas falhas ocorrem no texto e o quanto elas prejudicam sua compreensão como um todo são os critérios que ajudarão a definir o nível em que uma redação deve ser avaliada na Competência I." (Cartilha 2025, p.13)

**Não há thresholds numéricos absolutos.** A gradação integra frequência + impacto sobre compreensão + reincidência.

### Descritores

- **200** — Excelente domínio. Desvios apenas como excepcionalidade e **sem reincidência**. Estrutura sintática excelente, com períodos complexos bem construídos.
- **160** — Bom domínio. Poucos desvios. Estrutura sintática boa, com falhas pontuais que não comprometem a fluidez. Reincidência pontual de um único tipo de erro pode aparecer.
- **120** — Domínio mediano. Alguns desvios. Estrutura sintática regular, com falhas que não impedem compreensão geral.
- **80** — Domínio insuficiente. Muitos desvios. Estrutura sintática deficitária com truncamento ou justaposição frequentes. Pode haver registro inadequado (gírias, regionalismos, oralidade marcada).
- **40** — Domínio precário sistemático. Desvios diversificados e frequentes em todas as frentes.
- **0** — Desconhecimento da modalidade.

### Calibração operacional (referência ao LLM, não threshold)

Para orientar o LLM, **referenciais aproximados observados nos 38 comentários INEP em redações nota 1000**:

- 1-2 desvios pontuais não-reincidentes em texto longo e bem estruturado → compatível com 200.
- 3-4 desvios pontuais em frentes diferentes (1 vírgula, 1 crase, 1 colocação) sem reincidência → compatível com 200 ainda, ou 160 dependendo do impacto.
- Reincidência de um mesmo tipo de erro (ex.: 3 erros de pontuação do mesmo padrão) → 160 ou 120, dependendo da frequência.
- Estrutura sintática com truncamento em mais de um parágrafo → no máximo 120, mesmo com desvios pontuais poucos.

**Estes são referenciais para calibração da escala, não regras de contagem.** O juízo final é qualitativo e integra impacto sobre compreensão.

### Reincidência como divisor 200/160 (Cartilha 2025, p.14)

> "Desvios gramaticais ou de convenções da escrita serão aceitos somente como excepcionalidade e quando não caracterizarem reincidência."

Implicação: três desvios variados pontuais (vírgula + crase + acentuação) podem ser 200; três desvios reincidentes do mesmo tipo (três erros de regência verbal) caem para 160 ou 120.

---

## 2. COMPETÊNCIA II — COMPREENSÃO DA PROPOSTA E REPERTÓRIO

### Objeto avaliado (Cartilha 2025, pp.14-26)

Três componentes integrados:
1. **Compreensão da proposta:** abordagem do tema dentro do recorte definido.
2. **Repertório sociocultural:** informação, fato, citação ou experiência relacionada ao tema, articulada produtivamente ao argumento.
3. **Domínio do tipo dissertativo-argumentativo:** proposição + argumentação + conclusão; defesa explícita de ponto de vista.

### Definição INEP de tangenciamento (Cartilha 2025, p.25, literal)

Tangenciamento = "abordagem parcial baseada **somente** no assunto mais amplo a que o tema está vinculado." É teste de **cobertura do recorte temático**, não de presença de palavras-chave.

Exemplo INEP (tema "Desafios para a valorização da herança africana no Brasil"):
- Tangenciamento = abordar herança africana no Brasil sem relacionar com desafios/valorização.
- Tangenciamento = abordar valorização da herança africana mas em outro país.
- Tangenciamento = abordar desafio (preconceito) e herança africana sem relacionar com valorização no Brasil.

**Detector de tangenciamento:** decompor o tema em seus elementos constitutivos (não em palavras-chave) e verificar se o texto cobre **todos** os elementos em sua articulação. Falta de um elemento essencial = tangenciamento. Texto com elementos cobertos mas terminologia ampla (ex.: "ambiente digital" em tema "redes sociais") **não é tangenciamento** se a discussão de fato cobre o recorte.

**Penalização do tangenciamento:** afeta C2, C3 e C5 simultaneamente — máximo 40 em todas as três (Cartilha 2025, p.25).

### Definição INEP de repertório de bolso (Cartilha 2025, pp.16-21)

Repertório de bolso = referência pronta, memorizada, usada de forma genérica e pouco aprofundada, sem conexão genuína com o tema.

**Critério de produtividade INEP:** está na **articulação ao argumento específico onde aparece**, não na qualidade isolada da fonte.

Mesma referência (Bauman, Thomas More, Han, Zuboff) pode ser:
- **Produtiva** se contextualizada e articulada à argumentação específica do parágrafo.
- **Repertório de bolso** se citada decorativamente, com explicação genérica, sem articulação concreta ao tema.

**Detector de repertório de bolso (heurística):**
1. A referência é explicada e contextualizada, ou apenas mencionada como autoridade?
2. A referência é retomada/aprofundada nos parágrafos seguintes, ou desaparece após a citação?
3. A articulação ao tema específico é concreta (com ponte explicativa) ou genérica (apenas justaposição)?
4. A função argumentativa da referência é específica (sustenta uma tese particular) ou ornamental (eleva o tom do texto)?

Se 2+ flags positivas → repertório de bolso → não conta como produtivo, mesmo se legitimado.

### Repertório legítimo (Cartilha 2025, pp.21-23)

INEP valoriza **explicitamente** dois tipos:
- **Conhecimento institucionalizado:** historiadores, escritores, filósofos, artistas, obras canônicas, dados de pesquisas.
- **Conhecimento de mundo:** referências culturais (Cartola, samba-enredo), experiência pessoal articulada ao tema, observações cotidianas legítimas.

**Não há exigência de fonte citada formal (autor + obra + data) para 200.** Não há exigência de distribuição parágrafo a parágrafo.

### Descritores

- **200** — Argumentação consistente, repertório produtivo, excelente domínio do dissertativo-argumentativo.
- **160** — Argumentação consistente, bom domínio do tipo (proposição/argumentação/conclusão).
- **120** — Argumentação **previsível**, domínio mediano.
- **80** — Recorre à cópia dos motivadores OU domínio insuficiente do tipo textual.
- **40** — Tangencia o tema OU domínio precário com traços de outros tipos textuais.
- **0** — Fuga total ou não atendimento ao tipo.

### Critério qualitativo 160/120: "consistente" vs "previsível"

> Distinção INEP central. Argumentação previsível pode ter três parágrafos completos, repertório legitimado, tipo dissertativo-argumentativo intacto, e ainda ser 120.

**Indicadores de argumentação previsível:**
- Estrutura argumentativa clichê (causa-consequência sem aprofundamento, "primeiro/segundo/conclusão" sem desenvolvimento real).
- Repertório usado como ornamento, sem aprofundamento (categoria adjacente a repertório de bolso, mas pode aparecer sem ele).
- Argumentos genéricos aplicáveis a qualquer tema próximo ("a sociedade precisa mudar", "a educação é a chave", "o governo precisa agir").
- Ausência de recorte original — repete o que os textos motivadores já dizem.

---

## 3. COMPETÊNCIA III — SELEÇÃO, RELAÇÃO, ORGANIZAÇÃO, INTERPRETAÇÃO

### Objeto avaliado (Cartilha 2025, pp.27-30)

Projeto de texto: planejamento prévio à escrita, legível pela organização estratégica dos argumentos. Quatro fatores compõem inteligibilidade:
- Seleção de argumentos
- Relação de sentido entre as partes
- Progressão adequada ao desenvolvimento do tema
- Desenvolvimento dos argumentos (com explicitação da relevância)

### Termo operativo de banca: "projeto de texto bem definido"

Observação dos 38 comentários INEP: a banca usa "projeto de texto bem definido / bem delimitado / bem delineado" como termo operativo recorrente (34/38 comentários). O termo "autoria" do descritor oficial **não aparece nos comentários** — opera como conceito técnico abstrato cujo correlato observável é "projeto de texto evidenciando estratégia clara".

### Descritores

- **200** — Informações, fatos e opiniões relacionados ao tema, de forma consistente e organizada, configurando autoria, em defesa de um ponto de vista. **Operacionalmente:** projeto de texto bem definido com estratégia argumentativa legível, recorte original.
- **160** — Informações organizadas, com **indícios de autoria**, em defesa de um ponto de vista. **Operacionalmente:** projeto de texto presente mas com inadequações pontuais, ou estratégia menos articulada.
- **120** — Informações relacionadas ao tema, **limitadas aos argumentos dos textos motivadores** e pouco organizadas. **Operacionalmente:** texto não foge dos motivadores, sem aprofundamento próprio.
- **80** — Informações desorganizadas ou contraditórias, limitadas aos motivadores.
- **40** — Informações pouco relacionadas ao tema, sem ponto de vista claro.
- **0** — Informações não relacionadas, sem defesa de ponto de vista.

### Detectores de rebaixamento C3

- **Limitação aos motivadores:** texto repete ideias dos textos motivadores sem extrapolação. Disparador para 120 mesmo se bem organizado.
- **Saltos temáticos:** mudanças abruptas entre parágrafos sem articulação. Disparador para 80.
- **Contradição interna:** parágrafo 2 desmente parágrafo 3, ou conclusão desmente desenvolvimento. Disparador para 80.
- **Linhas perdidas com informação irrelevante:** parágrafos com encheção, repetição ou tangentes não articuladas ao ponto de vista. Pesa para 120 ou 80.

---

## 4. COMPETÊNCIA IV — MECANISMOS LINGUÍSTICOS

### Objeto avaliado (Cartilha 2025, pp.30-33)

Articulação entre as partes do texto + repertório de recursos coesivos. Em três níveis:
- **Estruturação de parágrafos:** articulação explícita entre eles.
- **Estruturação de períodos:** períodos complexos com orações coordenadas e subordinadas, sem truncamento.
- **Referenciação:** retomada de pessoas, coisas, lugares e fatos por pronomes, sinônimos, hipônimos, hiperônimos, expressões resumitivas, elipse.

### Distinção C3 vs C4 (Cartilha 2025, p.31, literal)

C3 = "estrutura mais profunda do texto" (projeto, organização das ideias).
C4 = "marcas linguísticas que ajudam o leitor a chegar à compreensão profunda" (superfície coesiva).

### Critério INEP central (Cartilha 2025, p.33, literal)

> "Boa coesão não depende da mera presença de conectivos no texto, muito menos de serem utilizados em grande quantidade — é preciso que esses recursos estabeleçam relações lógicas adequadas entre as ideias apresentadas."

**Avalia-se adequação semântica do conectivo, não contagem nem variedade pela variedade.** Conectivo errado pode ser pior que conectivo ausente.

### Descritores

- **200** — Articula bem as partes; repertório diversificado de recursos coesivos.
- **160** — Articula com poucas inadequações; repertório diversificado.
- **120** — Articulação mediana com inadequações; repertório pouco diversificado.
- **80** — Articulação insuficiente, muitas inadequações; repertório limitado.
- **40** — Articulação precária.
- **0** — Não articula as informações.

### Detectores de rebaixamento C4

- **Conectivo com relação lógica errada:** "portanto" introduzindo causa em vez de consequência, "no entanto" entre ideias compatíveis, etc. Mais grave que ausência de conectivo.
- **Repetição excessiva de conectivos:** "Além disso, além disso, ademais" — disparador para repertório pouco diversificado.
- **Falta de articulação entre parágrafos:** parágrafos justapostos sem conexão lógica explícita.
- **Referenciação ambígua:** pronomes sem antecedente claro, "isso" / "esse" sem referência identificável.
- **Períodos truncados:** ponto final entre orações que deveriam ser uma só. (Atenção: também pesa em C1 — fronteira porosa.)

---

## 5. COMPETÊNCIA V — PROPOSTA DE INTERVENÇÃO

### Objeto avaliado (Cartilha 2025, pp.33-37)

Proposta de iniciativa que enfrente o problema, articulada à discussão desenvolvida no texto, respeitando os direitos humanos.

### Os 4 atributos canônicos (observados em 38 comentários INEP)

A fórmula recorrente para C5=200 nos comentários da banca:

> "elabora proposta de intervenção muito boa: **concreta, detalhada, articulada à discussão desenvolvida no texto e que respeita os direitos humanos**."

Quatro atributos qualitativos integrados:
1. **Concreta** — não vaga; aponta solução específica, não apenas constata problema.
2. **Detalhada** — informação adicional que aprofunda a proposta.
3. **Articulada à discussão desenvolvida no texto** — coerente com o ponto de vista e os argumentos do texto, não desconectada.
4. **Respeita os direitos humanos** — sem propostas que firam dignidade, igualdade, valorização das diferenças.

### Os 6 elementos pedagógicos da Cartilha (são ferramentas, não checklist)

A Cartilha sugere ao participante 6 perguntas para construir uma boa proposta:
1. O que apresentar como solução?
2. Que ação tomar?
3. Quem deve executá-la? (agente)
4. Como viabilizar? (modo/meio)
5. Qual efeito? (finalidade)
6. Que detalhamento adicional?

**Estes são critérios pedagógicos para o aluno, não régua de contagem para o corretor.** Em 38 comentários INEP, a banca **não enumera 5 elementos**. A banca avalia pela qualidade integrada da proposta.

### Descritores

- **200** — Proposta detalhada, relacionada ao tema **e articulada à discussão** desenvolvida no texto.
- **160** — Proposta bem elaborada, relacionada ao tema **e articulada** à discussão.
- **120** — Proposta mediana, relacionada ao tema e articulada à discussão.
- **80** — Proposta insuficiente OU **não articulada** à discussão.
- **40** — Proposta vaga, precária, **OU relacionada apenas ao assunto** (não ao tema específico).
- **0** — Sem proposta OU desconectada do tema OU desrespeito aos direitos humanos (zera C5, não a redação inteira).

### Detectores de rebaixamento C5

- **Proposta vaga:** "é preciso que algo seja feito", "a sociedade deve mudar". Disparador para 40.
- **Proposta apenas constatatória:** "faltam investimentos em educação", "o governo precisa agir mais". Não é proposta — é constatação. Disparador para 40.
- **Proposta condicional:** "se isso fosse feito, o resultado seria...". Não é proposta — é hipótese. Disparador para 80 ou 40.
- **Proposta desarticulada:** apresenta solução genérica que não responde aos problemas específicos discutidos no texto. Disparador para 80, mesmo com agente/ação/meio/finalidade formalmente presentes.
- **Proposta apenas ao assunto:** trata o assunto amplo, não o recorte temático específico. Disparador para 40.
- **Desrespeito aos direitos humanos:** proposta inclui violência, discriminação, "justiça com as próprias mãos", privação de direitos a grupos. Disparador para C5=0.

### Por que NÃO contar 5 elementos

A v2 contava: 5 elementos = 200, 4 = 160, 3 = 120, 2 = 80, 1 = 40.

A banca INEP não faz isso. Implicações:
- Proposta com 5 elementos formalmente presentes mas desarticulada da discussão = **80 INEP** (descritor literal: "não articulada"), não 200.
- Proposta com 4 elementos bem articulados, com detalhamento substancial, integrada ao projeto = **200 INEP** possível (descritor não exige 5 elementos), não 160.
- Proposta vaga com agente nomeado + verbo de ação ("Ministério atua, Congresso age, autoridades dão atenção") = **40 INEP** ("vaga, precária, ou apenas ao assunto"), não 80.

A v3 abandona contagem aritmética. O LLM avalia a proposta nos 4 atributos canônicos e aplica detectores de rebaixamento.

---

## 6. PROPAGAÇÃO DE EFEITOS ENTRE COMPETÊNCIAS

### Tangenciamento (Cartilha 2025, p.25)

Afeta C2, C3 e C5 simultaneamente — máximo 40 em todas as três.

### Cópia recorrente dos motivadores (Cartilha 2025, p.15)

Pesa em C2 (até 80 — "recorre à cópia dos motivadores") e C3 (até 120 — "limitados aos argumentos dos textos motivadores").

### Desrespeito aos direitos humanos (Cartilha 2025, p.36)

Zera C5 apenas. Não afeta as outras competências (a redação inteira não é zerada).

### Domínio precário do tipo dissertativo-argumentativo

Se a redação tem traços constantes de outros tipos textuais (narrativo, descritivo) sem ser predominantemente desses tipos, pesa em C2 (até 40). Predominância de outro tipo = anulação total (Cartilha 2025, p.27).

### Reciprocidade C3 ↔ C4

A fronteira é porosa por construção da Cartilha. Linhas perdidas com informação irrelevante = C3. Repetição de termos coesivos sem variedade = C4. Truncamento sintático = C1 + C4 (estrutura + falta de articulação). O LLM deve nomear o problema mas evitar contar duas vezes — escolher a competência onde o impacto é mais saliente.

---

## 7. SAÍDA ESPERADA DO LLM

### Camada 1 — Audit em prosa (voz de banca operativa)

Para cada redação, o LLM produz um audit em prosa de 400-800 palavras estruturado em parágrafos por competência, na ordem em que cada competência for mais saliente para aquela redação específica (não há ordem fixa). Linguagem: termos técnicos INEP da camada 2 (projeto de texto bem definido, repertório legítimo e pertinente e produtivo, recursos coesivos sem inadequações, proposta concreta articulada à discussão, apenas um desvio, imprecisão vocabular). Quotes literais para evidência.

### Camada 2 — Estrutura JSON

```json
{
  "notas": {
    "c1": <0|40|80|120|160|200>,
    "c2": <0|40|80|120|160|200>,
    "c3": <0|40|80|120|160|200>,
    "c4": <0|40|80|120|160|200>,
    "c5": <0|40|80|120|160|200>
  },
  "flags": {
    "anulacao": null | "fuga_total" | "nao_atende_tipo" | "extensao_insuficiente" | "improperio" | "parte_desconectada" | "lingua_estrangeira" | "ilegivel",
    "tangenciamento": <bool>,
    "copia_motivadores_recorrente": <bool>,
    "repertorio_de_bolso": <bool>,
    "argumentacao_previsivel": <bool>,
    "limitacao_aos_motivadores": <bool>,
    "proposta_vaga_ou_constatatoria": <bool>,
    "proposta_desarticulada": <bool>,
    "desrespeito_direitos_humanos": <bool>
  },
  "evidencias": {
    "c1": [{"trecho": "...", "tipo_desvio": "...", "comentario": "..."}],
    "c2": [{"trecho": "...", "categoria": "tangenciamento|repertorio_bolso|...", "comentario": "..."}],
    "c3": [{"trecho": "...", "categoria": "...", "comentario": "..."}],
    "c4": [{"trecho": "...", "categoria": "...", "comentario": "..."}],
    "c5": [{"trecho": "...", "categoria": "...", "comentario": "..."}]
  }
}
```

### Consistência entre camadas

- Toda nota < 200 deve ter pelo menos uma evidência associada.
- Toda flag = true deve estar refletida no audit em prosa.
- Notas e flags devem ser consistentes com os critérios desta rubrica.
- Divergência entre camada 1 e camada 2 é sinal de erro de raciocínio do LLM.

---

## 8. SÍNTESE DAS DIVERGÊNCIAS V2 → V3

| Tópico | v2 | v3 |
|---|---|---|
| C1 — gradação | thresholds numéricos absolutos | excepcionalidade + reincidência + impacto sobre compreensão |
| C1 — coloquialismo | em C4 | em C1 (escolha de registro), conforme Cartilha |
| C2 — tangenciamento | palavras-chave por parágrafo | cobertura do recorte temático |
| C2 — repertório | legitimated/productive como flags | detector de repertório de bolso (4 heurísticas) + repertório legítimo inclui conhecimento de mundo |
| C2 — fonte citada | exigida para 200 | não exigida (Cartilha não exige) |
| C2 — distribuição D1+D2 | exigida | não aplicável |
| C2 — argumentação previsível | ausente | descritor 120 com indicadores explícitos |
| C3 — autoria | termo central | termo técnico, mas critério operacional é "projeto de texto bem definido" |
| C3 — linhas irrelevantes | em C4 | em C3 (Cartilha) |
| C5 — gradação | contagem aritmética 5/4/3/2/1 elementos | 4 atributos qualitativos (concreta, detalhada, articulada, respeita DH) |
| C5 — meio/finalidade | marcadores literais obrigatórios | presença semântica suficiente |
| C5 — direitos humanos | ausente | zera C5 (não a redação) |
| 0.2 — título | coerência temática exigida | só anulação por desenho/sinal/impropério (Cartilha) |
| Detectores rebaixamento | parciais | explícitos para repertório de bolso, tangenciamento, previsível, vaga, desarticulada, desrespeito DH |
| Saída | nota + raciocínio | camada 1 (audit prosa) + camada 2 (JSON estruturado) |
