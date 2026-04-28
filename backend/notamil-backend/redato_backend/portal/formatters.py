"""Helpers de formatação humana de série, missão e modo de correção.

Espelha `redato_frontend/lib/format.ts`. Usado em PDFs e emails
transacionais. UI nunca expõe códigos técnicos como `1S` ou
`RJ1·OF10·MF` — só o nome humano.

Mantido em sync com o frontend manualmente (seria bom OpenAPI codegen
ou compartilhamento via JSON, mas hoje o custo de manter os 2 alinhados
é baixo).
"""
from __future__ import annotations

from typing import Optional


_SERIE_HUMANA = {
    "1S": "1ª série",
    "2S": "2ª série",
    "3S": "3ª série",
}


def format_serie(serie: Optional[str]) -> str:
    """'1S' → '1ª série'. Fallback: devolve o input se não conhecido."""
    if not serie:
        return ""
    return _SERIE_HUMANA.get(serie, serie)


_MODO_HUMANO = {
    "foco_c1": "Foco C1",
    "foco_c2": "Foco C2",
    "foco_c3": "Foco C3",
    "foco_c4": "Foco C4",
    "foco_c5": "Foco C5",
    "completo_parcial": "Correção parcial",
    "completo": "Correção 5 competências",
}


def format_modo_correcao(modo: Optional[str]) -> str:
    """'foco_c3' → 'Foco C3'. Fallback humanizado pra modos novos."""
    if not modo:
        return ""
    if modo in _MODO_HUMANO:
        return _MODO_HUMANO[modo]
    return modo.replace("_", " ").title()


def format_missao_label_humana(
    *, oficina_numero: Optional[int],
    titulo: Optional[str],
    modo_correcao: Optional[str] = None,
) -> str:
    """Constrói label "Oficina 10 — Jogo Dissertativo (Foco C3)".

    Sem `modo_correcao`: omite parênteses.
    Sem `oficina_numero`: usa apenas título.
    Sem `titulo`: fallback "Oficina N".
    """
    base: str
    if oficina_numero and titulo:
        base = f"Oficina {oficina_numero} — {titulo}"
    elif oficina_numero:
        base = f"Oficina {oficina_numero}"
    elif titulo:
        base = titulo
    else:
        return "Missão"
    if modo_correcao:
        return f"{base} ({format_modo_correcao(modo_correcao)})"
    return base
