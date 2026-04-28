"""Override determinístico da nota ENEM por modo (FIX 3 — 2026-04-27).

Contexto: o LLM oscila na tradução rubrica REJ → nota ENEM final mesmo
com scores 0-100 consistentes. Caso real: 3 runs com rubrica idêntica
(scores médios ~40, banda 'insuficiente') geraram notas 80/40/80,
porque a heurística no prompt não é respeitada estritamente.

Fix: a tradução final é Python puro, baseada na média dos scores +
caps semânticos das flags. O LLM continua emitindo `nota_cN_enem`,
mas o `router` sobrescreve esse campo com o valor calculado.

Cada função:
- recebe `rubrica` (dict criterio → score 0-100) + `flags` (dict bool)
- retorna nota ENEM discreta (0/40/80/120/160/200)
- aplica caps cirúrgicos da spec REJ 1S na ordem documentada

Tabela média → ENEM (idêntica em todos os modos foco/parcial):
   média 0-29   → 0
   média 30-49  → 40
   média 50-64  → 80
   média 65-79  → 120
   média 80-89  → 160
   média 90-100 → 200

Spec dos caps: docs/redato/v3/redato_1S_criterios.md.
"""
from __future__ import annotations
from typing import Any, Dict


def _media(rubrica: Dict[str, Any]) -> float:
    nums = [int(v) for v in rubrica.values()
            if isinstance(v, (int, float)) and v is not None]
    return sum(nums) / len(nums) if nums else 0.0


def media_to_inep(media: float) -> int:
    """Heurística determinística: média de scores 0-100 → nota INEP discreta."""
    if media < 30:
        return 0
    if media < 50:
        return 40
    if media < 65:
        return 80
    if media < 80:
        return 120
    if media < 90:
        return 160
    return 200


# ──────────────────────────────────────────────────────────────────────
# Foco C2 (RJ2·OF04·MF, RJ2·OF06·MF) — M9.1
# ──────────────────────────────────────────────────────────────────────

def rej_to_c2_score(rubrica: Dict[str, int], flags: Dict[str, bool]) -> int:
    """Foco C2 0-200. Caps semânticos sobrescrevem a média.

    Decisão Daniel 2026-04-28 (G.4): defesa em profundidade. O tool
    emite a flag e tenta respeitar o cap declarado em description; o
    Python aplica `min` aqui pra garantir. Idempotente — se o LLM já
    capou, `min` preserva.

    Hierarquia (em ordem, primeiro flag positivo no escopo manda):
    1. fuga_tema → 0 (anula a redação inteira; rubrica oficial INEP)
    2. tipo_textual_inadequado → 0 (anula; rubrica oficial)
    3. tangenciamento_tema → ≤ 80 (cap rígido — Cartilha)
    4. repertorio_de_bolso → ≤ 120 (cap suave — repertório legitimado
       mas não pertinente, rubrica v2 nota 3)
    5. copia_motivadores_recorrente → ≤ 160 (cap suave — produção
       autoral comprometida; nota 4 mas não 5)
    6. Senão, base = média(rubrica) traduzida pra ENEM
    """
    if flags.get("fuga_tema"):
        return 0
    if flags.get("tipo_textual_inadequado"):
        return 0
    base = media_to_inep(_media(rubrica))
    if flags.get("tangenciamento_tema"):
        base = min(base, 80)
    if flags.get("repertorio_de_bolso"):
        base = min(base, 120)
    if flags.get("copia_motivadores_recorrente"):
        base = min(base, 160)
    return base


# ──────────────────────────────────────────────────────────────────────
# Foco C3 (OF10)
# ──────────────────────────────────────────────────────────────────────

def rej_to_c3_score(rubrica: Dict[str, int], flags: Dict[str, bool]) -> int:
    """Foco C3 0-200. Caps por flag negativa.

    Hierarquia:
    1. base = média(rubrica) traduzida pra ENEM
    2. tese_generica → ≤ 120 (spec OF10 caso 4)
    3. andaime_copiado → ≤ 120 (spec OF10 caso 1)
    4. exemplo_redundante → ≤ 160 (cap suave)
    """
    base = media_to_inep(_media(rubrica))
    if flags.get("tese_generica"):
        base = min(base, 120)
    if flags.get("andaime_copiado"):
        base = min(base, 120)
    if flags.get("exemplo_redundante"):
        base = min(base, 160)
    return base


# ──────────────────────────────────────────────────────────────────────
# Foco C4 (OF11)
# ──────────────────────────────────────────────────────────────────────

def rej_to_c4_score(rubrica: Dict[str, int], flags: Dict[str, bool]) -> int:
    """Foco C4 0-200. Caps por flag de conectivo/cadeia.

    Hierarquia:
    1. base = média(rubrica) traduzida pra ENEM
    2. conectivo_relacao_errada → ≤ 120 (mais grave que ausência)
    3. salto_logico → ≤ 120 (cadeia incompleta)
    4. palavra_dia_uso_errado → ≤ 160 (cap suave)
    5. conectivo_repetido → ≤ 160 (cap suave)
    """
    base = media_to_inep(_media(rubrica))
    if flags.get("conectivo_relacao_errada"):
        base = min(base, 120)
    if flags.get("salto_logico"):
        base = min(base, 120)
    if flags.get("palavra_dia_uso_errado"):
        base = min(base, 160)
    if flags.get("conectivo_repetido"):
        base = min(base, 160)
    return base


# ──────────────────────────────────────────────────────────────────────
# Foco C5 (OF12) — caps semânticos sobrescrevem a média
# ──────────────────────────────────────────────────────────────────────

def rej_to_c5_score(rubrica: Dict[str, int], flags: Dict[str, bool],
                    articulacao: str = "clara") -> int:
    """Foco C5 0-200. Cartilha INEP é primária — caps semânticos
    sobrescrevem qualquer média.

    Hierarquia (em ordem):
    1. desrespeito_direitos_humanos → 0 (Cartilha)
    2. proposta_vaga_constatatoria → ≤ 40
    3. articulacao == 'ausente' → ≤ 40
    4. proposta_desarticulada → ≤ 80
    5. articulacao == 'fragil' → ≤ 80
    6. agente_generico → ≤ 120
    7. verbo_fraco → ≤ 160 (mais leve)
    8. Senão, base = média(rubrica)
    """
    if flags.get("desrespeito_direitos_humanos"):
        return 0
    base = media_to_inep(_media(rubrica))
    if flags.get("proposta_vaga_constatatoria"):
        base = min(base, 40)
    if articulacao == "ausente":
        base = min(base, 40)
    if flags.get("proposta_desarticulada"):
        base = min(base, 80)
    if articulacao == "fragil":
        base = min(base, 80)
    if flags.get("agente_generico"):
        base = min(base, 120)
    if flags.get("verbo_fraco"):
        base = min(base, 160)
    return base


# ──────────────────────────────────────────────────────────────────────
# Completo Parcial (OF13) — 4 competências derivadas da rubrica
# ──────────────────────────────────────────────────────────────────────

def rej_to_partial_scores(
    rubrica: Dict[str, int], flags: Dict[str, bool], llm_c1: int,
) -> Dict[str, int]:
    """OF13. Mapeia 4 critérios REJ pra C2/C3/C4 ENEM. C1 vem do LLM
    (rubrica REJ não cobre norma culta).

    Mapping (spec OF13):
    - Tópico Frasal → C2 (proposição) + C3 (defesa do PDV)
    - Argumento → C3 (desenvolvimento)
    - Repertório → C2 (informações)
    - Coesão → C4 (integral)

    Fórmulas:
    - C2 = media_to_inep( (topico + repertorio) / 2 )
    - C3 = media_to_inep( (topico + argumento) / 2 )
    - C4 = media_to_inep( coesao )

    Caps das flags:
    - repertorio_de_bolso → C2 ≤ 120
    - argumento_superficial → C3 ≤ 120
    - topico_e_pergunta → C2 e C3 ≤ 80 (Cartilha rebaixa proposição interrogativa)
    - coesao_perfeita_sem_progressao → C3 e C4 nas faixas que o LLM emitiu;
      esse flag não dispara cap aqui (é diagnóstico, não punitivo).
    """
    topico = int(rubrica.get("topico_frasal", 0) or 0)
    argumento = int(rubrica.get("argumento", 0) or 0)
    repertorio = int(rubrica.get("repertorio", 0) or 0)
    coesao = int(rubrica.get("coesao", 0) or 0)

    c2 = media_to_inep((topico + repertorio) / 2)
    c3 = media_to_inep((topico + argumento) / 2)
    c4 = media_to_inep(coesao)

    if flags.get("topico_e_pergunta"):
        c2 = min(c2, 80)
        c3 = min(c3, 80)
    if flags.get("repertorio_de_bolso"):
        c2 = min(c2, 120)
    if flags.get("argumento_superficial"):
        c3 = min(c3, 120)

    return {"c1": llm_c1, "c2": c2, "c3": c3, "c4": c4}


# ──────────────────────────────────────────────────────────────────────
# Aplicação no tool_args (chamada do router)
# ──────────────────────────────────────────────────────────────────────

def apply_override(mode: str, tool_args: Dict[str, Any]) -> Dict[str, Any]:
    """Sobrescreve nota_cN_enem (ou notas_enem) com cálculo determinístico.

    Retorna dict com chaves:
    - `tool_args` (modificado in-place)
    - `divergiu` (bool): True se o LLM emitiu nota diferente da calculada
    - `nota_emitida_llm` (any): valor original
    - `nota_final_python` (any): valor calculado

    A função muta tool_args in-place mas também retorna pra encadeamento.
    """
    rubrica = tool_args.get("rubrica_rej") or {}
    flags = tool_args.get("flags") or {}

    if mode == "foco_c2":
        nota_calc = rej_to_c2_score(rubrica, flags)
        emitida = tool_args.get("nota_c2_enem")
        tool_args["nota_c2_enem"] = nota_calc
        return {
            "tool_args": tool_args,
            "divergiu": emitida != nota_calc,
            "nota_emitida_llm": emitida,
            "nota_final_python": nota_calc,
        }

    if mode == "foco_c3":
        nota_calc = rej_to_c3_score(rubrica, flags)
        emitida = tool_args.get("nota_c3_enem")
        tool_args["nota_c3_enem"] = nota_calc
        return {
            "tool_args": tool_args,
            "divergiu": emitida != nota_calc,
            "nota_emitida_llm": emitida,
            "nota_final_python": nota_calc,
        }

    if mode == "foco_c4":
        nota_calc = rej_to_c4_score(rubrica, flags)
        emitida = tool_args.get("nota_c4_enem")
        tool_args["nota_c4_enem"] = nota_calc
        return {
            "tool_args": tool_args,
            "divergiu": emitida != nota_calc,
            "nota_emitida_llm": emitida,
            "nota_final_python": nota_calc,
        }

    if mode == "foco_c5":
        articulacao = tool_args.get("articulacao_a_discussao", "clara")
        nota_calc = rej_to_c5_score(rubrica, flags, articulacao)
        emitida = tool_args.get("nota_c5_enem")
        tool_args["nota_c5_enem"] = nota_calc
        return {
            "tool_args": tool_args,
            "divergiu": emitida != nota_calc,
            "nota_emitida_llm": emitida,
            "nota_final_python": nota_calc,
        }

    if mode == "completo_parcial":
        notas_emitidas = dict(tool_args.get("notas_enem") or {})
        llm_c1 = int(notas_emitidas.get("c1", 0) or 0)
        notas_calc = rej_to_partial_scores(rubrica, flags, llm_c1)
        # Preserva c5 = "não_aplicável"
        new_notas = {**notas_calc, "c5": notas_emitidas.get("c5", "não_aplicável")}
        tool_args["notas_enem"] = new_notas
        total_calc = notas_calc["c1"] + notas_calc["c2"] + notas_calc["c3"] + notas_calc["c4"]
        tool_args["nota_total_parcial"] = total_calc
        emitida_total = sum(int(notas_emitidas.get(k, 0) or 0) for k in ("c1", "c2", "c3", "c4"))
        return {
            "tool_args": tool_args,
            "divergiu": emitida_total != total_calc,
            "nota_emitida_llm": emitida_total,
            "nota_final_python": total_calc,
            "detalhe_notas_emitidas": {k: notas_emitidas.get(k) for k in ("c1", "c2", "c3", "c4")},
            "detalhe_notas_python": notas_calc,
        }

    # completo_integral (OF14) não passa por este override — pipeline v2
    return {
        "tool_args": tool_args,
        "divergiu": False,
        "nota_emitida_llm": None,
        "nota_final_python": None,
    }
