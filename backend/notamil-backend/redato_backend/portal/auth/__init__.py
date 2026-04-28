"""Autenticação do portal — M3.

Submódulos:
- `password`: bcrypt hashing + validação de senha
- `jwt_service`: encode/decode JWT com JTI, audience, issuer
- `middleware`: dependencies FastAPI (get_current_user, require_*)
- `permissions`: funções puras de autorização (can_view_*, etc.)
- `cleanup`: limpeza periódica de tokens expirados
- `api`: endpoints HTTP /auth/*
"""
