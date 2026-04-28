"""Simulador de provedor WhatsApp (sem rede). Útil pra dev/teste local
antes de integrar Twilio ou Meta Cloud API.

Modela 2 lados:
- inbound: aluno manda mensagem → bot.handle_inbound
- outbound: bot manda resposta → captura em log local

Em produção, isso é substituído por webhook receiver (Twilio/Meta) +
client de envio. Spec do contrato: shape de InboundMessage e
OutboundMessage do `bot.py`.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import List, Optional

from redato_backend.whatsapp.bot import (
    InboundMessage, OutboundMessage, handle_inbound,
)


class WhatsAppSimulator:
    """Simulador sequencial — chamadas síncronas, log em memória."""

    def __init__(self) -> None:
        self.outbox: List[dict] = []  # [{phone, text, ts}]

    def send_from_aluno(
        self, phone: str, text: Optional[str] = None,
        image_path: Optional[str | Path] = None,
    ) -> List[OutboundMessage]:
        msg = InboundMessage(
            phone=phone,
            text=text,
            image_path=str(image_path) if image_path else None,
        )
        responses = handle_inbound(msg)
        for r in responses:
            self.outbox.append({
                "phone": phone,
                "text": r.text,
                "ts": datetime.utcnow().isoformat(),
            })
        return responses

    def last_replies_to(self, phone: str, n: int = 5) -> List[str]:
        msgs = [m["text"] for m in self.outbox if m["phone"] == phone]
        return msgs[-n:]

    def clear(self) -> None:
        self.outbox.clear()
