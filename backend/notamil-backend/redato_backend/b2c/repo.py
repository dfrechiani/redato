"""Acesso a dados do B2C (Postgres via portal.db).

Retorna DTOs *desacoplados* da sessão (nada de ORM detached vazando pro
router) — assim os handlers ficam puros o suficiente pra teste, e os
testes monkeypatcham estas funções por fakes em memória (mesmo idioma
dos testes de `portal_link` no fluxo escola).

Nenhuma função aqui é chamada quando REDATO_B2C_ENABLED está off — o
desvio no bot é guardado pela flag antes de tocar este módulo.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from sqlalchemy import func, select

from redato_backend.portal.db import get_session
from redato_backend.portal.models import (
    AlunoB2C, AssinaturaB2C, EnvioB2C, EventoBilling,
    NotificacaoDegradada, ParceiroB2C,
)


_BRT = ZoneInfo("America/Sao_Paulo")


# ──────────────────────────────────────────────────────────────────────
# DTOs (detached — seguros pra usar fora da sessão)
# ──────────────────────────────────────────────────────────────────────

@dataclass
class ParceiroDTO:
    id: str
    slug: str
    codigo_entrada: str
    nome_publico: str
    nome_professor: str
    wallet_id_asaas: Optional[str]
    share_pct: Optional[float]
    preco_centavos: int
    ativo: bool
    branding: Dict[str, Any]


@dataclass
class AlunoDTO:
    id: str
    telefone_e164: str
    nome: Optional[str]
    parceiro_id: str
    estado: str
    cpf: Optional[str]
    correcoes_gratis_usadas: int
    consent_lgpd_at: Optional[datetime]
    consent_version: Optional[str] = None
    ultima_inbound_at: Optional[datetime] = None
    ultimo_tema_sorteado: Optional[str] = None
    ultimo_tema_sorteado_at: Optional[datetime] = None


@dataclass
class AssinaturaDTO:
    id: str
    aluno_id: str
    asaas_customer_id: Optional[str]
    asaas_subscription_id: Optional[str]
    status: str
    valor_centavos: int
    ciclo: str
    proximo_vencimento: Optional[datetime]
    overdue_desde: Optional[datetime] = None
    regua_estagio: int = 0


def _parceiro_dto(p: ParceiroB2C) -> ParceiroDTO:
    return ParceiroDTO(
        id=str(p.id), slug=p.slug, codigo_entrada=p.codigo_entrada,
        nome_publico=p.nome_publico, nome_professor=p.nome_professor,
        wallet_id_asaas=p.wallet_id_asaas,
        share_pct=float(p.share_pct) if p.share_pct is not None else None,
        preco_centavos=int(p.preco_centavos), ativo=bool(p.ativo),
        branding=dict(p.branding or {}),
    )


def _aluno_dto(a: AlunoB2C) -> AlunoDTO:
    return AlunoDTO(
        id=str(a.id), telefone_e164=a.telefone_e164, nome=a.nome,
        parceiro_id=str(a.parceiro_id), estado=a.estado, cpf=a.cpf,
        correcoes_gratis_usadas=int(a.correcoes_gratis_usadas),
        consent_lgpd_at=a.consent_lgpd_at,
        consent_version=a.consent_version,
        ultima_inbound_at=a.ultima_inbound_at,
        ultimo_tema_sorteado=a.ultimo_tema_sorteado,
        ultimo_tema_sorteado_at=a.ultimo_tema_sorteado_at,
    )


def _assinatura_dto(s: AssinaturaB2C) -> AssinaturaDTO:
    return AssinaturaDTO(
        id=str(s.id), aluno_id=str(s.aluno_id),
        asaas_customer_id=s.asaas_customer_id,
        asaas_subscription_id=s.asaas_subscription_id,
        status=s.status, valor_centavos=int(s.valor_centavos),
        ciclo=s.ciclo, proximo_vencimento=s.proximo_vencimento,
        overdue_desde=s.overdue_desde, regua_estagio=int(s.regua_estagio),
    )


# ──────────────────────────────────────────────────────────────────────
# Parceiros
# ──────────────────────────────────────────────────────────────────────

def get_parceiro_por_codigo(codigo: str) -> Optional[ParceiroDTO]:
    """Casa o código de entrada (case-insensitive). Só parceiros ativos."""
    if not codigo:
        return None
    alvo = codigo.strip().upper()
    with get_session() as s:
        p = s.execute(
            select(ParceiroB2C).where(
                func.upper(ParceiroB2C.codigo_entrada) == alvo,
                ParceiroB2C.ativo.is_(True),
            )
        ).scalar_one_or_none()
        return _parceiro_dto(p) if p else None


def get_parceiro_por_slug(slug: str) -> Optional[ParceiroDTO]:
    with get_session() as s:
        p = s.execute(
            select(ParceiroB2C).where(ParceiroB2C.slug == slug)
        ).scalar_one_or_none()
        return _parceiro_dto(p) if p else None


def get_parceiro_por_id(parceiro_id: str) -> Optional[ParceiroDTO]:
    with get_session() as s:
        p = s.get(ParceiroB2C, parceiro_id)
        return _parceiro_dto(p) if p else None


# ──────────────────────────────────────────────────────────────────────
# Alunos (FSM por telefone)
# ──────────────────────────────────────────────────────────────────────

def get_aluno_por_telefone(telefone: str) -> Optional[AlunoDTO]:
    with get_session() as s:
        a = s.execute(
            select(AlunoB2C).where(AlunoB2C.telefone_e164 == telefone)
        ).scalar_one_or_none()
        return _aluno_dto(a) if a else None


def get_aluno_por_id(aluno_id: str) -> Optional[AlunoDTO]:
    with get_session() as s:
        a = s.get(AlunoB2C, aluno_id)
        return _aluno_dto(a) if a else None


def criar_aluno(telefone: str, parceiro_id: str,
                estado: str = "novo") -> AlunoDTO:
    with get_session() as s:
        a = AlunoB2C(
            telefone_e164=telefone, parceiro_id=parceiro_id, estado=estado,
        )
        s.add(a)
        s.flush()
        return _aluno_dto(a)


def atualizar_aluno(telefone: str, **campos: Any) -> Optional[AlunoDTO]:
    """Atualiza campos do aluno (estado, nome, cpf, consent_lgpd_at)."""
    with get_session() as s:
        a = s.execute(
            select(AlunoB2C).where(AlunoB2C.telefone_e164 == telefone)
        ).scalar_one_or_none()
        if a is None:
            return None
        for k, v in campos.items():
            setattr(a, k, v)
        s.flush()
        return _aluno_dto(a)


def incrementar_gratis(telefone: str) -> Optional[AlunoDTO]:
    with get_session() as s:
        a = s.execute(
            select(AlunoB2C).where(AlunoB2C.telefone_e164 == telefone)
        ).scalar_one_or_none()
        if a is None:
            return None
        a.correcoes_gratis_usadas = int(a.correcoes_gratis_usadas) + 1
        s.flush()
        return _aluno_dto(a)


# ──────────────────────────────────────────────────────────────────────
# Envios / histórico / fair use
# ──────────────────────────────────────────────────────────────────────

def registrar_envio(
    aluno_id: str,
    parceiro_id: str,
    *,
    texto_ocr: Optional[str] = None,
    texto_final: Optional[str] = None,
    nota_total: Optional[int] = None,
    notas_competencias: Optional[Dict[str, Any]] = None,
    diagnostico: Optional[Dict[str, Any]] = None,
    gratis: bool = False,
    tempo_processamento_ms: Optional[int] = None,
    custo_estimado_centavos: Optional[int] = None,
    imagem_url: Optional[str] = None,
    tema: Optional[str] = None,
    status: str = "corrigido",
) -> str:
    with get_session() as s:
        e = EnvioB2C(
            aluno_id=aluno_id, parceiro_id=parceiro_id,
            texto_ocr=texto_ocr, texto_final=texto_final,
            nota_total=nota_total, notas_competencias=notas_competencias,
            diagnostico=diagnostico, gratis=gratis,
            tempo_processamento_ms=tempo_processamento_ms,
            custo_estimado_centavos=custo_estimado_centavos,
            imagem_url=imagem_url, tema=tema, status=status,
        )
        s.add(e)
        s.flush()
        return str(e.id)


def contar_envios_hoje(aluno_id: str, *, agora: Optional[datetime] = None) -> int:
    """Correções do aluno no dia corrente (fuso de Brasília)."""
    agora = agora or datetime.now(timezone.utc)
    inicio_brt = agora.astimezone(_BRT).replace(
        hour=0, minute=0, second=0, microsecond=0,
    )
    inicio_utc = inicio_brt.astimezone(timezone.utc)
    with get_session() as s:
        n = s.execute(
            select(func.count()).select_from(EnvioB2C).where(
                EnvioB2C.aluno_id == aluno_id,
                EnvioB2C.created_at >= inicio_utc,
                # ADENDO §D7: fair use conta SÓ envio efetivamente corrigido
                # — foto pendente de tema não queima o dia.
                EnvioB2C.status == "corrigido",
            )
        ).scalar_one()
        return int(n or 0)


def listar_notas_competencias(
    aluno_id: str, limite: int = 20,
) -> List[Dict[str, Any]]:
    """notas_competencias dos envios recentes (pra médias/pior comp. no
    comando 'evolução')."""
    with get_session() as s:
        rows = s.execute(
            select(EnvioB2C.notas_competencias).where(
                EnvioB2C.aluno_id == aluno_id,
                EnvioB2C.notas_competencias.isnot(None),
            ).order_by(EnvioB2C.created_at.desc()).limit(limite)
        ).scalars().all()
    return [dict(r) for r in rows if r]


def ultimas_notas(aluno_id: str, limite: int = 5) -> List[int]:
    """Últimas notas totais (mais antiga → mais recente) pra linha de
    evolução '800 → 840 → 880'."""
    with get_session() as s:
        rows = s.execute(
            select(EnvioB2C.nota_total).where(
                EnvioB2C.aluno_id == aluno_id,
                EnvioB2C.nota_total.isnot(None),
            ).order_by(EnvioB2C.created_at.desc()).limit(limite)
        ).scalars().all()
    notas = [int(n) for n in rows if n is not None]
    notas.reverse()
    return notas


def contar_corrigidos(aluno_id: str) -> int:
    """Total de envios efetivamente corrigidos (pro bloco de evolução do
    M6, que só aparece com ≥2 — §9.2)."""
    with get_session() as s:
        n = s.execute(
            select(func.count()).select_from(EnvioB2C).where(
                EnvioB2C.aluno_id == aluno_id,
                EnvioB2C.status == "corrigido",
            )
        ).scalar_one()
        return int(n or 0)


# ──────────────────────────────────────────────────────────────────────
# Fluxo do tema (D7) — envio pendente aguardando_tema
# ──────────────────────────────────────────────────────────────────────

def get_envio_pendente(aluno_id: str) -> Optional[Dict[str, Any]]:
    """O (único) envio do aluno em `aguardando_tema`, se houver."""
    with get_session() as s:
        e = s.execute(
            select(EnvioB2C).where(
                EnvioB2C.aluno_id == aluno_id,
                EnvioB2C.status == "aguardando_tema",
            ).order_by(EnvioB2C.created_at.desc())
        ).scalars().first()
        if e is None:
            return None
        return {"id": str(e.id), "texto_ocr": e.texto_ocr, "tema": e.tema,
                "gratis": bool(e.gratis)}


def substituir_envio_pendente(
    aluno_id: str, parceiro_id: str, *,
    texto_ocr: Optional[str], gratis: bool = False,
    tema: Optional[str] = None,
) -> str:
    """Cria um envio `aguardando_tema`, removendo qualquer pendência
    anterior do aluno (regra: máx 1 pendente — nova foto substitui)."""
    with get_session() as s:
        antigos = s.execute(
            select(EnvioB2C).where(
                EnvioB2C.aluno_id == aluno_id,
                EnvioB2C.status == "aguardando_tema",
            )
        ).scalars().all()
        for a in antigos:
            s.delete(a)
        e = EnvioB2C(
            aluno_id=aluno_id, parceiro_id=parceiro_id, texto_ocr=texto_ocr,
            texto_final=texto_ocr, tema=tema, gratis=gratis,
            status="aguardando_tema",
        )
        s.add(e)
        s.flush()
        return str(e.id)


def corrigir_envio_pendente(
    envio_id: str, *, tema: str, nota_total: Optional[int],
    notas_competencias: Optional[Dict[str, Any]],
    custo_estimado_centavos: Optional[int] = None,
    tempo_processamento_ms: Optional[int] = None,
) -> None:
    """Resolve o tema de um envio pendente → status `corrigido`."""
    with get_session() as s:
        e = s.get(EnvioB2C, envio_id)
        if e is None:
            return
        e.tema = tema
        e.nota_total = nota_total
        e.notas_competencias = notas_competencias
        e.custo_estimado_centavos = custo_estimado_centavos
        e.tempo_processamento_ms = tempo_processamento_ms
        e.status = "corrigido"


def atualizar_tema_pendente(envio_id: str, tema: Optional[str]) -> None:
    """Atualiza o campo `tema` (candidato/sentinel) de um envio pendente
    — usado pelo anti-loop (M17) e ajustes de candidato."""
    with get_session() as s:
        e = s.get(EnvioB2C, envio_id)
        if e is not None and e.status == "aguardando_tema":
            e.tema = tema


def registrar_envio_bloqueado(
    aluno_id: str, parceiro_id: str,
) -> str:
    """Foto de aluno inadimplente: grava SEM rodar OCR/grader (custo zero,
    §D10). status='bloqueado'."""
    return registrar_envio(
        aluno_id, parceiro_id, status="bloqueado",
    )


# ──────────────────────────────────────────────────────────────────────
# Assinaturas
# ──────────────────────────────────────────────────────────────────────

def get_assinatura_por_aluno(aluno_id: str) -> Optional[AssinaturaDTO]:
    with get_session() as s:
        sub = s.execute(
            select(AssinaturaB2C).where(AssinaturaB2C.aluno_id == aluno_id)
        ).scalar_one_or_none()
        return _assinatura_dto(sub) if sub else None


def get_assinatura_por_subscription(sub_id: str) -> Optional[AssinaturaDTO]:
    with get_session() as s:
        sub = s.execute(
            select(AssinaturaB2C).where(
                AssinaturaB2C.asaas_subscription_id == sub_id
            )
        ).scalar_one_or_none()
        return _assinatura_dto(sub) if sub else None


def upsert_assinatura(
    aluno_id: str,
    *,
    valor_centavos: int,
    asaas_customer_id: Optional[str] = None,
    asaas_subscription_id: Optional[str] = None,
    status: str = "pendente",
    ciclo: str = "MONTHLY",
    proximo_vencimento: Optional[datetime] = None,
) -> AssinaturaDTO:
    with get_session() as s:
        sub = s.execute(
            select(AssinaturaB2C).where(AssinaturaB2C.aluno_id == aluno_id)
        ).scalar_one_or_none()
        if sub is None:
            sub = AssinaturaB2C(aluno_id=aluno_id, valor_centavos=valor_centavos)
            s.add(sub)
        sub.valor_centavos = valor_centavos
        if asaas_customer_id is not None:
            sub.asaas_customer_id = asaas_customer_id
        if asaas_subscription_id is not None:
            sub.asaas_subscription_id = asaas_subscription_id
        sub.status = status
        sub.ciclo = ciclo
        if proximo_vencimento is not None:
            sub.proximo_vencimento = proximo_vencimento
        s.flush()
        return _assinatura_dto(sub)


def atualizar_status_assinatura(
    sub_id: str, status: str,
    *, proximo_vencimento: Optional[datetime] = None,
) -> Optional[AssinaturaDTO]:
    with get_session() as s:
        sub = s.execute(
            select(AssinaturaB2C).where(
                AssinaturaB2C.asaas_subscription_id == sub_id
            )
        ).scalar_one_or_none()
        if sub is None:
            return None
        sub.status = status
        if proximo_vencimento is not None:
            sub.proximo_vencimento = proximo_vencimento
        s.flush()
        return _assinatura_dto(sub)


# ──────────────────────────────────────────────────────────────────────
# Régua de inadimplência (D8) — overdue_desde + regua_estagio
# ──────────────────────────────────────────────────────────────────────

def iniciar_overdue(sub_id: str, quando: datetime) -> None:
    """Webhook OVERDUE (D0): marca atraso + estágio 1 (M8). Idempotente —
    não regride overdue_desde/estágio se já em atraso."""
    with get_session() as s:
        sub = s.execute(
            select(AssinaturaB2C).where(
                AssinaturaB2C.asaas_subscription_id == sub_id
            )
        ).scalar_one_or_none()
        if sub is None:
            return
        sub.status = "atrasada"
        if sub.overdue_desde is None:
            sub.overdue_desde = quando
        if sub.regua_estagio < 1:
            sub.regua_estagio = 1


def avancar_regua(sub_id: str, novo_estagio: int) -> None:
    """Só AVANÇA o estágio (nunca repete/regride) — idempotência do tick."""
    with get_session() as s:
        sub = s.execute(
            select(AssinaturaB2C).where(
                AssinaturaB2C.asaas_subscription_id == sub_id
            )
        ).scalar_one_or_none()
        if sub is None:
            return
        if novo_estagio > sub.regua_estagio:
            sub.regua_estagio = novo_estagio


def zerar_regua(sub_id: str) -> None:
    """Pagamento confirmado → zera régua e sai do atraso."""
    with get_session() as s:
        sub = s.execute(
            select(AssinaturaB2C).where(
                AssinaturaB2C.asaas_subscription_id == sub_id
            )
        ).scalar_one_or_none()
        if sub is None:
            return
        sub.overdue_desde = None
        sub.regua_estagio = 0


def listar_atrasadas_para_tick() -> List[Dict[str, Any]]:
    """Assinaturas em atraso ainda não no estágio final (3), pro
    daily-tick promover. Junta dados do aluno pra montar as mensagens."""
    with get_session() as s:
        rows = s.execute(
            select(
                AssinaturaB2C.asaas_subscription_id,
                AssinaturaB2C.overdue_desde,
                AssinaturaB2C.regua_estagio,
                AlunoB2C.id, AlunoB2C.telefone_e164, AlunoB2C.nome,
                AlunoB2C.parceiro_id,
            ).join(AlunoB2C, AlunoB2C.id == AssinaturaB2C.aluno_id).where(
                AssinaturaB2C.status == "atrasada",
                AssinaturaB2C.overdue_desde.isnot(None),
                AssinaturaB2C.regua_estagio < 3,
            )
        ).all()
    return [
        {
            "sub_id": r[0], "overdue_desde": r[1], "regua_estagio": r[2],
            "aluno_id": str(r[3]), "telefone": r[4], "nome": r[5],
            "parceiro_id": str(r[6]),
        }
        for r in rows
    ]


# ──────────────────────────────────────────────────────────────────────
# Eventos de billing (idempotência)
# ──────────────────────────────────────────────────────────────────────

def registrar_evento_billing(
    dedupe_key: str, tipo: str,
    *, aluno_id: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
) -> bool:
    """Grava o evento. Retorna True se é NOVO (deve processar), False se
    já existia (idempotência — não reprocessar). Corrida entre threads é
    resolvida pela UNIQUE em dedupe_key: o segundo INSERT falha e caímos
    no ramo 'já existia'."""
    from sqlalchemy.exc import IntegrityError
    with get_session() as s:
        existe = s.execute(
            select(EventoBilling.id).where(
                EventoBilling.dedupe_key == dedupe_key
            )
        ).scalar_one_or_none()
        if existe is not None:
            return False
        s.add(EventoBilling(
            dedupe_key=dedupe_key, tipo=tipo, aluno_id=aluno_id,
            payload=payload, processado=False,
        ))
        try:
            s.flush()
        except IntegrityError:
            s.rollback()
            return False
    return True


def contar_eventos_tipo(aluno_id: str, tipo: str) -> int:
    with get_session() as s:
        n = s.execute(
            select(func.count()).select_from(EventoBilling).where(
                EventoBilling.aluno_id == aluno_id,
                EventoBilling.tipo == tipo,
            )
        ).scalar_one()
        return int(n or 0)


def marcar_evento_processado(dedupe_key: str) -> None:
    with get_session() as s:
        ev = s.execute(
            select(EventoBilling).where(
                EventoBilling.dedupe_key == dedupe_key
            )
        ).scalar_one_or_none()
        if ev is not None:
            ev.processado = True


# ──────────────────────────────────────────────────────────────────────
# Métricas (F10)
# ──────────────────────────────────────────────────────────────────────

def contar_alunos_por_estado(parceiro_id: str) -> Dict[str, int]:
    with get_session() as s:
        rows = s.execute(
            select(AlunoB2C.estado, func.count()).where(
                AlunoB2C.parceiro_id == parceiro_id
            ).group_by(AlunoB2C.estado)
        ).all()
    return {estado: int(n) for estado, n in rows}


def metricas_envios(parceiro_id: str) -> Dict[str, Any]:
    """Total de correções, tempo médio e custo estimado do parceiro."""
    with get_session() as s:
        row = s.execute(
            select(
                func.count(),
                func.avg(EnvioB2C.tempo_processamento_ms),
                func.coalesce(func.sum(EnvioB2C.custo_estimado_centavos), 0),
            ).where(
                EnvioB2C.parceiro_id == parceiro_id,
                EnvioB2C.status == "corrigido",
            )
        ).one()
    total, tempo_medio, custo = row
    return {
        "total_correcoes": int(total or 0),
        "tempo_medio_ms": int(tempo_medio) if tempo_medio is not None else None,
        "custo_estimado_centavos": int(custo or 0),
    }


def contar_fotos_bloqueadas(parceiro_id: str) -> int:
    """Fotos de inadimplentes guardadas sem correção (§D10). Se o piloto
    mostrar volume, fila vira candidata de Fase 2."""
    with get_session() as s:
        n = s.execute(
            select(func.count()).select_from(EnvioB2C).where(
                EnvioB2C.parceiro_id == parceiro_id,
                EnvioB2C.status == "bloqueado",
            )
        ).scalar_one()
        return int(n or 0)


def contar_eventos_pendentes(parceiro_id: str) -> int:
    """Eventos de billing não processados (evento Asaas desconhecido, §D13)
    dos alunos do parceiro. Nada é descartado em silêncio."""
    with get_session() as s:
        n = s.execute(
            select(func.count()).select_from(EventoBilling)
            .join(AlunoB2C, AlunoB2C.id == EventoBilling.aluno_id)
            .where(
                AlunoB2C.parceiro_id == parceiro_id,
                EventoBilling.processado.is_(False),
            )
        ).scalar_one()
        return int(n or 0)


def registrar_notificacao_degradada(
    parceiro_id: str, template_key: str, *,
    aluno_id: Optional[str] = None, telefone: Optional[str] = None,
) -> None:
    """Registra mensagem de negócio que caiu no envio degradado (§D9) —
    fora da janela 24h e sem Content SID. Vira número visível."""
    with get_session() as s:
        s.add(NotificacaoDegradada(
            parceiro_id=parceiro_id, aluno_id=aluno_id,
            template_key=template_key, telefone_e164=telefone,
        ))


def contar_notificacoes_degradadas(parceiro_id: str) -> int:
    with get_session() as s:
        n = s.execute(
            select(func.count()).select_from(NotificacaoDegradada).where(
                NotificacaoDegradada.parceiro_id == parceiro_id,
            )
        ).scalar_one()
        return int(n or 0)


def correcoes_por_assinante_ativo(parceiro_id: str) -> List[int]:
    """Nº de correções por assinante ativo — base pro P50/P95 (§D11)."""
    ativos = ("ativo", "aguardando_cancelamento")
    with get_session() as s:
        rows = s.execute(
            select(EnvioB2C.aluno_id, func.count())
            .join(AlunoB2C, AlunoB2C.id == EnvioB2C.aluno_id)
            .where(
                AlunoB2C.parceiro_id == parceiro_id,
                AlunoB2C.estado.in_(ativos),
                EnvioB2C.status == "corrigido",
            ).group_by(EnvioB2C.aluno_id)
        ).all()
    return [int(n) for _, n in rows]
