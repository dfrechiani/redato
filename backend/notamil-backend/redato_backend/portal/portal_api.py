"""Endpoints do portal `/portal/*` — M4 + M6.

M4: notificação de alunos via WhatsApp.
M6: gestão (turmas, atividades, alunos, dashboard simples).

Auth: JWT (M3). Permissions: `can_create_atividade` (professor) ou
`can_view_dashboard_escola` (coordenador).
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from redato_backend.portal.auth.middleware import (
    AuthenticatedUser, get_current_user,
)
from redato_backend.portal.auth.permissions import (
    can_create_atividade, can_view_dashboard_escola, can_view_turma,
)
from redato_backend.portal.db import get_engine
from redato_backend.portal.detectores import (
    canonical_detectores, get_canonical, humanize_detector, is_canonical,
)
from redato_backend.portal.models import (
    AlunoTurma, Atividade, Envio, Escola, Interaction, Missao, PdfGerado,
    Professor, Turma,
)
from redato_backend.missions.schemas import TOOLS_BY_MODE
from redato_backend.whatsapp import messages as MSG
from redato_backend.whatsapp import portal_link as PL


# Modos cuja rubrica/prompt já existe em código — só esses podem ser
# ativados como atividade no portal. Mantém em sincronia com:
#   - `redato_backend/missions/schemas.py:TOOLS_BY_MODE` (foco_c3,
#     foco_c4, foco_c5, completo_parcial)
#   - pipeline v2 legado em `dev_offline.py` que cobre `completo`
#     (OF14, modo full ENEM)
# Modos novos (foco_c1, foco_c2) entram aqui quando ganharem schema/
# prompt — ver `docs/redato/v3/series_oficinas_canonico.md`.
_MODOS_COM_PROMPT: set[str] = set(TOOLS_BY_MODE.keys()) | {"completo"}


def _modo_disponivel(modo: str) -> bool:
    """True se o modo tem rubrica/prompt implementado e pode virar
    atividade real. Modos sem prompt aparecem no catálogo (linha em
    `missoes`) mas o portal bloqueia ativação até o schema chegar."""
    return modo in _MODOS_COM_PROMPT


router = APIRouter(prefix="/portal", tags=["portal"])


_AUDIT_LOG = (
    Path(__file__).resolve().parents[2] / "data" / "portal" / "audit_log.jsonl"
)


def _audit(record: dict) -> None:
    _AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    record_full = {"ts": datetime.now(timezone.utc).isoformat(), **record}
    try:
        with _AUDIT_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record_full, ensure_ascii=False,
                                default=str) + "\n")
    except Exception:  # noqa: BLE001
        pass


def _format_data_pt(dt: datetime) -> str:
    return dt.strftime("%d/%m %H:%M")


def _check_permission_atividade(
    auth: AuthenticatedUser, atividade_id: uuid.UUID,
) -> None:
    """Levanta 404 se não existe; 403 se sem permission."""
    with Session(get_engine()) as session:
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
        # Permite professor responsável OU coordenador da escola
        ok = (
            can_create_atividade(auth, turma)
            or can_view_dashboard_escola(auth, turma.escola_id)
        )
        if not ok:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Sem permissão pra essa atividade",
            )


# ──────────────────────────────────────────────────────────────────────
# GET /portal/atividades/{id}/texto-notificacao
# ──────────────────────────────────────────────────────────────────────

class TextoNotificacaoResponse(BaseModel):
    texto: str
    quantidade_alunos: int
    missao_codigo: str
    missao_titulo: str
    data_fim_pt: str
    professor_nome: str


@router.get("/atividades/{atividade_id}/texto-notificacao",
            response_model=TextoNotificacaoResponse)
def texto_notificacao(
    atividade_id: uuid.UUID,
    auth: AuthenticatedUser = Depends(get_current_user),
) -> TextoNotificacaoResponse:
    """Retorna o texto que seria enviado pros alunos. Útil pra professor
    copiar e colar no grupo WhatsApp manualmente."""
    _check_permission_atividade(auth, atividade_id)
    ctx = PL.get_notificacao_context(atividade_id)
    if ctx is None:
        raise HTTPException(status_code=404,
                             detail="Atividade não encontrada")
    template = MSG.MSG_NOTIFICACAO_NOVA_ATIVIDADE
    # Texto neutro de 1ª pessoa (sem `primeiro_nome` específico — caller
    # vai personalizar por aluno se quiser)
    texto = template.format(
        primeiro_nome="<aluno>",
        nome_prof=ctx.professor_nome,
        missao_titulo=ctx.missao_titulo,
        missao_codigo=ctx.missao_codigo,
        data_fim_pt=_format_data_pt(ctx.data_fim),
    )
    return TextoNotificacaoResponse(
        texto=texto,
        quantidade_alunos=len(ctx.alunos),
        missao_codigo=ctx.missao_codigo,
        missao_titulo=ctx.missao_titulo,
        data_fim_pt=_format_data_pt(ctx.data_fim),
        professor_nome=ctx.professor_nome,
    )


# ──────────────────────────────────────────────────────────────────────
# POST /portal/atividades/{id}/notificar
# ──────────────────────────────────────────────────────────────────────

class NotificarResponse(BaseModel):
    enviadas: int
    falhas: List[dict]
    ja_notificada_em: Optional[str] = None


@router.post("/atividades/{atividade_id}/notificar",
             response_model=NotificarResponse)
def notificar_alunos(
    atividade_id: uuid.UUID,
    auth: AuthenticatedUser = Depends(get_current_user),
) -> NotificarResponse:
    """Dispara WhatsApp via Twilio pros alunos da turma. Idempotente:
    2ª chamada responde com `ja_notificada_em` sem reenviar."""
    _check_permission_atividade(auth, atividade_id)
    ctx = PL.get_notificacao_context(atividade_id)
    if ctx is None:
        raise HTTPException(status_code=404, detail="Atividade não encontrada")

    if ctx.notificacao_enviada_em is not None:
        return NotificarResponse(
            enviadas=0, falhas=[],
            ja_notificada_em=ctx.notificacao_enviada_em.isoformat(),
        )

    # Envia via Twilio (mesmo client do Caminho 2)
    enviadas = 0
    falhas: List[dict] = []
    twilio_disponivel = bool(os.getenv("TWILIO_ACCOUNT_SID"))

    for aluno in ctx.alunos:
        primeiro = (aluno.nome or "aluno").split()[0]
        body = MSG.MSG_NOTIFICACAO_NOVA_ATIVIDADE.format(
            primeiro_nome=primeiro,
            nome_prof=ctx.professor_nome,
            missao_titulo=ctx.missao_titulo,
            missao_codigo=ctx.missao_codigo,
            data_fim_pt=_format_data_pt(ctx.data_fim),
        )
        if not twilio_disponivel:
            # Modo dry-run: registra em audit log
            _audit({
                "op": "notificar-dry-run",
                "atividade_id": str(atividade_id),
                "aluno_turma_id": str(aluno.aluno_turma_id),
                "telefone": aluno.telefone,
                "body": body,
            })
            enviadas += 1
            continue
        try:
            from redato_backend.whatsapp import twilio_provider as TW
            TW.send_text(aluno.telefone, body)
            enviadas += 1
        except Exception as exc:  # noqa: BLE001
            falhas.append({
                "aluno_turma_id": str(aluno.aluno_turma_id),
                "telefone": aluno.telefone,
                "motivo": f"{type(exc).__name__}: {exc}",
            })

    PL.marcar_notificacao_enviada(atividade_id)
    _audit({
        "op": "notificar-executada",
        "atividade_id": str(atividade_id),
        "enviadas": enviadas, "falhas": len(falhas),
        "twilio": twilio_disponivel,
    })
    return NotificarResponse(enviadas=enviadas, falhas=falhas)


# ════════════════════════════════════════════════════════════════════════
# M6 — Endpoints de gestão (turmas, atividades, alunos)
# ════════════════════════════════════════════════════════════════════════


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────

def _parse_redato_output(raw: Optional[str]) -> Optional[Dict[str, Any]]:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return None


def _nota_total_de(redato: Optional[Dict[str, Any]]) -> Optional[int]:
    """Extrai nota do redato_output.

    Formatos aceitos (em ordem de prioridade):
    1. **Moderno (bot real do Claude, M9+)**: `modo` + `nota_c{N}_enem`
       em foco — escala 0-200 da competência focada. Em completo,
       `nota_total` ou `rubrica_rej.nota_total` (escala 0-1000).
    2. **Legacy (seeds sintéticos M6/M7)**: keys flat `nota_total`,
       `total`, `nota` (top-level), ou C1-C5 como sub-dicts somáveis.

    Retorna `None` se nenhum formato bate — bucket cai em "sem_nota".
    """
    if not redato:
        return None

    # 1. Formato moderno por modo
    modo = redato.get("modo")
    if isinstance(modo, str):
        if modo.startswith("foco_c"):
            # foco_c1, ..., foco_c5 → procura `nota_c{N}_enem`
            n = modo[len("foco_"):]  # "c1", "c2", ...
            v = redato.get(f"nota_{n}_enem")
            if isinstance(v, (int, float)):
                return int(v)
        elif modo.startswith("completo"):
            # completo / completo_parcial → nota_total_enem ou
            # rubrica_rej.nota_total (sub-dict)
            v = redato.get("nota_total_enem")
            if isinstance(v, (int, float)):
                return int(v)
            rubrica = redato.get("rubrica_rej")
            if isinstance(rubrica, dict):
                for key in ("nota_total", "total"):
                    v = rubrica.get(key)
                    if isinstance(v, (int, float)):
                        return int(v)

    # 2. Legacy / fallbacks flat
    for key in ("nota_total", "total", "nota"):
        v = redato.get(key)
        if isinstance(v, (int, float)):
            return int(v)
    # Soma C1-C5 se presentes
    soma = 0
    contadas = 0
    for ck in ("C1", "C2", "C3", "C4", "C5", "c1", "c2", "c3", "c4", "c5"):
        v = redato.get(ck)
        if isinstance(v, dict):
            v = v.get("nota") or v.get("score")
        if isinstance(v, (int, float)):
            soma += int(v)
            contadas += 1
    return soma if contadas == 5 else None


def _faixa_de_nota(nota: Optional[int]) -> str:
    if nota is None:
        return "sem_nota"
    if nota <= 200:
        return "0-200"
    if nota <= 400:
        return "201-400"
    if nota <= 600:
        return "401-600"
    if nota <= 800:
        return "601-800"
    return "801-1000"


def _get_turma_or_404(session: Session, turma_id: uuid.UUID) -> Turma:
    turma = session.get(Turma, turma_id)
    if turma is None or turma.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Turma não encontrada")
    return turma


def _check_view_turma(auth: AuthenticatedUser, turma: Turma) -> None:
    if not can_view_turma(auth, turma):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sem permissão pra essa turma",
        )


# ──────────────────────────────────────────────────────────────────────
# GET /portal/missoes
# ──────────────────────────────────────────────────────────────────────

class MissaoSchema(BaseModel):
    id: str
    codigo: str
    serie: str
    oficina_numero: int
    titulo: str
    modo_correcao: str
    # `False` = modo está no catálogo de séries (ex.: foco_c1/c2 da 2S)
    # mas ainda não tem schema/prompt — frontend desabilita opção no
    # dropdown até a rubrica ser definida. Decisão M9 (Opção B): em vez
    # de esconder, mostrar bloqueado pra dar visibilidade pedagógica.
    disponivel_para_ativacao: bool


@router.get("/missoes", response_model=List[MissaoSchema])
def listar_missoes(
    serie: Optional[str] = Query(
        None, description="Filtra catálogo por série (1S, 2S, 3S).",
        pattern="^(1S|2S|3S)$",
    ),
    auth: AuthenticatedUser = Depends(get_current_user),
) -> List[MissaoSchema]:
    """Catálogo de missões ativas — pra dropdown no modal de ativar missão.

    `serie` opcional filtra pelo segmento (1S/2S/3S). Sem filtro, retorna
    todas as ativas. Frontend usa o filtro pra mostrar só missões
    compatíveis com a série da turma — turma 1S não deve ver oficinas 2S
    no dropdown.

    Retorna ordenado por `oficina_numero`.
    """
    with Session(get_engine()) as session:
        stmt = select(Missao).where(Missao.ativa.is_(True))
        if serie:
            stmt = stmt.where(Missao.serie == serie)
        rows = session.execute(
            stmt.order_by(Missao.oficina_numero)
        ).scalars().all()
    return [
        MissaoSchema(
            id=str(m.id), codigo=m.codigo, serie=m.serie,
            oficina_numero=m.oficina_numero, titulo=m.titulo,
            modo_correcao=m.modo_correcao,
            disponivel_para_ativacao=_modo_disponivel(m.modo_correcao),
        )
        for m in rows
    ]


# ──────────────────────────────────────────────────────────────────────
# GET /portal/turmas
# ──────────────────────────────────────────────────────────────────────

class TurmaListItem(BaseModel):
    id: str
    codigo: str
    serie: str
    codigo_join: str
    ano_letivo: int
    ativa: bool
    n_alunos: int
    n_atividades_ativas: int
    n_atividades_encerradas: int
    professor_id: str
    professor_nome: str


@router.get("/turmas", response_model=List[TurmaListItem])
def listar_turmas(
    auth: AuthenticatedUser = Depends(get_current_user),
) -> List[TurmaListItem]:
    """Lista turmas visíveis pelo user.

    - Professor: turmas onde `professor_id == user.id`.
    - Coordenador: turmas da escola dele (qualquer professor).
    """
    with Session(get_engine()) as session:
        q = (
            select(Turma, Professor)
            .join(Professor, Professor.id == Turma.professor_id)
            .where(Turma.deleted_at.is_(None))
        )
        if auth.papel == "professor":
            q = q.where(Turma.professor_id == auth.user_id)
        else:
            q = q.where(Turma.escola_id == auth.escola_id)
        q = q.order_by(Professor.nome, Turma.serie, Turma.codigo)
        rows = session.execute(q).all()

        result: List[TurmaListItem] = []
        agora = datetime.now(timezone.utc)
        for turma, prof in rows:
            n_alunos = session.execute(
                select(func.count(AlunoTurma.id)).where(
                    AlunoTurma.turma_id == turma.id,
                    AlunoTurma.ativo.is_(True),
                )
            ).scalar() or 0
            n_ativas = session.execute(
                select(func.count(Atividade.id)).where(
                    Atividade.turma_id == turma.id,
                    Atividade.deleted_at.is_(None),
                    Atividade.data_inicio <= agora,
                    Atividade.data_fim >= agora,
                )
            ).scalar() or 0
            n_encerradas = session.execute(
                select(func.count(Atividade.id)).where(
                    Atividade.turma_id == turma.id,
                    Atividade.deleted_at.is_(None),
                    Atividade.data_fim < agora,
                )
            ).scalar() or 0
            result.append(TurmaListItem(
                id=str(turma.id), codigo=turma.codigo, serie=turma.serie,
                codigo_join=turma.codigo_join,
                ano_letivo=turma.ano_letivo, ativa=turma.ativa,
                n_alunos=int(n_alunos),
                n_atividades_ativas=int(n_ativas),
                n_atividades_encerradas=int(n_encerradas),
                professor_id=str(prof.id), professor_nome=prof.nome,
            ))
    return result


# ──────────────────────────────────────────────────────────────────────
# GET /portal/turmas/{turma_id}
# ──────────────────────────────────────────────────────────────────────

class AlunoTurmaSchema(BaseModel):
    id: str
    nome: str
    telefone_mascarado: str
    vinculado_em: str
    ativo: bool
    n_envios: int


class AtividadeListItem(BaseModel):
    id: str
    missao_id: str
    missao_codigo: str
    missao_titulo: str
    # M8 — frontend usa esses 2 pra renderizar "Oficina 10 — Jogo
    # Dissertativo (Foco C3)" sem expor o código técnico RJ1·OF10·MF.
    oficina_numero: int
    modo_correcao: str
    data_inicio: str
    data_fim: str
    status: str  # agendada | ativa | encerrada
    n_envios: int
    notificacao_enviada_em: Optional[str]


class TurmaDetailResponse(BaseModel):
    id: str
    codigo: str
    serie: str
    codigo_join: str
    ano_letivo: int
    ativa: bool
    professor_id: str
    professor_nome: str
    escola_id: str
    escola_nome: str
    pode_criar_atividade: bool
    alunos: List[AlunoTurmaSchema]
    atividades: List[AtividadeListItem]


def _mascarar_telefone(tel: str) -> str:
    """+5511999998888 → +55 11 99999-8***"""
    t = (tel or "").strip()
    if len(t) < 6:
        return t
    return t[:-3] + "***"


@router.get("/turmas/{turma_id}", response_model=TurmaDetailResponse)
def detalhe_turma(
    turma_id: uuid.UUID,
    auth: AuthenticatedUser = Depends(get_current_user),
) -> TurmaDetailResponse:
    """Turma + alunos ativos + atividades (com counts de envios)."""
    with Session(get_engine()) as session:
        turma = _get_turma_or_404(session, turma_id)
        _check_view_turma(auth, turma)
        prof = session.get(Professor, turma.professor_id)
        escola = session.get(Escola, turma.escola_id)

        alunos_rows = session.execute(
            select(AlunoTurma).where(
                AlunoTurma.turma_id == turma.id,
                AlunoTurma.ativo.is_(True),
            ).order_by(AlunoTurma.nome)
        ).scalars().all()

        alunos: List[AlunoTurmaSchema] = []
        for a in alunos_rows:
            n = session.execute(
                select(func.count(Envio.id)).where(
                    Envio.aluno_turma_id == a.id,
                )
            ).scalar() or 0
            alunos.append(AlunoTurmaSchema(
                id=str(a.id), nome=a.nome,
                telefone_mascarado=_mascarar_telefone(a.telefone),
                vinculado_em=a.vinculado_em.isoformat(),
                ativo=a.ativo, n_envios=int(n),
            ))

        atv_rows = session.execute(
            select(Atividade, Missao)
            .join(Missao, Missao.id == Atividade.missao_id)
            .where(
                Atividade.turma_id == turma.id,
                Atividade.deleted_at.is_(None),
            )
            .order_by(Atividade.data_inicio.desc())
        ).all()

        atividades: List[AtividadeListItem] = []
        for ativ, missao in atv_rows:
            n_envios = session.execute(
                select(func.count(Envio.id)).where(
                    Envio.atividade_id == ativ.id,
                )
            ).scalar() or 0
            atividades.append(AtividadeListItem(
                id=str(ativ.id),
                missao_id=str(missao.id),
                missao_codigo=missao.codigo,
                missao_titulo=missao.titulo,
                oficina_numero=missao.oficina_numero,
                modo_correcao=missao.modo_correcao,
                data_inicio=ativ.data_inicio.isoformat(),
                data_fim=ativ.data_fim.isoformat(),
                status=ativ.status,
                n_envios=int(n_envios),
                notificacao_enviada_em=(
                    ativ.notificacao_enviada_em.isoformat()
                    if ativ.notificacao_enviada_em else None
                ),
            ))

        return TurmaDetailResponse(
            id=str(turma.id), codigo=turma.codigo, serie=turma.serie,
            codigo_join=turma.codigo_join,
            ano_letivo=turma.ano_letivo, ativa=turma.ativa,
            professor_id=str(prof.id) if prof else "",
            professor_nome=prof.nome if prof else "",
            escola_id=str(escola.id) if escola else "",
            escola_nome=escola.nome if escola else "",
            pode_criar_atividade=can_create_atividade(auth, turma),
            alunos=alunos,
            atividades=atividades,
        )


# ──────────────────────────────────────────────────────────────────────
# POST /portal/atividades
# ──────────────────────────────────────────────────────────────────────

class CriarAtividadeRequest(BaseModel):
    turma_id: uuid.UUID
    missao_id: uuid.UUID
    data_inicio: datetime
    data_fim: datetime
    notificar_alunos: bool = False
    confirmar_duplicata: bool = False


class CriarAtividadeResponse(BaseModel):
    id: Optional[str] = None
    duplicate_warning: bool = False
    duplicata_atividade_id: Optional[str] = None
    notificacao_disparada: bool = False
    notificacao_enviadas: int = 0


@router.post("/atividades", response_model=CriarAtividadeResponse)
def criar_atividade(
    body: CriarAtividadeRequest,
    auth: AuthenticatedUser = Depends(get_current_user),
) -> CriarAtividadeResponse:
    """Cria atividade na turma. Validações:

    - turma e missão existem (404 senão);
    - data_fim > data_inicio (400 senão);
    - apenas o professor responsável pela turma cria (403 senão);
    - se já existe atividade ativa pra (turma, missão), retorna
      `duplicate_warning=True` e NÃO cria. Cliente confirma com
      `confirmar_duplicata=True` pra forçar criação.

    `notificar_alunos=True` chama o fluxo de /notificar logo após
    criar — útil pro modal "ativar missão" do M6. Se a notificação
    falhar, atividade segue criada (sem rollback).
    """
    if body.data_fim <= body.data_inicio:
        raise HTTPException(
            status_code=400, detail="data_fim deve ser posterior a data_inicio")

    with Session(get_engine()) as session:
        turma = _get_turma_or_404(session, body.turma_id)
        if not can_create_atividade(auth, turma):
            raise HTTPException(
                status_code=403,
                detail="Apenas o professor responsável pela turma cria atividades",
            )
        missao = session.get(Missao, body.missao_id)
        if missao is None or not missao.ativa:
            raise HTTPException(status_code=404, detail="Missão não encontrada")

        # Defesa em profundidade: o frontend já desabilita missões sem
        # rubrica no dropdown, mas alguém com curl bypassaria. Bloqueia
        # aqui também — se chegou request com modo sem schema, é bug
        # ou intenção maliciosa.
        if not _modo_disponivel(missao.modo_correcao):
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Missão '{missao.codigo}' usa modo "
                    f"'{missao.modo_correcao}' cuja rubrica ainda está "
                    "em desenvolvimento. Disponível em breve."
                ),
            )

        # Detecta duplicata: atividade não-encerrada (ativa OU agendada)
        # da mesma turma+missão.
        agora = datetime.now(timezone.utc)
        existente = session.execute(
            select(Atividade).where(
                Atividade.turma_id == turma.id,
                Atividade.missao_id == missao.id,
                Atividade.deleted_at.is_(None),
                Atividade.data_fim >= agora,
            )
            .order_by(Atividade.data_inicio.desc())
            .limit(1)
        ).scalar_one_or_none()

        if existente is not None and not body.confirmar_duplicata:
            return CriarAtividadeResponse(
                duplicate_warning=True,
                duplicata_atividade_id=str(existente.id),
            )

        nova = Atividade(
            turma_id=turma.id, missao_id=missao.id,
            data_inicio=body.data_inicio, data_fim=body.data_fim,
            criada_por_professor_id=auth.user_id,
        )
        session.add(nova)
        session.commit()
        session.refresh(nova)
        nova_id = nova.id
    _audit({
        "op": "atividade-criada",
        "atividade_id": str(nova_id),
        "turma_id": str(body.turma_id),
        "missao_id": str(body.missao_id),
        "by": str(auth.user_id),
    })

    notif_disparada = False
    notif_enviadas = 0
    if body.notificar_alunos:
        try:
            resp = notificar_alunos(nova_id, auth=auth)  # reusa lógica
            notif_disparada = True
            notif_enviadas = resp.enviadas
        except HTTPException:
            # Se notificar falhar, mantém atividade — cliente vê
            # notificacao_disparada=False e pode tentar de novo.
            pass

    return CriarAtividadeResponse(
        id=str(nova_id),
        duplicate_warning=False,
        notificacao_disparada=notif_disparada,
        notificacao_enviadas=notif_enviadas,
    )


# ──────────────────────────────────────────────────────────────────────
# GET /portal/atividades/{atividade_id}
# ──────────────────────────────────────────────────────────────────────

class EnvioListItem(BaseModel):
    aluno_turma_id: str
    aluno_nome: str
    envio_id: Optional[str]
    enviado_em: Optional[str]
    nota_total: Optional[int]
    faixa: str
    tem_feedback: bool


class DistribuicaoNotas(BaseModel):
    range_0_200: int = Field(0, alias="0-200")
    range_201_400: int = Field(0, alias="201-400")
    range_401_600: int = Field(0, alias="401-600")
    range_601_800: int = Field(0, alias="601-800")
    range_801_1000: int = Field(0, alias="801-1000")
    sem_nota: int = 0

    class Config:
        populate_by_name = True


class AtividadeDetailResponse(BaseModel):
    id: str
    turma_id: str
    turma_codigo: str
    turma_serie: str
    escola_nome: str
    professor_nome: str
    missao_id: str
    missao_codigo: str
    missao_titulo: str
    oficina_numero: int
    modo_correcao: str
    data_inicio: str
    data_fim: str
    status: str
    notificacao_enviada_em: Optional[str]
    pode_editar: bool
    n_alunos_total: int
    n_enviados: int
    n_pendentes: int
    distribuicao: Dict[str, int]
    top_detectores: List[Dict[str, Any]]
    envios: List[EnvioListItem]


def _detector_triggered(value: Any) -> bool:
    """Determina se uma chave de detector foi acionada."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.lower() not in ("", "false", "no", "não")
    if isinstance(value, dict):
        return bool(value.get("triggered") or value.get("ativo"))
    return False


def _detectores_acionados_de(out: Optional[Dict[str, Any]]) -> List[str]:
    """Lista códigos crus de detectores acionados num redato_output.

    Aceita 2 formatos:
    1. **Moderno (bot real)**: `redato["flags"]` é dict {nome: bool}.
       Cada chave True vira detector acionado (sem prefixo).
    2. **Legacy (seeds sintéticos M6/M7)**: keys top-level com prefixo
       `flag_/detector_/alerta_/aviso_`.

    Os 2 formatos coexistem — se ambos estiverem presentes, ambos são
    coletados (sem dedupe estrito; `_coletar_top_detectores` faz a
    contagem).
    """
    if not out:
        return []
    codigos: List[str] = []

    # 1. Formato moderno: out["flags"] é sub-dict
    flags_dict = out.get("flags")
    if isinstance(flags_dict, dict):
        for k, v in flags_dict.items():
            if isinstance(k, str) and _detector_triggered(v):
                codigos.append(k)

    # 2. Formato legacy: keys top-level com prefixo flag_/detector_/...
    for k, v in out.items():
        if not isinstance(k, str):
            continue
        kl = k.lower()
        if not (kl.startswith("flag_") or kl.startswith("detector_")
                or kl.startswith("alerta_") or kl.startswith("aviso_")):
            continue
        if _detector_triggered(v):
            codigos.append(k)
    return codigos


def _coletar_top_detectores(
    interactions: List[Interaction], top_n: int = 3,
    *, only_canonical: bool = True,
) -> List[Dict[str, Any]]:
    """Conta detectores acionados nos redato_outputs e retorna top-N.

    M7: filtra pra detectores canônicos (lista em
    `redato_backend.portal.detectores`). Detectores desconhecidos
    podem ser incluídos se `only_canonical=False`.
    """
    counts: Dict[str, int] = {}
    for it in interactions:
        out = _parse_redato_output(it.redato_output)
        for codigo in _detectores_acionados_de(out):
            if only_canonical and not is_canonical(codigo):
                continue
            canon = get_canonical(codigo)
            chave = canon.codigo if canon else codigo
            counts[chave] = counts.get(chave, 0) + 1
    ordenados = sorted(counts.items(), key=lambda kv: -kv[1])[:top_n]
    return [
        {
            "detector": k,
            "codigo": k,
            "nome": humanize_detector(k),
            "ocorrencias": v,
        }
        for k, v in ordenados
    ]


def _contar_detectores_outros(interactions: List[Interaction]) -> int:
    """Soma de acionamentos de detectores NÃO canônicos.

    Útil pro card "outros" no dashboard.
    """
    n = 0
    for it in interactions:
        out = _parse_redato_output(it.redato_output)
        for codigo in _detectores_acionados_de(out):
            if not is_canonical(codigo):
                n += 1
    return n


@router.get("/atividades/{atividade_id}", response_model=AtividadeDetailResponse)
def detalhe_atividade(
    atividade_id: uuid.UUID,
    auth: AuthenticatedUser = Depends(get_current_user),
) -> AtividadeDetailResponse:
    """Detalhe da atividade + tabela de envios + agregados pra dashboard."""
    _check_permission_atividade(auth, atividade_id)
    with Session(get_engine()) as session:
        ativ = session.get(Atividade, atividade_id)
        if ativ is None or ativ.deleted_at is not None:
            raise HTTPException(status_code=404, detail="Atividade não encontrada")
        turma = session.get(Turma, ativ.turma_id)
        missao = session.get(Missao, ativ.missao_id)
        prof = session.get(Professor, turma.professor_id) if turma else None
        escola = session.get(Escola, turma.escola_id) if turma else None

        # Lista todos os alunos ativos da turma — pendentes incluídos.
        alunos = session.execute(
            select(AlunoTurma).where(
                AlunoTurma.turma_id == ativ.turma_id,
                AlunoTurma.ativo.is_(True),
            ).order_by(AlunoTurma.nome)
        ).scalars().all()

        # Envios + interactions associados.
        envios_rows = session.execute(
            select(Envio).where(Envio.atividade_id == ativ.id)
        ).scalars().all()

        envio_por_aluno: Dict[uuid.UUID, Envio] = {
            e.aluno_turma_id: e for e in envios_rows
        }
        interactions: List[Interaction] = []
        for e in envios_rows:
            if e.interaction_id:
                it = session.get(Interaction, e.interaction_id)
                if it is not None:
                    interactions.append(it)

        # Distribuição
        distrib: Dict[str, int] = {
            "0-200": 0, "201-400": 0, "401-600": 0,
            "601-800": 0, "801-1000": 0, "sem_nota": 0,
        }
        notas_por_envio: Dict[uuid.UUID, Optional[int]] = {}
        for it in interactions:
            out = _parse_redato_output(it.redato_output)
            nota = _nota_total_de(out)
            if it.envio_id is not None:
                notas_por_envio[it.envio_id] = nota
            distrib[_faixa_de_nota(nota)] += 1

        envios_response: List[EnvioListItem] = []
        for a in alunos:
            envio = envio_por_aluno.get(a.id)
            envio_id_str = str(envio.id) if envio else None
            nota = notas_por_envio.get(envio.id) if envio else None
            envios_response.append(EnvioListItem(
                aluno_turma_id=str(a.id),
                aluno_nome=a.nome,
                envio_id=envio_id_str,
                enviado_em=envio.enviado_em.isoformat() if envio else None,
                nota_total=nota,
                faixa=_faixa_de_nota(nota),
                tem_feedback=bool(envio and envio.interaction_id),
            ))

        n_total = len(alunos)
        n_enviados = len(envio_por_aluno)
        # Pendentes não entram na distribuição (sem foto enviada). Caso
        # alunos pendentes tenham sido contados em sem_nota, removemos:
        distrib_clean = dict(distrib)
        # sem_nota foi contado só pra envios que existem mas falharam OCR/grade

        return AtividadeDetailResponse(
            id=str(ativ.id),
            turma_id=str(turma.id) if turma else "",
            turma_codigo=turma.codigo if turma else "",
            turma_serie=turma.serie if turma else "",
            escola_nome=escola.nome if escola else "",
            professor_nome=prof.nome if prof else "",
            missao_id=str(missao.id) if missao else "",
            missao_codigo=missao.codigo if missao else "",
            missao_titulo=missao.titulo if missao else "",
            oficina_numero=missao.oficina_numero if missao else 0,
            modo_correcao=missao.modo_correcao if missao else "",
            data_inicio=ativ.data_inicio.isoformat(),
            data_fim=ativ.data_fim.isoformat(),
            status=ativ.status,
            notificacao_enviada_em=(
                ativ.notificacao_enviada_em.isoformat()
                if ativ.notificacao_enviada_em else None
            ),
            pode_editar=can_create_atividade(auth, turma) if turma else False,
            n_alunos_total=n_total,
            n_enviados=n_enviados,
            n_pendentes=max(0, n_total - n_enviados),
            distribuicao=distrib_clean,
            top_detectores=_coletar_top_detectores(interactions),
            envios=envios_response,
        )


# ──────────────────────────────────────────────────────────────────────
# PATCH /portal/atividades/{atividade_id}
# ──────────────────────────────────────────────────────────────────────

class PatchAtividadeRequest(BaseModel):
    data_inicio: Optional[datetime] = None
    data_fim: Optional[datetime] = None


@router.patch("/atividades/{atividade_id}", response_model=AtividadeListItem)
def patch_atividade(
    atividade_id: uuid.UUID,
    body: PatchAtividadeRequest,
    auth: AuthenticatedUser = Depends(get_current_user),
) -> AtividadeListItem:
    """Atualiza data_inicio e/ou data_fim. Apenas professor da turma.

    Sem campos a atualizar: 400. Datas inconsistentes (fim <= início):
    400. Atividade encerrada pode ser reaberta movendo data_fim.
    """
    if body.data_inicio is None and body.data_fim is None:
        raise HTTPException(status_code=400, detail="Nada a atualizar")
    with Session(get_engine()) as session:
        ativ = session.get(Atividade, atividade_id)
        if ativ is None or ativ.deleted_at is not None:
            raise HTTPException(status_code=404, detail="Atividade não encontrada")
        turma = session.get(Turma, ativ.turma_id)
        if turma is None:
            raise HTTPException(status_code=404, detail="Turma não encontrada")
        if not can_create_atividade(auth, turma):
            raise HTTPException(
                status_code=403,
                detail="Apenas o professor responsável pode editar a atividade",
            )
        novo_inicio = body.data_inicio or ativ.data_inicio
        novo_fim = body.data_fim or ativ.data_fim
        if novo_fim <= novo_inicio:
            raise HTTPException(
                status_code=400,
                detail="data_fim deve ser posterior a data_inicio",
            )
        ativ.data_inicio = novo_inicio
        ativ.data_fim = novo_fim
        session.commit()
        session.refresh(ativ)
        missao = session.get(Missao, ativ.missao_id)
        n_envios = session.execute(
            select(func.count(Envio.id)).where(Envio.atividade_id == ativ.id)
        ).scalar() or 0
        _audit({
            "op": "atividade-editada",
            "atividade_id": str(atividade_id),
            "by": str(auth.user_id),
            "novo_inicio": novo_inicio.isoformat(),
            "novo_fim": novo_fim.isoformat(),
        })
        return AtividadeListItem(
            id=str(ativ.id),
            missao_id=str(missao.id) if missao else "",
            missao_codigo=missao.codigo if missao else "",
            missao_titulo=missao.titulo if missao else "",
            oficina_numero=missao.oficina_numero if missao else 0,
            modo_correcao=missao.modo_correcao if missao else "",
            data_inicio=ativ.data_inicio.isoformat(),
            data_fim=ativ.data_fim.isoformat(),
            status=ativ.status,
            n_envios=int(n_envios),
            notificacao_enviada_em=(
                ativ.notificacao_enviada_em.isoformat()
                if ativ.notificacao_enviada_em else None
            ),
        )


# ──────────────────────────────────────────────────────────────────────
# POST /portal/atividades/{atividade_id}/encerrar
# ──────────────────────────────────────────────────────────────────────

@router.post("/atividades/{atividade_id}/encerrar",
             response_model=AtividadeListItem)
def encerrar_atividade(
    atividade_id: uuid.UUID,
    auth: AuthenticatedUser = Depends(get_current_user),
) -> AtividadeListItem:
    """Atalho: seta data_fim = now(). Idempotente — encerrar de novo
    avança data_fim pra now() atual. Apenas professor."""
    with Session(get_engine()) as session:
        ativ = session.get(Atividade, atividade_id)
        if ativ is None or ativ.deleted_at is not None:
            raise HTTPException(status_code=404, detail="Atividade não encontrada")
        turma = session.get(Turma, ativ.turma_id)
        if turma is None:
            raise HTTPException(status_code=404, detail="Turma não encontrada")
        if not can_create_atividade(auth, turma):
            raise HTTPException(
                status_code=403,
                detail="Apenas o professor responsável pode encerrar",
            )
        agora = datetime.now(timezone.utc)
        # Garante que data_inicio < data_fim (CHECK constraint)
        if agora <= ativ.data_inicio:
            ativ.data_inicio = agora
        ativ.data_fim = agora
        session.commit()
        session.refresh(ativ)
        missao = session.get(Missao, ativ.missao_id)
        n_envios = session.execute(
            select(func.count(Envio.id)).where(Envio.atividade_id == ativ.id)
        ).scalar() or 0
        _audit({
            "op": "atividade-encerrada",
            "atividade_id": str(atividade_id),
            "by": str(auth.user_id),
        })
        return AtividadeListItem(
            id=str(ativ.id),
            missao_id=str(missao.id) if missao else "",
            missao_codigo=missao.codigo if missao else "",
            missao_titulo=missao.titulo if missao else "",
            oficina_numero=missao.oficina_numero if missao else 0,
            modo_correcao=missao.modo_correcao if missao else "",
            data_inicio=ativ.data_inicio.isoformat(),
            data_fim=ativ.data_fim.isoformat(),
            status=ativ.status,
            n_envios=int(n_envios),
            notificacao_enviada_em=(
                ativ.notificacao_enviada_em.isoformat()
                if ativ.notificacao_enviada_em else None
            ),
        )


# ──────────────────────────────────────────────────────────────────────
# GET /portal/atividades/{atividade_id}/envios/{aluno_turma_id}
# ──────────────────────────────────────────────────────────────────────

class FaixaQualitativa(BaseModel):
    competencia: str
    nota: Optional[int]
    faixa: str  # "Insuficiente" | "Bom" | etc.


class EnvioFeedbackResponse(BaseModel):
    atividade_id: str
    missao_codigo: str
    missao_titulo: str
    oficina_numero: int
    modo_correcao: str
    aluno_id: str
    aluno_nome: str
    enviado_em: Optional[str]
    # `foto_url`: URL relativa ao frontend (proxy /api/portal/...) que
    # serve a imagem com auth do JWT-cookie. NÃO usar mais filesystem
    # path absoluto do backend — `<img src=>` não passa Authorization
    # header e arquivos não são servidos pelo Next.js.
    foto_url: Optional[str]
    foto_hash: Optional[str]
    texto_transcrito: Optional[str]
    nota_total: Optional[int]
    faixas: List[FaixaQualitativa]
    audit_pedagogico: Optional[str]
    detectores: List[Dict[str, Any]]
    ocr_quality_issues: List[str]
    raw_output: Optional[Dict[str, Any]]


def _faixa_qualitativa(nota: Optional[int]) -> str:
    if nota is None:
        return "sem_nota"
    if nota <= 80:
        return "Insuficiente"
    if nota <= 120:
        return "Regular"
    if nota <= 160:
        return "Bom"
    return "Excelente"


@router.get("/atividades/{atividade_id}/envios/{aluno_turma_id}",
            response_model=EnvioFeedbackResponse)
def detalhe_envio(
    atividade_id: uuid.UUID,
    aluno_turma_id: uuid.UUID,
    auth: AuthenticatedUser = Depends(get_current_user),
) -> EnvioFeedbackResponse:
    """Feedback completo do aluno na atividade.

    Inclui: foto, transcrição OCR, nota total, competências (C1-C5
    com faixa qualitativa), audit pedagógico em prosa e detectores
    acionados.
    """
    _check_permission_atividade(auth, atividade_id)
    with Session(get_engine()) as session:
        ativ = session.get(Atividade, atividade_id)
        missao = session.get(Missao, ativ.missao_id) if ativ else None
        aluno = session.get(AlunoTurma, aluno_turma_id)
        if aluno is None or aluno.turma_id != ativ.turma_id:
            raise HTTPException(status_code=404, detail="Aluno não encontrado nessa turma")
        envio = session.execute(
            select(Envio).where(
                Envio.atividade_id == atividade_id,
                Envio.aluno_turma_id == aluno_turma_id,
            )
        ).scalar_one_or_none()
        if envio is None:
            return EnvioFeedbackResponse(
                atividade_id=str(atividade_id),
                missao_codigo=missao.codigo if missao else "",
                missao_titulo=missao.titulo if missao else "",
                oficina_numero=missao.oficina_numero if missao else 0,
                modo_correcao=missao.modo_correcao if missao else "",
                aluno_id=str(aluno.id), aluno_nome=aluno.nome,
                enviado_em=None,
                foto_url=None, foto_hash=None, texto_transcrito=None,
                nota_total=None, faixas=[], audit_pedagogico=None,
                detectores=[], ocr_quality_issues=[], raw_output=None,
            )
        interaction = (
            session.get(Interaction, envio.interaction_id)
            if envio.interaction_id else None
        )
        out = _parse_redato_output(
            interaction.redato_output if interaction else None
        )
        nota_total = _nota_total_de(out)

        faixas: List[FaixaQualitativa] = []
        if out:
            for ck in ("C1", "C2", "C3", "C4", "C5"):
                v = out.get(ck) or out.get(ck.lower())
                nota_c: Optional[int] = None
                if isinstance(v, dict):
                    raw = v.get("nota") or v.get("score")
                    if isinstance(raw, (int, float)):
                        nota_c = int(raw)
                elif isinstance(v, (int, float)):
                    nota_c = int(v)
                if nota_c is not None:
                    faixas.append(FaixaQualitativa(
                        competencia=ck, nota=nota_c,
                        faixa=_faixa_qualitativa(nota_c),
                    ))

        detectores: List[Dict[str, Any]] = []
        if out:
            for k, v in out.items():
                if not isinstance(k, str):
                    continue
                kl = k.lower()
                if not (kl.startswith("flag_") or kl.startswith("detector_")
                        or kl.startswith("alerta_") or kl.startswith("aviso_")):
                    continue
                triggered = bool(v) if not isinstance(v, dict) else bool(
                    v.get("triggered") or v.get("ativo")
                )
                if triggered:
                    canon = get_canonical(k)
                    detectores.append({
                        "detector": k,
                        "codigo": canon.codigo if canon else k,
                        "nome": humanize_detector(k),
                        "categoria": canon.categoria if canon else "forma",
                        "severidade": canon.severidade if canon else "media",
                        "canonical": canon is not None,
                        "detalhe": (
                            v.get("detalhe") if isinstance(v, dict) else None
                        ),
                    })

        audit_prose: Optional[str] = None
        if out:
            for k in ("audit", "audit_pedagogico", "feedback", "comentario_geral"):
                if isinstance(out.get(k), str):
                    audit_prose = out.get(k)
                    break

        try:
            issues = json.loads(interaction.ocr_quality_issues) if (
                interaction and interaction.ocr_quality_issues
            ) else []
        except (ValueError, TypeError):
            issues = []

        # `foto_url` aponta pro proxy frontend, que injeta o JWT-cookie
        # e encaminha pra `/portal/atividades/{aid}/envios/{atid}/foto`.
        # Só populamos quando a interação tem foto persistida — caso
        # contrário frontend renderiza fallback "Foto não disponível".
        foto_url: Optional[str] = None
        if interaction is not None and interaction.foto_path:
            foto_url = (
                f"/api/portal/atividades/{atividade_id}"
                f"/envios/{aluno_turma_id}/foto"
            )

        return EnvioFeedbackResponse(
            atividade_id=str(atividade_id),
            missao_codigo=missao.codigo if missao else "",
            missao_titulo=missao.titulo if missao else "",
            oficina_numero=missao.oficina_numero if missao else 0,
            modo_correcao=missao.modo_correcao if missao else "",
            aluno_id=str(aluno.id), aluno_nome=aluno.nome,
            enviado_em=envio.enviado_em.isoformat(),
            foto_url=foto_url,
            foto_hash=interaction.foto_hash if interaction else None,
            texto_transcrito=interaction.texto_transcrito if interaction else None,
            nota_total=nota_total,
            faixas=faixas,
            audit_pedagogico=audit_prose,
            detectores=detectores,
            ocr_quality_issues=issues if isinstance(issues, list) else [],
            raw_output=out,
        )


# ──────────────────────────────────────────────────────────────────────
# GET /portal/atividades/{atividade_id}/envios/{aluno_turma_id}/foto
# ──────────────────────────────────────────────────────────────────────

# Mapeamento extensão → MIME. Lista curta — o que o WhatsApp envia
# (sempre image/jpeg via Twilio) + variações comuns que professores
# poderiam upload manualmente no futuro.
_FOTO_MIME_BY_EXT = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".heic": "image/heic",
    ".heif": "image/heif",
}


@router.get("/atividades/{atividade_id}/envios/{aluno_turma_id}/foto")
def baixar_foto_envio(
    atividade_id: uuid.UUID,
    aluno_turma_id: uuid.UUID,
    auth: AuthenticatedUser = Depends(get_current_user),
) -> FileResponse:
    """Stream da foto da redação enviada pelo aluno.

    Permission: mesma do `detalhe_envio` — professor da turma OU
    admin/coordenador da escola. Frontend usa via proxy
    `/api/portal/...` que injeta o JWT do cookie httpOnly.

    Retorna:
    - 404 se atividade/aluno não existe ou não há envio
    - 410 se path no DB mas arquivo sumiu (volume Railway perdido)
    - 200 com a imagem nos formatos comuns do WhatsApp
    """
    _check_permission_atividade(auth, atividade_id)
    with Session(get_engine()) as session:
        ativ = session.get(Atividade, atividade_id)
        if ativ is None or ativ.deleted_at is not None:
            raise HTTPException(status_code=404, detail="Atividade não encontrada")
        aluno = session.get(AlunoTurma, aluno_turma_id)
        if aluno is None or aluno.turma_id != ativ.turma_id:
            raise HTTPException(
                status_code=404,
                detail="Aluno não encontrado nessa turma",
            )
        envio = session.execute(
            select(Envio).where(
                Envio.atividade_id == atividade_id,
                Envio.aluno_turma_id == aluno_turma_id,
            )
        ).scalar_one_or_none()
        if envio is None or envio.interaction_id is None:
            raise HTTPException(status_code=404, detail="Envio não encontrado")
        interaction = session.get(Interaction, envio.interaction_id)
        foto_path_str = (
            interaction.foto_path if interaction is not None else None
        )

    if not foto_path_str:
        raise HTTPException(status_code=404, detail="Sem foto registrada")

    foto_path = Path(foto_path_str)
    if not foto_path.is_absolute():
        # Histórico: alguns paths foram salvos relativos ao cwd do
        # backend. Normaliza pro filesystem.
        backend_root = Path(__file__).resolve().parents[2]
        foto_path = (backend_root / foto_path).resolve()
    if not foto_path.exists() or not foto_path.is_file():
        raise HTTPException(
            status_code=410,
            detail="Arquivo da foto não está mais disponível no servidor",
        )

    mime = _FOTO_MIME_BY_EXT.get(foto_path.suffix.lower(), "image/jpeg")
    return FileResponse(path=str(foto_path), media_type=mime)


# ──────────────────────────────────────────────────────────────────────
# PATCH /portal/turmas/{turma_id}/alunos/{aluno_turma_id}
# ──────────────────────────────────────────────────────────────────────

class PatchAlunoRequest(BaseModel):
    ativo: bool


@router.patch("/turmas/{turma_id}/alunos/{aluno_turma_id}")
def patch_aluno(
    turma_id: uuid.UUID,
    aluno_turma_id: uuid.UUID,
    body: PatchAlunoRequest,
    auth: AuthenticatedUser = Depends(get_current_user),
) -> dict:
    """Marca aluno ativo/inativo na turma. Apenas professor da turma.

    NÃO faz DELETE físico — preserva histórico de envios pra dashboards
    históricos. Bot rejeita aluno inativo na próxima foto."""
    with Session(get_engine()) as session:
        turma = _get_turma_or_404(session, turma_id)
        if not can_create_atividade(auth, turma):
            raise HTTPException(
                status_code=403,
                detail="Apenas o professor responsável pode mexer em alunos",
            )
        aluno = session.get(AlunoTurma, aluno_turma_id)
        if aluno is None or aluno.turma_id != turma_id:
            raise HTTPException(
                status_code=404, detail="Aluno não encontrado nessa turma")
        aluno.ativo = body.ativo
        session.commit()
    _audit({
        "op": "aluno-status",
        "turma_id": str(turma_id),
        "aluno_turma_id": str(aluno_turma_id),
        "ativo": body.ativo,
        "by": str(auth.user_id),
    })
    return {"sucesso": True, "ativo": body.ativo}


# ════════════════════════════════════════════════════════════════════════
# M7 — Dashboards (turma, escola, evolução do aluno)
# ════════════════════════════════════════════════════════════════════════


# ──────────────────────────────────────────────────────────────────────
# Helpers de modo / faixa
# ──────────────────────────────────────────────────────────────────────

_FOCO_BUCKETS = ["0-40", "41-80", "81-120", "121-160", "161-200"]
_COMPLETO_BUCKETS = ["0-200", "201-400", "401-600", "601-800", "801-1000"]


def _modo_bucket(modo: Optional[str]) -> str:
    """Retorna 'foco' ou 'completo' baseado no modo de correção."""
    if modo and modo.startswith("foco_"):
        return "foco"
    return "completo"


def _bucket_foco(nota: Optional[int]) -> Optional[str]:
    if nota is None:
        return None
    if nota <= 40:
        return "0-40"
    if nota <= 80:
        return "41-80"
    if nota <= 120:
        return "81-120"
    if nota <= 160:
        return "121-160"
    return "161-200"


def _bucket_completo(nota: Optional[int]) -> Optional[str]:
    if nota is None:
        return None
    if nota <= 200:
        return "0-200"
    if nota <= 400:
        return "201-400"
    if nota <= 600:
        return "401-600"
    if nota <= 800:
        return "601-800"
    return "801-1000"


def _empty_dist_foco() -> Dict[str, int]:
    return {b: 0 for b in _FOCO_BUCKETS}


def _empty_dist_completo() -> Dict[str, int]:
    return {b: 0 for b in _COMPLETO_BUCKETS}


def _is_insuficiente(modo: Optional[str], nota: Optional[int]) -> bool:
    """Faixa "insuficiente" pra alerta de aluno em risco.

    - Foco (0-200): nota <= 80 (médias C abaixo de 80 por competência).
    - Completo (0-1000): nota <= 400 (média < 80 por competência).
    """
    if nota is None:
        return False
    if _modo_bucket(modo) == "foco":
        return nota <= 80
    return nota <= 400


# ──────────────────────────────────────────────────────────────────────
# Coletor compartilhado: envios + interactions de uma lista de atividades
# ──────────────────────────────────────────────────────────────────────

def _coletar_envios_full(
    session: Session, atividade_ids: List[uuid.UUID],
) -> List[Dict[str, Any]]:
    """Pra cada envio nas atividades dadas, retorna dict denormalizado:
        atividade_id, missao_codigo, missao_titulo, modo,
        aluno_turma_id, aluno_nome, enviado_em, nota_total,
        interaction (Interaction|None)

    Usado pelos dashboards. Uma única query pra interactions evita N+1.
    """
    if not atividade_ids:
        return []

    rows = session.execute(
        select(Envio, Atividade, Missao, AlunoTurma)
        .join(Atividade, Atividade.id == Envio.atividade_id)
        .join(Missao, Missao.id == Atividade.missao_id)
        .join(AlunoTurma, AlunoTurma.id == Envio.aluno_turma_id)
        .where(Envio.atividade_id.in_(atividade_ids))
        .order_by(Envio.enviado_em)
    ).all()

    interaction_ids = [
        e.interaction_id for (e, _, _, _) in rows if e.interaction_id
    ]
    interactions_by_id: Dict[int, Interaction] = {}
    if interaction_ids:
        its = session.execute(
            select(Interaction).where(Interaction.id.in_(interaction_ids))
        ).scalars().all()
        interactions_by_id = {it.id: it for it in its}

    out: List[Dict[str, Any]] = []
    for envio, ativ, missao, aluno in rows:
        it = (
            interactions_by_id.get(envio.interaction_id)
            if envio.interaction_id else None
        )
        redato = _parse_redato_output(it.redato_output) if it else None
        nota = _nota_total_de(redato)
        out.append({
            "atividade_id": ativ.id,
            "missao_codigo": missao.codigo,
            "missao_titulo": missao.titulo,
            "oficina_numero": missao.oficina_numero,
            "modo": missao.modo_correcao,
            "aluno_turma_id": aluno.id,
            "aluno_nome": aluno.nome,
            "enviado_em": envio.enviado_em,
            "nota_total": nota,
            "redato_output": redato,
            "interaction": it,
        })
    return out


def _alunos_em_risco(
    envios: List[Dict[str, Any]], min_missoes_baixa: int = 2,
) -> List[Dict[str, Any]]:
    """Identifica alunos com ≥ min_missoes_baixa missões em faixa
    insuficiente. Retorna ordenado pela contagem desc."""
    contador: Dict[uuid.UUID, Dict[str, Any]] = {}
    for e in envios:
        if not _is_insuficiente(e["modo"], e["nota_total"]):
            continue
        slot = contador.setdefault(e["aluno_turma_id"], {
            "aluno_id": str(e["aluno_turma_id"]),
            "nome": e["aluno_nome"],
            "n_missoes_baixa": 0,
            "ultima_nota": None,
            "ultima_em": None,
        })
        slot["n_missoes_baixa"] += 1
        if (slot["ultima_em"] is None
                or e["enviado_em"] > slot["ultima_em"]):
            slot["ultima_em"] = e["enviado_em"]
            slot["ultima_nota"] = e["nota_total"]

    em_risco = [
        {
            "aluno_id": s["aluno_id"], "nome": s["nome"],
            "n_missoes_baixa": s["n_missoes_baixa"],
            "ultima_nota": s["ultima_nota"],
        }
        for s in contador.values()
        if s["n_missoes_baixa"] >= min_missoes_baixa
    ]
    em_risco.sort(key=lambda x: -x["n_missoes_baixa"])
    return em_risco


def _distribuicao_por_modo(
    envios: List[Dict[str, Any]],
) -> Dict[str, Dict[str, int]]:
    """Distribuição segregada por modo (foco vs completo)."""
    foco = _empty_dist_foco()
    completo = _empty_dist_completo()
    for e in envios:
        nota = e["nota_total"]
        if nota is None:
            continue
        if _modo_bucket(e["modo"]) == "foco":
            b = _bucket_foco(nota)
            if b:
                foco[b] += 1
        else:
            b = _bucket_completo(nota)
            if b:
                completo[b] += 1
    return {"foco": foco, "completo": completo}


def _evolucao_temporal(
    envios: List[Dict[str, Any]], group_by_atividade: bool = True,
) -> List[Dict[str, Any]]:
    """Série temporal: média de nota por atividade (ordenado por data).

    Útil pra chart de linha. Ignora envios sem nota."""
    por_ativ: Dict[uuid.UUID, Dict[str, Any]] = {}
    for e in envios:
        if e["nota_total"] is None:
            continue
        slot = por_ativ.setdefault(e["atividade_id"], {
            "atividade_id": str(e["atividade_id"]),
            "missao_codigo": e["missao_codigo"],
            "missao_titulo": e["missao_titulo"],
            "modo": e["modo"],
            "data": e["enviado_em"],
            "soma": 0,
            "n": 0,
        })
        slot["soma"] += e["nota_total"]
        slot["n"] += 1
        if e["enviado_em"] < slot["data"]:
            slot["data"] = e["enviado_em"]

    serie = [
        {
            "atividade_id": s["atividade_id"],
            "missao_codigo": s["missao_codigo"],
            "missao_titulo": s["missao_titulo"],
            "modo": s["modo"],
            "data": s["data"].isoformat() if hasattr(s["data"], "isoformat") else s["data"],
            "nota_media": round(s["soma"] / s["n"]) if s["n"] else 0,
            "n_envios": s["n"],
        }
        for s in por_ativ.values()
    ]
    serie.sort(key=lambda x: x["data"])
    return serie


# ──────────────────────────────────────────────────────────────────────
# GET /portal/turmas/{turma_id}/dashboard
# ──────────────────────────────────────────────────────────────────────

class TurmaDashboardResumo(BaseModel):
    id: str
    codigo: str
    n_alunos_ativos: int


class AlunoEmRisco(BaseModel):
    aluno_id: str
    nome: str
    n_missoes_baixa: int
    ultima_nota: Optional[int]


class TopDetector(BaseModel):
    codigo: str
    nome: str
    contagem: int


class EvolucaoPonto(BaseModel):
    atividade_id: str
    missao_codigo: str
    missao_titulo: str
    modo: str
    data: str
    nota_media: int
    n_envios: int


class TurmaDashboardResponse(BaseModel):
    turma: TurmaDashboardResumo
    atividades_total: int
    atividades_ativas: int
    atividades_encerradas: int
    distribuicao_notas: Dict[str, Dict[str, int]]
    top_detectores: List[TopDetector]
    outros_detectores: int
    alunos_em_risco: List[AlunoEmRisco]
    evolucao_turma: List[EvolucaoPonto]
    n_envios_total: int


@router.get("/turmas/{turma_id}/dashboard",
            response_model=TurmaDashboardResponse)
def dashboard_turma(
    turma_id: uuid.UUID,
    auth: AuthenticatedUser = Depends(get_current_user),
) -> TurmaDashboardResponse:
    """Dashboard agregado da turma — visível pra prof responsável OU
    coord da escola."""
    with Session(get_engine()) as session:
        turma = _get_turma_or_404(session, turma_id)
        _check_view_turma(auth, turma)

        n_alunos = session.execute(
            select(func.count(AlunoTurma.id)).where(
                AlunoTurma.turma_id == turma.id, AlunoTurma.ativo.is_(True),
            )
        ).scalar() or 0

        agora = datetime.now(timezone.utc)
        atividades = session.execute(
            select(Atividade).where(
                Atividade.turma_id == turma.id,
                Atividade.deleted_at.is_(None),
            )
        ).scalars().all()
        ativas = sum(
            1 for a in atividades
            if a.data_inicio <= agora <= a.data_fim
        )
        encerradas = sum(1 for a in atividades if a.data_fim < agora)

        envios_full = _coletar_envios_full(
            session, [a.id for a in atividades],
        )
        interactions = [
            e["interaction"] for e in envios_full if e["interaction"]
        ]

        return TurmaDashboardResponse(
            turma=TurmaDashboardResumo(
                id=str(turma.id), codigo=turma.codigo,
                n_alunos_ativos=int(n_alunos),
            ),
            atividades_total=len(atividades),
            atividades_ativas=ativas,
            atividades_encerradas=encerradas,
            distribuicao_notas=_distribuicao_por_modo(envios_full),
            top_detectores=[
                TopDetector(codigo=d["codigo"], nome=d["nome"],
                            contagem=d["ocorrencias"])
                for d in _coletar_top_detectores(interactions, top_n=3,
                                                  only_canonical=True)
            ],
            outros_detectores=_contar_detectores_outros(interactions),
            alunos_em_risco=[
                AlunoEmRisco(**a) for a in _alunos_em_risco(envios_full)
            ],
            evolucao_turma=[
                EvolucaoPonto(**p) for p in _evolucao_temporal(envios_full)
            ],
            n_envios_total=len(envios_full),
        )


# ──────────────────────────────────────────────────────────────────────
# GET /portal/escolas/{escola_id}/dashboard
# ──────────────────────────────────────────────────────────────────────

class EscolaDashboardResumo(BaseModel):
    id: str
    nome: str
    n_turmas: int
    n_alunos_ativos: int


class TurmaResumo(BaseModel):
    turma_id: str
    codigo: str
    serie: str
    professor_nome: str
    media_geral: Optional[int]
    n_atividades: int
    n_em_risco: int


class ComparacaoTurma(BaseModel):
    turma_codigo: str
    turma_id: str
    media: int
    n_envios: int


class EscolaDashboardResponse(BaseModel):
    escola: EscolaDashboardResumo
    turmas_resumo: List[TurmaResumo]
    distribuicao_notas_escola: Dict[str, Dict[str, int]]
    top_detectores_escola: List[TopDetector]
    outros_detectores_escola: int
    alunos_em_risco_escola: List[AlunoEmRisco]
    evolucao_escola: List[EvolucaoPonto]
    comparacao_turmas: List[ComparacaoTurma]


@router.get("/escolas/{escola_id}/dashboard",
            response_model=EscolaDashboardResponse)
def dashboard_escola(
    escola_id: uuid.UUID,
    auth: AuthenticatedUser = Depends(get_current_user),
) -> EscolaDashboardResponse:
    """Dashboard agregado da escola. APENAS coordenador da escola
    (papel + escola batem com auth). Professor recebe 403 mesmo sendo
    da escola — UX é via dashboard de turma.
    """
    if not can_view_dashboard_escola(auth, escola_id):
        raise HTTPException(
            status_code=403,
            detail="Apenas coordenador da escola acessa esse dashboard",
        )
    with Session(get_engine()) as session:
        escola = session.get(Escola, escola_id)
        if escola is None or escola.deleted_at is not None:
            raise HTTPException(status_code=404, detail="Escola não encontrada")

        turmas = session.execute(
            select(Turma, Professor)
            .join(Professor, Professor.id == Turma.professor_id)
            .where(Turma.escola_id == escola_id, Turma.deleted_at.is_(None))
        ).all()

        n_alunos_total = session.execute(
            select(func.count(AlunoTurma.id))
            .join(Turma, Turma.id == AlunoTurma.turma_id)
            .where(
                Turma.escola_id == escola_id,
                Turma.deleted_at.is_(None),
                AlunoTurma.ativo.is_(True),
            )
        ).scalar() or 0

        # Coletar todas as atividades de todas as turmas da escola
        atividades_all = session.execute(
            select(Atividade)
            .join(Turma, Turma.id == Atividade.turma_id)
            .where(
                Turma.escola_id == escola_id,
                Atividade.deleted_at.is_(None),
            )
        ).scalars().all()
        envios_all = _coletar_envios_full(
            session, [a.id for a in atividades_all],
        )
        interactions_all = [
            e["interaction"] for e in envios_all if e["interaction"]
        ]

        # Resumo por turma + comparação
        turmas_resumo: List[TurmaResumo] = []
        comparacao: List[ComparacaoTurma] = []
        for turma, prof in turmas:
            atividades_t = [a for a in atividades_all if a.turma_id == turma.id]
            envios_t = [e for e in envios_all if any(
                a.id == e["atividade_id"] for a in atividades_t
            )]
            notas = [e["nota_total"] for e in envios_t
                     if e["nota_total"] is not None]
            media = round(sum(notas) / len(notas)) if notas else None
            em_risco_t = _alunos_em_risco(envios_t)
            turmas_resumo.append(TurmaResumo(
                turma_id=str(turma.id), codigo=turma.codigo,
                serie=turma.serie, professor_nome=prof.nome,
                media_geral=media, n_atividades=len(atividades_t),
                n_em_risco=len(em_risco_t),
            ))
            if media is not None:
                comparacao.append(ComparacaoTurma(
                    turma_codigo=turma.codigo, turma_id=str(turma.id),
                    media=media, n_envios=len(envios_t),
                ))

        # Comparação só faz sentido com >= 2 turmas com dados
        if len(comparacao) < 2:
            comparacao = []

        return EscolaDashboardResponse(
            escola=EscolaDashboardResumo(
                id=str(escola.id), nome=escola.nome,
                n_turmas=len(turmas), n_alunos_ativos=int(n_alunos_total),
            ),
            turmas_resumo=turmas_resumo,
            distribuicao_notas_escola=_distribuicao_por_modo(envios_all),
            top_detectores_escola=[
                TopDetector(codigo=d["codigo"], nome=d["nome"],
                            contagem=d["ocorrencias"])
                for d in _coletar_top_detectores(
                    interactions_all, top_n=5, only_canonical=True,
                )
            ],
            outros_detectores_escola=_contar_detectores_outros(interactions_all),
            alunos_em_risco_escola=[
                AlunoEmRisco(**a) for a in _alunos_em_risco(envios_all)
            ],
            evolucao_escola=[
                EvolucaoPonto(**p) for p in _evolucao_temporal(envios_all)
            ],
            comparacao_turmas=comparacao,
        )


# ──────────────────────────────────────────────────────────────────────
# GET /portal/turmas/{turma_id}/alunos/{aluno_turma_id}/evolucao
# ──────────────────────────────────────────────────────────────────────

class EvolucaoEnvio(BaseModel):
    atividade_id: str
    missao_codigo: str
    missao_titulo: str
    oficina_numero: int
    modo: str
    data: str
    nota: Optional[int]
    faixa: str
    detectores: List[str]  # nomes humanizados


class EvolucaoChartPonto(BaseModel):
    data: str
    nota: int
    missao_codigo: str


class MissaoPendente(BaseModel):
    atividade_id: str
    missao_codigo: str
    missao_titulo: str
    oficina_numero: int
    modo_correcao: str
    data_fim: str
    status: str


class AlunoEvolucaoResumo(BaseModel):
    id: str
    nome: str


class AlunoEvolucaoResponse(BaseModel):
    aluno: AlunoEvolucaoResumo
    envios: List[EvolucaoEnvio]
    evolucao_chart: List[EvolucaoChartPonto]
    n_missoes_realizadas: int
    missoes_pendentes: List[MissaoPendente]


@router.get(
    "/turmas/{turma_id}/alunos/{aluno_turma_id}/evolucao",
    response_model=AlunoEvolucaoResponse,
)
def evolucao_aluno(
    turma_id: uuid.UUID,
    aluno_turma_id: uuid.UUID,
    auth: AuthenticatedUser = Depends(get_current_user),
) -> AlunoEvolucaoResponse:
    """Histórico do aluno: envios + chart + pendências."""
    with Session(get_engine()) as session:
        turma = _get_turma_or_404(session, turma_id)
        _check_view_turma(auth, turma)
        aluno = session.get(AlunoTurma, aluno_turma_id)
        if aluno is None or aluno.turma_id != turma_id:
            raise HTTPException(
                status_code=404, detail="Aluno não encontrado nessa turma")

        # Atividades da turma (todas)
        atividades = session.execute(
            select(Atividade).where(
                Atividade.turma_id == turma_id,
                Atividade.deleted_at.is_(None),
            ).order_by(Atividade.data_inicio)
        ).scalars().all()

        envios_full = _coletar_envios_full(
            session, [a.id for a in atividades],
        )
        envios_aluno = [
            e for e in envios_full if e["aluno_turma_id"] == aluno_turma_id
        ]

        envios_resp: List[EvolucaoEnvio] = []
        chart_pontos: List[EvolucaoChartPonto] = []
        for e in envios_aluno:
            faixa = _faixa_qualitativa(e["nota_total"]) if (
                _modo_bucket(e["modo"]) == "foco"
            ) else (
                "Insuficiente" if (e["nota_total"] is not None
                                    and e["nota_total"] <= 400)
                else "Regular" if (e["nota_total"] is not None
                                    and e["nota_total"] <= 600)
                else "Bom" if (e["nota_total"] is not None
                                and e["nota_total"] <= 800)
                else "Excelente" if e["nota_total"] is not None
                else "sem_nota"
            )
            it = e["interaction"]
            redato = e["redato_output"]
            codigos_acionados = _detectores_acionados_de(redato)
            nomes = [humanize_detector(c) for c in codigos_acionados]
            envios_resp.append(EvolucaoEnvio(
                atividade_id=str(e["atividade_id"]),
                missao_codigo=e["missao_codigo"],
                missao_titulo=e["missao_titulo"],
                oficina_numero=e["oficina_numero"],
                modo=e["modo"],
                data=e["enviado_em"].isoformat(),
                nota=e["nota_total"],
                faixa=faixa,
                detectores=nomes,
            ))
            if e["nota_total"] is not None:
                chart_pontos.append(EvolucaoChartPonto(
                    data=e["enviado_em"].isoformat(),
                    nota=e["nota_total"],
                    missao_codigo=e["missao_codigo"],
                ))

        envios_atividades_ids = {e["atividade_id"] for e in envios_aluno}
        pendentes: List[MissaoPendente] = []
        for ativ in atividades:
            if ativ.id in envios_atividades_ids:
                continue
            if ativ.status == "encerrada":
                continue
            missao = session.get(Missao, ativ.missao_id)
            pendentes.append(MissaoPendente(
                atividade_id=str(ativ.id),
                missao_codigo=missao.codigo if missao else "",
                missao_titulo=missao.titulo if missao else "",
                oficina_numero=missao.oficina_numero if missao else 0,
                modo_correcao=missao.modo_correcao if missao else "",
                data_fim=ativ.data_fim.isoformat(),
                status=ativ.status,
            ))

        return AlunoEvolucaoResponse(
            aluno=AlunoEvolucaoResumo(id=str(aluno.id), nome=aluno.nome),
            envios=envios_resp,
            evolucao_chart=chart_pontos,
            n_missoes_realizadas=len(envios_resp),
            missoes_pendentes=pendentes,
        )


# ════════════════════════════════════════════════════════════════════════
# M8 — PDF (geração + histórico + download)
# ════════════════════════════════════════════════════════════════════════

from fastapi.responses import FileResponse  # noqa: E402

from redato_backend.portal import pdf_generator as PDF  # noqa: E402


# ──────────────────────────────────────────────────────────────────────
# Helpers PDF
# ──────────────────────────────────────────────────────────────────────

def _serializar_dashboard_turma(
    auth: AuthenticatedUser, turma_id: uuid.UUID,
) -> Dict[str, Any]:
    """Reusa `dashboard_turma` mas devolve dict (não Pydantic model)
    pra alimentar o gerador de PDF."""
    resp = dashboard_turma(turma_id, auth=auth)
    return resp.model_dump(mode="json")


def _serializar_dashboard_escola(
    auth: AuthenticatedUser, escola_id: uuid.UUID,
) -> Dict[str, Any]:
    resp = dashboard_escola(escola_id, auth=auth)
    return resp.model_dump(mode="json")


def _serializar_evolucao_aluno(
    auth: AuthenticatedUser, turma_id: uuid.UUID,
    aluno_turma_id: uuid.UUID,
) -> Dict[str, Any]:
    resp = evolucao_aluno(turma_id, aluno_turma_id, auth=auth)
    return resp.model_dump(mode="json")


def _registrar_pdf(
    *, tipo: str, escopo_id: uuid.UUID, escola_id: uuid.UUID,
    user_id: uuid.UUID, arquivo_path: Path, tamanho: int,
    parametros: Optional[Dict[str, Any]] = None,
) -> uuid.UUID:
    with Session(get_engine()) as session:
        pdf = PdfGerado(
            tipo=tipo, escopo_id=escopo_id, escola_id=escola_id,
            gerado_por_user_id=user_id,
            arquivo_path=str(arquivo_path),
            tamanho_bytes=tamanho,
            parametros=json.dumps(parametros or {}, default=str),
        )
        session.add(pdf)
        session.commit()
        session.refresh(pdf)
        return pdf.id


# ──────────────────────────────────────────────────────────────────────
# POST /portal/pdfs/dashboard-turma/{turma_id}
# ──────────────────────────────────────────────────────────────────────

class GerarPdfRequest(BaseModel):
    periodo_inicio: Optional[datetime] = None
    periodo_fim: Optional[datetime] = None


class GerarPdfResponse(BaseModel):
    pdf_id: str
    download_url: str
    tamanho_bytes: int


@router.post("/pdfs/dashboard-turma/{turma_id}",
             response_model=GerarPdfResponse)
def gerar_pdf_turma(
    turma_id: uuid.UUID,
    body: GerarPdfRequest = GerarPdfRequest(),
    auth: AuthenticatedUser = Depends(get_current_user),
) -> GerarPdfResponse:
    """Gera PDF do dashboard da turma + grava em storage + registra
    em `pdfs_gerados`. Retorna `download_url`."""
    with Session(get_engine()) as session:
        turma = _get_turma_or_404(session, turma_id)
        _check_view_turma(auth, turma)
        escola_id = turma.escola_id

    dashboard = _serializar_dashboard_turma(auth, turma_id)
    pdf_bytes = PDF.gerar_pdf_dashboard_turma(
        turma_id, dashboard,
        periodo_inicio=body.periodo_inicio,
        periodo_fim=body.periodo_fim,
    )
    rel_path, size = PDF.salvar_pdf(
        pdf_bytes, tipo="dashboard_turma", escopo_id=turma_id,
    )
    pdf_id = _registrar_pdf(
        tipo="dashboard_turma", escopo_id=turma_id, escola_id=escola_id,
        user_id=auth.user_id, arquivo_path=rel_path, tamanho=size,
        parametros=body.model_dump(mode="json"),
    )
    _audit({
        "op": "pdf-gerado", "tipo": "dashboard_turma",
        "escopo_id": str(turma_id), "pdf_id": str(pdf_id),
        "by": str(auth.user_id), "tamanho": size,
    })
    return GerarPdfResponse(
        pdf_id=str(pdf_id),
        download_url=f"/portal/pdfs/{pdf_id}/download",
        tamanho_bytes=size,
    )


# ──────────────────────────────────────────────────────────────────────
# POST /portal/pdfs/dashboard-escola/{escola_id}
# ──────────────────────────────────────────────────────────────────────

@router.post("/pdfs/dashboard-escola/{escola_id}",
             response_model=GerarPdfResponse)
def gerar_pdf_escola(
    escola_id: uuid.UUID,
    body: GerarPdfRequest = GerarPdfRequest(),
    auth: AuthenticatedUser = Depends(get_current_user),
) -> GerarPdfResponse:
    if not can_view_dashboard_escola(auth, escola_id):
        raise HTTPException(
            status_code=403,
            detail="Apenas coordenador da escola pode exportar PDF",
        )
    dashboard = _serializar_dashboard_escola(auth, escola_id)
    pdf_bytes = PDF.gerar_pdf_dashboard_escola(
        escola_id, dashboard,
        periodo_inicio=body.periodo_inicio,
        periodo_fim=body.periodo_fim,
    )
    rel_path, size = PDF.salvar_pdf(
        pdf_bytes, tipo="dashboard_escola", escopo_id=escola_id,
    )
    pdf_id = _registrar_pdf(
        tipo="dashboard_escola", escopo_id=escola_id,
        escola_id=escola_id, user_id=auth.user_id,
        arquivo_path=rel_path, tamanho=size,
        parametros=body.model_dump(mode="json"),
    )
    _audit({
        "op": "pdf-gerado", "tipo": "dashboard_escola",
        "escopo_id": str(escola_id), "pdf_id": str(pdf_id),
        "by": str(auth.user_id), "tamanho": size,
    })
    return GerarPdfResponse(
        pdf_id=str(pdf_id),
        download_url=f"/portal/pdfs/{pdf_id}/download",
        tamanho_bytes=size,
    )


# ──────────────────────────────────────────────────────────────────────
# POST /portal/pdfs/evolucao-aluno/{turma_id}/{aluno_turma_id}
# ──────────────────────────────────────────────────────────────────────

@router.post(
    "/pdfs/evolucao-aluno/{turma_id}/{aluno_turma_id}",
    response_model=GerarPdfResponse,
)
def gerar_pdf_aluno_evolucao(
    turma_id: uuid.UUID,
    aluno_turma_id: uuid.UUID,
    body: GerarPdfRequest = GerarPdfRequest(),
    auth: AuthenticatedUser = Depends(get_current_user),
) -> GerarPdfResponse:
    with Session(get_engine()) as session:
        turma = _get_turma_or_404(session, turma_id)
        _check_view_turma(auth, turma)
        escola = session.get(Escola, turma.escola_id)
        escola_id = turma.escola_id
        escola_nome = escola.nome if escola else ""
        turma_codigo = turma.codigo

    evolucao = _serializar_evolucao_aluno(auth, turma_id, aluno_turma_id)
    pdf_bytes = PDF.gerar_pdf_evolucao_aluno(
        aluno_turma_id, evolucao,
        turma_codigo=turma_codigo, escola_nome=escola_nome,
    )
    rel_path, size = PDF.salvar_pdf(
        pdf_bytes, tipo="evolucao_aluno", escopo_id=aluno_turma_id,
    )
    pdf_id = _registrar_pdf(
        tipo="evolucao_aluno", escopo_id=aluno_turma_id,
        escola_id=escola_id, user_id=auth.user_id,
        arquivo_path=rel_path, tamanho=size,
        parametros=body.model_dump(mode="json"),
    )
    _audit({
        "op": "pdf-gerado", "tipo": "evolucao_aluno",
        "escopo_id": str(aluno_turma_id), "pdf_id": str(pdf_id),
        "by": str(auth.user_id), "tamanho": size,
    })
    return GerarPdfResponse(
        pdf_id=str(pdf_id),
        download_url=f"/portal/pdfs/{pdf_id}/download",
        tamanho_bytes=size,
    )


# ──────────────────────────────────────────────────────────────────────
# GET /portal/pdfs/{pdf_id}/download
# ──────────────────────────────────────────────────────────────────────

@router.get("/pdfs/{pdf_id}/download")
def baixar_pdf(
    pdf_id: uuid.UUID,
    auth: AuthenticatedUser = Depends(get_current_user),
) -> FileResponse:
    """Stream do PDF. Permission: gerador OR mesma escola do user."""
    with Session(get_engine()) as session:
        pdf = session.get(PdfGerado, pdf_id)
        if pdf is None:
            raise HTTPException(status_code=404, detail="PDF não encontrado")
        same_escola = pdf.escola_id == auth.escola_id
        is_owner = pdf.gerado_por_user_id == auth.user_id
        if not (same_escola or is_owner):
            raise HTTPException(status_code=403, detail="Sem permissão")
        full = PDF.storage_root() / pdf.arquivo_path
        if not full.exists():
            raise HTTPException(
                status_code=410,
                detail="Arquivo do PDF não está mais disponível",
            )
        nome = f"redato_{pdf.tipo}_{pdf.gerado_em.strftime('%Y%m%d')}.pdf"
        return FileResponse(
            path=str(full),
            media_type="application/pdf",
            filename=nome,
        )


# ──────────────────────────────────────────────────────────────────────
# GET /portal/pdfs/historico
# ──────────────────────────────────────────────────────────────────────

class PdfHistoricoItem(BaseModel):
    id: str
    tipo: str
    escopo_id: str
    gerado_em: str
    gerado_por_user_id: str
    tamanho_bytes: int
    download_url: str


@router.get("/pdfs/historico", response_model=List[PdfHistoricoItem])
def historico_pdfs(
    tipo: Optional[str] = Query(None),
    escopo_id: Optional[uuid.UUID] = Query(None),
    limit: int = Query(20, ge=1, le=200),
    auth: AuthenticatedUser = Depends(get_current_user),
) -> List[PdfHistoricoItem]:
    """Lista PDFs visíveis pelo user.

    - Coordenador: todos os PDFs da sua escola.
    - Professor: PDFs que ele gerou + PDFs de turmas onde ele é prof.
    """
    with Session(get_engine()) as session:
        q = select(PdfGerado).where(PdfGerado.escola_id == auth.escola_id)
        if auth.papel == "professor":
            # Professor só vê os que gerou (não vê PDFs de outras turmas
            # ou da escola). UX simples; refinaria se valer a pena.
            q = q.where(PdfGerado.gerado_por_user_id == auth.user_id)
        if tipo:
            q = q.where(PdfGerado.tipo == tipo)
        if escopo_id:
            q = q.where(PdfGerado.escopo_id == escopo_id)
        q = q.order_by(PdfGerado.gerado_em.desc()).limit(limit)
        rows = session.execute(q).scalars().all()
    return [
        PdfHistoricoItem(
            id=str(p.id), tipo=p.tipo,
            escopo_id=str(p.escopo_id),
            gerado_em=p.gerado_em.isoformat(),
            gerado_por_user_id=str(p.gerado_por_user_id),
            tamanho_bytes=p.tamanho_bytes,
            download_url=f"/portal/pdfs/{p.id}/download",
        )
        for p in rows
    ]
