"""Agregação de diagnóstico cognitivo por turma (Fase 4).

Lê o último diagnóstico de cada aluno ATIVO da turma e produz visão
coletiva: contagem por descritor, % alunos por status, top lacunas
mais frequentes, médias por competência e resumo executivo (template).

Decisões de design (Daniel, Fase 4):
- "Último diagnóstico" = último envio do aluno com `diagnostico IS
  NOT NULL`. Aluno com 5 envios mas só o 3º teve diagnóstico bom →
  conta o 3º. Não pondera por antiguidade — assume que o último
  reflete o estado atual do aluno.
- Aluno sem nenhum envio diagnosticado é **ignorado** no agregado
  (não conta no denominador). Mostra-se separadamente como
  "alunos sem diagnóstico".
- Resumo executivo é **template estático**, não LLM (Daniel decidiu
  pra Fase 4 — barato, previsível). LLM dinâmico fica pra Fase 5.
- Threshold cores do heatmap (ver HOWTO_diagnostico_turma.md):
    < 30% lacuna → verde
    30-50%       → amarelo
    > 50%        → vermelho
- Threshold pra entrar no top lacunas: ≥ 30% (filtra ruído de turma
  pequena onde 1-2 alunos com lacuna inflam %).
- Sugestões pedagógicas vêm do dicionário Fase 3 +
  oficinas filtradas pela série da turma.

Usado por:
- Endpoint GET /portal/turmas/{turma_id}/diagnostico-agregado
- Futuramente: dashboard professor via WhatsApp (mesmo helper)
"""
from __future__ import annotations

import logging
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from redato_backend.diagnostico.descritores import (
    Descritor, descritores_por_id, load_descritores,
)
from redato_backend.diagnostico.sugestoes_pedagogicas import (
    get_definicao_curta, get_sugestao_pedagogica,
)
from redato_backend.portal.models import (
    Atividade, AlunoTurma, Envio,
)

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────
# Constantes
# ──────────────────────────────────────────────────────────────────────

THRESHOLD_TOP_LACUNAS_PERCENT = 30.0
"""% mínimo de alunos com lacuna pra entrar no top. Abaixo disso, é
ruído estatístico (turma pequena com 1-2 alunos com problema)."""

THRESHOLD_HEATMAP_AMARELO = 30.0
"""% lacuna a partir do qual heatmap vira amarelo (atenção)."""

THRESHOLD_HEATMAP_VERMELHO = 50.0
"""% lacuna a partir do qual heatmap vira vermelho (lacuna coletiva)."""

THRESHOLD_COBERTURA_AVISO = 50.0
"""% alunos diagnosticados abaixo do qual mostramos aviso de
cobertura insuficiente."""

MAX_TOP_LACUNAS = 10
"""Cap de descritores que entram no top — UI mostra 5-10."""

MAX_DESCRITORES_EM_ALERTA = 8
"""Cap por competência na lista descritores_em_alerta (>50% lacuna)."""


# ──────────────────────────────────────────────────────────────────────
# Helpers de cálculo
# ──────────────────────────────────────────────────────────────────────

def _percent(num: int, total: int) -> float:
    """Helper defensivo: retorna 0.0 quando total=0 em vez de
    ZeroDivisionError."""
    if total <= 0:
        return 0.0
    return round((num / total) * 100, 1)


def _coletar_diagnosticos_da_turma(
    session: Session, turma_id: uuid.UUID,
) -> Tuple[List[Dict[str, Any]], int]:
    """Pra cada aluno ativo da turma, busca o último envio com
    diagnostico IS NOT NULL. Retorna (lista_diagnosticos, total_alunos_ativos).

    Total dos alunos ativos é separado da lista de diagnósticos —
    diferença = alunos sem diagnóstico (não enviaram ou todos
    falharam).

    Strategy: 1 query pra alunos + 1 query agregada pra envios
    (LATERAL JOIN no Postgres seria ideal mas só Sa-Core; usamos
    Python pra simplicidade — turmas têm 20-40 alunos, custo
    desprezível).
    """
    alunos_ativos = session.execute(
        select(AlunoTurma).where(
            AlunoTurma.turma_id == turma_id,
            AlunoTurma.ativo.is_(True),
        )
    ).scalars().all()

    aluno_ids = [a.id for a in alunos_ativos]
    if not aluno_ids:
        return [], 0

    # Pega TODOS envios desses alunos com diagnostico não-null + da
    # turma (filtro defesa em profundidade via JOIN com Atividade).
    # Ordena desc pra usar dict aglutinador (primeiro = mais recente).
    rows = session.execute(
        select(Envio)
        .join(Atividade, Atividade.id == Envio.atividade_id)
        .where(
            Envio.aluno_turma_id.in_(aluno_ids),
            Atividade.turma_id == turma_id,
            Atividade.deleted_at.is_(None),
            Envio.diagnostico.isnot(None),
        )
        .order_by(Envio.enviado_em.desc())
    ).scalars().all()

    # Mantém só o mais recente por aluno (primeiro a aparecer com
    # esse aluno_turma_id é o último cronologicamente, pq DESC).
    diagnosticos: List[Dict[str, Any]] = []
    visto: set = set()
    for envio in rows:
        if envio.aluno_turma_id in visto:
            continue
        diag = envio.diagnostico
        if not isinstance(diag, dict):
            logger.warning(
                "[agg] envio %s.diagnostico tipo inesperado %s — pulando",
                envio.id, type(diag).__name__,
            )
            continue
        diagnosticos.append({
            "aluno_turma_id": envio.aluno_turma_id,
            "envio_id": envio.id,
            "enviado_em": envio.enviado_em,
            "diagnostico": diag,
        })
        visto.add(envio.aluno_turma_id)

    return diagnosticos, len(alunos_ativos)


def _agregar_por_descritor(
    diagnosticos: List[Dict[str, Any]],
    descritores_yaml: Dict[str, Descritor],
) -> List[Dict[str, Any]]:
    """Pra cada um dos 40 descritores, conta alunos por status e
    monta entry com nome + definição + sugestão pedagógica.

    Importante: ITERA OS 40 DESCRITORES DO YAML (não o que veio dos
    diagnósticos). Mesmo descritor que ninguém violou aparece na
    saída (status 0/0/0) — heatmap precisa renderizar todos os 40
    pra coluna ficar consistente.
    """
    n_total = len(diagnosticos)

    # Index: descritor_id → Counter de status por aluno (a Fase 2
    # produz 40 entries por aluno; acumulamos cross-aluno aqui).
    contagem: Dict[str, Counter] = defaultdict(Counter)
    for d in diagnosticos:
        descs = (d["diagnostico"] or {}).get("descritores") or []
        for entry in descs:
            if not isinstance(entry, dict):
                continue
            did = entry.get("id")
            status = entry.get("status")
            if did and status in {"dominio", "lacuna", "incerto"}:
                contagem[did][status] += 1

    # Constrói saída ordenada pelos 40 IDs do YAML
    out: List[Dict[str, Any]] = []
    for did, yaml_d in sorted(
        descritores_yaml.items(),
        key=lambda kv: (kv[1].comp_num, kv[1].id),
    ):
        c = contagem.get(did, Counter())
        n_lacuna = c.get("lacuna", 0)
        n_incerto = c.get("incerto", 0)
        n_dominio = c.get("dominio", 0)
        out.append({
            "id": did,
            "competencia": yaml_d.competencia,
            "nome": yaml_d.nome,
            "categoria_inep": yaml_d.categoria_inep,
            "alunos_com_lacuna": n_lacuna,
            "alunos_com_incerto": n_incerto,
            "alunos_com_dominio": n_dominio,
            "percent_lacuna": _percent(n_lacuna, n_total),
            "percent_dominio": _percent(n_dominio, n_total),
            "definicao_curta": get_definicao_curta(did, yaml_d.definicao),
            "sugestao_pedagogica": get_sugestao_pedagogica(did),
        })
    return out


def _agregar_por_competencia(
    agregado_por_descritor: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Pra cada competência (C1-C5), calcula médias % e identifica
    descritores em alerta (>50% lacuna)."""
    by_comp: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for d in agregado_por_descritor:
        by_comp[d["competencia"]].append(d)

    out: List[Dict[str, Any]] = []
    for comp in ("C1", "C2", "C3", "C4", "C5"):
        descs = by_comp.get(comp, [])
        if not descs:
            out.append({
                "competencia": comp,
                "percent_dominio_medio": 0.0,
                "percent_lacuna_medio": 0.0,
                "descritores_em_alerta": [],
            })
            continue
        soma_dom = sum(d["percent_dominio"] for d in descs)
        soma_lac = sum(d["percent_lacuna"] for d in descs)
        em_alerta = sorted(
            [d for d in descs if d["percent_lacuna"] >= THRESHOLD_HEATMAP_VERMELHO],
            key=lambda d: -d["percent_lacuna"],
        )[:MAX_DESCRITORES_EM_ALERTA]
        out.append({
            "competencia": comp,
            "percent_dominio_medio": round(soma_dom / len(descs), 1),
            "percent_lacuna_medio": round(soma_lac / len(descs), 1),
            "descritores_em_alerta": [d["id"] for d in em_alerta],
        })
    return out


def calcular_top_lacunas(
    agregado_por_descritor: List[Dict[str, Any]],
    *,
    limite: int = MAX_TOP_LACUNAS,
    min_percent: float = THRESHOLD_TOP_LACUNAS_PERCENT,
) -> List[Dict[str, Any]]:
    """Ranqueia descritores por % alunos com lacuna.

    Aplica `min_percent` (default 30%) — descritores abaixo viram
    ruído em turmas pequenas (1 aluno com lacuna em turma de 3 dá
    33%, o que ENTRA; 1 em 10 dá 10%, fica fora — apropriado).

    Retorna lista ordenada DESC por percent_lacuna, max `limite`.
    Cada entry tem o suficiente pra UI renderizar card direto:
    id, nome, percent_lacuna, qtd_alunos, sugestao_pedagogica.
    """
    candidatos = [
        d for d in agregado_por_descritor
        if d["percent_lacuna"] >= min_percent
    ]
    candidatos.sort(key=lambda d: -d["percent_lacuna"])
    out: List[Dict[str, Any]] = []
    for d in candidatos[:limite]:
        out.append({
            "id": d["id"],
            "competencia": d["competencia"],
            "nome": d["nome"],
            "percent_lacuna": d["percent_lacuna"],
            "qtd_alunos": d["alunos_com_lacuna"],
            "sugestao_pedagogica": d["sugestao_pedagogica"],
            "definicao_curta": d["definicao_curta"],
        })
    return out


# ──────────────────────────────────────────────────────────────────────
# Resumo executivo (template estático — Fase 4)
# ──────────────────────────────────────────────────────────────────────
#
# Daniel (Fase 4): LLM dinâmico fica pra Fase 5/6. Template
# preenchido com dados é barato, previsível e suficiente pra MVP do
# dashboard coletivo.

_NOMES_COMPETENCIA_TXT = {
    "C1": "norma culta",
    "C2": "tema e repertório",
    "C3": "argumentação",
    "C4": "coesão textual",
    "C5": "proposta de intervenção",
}


def _gerar_resumo_executivo(
    *,
    turma_codigo: str,
    n_alunos_diagnosticados: int,
    n_alunos_total: int,
    agregado_por_competencia: List[Dict[str, Any]],
    top_lacunas: List[Dict[str, Any]],
) -> str:
    """3-5 frases descrevendo: pontos fortes, pontos críticos, plano
    sugerido. Template estático — Fase 4 não usa LLM aqui.
    """
    if n_alunos_diagnosticados == 0:
        return (
            "Aguardando primeira redação corrigida da turma. Quando "
            "alunos enviarem suas redações, o diagnóstico coletivo "
            "aparece aqui."
        )

    # Identifica competência com mais domínio + competência com mais lacuna
    comps_ordenados = sorted(
        agregado_por_competencia,
        key=lambda c: -c["percent_dominio_medio"],
    )
    comp_forte = comps_ordenados[0] if comps_ordenados else None
    comps_por_lacuna = sorted(
        agregado_por_competencia,
        key=lambda c: -c["percent_lacuna_medio"],
    )
    comp_critica = comps_por_lacuna[0] if comps_por_lacuna else None

    cobertura_pct = _percent(n_alunos_diagnosticados, n_alunos_total)

    fragmentos: List[str] = []

    # Frase 1 — visão geral + cobertura
    if cobertura_pct < THRESHOLD_COBERTURA_AVISO:
        fragmentos.append(
            f"A turma {turma_codigo} tem diagnóstico de "
            f"{n_alunos_diagnosticados} de {n_alunos_total} alunos "
            f"({cobertura_pct}%). Cobertura abaixo de 50% — o quadro "
            f"abaixo pode não refletir a turma completa."
        )
    else:
        fragmentos.append(
            f"A turma {turma_codigo} tem diagnóstico de "
            f"{n_alunos_diagnosticados} de {n_alunos_total} alunos "
            f"({cobertura_pct}%)."
        )

    # Frase 2 — ponto forte
    if comp_forte and comp_forte["percent_dominio_medio"] >= 50:
        nome_forte = _NOMES_COMPETENCIA_TXT[comp_forte["competencia"]]
        fragmentos.append(
            f"Forte domínio coletivo em {nome_forte} "
            f"({comp_forte['competencia']}, "
            f"{comp_forte['percent_dominio_medio']}% médio em domínio)."
        )

    # Frase 3 — top lacunas
    if not top_lacunas:
        fragmentos.append(
            "Nenhum descritor crítico (≥30% alunos com lacuna) "
            "identificado — turma está distribuída sem concentração "
            "em lacuna específica."
        )
    else:
        top3 = top_lacunas[:3]
        if len(top3) == 1:
            l = top3[0]
            fragmentos.append(
                f"{l['percent_lacuna']}% dos alunos têm lacuna em "
                f"'{l['nome']}' ({l['id']}) — descritor mais crítico."
            )
        else:
            descritores_txt = "; ".join(
                f"'{l['nome']}' ({l['id']}, {l['percent_lacuna']}%)"
                for l in top3
            )
            fragmentos.append(
                f"Lacunas coletivas mais frequentes: {descritores_txt}."
            )

    # Frase 4 — recomendação acionável
    if top_lacunas:
        l_principal = top_lacunas[0]
        fragmentos.append(
            f"Recomenda-se trabalhar {l_principal['nome'].lower()} "
            f"com a turma toda antes da próxima atividade — ver "
            f"sugestão pedagógica detalhada no card abaixo."
        )
    elif comp_critica and comp_critica["percent_lacuna_medio"] >= 30:
        nome = _NOMES_COMPETENCIA_TXT[comp_critica["competencia"]]
        fragmentos.append(
            f"Atenção a {nome} ({comp_critica['competencia']}) "
            f"— competência com maior média de lacunas, mesmo sem "
            f"descritor isolado crítico."
        )

    return " ".join(fragmentos)


# ──────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────

def agregar_diagnosticos_turma(
    *,
    turma_id: uuid.UUID,
    turma_codigo: str,
    turma_serie: str,
    db_session: Session,
) -> Dict[str, Any]:
    """Lê todos os diagnósticos mais recentes da turma e agrega.

    Args:
        turma_id: UUID da turma.
        turma_codigo: código display (ex.: "1A") — pra resumo executivo.
        turma_serie: "1S"/"2S"/"3S" — pra filtrar oficinas sugeridas
            no top lacunas.
        db_session: sessão SQLAlchemy aberta.

    Returns:
        Dict com agregado completo (estrutura documentada em
        `HOWTO_diagnostico_turma.md`). Sempre retorna estrutura
        válida; campos vazios quando turma sem dados.
    """
    diagnosticos, n_alunos_ativos = _coletar_diagnosticos_da_turma(
        db_session, turma_id,
    )
    n_diagnosticados = len(diagnosticos)

    # YAML lookup pra enriquecer descritores com nome/competencia
    yaml_lookup = descritores_por_id()

    agregado_por_descritor = _agregar_por_descritor(diagnosticos, yaml_lookup)
    agregado_por_competencia = _agregar_por_competencia(agregado_por_descritor)
    top_lacunas = calcular_top_lacunas(agregado_por_descritor)

    # Sugestões de oficinas pras top lacunas. Reutiliza helper Fase 3
    # que já filtra por série, dedup, ranking foco-antes.
    from redato_backend.diagnostico.sugestoes import (
        sugerir_oficinas, sugestoes_to_dicts,
    )
    diag_sintetico_pra_sugestao = {
        "lacunas_prioritarias": [l["id"] for l in top_lacunas[:5]],
    }
    oficinas_globais = sugerir_oficinas(
        diagnostico=diag_sintetico_pra_sugestao,
        serie_aluno=turma_serie,
        db_session=db_session,
    )
    oficinas_dicts = sugestoes_to_dicts(oficinas_globais)
    # Anexa lista de oficinas em cada top lacuna (filtrada pelo
    # competência da lacuna — só oficinas que cobrem aquela C).
    for l in top_lacunas:
        comp = l["competencia"]
        l["oficinas_sugeridas"] = [
            o for o in oficinas_dicts
            # Filtro defensivo: oficina ranqueada pra aquela competência
            # sempre vai ter `razao` mencionando ela. Em foco_cN o modo
            # bate; em completo cobre todas — incluímos ambos.
            if (
                o["modo_correcao"].endswith(f"_{comp.lower()}")
                or o["modo_correcao"] in ("completo", "completo_parcial")
            )
        ][:2]  # max 2 oficinas por lacuna

    resumo_executivo = _gerar_resumo_executivo(
        turma_codigo=turma_codigo,
        n_alunos_diagnosticados=n_diagnosticados,
        n_alunos_total=n_alunos_ativos,
        agregado_por_competencia=agregado_por_competencia,
        top_lacunas=top_lacunas,
    )

    # Data do diagnóstico mais recente da turma — pra UI mostrar
    # "atualizado em DD/MM HH:MM"
    atualizado_em: Optional[datetime] = None
    if diagnosticos:
        atualizado_em = max(d["enviado_em"] for d in diagnosticos)

    return {
        "turma": {
            "id": str(turma_id),
            "codigo": turma_codigo,
            "serie": turma_serie,
            "total_alunos": n_alunos_ativos,
            "alunos_com_diagnostico": n_diagnosticados,
            "alunos_sem_diagnostico": n_alunos_ativos - n_diagnosticados,
        },
        "atualizado_em": (
            atualizado_em.isoformat() if atualizado_em else None
        ),
        "agregado_por_descritor": agregado_por_descritor,
        "agregado_por_competencia": agregado_por_competencia,
        "top_lacunas": top_lacunas,
        "resumo_executivo": resumo_executivo,
    }
