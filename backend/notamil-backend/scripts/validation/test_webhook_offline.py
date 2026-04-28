#!/usr/bin/env python3
"""Smoke offline do webhook Twilio — injeta payload fake e verifica que
o pipeline roteia certo, sem chamar Twilio nem Anthropic.

Cobre:
- parse_inbound: form Twilio → InboundMessage com phone limpo, text, image_path
- webhook: signature validation desligada, dispatch pra background thread
- bot.handle_inbound: cadastro inicial (NEW → AWAITING_NOME)

NÃO cobre (pra isso, usar caminho2_setup_passo_a_passo.md + celular real):
- OCR real
- grade_mission real
- envio Twilio real
- assinatura HMAC real

Uso: python scripts/validation/test_webhook_offline.py
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from unittest.mock import patch

BACKEND = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND))

# Isola DB
test_db = BACKEND / "data" / "whatsapp" / "redato_webhook_test.db"
if test_db.exists():
    test_db.unlink()
os.environ["REDATO_WHATSAPP_DB"] = str(test_db)

# Fake credenciais Twilio (signature OFF, send mockado)
os.environ.setdefault("TWILIO_ACCOUNT_SID", "ACfakefakefakefakefakefakefakefake")
os.environ.setdefault("TWILIO_AUTH_TOKEN", "faketoken")
os.environ.setdefault("TWILIO_WHATSAPP_NUMBER", "whatsapp:+14155238886")
os.environ["TWILIO_VALIDATE_SIGNATURE"] = "0"
os.environ.setdefault("REDATO_DEV_OFFLINE", "1")
os.environ.setdefault("REDATO_DEV_PERSIST", "0")

from redato_backend.dev_offline import apply_patches  # noqa: E402
apply_patches()
# apply_patches chama load_dotenv(override=True) que sobrescreve nosso
# TWILIO_VALIDATE_SIGNATURE=0. Re-aplicar depois.
os.environ["TWILIO_VALIDATE_SIGNATURE"] = "0"

from fastapi.testclient import TestClient  # noqa: E402
from redato_backend.whatsapp import twilio_provider as TW  # noqa: E402
from redato_backend.whatsapp import persistence as P  # noqa: E402
from redato_backend.whatsapp.app import app  # noqa: E402


# ──────────────────────────────────────────────────────────────────────
# Test cases
# ──────────────────────────────────────────────────────────────────────

PHONE = "+5511555000999"


def test_parse_inbound_text_only():
    form = {
        "From": f"whatsapp:{PHONE}",
        "Body": "RJ1OF10MF",
        "NumMedia": "0",
    }
    msg = TW.parse_inbound(form)
    assert msg.phone == PHONE, f"phone esperado={PHONE}, got={msg.phone}"
    assert msg.text == "RJ1OF10MF"
    assert msg.image_path is None
    return "parse_inbound text-only OK"


def test_parse_inbound_with_image():
    """Mocka requests.get pra evitar download real de Twilio CDN."""
    form = {
        "From": f"whatsapp:{PHONE}",
        "Body": "",
        "NumMedia": "1",
        "MediaUrl0": "https://api.twilio.com/fake/media/MM123",
        "MediaContentType0": "image/jpeg",
    }

    # Cria PNG minimalista 1x1 pra simular response Twilio
    from PIL import Image
    import io as _io
    img = Image.new("RGB", (10, 10), "white")
    buf = _io.BytesIO()
    img.save(buf, "JPEG")
    fake_jpeg = buf.getvalue()

    class FakeResp:
        content = fake_jpeg
        def raise_for_status(self): pass

    with patch.object(TW.requests, "get", return_value=FakeResp()):
        msg = TW.parse_inbound(form)

    assert msg.phone == PHONE
    assert msg.image_path is not None
    p = Path(msg.image_path)
    assert p.exists() and p.stat().st_size > 0
    return f"parse_inbound with-image OK ({p.stat().st_size} bytes)"


def test_webhook_routing_first_message():
    """Webhook recebe 'oi' do user novo, dispara cadastro. Filtra captured
    pelo phone específico — outras threads (de tests anteriores que ainda
    rodam) podem populá-lo concorrentemente."""
    routing_phone = "+5511555000777"  # único pra este teste
    captured: list = []

    def fake_send_replies(phone: str, replies):
        captured.append((phone, list(replies)))
        return ["SM_FAKE"] * len(replies)

    original = TW.send_replies
    TW.send_replies = fake_send_replies
    try:
        client = TestClient(app)
        resp = client.post(
            "/twilio/webhook",
            data={
                "From": f"whatsapp:{routing_phone}",
                "Body": "oi",
                "NumMedia": "0",
            },
        )
        assert resp.status_code == 200
        deadline = time.time() + 5
        while time.time() < deadline and not any(
            c[0] == routing_phone for c in captured
        ):
            time.sleep(0.1)
    finally:
        TW.send_replies = original

    matching = [c for c in captured if c[0] == routing_phone]
    assert matching, f"send_replies não foi chamado p/ {routing_phone} em 5s. captured={captured!r}"
    phone, replies = matching[0]
    assert replies, f"replies vazias: {replies!r}"
    assert "Redato" in replies[0], f"reply sem 'Redato': {replies[0]!r}"
    aluno = P.get_aluno(routing_phone)
    # M4: NEW → AWAITING_CODIGO_TURMA (era AWAITING_NOME no fluxo legado).
    assert aluno and aluno["estado"] == "AWAITING_CODIGO_TURMA"
    return f"webhook routed first message → AWAITING_CODIGO_TURMA (reply: {len(replies[0])} chars)"


def test_webhook_health():
    client = TestClient(app)
    resp = client.get("/twilio/health")
    assert resp.status_code == 200
    j = resp.json()
    assert "env" in j
    assert j["env"]["TWILIO_ACCOUNT_SID"] is True
    return "health check OK"


def test_signature_validation_off():
    """Quando TWILIO_VALIDATE_SIGNATURE=0, webhook aceita sem header."""
    client = TestClient(app)
    resp = client.post(
        "/twilio/webhook",
        data={
            "From": f"whatsapp:{PHONE}_nosig",
            "Body": "test",
            "NumMedia": "0",
        },
    )
    assert resp.status_code == 200
    return "signature validation OFF aceita sem X-Twilio-Signature"


def test_signature_validation_on_rejects_missing():
    """Quando TWILIO_VALIDATE_SIGNATURE=1, sem header rejeita 403."""
    os.environ["TWILIO_VALIDATE_SIGNATURE"] = "1"
    try:
        client = TestClient(app)
        resp = client.post(
            "/twilio/webhook",
            data={
                "From": f"whatsapp:{PHONE}_sig",
                "Body": "test",
                "NumMedia": "0",
            },
        )
        assert resp.status_code == 403, f"esperado 403, got {resp.status_code}"
    finally:
        os.environ["TWILIO_VALIDATE_SIGNATURE"] = "0"
    return "signature validation ON rejeita sem header (403)"


# ──────────────────────────────────────────────────────────────────────
# Runner
# ──────────────────────────────────────────────────────────────────────

TESTS = [
    test_parse_inbound_text_only,
    test_parse_inbound_with_image,
    test_webhook_health,
    test_signature_validation_off,
    test_signature_validation_on_rejects_missing,
    test_webhook_routing_first_message,
]


def main():
    P.init_db()
    print(f"DB: {os.environ['REDATO_WHATSAPP_DB']}")
    print(f"\n{'='*70}")
    failures = []
    for fn in TESTS:
        name = fn.__name__
        try:
            result = fn()
            print(f"  ✓ {name}: {result}")
        except AssertionError as exc:
            print(f"  ✗ {name}: AssertionError: {exc}")
            failures.append((name, str(exc)))
        except Exception as exc:
            print(f"  ✗ {name}: {type(exc).__name__}: {exc}")
            failures.append((name, repr(exc)))

    print(f"\n{'='*70}")
    if failures:
        print(f"FALHA: {len(failures)}/{len(TESTS)}")
        sys.exit(1)
    else:
        print(f"OK: {len(TESTS)}/{len(TESTS)} testes passaram")


if __name__ == "__main__":
    main()
