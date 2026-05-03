"""Sugestão de oficinas pro professor (Fase 3).

A partir do diagnóstico de um aluno, sugere oficinas da MESMA SÉRIE
do aluno que trabalham as competências em lacuna. Lista única
deduplicada — mesma oficina não aparece 2x mesmo cobrindo 2 lacunas.

Decisões de design (Daniel, Fase 3):
- Sugestão por COMPETÊNCIA (C1..C5), não por descritor — descritor é
  granular demais pra mapear pra oficina catalogada.
- Filtro por SÉRIE — turma 2S não pode ver oficinas RJ1·... (séries
  diferentes têm temáticas e níveis distintos).
- Max 2 oficinas POR LACUNA mas dedup global (oficina vista 1x só).
- Foco específico (foco_c5) ranqueia ANTES de modos completos —
  intervenção dirigida é mais útil que prática genérica.
- Modo `completo` e `completo_parcial` cobrem TODAS as competências
  (mas vêm depois dos foco específicos no ranking).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from redato_backend.portal.models import Missao

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────
# Mapping competência → modos relevantes (em ordem de prioridade)
# ──────────────────────────────────────────────────────────────────────
#
# foco_cN é o modo mais dirigido: oficina trabalha especificamente
# aquela competência. Vem primeiro no ranking. completo_parcial e
# completo trabalham várias competências — caem como fallback útil
# quando não há foco específico disponível na série.

_MODOS_POR_COMPETENCIA: Dict[str, List[str]] = {
    "C1": ["foco_c1", "completo_parcial", "completo"],
    "C2": ["foco_c2", "completo_parcial", "completo"],
    "C3": ["foco_c3", "completo_parcial", "completo"],
    "C4": ["foco_c4", "completo_parcial", "completo"],
    "C5": ["foco_c5", "completo_parcial", "completo"],
}

MAX_POR_LACUNA = 2
"""Briefing pediu max 2 por descritor."""

SERIES_VALIDAS = ("1S", "2S", "3S")


@dataclass(frozen=True)
class OficinaSugerida:
    """Oficina recomendada pra resolver lacuna(s) específica(s)."""
    codigo: str            # "RJ2·OF12·MF"
    titulo: str
    modo_correcao: str
    oficina_numero: int
    razao: str             # "Trabalha proposta de intervenção (C5)"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "codigo": self.codigo,
            "titulo": self.titulo,
            "modo_correcao": self.modo_correcao,
            "oficina_numero": self.oficina_numero,
            "razao": self.razao,
        }


_NOMES_COMPETENCIA = {
    "C1": "norma culta",
    "C2": "compreensão da proposta e repertório",
    "C3": "argumentação",
    "C4": "coesão textual",
    "C5": "proposta de intervenção",
}


def _competencia_de(descritor_id: str) -> Optional[str]:
    if not isinstance(descritor_id, str) or len(descritor_id) < 2:
        return None
    comp = descritor_id[:2]
    return comp if comp in _MODOS_POR_COMPETENCIA else None


def _rank_modo(modo: str) -> int:
    """Ranking pra ordenar oficinas: foco específico antes, depois
    completo_parcial, depois completo. Menor = mais prioritário."""
    if modo.startswith("foco_c"):
        return 0
    if modo == "completo_parcial":
        return 1
    if modo == "completo":
        return 2
    return 3


def sugerir_oficinas(
    *,
    diagnostico: Optional[Dict[str, Any]],
    serie_aluno: str,
    db_session: Session,
) -> List[OficinaSugerida]:
    """Pra cada lacuna prioritária do diagnóstico, sugere oficinas da
    `serie_aluno` que trabalham a competência relacionada.

    Args:
        diagnostico: payload Fase 2. Se None ou sem `lacunas_prioritarias`,
            retorna [].
        serie_aluno: "1S" | "2S" | "3S". Outras séries → [].
        db_session: sessão SQLAlchemy aberta. Quem chama controla o
            escopo da transação (helper só faz SELECT).

    Returns:
        Lista deduplicada de OficinaSugerida. Vazia se nenhuma
        oficina catalogada cobre as competências em lacuna.

    Notas:
        - Dedup GLOBAL — mesma oficina aparece 1x mesmo cobrindo
          múltiplas lacunas. Usa primeiro `razao` encontrado.
        - Ordem de saída: por ranking de modo (foco antes), depois
          por oficina_numero ascendente — UI renderiza em cards.
    """
    if serie_aluno not in SERIES_VALIDAS:
        logger.warning(
            "sugerir_oficinas: série inválida %r (esperado 1S/2S/3S)",
            serie_aluno,
        )
        return []
    if not isinstance(diagnostico, dict):
        return []
    lacunas = diagnostico.get("lacunas_prioritarias")
    if not isinstance(lacunas, list) or not lacunas:
        return []

    # 1. Coleta competências distintas em ordem de prioridade
    #    (preserva ordem do diagnóstico — primeira lacuna pesa mais).
    comps_em_ordem: List[str] = []
    for did in lacunas:
        c = _competencia_de(did)
        if c and c not in comps_em_ordem:
            comps_em_ordem.append(c)
    if not comps_em_ordem:
        return []

    # 2. Pra cada competência, query oficinas da série compatíveis
    #    com os modos relevantes. Uma única query por série + filtro
    #    em memória — séries têm 11-15 oficinas, custo desprezível.
    rows = db_session.execute(
        select(Missao).where(
            Missao.serie == serie_aluno,
            Missao.ativa.is_(True),
        )
    ).scalars().all()
    if not rows:
        logger.info(
            "sugerir_oficinas: série %s não tem oficinas no catálogo "
            "(esperado em 3S onde OF02/08/12/13 ainda não foram seedadas)",
            serie_aluno,
        )
        return []

    # 3. Pra cada lacuna (em ordem), seleciona até MAX_POR_LACUNA
    #    oficinas. Dedup global por código.
    out: List[OficinaSugerida] = []
    vistas: set = set()
    for comp in comps_em_ordem:
        modos_relevantes = _MODOS_POR_COMPETENCIA[comp]
        # Filtra missões cujo modo está em relevantes
        candidatas = [m for m in rows if m.modo_correcao in modos_relevantes]
        # Ordena: rank de modo primeiro (foco antes), depois oficina_numero
        candidatas.sort(key=lambda m: (_rank_modo(m.modo_correcao), m.oficina_numero))
        # Adiciona até MAX_POR_LACUNA novas oficinas pra essa competência
        adicionadas = 0
        razao_base = (
            f"Trabalha {_NOMES_COMPETENCIA.get(comp, comp)} ({comp})"
        )
        for m in candidatas:
            if adicionadas >= MAX_POR_LACUNA:
                break
            if m.codigo in vistas:
                continue
            vistas.add(m.codigo)
            out.append(OficinaSugerida(
                codigo=m.codigo,
                titulo=m.titulo,
                modo_correcao=m.modo_correcao,
                oficina_numero=m.oficina_numero,
                razao=razao_base,
            ))
            adicionadas += 1

    # 4. Re-ordena saída: rank modo (foco antes) + oficina_numero
    out.sort(key=lambda o: (_rank_modo(o.modo_correcao), o.oficina_numero))
    return out


def sugestoes_to_dicts(sugestoes: List[OficinaSugerida]) -> List[Dict[str, Any]]:
    """Helper: serializa sugestões pro JSON do endpoint."""
    return [s.to_dict() for s in sugestoes]
