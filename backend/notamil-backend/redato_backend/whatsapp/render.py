"""Renderizador WhatsApp pro aluno — converte tool_args do router em
mensagem curta (≤800 chars) com formatação WhatsApp.

Estrutura da mensagem (2026-04-27):
1. Bloco de transcrição (~80 chars + instrução "ocr errado")
2. Bloco de status (modo + faixa + nota total)
3. Bloco "Por critério" (faixa qualitativa por critério, pior com ⚠️)
4. Bloco de feedback (acertos + ajustes)

Formatação WhatsApp:
- *negrito* (single asterisk)
- _itálico_ (single underscore)
- Listas: linhas começando com `-`
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from redato_backend.missions.discretize import discretiza_score


_MAX_CHARS = 1200          # cap WhatsApp pra leitura confortável em mobile
_MAX_BULLET_CHARS = 350    # cabe frase completa de 1-2 ideias
_TRANSCRIPT_CHARS = 80     # primeiros chars do OCR


# Faixa qualitativa por nota INEP (escala 0-200). Tom formal,
# alinhado com terminologia pedagógica neutra.
def _faixa_inep(nota: int) -> str:
    if nota >= 200:
        return "excelente"
    if nota >= 160:
        return "muito boa"
    if nota >= 120:
        return "regular"
    if nota >= 80:
        return "em desenvolvimento"
    if nota >= 40:
        return "insuficiente"
    return "abaixo do esperado"


# Faixa qualitativa total (Modo Completo Integral 0-1000)
def _faixa_total_1000(total: int) -> str:
    if total >= 901:
        return "excelente"
    if total >= 801:
        return "muito boa"
    if total >= 601:
        return "regular"
    if total >= 401:
        return "em desenvolvimento"
    return "insuficiente"


# Faixa qualitativa parcial (OF13, escala 0-800 — sem C5)
def _faixa_total_800(total: int) -> str:
    if total >= 720:
        return "excelente"
    if total >= 640:
        return "muito boa"
    if total >= 480:
        return "regular"
    if total >= 320:
        return "em desenvolvimento"
    return "insuficiente"


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    cut = text[: limit - 1].rstrip()
    if " " in cut[-30:]:
        cut = cut.rsplit(" ", 1)[0]
    return cut + "…"


def _bullets(items: List[str], limit_each: int = _MAX_BULLET_CHARS) -> List[str]:
    out: List[str] = []
    for it in items:
        s = (it or "").strip()
        if not s:
            continue
        out.append("- " + _truncate(s, limit_each))
    return out


# ──────────────────────────────────────────────────────────────────────
# Bloco transcrição
# ──────────────────────────────────────────────────────────────────────

def _bloco_transcricao(texto_transcrito: Optional[str]) -> str:
    """Retorna bloco de transcrição (≤170 chars) ou string vazia."""
    if not texto_transcrito:
        return ""
    snippet = texto_transcrito.strip().split("\n")[0]  # 1ª linha
    snippet = _truncate(snippet, _TRANSCRIPT_CHARS)
    return (
        f"📝 *Texto identificado:*\n"
        f"\"{snippet}\"\n\n"
        f"_Se a Redato leu errado, escreva *ocr errado* e mande a foto "
        f"de novo._\n"
        f"\n────\n\n"
    )


# ──────────────────────────────────────────────────────────────────────
# Bloco "Por critério" com faixas qualitativas
# ──────────────────────────────────────────────────────────────────────

# Mapeamento de chave técnica → label legível ao aluno
_CRITERIO_LABEL = {
    # foco_c2 (RJ2·OF04·MF, RJ2·OF06·MF — M9.2)
    "compreensao_tema": "Compreensão do tema",
    "tipo_textual": "Tipo textual",
    # foco_c3 (OF10) — Conclusão / Premissa / Exemplo / Fluência
    "conclusao": "Conclusão",
    "premissa": "Premissa",
    "exemplo": "Exemplo",
    "fluencia": "Fluência",
    # foco_c4 (OF11) — Estrutura / Conectivos / Cadeia / Palavra do Dia
    "estrutura": "Estrutura",
    "conectivos": "Conectivos",
    "cadeia_logica": "Cadeia lógica",
    "palavra_dia": "Palavra do Dia",
    # foco_c5 (OF12) — 6 critérios da proposta
    "agente": "Agente",
    "acao_verbo": "Ação e verbo",
    "meio": "Meio",
    "finalidade": "Finalidade",
    "detalhamento": "Detalhamento",
    "direitos_humanos": "Direitos humanos",
    # completo_parcial (OF13) — Tópico / Argumento / Repertório / Coesão
    "topico_frasal": "Tópico frasal",
    "argumento": "Argumento",
    "repertorio": "Repertório",
    "coesao": "Coesão",
}

_BANDA_RANK = {"insuficiente": 0, "adequado": 1, "excelente": 2}


def _bloco_por_criterio(rubrica: Dict[str, Any]) -> str:
    """Lista cada critério com faixa qualitativa. Marca pior com ⚠️.
    Retorna string vazia se rubrica vazia ou inválida.
    """
    if not rubrica:
        return ""

    items: List[Tuple[str, str, str]] = []  # (key, label, faixa)
    pior_rank = 99
    pior_idx = -1
    for k, v in rubrica.items():
        if not isinstance(v, (int, float)):
            continue
        label = _CRITERIO_LABEL.get(k, k)
        faixa = discretiza_score(int(v))
        rank = _BANDA_RANK.get(faixa, 99)
        if rank < pior_rank:
            pior_rank = rank
            pior_idx = len(items)
        items.append((k, label, faixa))

    if not items:
        return ""

    lines = ["📊 *Por critério:*"]
    for i, (k, label, faixa) in enumerate(items):
        marker = " ⚠️" if i == pior_idx else ""
        lines.append(f"- {label}: {faixa}{marker}")
    lines.append("")
    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────
# Renderers por modo
# ──────────────────────────────────────────────────────────────────────

def _render_foco(args: Dict[str, Any], comp: str,
                 transcript: Optional[str]) -> str:
    nota_key = f"nota_{comp}_enem"
    nota = int(args.get(nota_key, 0) or 0)
    faixa = _faixa_inep(nota)
    fa = args.get("feedback_aluno") or {}
    acertos = list(fa.get("acertos") or [])[:2]
    ajustes = list(fa.get("ajustes") or [])[:2]
    rubrica = args.get("rubrica_rej") or {}

    parts: List[str] = []
    if transcript:
        parts.append(_bloco_transcricao(transcript))
    parts.append(f"📊 *{comp.upper()}* — {faixa} ({nota}/200)\n")
    bloco_crit = _bloco_por_criterio(rubrica)
    if bloco_crit:
        parts.append(bloco_crit)
    if acertos:
        parts.append("*O que ficou bom:*")
        parts.extend(_bullets(acertos))
        parts.append("")
    if ajustes:
        parts.append("*Pra trabalhar:*")
        parts.extend(_bullets(ajustes))
    return "\n".join(parts)


def _render_completo_parcial(args: Dict[str, Any],
                              transcript: Optional[str]) -> str:
    notas = args.get("notas_enem") or {}
    total = int(args.get("nota_total_parcial", 0) or 0)
    faixa = _faixa_total_800(total)
    fa = args.get("feedback_aluno") or {}
    acertos = list(fa.get("acertos") or [])[:1]
    ajustes = list(fa.get("ajustes") or [])[:2]
    rubrica = args.get("rubrica_rej") or {}

    notas_inline = " · ".join(
        f"{k.upper()} {notas.get(k, 0)}" for k in ("c1", "c2", "c3", "c4")
    )
    parts: List[str] = []
    if transcript:
        parts.append(_bloco_transcricao(transcript))
    parts.append(f"📊 *Correção completa parcial* — {faixa} ({total}/800)")
    parts.append(f"_{notas_inline}_")
    parts.append("_C5 não se aplica em parágrafo único_\n")
    bloco_crit = _bloco_por_criterio(rubrica)
    if bloco_crit:
        parts.append(bloco_crit)
    if acertos:
        parts.append("*O que ficou bom:*")
        parts.extend(_bullets(acertos))
        parts.append("")
    if ajustes:
        parts.append("*Pra trabalhar:*")
        parts.extend(_bullets(ajustes))
    return "\n".join(parts)


def _render_completo_integral(args: Dict[str, Any],
                                transcript: Optional[str]) -> str:
    c1 = (args.get("c1_audit") or {}).get("nota") or 0
    c2 = (args.get("c2_audit") or {}).get("nota") or 0
    c3 = (args.get("c3_audit") or {}).get("nota") or 0
    c4 = (args.get("c4_audit") or {}).get("nota") or 0
    c5 = (args.get("c5_audit") or {}).get("nota") or 0
    total = c1 + c2 + c3 + c4 + c5
    faixa = _faixa_total_1000(total)
    feedback = (args.get("feedback_text") or "").strip()

    notas_inline = (
        f"C1 {c1} · C2 {c2} · C3 {c3} · C4 {c4} · C5 {c5}"
    )
    parts: List[str] = []
    if transcript:
        parts.append(_bloco_transcricao(transcript))
    parts.append(f"📊 *Redação completa* — {faixa} ({total}/1000)")
    parts.append(f"_{notas_inline}_")
    if feedback:
        parts.append("")
        budget = _MAX_CHARS - sum(len(p) + 1 for p in parts) - 4
        if budget > 80:
            parts.append(_truncate(feedback, budget))
    return "\n".join(parts)


def render_aluno_whatsapp(
    args: Dict[str, Any], texto_transcrito: Optional[str] = None,
) -> str:
    """Entry point. Dispatch por `modo` no tool_args.

    `texto_transcrito` é injetado no topo da mensagem como bloco
    "Texto identificado" pra o aluno conferir o que o OCR leu.
    """
    if not isinstance(args, dict):
        return "Algo deu errado na avaliação. Tenta mandar a foto de novo."

    mode = args.get("modo")
    if mode == "foco_c2":
        # M9.2 (2026-04-29) — RJ2·OF04·MF e RJ2·OF06·MF.
        # Reusa _render_foco genérico: nota_c2_enem (0-200) + rubrica
        # de 3 critérios (compreensao_tema, tipo_textual, repertorio).
        out = _render_foco(args, "c2", texto_transcrito)
    elif mode == "foco_c3":
        out = _render_foco(args, "c3", texto_transcrito)
    elif mode == "foco_c4":
        out = _render_foco(args, "c4", texto_transcrito)
    elif mode == "foco_c5":
        out = _render_foco(args, "c5", texto_transcrito)
    elif mode == "completo_parcial":
        out = _render_completo_parcial(args, texto_transcrito)
    elif "essay_analysis" in args:
        out = _render_completo_integral(args, texto_transcrito)
    else:
        out = "Avaliação concluída. (Não consegui formatar o resumo.)"

    if len(out) > _MAX_CHARS:
        out = _truncate(out, _MAX_CHARS)
    return out
