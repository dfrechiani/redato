"""Triggers automáticos de email transacional (M8).

Os triggers são chamados por:
1. Endpoint `POST /admin/triggers/run` — invocado por cron externo
   (Railway cron / GitHub Actions / etc.) com frequência diária.
2. Hooks oportunistas no app (ex.: ao encerrar atividade manualmente).

Não fazem cron interno — preferimos cron externo pra que o app possa
escalar horizontal sem disputa de leader election.

Estado: usamos a tabela `pdfs_gerados.parametros` ou um JSONL de audit
log (`data/portal/triggers_log.jsonl`) pra dedupe — não criamos uma
tabela dedicada de "triggers disparados" por simplicidade. Refinamento
futuro pode formalizar.

Limite de spam:
- Atividade encerrada: 1× por (atividade, prof). Marcado por
  `Atividade.notificacao_enviada_em` reaproveitada como flag de aviso?
  → não, esse campo é da notificação aos alunos. Usamos JSONL.
- Alunos em risco: 1× por semana por turma+professor.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from redato_backend.portal.db import get_engine
from redato_backend.portal import email_service as ES
from redato_backend.portal.models import (
    AlunoTurma, Atividade, Envio, Missao, Professor, Turma,
)


_BACKEND = Path(__file__).resolve().parents[2]
_TRIGGERS_LOG = _BACKEND / "data" / "portal" / "triggers_log.jsonl"

# Limite anti-spam: alerta de alunos em risco no máximo 1× por semana.
RATE_LIMIT_RISCO_DIAS = 7
# Mínimo de missões abaixo pra considerar "em risco" no email.
MIN_MISSOES_RISCO = 3


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _log_trigger(record: dict) -> None:
    _TRIGGERS_LOG.parent.mkdir(parents=True, exist_ok=True)
    record_full = {"ts": _utc_now().isoformat(), **record}
    with _TRIGGERS_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record_full, ensure_ascii=False, default=str) + "\n")


def _last_trigger(kind: str, scope_key: str) -> Optional[datetime]:
    """Lê JSONL pra ver quando o último trigger desse tipo+escopo
    rolou. Retorna None se nunca."""
    if not _TRIGGERS_LOG.exists():
        return None
    last: Optional[datetime] = None
    with _TRIGGERS_LOG.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                rec = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue
            if rec.get("kind") != kind or rec.get("scope_key") != scope_key:
                continue
            try:
                ts = datetime.fromisoformat(rec.get("ts"))
                if last is None or ts > last:
                    last = ts
            except (TypeError, ValueError):
                continue
    return last


# ──────────────────────────────────────────────────────────────────────
# Helpers de domínio
# ──────────────────────────────────────────────────────────────────────

def _modo_bucket(modo: Optional[str]) -> str:
    if modo and modo.startswith("foco_"):
        return "foco"
    return "completo"


def _is_insuficiente(modo: Optional[str], nota: Optional[int]) -> bool:
    if nota is None:
        return False
    if _modo_bucket(modo) == "foco":
        return nota <= 80
    return nota <= 400


def _parse_nota(redato_output_json: Optional[str]) -> Optional[int]:
    if not redato_output_json:
        return None
    try:
        out = json.loads(redato_output_json)
    except (ValueError, TypeError):
        return None
    for key in ("nota_total", "total", "nota"):
        v = out.get(key)
        if isinstance(v, (int, float)):
            return int(v)
    return None


@dataclass
class TriggerResult:
    """Resultado de um run de triggers."""
    encerradas_avisadas: int = 0
    risco_avisados: int = 0
    skipped: int = 0


# ──────────────────────────────────────────────────────────────────────
# Trigger 1: atividade encerrada com pendentes
# ──────────────────────────────────────────────────────────────────────

def trigger_atividade_encerrada(
    atividade_id, *, force: bool = False,
) -> bool:
    """Avisa o professor responsável quando a atividade encerrou e há
    pendentes. Retorna True se enviou, False se pulou (rate-limited ou
    sem pendentes).

    `force=True` ignora rate limit — usado por hook manual ao encerrar
    via UI. Cron diário sempre passa force=False.
    """
    scope = f"atividade:{atividade_id}"
    if not force:
        last = _last_trigger("atividade_encerrada", scope)
        if last is not None:
            # Já avisado uma vez; não reenvia
            return False

    with Session(get_engine()) as session:
        ativ = session.get(Atividade, atividade_id)
        if ativ is None or ativ.deleted_at is not None:
            return False
        # Só dispara pra atividades já encerradas.
        if ativ.data_fim > _utc_now():
            return False
        turma = session.get(Turma, ativ.turma_id)
        if turma is None or not turma.ativa:
            return False
        prof = session.get(Professor, turma.professor_id)
        if prof is None or not prof.ativo or not prof.email:
            return False
        missao = session.get(Missao, ativ.missao_id)

        # Conta pendentes
        n_alunos = session.execute(
            select(AlunoTurma).where(
                AlunoTurma.turma_id == turma.id,
                AlunoTurma.ativo.is_(True),
            )
        ).scalars().all()
        n_total = len(n_alunos)
        n_enviados = session.execute(
            select(Envio).where(Envio.atividade_id == ativ.id)
        ).scalars().all()
        n_pendentes = n_total - len(n_enviados)

    if n_pendentes <= 0:
        return False

    ok, msg = ES.send_atividade_encerrada_pendentes(
        to_email=prof.email, to_name=prof.nome,
        turma_codigo=turma.codigo,
        missao_codigo=missao.codigo if missao else "?",
        missao_titulo=missao.titulo if missao else "?",
        oficina_numero=missao.oficina_numero if missao else None,
        modo_correcao=missao.modo_correcao if missao else None,
        atividade_id=str(atividade_id),
        n_pendentes=n_pendentes,
    )
    _log_trigger({
        "kind": "atividade_encerrada", "scope_key": scope,
        "atividade_id": str(atividade_id),
        "prof_email": prof.email,
        "n_pendentes": n_pendentes, "ok": ok, "msg": msg,
    })
    return bool(ok)


# ──────────────────────────────────────────────────────────────────────
# Trigger 2: alunos em risco
# ──────────────────────────────────────────────────────────────────────

def trigger_alunos_em_risco(turma_id, *, force: bool = False) -> bool:
    """Avisa o professor sobre alunos com ≥ MIN_MISSOES_RISCO missões
    insuficientes. Rate-limited a 1×/semana por turma.

    Retorna True se mandou email, False senão.
    """
    scope = f"turma:{turma_id}"
    if not force:
        last = _last_trigger("alunos_risco", scope)
        if last is not None:
            cutoff = _utc_now() - timedelta(days=RATE_LIMIT_RISCO_DIAS)
            if last > cutoff:
                return False

    with Session(get_engine()) as session:
        turma = session.get(Turma, turma_id)
        if turma is None or not turma.ativa or turma.deleted_at is not None:
            return False
        prof = session.get(Professor, turma.professor_id)
        if prof is None or not prof.ativo or not prof.email:
            return False

        # Lista atividades não-deletadas + envios + interactions
        atividades = session.execute(
            select(Atividade).where(
                Atividade.turma_id == turma.id,
                Atividade.deleted_at.is_(None),
            )
        ).scalars().all()
        if not atividades:
            return False
        ativ_by_id = {a.id: a for a in atividades}

        # Pra cada envio, decide se nota é insuficiente
        from redato_backend.portal.models import Interaction  # noqa: WPS433
        rows = session.execute(
            select(Envio, Atividade, Missao)
            .join(Atividade, Atividade.id == Envio.atividade_id)
            .join(Missao, Missao.id == Atividade.missao_id)
            .where(Envio.atividade_id.in_([a.id for a in atividades]))
        ).all()

        contagem: Dict[str, Dict[str, object]] = {}
        for envio, ativ, missao in rows:
            interaction = (
                session.get(Interaction, envio.interaction_id)
                if envio.interaction_id else None
            )
            nota = _parse_nota(interaction.redato_output if interaction else None)
            if not _is_insuficiente(missao.modo_correcao, nota):
                continue
            aluno = session.get(AlunoTurma, envio.aluno_turma_id)
            if aluno is None or not aluno.ativo:
                continue
            slot = contagem.setdefault(str(aluno.id), {
                "aluno_id": str(aluno.id),
                "nome": aluno.nome, "n_missoes_baixa": 0,
            })
            slot["n_missoes_baixa"] = int(slot["n_missoes_baixa"]) + 1

        em_risco = [
            v for v in contagem.values()
            if int(v["n_missoes_baixa"]) >= MIN_MISSOES_RISCO
        ]
        em_risco.sort(key=lambda x: -int(x["n_missoes_baixa"]))

    if not em_risco:
        return False

    ok, msg = ES.send_alunos_em_risco_alert(
        to_email=prof.email, to_name=prof.nome,
        turma_id=str(turma_id), turma_codigo=turma.codigo,
        alunos=em_risco,
    )
    _log_trigger({
        "kind": "alunos_risco", "scope_key": scope,
        "turma_id": str(turma_id),
        "prof_email": prof.email,
        "n_alunos": len(em_risco), "ok": ok, "msg": msg,
    })
    return bool(ok)


# ──────────────────────────────────────────────────────────────────────
# Run completo: percorre todas atividades/turmas e dispara o que tem
# ──────────────────────────────────────────────────────────────────────

def check_e_disparar_triggers() -> TriggerResult:
    """Varre o estado atual do banco e dispara triggers oportunistas.

    Idempotente via dedup de JSONL — pode rodar várias vezes/dia sem
    problema.
    """
    res = TriggerResult()
    with Session(get_engine()) as session:
        # Atividades encerradas nos últimos 30 dias (não muito retroativo)
        cutoff = _utc_now() - timedelta(days=30)
        atividades = session.execute(
            select(Atividade.id).where(
                Atividade.deleted_at.is_(None),
                Atividade.data_fim < _utc_now(),
                Atividade.data_fim > cutoff,
            )
        ).scalars().all()

        turmas = session.execute(
            select(Turma.id).where(
                Turma.deleted_at.is_(None),
                Turma.ativa.is_(True),
            )
        ).scalars().all()

    for atv_id in atividades:
        try:
            if trigger_atividade_encerrada(atv_id):
                res.encerradas_avisadas += 1
            else:
                res.skipped += 1
        except Exception as exc:  # noqa: BLE001
            _log_trigger({
                "kind": "atividade_encerrada_error",
                "scope_key": f"atividade:{atv_id}",
                "error": f"{type(exc).__name__}: {exc}",
            })

    for turma_id in turmas:
        try:
            if trigger_alunos_em_risco(turma_id):
                res.risco_avisados += 1
            else:
                res.skipped += 1
        except Exception as exc:  # noqa: BLE001
            _log_trigger({
                "kind": "alunos_risco_error",
                "scope_key": f"turma:{turma_id}",
                "error": f"{type(exc).__name__}: {exc}",
            })

    return res
