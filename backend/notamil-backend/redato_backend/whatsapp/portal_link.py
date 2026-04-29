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


# ──────────────────────────────────────────────────────────────────────
# Fase 2 passo 4 — partidas do jogo
# ──────────────────────────────────────────────────────────────────────

@dataclass
class PartidaPendenteContext:
    """Snapshot de uma partida pendente pro aluno (sem cartas escolhidas
    ou sem reescrita). Bot usa pra decidir entre fluxo M9.2 (foto) e
    fluxo de partida.

    Estado:
    - "aguardando_cartas": texto_montado vazio, cartas ainda não escolhidas
    - "aguardando_reescrita": texto_montado preenchido, aluno ainda não
      mandou reescrita
    """
    partida_id: uuid.UUID
    atividade_id: uuid.UUID
    aluno_turma_id: uuid.UUID
    minideck_id: uuid.UUID
    minideck_tema: str
    minideck_nome_humano: str
    grupo_codigo: str
    missao_codigo: str
    missao_titulo: str
    prazo_reescrita: datetime
    estado_partida: str  # "aguardando_cartas" | "aguardando_reescrita" | "concluida"
    texto_montado: str   # vazio se estado=aguardando_cartas


def find_partida_pendente_para_aluno(
    phone: str,
) -> Optional[PartidaPendenteContext]:
    """Encontra a primeira partida pendente pro aluno em alguma das
    suas turmas:

    - Atividade ATIVA (data_inicio <= now <= data_fim)
    - Aluno na lista `cartas_escolhidas._alunos_turma_ids` da partida
    - Prazo da reescrita > now
    - Aluno ainda NÃO submeteu reescrita

    Retorna None se aluno não tem nenhuma partida pendente. Caller
    (bot) usa pra decidir entre fluxo de partida e fluxo M9.2 normal.

    Decisão G.1.4: sem partida → fluxo normal de foto.
    """
    from redato_backend.portal.models import (
        JogoMinideck, PartidaJogo, ReescritaIndividual,
    )

    agora = _utc_now()
    with _open_session() as session:
        # Vínculos do aluno
        aluno_rows = session.execute(
            select(AlunoTurma).where(
                AlunoTurma.telefone == phone,
                AlunoTurma.ativo.is_(True),
            )
        ).scalars().all()
        if not aluno_rows:
            return None

        aluno_ids = [a.id for a in aluno_rows]
        turma_ids = [a.turma_id for a in aluno_rows]

        # Partidas em atividades ativas pras turmas do aluno, com
        # prazo no futuro. Filtrar "aluno faz parte" e "ainda sem
        # reescrita" em Python — `cartas_escolhidas` é JSONB com
        # estrutura conhecida pelo jogo_api.
        rows = session.execute(
            select(PartidaJogo, Atividade, Missao, JogoMinideck)
            .join(Atividade, Atividade.id == PartidaJogo.atividade_id)
            .join(Missao, Missao.id == Atividade.missao_id)
            .join(
                JogoMinideck,
                JogoMinideck.id == PartidaJogo.minideck_id,
            )
            .where(
                Atividade.turma_id.in_(turma_ids),
                Atividade.deleted_at.is_(None),
                Atividade.data_inicio <= agora,
                Atividade.data_fim >= agora,
                PartidaJogo.prazo_reescrita > agora,
            )
            .order_by(PartidaJogo.created_at.asc())
        ).all()
        if not rows:
            return None

        # Pra cada partida, decidir se é pendente pra esse aluno
        for partida, ativ, missao, minideck in rows:
            cartas_dict = partida.cartas_escolhidas or {}
            if isinstance(cartas_dict, list):
                # Formato antigo, sem campo _alunos — pula (sem
                # vínculo direto).
                continue
            alunos_da_partida_raw = cartas_dict.get(
                "_alunos_turma_ids", [],
            )
            try:
                alunos_da_partida = {
                    uuid.UUID(str(s)) for s in alunos_da_partida_raw
                }
            except (ValueError, TypeError):
                continue

            # Match com algum vínculo do aluno
            aluno_match = next(
                (aid for aid in aluno_ids if aid in alunos_da_partida),
                None,
            )
            if aluno_match is None:
                continue

            # Aluno já submeteu reescrita? Se sim, partida não é
            # pendente PRA ele (mesmo que outros do grupo ainda
            # devam) — bot fica em READY e fluxo de foto.
            existe_reescrita = session.execute(
                select(ReescritaIndividual.id).where(
                    ReescritaIndividual.partida_id == partida.id,
                    ReescritaIndividual.aluno_turma_id == aluno_match,
                )
            ).first()
            if existe_reescrita is not None:
                continue

            estado_partida = (
                "aguardando_cartas"
                if not (partida.texto_montado or "").strip()
                else "aguardando_reescrita"
            )

            return PartidaPendenteContext(
                partida_id=partida.id,
                atividade_id=ativ.id,
                aluno_turma_id=aluno_match,
                minideck_id=minideck.id,
                minideck_tema=minideck.tema,
                minideck_nome_humano=minideck.nome_humano,
                grupo_codigo=partida.grupo_codigo,
                missao_codigo=missao.codigo,
                missao_titulo=missao.titulo,
                prazo_reescrita=partida.prazo_reescrita,
                estado_partida=estado_partida,
                texto_montado=partida.texto_montado or "",
            )
    return None


def get_partida_by_id(
    partida_id: uuid.UUID, *, phone: str,
) -> Optional[PartidaPendenteContext]:
    """Re-resolve uma partida pelo id pro aluno (após FSM cache).
    Garante autorização: phone deve estar em alunos_turma_ids da
    partida. Retorna None senão (não autorizado ou não existe)."""
    from redato_backend.portal.models import (
        JogoMinideck, PartidaJogo,
    )

    agora = _utc_now()
    with _open_session() as session:
        partida = session.get(PartidaJogo, partida_id)
        if partida is None:
            return None
        ativ = session.get(Atividade, partida.atividade_id)
        if ativ is None or ativ.deleted_at is not None:
            return None
        missao = session.get(Missao, ativ.missao_id)
        minideck = session.get(JogoMinideck, partida.minideck_id)
        if missao is None or minideck is None:
            return None

        cartas_dict = partida.cartas_escolhidas or {}
        if isinstance(cartas_dict, list):
            return None
        alunos_da_partida_raw = cartas_dict.get(
            "_alunos_turma_ids", [],
        )
        try:
            alunos_da_partida = {
                uuid.UUID(str(s)) for s in alunos_da_partida_raw
            }
        except (ValueError, TypeError):
            return None

        # Vínculos desse phone
        aluno_rows = session.execute(
            select(AlunoTurma).where(
                AlunoTurma.telefone == phone,
                AlunoTurma.ativo.is_(True),
            )
        ).scalars().all()
        aluno_match = next(
            (a.id for a in aluno_rows if a.id in alunos_da_partida),
            None,
        )
        if aluno_match is None:
            return None

        estado_partida = (
            "aguardando_cartas"
            if not (partida.texto_montado or "").strip()
            else "aguardando_reescrita"
        )
        return PartidaPendenteContext(
            partida_id=partida.id,
            atividade_id=ativ.id,
            aluno_turma_id=aluno_match,
            minideck_id=minideck.id,
            minideck_tema=minideck.tema,
            minideck_nome_humano=minideck.nome_humano,
            grupo_codigo=partida.grupo_codigo,
            missao_codigo=missao.codigo,
            missao_titulo=missao.titulo,
            prazo_reescrita=partida.prazo_reescrita,
            estado_partida=estado_partida,
            texto_montado=partida.texto_montado or "",
        )


def carregar_contexto_validacao(
    minideck_id: uuid.UUID,
):
    """Carrega snapshot do catálogo (estruturais + lacunas do minideck)
    em forma `ContextoValidacao` pronto pra `validar_partida` e
    `montar_texto_montado`. Roda 2 SELECTs.

    Returns: ContextoValidacao (do módulo jogo_partida) ou None se
    minideck não existe."""
    from redato_backend.portal.models import (
        CartaEstrutural, CartaLacuna, JogoMinideck,
    )
    from redato_backend.whatsapp.jogo_partida import (
        CartaEstruturalSnapshot, CartaLacunaSnapshot, ContextoValidacao,
    )

    with _open_session() as session:
        minideck = session.get(JogoMinideck, minideck_id)
        if minideck is None:
            return None

        estr_rows = session.execute(
            select(CartaEstrutural)
            .order_by(CartaEstrutural.codigo.asc())
        ).scalars().all()
        lac_rows = session.execute(
            select(CartaLacuna)
            .where(CartaLacuna.minideck_id == minideck_id)
            .order_by(CartaLacuna.codigo.asc())
        ).scalars().all()

        estruturais = {
            e.codigo: CartaEstruturalSnapshot(
                codigo=e.codigo, secao=e.secao, cor=e.cor,
                texto=e.texto,
                lacunas=tuple(e.lacunas or []),
            )
            for e in estr_rows
        }
        lacunas = {
            l.codigo: CartaLacunaSnapshot(
                codigo=l.codigo, tipo=l.tipo, conteudo=l.conteudo,
            )
            for l in lac_rows
        }
        return ContextoValidacao(
            estruturais_por_codigo=estruturais,
            lacunas_por_codigo=lacunas,
            minideck_tema=minideck.tema,
            minideck_nome_humano=minideck.nome_humano,
        )


def persist_cartas_e_texto(
    *,
    partida_id: uuid.UUID,
    codigos: List[str],
    texto_montado: str,
) -> None:
    """Atualiza partida_jogo após validação das cartas:
    - cartas_escolhidas[codigos] = lista de codes (preserva _alunos_turma_ids)
    - texto_montado = redação cooperativa expandida
    Não muda alunos vinculados (campo _alunos_turma_ids preservado)."""
    from redato_backend.portal.models import PartidaJogo

    with _open_session() as session:
        partida = session.get(PartidaJogo, partida_id)
        if partida is None:
            raise RuntimeError(f"Partida {partida_id} não encontrada")
        cartas = dict(partida.cartas_escolhidas or {})
        cartas["codigos"] = list(codigos)
        partida.cartas_escolhidas = cartas
        partida.texto_montado = texto_montado
        session.commit()


def persist_reescrita(
    *,
    partida_id: uuid.UUID,
    aluno_turma_id: uuid.UUID,
    texto: str,
) -> uuid.UUID:
    """Cria ReescritaIndividual. Levanta se UNIQUE constraint barrar
    (aluno tentando resubmeter reescrita)."""
    from redato_backend.portal.models import ReescritaIndividual

    with _open_session() as session:
        r = ReescritaIndividual(
            partida_id=partida_id,
            aluno_turma_id=aluno_turma_id,
            texto=texto,
            redato_output=None,  # Passo 5 popula
        )
        session.add(r)
        session.commit()
        session.refresh(r)
        return r.id


def find_reescrita_existente(
    *, partida_id: uuid.UUID, aluno_turma_id: uuid.UUID,
) -> bool:
    """True se aluno já submeteu reescrita pra essa partida (UNIQUE)."""
    from redato_backend.portal.models import ReescritaIndividual

    with _open_session() as session:
        n = session.execute(
            select(ReescritaIndividual.id).where(
                ReescritaIndividual.partida_id == partida_id,
                ReescritaIndividual.aluno_turma_id == aluno_turma_id,
            )
        ).first()
        return n is not None


def update_reescrita_redato_output(
    *, reescrita_id: uuid.UUID, redato_output: dict,
    elapsed_ms: Optional[int] = None,
) -> None:
    """Atualiza `redato_output` (e opcionalmente `elapsed_ms`) de uma
    reescrita após o pipeline Redato concluir. Chamado pelo bot no
    _handle_revisando_texto_montado depois da chamada ao Claude."""
    from redato_backend.portal.models import ReescritaIndividual

    with _open_session() as session:
        r = session.get(ReescritaIndividual, reescrita_id)
        if r is None:
            raise RuntimeError(
                f"Reescrita {reescrita_id} não encontrada — "
                f"persistência inconsistente",
            )
        r.redato_output = redato_output
        if elapsed_ms is not None:
            r.elapsed_ms = elapsed_ms
        session.commit()
