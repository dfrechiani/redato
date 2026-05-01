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

import logging
from typing import Any, Dict, List, Optional, Tuple

from redato_backend.missions.discretize import discretiza_score


# Logger pros pontos de quebra no render. Bug do 01/05 (FT migration):
# OF14 caía no fallback "Não consegui formatar" porque dispatch exigia
# `essay_analysis` que o FT não retorna. Sem log, debug em prod era
# adivinhação.
logger = logging.getLogger(__name__)


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


def _render_jogo_redacao(args: Dict[str, Any],
                          transcript: Optional[str]) -> str:
    """Renderiza feedback do modo jogo_redacao (Fase 2 passo 5).

    Diferenças vs `_render_completo_parcial`:
    - 5 competências (não só C1-C4)
    - Total 0-1000 (não 0-800)
    - Badge separado pra `transformacao_cartas` (decisão G.1.6 —
      visualmente fora do bloco de nota ENEM)
    - Lista de sugestões de cartas alternativas se houver (até 2)
    - SEM bloco de transcrição (reescrita é texto digitado, não foto)
    """
    notas = args.get("notas_enem") or {}
    total = int(args.get("nota_total_enem", 0) or 0)
    faixa = _faixa_total_1000(total)
    transformacao = int(args.get("transformacao_cartas", 0) or 0)
    sugestoes = args.get("sugestoes_cartas_alternativas") or []
    fa = args.get("feedback_aluno") or {}
    acertos = list(fa.get("acertos") or [])[:2]
    ajustes = list(fa.get("ajustes") or [])[:2]

    # Linha inline com 5 notas — exemplo "C1 160 · C2 160 · C3 120 · C4 120 · C5 80"
    notas_inline = " · ".join(
        f"{k.upper()} {int(notas.get(k, 0) or 0)}"
        for k in ("c1", "c2", "c3", "c4", "c5")
    )

    parts: List[str] = []
    # transcrição: reescrita é texto, não OCR — não mostra bloco

    parts.append(f"📊 *Reescrita avaliada* — {faixa} ({total}/1000)")
    parts.append(f"_{notas_inline}_\n")

    # Badge separado de transformacao_cartas (decisão G.1.6)
    parts.append(_render_transformacao_badge(transformacao))
    parts.append("")

    if acertos:
        parts.append("*O que ficou bom:*")
        parts.extend(_bullets(acertos))
        parts.append("")
    if ajustes:
        parts.append("*Pra trabalhar:*")
        parts.extend(_bullets(ajustes))
        parts.append("")

    if sugestoes:
        parts.append("*Cartas alternativas que valem testar:*")
        for s in sugestoes[:2]:
            if not isinstance(s, dict):
                continue
            cod_ori = s.get("codigo_original", "?")
            cod_sug = s.get("codigo_sugerido", "?")
            motivo = (s.get("motivo") or "").strip()
            motivo_short = _truncate(motivo, _MAX_BULLET_CHARS)
            parts.append(f"- {cod_ori} → {cod_sug}: {motivo_short}")
        parts.append("")

    return "\n".join(parts).rstrip()


def _render_transformacao_badge(score: int) -> str:
    """Badge visual pra `transformacao_cartas` (0-100). Decisão G.1.6:
    score independente da nota ENEM — visualmente separado."""
    if score >= 91:
        emoji, label = "🏆", "autoria plena"
    elif score >= 71:
        emoji, label = "🎯", "autoria substancial"
    elif score >= 41:
        emoji, label = "🔄", "paráfrase com algum recorte"
    elif score >= 16:
        emoji, label = "📋", "esqueleto reconhecível"
    else:
        emoji, label = "⚠️", "cópia das cartas"
    return f"{emoji} *Transformação das cartas:* {score}/100 — _{label}_"


# ──────────────────────────────────────────────────────────────────────
# OF14 (modo completo_integral) — renderizador
# ──────────────────────────────────────────────────────────────────────
#
# 2 schemas suportados:
#
# A. Schema FT (default desde 30/04 — commit feat(of14) 8554146):
#    {
#      "c1_audit": {"nota": int, "feedback_text": str,
#                   "evidencias": [{"trecho": str, "comentario": str}]},
#      "c2_audit": {...}, ..., "c5_audit": {...}
#    }
#    Sem `feedback_text` top-level, sem `essay_analysis`,
#    sem `priorization`, sem `flags`. Cada cN_audit traz seu
#    próprio feedback + evidências.
#
# B. Schema v2 legado (fallback Claude — REDATO_OF14_BACKEND=claude):
#    cN_audit com 12+ campos (desvios_gramaticais, threshold_check,
#    marcas_oralidade, etc.) + `feedback_text` top-level + outros.
#    Renderizador NÃO acessa esses campos extras — só `nota` e o
#    eventual `feedback_text` top-level.
#
# Estratégia: ambos schemas têm `cN_audit.nota`. Renderizador prefere
# `cN_audit.feedback_text` (FT) e cai em `args["feedback_text"]` solto
# (v2) se o por-competência não vier.

# Limite mais generoso pra OF14 — 5 competências × ~400 chars cada ainda
# cabe nos 1600 chars/chunk do Twilio com chunking de bot.py.
_OF14_MAX_CHARS = 2800
_OF14_FB_CHARS = 200          # feedback_text resumido por competência
_OF14_TRECHO_CHARS = 80       # citação literal
_OF14_COMENT_CHARS = 100      # comentário sobre o trecho
_OF14_EVID_PER_COMP = 2       # até 2 evidências por competência


def _is_completo_integral(args: Dict[str, Any]) -> bool:
    """Detecta payload OF14 sem depender de `modo` (FT não preenche
    esse campo) nem de `essay_analysis` (FT não retorna). Critério:
    ao menos 3 das 5 chaves cN_audit presentes como dicts com `nota`.
    """
    if not isinstance(args, dict):
        return False
    audits_validos = sum(
        1 for c in ("c1_audit", "c2_audit", "c3_audit", "c4_audit", "c5_audit")
        if isinstance(args.get(c), dict)
        and isinstance(args[c].get("nota"), (int, float))
    )
    return audits_validos >= 3


def _of14_nota(args: Dict[str, Any], chave: str) -> Optional[int]:
    """Lê `cN_audit.nota` defensivamente. Retorna None se ausente
    ou tipo errado — caller renderiza 'dados incompletos'."""
    bloco = args.get(chave)
    if not isinstance(bloco, dict):
        return None
    nota = bloco.get("nota")
    if isinstance(nota, (int, float)):
        return int(nota)
    return None


def _of14_feedback(args: Dict[str, Any], chave: str) -> str:
    """Pega `cN_audit.feedback_text` (schema FT). Fallback pra
    `args["feedback_text"]` top-level (schema v2) só se ausente."""
    bloco = args.get(chave)
    if isinstance(bloco, dict):
        fb = bloco.get("feedback_text")
        if isinstance(fb, str) and fb.strip():
            return fb.strip()
    return ""


def _of14_evidencias(args: Dict[str, Any], chave: str) -> List[Tuple[str, str]]:
    """Lista de (trecho, comentário) de `cN_audit.evidencias`. Tolera
    formato inesperado (não é lista, item não é dict) — retorna []."""
    bloco = args.get(chave)
    if not isinstance(bloco, dict):
        return []
    evs = bloco.get("evidencias")
    if not isinstance(evs, list):
        return []
    out: List[Tuple[str, str]] = []
    for ev in evs:
        if not isinstance(ev, dict):
            continue
        trecho = str(ev.get("trecho") or "").strip()
        coment = str(ev.get("comentario") or "").strip()
        if trecho or coment:
            out.append((trecho, coment))
    return out


def _of14_bloco_competencia(
    label: str, nota: Optional[int], feedback: str,
    evidencias: List[Tuple[str, str]],
) -> str:
    """Renderiza 1 competência (~400 chars).

    `nota=None` → "*C{N}*: dados incompletos" (não derruba o render
    inteiro se schema veio quebrado em 1-2 competências).
    """
    if nota is None:
        return f"*{label}*: _dados incompletos_"

    linhas = [f"*{label} — {nota}* {_faixa_inep(nota)}"]
    if feedback:
        linhas.append(_truncate(feedback, _OF14_FB_CHARS))
    for trecho, coment in evidencias[:_OF14_EVID_PER_COMP]:
        trecho_curto = _truncate(trecho, _OF14_TRECHO_CHARS)
        coment_curto = _truncate(coment, _OF14_COMENT_CHARS)
        if trecho_curto and coment_curto:
            linhas.append(f"- _\"{trecho_curto}\"_ → {coment_curto}")
        elif trecho_curto:
            linhas.append(f"- _\"{trecho_curto}\"_")
        elif coment_curto:
            linhas.append(f"- {coment_curto}")
    return "\n".join(linhas)


def _render_completo_integral(args: Dict[str, Any],
                                transcript: Optional[str]) -> str:
    """Render OF14 robusto pros 2 schemas (FT subset + v2 legado).

    Layout:
      📊 *Redação completa* — {faixa} ({total}/1000)
      _C1 {n1} · C2 {n2} · ... · C5 {n5}_

      *C1 — {n1}* {faixa_qual}
      {feedback resumido}
      - "{trecho}" → {comentário}

      *C2 — {n2}* ...
      ...
    """
    logger.info(
        "rendering OF14: keys=%s, has_evidencias_c1=%s",
        sorted(args.keys()) if isinstance(args, dict) else type(args).__name__,
        bool((args.get("c1_audit") or {}).get("evidencias"))
            if isinstance(args, dict) else False,
    )

    competencias = ("c1_audit", "c2_audit", "c3_audit", "c4_audit", "c5_audit")
    notas: Dict[str, Optional[int]] = {
        c: _of14_nota(args, c) for c in competencias
    }
    notas_int: List[int] = [n for n in notas.values() if n is not None]

    # Total = soma das notas presentes (zera as ausentes pra não
    # confundir aluno; faixa qualitativa cita só o número final).
    total_explicito = args.get("nota_total")
    if isinstance(total_explicito, (int, float)):
        total = int(total_explicito)
    else:
        total = sum(notas_int)
    faixa = _faixa_total_1000(total)

    notas_inline_partes: List[str] = []
    for idx, c in enumerate(competencias, 1):
        n = notas[c]
        notas_inline_partes.append(
            f"C{idx} {n}" if n is not None else f"C{idx} —"
        )
    notas_inline = " · ".join(notas_inline_partes)

    parts: List[str] = []
    if transcript:
        parts.append(_bloco_transcricao(transcript))
    parts.append(f"📊 *Redação completa* — {faixa} ({total}/1000)")
    parts.append(f"_{notas_inline}_")

    # Por-competência: mostra se temos pelo menos `nota` ou `feedback`
    blocos: List[str] = []
    for idx, c in enumerate(competencias, 1):
        nota = notas[c]
        feedback = _of14_feedback(args, c)
        evidencias = _of14_evidencias(args, c)
        if nota is None and not feedback and not evidencias:
            # cN_audit ausente totalmente — pula em vez de poluir
            continue
        blocos.append(
            _of14_bloco_competencia(
                f"C{idx}", nota, feedback, evidencias,
            )
        )

    # Fallback v2: se NENHUM cN_audit.feedback_text veio, usa
    # `feedback_text` solto top-level (schema v2 legado de Sonnet).
    sem_fb_por_comp = not any(
        _of14_feedback(args, c) for c in competencias
    )
    fb_top = (args.get("feedback_text") or "").strip() if isinstance(args, dict) else ""
    if sem_fb_por_comp and fb_top:
        # Coloca após o cabeçalho, antes dos blocos por competência
        parts.append("")
        parts.append(_truncate(fb_top, 400))

    # Junta blocos respeitando budget. Se estourar, trunca o último.
    if blocos:
        parts.append("")  # linha em branco antes
        consumido = sum(len(p) + 1 for p in parts)
        for bloco in blocos:
            tamanho_provavel = consumido + len(bloco) + 2
            if tamanho_provavel > _OF14_MAX_CHARS:
                # Não cabe — tenta versão minimalista (só nota)
                # ou pula. Pega primeira linha do bloco que é o header.
                primeiro_linha = bloco.split("\n", 1)[0]
                if consumido + len(primeiro_linha) + 2 <= _OF14_MAX_CHARS:
                    parts.append(primeiro_linha)
                    consumido += len(primeiro_linha) + 2
                continue
            parts.append(bloco)
            parts.append("")  # separador entre competências
            consumido = tamanho_provavel + 1

    return "\n".join(parts).rstrip()


def render_aluno_whatsapp(
    args: Dict[str, Any], texto_transcrito: Optional[str] = None,
) -> str:
    """Entry point. Dispatch por `modo` no tool_args.

    `texto_transcrito` é injetado no topo da mensagem como bloco
    "Texto identificado" pra o aluno conferir o que o OCR leu.
    """
    if not isinstance(args, dict):
        return "Algo deu errado na avaliação. Tenta mandar a foto de novo."

    try:
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
        elif mode == "jogo_redacao":
            # Fase 2 passo 5 — reescrita individual do jogo de redação.
            # Não passa transcrição (reescrita é texto digitado).
            out = _render_jogo_redacao(args, None)
        elif _is_completo_integral(args):
            # Detecta OF14 sem depender de `modo` (FT não preenche)
            # nem de `essay_analysis` (FT não retorna). Cobre
            # ambos schemas: FT subset + v2 legado.
            out = _render_completo_integral(args, texto_transcrito)
        else:
            logger.warning(
                "render fallback: modo desconhecido. mode=%r, keys=%s",
                mode,
                sorted(args.keys()) if isinstance(args, dict) else "—",
            )
            out = "Avaliação concluída. (Não consegui formatar o resumo.)"
    except Exception:  # noqa: BLE001
        # Defensa em profundidade: KeyError/AttributeError/TypeError em
        # qualquer renderer não pode resultar em 500 silencioso. Loga
        # com stack pro Railway, retorna fallback amigável pro aluno.
        logger.exception(
            "render_aluno_whatsapp failed. mode=%r, keys=%s",
            args.get("modo") if isinstance(args, dict) else "—",
            sorted(args.keys()) if isinstance(args, dict) else "—",
        )
        return "Avaliação concluída. (Não consegui formatar o resumo.)"

    # OF14 tem cap próprio (mensagem mais longa por design); demais
    # modos seguem _MAX_CHARS=1200.
    cap = _OF14_MAX_CHARS if _is_completo_integral(args) else _MAX_CHARS
    if len(out) > cap:
        out = _truncate(out, cap)
    return out
