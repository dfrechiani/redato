"""Configuração do modo B2C — lida de env, sem nada hardcoded.

Nenhum termo comercial (preço/percentual) vive aqui: isso é por
parceiro em `parceiros_b2c`. Aqui ficam só os toggles de operação.

Envs (SPEC_B2C_REDATO.md §5):
- REDATO_B2C_ENABLED   : liga/desliga o modo inteiro (default 0/off).
- B2C_FAIR_USE_DIA     : correções/dia por aluno assinante (default 10).
- B2C_FREE_CORRECTIONS : degustações grátis antes do paywall (default 1).
- B2C_EXIGE_CPF        : pede CPF no chat antes do checkout (default 0).
- B2C_NUMERO_WHATSAPP  : número Twilio compartilhado (deep link).
- B2C_POLITICA_URL     : link da política de privacidade (LGPD).
"""
from __future__ import annotations

import os


def _flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on", "sim")


def _int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def b2c_enabled() -> bool:
    """Master switch. Desligada → o desvio B2C nem é consultado no bot."""
    return _flag("REDATO_B2C_ENABLED", default=False)


def fair_use_dia() -> int:
    return _int("B2C_FAIR_USE_DIA", 10)


def free_corrections() -> int:
    return _int("B2C_FREE_CORRECTIONS", 1)


def exige_cpf() -> bool:
    return _flag("B2C_EXIGE_CPF", default=False)


def numero_whatsapp() -> str:
    return os.getenv("B2C_NUMERO_WHATSAPP", "").strip()


def politica_url() -> str:
    return os.getenv(
        "B2C_POLITICA_URL",
        "https://redato.com.br/privacidade",
    ).strip()
