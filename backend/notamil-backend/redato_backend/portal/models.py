"""Modelos SQLAlchemy do portal — M1 da Fase B+.

Spec: ver `docs/redato/v3/REPORT_caminho2_realuse.md` (seção 5) e
`redato_backend/portal/README.md`.

Convenções:
- PK: UUID v4 (Postgres `uuid` nativo).
- Timestamps: `created_at` / `updated_at` em todas as tabelas
  (default = `now() at time zone 'utc'`).
- Soft delete: `deleted_at TIMESTAMPTZ NULLABLE` em escolas, turmas,
  atividades. NUNCA usar DELETE físico nessas tabelas (ver README).
- Coordenador, Professor, AlunoTurma usam flag `ativo` (boolean) em
  vez de soft delete — uso mais simples, sem necessidade de auditoria
  histórica.
- Senhas: `senha_hash` armazena bcrypt/argon2 (nunca plaintext);
  `nullable` enquanto user não fez 1º acesso.
- Token de 1º acesso: `primeiro_acesso_token` é random 32 bytes
  hex-encoded (gerado em M3).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import (
    Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer,
    String, Text, UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from redato_backend.portal.db import Base


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────

def _uuid_pk() -> Mapped[uuid.UUID]:
    """UUID v4 como PK (Postgres uuid nativo). Default gerado no Python
    pra portabilidade — caller não precisa instalar extension uuid-ossp."""
    return mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


# ──────────────────────────────────────────────────────────────────────
# Escola
# ──────────────────────────────────────────────────────────────────────

class Escola(Base):
    __tablename__ = "escolas"

    id: Mapped[uuid.UUID] = _uuid_pk()
    codigo: Mapped[str] = mapped_column(String(64), unique=True, index=True,
                                         nullable=False)
    nome: Mapped[str] = mapped_column(String(255), nullable=False)
    estado: Mapped[str] = mapped_column(String(2), nullable=False)
    municipio: Mapped[str] = mapped_column(String(120), nullable=False)
    ativa: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, onupdate=_utc_now,
        nullable=False,
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    # Relacionamentos
    coordenadores: Mapped[List["Coordenador"]] = relationship(
        back_populates="escola", cascade="all", lazy="selectin",
    )
    professores: Mapped[List["Professor"]] = relationship(
        back_populates="escola", cascade="all", lazy="selectin",
    )
    turmas: Mapped[List["Turma"]] = relationship(
        back_populates="escola", cascade="all", lazy="selectin",
    )

    __table_args__ = (
        CheckConstraint("length(estado) = 2", name="ck_escola_estado_2chars"),
    )


# ──────────────────────────────────────────────────────────────────────
# Coordenador
# ──────────────────────────────────────────────────────────────────────

class Coordenador(Base):
    __tablename__ = "coordenadores"

    id: Mapped[uuid.UUID] = _uuid_pk()
    escola_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("escolas.id"), index=True,
        nullable=False,
    )
    nome: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True,
                                        nullable=False)
    senha_hash: Mapped[Optional[str]] = mapped_column(String(255),
                                                       nullable=True)
    primeiro_acesso_token: Mapped[Optional[str]] = mapped_column(
        String(64), index=True, nullable=True,
    )
    primeiro_acesso_expira_em: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    # M3 — reset de senha
    reset_password_token: Mapped[Optional[str]] = mapped_column(
        String(64), unique=True, index=True, nullable=True,
    )
    reset_password_expira_em: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    ultimo_login_em: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    # M6: corte de validade pra "sair de todas as sessões". Tokens com
    # iat < sessoes_invalidadas_em são rejeitados pelo middleware.
    sessoes_invalidadas_em: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, onupdate=_utc_now,
        nullable=False,
    )

    escola: Mapped[Escola] = relationship(back_populates="coordenadores")


# ──────────────────────────────────────────────────────────────────────
# Professor
# ──────────────────────────────────────────────────────────────────────

class Professor(Base):
    __tablename__ = "professores"

    id: Mapped[uuid.UUID] = _uuid_pk()
    escola_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("escolas.id"), index=True,
        nullable=False,
    )
    nome: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True,
                                        nullable=False)
    senha_hash: Mapped[Optional[str]] = mapped_column(String(255),
                                                       nullable=True)
    primeiro_acesso_token: Mapped[Optional[str]] = mapped_column(
        String(64), index=True, nullable=True,
    )
    primeiro_acesso_expira_em: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    # M3 — reset de senha
    reset_password_token: Mapped[Optional[str]] = mapped_column(
        String(64), unique=True, index=True, nullable=True,
    )
    reset_password_expira_em: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    ultimo_login_em: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    # M6: corte de validade pra "sair de todas as sessões". Tokens com
    # iat < sessoes_invalidadas_em são rejeitados pelo middleware.
    sessoes_invalidadas_em: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, onupdate=_utc_now,
        nullable=False,
    )

    escola: Mapped[Escola] = relationship(back_populates="professores")
    turmas: Mapped[List["Turma"]] = relationship(
        back_populates="professor", cascade="all",
    )


# ──────────────────────────────────────────────────────────────────────
# Turma
# ──────────────────────────────────────────────────────────────────────

SERIES_VALIDAS = ("1S", "2S", "3S")


class Turma(Base):
    __tablename__ = "turmas"

    id: Mapped[uuid.UUID] = _uuid_pk()
    escola_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("escolas.id"), index=True,
        nullable=False,
    )
    professor_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("professores.id"), index=True,
        nullable=False,
    )
    codigo: Mapped[str] = mapped_column(String(32), nullable=False)
    serie: Mapped[str] = mapped_column(String(2), nullable=False)
    codigo_join: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False,
    )
    ano_letivo: Mapped[int] = mapped_column(Integer, nullable=False)
    ativa: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, onupdate=_utc_now,
        nullable=False,
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    escola: Mapped[Escola] = relationship(back_populates="turmas")
    professor: Mapped[Professor] = relationship(back_populates="turmas")
    alunos: Mapped[List["AlunoTurma"]] = relationship(
        back_populates="turma", cascade="all", lazy="selectin",
    )
    atividades: Mapped[List["Atividade"]] = relationship(
        back_populates="turma", cascade="all",
    )

    __table_args__ = (
        CheckConstraint(
            "serie IN ('1S', '2S', '3S')",
            name="ck_turma_serie_em_set",
        ),
    )


# ──────────────────────────────────────────────────────────────────────
# AlunoTurma
# ──────────────────────────────────────────────────────────────────────

class AlunoTurma(Base):
    __tablename__ = "alunos_turma"

    id: Mapped[uuid.UUID] = _uuid_pk()
    turma_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("turmas.id"), index=True,
        nullable=False,
    )
    nome: Mapped[str] = mapped_column(String(255), nullable=False)
    telefone: Mapped[str] = mapped_column(String(20), index=True,
                                           nullable=False)
    vinculado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, nullable=False,
    )
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, onupdate=_utc_now,
        nullable=False,
    )

    turma: Mapped[Turma] = relationship(back_populates="alunos")
    envios: Mapped[List["Envio"]] = relationship(
        back_populates="aluno_turma", cascade="all",
    )

    __table_args__ = (
        UniqueConstraint("turma_id", "telefone", name="uq_aluno_turma_phone"),
    )


# ──────────────────────────────────────────────────────────────────────
# Atividade
# ──────────────────────────────────────────────────────────────────────

# Whitelist de missões REJ 1S — popular via seed_missoes (M4).
MISSOES_VALIDAS = (
    "RJ1·OF10·MF",
    "RJ1·OF11·MF",
    "RJ1·OF12·MF",
    "RJ1·OF13·MF",
    "RJ1·OF14·MF",
)

MODO_CORRECAO_VALIDOS = (
    "foco_c1", "foco_c2", "foco_c3", "foco_c4", "foco_c5",
    "completo_parcial", "completo",
)

ATIVIDADE_STATUS = ("agendada", "ativa", "encerrada")


class Missao(Base):
    """Catálogo de missões disponíveis. Populado por
    [`seed_missoes.py`](../portal/seed_missoes.py)."""
    __tablename__ = "missoes"

    id: Mapped[uuid.UUID] = _uuid_pk()
    codigo: Mapped[str] = mapped_column(
        String(32), unique=True, index=True, nullable=False,
    )
    serie: Mapped[str] = mapped_column(String(2), nullable=False)
    oficina_numero: Mapped[int] = mapped_column(Integer, nullable=False)
    titulo: Mapped[str] = mapped_column(String(120), nullable=False)
    modo_correcao: Mapped[str] = mapped_column(String(32), nullable=False)
    ativa: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, onupdate=_utc_now,
        nullable=False,
    )

    atividades: Mapped[List["Atividade"]] = relationship(
        back_populates="missao",
    )

    __table_args__ = (
        CheckConstraint(
            "serie IN ('1S', '2S', '3S')",
            name="ck_missao_serie",
        ),
        CheckConstraint(
            "modo_correcao IN ('foco_c1', 'foco_c2', "
            "'foco_c3', 'foco_c4', 'foco_c5', "
            "'completo_parcial', 'completo')",
            name="ck_missao_modo_correcao",
        ),
    )


class Atividade(Base):
    __tablename__ = "atividades"

    id: Mapped[uuid.UUID] = _uuid_pk()
    turma_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("turmas.id"), index=True,
        nullable=False,
    )
    # M4: missao_id virou FK pra catálogo `missoes`. Em M2/M3 era
    # String(32) com CHECK enum; migração trocou pra UUID.
    missao_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("missoes.id"), index=True,
        nullable=False,
    )
    data_inicio: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True, nullable=False,
    )
    data_fim: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True, nullable=False,
    )
    criada_por_professor_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("professores.id"), nullable=False,
    )
    notas_criacao: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # M4: idempotência de notificação aos alunos.
    notificacao_enviada_em: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, onupdate=_utc_now,
        nullable=False,
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    turma: Mapped[Turma] = relationship(back_populates="atividades")
    missao: Mapped[Missao] = relationship(back_populates="atividades")
    envios: Mapped[List["Envio"]] = relationship(
        back_populates="atividade", cascade="all",
    )

    __table_args__ = (
        CheckConstraint(
            "data_fim > data_inicio",
            name="ck_atividade_intervalo_valido",
        ),
        Index("ix_atividade_turma_missao_inicio",
              "turma_id", "missao_id", "data_inicio"),
    )

    @property
    def status(self) -> str:
        """Status calculado a partir das datas vs UTC agora.

        agendada — antes de data_inicio
        ativa    — entre data_inicio e data_fim (inclusive)
        encerrada — depois de data_fim
        """
        agora = _utc_now()
        # Se o objeto vem do DB com tz-naive (raro mas possível em SQLite),
        # assume UTC pra comparar coerente com `agora`.
        ini = self.data_inicio
        fim = self.data_fim
        if ini.tzinfo is None:
            ini = ini.replace(tzinfo=timezone.utc)
        if fim.tzinfo is None:
            fim = fim.replace(tzinfo=timezone.utc)
        if agora < ini:
            return "agendada"
        if agora <= fim:
            return "ativa"
        return "encerrada"


# ──────────────────────────────────────────────────────────────────────
# Envio
# ──────────────────────────────────────────────────────────────────────

class Envio(Base):
    __tablename__ = "envios"

    id: Mapped[uuid.UUID] = _uuid_pk()
    atividade_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("atividades.id"), index=True,
        nullable=False,
    )
    aluno_turma_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("alunos_turma.id"), index=True,
        nullable=False,
    )
    # FK pra interactions.id (INTEGER, definido em Interaction abaixo)
    interaction_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("interactions.id"), index=True, nullable=True,
    )
    enviado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, nullable=False,
    )
    # M9.6 (2026-04-29): número da tentativa do aluno nessa atividade.
    # Antes desse milestone, havia constraint UNIQUE (atividade_id,
    # aluno_turma_id) que bloqueava reenvios — quando aluno escolhia
    # "reavaliar como nova tentativa" no bot, o INSERT do novo envio
    # falhava silenciosamente. Agora a constraint inclui tentativa_n,
    # permitindo histórico completo. Default 1 cobre rows pré-M9.6
    # (backfilled pela migration g0a1b2c3d4e5).
    tentativa_n: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, onupdate=_utc_now,
        nullable=False,
    )

    atividade: Mapped[Atividade] = relationship(back_populates="envios")
    aluno_turma: Mapped[AlunoTurma] = relationship(back_populates="envios")
    # Há 2 FKs entre envios e interactions (envios.interaction_id e
    # interactions.envio_id). Cada relacionamento aponta pra uma FK
    # específica e NÃO usa back_populates pra evitar ambiguidade de
    # direção. Pra navegar inverso, use `Interaction.envio` (definido
    # na classe Interaction com a FK envio_id).
    interaction: Mapped[Optional["Interaction"]] = relationship(
        foreign_keys="Envio.interaction_id",
    )

    __table_args__ = (
        UniqueConstraint(
            "atividade_id", "aluno_turma_id", "tentativa_n",
            name="uq_envio_atividade_aluno_tentativa",
        ),
    )


# ──────────────────────────────────────────────────────────────────────
# Interaction (legado, agora SQLAlchemy + Postgres)
# ──────────────────────────────────────────────────────────────────────
# Modelo SQLAlchemy da tabela `interactions` que existe desde a Fase A
# (originalmente em SQLite, vide redato_backend.whatsapp.persistence).
# Migração Sqlite → Postgres preserva o schema legado + adiciona:
# - `aluno_turma_id` (nullable, populado a partir de M4)
# - `envio_id`        (nullable, populado a partir de M4)
# - `source`          (default "whatsapp_v1")
#
# `aluno_phone` continua sendo gravado pelo bot atual (Fase A); fica
# como **fallback transitório**. Cleanup retroativo (popular
# aluno_turma_id por matching de telefone, depois remover aluno_phone)
# é débito técnico anotado no portal/README.md — NÃO executar em M1.

class Interaction(Base):
    __tablename__ = "interactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True,
                                     autoincrement=True)
    aluno_phone: Mapped[str] = mapped_column(String(20), index=True,
                                              nullable=False)
    # M4 popula. Antes disso, NULL.
    aluno_turma_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("alunos_turma.id"),
        nullable=True, index=True,
    )
    # M4 popula. Antes disso, NULL.
    # use_alter=True: FK criada via ALTER TABLE depois das duas tabelas
    # existirem. Resolve dependência circular envios.interaction_id ↔
    # interactions.envio_id.
    envio_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("envios.id", use_alter=True, name="fk_interactions_envio"),
        nullable=True, index=True,
    )
    # Distingue Fase A (whatsapp_v1, sem atividade) de M4+ (whatsapp_v2).
    source: Mapped[str] = mapped_column(
        String(32), default="whatsapp_v1", nullable=False,
    )

    # Campos legados — preservar nomes idênticos aos do SQLite atual.
    turma_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    missao_id: Mapped[str] = mapped_column(String(32), nullable=False)
    activity_id: Mapped[str] = mapped_column(String(64), nullable=False)
    foto_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    foto_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    texto_transcrito: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ocr_quality_issues: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ocr_metrics: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    redato_output: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resposta_aluno: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    elapsed_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    invalidated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, nullable=False,
    )

    # Aponta pro envio dono dessa interação (M4+). Usa a FK envio_id
    # explicitamente — a outra FK (envios.interaction_id) é coberta
    # por Envio.interaction.
    envio: Mapped[Optional[Envio]] = relationship(
        foreign_keys=[envio_id],
    )

    __table_args__ = (
        Index("ix_interactions_phone_created",
              "aluno_phone", "created_at"),
        Index("ix_interactions_missao_created",
              "missao_id", "created_at"),
        Index("ix_interactions_phone_missao_hash",
              "aluno_phone", "missao_id", "foto_hash"),
    )


# ──────────────────────────────────────────────────────────────────────
# TokenBlocklist (M3 — JWT logout)
# ──────────────────────────────────────────────────────────────────────

class TokenBlocklist(Base):
    """JTI claim de JWTs revogados via /auth/logout. Cleanup periódico
    remove entradas com `exp_original < now()` — após exp natural não
    há razão pra manter na blocklist."""
    __tablename__ = "token_blocklist"

    id: Mapped[uuid.UUID] = _uuid_pk()
    token_jti: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False,
    )
    blocklisted_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, nullable=False,
    )
    exp_original: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True, nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, nullable=False,
    )


# ──────────────────────────────────────────────────────────────────────
# PdfGerado (M8)
# ──────────────────────────────────────────────────────────────────────

PDF_TIPOS = (
    "dashboard_turma", "dashboard_escola",
    "evolucao_aluno", "atividade_detalhe",
)


class PdfGerado(Base):
    """Histórico de PDFs gerados pelo portal (M8).

    `arquivo_path` é relativo a STORAGE_PDFS_PATH (default
    `data/portal/pdfs`). Em Railway, esse diretório deve estar em
    volume persistente — caso contrário, PDFs são perdidos no deploy.

    Política de retenção: 365 dias. Cleanup futuro pode remover
    entradas + arquivos com `gerado_em < now() - 365d`.
    """
    __tablename__ = "pdfs_gerados"

    id: Mapped[uuid.UUID] = _uuid_pk()
    tipo: Mapped[str] = mapped_column(String(32), nullable=False)
    escopo_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False, index=True,
    )
    escola_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("escolas.id"),
        nullable=False, index=True,
    )
    gerado_por_user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False,
    )
    gerado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, nullable=False,
    )
    arquivo_path: Mapped[str] = mapped_column(String(255), nullable=False)
    tamanho_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    parametros: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "tipo IN ('dashboard_turma', 'dashboard_escola', "
            "'evolucao_aluno', 'atividade_detalhe')",
            name="ck_pdf_tipo_em_set",
        ),
        Index("ix_pdf_escopo_tipo_gerado",
              "escopo_id", "tipo", "gerado_em"),
    )
