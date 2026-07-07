"""Webhook do Asaas — POST /billing/asaas/webhook (SPEC_B2C_REDATO.md §3-4).

Trata os eventos de cobrança e move a FSM do aluno:
- PAYMENT_CONFIRMED / PAYMENT_RECEIVED → assinatura ativa, aluno ativo,
  dispara M5.
- PAYMENT_OVERDUE → régua M8 (D0) / M9 / M10; na 3ª cobrança o aluno
  vira inadimplente (recebe foto, não corrige).
- SUBSCRIPTION_DELETED / PAYMENT_DELETED → assinatura cancelada.

Proteções:
- Token no header `asaas-access-token` (env ASAAS_WEBHOOK_TOKEN). Sem
  token configurado (dev), a checagem é pulada.
- Idempotência via `eventos_billing.dedupe_key` (id do evento Asaas):
  evento repetido não reprocessa.

A lógica de negócio vive em `handle_asaas_event` (pura o suficiente pra
teste — repo e `notificar` são injetáveis/monkeypatcháveis). O endpoint
só faz auth + idempotência + delega.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Callable, Dict, List, Optional

from fastapi import APIRouter, Header, HTTPException, Request, Response

from redato_backend.b2c import config, repo
from redato_backend.b2c import messages as M


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/billing", tags=["billing"])


# ──────────────────────────────────────────────────────────────────────
# Extração do payload
# ──────────────────────────────────────────────────────────────────────

def _subscription_id(payload: Dict[str, Any]) -> Optional[str]:
    pay = payload.get("payment") or {}
    if pay.get("subscription"):
        return pay["subscription"]
    sub = payload.get("subscription") or {}
    if isinstance(sub, dict) and sub.get("id"):
        return sub["id"]
    if isinstance(sub, str):
        return sub
    return None


def _invoice_url(payload: Dict[str, Any], sub_id: Optional[str]) -> str:
    pay = payload.get("payment") or {}
    if pay.get("invoiceUrl"):
        return pay["invoiceUrl"]
    if sub_id:
        return f"https://sandbox.asaas.com/i/{sub_id}"
    return "https://wa.me/"


def _dedupe_key(payload: Dict[str, Any]) -> str:
    if payload.get("id"):
        return str(payload["id"])
    pay = payload.get("payment") or {}
    return f"{payload.get('event','?')}:{pay.get('id') or _subscription_id(payload) or 'na'}"


def _notificar_twilio(phone: str, textos: List[str]) -> None:
    """Envia mensagens via Twilio REST (mesma via do webhook do bot).
    Guardado: falha de envio não deve derrubar o processamento do
    webhook (o estado no banco já mudou)."""
    try:
        from redato_backend.whatsapp import twilio_provider as TW
        TW.send_replies(phone, textos)
    except Exception:  # noqa: BLE001
        logger.exception("B2C billing: falha enviando notificação a %s", phone)


# ──────────────────────────────────────────────────────────────────────
# Lógica de negócio (testável)
# ──────────────────────────────────────────────────────────────────────

_PAGO = {"PAYMENT_CONFIRMED", "PAYMENT_RECEIVED", "PAYMENT_RECEIVED_IN_CASH"}
_OVERDUE = {"PAYMENT_OVERDUE"}
_CANCELADO = {"SUBSCRIPTION_DELETED", "PAYMENT_DELETED", "SUBSCRIPTION_INACTIVATED"}


def handle_asaas_event(
    payload: Dict[str, Any],
    *,
    notificar: Callable[[str, List[str]], None] = _notificar_twilio,
) -> Dict[str, Any]:
    """Aplica um evento já validado + de-duplicado. Retorna um resumo do
    que aconteceu (útil pro endpoint e pros testes)."""
    event = payload.get("event") or ""
    sub_id = _subscription_id(payload)
    if not sub_id:
        return {"handled": False, "reason": "sem_subscription_id", "event": event}

    assinatura = repo.get_assinatura_por_subscription(sub_id)
    if assinatura is None:
        return {"handled": False, "reason": "assinatura_desconhecida", "event": event}

    aluno = repo.get_aluno_por_id(assinatura.aluno_id)
    if aluno is None:
        return {"handled": False, "reason": "aluno_desconhecido", "event": event}

    parceiro = repo.get_parceiro_por_id(aluno.parceiro_id)
    branding = parceiro.branding if parceiro else None
    nome = (aluno.nome or "").split(" ")[0] or "aluno(a)"
    nome_publico = parceiro.nome_publico if parceiro else "Redato"
    link = _invoice_url(payload, sub_id)

    if event in _PAGO:
        repo.atualizar_status_assinatura(sub_id, "ativa")
        repo.atualizar_aluno(aluno.telefone_e164, estado="ativo")
        notificar(aluno.telefone_e164, [M.assinar(M.M5_LIBERADO.format(nome=nome), branding)])
        return {"handled": True, "acao": "ativado", "estado": "ativo"}

    if event in _OVERDUE:
        repo.atualizar_status_assinatura(sub_id, "atrasada")
        seq = repo.contar_eventos_tipo(aluno.id, "PAYMENT_OVERDUE")
        if seq <= 1:
            texto = M.M8_OVERDUE_D0.format(nome=nome, nome_publico=nome_publico, link_fatura=link)
            estado = None
        elif seq == 2:
            texto = M.M9_OVERDUE_D3.format(nome=nome, link_fatura=link)
            estado = None
        else:
            texto = M.M10_BLOQUEADO.format(link_fatura=link)
            estado = "inadimplente"
        if estado:
            repo.atualizar_aluno(aluno.telefone_e164, estado=estado)
        notificar(aluno.telefone_e164, [M.assinar(texto, branding)])
        return {"handled": True, "acao": "overdue", "seq": seq, "estado": estado or aluno.estado}

    if event in _CANCELADO:
        repo.atualizar_status_assinatura(sub_id, "cancelada")
        repo.atualizar_aluno(aluno.telefone_e164, estado="cancelado")
        return {"handled": True, "acao": "cancelado", "estado": "cancelado"}

    return {"handled": False, "reason": "evento_ignorado", "event": event}


def processar_webhook(
    payload: Dict[str, Any],
    *,
    notificar: Callable[[str, List[str]], None] = _notificar_twilio,
) -> Dict[str, Any]:
    """Idempotência + processamento. Reusado pelo endpoint e pelos testes.

    Registra o evento pela `dedupe_key`; se já existia, é no-op (não
    reprocessa). Caso novo, delega pra `handle_asaas_event` e marca
    processado."""
    event = payload.get("event") or ""
    dedupe = _dedupe_key(payload)
    sub_id = _subscription_id(payload)

    aluno_id = None
    if sub_id:
        assinatura = repo.get_assinatura_por_subscription(sub_id)
        aluno_id = assinatura.aluno_id if assinatura else None

    novo = repo.registrar_evento_billing(
        dedupe, event, aluno_id=aluno_id, payload=payload,
    )
    if not novo:
        return {"status": "duplicate", "dedupe_key": dedupe}

    resultado = handle_asaas_event(payload, notificar=notificar)
    repo.marcar_evento_processado(dedupe)
    return {"status": "ok", "dedupe_key": dedupe, "resultado": resultado}


# ──────────────────────────────────────────────────────────────────────
# Endpoint
# ──────────────────────────────────────────────────────────────────────

@router.post("/asaas/webhook")
async def asaas_webhook(
    request: Request,
    asaas_access_token: Optional[str] = Header(default=None,
                                               alias="asaas-access-token"),
) -> Dict[str, Any]:
    if not config.b2c_enabled():
        # Com o modo desligado, o webhook não faz nada (mas responde 200
        # pra não gerar retry infinito no gateway).
        return {"status": "disabled"}

    expected = os.getenv("ASAAS_WEBHOOK_TOKEN", "").strip()
    if expected and asaas_access_token != expected:
        raise HTTPException(status_code=401, detail="Invalid webhook token")

    payload = await request.json()
    return processar_webhook(payload)


@router.get("/asaas/health")
def asaas_health() -> Dict[str, Any]:
    return {
        "status": "ok",
        "b2c_enabled": config.b2c_enabled(),
        "webhook_token_set": bool(os.getenv("ASAAS_WEBHOOK_TOKEN")),
        "asaas_key_set": bool(os.getenv("ASAAS_API_KEY")),
    }
