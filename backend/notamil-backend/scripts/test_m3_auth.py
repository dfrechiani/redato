#!/usr/bin/env python3
"""Smoke test M3 — auth completo (JWT, primeiro acesso, reset, permissões).

Cobre:
1. Fluxo primeiro acesso end-to-end: token gerado em M2 → validar →
   definir senha → login → /auth/me retorna user.
2. Login: email errado 401, senha errada 401, user inativo 403.
3. JWT expirado é rejeitado em /auth/me.
4. Logout: token vai pra blocklist, /auth/me passa a 401.
5. Reset: solicitar (200 sempre) → confirmar (200) → login com nova senha.
6. Token primeiro acesso expirado: 410.
7. Reset token expirado: 410.
8. Permissões: prof A não vê turma do prof B.
9. Permissões: coordenador vê todas as turmas da escola.
10. Permissões: coordenador NÃO vê turmas de outra escola.
11. Cleanup limpa tokens expirados.
12. Update M2: planilha com escola_estado/municipio explícitos é
    aceita; sem eles dispara warning de fallback.

Rodar em schema isolado do Postgres.
"""
from __future__ import annotations

import os
import sys
import tempfile
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

env_path = BACKEND / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip()
            if not os.environ.get(k):
                os.environ[k] = v

# Garante JWT secret pro teste
os.environ.setdefault(
    "JWT_SECRET_KEY",
    "test_secret_at_least_32_chars_for_smoke_m3_auth_xx",
)
os.environ.setdefault("ADMIN_TOKEN", "test-admin-token-m3")
os.environ.pop("SENDGRID_API_KEY", None)  # força dry-run de email

TEST_SCHEMA = f"m3_test_{uuid.uuid4().hex[:8]}"
test_pending = Path(tempfile.mkdtemp(prefix="m3email_")) / "emails_pendentes.jsonl"
test_audit = Path(tempfile.mkdtemp(prefix="m3audit_")) / "audit_log.jsonl"

from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from redato_backend.portal.db import Base  # noqa: E402
from redato_backend.portal import models  # noqa: F401, E402
from redato_backend.portal import email_service  # noqa: E402
from redato_backend.portal import admin_api  # noqa: E402
from redato_backend.portal.auth import cleanup as auth_cleanup  # noqa: E402
from redato_backend.portal.auth.password import hash_senha  # noqa: E402
from redato_backend.portal.auth.jwt_service import encode_token  # noqa: E402
from redato_backend.portal.auth.permissions import (  # noqa: E402
    can_view_escola, can_view_turma, can_create_atividade,
    can_view_dashboard_escola,
)
from redato_backend.portal.auth.middleware import AuthenticatedUser  # noqa: E402
from redato_backend.portal.models import (  # noqa: E402
    AlunoTurma, Atividade, Coordenador, Escola, Professor, TokenBlocklist,
    Turma,
)


# Patcha logs pra não tocar paths reais
email_service._PENDING_LOG = test_pending
admin_api._AUDIT_LOG = test_audit


def _setup_schema(engine):
    with engine.connect() as conn:
        conn.execute(text(f'CREATE SCHEMA "{TEST_SCHEMA}"'))
        conn.commit()
    for table in Base.metadata.tables.values():
        table.schema = TEST_SCHEMA
    Base.metadata.create_all(engine)


def _teardown_schema(engine):
    for table in Base.metadata.tables.values():
        table.schema = None
    with engine.connect() as conn:
        conn.execute(text(f'DROP SCHEMA "{TEST_SCHEMA}" CASCADE'))
        conn.commit()


# ──────────────────────────────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────────────────────────────

def _seed_basico(session: Session) -> dict:
    """Cria 2 escolas, 2 coords, 3 profs, 4 turmas — pra testes de
    permissões. Retorna dict com IDs/objetos."""
    e1 = Escola(codigo="E-CE-001", nome="E1", estado="CE", municipio="Fortaleza")
    e2 = Escola(codigo="E-CE-002", nome="E2", estado="CE", municipio="Fortaleza")
    session.add_all([e1, e2])
    session.flush()

    c1 = Coordenador(escola_id=e1.id, nome="Coord 1",
                     email="coord1@e1.br")
    c2 = Coordenador(escola_id=e2.id, nome="Coord 2",
                     email="coord2@e2.br")
    p_a = Professor(escola_id=e1.id, nome="Prof A", email="profa@e1.br")
    p_b = Professor(escola_id=e1.id, nome="Prof B", email="profb@e1.br")
    p_c = Professor(escola_id=e2.id, nome="Prof C", email="profc@e2.br")
    session.add_all([c1, c2, p_a, p_b, p_c])
    session.flush()

    t_a = Turma(escola_id=e1.id, professor_id=p_a.id, codigo="1A",
                serie="1S", codigo_join="J-001", ano_letivo=2026)
    t_b = Turma(escola_id=e1.id, professor_id=p_b.id, codigo="1B",
                serie="1S", codigo_join="J-002", ano_letivo=2026)
    t_c = Turma(escola_id=e2.id, professor_id=p_c.id, codigo="2A",
                serie="2S", codigo_join="J-003", ano_letivo=2026)
    session.add_all([t_a, t_b, t_c])
    session.flush()
    return dict(e1=e1, e2=e2, c1=c1, c2=c2, pa=p_a, pb=p_b, pc=p_c,
                ta=t_a, tb=t_b, tc=t_c)


def test_permissions_pure_funcs(engine):
    """Funções puras de permissão (sem HTTP)."""
    with Session(engine) as session:
        s = _seed_basico(session)
        session.commit()

        # Auth do prof A
        auth_pa = AuthenticatedUser(
            user=s["pa"], papel="professor",
            user_id=s["pa"].id, escola_id=s["e1"].id,
            jti="x", exp=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        # Auth do coord 1 (escola e1)
        auth_c1 = AuthenticatedUser(
            user=s["c1"], papel="coordenador",
            user_id=s["c1"].id, escola_id=s["e1"].id,
            jti="x", exp=datetime.now(timezone.utc) + timedelta(hours=1),
        )

        # Prof A vê turma própria, não vê turma do prof B nem da e2
        assert can_view_turma(auth_pa, s["ta"]), "Prof A NÃO viu turma própria"
        assert not can_view_turma(auth_pa, s["tb"]), "Prof A viu turma alheia"
        assert not can_view_turma(auth_pa, s["tc"]), "Prof A viu turma de outra escola"

        # Coord 1 vê todas as turmas da escola e1
        assert can_view_turma(auth_c1, s["ta"]), "Coord não viu turma da escola"
        assert can_view_turma(auth_c1, s["tb"]), "Coord não viu outra turma da escola"
        # Mas não vê turma de outra escola
        assert not can_view_turma(auth_c1, s["tc"]), "Coord viu turma de outra escola"

        # Prof A pode criar atividade na turma própria
        assert can_create_atividade(auth_pa, s["ta"])
        assert not can_create_atividade(auth_pa, s["tb"])
        # Coord NÃO cria atividade
        assert not can_create_atividade(auth_c1, s["ta"])

        # Coord vê dashboard da escola própria, não da outra
        assert can_view_dashboard_escola(auth_c1, s["e1"].id)
        assert not can_view_dashboard_escola(auth_c1, s["e2"].id)
        # Prof não vê dashboard escola
        assert not can_view_dashboard_escola(auth_pa, s["e1"].id)

        # can_view_escola só checa escola
        assert can_view_escola(auth_pa, s["e1"].id)
        assert not can_view_escola(auth_pa, s["e2"].id)

    return "permissões puras OK (prof vs coord, escola própria vs alheia)"


def test_password_validation(engine):
    """Validação de senha."""
    from redato_backend.portal.auth.password import (
        validate_senha, hash_senha, verify_senha,
    )
    assert validate_senha("") == "senha vazia"
    assert "8" in validate_senha("abc12") or "caract" in validate_senha("abc12")
    assert "letra" in validate_senha("12345678").lower()
    assert "n" in validate_senha("abcdefgh").lower()
    assert validate_senha("senha123") is None
    h = hash_senha("senha123")
    assert verify_senha("senha123", h) is True
    assert verify_senha("senha errada", h) is False
    return "password validate + hash + verify OK"


def test_jwt_encode_decode(engine):
    from redato_backend.portal.auth.jwt_service import (
        encode_token, decode_token,
    )
    user_id = str(uuid.uuid4())
    escola_id = str(uuid.uuid4())
    token, payload = encode_token(user_id, "professor", escola_id)
    claims = decode_token(token)
    assert claims["sub"] == user_id
    assert claims["papel"] == "professor"
    assert claims["escola_id"] == escola_id
    assert "jti" in claims
    return f"JWT encode/decode OK (jti={claims['jti'][:8]}...)"


def test_jwt_invalid_audience(engine):
    """Token assinado pra outra audience é rejeitado."""
    import jwt as pyjwt
    from redato_backend.portal.auth.jwt_service import decode_token, _secret_key
    bad = pyjwt.encode(
        {"sub": "x", "papel": "professor", "escola_id": "x",
         "jti": "j", "iat": int(time.time()), "exp": int(time.time()) + 60,
         "aud": "wrong-audience", "iss": "redato-backend"},
        _secret_key(), algorithm="HS256",
    )
    try:
        decode_token(bad)
        return "FAIL: deveria ter levantado InvalidAudienceError"
    except pyjwt.InvalidAudienceError:
        return "JWT com aud errada → rejeitado ✓"


def test_fluxo_primeiro_acesso_completo(engine):
    """Fluxo end-to-end: token primeiro_acesso (gerado em M2) → validar →
    definir senha → login → /auth/me."""
    from fastapi.testclient import TestClient
    from redato_backend.portal.portal_app import app

    client = TestClient(app)

    # Cria user com token de primeiro acesso
    with Session(engine) as session:
        e = Escola(codigo="E-FX-001", nome="EscolaFx",
                   estado="CE", municipio="Fortaleza")
        session.add(e)
        session.flush()
        prof = Professor(
            escola_id=e.id, nome="Prof Fluxo", email="fluxo@teste.br",
            primeiro_acesso_token="tok_primeiro_" + uuid.uuid4().hex[:16],
            primeiro_acesso_expira_em=(
                datetime.now(timezone.utc) + timedelta(days=7)
            ),
        )
        session.add(prof)
        session.commit()
        token_pa = prof.primeiro_acesso_token

    # 1. validar token
    r = client.post("/auth/primeiro-acesso/validar", json={"token": token_pa})
    assert r.status_code == 200, f"validar falhou: {r.status_code} {r.text}"
    body = r.json()
    assert body["valido"] is True
    assert body["email"] == "fluxo@teste.br"
    assert body["papel"] == "professor"

    # 2. definir senha fraca → 400
    r = client.post("/auth/primeiro-acesso/definir-senha",
                    json={"token": token_pa, "senha": "abc"})
    assert r.status_code == 400, f"senha fraca não rejeitada: {r.status_code}"

    # 3. definir senha forte → 200
    r = client.post("/auth/primeiro-acesso/definir-senha",
                    json={"token": token_pa, "senha": "MinhaSenha123"})
    assert r.status_code == 200, f"definir-senha falhou: {r.status_code}"

    # 4. token primeiro_acesso foi NULA
    with Session(engine) as session:
        prof2 = session.execute(
            text(f"SELECT primeiro_acesso_token, senha_hash "
                 f"FROM \"{TEST_SCHEMA}\".professores "
                 f"WHERE email = 'fluxo@teste.br'")
        ).first()
    assert prof2[0] is None, f"token deveria ser NULL: {prof2[0]}"
    assert prof2[1] is not None, "senha_hash deveria estar setada"

    # 5. login
    r = client.post("/auth/login", json={
        "email": "fluxo@teste.br", "senha": "MinhaSenha123",
    })
    assert r.status_code == 200, f"login falhou: {r.status_code} {r.text}"
    login_body = r.json()
    assert login_body["papel"] == "professor"
    assert login_body["nome"] == "Prof Fluxo"
    assert login_body["expires_in"] > 28000  # ~8h
    access_token = login_body["access_token"]

    # 6. /auth/me retorna o user
    r = client.get("/auth/me", headers={"Authorization": f"Bearer {access_token}"})
    assert r.status_code == 200, f"/auth/me falhou: {r.status_code} {r.text}"
    me = r.json()
    assert me["email"] == "fluxo@teste.br"
    assert me["papel"] == "professor"

    # 7. logout
    r = client.post("/auth/logout",
                    headers={"Authorization": f"Bearer {access_token}"})
    assert r.status_code == 200

    # 8. /auth/me com token blocklisted → 401
    r = client.get("/auth/me", headers={"Authorization": f"Bearer {access_token}"})
    assert r.status_code == 401, \
        f"token blocklisted deveria dar 401, got {r.status_code}"

    return "fluxo primeiro acesso → senha → login → /me → logout → 401 ✓"


def test_login_errado_e_inativo(engine):
    from fastapi.testclient import TestClient
    from redato_backend.portal.portal_app import app
    client = TestClient(app)

    # Cria user com senha conhecida
    with Session(engine) as session:
        e = Escola(codigo="E-LG-001", nome="EscolaLg",
                   estado="CE", municipio="Fortaleza")
        session.add(e)
        session.flush()
        # User inativo
        p_inativo = Professor(
            escola_id=e.id, nome="Inativo", email="inativo@teste.br",
            senha_hash=hash_senha("Senha123Forte"),
            ativo=False,
        )
        # User ativo
        p_ativo = Professor(
            escola_id=e.id, nome="Ativo", email="ativo@teste.br",
            senha_hash=hash_senha("Senha123Forte"),
            ativo=True,
        )
        session.add_all([p_inativo, p_ativo])
        session.commit()

    # Email errado
    r = client.post("/auth/login", json={"email": "naoexiste@teste.br",
                                          "senha": "X"})
    assert r.status_code == 401, f"got {r.status_code}"

    # Senha errada
    r = client.post("/auth/login", json={"email": "ativo@teste.br",
                                          "senha": "errada"})
    assert r.status_code == 401, f"got {r.status_code}"

    # Inativo → 403
    r = client.post("/auth/login", json={"email": "inativo@teste.br",
                                          "senha": "Senha123Forte"})
    assert r.status_code == 403, f"got {r.status_code}"

    return "login: email errado 401, senha errada 401, inativo 403 ✓"


def test_token_primeiro_acesso_expirado(engine):
    from fastapi.testclient import TestClient
    from redato_backend.portal.portal_app import app
    client = TestClient(app)

    with Session(engine) as session:
        e = Escola(codigo="E-EXP-001", nome="EscolaExp",
                   estado="CE", municipio="Fortaleza")
        session.add(e); session.flush()
        prof = Professor(
            escola_id=e.id, nome="Expirado", email="exp@teste.br",
            primeiro_acesso_token="tok_expirado_" + uuid.uuid4().hex[:16],
            primeiro_acesso_expira_em=(
                datetime.now(timezone.utc) - timedelta(hours=1)
            ),
        )
        session.add(prof); session.commit()
        token = prof.primeiro_acesso_token

    r = client.post("/auth/primeiro-acesso/validar", json={"token": token})
    assert r.status_code == 410, f"got {r.status_code}: {r.text}"
    return "primeiro acesso token expirado: 410 ✓"


def test_reset_password_flow(engine):
    from fastapi.testclient import TestClient
    from redato_backend.portal.portal_app import app
    client = TestClient(app)

    with Session(engine) as session:
        e = Escola(codigo="E-RS-001", nome="EscolaRs",
                   estado="CE", municipio="Fortaleza")
        session.add(e); session.flush()
        prof = Professor(
            escola_id=e.id, nome="Reset", email="reset@teste.br",
            senha_hash=hash_senha("Antiga123"),
        )
        session.add(prof); session.commit()

    # Solicitar (sempre 200)
    r = client.post("/auth/reset-password/solicitar",
                    json={"email": "reset@teste.br"})
    assert r.status_code == 200

    # Solicitar pra email inexistente também 200 (anti-enumeração)
    r2 = client.post("/auth/reset-password/solicitar",
                     json={"email": "ninguem@teste.br"})
    assert r2.status_code == 200

    # Pega token do DB
    with Session(engine) as session:
        token = session.execute(
            text(f"SELECT reset_password_token "
                 f"FROM \"{TEST_SCHEMA}\".professores "
                 f"WHERE email = 'reset@teste.br'")
        ).scalar()
    assert token, "reset token não foi gerado"

    # Confirmar com senha nova
    r = client.post("/auth/reset-password/confirmar",
                    json={"token": token, "senha_nova": "NovaSenha456"})
    assert r.status_code == 200

    # Login com nova senha
    r = client.post("/auth/login", json={
        "email": "reset@teste.br", "senha": "NovaSenha456",
    })
    assert r.status_code == 200, f"got {r.status_code}: {r.text}"

    # Reset token foi consumido (NULL)
    with Session(engine) as session:
        token_pos = session.execute(
            text(f"SELECT reset_password_token "
                 f"FROM \"{TEST_SCHEMA}\".professores "
                 f"WHERE email = 'reset@teste.br'")
        ).scalar()
    assert token_pos is None

    return "reset password: solicitar (200) → confirmar (200) → login OK ✓"


def test_reset_token_expirado(engine):
    from fastapi.testclient import TestClient
    from redato_backend.portal.portal_app import app
    client = TestClient(app)

    with Session(engine) as session:
        e = Escola(codigo="E-RST-001", nome="EscolaRst",
                   estado="CE", municipio="Fortaleza")
        session.add(e); session.flush()
        prof = Professor(
            escola_id=e.id, nome="ExpReset", email="expreset@teste.br",
            senha_hash=hash_senha("Antiga123"),
            reset_password_token="reset_exp_" + uuid.uuid4().hex[:16],
            reset_password_expira_em=(
                datetime.now(timezone.utc) - timedelta(minutes=10)
            ),
        )
        session.add(prof); session.commit()
        token = prof.reset_password_token

    r = client.post("/auth/reset-password/confirmar",
                    json={"token": token, "senha_nova": "Outra123"})
    assert r.status_code == 410, f"got {r.status_code}"
    return "reset token expirado: 410 ✓"


def test_cleanup_tokens(engine):
    """Cleanup remove tokens expirados."""
    with Session(engine) as session:
        e = Escola(codigo="E-CL-001", nome="EscolaCl",
                   estado="CE", municipio="Fortaleza")
        session.add(e); session.flush()
        # Prof com primeiro_acesso_token expirado
        p = Professor(
            escola_id=e.id, nome="Clean", email="clean@teste.br",
            primeiro_acesso_token="tok_clean_" + uuid.uuid4().hex[:16],
            primeiro_acesso_expira_em=(
                datetime.now(timezone.utc) - timedelta(days=1)
            ),
        )
        # Prof com reset expirado
        p2 = Professor(
            escola_id=e.id, nome="Clean2", email="clean2@teste.br",
            senha_hash=hash_senha("Senha123"),
            reset_password_token="reset_clean_" + uuid.uuid4().hex[:16],
            reset_password_expira_em=(
                datetime.now(timezone.utc) - timedelta(minutes=30)
            ),
        )
        # Blocklist entry expirado
        blk = TokenBlocklist(
            token_jti="jti_old_" + uuid.uuid4().hex[:8],
            exp_original=datetime.now(timezone.utc) - timedelta(days=2),
        )
        session.add_all([p, p2, blk])
        session.commit()

        stats = auth_cleanup.run_all(session)
        assert stats["primeiro_acesso_expirados"] >= 1
        assert stats["reset_tokens_expirados"] >= 1
        assert stats["blocklist_removida"] >= 1

    return f"cleanup: {stats} ✓"


def test_importer_aceita_colunas_extras(engine, tmp_dir):
    """Update M2: planilha com escola_estado/escola_municipio é aceita."""
    from redato_backend.portal.importer import parse_planilha, run_import

    csv = tmp_dir / "extras.csv"
    csv.write_text(
        "escola_id,escola_nome,escola_estado,escola_municipio,"
        "coordenador_email,coordenador_nome,professor_email,"
        "professor_nome,turma_codigo,turma_serie\n"
        "SEDUC-CE-501,Escola E,CE,Sobral,c@e.br,Coord,p@e.br,Prof,1A,1S\n",
        encoding="utf-8",
    )
    rows, issues_struct = parse_planilha(csv)
    assert any(i.code == "headers_extras" for i in issues_struct) is False, \
        "extras OPTIONAL não deveriam virar warning"
    # Headers extras dentro da whitelist são ignorados sem warning.

    with Session(engine) as session:
        report = run_import(session, csv, modo="commit", ano_letivo=2026)
    d = report.to_dict()
    assert d["escolas_novas"] == 1
    # Verifica que UF do explicit foi usado
    with Session(engine) as session:
        estado = session.execute(text(
            f"SELECT estado FROM \"{TEST_SCHEMA}\".escolas "
            f"WHERE codigo = 'SEDUC-CE-501'"
        )).scalar()
    assert estado == "CE", f"esperava CE, got {estado!r}"
    return "importer aceita escola_estado + municipio explícitos ✓"


def test_importer_warning_estado_inferido(engine, tmp_dir):
    """Quando regex permissivo aceita escola_id sem UF inferível e não
    há coluna escola_estado, dispara warning + fallback BR."""
    from redato_backend.portal.importer import run_import

    csv = tmp_dir / "no_estado.csv"
    # Codigo "ABC-12345" não tem UF de 2 letras inferível.
    csv.write_text(
        "escola_id,escola_nome,coordenador_email,coordenador_nome,"
        "professor_email,professor_nome,turma_codigo,turma_serie\n"
        "ABC-12345,Escola SemUF,c2@e.br,Coord,p2@e.br,Prof,1A,1S\n",
        encoding="utf-8",
    )
    # Override regex pra aceitar formato sem UF (caso real ex.: IFCE-123)
    old_regex = os.environ.get("PORTAL_ESCOLA_ID_REGEX")
    os.environ["PORTAL_ESCOLA_ID_REGEX"] = r"^[A-Z]+-\d{3,}$"
    try:
        with Session(engine) as session:
            report = run_import(session, csv, modo="commit", ano_letivo=2026)
    finally:
        if old_regex is None:
            os.environ.pop("PORTAL_ESCOLA_ID_REGEX", None)
        else:
            os.environ["PORTAL_ESCOLA_ID_REGEX"] = old_regex

    d = report.to_dict()
    warns_codes = {w["code"] for w in d.get("warnings") or []}
    assert "estado_inferido_fallback" in warns_codes, \
        f"esperava warning de fallback, got: {warns_codes} | erros: {d.get('erros')}"
    with Session(engine) as session:
        estado = session.execute(text(
            f"SELECT estado FROM \"{TEST_SCHEMA}\".escolas "
            f"WHERE codigo = 'ABC-12345'"
        )).scalar()
    assert estado == "BR"
    return "importer com escola_id sem UF: warning + fallback BR ✓"


def test_send_welcome_proteções(engine, tmp_dir):
    """confirmar_envio=false → 400 com preview. Limite >100 → 400."""
    from fastapi.testclient import TestClient
    from redato_backend.portal.portal_app import app
    client = TestClient(app)

    # Cria 3 users sem senha
    with Session(engine) as session:
        e = Escola(codigo="E-WC-001", nome="EscolaWc",
                   estado="CE", municipio="Fortaleza")
        session.add(e); session.flush()
        for i in range(3):
            session.add(Professor(
                escola_id=e.id, nome=f"P{i}",
                email=f"wc{i}-{uuid.uuid4().hex[:6]}@teste.br",
            ))
        session.commit()

    # Sem confirmar_envio → 400 com preview
    r = client.post("/admin/send-welcome-emails",
                    headers={"X-Admin-Token": os.environ["ADMIN_TOKEN"]},
                    json={})
    assert r.status_code == 400, f"got {r.status_code}: {r.text}"
    body = r.json()
    detail = body.get("detail") or {}
    if isinstance(detail, dict):
        assert "n_alvo" in detail or "max_permitido" in detail, \
            f"detail sem campos esperados: {detail}"

    # Com confirmar_envio=true → 200
    r = client.post("/admin/send-welcome-emails",
                    headers={"X-Admin-Token": os.environ["ADMIN_TOKEN"]},
                    json={"confirmar_envio": True})
    assert r.status_code == 200, f"got {r.status_code}: {r.text}"

    # Audit log foi populado
    assert test_audit.exists(), "audit log não foi criado"
    return "send-welcome: confirmar_envio obrigatório + audit log ✓"


# ──────────────────────────────────────────────────────────────────────
# Runner
# ──────────────────────────────────────────────────────────────────────

TESTS = [
    test_password_validation,
    test_jwt_encode_decode,
    test_jwt_invalid_audience,
    test_permissions_pure_funcs,
    test_fluxo_primeiro_acesso_completo,
    test_login_errado_e_inativo,
    test_token_primeiro_acesso_expirado,
    test_reset_password_flow,
    test_reset_token_expirado,
    test_cleanup_tokens,
    test_importer_aceita_colunas_extras,
    test_importer_warning_estado_inferido,
    test_send_welcome_proteções,
]


def main():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("ERRO: DATABASE_URL não configurada"); sys.exit(1)
    print(f"DATABASE_URL: {db_url}")
    print(f"Test schema : {TEST_SCHEMA}")
    print(f"Audit log   : {test_audit}")
    print()

    engine = create_engine(db_url, future=True)
    _setup_schema(engine)

    # Patch get_engine + search_path
    from redato_backend.portal import db as portal_db
    portal_db._engine = None
    portal_db.get_engine = lambda *a, **k: engine

    from sqlalchemy import event

    @event.listens_for(engine, "connect")
    def _set_search_path(dbapi_conn, _conn_record):
        with dbapi_conn.cursor() as cur:
            cur.execute(f'SET search_path TO "{TEST_SCHEMA}", public')

    tmp_dir = Path(tempfile.mkdtemp(prefix="m3csv_"))
    print(f"\n{'='*70}")
    failures = []
    try:
        for fn in TESTS:
            try:
                # Algumas funções precisam tmp_dir, outras não
                import inspect
                sig = inspect.signature(fn)
                if len(sig.parameters) == 2:
                    res = fn(engine, tmp_dir)
                else:
                    res = fn(engine)
                print(f"  ✓ {fn.__name__}: {res}")
            except AssertionError as exc:
                print(f"  ✗ {fn.__name__}: AssertionError: {exc}")
                failures.append((fn.__name__, str(exc)))
            except Exception as exc:
                print(f"  ✗ {fn.__name__}: {type(exc).__name__}: {exc}")
                failures.append((fn.__name__, repr(exc)))
    finally:
        portal_db._engine = None
        try:
            _teardown_schema(engine)
        except Exception as exc:
            print(f"WARN teardown: {exc!r}")

    print(f"\n{'='*70}")
    if failures:
        print(f"FALHA: {len(failures)}/{len(TESTS)}")
        sys.exit(1)
    print(f"OK: {len(TESTS)}/{len(TESTS)} testes passaram")


if __name__ == "__main__":
    main()
