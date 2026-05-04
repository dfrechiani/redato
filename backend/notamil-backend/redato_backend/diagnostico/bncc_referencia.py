"""Referência das 54 habilidades BNCC do Ensino Médio — Língua Portuguesa.

Códigos EM13LP01 a EM13LP54 organizados por **eixos de organização
curricular** da BNCC EM (área de Linguagens, componente de Língua
Portuguesa).

Importante:
- As descrições aqui são **resumidas** (1-2 frases por habilidade)
  baseadas no documento oficial da BNCC EM. Versão completa tem
  desdobramentos extras — esta versão mantém o núcleo da habilidade
  pra caber em UI.
- Cross-referenciado com descrições paráfrase dos livros do
  professor (1S/2S/3S) onde havia.
- Habilidades fora do range LP01-LP54 (ex.: EM13LGG101, EM13LGG701)
  pertencem ao componente Linguagens GERAL — fora do escopo desta
  referência. Aluno e professor lidam com elas em outras
  disciplinas.

Fonte: Base Nacional Comum Curricular — Ensino Médio, área de
Linguagens, componente Língua Portuguesa. Verificar contra texto
oficial antes de usar em material pedagógico publicado.

Uso:
    from redato_backend.diagnostico.bncc_referencia import (
        BNCC_LP_EM, get_bncc_descricao,
    )
    desc = get_bncc_descricao("EM13LP02")
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass(frozen=True)
class HabilidadeBNCC:
    codigo: str             # "EM13LP01"
    descricao: str          # texto resumido (1-2 frases)
    eixo: str               # "Leitura" | "Produção de textos" | "Análise linguística/semiótica" | "Oralidade"
    area: str = "Linguagens, Códigos e suas Tecnologias"
    componente: str = "Língua Portuguesa"


# ──────────────────────────────────────────────────────────────────────
# Catálogo BNCC EM — Língua Portuguesa
# ──────────────────────────────────────────────────────────────────────
#
# Organizado por eixos:
# - Todas as práticas (LP01-LP07): habilidades transversais
# - Leitura (LP08-LP18): compreensão e análise de textos
# - Produção de textos (LP19-LP31): escrita e revisão
# - Análise linguística/semiótica (LP32-LP46): metalinguagem
# - Oralidade (LP47-LP54): práticas orais formais
#
# Atenção: a numeração exata por eixo varia entre versões da BNCC.
# Esta organização é orientativa — o que importa pro mapeamento é a
# habilidade individual.

_HABILIDADES: List[HabilidadeBNCC] = [
    # ── Todas as práticas (LP01-LP07) ─────────────────────────────
    HabilidadeBNCC("EM13LP01",
        "Relacionar o texto, tanto na produção como na leitura/escuta, "
        "com suas condições de produção e seu contexto sócio-histórico "
        "de circulação.",
        "Todas as práticas"),
    HabilidadeBNCC("EM13LP02",
        "Estabelecer relações entre as partes do texto, levando em "
        "conta a construção composicional e o estilo do gênero, "
        "identificando recursos linguísticos e semióticos que operam "
        "nos textos.",
        "Todas as práticas"),
    HabilidadeBNCC("EM13LP03",
        "Analisar relações de intertextualidade e interdiscursividade "
        "que permitam a explicitação de relações dialógicas, "
        "polêmicas e contratuais.",
        "Todas as práticas"),
    HabilidadeBNCC("EM13LP04",
        "Estabelecer relações de interdiscursividade e "
        "intertextualidade para explicitar, sustentar e qualificar "
        "posicionamentos e para construir e referendar argumentos.",
        "Todas as práticas"),
    HabilidadeBNCC("EM13LP05",
        "Analisar, em textos argumentativos, os movimentos "
        "argumentativos utilizados (sustentação, refutação e "
        "negociação), avaliando os valores neles imbricados.",
        "Todas as práticas"),
    HabilidadeBNCC("EM13LP06",
        "Analisar efeitos de sentido decorrentes do uso de mecanismos "
        "de intertextualidade (referências, alusões, retomadas) entre "
        "textos literários, identificando filiações estéticas.",
        "Todas as práticas"),
    HabilidadeBNCC("EM13LP07",
        "Analisar, em textos de diferentes gêneros, marcas que "
        "expressam a posição do enunciador frente àquilo que é dito.",
        "Todas as práticas"),

    # ── Leitura (LP08-LP18) ───────────────────────────────────────
    HabilidadeBNCC("EM13LP08",
        "Inferir e justificar, em textos multissemióticos, o efeito "
        "de sentido decorrente da escolha de imagens estáticas, "
        "sequenciação ou sobreposição de imagens, definição de "
        "figura/fundo, ângulo, profundidade e foco.",
        "Leitura"),
    HabilidadeBNCC("EM13LP09",
        "Comparar o tratamento dado pela mídia jornalística a um "
        "mesmo fato noticioso, identificando particularidades da "
        "linha editorial de cada veículo.",
        "Leitura"),
    HabilidadeBNCC("EM13LP10",
        "Analisar o fenômeno da pós-verdade, exemplificando-o a "
        "partir de casos verificados em ações comunicativas em "
        "diferentes campos, com atenção aos riscos pra a sociedade "
        "e democracia.",
        "Leitura"),
    HabilidadeBNCC("EM13LP11",
        "Fazer curadoria de informação, tendo em vista diferentes "
        "propósitos e projetos discursivos, levando em conta a "
        "confiabilidade das fontes.",
        "Leitura"),
    HabilidadeBNCC("EM13LP12",
        "Selecionar informações, dados e argumentos em fontes "
        "confiáveis, impressas e digitais, e utilizá-los de forma "
        "referenciada, pra que o texto a ser produzido tenha um "
        "nível de aprofundamento adequado.",
        "Leitura"),
    HabilidadeBNCC("EM13LP13",
        "Analisar, a partir de referências contextuais, estéticas e "
        "culturais, efeitos de sentido decorrentes de escolhas e "
        "composições expressivas em diferentes textos.",
        "Leitura"),
    HabilidadeBNCC("EM13LP14",
        "Analisar, em textos de diferentes gêneros, os efeitos de "
        "sentido decorrentes do uso de recursos linguísticos e "
        "multissemióticos.",
        "Leitura"),
    HabilidadeBNCC("EM13LP15",
        "Planejar, produzir, revisar, editar, reescrever e avaliar "
        "textos escritos e multissemióticos, considerando sua "
        "adequação às condições de produção do texto.",
        "Leitura"),
    HabilidadeBNCC("EM13LP16",
        "Produzir e analisar textos orais, considerando sua "
        "adequação aos contextos de produção, à forma composicional "
        "e ao estilo do gênero em questão.",
        "Leitura"),
    HabilidadeBNCC("EM13LP17",
        "Elaborar planos, esboços e roteiros de leitura de textos "
        "complexos, considerando suas características estilísticas, "
        "estruturais e linguísticas.",
        "Leitura"),
    HabilidadeBNCC("EM13LP18",
        "Investigar e analisar a organização política dos diferentes "
        "campos de atuação da vida pública, identificando o papel "
        "dos diversos agentes.",
        "Leitura"),

    # ── Produção de textos (LP19-LP31) ────────────────────────────
    HabilidadeBNCC("EM13LP19",
        "Compreender e produzir textos jornalísticos opinativos "
        "diversos, levando em conta o contexto de produção e as "
        "regularidades dos gêneros.",
        "Produção de textos"),
    HabilidadeBNCC("EM13LP20",
        "Compreender e produzir textos jornalísticos informativos "
        "(notícia, reportagem multimidiática, infográfico, "
        "minidocumentário) considerando seu contexto de produção.",
        "Produção de textos"),
    HabilidadeBNCC("EM13LP21",
        "Produzir, de forma colaborativa, e socializar playlists, "
        "vlogs, dramatizações, fotorreportagens, carteiras-síntese, "
        "minidocumentários, ensaios e outras produções, em diferentes "
        "mídias.",
        "Produção de textos"),
    HabilidadeBNCC("EM13LP22",
        "Construir e/ou atualizar, de forma colaborativa, registros "
        "dinâmicos sobre artistas, escritores, obras e movimentos "
        "estéticos brasileiros e estrangeiros.",
        "Produção de textos"),
    HabilidadeBNCC("EM13LP23",
        "Analisar criticamente o histórico e o discurso político de "
        "candidatos a partir do exame de propostas e de declarações "
        "em diferentes mídias.",
        "Produção de textos"),
    HabilidadeBNCC("EM13LP24",
        "Analisar discursos políticos, especialmente os campanhas "
        "eleitorais, considerando recursos linguísticos e ideologias "
        "subjacentes.",
        "Produção de textos"),
    HabilidadeBNCC("EM13LP25",
        "Participar de eventos científicos, expondo, com adequação "
        "linguística e estilo, resultados de pesquisas, projetos e "
        "outros trabalhos por meio de comunicações orais.",
        "Produção de textos"),
    HabilidadeBNCC("EM13LP26",
        "Tomar parte em discussões on-line e offline acerca de fatos, "
        "dados e informações pertinentes a temas relevantes pra a "
        "vida coletiva.",
        "Produção de textos"),
    HabilidadeBNCC("EM13LP27",
        "Engajar-se ativamente no processo de planejamento, "
        "execução, revisão pública, divulgação de pesquisas, "
        "considerando o contexto de produção.",
        "Produção de textos"),
    HabilidadeBNCC("EM13LP28",
        "Organizar situações de estudo, definindo objetivos, "
        "selecionando informações relevantes em fontes confiáveis, "
        "registrando por meio de notas, esquemas e resumos.",
        "Produção de textos"),
    HabilidadeBNCC("EM13LP29",
        "Resumir e resenhar textos, por meio do uso de paráfrases, "
        "produzindo textos argumentativos com domínio das técnicas "
        "discursivas e do gênero.",
        "Produção de textos"),
    HabilidadeBNCC("EM13LP30",
        "Realizar pesquisas de diferentes tipos, planejando e "
        "executando, individualmente ou em grupo, com apresentação "
        "dos resultados em diferentes gêneros.",
        "Produção de textos"),
    HabilidadeBNCC("EM13LP31",
        "Compreender criticamente discursos sobre estudos, ciência "
        "e tecnologia presentes na mídia, levando em conta seus "
        "efeitos pra a formação de opiniões.",
        "Produção de textos"),

    # ── Análise linguística/semiótica (LP32-LP46) ────────────────
    HabilidadeBNCC("EM13LP32",
        "Selecionar informações, dados e argumentos em diversos "
        "tipos de fontes, avaliando a qualidade e a utilidade pra "
        "produzir textos com confiabilidade.",
        "Análise linguística/semiótica"),
    HabilidadeBNCC("EM13LP33",
        "Selecionar, elaborar e utilizar instrumentos de coleta de "
        "dados e informações (questionários, entrevistas, mapeamentos) "
        "em pesquisas escolares.",
        "Análise linguística/semiótica"),
    HabilidadeBNCC("EM13LP34",
        "Produzir textos pra a divulgação científica em diferentes "
        "mídias e suportes (artigo de divulgação, notícia, post, "
        "infográfico).",
        "Análise linguística/semiótica"),
    HabilidadeBNCC("EM13LP35",
        "Utilizar adequadamente ferramentas de apoio a apresentações "
        "orais, de revisão e edição de textos escritos e "
        "multissemióticos, escolhendo as funcionalidades pertinentes.",
        "Análise linguística/semiótica"),
    HabilidadeBNCC("EM13LP36",
        "Produzir, revisar e editar textos voltados pra a divulgação "
        "do conhecimento e de dados e resultados de pesquisas, tais "
        "como artigos, posts, vídeos científicos.",
        "Análise linguística/semiótica"),
    HabilidadeBNCC("EM13LP37",
        "Analisar os interesses que movem o campo jornalístico, os "
        "efeitos das novas tecnologias no processo produtivo e em "
        "termos de impacto social.",
        "Análise linguística/semiótica"),
    HabilidadeBNCC("EM13LP38",
        "Analisar os efeitos de sentido provocados pelas escolhas "
        "linguísticas e multissemióticas (vocabulário, ortografia, "
        "tipografia, layout) na construção textual.",
        "Análise linguística/semiótica"),
    HabilidadeBNCC("EM13LP39",
        "Analisar relações entre textos e seus contextos de produção, "
        "circulação e recepção, identificando posicionamentos políticos, "
        "ideológicos e estéticos.",
        "Análise linguística/semiótica"),
    HabilidadeBNCC("EM13LP40",
        "Analisar o fenômeno da disseminação de notícias falsas e os "
        "mecanismos pra checagem de informação e formação de opinião "
        "em mídias digitais.",
        "Análise linguística/semiótica"),
    HabilidadeBNCC("EM13LP41",
        "Analisar os processos humanos e automáticos de curadoria que "
        "operam nas redes sociais e algoritmos digitais, comparando "
        "diferentes recortes editoriais.",
        "Análise linguística/semiótica"),
    HabilidadeBNCC("EM13LP42",
        "Acompanhar, analisar e discutir a cobertura da mídia frente "
        "a fatos de relevância social, comparando diferentes "
        "abordagens e linhas editoriais.",
        "Análise linguística/semiótica"),
    HabilidadeBNCC("EM13LP43",
        "Atuar de forma fundamentada, ética e crítica na produção e "
        "no compartilhamento de comentários, textos noticiosos e de "
        "opinião, memes, gifs, remixes diversos.",
        "Análise linguística/semiótica"),
    HabilidadeBNCC("EM13LP44",
        "Analisar formas contemporâneas de publicidade em contexto "
        "digital, e peças de campanhas publicitárias e políticas, "
        "discutindo apelos persuasivos.",
        "Análise linguística/semiótica"),
    HabilidadeBNCC("EM13LP45",
        "Analisar, discutir, produzir e socializar produções que "
        "tratem dos direitos humanos, das diferenças e da resolução "
        "de conflitos, propostos em redes sociais.",
        "Análise linguística/semiótica"),
    HabilidadeBNCC("EM13LP46",
        "Compartilhar sentidos construídos na leitura e na "
        "interpretação de textos, posicionando-se frente a "
        "diferentes pontos de vista.",
        "Análise linguística/semiótica"),

    # ── Oralidade (LP47-LP54) ─────────────────────────────────────
    HabilidadeBNCC("EM13LP47",
        "Participar de eventos (saraus, competições orais, debates, "
        "mostras, feiras, salões literários) que oportunizem o "
        "compartilhamento e a recepção de obras culturais.",
        "Oralidade"),
    HabilidadeBNCC("EM13LP48",
        "Identificar assimilações, rupturas e permanências no processo "
        "de constituição da literatura brasileira e ao longo de sua "
        "trajetória, por meio da leitura.",
        "Oralidade"),
    HabilidadeBNCC("EM13LP49",
        "Perceber as peculiaridades estruturais e estilísticas de "
        "diferentes gêneros literários (épico, lírico, dramático).",
        "Oralidade"),
    HabilidadeBNCC("EM13LP50",
        "Analisar relações intertextuais e interdiscursivas entre "
        "obras de diferentes autores e gêneros literários, percebendo "
        "diferentes recortes históricos.",
        "Oralidade"),
    HabilidadeBNCC("EM13LP51",
        "Selecionar obras do repertório artístico-literário "
        "contemporâneo à disposição segundo suas predileções, "
        "compreendendo o caráter dialógico das produções.",
        "Oralidade"),
    HabilidadeBNCC("EM13LP52",
        "Analisar obras significativas das literaturas brasileira e "
        "portuguesa e de outros países e povos, em especial a "
        "produzida pelos povos indígenas e africanos.",
        "Oralidade"),
    HabilidadeBNCC("EM13LP53",
        "Engajar-se em práticas de compartilhamento de leituras e "
        "discussões literárias com colegas e leitores externos à "
        "escola, incluindo registros em mídia.",
        "Oralidade"),
    HabilidadeBNCC("EM13LP54",
        "Criar obras autorais, em diferentes gêneros e mídias — "
        "mediante adaptação, paráfrase ou estilização — a partir "
        "de obras lidas.",
        "Oralidade"),
]


# ──────────────────────────────────────────────────────────────────────
# Indexação
# ──────────────────────────────────────────────────────────────────────

BNCC_LP_EM: Dict[str, HabilidadeBNCC] = {h.codigo: h for h in _HABILIDADES}
"""Mapping codigo → HabilidadeBNCC pra lookup O(1)."""

CODIGOS_VALIDOS: frozenset = frozenset(BNCC_LP_EM.keys())
"""Set imutável usado pelo schema do mapeador (enum) e pela
validação no helper."""


def get_bncc_descricao(codigo: str) -> Optional[str]:
    """Retorna descrição da habilidade ou None se código não existe.
    Útil pra UI mostrar tooltip com texto BNCC."""
    h = BNCC_LP_EM.get(codigo)
    return h.descricao if h else None


def listar_codigos_ordenados() -> List[str]:
    """Lista de códigos ordenada (LP01, LP02, ..., LP54). Usado em
    schemas + tests pra ordem determinística."""
    return sorted(
        BNCC_LP_EM.keys(),
        key=lambda c: int(c.replace("EM13LP", "")),
    )


def is_codigo_valido(codigo: str) -> bool:
    """True se está no catálogo. False pra códigos fora do range
    LP01-LP54 (ex.: EM13LGG101 do componente Linguagens GERAL)."""
    return codigo in CODIGOS_VALIDOS
