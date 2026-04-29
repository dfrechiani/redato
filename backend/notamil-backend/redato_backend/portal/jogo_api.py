"""Endpoints REST do jogo "Redação em Jogo" — Fase 2 passo 3.

Tudo registrado num router separado pra manter `portal_api.py` (já com
2500 linhas) administrável. Mesmo prefix `/portal` — frontend não vê
diferença.

Endpoints:

- POST   /portal/partidas                     cria partida (1 grupo)
- GET    /portal/partidas/{id}                detalha partida
- PATCH  /portal/partidas/{id}                edita grupo/alunos/prazo
- DELETE /portal/partidas/{id}                apaga (se sem reescritas)
- GET    /portal/atividades/{aid}/partidas    lista partidas da atividade
- GET    /portal/jogos/minidecks              lista minidecks ativos

Decisões aplicadas (adendo G):
- G.1.2: 1:N atividade↔partidas. Distingue por (atividade_id, grupo_codigo).
- G.1.3: reescritas imutáveis após criadas — DELETE da partida bloqueia
  se há reescritas (preservar trabalho do aluno).
- G.1.5: tema do minideck domina. Atividade ainda não tem coluna `tema`
  (decisão futura) — validação `tema_atividade == tema_minideck` fica
  como no-op até a coluna existir; só checamos que o tema é minideck
  válido + ativo.

Permissões:
- POST/PATCH/DELETE: só professor responsável pela turma da atividade.
- GET partida: professor da turma OU aluno do grupo (se aluno_turma_id
  está na lista de alunos vinculados à partida).
- GET lista de partidas + minidecks: qualquer professor autenticado
  (filtrado por permissão de turma).
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from redato_backend.portal.auth.middleware import (
    AuthenticatedUser, get_current_user,
)
from redato_backend.portal.auth.permissions import (
    can_create_atividade, can_view_turma,
)
from redato_backend.portal.db import get_engine
from redato_backend.portal.models import (
    AlunoTurma, Atividade, CartaLacuna, JogoMinideck, PartidaJogo,
    Professor, ReescritaIndividual, Turma,
)


logger = logging.getLogger(__name__)


# Router próprio mas mesmo prefix do portal — `app.include_router(jogo_router)`
# adiciona às rotas existentes sem conflito.
router = APIRouter(prefix="/portal", tags=["portal:jogo"])


# ──────────────────────────────────────────────────────────────────────
# Schemas
# ──────────────────────────────────────────────────────────────────────

class PartidaCreate(BaseModel):
    """Body do POST /portal/partidas."""
    atividade_id: uuid.UUID
    tema: str = Field(..., min_length=1, max_length=64,
                       description="Slug do minideck (ex.: saude_mental)")
    grupo_codigo: str = Field(..., min_length=1, max_length=120,
                               description="Ex.: 'Grupo Azul'")
    alunos_turma_ids: List[uuid.UUID] = Field(
        ..., min_length=1,
        description="Pelo menos 1 aluno; todos da mesma turma da atividade",
    )
    prazo_reescrita: datetime = Field(
        ..., description="Datetime aware ISO 8601 — ex.: 2026-05-06T22:00:00-03:00",
    )


class PartidaUpdate(BaseModel):
    """Body do PATCH /portal/partidas/{id}. Todos opcionais. Não permite
    alterar `atividade_id` nem `tema` (criar partida nova se precisar)."""
    grupo_codigo: Optional[str] = Field(None, min_length=1, max_length=120)
    alunos_turma_ids: Optional[List[uuid.UUID]] = Field(None, min_length=1)
    prazo_reescrita: Optional[datetime] = None


class AlunoResumo(BaseModel):
    """Resumo de aluno vinculado à partida — frontend renderiza
    avatar/nome sem precisar fetch extra."""
    aluno_turma_id: str
    nome: str


class TentativaReescritaResumo(BaseModel):
    """Preview de reescrita do aluno — usado em PartidaDetail.
    Avoid carregar texto completo (KB/aluno) na lista — endpoint
    dedicado serve o texto completo na Fase 3."""
    id: str
    aluno_turma_id: str
    aluno_nome: str
    tem_redato_output: bool
    enviado_em: str  # ISO UTC


class PartidaResumo(BaseModel):
    """Item de listagem (GET /atividades/{id}/partidas)."""
    id: str
    atividade_id: str
    tema: str
    nome_humano_tema: str
    grupo_codigo: str
    alunos: List[AlunoResumo]
    prazo_reescrita: str  # ISO UTC
    status_partida: str   # "aguardando_cartas" | "aguardando_reescritas" | "concluida"
    n_reescritas: int
    n_alunos: int
    created_at: str


class PartidaDetail(BaseModel):
    """GET /portal/partidas/{id} — full detail."""
    id: str
    atividade_id: str
    tema: str
    nome_humano_tema: str
    grupo_codigo: str
    alunos: List[AlunoResumo]
    cartas_escolhidas: List[str]   # codes — vazia até bot popular
    texto_montado: str             # vazio até bot popular
    prazo_reescrita: str
    status_partida: str
    reescritas: List[TentativaReescritaResumo]
    created_at: str


class MinideckResumo(BaseModel):
    """GET /portal/jogos/minidecks — item da lista pra dropdown UI."""
    tema: str
    nome_humano: str
    serie: Optional[str]
    descricao: Optional[str]
    total_cartas: int


# ──────────────────────────────────────────────────────────────────────
# Helpers internos
# ──────────────────────────────────────────────────────────────────────

# Vínculo aluno↔partida vive em `partidas_jogo.cartas_escolhidas`
# (JSONB) só no momento da partida estar formada. Pra grupo "lista de
# alunos" antes do bot rodar, usamos um JSON paralelo dentro do mesmo
# campo — chave reservada `_alunos_turma_ids`. Decisão de não criar
# tabela `partidas_alunos` separada: lista é pequena (≤ ~6 alunos) e
# imutável após criação; index não compensa overhead da tabela. Se
# queries do tipo "todas as partidas do aluno X" virarem comum, criar
# tabela depois.
_ALUNOS_KEY = "_alunos_turma_ids"


def _alunos_ids_da_partida(partida: PartidaJogo) -> List[uuid.UUID]:
    """Extrai os aluno_turma_ids vinculados à partida do campo
    `cartas_escolhidas` (JSONB). Retorna lista vazia se ainda não
    populada."""
    raw = partida.cartas_escolhidas or {}
    if isinstance(raw, list):
        # Formato pré-G.1.2 (lista de codigos puros) — sem alunos
        # cadastrados ainda. Não acontece com partidas criadas por
        # esse endpoint, mas defensivo.
        return []
    items = raw.get(_ALUNOS_KEY, [])
    out: List[uuid.UUID] = []
    for s in items:
        try:
            out.append(uuid.UUID(str(s)))
        except (ValueError, TypeError):
            continue
    return out


def _set_alunos_partida(partida: PartidaJogo, ids: List[uuid.UUID]) -> None:
    """Materializa lista de alunos no `cartas_escolhidas` (JSONB).
    Preserva os outros campos do JSONB — bot pode ter populado os
    codigos das cartas."""
    raw = partida.cartas_escolhidas or {}
    if isinstance(raw, list):
        # Migração inline de formato antigo — converte pra dict.
        raw = {"codigos": list(raw)}
    raw = dict(raw)
    raw[_ALUNOS_KEY] = [str(i) for i in ids]
    partida.cartas_escolhidas = raw


def _codigos_da_partida(partida: PartidaJogo) -> List[str]:
    """Extrai a lista de codigos (E##/P##/etc.) do `cartas_escolhidas`,
    excluindo o campo `_alunos_turma_ids`."""
    raw = partida.cartas_escolhidas or {}
    if isinstance(raw, list):
        return [str(c) for c in raw]
    codigos = raw.get("codigos", [])
    if isinstance(codigos, list):
        return [str(c) for c in codigos]
    return []


def _status_partida(
    partida: PartidaJogo, n_reescritas: int, n_alunos: int,
) -> str:
    """Calcula status sem persistir — derivado do estado do jogo.

    - aguardando_cartas:    bot ainda não recebeu codigos das cartas
                            (texto_montado vazio)
    - aguardando_reescritas: cartas escolhidas mas nem todos os alunos
                             do grupo enviaram reescrita
    - concluida:             cada aluno do grupo já enviou reescrita
    """
    if not partida.texto_montado.strip():
        return "aguardando_cartas"
    if n_reescritas < n_alunos:
        return "aguardando_reescritas"
    return "concluida"


def _carregar_alunos_resumo(
    session: Session, ids: List[uuid.UUID],
) -> List[AlunoResumo]:
    if not ids:
        return []
    rows = session.execute(
        select(AlunoTurma).where(AlunoTurma.id.in_(ids))
    ).scalars().all()
    by_id = {a.id: a for a in rows}
    out: List[AlunoResumo] = []
    for aid in ids:  # preserva ordem do input
        a = by_id.get(aid)
        if a is not None:
            out.append(AlunoResumo(
                aluno_turma_id=str(a.id), nome=a.nome,
            ))
    return out


def _checa_professor_da_atividade(
    session: Session, auth: AuthenticatedUser,
    atividade_id: uuid.UUID,
) -> Atividade:
    """Resolve a atividade + valida que `auth` é professor responsável.
    Diferente de `_check_permission_atividade` em portal_api.py que
    permite coordenador também — aqui é restrito a professor."""
    ativ = session.get(Atividade, atividade_id)
    if ativ is None or ativ.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Atividade não encontrada",
        )
    turma = session.get(Turma, ativ.turma_id)
    if turma is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Turma da atividade não encontrada",
        )
    if not can_create_atividade(auth, turma):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Apenas o professor responsável pela turma pode "
                "operar partidas dessa atividade"
            ),
        )
    return ativ


def _to_partida_resumo(
    session: Session, partida: PartidaJogo, minideck: JogoMinideck,
) -> PartidaResumo:
    aluno_ids = _alunos_ids_da_partida(partida)
    alunos = _carregar_alunos_resumo(session, aluno_ids)
    n_reescritas = session.execute(
        select(func.count(ReescritaIndividual.id))
        .where(ReescritaIndividual.partida_id == partida.id)
    ).scalar() or 0
    return PartidaResumo(
        id=str(partida.id),
        atividade_id=str(partida.atividade_id),
        tema=minideck.tema,
        nome_humano_tema=minideck.nome_humano,
        grupo_codigo=partida.grupo_codigo,
        alunos=alunos,
        prazo_reescrita=partida.prazo_reescrita.isoformat(),
        status_partida=_status_partida(partida, int(n_reescritas), len(alunos)),
        n_reescritas=int(n_reescritas),
        n_alunos=len(alunos),
        created_at=partida.created_at.isoformat(),
    )


# ──────────────────────────────────────────────────────────────────────
# POST /portal/partidas
# ──────────────────────────────────────────────────────────────────────

class _PartidaCreateResponse(BaseModel):
    id: str
    partida: PartidaDetail


@router.post("/partidas", status_code=status.HTTP_201_CREATED,
             response_model=_PartidaCreateResponse)
def criar_partida(
    body: PartidaCreate,
    auth: AuthenticatedUser = Depends(get_current_user),
) -> _PartidaCreateResponse:
    """Cria partida do jogo pro grupo. Professor declarou cartas mais
    tarde via bot WhatsApp — aqui só cadastra grupo + alunos + prazo.

    Validações:
    - Atividade existe, professor é dono.
    - Tema bate com slug em jogos_minideck (ativo=True).
    - Todos os alunos pertencem à turma + estão ativos.
    - prazo_reescrita > now (UTC).
    - Não existe partida (atividade_id, grupo_codigo) — UNIQUE.
    """
    # Normalizações leves antes de tocar o DB.
    tema_slug = body.tema.strip().lower()
    grupo = body.grupo_codigo.strip()
    if not grupo:
        raise HTTPException(
            status_code=400, detail="grupo_codigo não pode ser vazio",
        )

    # Prazo no futuro. Aceita aware (com tz) — converte pra UTC pra
    # comparar com `now()`. Naive recusado — Daniel teria typo no
    # frontend ao não anexar tz.
    if body.prazo_reescrita.tzinfo is None:
        raise HTTPException(
            status_code=400,
            detail=(
                "prazo_reescrita precisa ser aware (com timezone). "
                "Use ISO 8601 com offset, ex.: "
                "2026-05-06T22:00:00-03:00"
            ),
        )
    prazo_utc = body.prazo_reescrita.astimezone(timezone.utc)
    if prazo_utc <= datetime.now(timezone.utc):
        raise HTTPException(
            status_code=400,
            detail="prazo_reescrita precisa ser no futuro",
        )

    # Dedup IDs preservando ordem — frontend pode enviar duplicado por
    # bug de double-click; aqui é defensivo.
    seen: set = set()
    aluno_ids: List[uuid.UUID] = []
    for aid in body.alunos_turma_ids:
        if aid not in seen:
            seen.add(aid)
            aluno_ids.append(aid)

    with Session(get_engine()) as session:
        ativ = _checa_professor_da_atividade(
            session, auth, body.atividade_id,
        )

        # Tema → minideck ativo.
        minideck = session.execute(
            select(JogoMinideck).where(
                JogoMinideck.tema == tema_slug,
                JogoMinideck.ativo.is_(True),
            )
        ).scalar_one_or_none()
        if minideck is None:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"tema {tema_slug!r} não é um minideck ativo. "
                    f"Use GET /portal/jogos/minidecks pra listar."
                ),
            )

        # Alunos da turma — todos os IDs informados precisam pertencer
        # à mesma turma da atividade + estar ativos.
        alunos = session.execute(
            select(AlunoTurma).where(AlunoTurma.id.in_(aluno_ids))
        ).scalars().all()
        achados = {a.id for a in alunos}
        faltando = [aid for aid in aluno_ids if aid not in achados]
        if faltando:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"alunos_turma_ids não encontrados: "
                    f"{[str(x) for x in faltando]}"
                ),
            )
        for a in alunos:
            if a.turma_id != ativ.turma_id:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"aluno {a.id} pertence a turma diferente da "
                        f"atividade"
                    ),
                )
            if not a.ativo:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"aluno {a.id} ({a.nome}) está inativo na "
                        f"turma"
                    ),
                )

        # G.1.5 — tema do minideck domina. Atividade ainda não tem
        # coluna `tema`; quando ganhar, validar aqui.

        partida = PartidaJogo(
            atividade_id=ativ.id,
            minideck_id=minideck.id,
            grupo_codigo=grupo,
            cartas_escolhidas={},  # populado por _set_alunos
            texto_montado="",
            prazo_reescrita=prazo_utc,
            criada_por_professor_id=auth.user_id,
        )
        _set_alunos_partida(partida, aluno_ids)
        session.add(partida)
        try:
            session.commit()
        except IntegrityError as exc:
            session.rollback()
            # uq_partidas_jogo_atividade_grupo — único motivo de
            # IntegrityError nesse INSERT.
            logger.warning(
                "criar_partida: violação UNIQUE atividade=%s grupo=%r: %s",
                ativ.id, grupo, exc.orig,
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Já existe uma partida com grupo_codigo "
                    f"{grupo!r} nessa atividade. Use outro nome ou "
                    f"PATCH na existente."
                ),
            ) from None
        session.refresh(partida)

        logger.info(
            "criar_partida ok: id=%s atividade=%s grupo=%r "
            "tema=%s alunos=%d professor=%s",
            partida.id, ativ.id, grupo, tema_slug,
            len(aluno_ids), auth.user_id,
        )

        detail = _to_partida_detail(session, partida, minideck)
        return _PartidaCreateResponse(id=str(partida.id), partida=detail)


def _to_partida_detail(
    session: Session, partida: PartidaJogo, minideck: JogoMinideck,
) -> PartidaDetail:
    aluno_ids = _alunos_ids_da_partida(partida)
    alunos = _carregar_alunos_resumo(session, aluno_ids)

    reescritas_rows = session.execute(
        select(ReescritaIndividual, AlunoTurma)
        .join(AlunoTurma, AlunoTurma.id == ReescritaIndividual.aluno_turma_id)
        .where(ReescritaIndividual.partida_id == partida.id)
        .order_by(ReescritaIndividual.created_at)
    ).all()
    reescritas: List[TentativaReescritaResumo] = []
    for r, a in reescritas_rows:
        reescritas.append(TentativaReescritaResumo(
            id=str(r.id),
            aluno_turma_id=str(a.id),
            aluno_nome=a.nome,
            tem_redato_output=r.redato_output is not None,
            enviado_em=r.created_at.isoformat(),
        ))

    return PartidaDetail(
        id=str(partida.id),
        atividade_id=str(partida.atividade_id),
        tema=minideck.tema,
        nome_humano_tema=minideck.nome_humano,
        grupo_codigo=partida.grupo_codigo,
        alunos=alunos,
        cartas_escolhidas=_codigos_da_partida(partida),
        texto_montado=partida.texto_montado,
        prazo_reescrita=partida.prazo_reescrita.isoformat(),
        status_partida=_status_partida(
            partida, len(reescritas), len(alunos),
        ),
        reescritas=reescritas,
        created_at=partida.created_at.isoformat(),
    )


# ──────────────────────────────────────────────────────────────────────
# GET /portal/partidas/{id}
# ──────────────────────────────────────────────────────────────────────

@router.get("/partidas/{partida_id}", response_model=PartidaDetail)
def detalhe_partida(
    partida_id: uuid.UUID,
    auth: AuthenticatedUser = Depends(get_current_user),
) -> PartidaDetail:
    """Retorna detalhes da partida.

    Acesso:
    - Professor responsável pela turma da atividade.
    - Aluno do grupo (cujo aluno_turma_id está em alunos_turma_ids).
    - Outros: 403.
    """
    with Session(get_engine()) as session:
        partida = session.get(PartidaJogo, partida_id)
        if partida is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Partida não encontrada",
            )
        ativ = session.get(Atividade, partida.atividade_id)
        if ativ is None or ativ.deleted_at is not None:
            # Caso muito raro: atividade soft-deletada com partida
            # órfã. Tratamos como 404 pra não vazar metadata.
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Partida pertence a atividade não disponível",
            )
        turma = session.get(Turma, ativ.turma_id)
        minideck = session.get(JogoMinideck, partida.minideck_id)

        # Verifica permissão: professor da turma OU aluno do grupo.
        is_prof = (
            turma is not None and can_view_turma(auth, turma)
            and auth.papel == "professor"
        )
        is_aluno_do_grupo = False
        if auth.papel == "professor":
            # Professores não-dono também caem em `is_prof=False` se
            # turma.professor_id != auth.user_id; pra esse endpoint
            # GET é mais permissivo (can_view_turma também aceita
            # coordenador da escola).
            if turma is not None and can_view_turma(auth, turma):
                is_prof = True
        if not is_prof:
            # Tenta como aluno. AlunoTurma não tem auth próprio na M9
            # (alunos não logam no portal — só via WhatsApp). Mantemos
            # a porta aberta pra Fase 4 quando aluno tiver login.
            # Por ora: se papel = "aluno_turma" (não existe ainda),
            # checa se está na lista. Se papel é coordenador, deixa
            # o can_view_turma decidir.
            if turma is not None and can_view_turma(auth, turma):
                # Coordenador da escola — vê.
                is_prof = True

        if not is_prof and not is_aluno_do_grupo:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Sem permissão pra ver essa partida",
            )

        if minideck is None:
            # Catalog drift — minideck deletado mas partida velha
            # ainda apontando. Retorna detail com placeholder pra
            # frontend não crashar.
            minideck = JogoMinideck(
                tema="?", nome_humano="(minideck removido)",
            )

        return _to_partida_detail(session, partida, minideck)


# ──────────────────────────────────────────────────────────────────────
# GET /portal/atividades/{id}/partidas
# ──────────────────────────────────────────────────────────────────────

@router.get("/atividades/{atividade_id}/partidas",
             response_model=List[PartidaResumo])
def listar_partidas_da_atividade(
    atividade_id: uuid.UUID,
    auth: AuthenticatedUser = Depends(get_current_user),
) -> List[PartidaResumo]:
    """Lista todas as partidas da atividade. Permite múltiplos grupos
    da mesma atividade jogando paralelo (G.1.2). Ordenado por
    `created_at` ascendente — primeira partida criada aparece primeiro
    (UI tipicamente mostra como timeline)."""
    with Session(get_engine()) as session:
        # Permite professor da turma OU coordenador da escola — mesma
        # regra dos outros GETs do portal_api.
        ativ = session.get(Atividade, atividade_id)
        if ativ is None or ativ.deleted_at is not None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Atividade não encontrada",
            )
        turma = session.get(Turma, ativ.turma_id)
        if turma is None or not can_view_turma(auth, turma):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Sem permissão pra essa atividade",
            )

        rows = session.execute(
            select(PartidaJogo, JogoMinideck)
            .join(JogoMinideck,
                   JogoMinideck.id == PartidaJogo.minideck_id)
            .where(PartidaJogo.atividade_id == atividade_id)
            .order_by(PartidaJogo.created_at.asc())
        ).all()
        return [
            _to_partida_resumo(session, p, m) for p, m in rows
        ]


# ──────────────────────────────────────────────────────────────────────
# GET /portal/jogos/minidecks
# ──────────────────────────────────────────────────────────────────────

@router.get("/jogos/minidecks", response_model=List[MinideckResumo])
def listar_minidecks(
    auth: AuthenticatedUser = Depends(get_current_user),
) -> List[MinideckResumo]:
    """Lista minidecks ativos pra UI popular dropdown ao cadastrar
    partida. Inclui contagem de cartas (do tema) — útil pra UI mostrar
    "Saúde Mental — 104 cartas" e o professor saber se tema está
    completo."""
    with Session(get_engine()) as session:
        rows = session.execute(
            select(JogoMinideck)
            .where(JogoMinideck.ativo.is_(True))
            .order_by(JogoMinideck.nome_humano.asc())
        ).scalars().all()

        # Conta cartas por minideck em uma só query (N+1 pequeno).
        ids = [m.id for m in rows]
        n_por_md: Dict[uuid.UUID, int] = {}
        if ids:
            count_rows = session.execute(
                select(
                    CartaLacuna.minideck_id,
                    func.count(CartaLacuna.id),
                )
                .where(CartaLacuna.minideck_id.in_(ids))
                .group_by(CartaLacuna.minideck_id)
            ).all()
            n_por_md = {mid: int(n) for mid, n in count_rows}

        return [
            MinideckResumo(
                tema=m.tema, nome_humano=m.nome_humano,
                serie=m.serie, descricao=m.descricao,
                total_cartas=n_por_md.get(m.id, 0),
            )
            for m in rows
        ]


# ──────────────────────────────────────────────────────────────────────
# PATCH /portal/partidas/{id}
# ──────────────────────────────────────────────────────────────────────

@router.patch("/partidas/{partida_id}", response_model=PartidaDetail)
def patch_partida(
    partida_id: uuid.UUID,
    body: PartidaUpdate,
    auth: AuthenticatedUser = Depends(get_current_user),
) -> PartidaDetail:
    """Atualiza grupo_codigo, alunos_turma_ids e/ou prazo_reescrita.
    Imutáveis: atividade_id, tema (criar partida nova se trocar).

    Idempotente: PATCH sem campo é no-op (mas retorna detail pra
    UI sincronizar)."""
    if (body.grupo_codigo is None
            and body.alunos_turma_ids is None
            and body.prazo_reescrita is None):
        # No-op explícito é OK — frontend pode ter chamado defensivo.
        # Apenas retornamos o detail atual.
        pass

    with Session(get_engine()) as session:
        partida = session.get(PartidaJogo, partida_id)
        if partida is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Partida não encontrada",
            )
        ativ = _checa_professor_da_atividade(
            session, auth, partida.atividade_id,
        )

        if body.grupo_codigo is not None:
            grupo_novo = body.grupo_codigo.strip()
            if not grupo_novo:
                raise HTTPException(
                    status_code=400,
                    detail="grupo_codigo não pode ser vazio",
                )
            partida.grupo_codigo = grupo_novo

        if body.alunos_turma_ids is not None:
            seen: set = set()
            ids_novos: List[uuid.UUID] = []
            for aid in body.alunos_turma_ids:
                if aid not in seen:
                    seen.add(aid)
                    ids_novos.append(aid)
            alunos = session.execute(
                select(AlunoTurma).where(AlunoTurma.id.in_(ids_novos))
            ).scalars().all()
            achados = {a.id for a in alunos}
            faltando = [aid for aid in ids_novos if aid not in achados]
            if faltando:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"alunos_turma_ids não encontrados: "
                        f"{[str(x) for x in faltando]}"
                    ),
                )
            for a in alunos:
                if a.turma_id != ativ.turma_id:
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            f"aluno {a.id} pertence a turma diferente "
                            f"da atividade"
                        ),
                    )
            _set_alunos_partida(partida, ids_novos)

        if body.prazo_reescrita is not None:
            if body.prazo_reescrita.tzinfo is None:
                raise HTTPException(
                    status_code=400,
                    detail="prazo_reescrita precisa ser aware (com timezone)",
                )
            partida.prazo_reescrita = body.prazo_reescrita.astimezone(
                timezone.utc,
            )

        try:
            session.commit()
        except IntegrityError as exc:
            session.rollback()
            logger.warning(
                "patch_partida: violação UNIQUE id=%s: %s",
                partida_id, exc.orig,
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Já existe outra partida com esse grupo_codigo na "
                    "atividade"
                ),
            ) from None
        session.refresh(partida)
        minideck = session.get(JogoMinideck, partida.minideck_id)
        if minideck is None:
            minideck = JogoMinideck(tema="?", nome_humano="(removido)")
        return _to_partida_detail(session, partida, minideck)


# ──────────────────────────────────────────────────────────────────────
# DELETE /portal/partidas/{id}
# ──────────────────────────────────────────────────────────────────────

class _DeletePartidaResponse(BaseModel):
    deleted_id: str


@router.delete("/partidas/{partida_id}",
                response_model=_DeletePartidaResponse)
def deletar_partida(
    partida_id: uuid.UUID,
    auth: AuthenticatedUser = Depends(get_current_user),
) -> _DeletePartidaResponse:
    """Apaga partida. Hard delete (não soft).

    Bloqueia se já houver reescritas — protege trabalho do aluno.
    Mensagem de erro orienta a editar prazo (PATCH) em vez de
    deletar."""
    with Session(get_engine()) as session:
        partida = session.get(PartidaJogo, partida_id)
        if partida is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Partida não encontrada",
            )
        _checa_professor_da_atividade(
            session, auth, partida.atividade_id,
        )

        n_reescritas = session.execute(
            select(func.count(ReescritaIndividual.id))
            .where(ReescritaIndividual.partida_id == partida_id)
        ).scalar() or 0
        if n_reescritas > 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Partida tem {n_reescritas} reescrita(s) de "
                    f"alunos. Apagar destruiria trabalho. Use PATCH "
                    f"pra ajustar prazo ou crie partida nova."
                ),
            )

        session.delete(partida)
        session.commit()
        logger.info(
            "deletar_partida ok: id=%s professor=%s",
            partida_id, auth.user_id,
        )
        return _DeletePartidaResponse(deleted_id=str(partida_id))
