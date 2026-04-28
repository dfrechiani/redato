"""Detectores Python por missão (advisory pre-flags).

Spec: docs/redato/v3/redato_1S_criterios.md.

Cada função recebe o texto do aluno e retorna `bool`. As detecções são
**advisory** — o LLM recebe os pre-flags como hint no user_msg e decide
se confirma ou não na flag final do schema. Detectores Python pegam só
casos cuja heurística é confiável (regex, contagem). Casos que dependem
de juízo semântico (tese genérica, salto lógico, articulação à discussão)
ficam exclusivamente com o LLM.

Cada detector é deliberadamente conservador — preferimos falso negativo
(LLM ainda decide) a falso positivo (poluir o feedback do aluno).
"""
from __future__ import annotations

import re
import unicodedata
from typing import Dict, List


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────

def _normalize(text: str) -> str:
    """Lowercase + strip de acentos pra comparação robusta."""
    nfkd = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()


# ──────────────────────────────────────────────────────────────────────
# Modo Foco C3 (OF10)
# ──────────────────────────────────────────────────────────────────────

_ANDAIME_PATTERN = re.compile(
    r"\b(conclusao|premissa|exemplo)\s*:",
    re.IGNORECASE,
)


def detect_andaime_copiado(text: str) -> bool:
    """True se o texto reescrito contém 'Conclusão:', 'Premissa:' ou
    'Exemplo:' como rótulos de seção (sinaliza que o aluno copiou o andaime
    em vez de reescrever em prosa contínua)."""
    norm = _normalize(text)
    return bool(_ANDAIME_PATTERN.search(norm))


# ──────────────────────────────────────────────────────────────────────
# Modo Foco C4 (OF11)
# ──────────────────────────────────────────────────────────────────────

# Conectivos de uso comum em redação argumentativa de aluno do EM.
# Lista propositalmente CURTA — só palavras-chave inequívocas.
_CONECTIVOS_TRACKED = [
    "alem disso",
    "ademais",
    "outrossim",
    "destarte",
    "portanto",
    "logo",
    "assim",
    "no entanto",
    "porem",
    "todavia",
    "contudo",
    "entretanto",
    "ja que",
    "porque",
    "pois",
    "uma vez que",
]


def detect_conectivo_repetido(text: str) -> bool:
    """True se algum conectivo da lista aparece 3+ vezes."""
    norm = _normalize(text)
    for conn in _CONECTIVOS_TRACKED:
        # boundary simples: precedido por início/espaço/pontuação, seguido por espaço.
        pattern = r"(?:^|[\s\.,;:!?])" + re.escape(conn) + r"(?=[\s\.,;:!?])"
        if len(re.findall(pattern, norm)) >= 3:
            return True
    return False


_PALAVRA_DIA_TERMS = ("premissa", "mitigar", "exacerbar")


def palavra_dia_presente(text: str) -> List[str]:
    """Retorna quais Palavras do Dia aparecem no texto.

    Usada como hint pro LLM avaliar uso correto. Não decide sozinho — só
    informa a presença.
    """
    norm = _normalize(text)
    return [p for p in _PALAVRA_DIA_TERMS if re.search(rf"\b{p}\w*\b", norm)]


# ──────────────────────────────────────────────────────────────────────
# Modo Foco C5 (OF12)
# ──────────────────────────────────────────────────────────────────────

_AGENTE_GENERICO_PATTERNS = [
    r"\bo governo\b",
    r"\ba sociedade\b",
    r"\bas pessoas\b",
    r"\bas autoridades\b",
    r"\bos orgaos\b",
]
_AGENTE_GENERICO_RE = re.compile("|".join(_AGENTE_GENERICO_PATTERNS), re.IGNORECASE)
_AGENTE_INSTITUCIONAL_PATTERNS = [
    # Heurística: presença de sigla institucional ou ministério explícito.
    r"\b(MEC|MS|STF|TSE|MP|MPF|MPT|ANS|ANVISA|IBGE|IBAMA|ANATEL|ANAC)\b",
    r"\bministerio (da|do|de) ",
    r"\bsecretaria (da|do|de) ",
    r"\bcamara (dos|de) ",
    r"\bsenado\b",
    r"\bcongresso nacional\b",
]
_AGENTE_INSTITUCIONAL_RE = re.compile(
    "|".join(_AGENTE_INSTITUCIONAL_PATTERNS), re.IGNORECASE
)


def detect_agente_generico(text: str) -> bool:
    """True se o texto cita agente genérico **e não** cita agente institucional
    nomeado.

    A combinação ("o governo" presente, mas nenhum órgão nomeado) é o caso
    crítico. "O governo, por meio do MEC" não dispara — porque há o MEC.
    """
    if not _AGENTE_GENERICO_RE.search(text):
        return False
    if _AGENTE_INSTITUCIONAL_RE.search(text):
        return False
    return True


_VERBO_FRACO_PATTERNS = [
    # "fazer" + objeto típico de proposta
    r"\b(fazer|faz|fazem|faca|facam)\s+(algo|alguma coisa|isso|com que)\b",
    # "ter" como verbo principal de ação
    r"\b(ter|tem|tera|terao|tenha|tenham)\s+(que|de|um|uma|mais)\s+\w+",
    # "ser" auxiliar fraco em ação
    r"\b(ser|sera|serao|seja|sejam)\s+(necessario|preciso|importante|fundamental)\b",
]
_VERBO_FRACO_RE = re.compile("|".join(_VERBO_FRACO_PATTERNS), re.IGNORECASE)


def detect_verbo_fraco(text: str) -> bool:
    """True se o texto usa fazer/ter/ser em construções típicas de proposta
    fraca ('é necessário fazer algo', 'tem que ter mais X')."""
    norm = _normalize(text)
    return bool(_VERBO_FRACO_RE.search(norm))


_PROPOSTA_CONSTATATORIA_HINTS = [
    r"\be preciso que\b",
    r"\be necessario que\b",
    r"\bdeve-se\b",
    r"\bdevemos\b",
    r"\bdeve\s+haver\b",
    r"\btem que ser feito\b",
    r"\balgo deve ser feito\b",
]
_PROPOSTA_CONSTATATORIA_RE = re.compile(
    "|".join(_PROPOSTA_CONSTATATORIA_HINTS), re.IGNORECASE
)


def detect_proposta_vaga_constatatoria_hint(text: str) -> bool:
    """Hint pro LLM: presença de fórmulas constatatórias típicas. Não cap
    sozinho — o LLM ainda precisa avaliar se a proposta como um todo é
    apenas constatatória."""
    norm = _normalize(text)
    return bool(_PROPOSTA_CONSTATATORIA_RE.search(norm))


# ──────────────────────────────────────────────────────────────────────
# Modo Completo Parcial (OF13)
# ──────────────────────────────────────────────────────────────────────

def detect_topico_e_pergunta(text: str) -> bool:
    """True se a primeira frase do parágrafo termina em '?' (tópico frasal
    é interrogativo)."""
    if not text:
        return False
    # Pega 1ª frase: até primeiro . ! ? ou fim do texto.
    m = re.match(r"\s*([^.!?]*[.!?])", text)
    if not m:
        # Sem pontuação final — usa o texto inteiro pro check.
        first = text.strip()
    else:
        first = m.group(1).strip()
    return first.endswith("?")


# ──────────────────────────────────────────────────────────────────────
# Dispatcher
# ──────────────────────────────────────────────────────────────────────

def compute_pre_flags(mode: str, text: str) -> Dict[str, bool]:
    """Computa pre-flags Python pra um modo. Retorna dict só com as flags
    que essa missão suporta (subset do schema flags)."""
    out: Dict[str, bool] = {}
    if mode == "foco_c3":
        out["andaime_copiado"] = detect_andaime_copiado(text)
    elif mode == "foco_c4":
        out["conectivo_repetido"] = detect_conectivo_repetido(text)
    elif mode == "foco_c5":
        out["agente_generico"] = detect_agente_generico(text)
        out["verbo_fraco"] = detect_verbo_fraco(text)
        out["proposta_vaga_constatatoria_hint"] = (
            detect_proposta_vaga_constatatoria_hint(text)
        )
    elif mode == "completo_parcial":
        out["topico_e_pergunta"] = detect_topico_e_pergunta(text)
    return out


def render_pre_flags_block(mode: str, flags: Dict[str, bool]) -> str:
    """Formata pre-flags como bloco markdown pra injetar no user_msg.

    Quando todas as flags são False, retorna string vazia — não polui o
    contexto com 'sem detecções'.
    """
    actives = {k: v for k, v in flags.items() if v}
    if not actives:
        return ""
    lines = [
        "",
        "### Pre-flags do detector Python (advisory — você decide a flag final)",
        "",
    ]
    for k, _ in actives.items():
        lines.append(f"- `{k}`: detector Python disparou. Avalie e confirme/discorde "
                     f"na flag correspondente do schema.")
    lines.append("")
    return "\n".join(lines)
