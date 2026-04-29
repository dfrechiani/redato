"""Camada de ligação entre bot WhatsApp e modelos do portal (M4).

Funções auxiliares que o bot usa pra:
- Encontrar AlunoTurma pelo telefone
- Cadastrar aluno via código de turma
- Encontrar atividade ativa pra (turma_id, missao_codigo)
- Registrar envio (atividade + aluno + interaction)

Usa SQLAlchemy + Postgres. Bot ainda mantém SQLite pra estado FSM
local — separação intencional pra não refatorar tudo.
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from redato_backend.portal.db import get_engine
from redato_backend.portal.models import (
    AlunoTurma, Atividade, Envio, Escola, Interaction, Missao, Professor,
    Turma,
)


# Formato esperado: TURMA-XXXXX-1A-2026 (ou variações com -2 sufixo)
CODIGO_TURMA_RE = re.compile(
    r"\bTURMA-[A-Z0-9]+-[A-Z0-9]+-\d{4}(-\d+)?\b",
    re.IGNORECASE,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _open_session() -> Session:
    return Session(get_engine())


# ──────────────────────────────────────────────────────────────────────
# Detecção de código de turma
# ──────────────────────────────────────────────────────────────────────

def extract_codigo_turma(text: Optional[str]) -> Optional[str]:
    """Detecta padrão TURMA-... numa string. Retorna em uppercase."""
    if not text:
        return None
    m = CODIGO_TURMA_RE.search(text)
    return m.group(0).upper() if m else None


# ──────────────────────────────────────────────────────────────────────
# Busca de turma
# ──────────────────────────────────────────────────────────────────────

@dataclass
class TurmaInfo:
    turma_id: uuid.UUID
    turma_codigo: str
    escola_nome: str
    ativa: bool


def find_turma_por_codigo_join(codigo_join: str) -> Optional[TurmaInfo]:
    """Busca turma pelo codigo_join (gerado em M2). None se não existir."""
    with _open_session() as session:
        row = session.execute(
            select(Turma, Escola)
            .join(Escola, Escola.id == Turma.escola_id)
            .where(Turma.codigo_join == codigo_join)
        ).first()
        if row is None:
            return None
        turma, escola = row
        return TurmaInfo(
            turma_id=turma.id, turma_codigo=turma.codigo,
            escola_nome=escola.nome,
            ativa=(
                turma.ativa
                and turma.deleted_at is None
                and escola.ativa
                and escola.deleted_at is None
            ),
        )


# ──────────────────────────────────────────────────────────────────────
# AlunoTurma: cadastro + busca por telefone
# ──────────────────────────────────────────────────────────────────────

@dataclass
class AlunoVinculo:
    aluno_turma_id: uuid.UUID
    nome: str
    telefone: str
    turma_id: uuid.UUID
    turma_codigo: str
    escola_nome: str


def list_alunos_ativos_por_telefone(phone: str) -> List[AlunoVinculo]:
    """Retorna lista (aluno_turma, turma, escola) onde aluno está
    ativo. Pode ser >1 se aluno pertenceu a múltiplas turmas."""
    with _open_session() as session:
        rows = session.execute(
            select(AlunoTurma, Turma, Escola)
            .join(Turma, Turma.id == AlunoTurma.turma_id)
            .join(Escola, Escola.id == Turma.escola_id)
            .where(
                AlunoTurma.telefone == phone,
                AlunoTurma.ativo.is_(True),
                Turma.ativa.is_(True),
                Turma.deleted_at.is_(None),
                Escola.ativa.is_(True),
                Escola.deleted_at.is_(None),
            )
            .order_by(AlunoTurma.vinculado_em.desc())
        ).all()
    return [
        AlunoVinculo(
            aluno_turma_id=at.id, nome=at.nome, telefone=at.telefone,
            turma_id=t.id, turma_codigo=t.codigo, escola_nome=e.nome,
        )
        for (at, t, e) in rows
    ]


def cadastrar_aluno_em_turma(
    *, turma_id: uuid.UUID, nome: str, telefone: str,
) -> tuple[AlunoVinculo, bool]:
    """Cria AlunoTurma. Retorna (vinculo, criado_agora).
    Se já existe (mesmo turma+phone), retorna o existente sem criar."""
    with _open_session() as session:
        existing = session.execute(
            select(AlunoTurma).where(
                AlunoTurma.turma_id == turma_id,
                AlunoTurma.telefone == telefone,
            )
        ).scalar_one_or_none()

        if existing is not None:
            turma = session.get(Turma, turma_id)
            escola = session.get(Escola, turma.escola_id) if turma else None
            return AlunoVinculo(
                aluno_turma_id=existing.id, nome=existing.nome,
                telefone=existing.telefone, turma_id=turma_id,
                turma_codigo=turma.codigo if turma else "",
                escola_nome=escola.nome if escola else "",
            ), False

        novo = AlunoTurma(
            turma_id=turma_id, nome=nome.strip(), telefone=telefone,
            vinculado_em=_utc_now(), ativo=True,
        )
        session.add(novo)
        session.commit()
        session.refresh(novo)

        turma = session.get(Turma, turma_id)
        escola = session.get(Escola, turma.escola_id) if turma else None
        return AlunoVinculo(
            aluno_turma_id=novo.id, nome=novo.nome, telefone=novo.telefone,
            turma_id=turma_id,
            turma_codigo=turma.codigo if turma else "",
            escola_nome=escola.nome if escola else "",
        ), True


# ──────────────────────────────────────────────────────────────────────
# Atividade ativa
# ──────────────────────────────────────────────────────────────────────

@dataclass
class AtividadeAtivaInfo:
    atividade_id: uuid.UUID
    missao_codigo: str
    missao_titulo: str
    modo_correcao: str
    data_inicio: datetime
    data_fim: datetime
    status: str  # "agendada" | "ativa" | "encerrada"


@dataclass
class AtividadeAtivaContext:
    """Atividade `ativa` (entre data_inicio e data_fim) numa turma onde
    o aluno está vinculado. Usado pelo bot pra resolver foto sem código
    automaticamente quando há uma única atividade aberta."""
    atividade_id: uuid.UUID
    missao_codigo: str             # canonical: RJ2·OF04·MF
    missao_titulo: str
    oficina_numero: int            # 4
    modo_correcao: str
    serie: str                     # "1S" | "2S" | "3S"
    turma_id: uuid.UUID
    turma_codigo: str
    escola_nome: str
    aluno_turma_id: uuid.UUID
    data_fim: datetime


def list_atividades_ativas_por_aluno(
    phone: str,
) -> List[AtividadeAtivaContext]:
    """Atividades de status `ativa` (entre data_inicio e data_fim) em
    todas as turmas onde o aluno está vinculado e ativo. Ordem: mais
    recente primeiro.

    Usado pelo bot pra resolver `foto sem código` automaticamente:
    - 1 atividade ativa → usa direto, sem perguntar
    - >1 → lista oficina_numero pro aluno escolher
    - 0 → pede código completo
    """
    agora = _utc_now()
    with _open_session() as session:
        rows = session.execute(
            select(Atividade, Missao, Turma, Escola, AlunoTurma)
            .join(Missao, Missao.id == Atividade.missao_id)
            .join(Turma, Turma.id == Atividade.turma_id)
            .join(Escola, Escola.id == Turma.escola_id)
            .join(AlunoTurma, AlunoTurma.turma_id == Turma.id)
            .where(
                AlunoTurma.telefone == phone,
                AlunoTurma.ativo.is_(True),
                Turma.ativa.is_(True),
                Turma.deleted_at.is_(None),
                Escola.ativa.is_(True),
                Escola.deleted_at.is_(None),
                Atividade.deleted_at.is_(None),
                Atividade.data_inicio <= agora,
                Atividade.data_fim >= agora,
            )
            .order_by(Atividade.data_inicio.desc())
        ).all()

    return [
        AtividadeAtivaContext(
            atividade_id=ativ.id,
            missao_codigo=missao.codigo,
            missao_titulo=missao.titulo,
            oficina_numero=missao.oficina_numero,
            modo_correcao=missao.modo_correcao,
            serie=missao.serie,
            turma_id=turma.id,
            turma_codigo=turma.codigo,
            escola_nome=escola.nome,
            aluno_turma_id=at.id,
            data_fim=ativ.data_fim,
        )
        for (ativ, missao, turma, escola, at) in rows
    ]


def find_atividade_para_missao(
    *, turma_id: uuid.UUID, missao_codigo: str,
) -> Optional[AtividadeAtivaInfo]:
    """Busca atividade NÃO deletada pra (turma + missão). Retorna a
    mais recente independente do status — caller decide se aceita
    baseado no .status. Permite mensagens distintas pra
    agendada/ativa/encerrada."""
    with _open_session() as session:
        row = session.execute(
            select(Atividade, Missao)
            .join(Missao, Missao.id == Atividade.missao_id)
            .where(
                Atividade.turma_id == turma_id,
                Missao.codigo == missao_codigo,
                Atividade.deleted_at.is_(None),
            )
            .order_by(Atividade.data_inicio.desc())
            .limit(1)
        ).first()
        if row is None:
            return None
        ativ, missao = row
        return AtividadeAtivaInfo(
            atividade_id=ativ.id, missao_codigo=missao.codigo,
            missao_titulo=missao.titulo,
            modo_correcao=missao.modo_correcao,
            data_inicio=ativ.data_inicio, data_fim=ativ.data_fim,
            status=ativ.status,
        )


# ──────────────────────────────────────────────────────────────────────
# Envio: criação + busca de duplicata
# ──────────────────────────────────────────────────────────────────────

def find_envio_existente(
    *, atividade_id: uuid.UUID, aluno_turma_id: uuid.UUID,
) -> Optional[uuid.UUID]:
    """Retorna envio_id se aluno já enviou pra essa atividade."""
    with _open_session() as session:
        eid = session.execute(
            select(Envio.id).where(
                Envio.atividade_id == atividade_id,
                Envio.aluno_turma_id == aluno_turma_id,
            )
        ).scalar_one_or_none()
        return eid


def registrar_envio(
    *, atividade_id: uuid.UUID, aluno_turma_id: uuid.UUID,
    interaction_id: Optional[int] = None,
) -> uuid.UUID:
    """Cria Envio + atualiza interactions.envio_id se interaction_id
    fornecido. Retorna envio_id."""
    with _open_session() as session:
        envio = Envio(
            atividade_id=atividade_id,
            aluno_turma_id=aluno_turma_id,
            interaction_id=interaction_id,
            enviado_em=_utc_now(),
        )
        session.add(envio)
        session.flush()

        if interaction_id is not None:
            interaction = session.get(Interaction, interaction_id)
            if interaction is not None:
                interaction.envio_id = envio.id
                interaction.aluno_turma_id = aluno_turma_id
                interaction.source = "whatsapp_portal"

        session.commit()
        return envio.id


def _proxima_tentativa_n(
    session: Session, atividade_id: uuid.UUID,
    aluno_turma_id: uuid.UUID,
) -> int:
    """Calcula `tentativa_n` pra novo Envio. Retorna `max(tentativa_n) + 1`
    ou 1 se não houver envio anterior. M9.6."""
    from sqlalchemy import func as _func
    n = session.execute(
        select(_func.max(Envio.tentativa_n)).where(
            Envio.atividade_id == atividade_id,
            Envio.aluno_turma_id == aluno_turma_id,
        )
    ).scalar()
    return (n or 0) + 1


def criar_interaction_e_envio_postgres(
    *,
    aluno_phone: str,
    aluno_turma_id: uuid.UUID,
    atividade_id: uuid.UUID,
    missao_codigo: str,
    activity_id: str,
    foto_path: str,
    foto_hash: str,
    texto_transcrito: Optional[str],
    ocr_quality_issues: Optional[list],
    ocr_metrics: Optional[dict],
    redato_output: Optional[dict],
    resposta_aluno: Optional[str],
    elapsed_ms: Optional[int],
) -> tuple[int, uuid.UUID, int]:
    """Cria Interaction (Postgres) + Envio + cross-link em uma transação.

    Retorna (interaction_id, envio_id, tentativa_n).

    M9.6 (2026-04-29): suporta múltiplas tentativas do mesmo aluno na
    mesma atividade. `tentativa_n` é calculado como `max+1` na hora.
    Em caso de race condition (2 processes inserindo simultâneo com
    mesmo `tentativa_n`), retry automático 1x com `tentativa_n+1`.
    Se falhar de novo, **raise IntegrityError barulhento** — não
    engole mais como warning silencioso (bug que escondeu o problema
    de tentativas órfãs por dias antes do M9.6).

    Caller continua sendo responsável pelo SQLite legado — se essa
    função raise, SQLite já salvou e bot pode mostrar feedback ao
    aluno mesmo com Postgres inconsistente. Mas vai surgir log ERROR
    bem visível no Railway pra Daniel investigar.
    """
    import json as _json
    from sqlalchemy.exc import IntegrityError
    import logging as _logging

    logger = _logging.getLogger(__name__)
    payload = {
        "interaction": dict(
            aluno_phone=aluno_phone,
            aluno_turma_id=aluno_turma_id,
            source="whatsapp_portal",
            missao_id=missao_codigo,
            activity_id=activity_id,
            foto_path=foto_path,
            foto_hash=foto_hash,
            texto_transcrito=texto_transcrito,
            ocr_quality_issues=_json.dumps(ocr_quality_issues or [],
                                            ensure_ascii=False),
            ocr_metrics=_json.dumps(ocr_metrics or {}, ensure_ascii=False),
            redato_output=_json.dumps(redato_output or {},
                                       ensure_ascii=False, default=str),
            resposta_aluno=resposta_aluno,
            elapsed_ms=elapsed_ms,
        ),
        "atividade_id": atividade_id,
        "aluno_turma_id": aluno_turma_id,
    }

    def _tentar(tentativa_n_forcado: Optional[int] = None) -> tuple[int, uuid.UUID, int]:
        with _open_session() as session:
            tentativa_n = (
                tentativa_n_forcado
                if tentativa_n_forcado is not None
                else _proxima_tentativa_n(
                    session, atividade_id, aluno_turma_id,
                )
            )
            interaction = Interaction(envio_id=None, **payload["interaction"])
            session.add(interaction)
            session.flush()

            envio = Envio(
                atividade_id=atividade_id,
                aluno_turma_id=aluno_turma_id,
                interaction_id=interaction.id,
                enviado_em=_utc_now(),
                tentativa_n=tentativa_n,
            )
            session.add(envio)
            session.flush()

            interaction.envio_id = envio.id
            session.commit()
            return interaction.id, envio.id, tentativa_n

    try:
        return _tentar()
    except IntegrityError as exc:
        # Race condition: outro processo criou tentativa_n=N entre
        # nosso SELECT max e INSERT. Retry 1x com tentativa_n+1.
        logger.warning(
            "criar_interaction_e_envio_postgres: race em "
            "tentativa_n (atividade=%s aluno=%s). Retry 1x: %s",
            atividade_id, aluno_turma_id, exc.orig,
        )
        try:
            with _open_session() as session:
                novo_n = _proxima_tentativa_n(
                    session, atividade_id, aluno_turma_id,
                )
            return _tentar(tentativa_n_forcado=novo_n)
        except IntegrityError as retry_exc:
            # Falhou 2x — raise barulhento (não engolir!).
            logger.error(
                "criar_interaction_e_envio_postgres FALHOU 2x mesmo "
                "com retry de race condition. atividade=%s aluno=%s "
                "missao=%s phone=%s. SQLite legado já salvou — "
                "Postgres ficou inconsistente. Investigar urgente.",
                atividade_id, aluno_turma_id, missao_codigo,
                aluno_phone,
            )
            raise


# ──────────────────────────────────────────────────────────────────────
# Notificação de alunos da turma
# ──────────────────────────────────────────────────────────────────────

@dataclass
class NotificacaoAtividadeContext:
    """Tudo que o caller precisa pra renderizar mensagem + iterar alunos."""
    atividade_id: uuid.UUID
    turma_id: uuid.UUID
    turma_codigo: str
    escola_nome: str
    missao_codigo: str
    missao_titulo: str
    data_fim: datetime
    professor_nome: str
    notificacao_enviada_em: Optional[datetime]
    alunos: List[AlunoVinculo]


def get_notificacao_context(
    atividade_id: uuid.UUID,
) -> Optional[NotificacaoAtividadeContext]:
    """Coleta tudo necessário pra rota /notificar e /texto-notificacao."""
    with _open_session() as session:
        ativ_row = session.execute(
            select(Atividade, Missao, Turma, Escola, Professor)
            .join(Missao, Missao.id == Atividade.missao_id)
            .join(Turma, Turma.id == Atividade.turma_id)
            .join(Escola, Escola.id == Turma.escola_id)
            .join(Professor, Professor.id == Atividade.criada_por_professor_id)
            .where(Atividade.id == atividade_id,
                   Atividade.deleted_at.is_(None))
        ).first()
        if ativ_row is None:
            return None
        ativ, missao, turma, escola, professor = ativ_row

        alunos_rows = session.execute(
            select(AlunoTurma)
            .where(
                AlunoTurma.turma_id == turma.id,
                AlunoTurma.ativo.is_(True),
            )
        ).scalars().all()
        alunos = [
            AlunoVinculo(
                aluno_turma_id=a.id, nome=a.nome, telefone=a.telefone,
                turma_id=turma.id, turma_codigo=turma.codigo,
                escola_nome=escola.nome,
            )
            for a in alunos_rows
        ]
        return NotificacaoAtividadeContext(
            atividade_id=ativ.id, turma_id=turma.id,
            turma_codigo=turma.codigo, escola_nome=escola.nome,
            missao_codigo=missao.codigo, missao_titulo=missao.titulo,
            data_fim=ativ.data_fim, professor_nome=professor.nome,
            notificacao_enviada_em=ativ.notificacao_enviada_em,
            alunos=alunos,
        )


def marcar_notificacao_enviada(atividade_id: uuid.UUID) -> None:
    with _open_session() as session:
        ativ = session.get(Atividade, atividade_id)
        if ativ is not None:
            ativ.notificacao_enviada_em = _utc_now()
            session.commit()
