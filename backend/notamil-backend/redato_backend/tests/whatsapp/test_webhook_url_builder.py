"""Testes do builder de URL pra validação de assinatura Twilio.

Bug que motivou (2026-04-29): Railway usa proxy reverso. Twilio assina
URL https://...railway.app/twilio/webhook, mas request.url chega como
http://...railway.app no app. HMAC compara strings literais e falha
com 403 "Assinatura Twilio inválida".

Fix: hierarquia de fontes pra URL de validação:
1. TWILIO_PUBLIC_URL env (override total)
2. X-Forwarded-Proto + X-Forwarded-Host (proxy padrão)
3. Heurística defensiva: força https em *.railway.app
4. Fallback: request.url
"""
from __future__ import annotations

from redato_backend.whatsapp.webhook import (
    _build_validation_url, _force_https_for_known_proxies,
)


# ──────────────────────────────────────────────────────────────────────
# (1) TWILIO_PUBLIC_URL override
# ──────────────────────────────────────────────────────────────────────

def test_public_url_env_override_substitui_scheme_e_host():
    out = _build_validation_url(
        request_url="http://internal.railway:8080/twilio/webhook?x=1",
        headers={},
        public_url_env="https://meu-bot.example.com",
    )
    assert out == "https://meu-bot.example.com/twilio/webhook?x=1"


def test_public_url_env_strip_trailing_slash():
    out = _build_validation_url(
        request_url="http://x:80/twilio/webhook",
        headers={},
        public_url_env="https://foo.bar/",
    )
    assert out == "https://foo.bar/twilio/webhook"


def test_public_url_env_vazio_e_ignorado():
    out = _build_validation_url(
        request_url="https://foo.railway.app/x",
        headers={},
        public_url_env="",
    )
    assert out == "https://foo.railway.app/x"


# ──────────────────────────────────────────────────────────────────────
# (2) X-Forwarded-Proto + X-Forwarded-Host (proxy padrão)
# ──────────────────────────────────────────────────────────────────────

def test_forwarded_proto_e_host_reconstroem_url():
    out = _build_validation_url(
        request_url="http://10.0.0.1:8080/twilio/webhook",
        headers={
            "x-forwarded-proto": "https",
            "x-forwarded-host": "backend-production.up.railway.app",
        },
        public_url_env="",
    )
    assert out == "https://backend-production.up.railway.app/twilio/webhook"


def test_forwarded_proto_so_preserva_host_do_request():
    out = _build_validation_url(
        request_url="http://backend.railway.app/twilio/webhook?a=b",
        headers={"x-forwarded-proto": "https"},
        public_url_env="",
    )
    assert out == "https://backend.railway.app/twilio/webhook?a=b"


def test_headers_sao_case_insensitive():
    out = _build_validation_url(
        request_url="http://x/twilio/webhook",
        headers={
            "X-Forwarded-Proto": "https",
            "X-Forwarded-Host": "host.example.com",
        },
        public_url_env="",
    )
    assert out == "https://host.example.com/twilio/webhook"


def test_forwarded_proto_lista_pega_primeiro():
    """Quando vários proxies em cadeia, o header pode vir como
    'https, http, http' — pegamos só o primeiro (cliente → 1º proxy)."""
    out = _build_validation_url(
        request_url="http://x/y",
        headers={"x-forwarded-proto": "https, http"},
        public_url_env="",
    )
    assert out.startswith("https://")


# ──────────────────────────────────────────────────────────────────────
# (3) Heurística railway.app (sem env nem header)
# ──────────────────────────────────────────────────────────────────────

def test_railway_app_force_https_sem_header():
    """Caso real do bug: Railway às vezes não envia X-Forwarded-Proto.
    Heurística defensiva força https quando host termina em
    .railway.app."""
    out = _build_validation_url(
        request_url="http://backend-production-3bd7.up.railway.app/twilio/webhook",
        headers={},
        public_url_env="",
    )
    assert out == "https://backend-production-3bd7.up.railway.app/twilio/webhook"


def test_railway_app_https_idempotente():
    """Quando já vem https, força_https não muda nada."""
    out = _build_validation_url(
        request_url="https://backend-production-3bd7.up.railway.app/x",
        headers={},
        public_url_env="",
    )
    assert out == "https://backend-production-3bd7.up.railway.app/x"


def test_force_https_helper_pula_hosts_desconhecidos():
    """Não força https em hosts arbitrários — só pra proxies conhecidos."""
    assert _force_https_for_known_proxies("http://localhost:8000/x") == \
        "http://localhost:8000/x"
    assert _force_https_for_known_proxies("http://foo.example.com/y") == \
        "http://foo.example.com/y"


def test_force_https_helper_cobre_subdominio_railway():
    assert _force_https_for_known_proxies("http://app.railway.app/x") == \
        "https://app.railway.app/x"
    assert _force_https_for_known_proxies("http://x.up.railway.app/y") == \
        "https://x.up.railway.app/y"


# ──────────────────────────────────────────────────────────────────────
# (4) Fallback puro
# ──────────────────────────────────────────────────────────────────────

def test_fallback_request_url_sem_proxy_sem_env():
    out = _build_validation_url(
        request_url="https://api.local/twilio/webhook?token=x",
        headers={},
        public_url_env="",
    )
    # Não é Railway → não muda
    assert out == "https://api.local/twilio/webhook?token=x"


# ──────────────────────────────────────────────────────────────────────
# Hierarquia: env > headers > heurística
# ──────────────────────────────────────────────────────────────────────

def test_env_vence_headers():
    """Se TWILIO_PUBLIC_URL setado, ignora X-Forwarded-* mesmo se vierem."""
    out = _build_validation_url(
        request_url="http://internal/twilio/webhook",
        headers={
            "x-forwarded-proto": "http",
            "x-forwarded-host": "wrong.example.com",
        },
        public_url_env="https://correct.example.com",
    )
    assert out == "https://correct.example.com/twilio/webhook"


def test_headers_vencem_heuristica_railway():
    """Se proxy manda X-Forwarded-Host com host customizado, usa ele
    em vez da heurística do railway.app do request.url."""
    out = _build_validation_url(
        request_url="http://internal.railway.app/twilio/webhook",
        headers={
            "x-forwarded-proto": "https",
            "x-forwarded-host": "custom-domain.com",
        },
        public_url_env="",
    )
    assert out == "https://custom-domain.com/twilio/webhook"
