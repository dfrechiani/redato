"""Geração de metas amigáveis pro aluno (Fase 3).

Recebe diagnóstico Fase 2 e produz 3-5 metas em linguagem positiva pra
o aluno focar na próxima redação. Frontend (ou WhatsApp) renderiza
sem expor status, confiança, evidências ou heatmap — só o "o que
fazer da próxima vez".

Decisões de design (Daniel, Fase 3):
- Linguagem motivacional, voz de professor (pra aluno).
- Máximo 5 metas — saturação cognitiva acima disso.
- Dedup de competência: se 3 lacunas em C5, agrupamos numa meta
  composta em vez de 3 frases redundantes.
- Dicionário fixo descritor → frase. Manutenção centralizada
  permite revisão pedagógica sem mudar pipeline.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────
# Dicionário descritor → meta amigável
# ──────────────────────────────────────────────────────────────────────
#
# (titulo, descricao). Cada um:
#   titulo:    1 frase curta, imperativa, voz pro aluno
#   descricao: 1-2 frases. Concreto, com exemplo quando ajuda.
#
# Manter sincrono com docs/redato/v3/diagnostico/descritores.yaml. Quando
# adicionar novo descritor, lembrar de adicionar entry aqui — fallback
# genérico cobre se faltar mas perde personalização.

_METAS: Dict[str, tuple] = {
    # ── C1 — Norma culta ──────────────────────────────────────────
    "C1.001": (
        "Escreva períodos completos",
        "Cada frase precisa ter sujeito, verbo e complemento. Evite "
        "fragmentos como 'Muitas pessoas. Sem oportunidade.'",
    ),
    "C1.002": (
        "Atenção à acentuação",
        "Reveja acentos: 'café' (não 'cafe'), 'está' vs 'esta', "
        "'porquê' vs 'por que' vs 'porque'.",
    ),
    "C1.003": (
        "Cuidado com mal/mau e mais/mas",
        "'Mau' é adjetivo (oposto de 'bom'); 'mal' é advérbio. 'Mas' é "
        "oposição; 'mais' é quantidade.",
    ),
    "C1.004": (
        "Use vírgula com cuidado",
        "Nunca separe sujeito do verbo com vírgula. Use vírgula em "
        "orações intercaladas e enumerações.",
    ),
    "C1.005": (
        "Verbo concorda com sujeito",
        "Não escreva 'fazem 5 anos' nem 'houveram problemas'. O correto "
        "é 'faz 5 anos' e 'houve problemas'.",
    ),
    "C1.006": (
        "Atenção às preposições",
        "'Prefiro X a Y' (não 'mais que'). 'Obediência à lei' (não 'da "
        "lei'). 'Esquecer-se de algo'.",
    ),
    "C1.007": (
        "Evite gírias e linguagem informal",
        "Sem 'tipo assim', 'a gente', 'né', 'vc'. Mantenha o registro "
        "formal do início ao fim.",
    ),
    "C1.008": (
        "Escolha palavras precisas",
        "Evite repetir o mesmo substantivo. Use sinônimos. Cuidado com "
        "palavras 'grandes' fora de contexto.",
    ),

    # ── C2 — Compreensão da proposta ──────────────────────────────
    "C2.001": (
        "Aborde o tema proposto",
        "Não fuja para temas correlatos. Se o tema é 'inclusão "
        "digital', escreva sobre isso — não 'educação em geral'.",
    ),
    "C2.002": (
        "Escolha um recorte específico",
        "Não tente cobrir o tema inteiro. Escolha um ângulo (uma "
        "causa, um aspecto, um grupo afetado) e desenvolva.",
    ),
    "C2.003": (
        "Mantenha a estrutura dissertativa",
        "Introdução + 2 desenvolvimentos + conclusão. Sem narração, "
        "carta, crônica, depoimento.",
    ),
    "C2.004": (
        "Use verbos no presente, terceira pessoa",
        "'Argumenta-se que...', 'a sociedade enfrenta...'. Sem "
        "personagens com nome, sem diálogo, sem lirismo.",
    ),
    "C2.005": (
        "Inclua repertório sociocultural",
        "Cite autor, lei, dado, fato histórico ou obra. Sem repertório, "
        "C2 fica baixa por falta de fundamentação.",
    ),
    "C2.006": (
        "Conecte o repertório ao tema",
        "Não basta citar — explique como a referência se aplica ao "
        "problema discutido. Citação solta vira enfeite.",
    ),
    "C2.007": (
        "Use o repertório como argumento",
        "Depois de citar, extraia consequência: 'logo, isso indica que...'. "
        "Não cite e abandone na frase seguinte.",
    ),
    "C2.008": (
        "Cite fontes nomeáveis",
        "Evite 'estudos mostram', 'pesquisas indicam', 'especialistas "
        "afirmam'. Nomeie autor, instituição ou lei.",
    ),

    # ── C3 — Argumentação ─────────────────────────────────────────
    "C3.001": (
        "Apresente uma tese clara na introdução",
        "Não basta dizer 'é importante refletir'. Tome posição: 'X deve "
        "ser feito porque Y'.",
    ),
    "C3.002": (
        "Defenda a tese ao longo do texto",
        "Os argumentos do desenvolvimento precisam sustentar a tese da "
        "introdução. Não trate de subtemas desconectados.",
    ),
    "C3.003": (
        "Comece cada parágrafo com tópico frasal",
        "Abra cada desenvolvimento com a ideia que será defendida ali — "
        "não com dado solto ou conectivo isolado.",
    ),
    "C3.004": (
        "Aprofunde os argumentos",
        "Não basta 'isso é grave'. Explique a causa, a consequência, "
        "o mecanismo de funcionamento.",
    ),
    "C3.005": (
        "Use argumentos diferentes em D1 e D2",
        "D1 e D2 precisam abordar aspectos distintos (ex.: D1=causa, "
        "D2=consequência). Não diga a mesma coisa duas vezes.",
    ),
    "C3.006": (
        "Articule tese, argumentos e conclusão",
        "Mantenha fio condutor. A conclusão precisa retomar a tese "
        "defendida ao longo do texto.",
    ),
    "C3.007": (
        "Defenda um ponto de vista",
        "Não basta listar causas e efeitos. Tome posição argumentativa "
        "a favor de uma leitura ou solução.",
    ),
    "C3.008": (
        "Demonstre voz própria",
        "Sintetize, contraste, infira. Não copie senso comum nem "
        "parafraseie os textos motivadores.",
    ),

    # ── C4 — Coesão textual ───────────────────────────────────────
    "C4.001": (
        "Varie os conectivos",
        "Não fique só em 'além disso' e 'também'. Use de causa "
        "(porque), conclusão (portanto), oposição (no entanto).",
    ),
    "C4.002": (
        "Escolha o conectivo certo",
        "Conectivo expressa relação lógica. Não use 'portanto' onde a "
        "relação é de oposição (use 'no entanto').",
    ),
    "C4.003": (
        "Use conectivos entre parágrafos",
        "Cada parágrafo novo deve abrir com marcador ('Em primeiro "
        "lugar', 'Ademais', 'Diante disso') — não bloco solto.",
    ),
    "C4.004": (
        "Retome ideias com pronomes e sinônimos",
        "Não repita o mesmo substantivo 4+ vezes. Use 'isso', 'essa "
        "questão', 'tal situação' ou sinônimos.",
    ),
    "C4.005": (
        "Garanta clareza na referência",
        "'Isso' precisa apontar pra antecedente claro. Pronome "
        "ambíguo confunde o leitor.",
    ),
    "C4.006": (
        "Cada parágrafo traz informação nova",
        "Não reescreva o anterior. A redação avança — não circula "
        "sobre as mesmas ideias.",
    ),
    "C4.007": (
        "Articule orações dentro do parágrafo",
        "Use 'porque', 'assim', 'logo' entre orações. Não justaponha "
        "'A. B. C.' sem ligação lógica.",
    ),
    "C4.008": (
        "Marque as transições estruturais",
        "'Primeiramente', 'Ademais', 'Por fim', 'Portanto' — sinalizam "
        "introdução, D1, D2, conclusão.",
    ),

    # ── C5 — Proposta de intervenção ──────────────────────────────
    "C5.001": (
        "Construa propostas com agente nomeado",
        "Quem vai executar? Ministério da Educação, ONGs, escolas. Não "
        "'a sociedade' nem 'todos nós'.",
    ),
    "C5.002": (
        "Use verbos de ação concretos",
        "'Criar', 'implementar', 'fiscalizar', 'ampliar'. Evite "
        "'combater' ou 'lutar contra' — vagos demais.",
    ),
    "C5.003": (
        "Explique o meio (como)",
        "Inclua 'por meio de', 'através de', 'a partir de'. Diga o "
        "instrumento concreto: programas, parcerias, recursos.",
    ),
    "C5.004": (
        "Diga a finalidade (pra quê)",
        "Use 'para', 'a fim de', 'com o objetivo de'. Toda proposta "
        "tem propósito explícito.",
    ),
    "C5.005": (
        "Detalhe pelo menos 1 elemento",
        "Expanda agente, ação, meio ou finalidade com explicação ou "
        "exemplo. Detalhamento é pré-requisito pra C5 nota 200.",
    ),
    "C5.006": (
        "Conecte a proposta ao problema",
        "A proposta resolve o que foi discutido em D1 e D2 — não "
        "pode ser sobre tema correlato.",
    ),
    "C5.007": (
        "Respeite os direitos humanos",
        "Sem violência institucional, exclusão de grupos, controle "
        "autoritário. C5 é zerada se violar — critério eliminatório.",
    ),
    "C5.008": (
        "Apresente os 5 elementos da proposta",
        "Agente + Ação + Meio + Finalidade + Detalhamento. Faltando "
        "qualquer um, C5 não chega ao topo.",
    ),
}

_FALLBACK_TITULO = "Continue praticando"
_FALLBACK_DESC = "Foque na competência indicada nas próximas redações."

MAX_METAS = 5
"""Hard cap. Briefing pediu 3-5; saturamos em 5."""


@dataclass(frozen=True)
class Meta:
    """Meta amigável pro aluno. Renderizada como cartão visual no
    portal/WhatsApp."""
    id: str             # "M1", "M2", ...
    competencia: str    # "C1".."C5"
    titulo: str
    descricao: str

    def to_dict(self) -> Dict[str, str]:
        return {
            "id": self.id,
            "competencia": self.competencia,
            "titulo": self.titulo,
            "descricao": self.descricao,
        }


def _competencia_de(descritor_id: str) -> str:
    """Extrai 'C1'..'C5' de um ID 'C1.005'. Retorna 'C?' se mal-formado."""
    if not isinstance(descritor_id, str) or len(descritor_id) < 2:
        return "C?"
    return descritor_id[:2]


def gerar_metas_aluno(diagnostico: Optional[Dict[str, Any]]) -> List[Meta]:
    """Recebe diagnóstico Fase 2 e gera 3-5 metas amigáveis pro aluno.

    Args:
        diagnostico: dict do schema Fase 2. Se None ou sem
            `lacunas_prioritarias`, retorna lista vazia.

    Returns:
        Lista com 0-5 Metas. Vazia se diagnóstico ausente ou sem
        lacunas detectadas.

    Lógica:
        1. Pega `lacunas_prioritarias` (top-5 já priorizado pelo LLM
           na Fase 2, ordem importa).
        2. Mapeia cada ID → frase amigável via dicionário fixo.
           Fallback genérico se ID desconhecido.
        3. Dedup PRESERVANDO ORDEM de competência: se 3 IDs em C5
           estão na fila, mantém o primeiro (mais prioritário) +
           descarta os outros — evita 3 metas redundantes em C5.
        4. Cap em MAX_METAS (5).
    """
    if not isinstance(diagnostico, dict):
        return []
    lacunas = diagnostico.get("lacunas_prioritarias")
    if not isinstance(lacunas, list):
        return []

    metas: List[Meta] = []
    competencias_vistas: set = set()
    for desc_id in lacunas:
        if not isinstance(desc_id, str):
            continue
        comp = _competencia_de(desc_id)
        # Dedup por competência: 1 meta por C{N}. Aluno em saturação
        # cognitiva — mostrar 3 metas em C5 dilui foco.
        if comp in competencias_vistas:
            logger.debug(
                "metas: descritor %s ignorado (competência %s já tem meta)",
                desc_id, comp,
            )
            continue
        competencias_vistas.add(comp)
        titulo, descricao = _METAS.get(
            desc_id, (_FALLBACK_TITULO, _FALLBACK_DESC),
        )
        metas.append(Meta(
            id=f"M{len(metas) + 1}",
            competencia=comp,
            titulo=titulo,
            descricao=descricao,
        ))
        if len(metas) >= MAX_METAS:
            break
    return metas


def metas_to_dicts(metas: List[Meta]) -> List[Dict[str, str]]:
    """Helper: serializa metas pro JSON do endpoint."""
    return [m.to_dict() for m in metas]


def render_metas_whatsapp(metas: List[Meta]) -> Optional[str]:
    """Renderiza metas como mensagem WhatsApp. Retorna None se 0 metas
    (caller pula o envio).

    Formato visual texto-only que cabe em chat:
        🎯 *Suas metas pra próxima redação*

        *1. Título da meta 1*
        Descrição da meta 1.

        *2. Título da meta 2*
        ...
    """
    if not metas:
        return None
    linhas = ["🎯 *Suas metas pra próxima redação*", ""]
    for i, m in enumerate(metas, start=1):
        linhas.append(f"*{i}. {m.titulo}*")
        linhas.append(m.descricao)
        linhas.append("")  # blank line entre metas
    return "\n".join(linhas).rstrip()
