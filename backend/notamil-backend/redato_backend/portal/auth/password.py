"""Hashing bcrypt + validação de senha (M3).

Usa biblioteca `bcrypt` direto (sem passlib). Cost factor 12 (default
do bcrypt — bom equilíbrio em 2026 entre segurança e latência).

Validação de senha: minimal e pragmática — UX > segurança teatral.
- Mínimo 8 chars
- Pelo menos 1 letra E 1 número
- Sem regras de "caractere especial obrigatório", "senha deve conter
  emoji em quarta-feira", etc.
"""
from __future__ import annotations

import re
from typing import Optional

import bcrypt


_MIN_LEN = 8
_HAS_LETTER = re.compile(r"[A-Za-zÀ-ÿ]")
_HAS_DIGIT = re.compile(r"\d")


def hash_senha(senha: str) -> str:
    """bcrypt hash. Retorna utf-8 string (cabe em VARCHAR(255))."""
    return bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_senha(senha: str, senha_hash: str) -> bool:
    """Verifica plaintext contra hash. Retorna False em qualquer erro
    (hash malformado, senha vazia, etc.) — evita exception leak."""
    if not senha or not senha_hash:
        return False
    try:
        return bcrypt.checkpw(senha.encode("utf-8"), senha_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def validate_senha(senha: str) -> Optional[str]:
    """Valida estrutura da senha. Retorna None se OK, ou string com
    motivo da rejeição."""
    if not senha:
        return "senha vazia"
    if len(senha) < _MIN_LEN:
        return f"senha precisa ter pelo menos {_MIN_LEN} caracteres"
    if not _HAS_LETTER.search(senha):
        return "senha precisa ter pelo menos 1 letra"
    if not _HAS_DIGIT.search(senha):
        return "senha precisa ter pelo menos 1 número"
    return None
