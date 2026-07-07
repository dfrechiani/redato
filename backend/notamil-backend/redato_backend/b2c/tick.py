"""Daily-tick da régua de inadimplência (ADENDO §D8).

O webhook OVERDUE só cobre a M8 (D0). A escalada M9 (D+3) e o bloqueio
(D+5) precisam de um job diário — o Railway chama
`POST /internal/b2c/daily-tick` (cron 10h BRT, configurado no Railway,
não no código). Protegido por token próprio (env `B2C_TICK_TOKEN`).

Idempotente: a promoção usa `assinaturas_b2c.regua_estagio` e só AVANÇA
o estágio (nunca repete). Rodar o tick 2× no mesmo dia não duplica M9
nem re-bloqueia.

A lógica vive em `rodar_tick` (pura o suficiente pra teste — `repo`,
`notificar` e `agora` injetáveis).
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from fastapi import APIRouter, Header, HTTPException

from redato_backend.b2c import config, notify, repo
from redato_backend.b2c import messages as M


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/internal/b2c", tags=["internal-b2c"])


def _link_fatura(sub_id: Optional[str]) -> str:
    return f"https://sandbox.asaas.com/i/{sub_id}" if sub_id else "https://wa.me/"


def _notificar_twilio(phone: str, textos: List[str]) -> None:
    try:
        from redato_backend.whatsapp import twilio_provider as TW
        TW.send_replies(phone, textos)
    except Exception:  # noqa: BLE001
        logger.exception("B2C tick: falha enviando notificação a %s", phone)


def rodar_tick(
    *,
    agora: Optional[datetime] = None,
    notificar: Optional[Callable[[str, List[str]], None]] = None,
) -> List[Dict[str, Any]]:
    """Promove a régua das assinaturas em atraso. Retorna o que fez."""
    agora = agora or datetime.now(timezone.utc)
    resultados: List[Dict[str, Any]] = []

    for a in repo.listar_atrasadas_para_tick():
        overdue_desde = a["overdue_desde"]
        if overdue_desde is None:
            continue
        dias = (agora - overdue_desde).days
        estagio = a["regua_estagio"]
        parceiro = repo.get_parceiro_por_id(a["parceiro_id"])
        branding = parceiro.branding if parceiro else None
        nome = (a["nome"] or "").split(" ")[0] or "aluno(a)"
        link = _link_fatura(a["sub_id"])

        if dias >= 5 and estagio < 3:
            # D+5 → bloqueia (recebe foto, não corrige — M10 sai na foto).
            repo.avancar_regua(a["sub_id"], 3)
            repo.atualizar_aluno(a["telefone"], estado="inadimplente")
            resultados.append({"sub_id": a["sub_id"], "acao": "bloqueado"})
        elif dias >= 3 and estagio < 2:
            # D+3 → M9 (respeitando a janela 24h — §D9). A régua AVANÇA
            # mesmo se o envio degradar (ela reflete o pagamento, não a
            # entrega da mensagem).
            repo.avancar_regua(a["sub_id"], 2)
            aluno = repo.get_aluno_por_id(a["aluno_id"])
            ultima_inbound = aluno.ultima_inbound_at if aluno else None
            path = notify.notificar_negocio(
                a["telefone"],
                M.assinar(M.M9_OVERDUE_D3.format(nome=nome, link_fatura=link),
                          branding),
                template_key="M9", template_vars=[nome, "", link],
                ultima_inbound_at=ultima_inbound, override=notificar,
            )
            degradado = path == "freeform_fallback"
            if degradado:
                repo.registrar_notificacao_degradada(
                    a["parceiro_id"], "M9", aluno_id=a["aluno_id"],
                    telefone=a["telefone"])
            resultados.append({"sub_id": a["sub_id"], "acao": "M9",
                               "degradado": degradado})

    return resultados


@router.post("/daily-tick")
def daily_tick(
    b2c_tick_token: Optional[str] = Header(default=None, alias="x-b2c-tick-token"),
) -> Dict[str, Any]:
    if not config.b2c_enabled():
        return {"status": "disabled"}
    expected = os.getenv("B2C_TICK_TOKEN", "").strip()
    if not expected or b2c_tick_token != expected:
        raise HTTPException(status_code=401, detail="Invalid tick token")
    resultados = rodar_tick()
    degradados = [r for r in resultados if r.get("degradado")]
    return {
        "status": "ok",
        "promovidos": len(resultados),
        "degradados": len(degradados),
        "detalhe": resultados,
    }
