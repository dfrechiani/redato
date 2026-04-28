#!/usr/bin/env python3
"""Smoke M8 — geração de PDF + emails transacionais + triggers + health.

Roda contra Postgres em schema isolado. Não depende de SendGrid real
(modo dry-run via ausência de SENDGRID_API_KEY) nem de Twilio.

Cenários:
- Geração de PDF dashboard turma com dados sintéticos
- PDF tem magic %PDF e tamanho razoável
- PDF de escola só pra coordenador (403 pra prof)
- PDF de evolução aluno
- Histórico lista os PDFs gerados
- Download retorna application/pdf
- Permission: prof não baixa PDF de outra escola (403)
- Email send_pdf_disponivel em modo dry-run gera linha no jsonl
- Trigger atividade encerrada dispara email pendente
- Trigger alunos em risco respeita limite semanal (1×/7d)
- Trigger é idempotente — chamada 2× só envia 1× por escopo
- /admin/health/full responde com status: ok | degraded
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
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

os.environ.setdefault(
    "JWT_SECRET_KEY",
    "test_secret_at_least_32_chars_for_smoke_m8_pdf_email_xx_yy_zz",
)
os.environ.setdefault("ADMIN_TOKEN", "test-admin-token-m8")
os.environ.pop("SENDGRID_API_KEY", None)   # força dry-run de email
os.environ.pop("TWILIO_ACCOUNT_SID", None)

# Storage isolado pros PDFs do test
_PDF_STORAGE = Path(tempfile.mkdtemp(prefix="m8pdfs_"))
os.environ["STORAGE_PDFS_PATH"] = str(_PDF_STORAGE)

TEST_SCHEMA = f"m8_test_{uuid.uuid4().hex[:8]}"

from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from redato_backend.portal.db import Base  # noqa: E402
from redato_backend.portal import models  # noqa: F401, E402
from redato_backend.portal import portal_api  # noqa: E402
from redato_backend.portal import email_service as ES  # noqa: E402
from redato_backend.portal import triggers as TR  # noqa: E402
from redato_backend.portal.auth.jwt_service import encode_token  # noqa: E402
from redato_backend.portal.auth.password import hash_senha  # noqa: E402
from redato_backend.portal.models import (  # noqa: E402
    AlunoTurma, Atividade, Coordenador, Envio, Escola, Interaction,
    Missao, PdfGerado, Professor, Turma,
)
from redato_backend.portal.seed_missoes import seed_missoes  # noqa: E402


_test_audit = Path(tempfile.mkdtemp(prefix="m8audit_")) / "audit.jsonl"
portal_api._AUDIT_LOG = _test_audit
# Log isolado pros triggers
TR._TRIGGERS_LOG = Path(tempfile.mkdtemp(prefix="m8trig_")) / "triggers_log.jsonl"
# JSONL isolado pros emails dry-run
ES._PENDING_LOG = Path(tempfile.mkdtemp(prefix="m8email_")) / "emails_pendentes.jsonl"


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


def _redato_output(nota: int) -> str:
    return json.dumps({
        "nota_total": nota,
        "C1": {"nota": min(nota // 5, 200)},
        "C2": {"nota": min(nota // 5, 200)},
        "C3": {"nota": min(nota // 5, 200)},
        "C4": {"nota": min(nota // 5, 200)},
        "C5": {"nota": min(nota // 5, 200)},
        "audit_pedagogico": "Texto de teste.",
        "flag_proposta_vaga": True,
    }, ensure_ascii=False)


class World:
    def __init__(self):
        self.escola_id = None
        self.escola_outra_id = None
        self.coord_id = None
        self.prof_id = None
        self.prof_outro_id = None
        self.turma_id = None
        self.aluno_id = None
        self.atividade_encerrada_id = None
        self.atividade_ativa_id = None


def _seed_world(engine) -> World:
    w = World()
    with Session(engine) as session:
        seed_missoes(session); session.commit()

        e1 = Escola(codigo=f"E-{uuid.uuid4().hex[:6]}", nome="Escola M8",
                    estado="CE", municipio="Fortaleza")
        e2 = Escola(codigo=f"E-{uuid.uuid4().hex[:6]}", nome="Outra Escola",
                    estado="CE", municipio="Fortaleza")
        session.add_all([e1, e2]); session.flush()

        coord = Coordenador(escola_id=e1.id, nome="Coord M8",
                            email=f"coord-{uuid.uuid4().hex[:4]}@m.br",
                            senha_hash=hash_senha("Senha123Forte"))
        prof = Professor(escola_id=e1.id, nome="Prof M8",
                         email=f"prof-{uuid.uuid4().hex[:4]}@m.br",
                         senha_hash=hash_senha("Senha123Forte"))
        prof2 = Professor(escola_id=e2.id, nome="Prof Outro",
                          email=f"prof2-{uuid.uuid4().hex[:4]}@m.br",
                          senha_hash=hash_senha("Senha123Forte"))
        session.add_all([coord, prof, prof2]); session.flush()

        turma = Turma(escola_id=e1.id, professor_id=prof.id,
                      codigo="2A", serie="1S",
                      codigo_join=f"TURMA-M-{uuid.uuid4().hex[:4]}-2026",
                      ano_letivo=2026)
        session.add(turma); session.flush()

        a1 = AlunoTurma(turma_id=turma.id, nome="Ana M8",
                        telefone=f"+5511{uuid.uuid4().hex[:8]}")
        a2 = AlunoTurma(turma_id=turma.id, nome="Bruno M8",
                        telefone=f"+5511{uuid.uuid4().hex[:8]}")
        a3 = AlunoTurma(turma_id=turma.id, nome="Carla M8",
                        telefone=f"+5511{uuid.uuid4().hex[:8]}")
        session.add_all([a1, a2, a3]); session.flush()

        m_foco = session.execute(
            text(f"SELECT id FROM \"{TEST_SCHEMA}\".missoes "
                 f"WHERE codigo = 'RJ1·OF10·MF'")
        ).scalar()
        m_completo = session.execute(
            text(f"SELECT id FROM \"{TEST_SCHEMA}\".missoes "
                 f"WHERE codigo = 'RJ1·OF14·MF'")
        ).scalar()

        agora = datetime.now(timezone.utc)
        atv_enc = Atividade(
            turma_id=turma.id, missao_id=m_foco,
            data_inicio=agora - timedelta(days=10),
            data_fim=agora - timedelta(days=2),  # encerrada
            criada_por_professor_id=prof.id,
        )
        atv_ativa = Atividade(
            turma_id=turma.id, missao_id=m_completo,
            data_inicio=agora - timedelta(days=1),
            data_fim=agora + timedelta(days=5),
            criada_por_professor_id=prof.id,
        )
        session.add_all([atv_enc, atv_ativa]); session.flush()

        # Ana fez encerrada com nota baixa (60), depois ativa também
        # baixa (320). 2 missões insuficientes.
        # Bruno fez encerrada com nota 60 (insuficiente também).
        # Carla fez ativa com nota 60 (foco).
        # Pra trigger de risco (≥3 missões baixas), criamos mais
        # uma atividade encerrada com Ana e Bruno também baixos.
        atv_enc2 = Atividade(
            turma_id=turma.id, missao_id=m_foco,
            data_inicio=agora - timedelta(days=20),
            data_fim=agora - timedelta(days=15),
            criada_por_professor_id=prof.id,
        )
        atv_enc3 = Atividade(
            turma_id=turma.id, missao_id=m_completo,
            data_inicio=agora - timedelta(days=25),
            data_fim=agora - timedelta(days=22),
            criada_por_professor_id=prof.id,
        )
        session.add_all([atv_enc2, atv_enc3]); session.flush()

        # Helper local pra criar Interaction + Envio
        def _envio(ativ, aluno, nota):
            it = Interaction(
                aluno_phone=aluno.telefone, aluno_turma_id=aluno.id,
                envio_id=None, source="whatsapp_portal",
                missao_id="STUB", activity_id=str(uuid.uuid4()),
                redato_output=_redato_output(nota),
                ocr_quality_issues="[]",
            )
            session.add(it); session.flush()
            ev = Envio(atividade_id=ativ.id, aluno_turma_id=aluno.id,
                       interaction_id=it.id, enviado_em=agora)
            session.add(ev); session.flush()
            it.envio_id = ev.id

        # Ana: 3 baixas (foco 60 + completo 320 + foco 60 + completo 380)
        _envio(atv_enc, a1, 60)
        _envio(atv_ativa, a1, 320)
        _envio(atv_enc2, a1, 60)
        _envio(atv_enc3, a1, 380)
        # Bruno: 1 baixa só → não ativa risco
        _envio(atv_enc, a2, 60)
        _envio(atv_ativa, a2, 720)  # bom
        # Carla: nenhum envio na atv_enc → pendente

        session.commit()

        w.escola_id = e1.id
        w.escola_outra_id = e2.id
        w.coord_id = coord.id
        w.prof_id = prof.id
        w.prof_outro_id = prof2.id
        w.turma_id = turma.id
        w.aluno_id = a1.id
        w.atividade_encerrada_id = atv_enc.id
        w.atividade_ativa_id = atv_ativa.id
    return w


def _client():
    from fastapi.testclient import TestClient
    from redato_backend.portal.portal_app import app
    return TestClient(app)


def _bearer(world, papel: str) -> dict:
    if papel == "professor":
        token, _ = encode_token(
            user_id=str(world.prof_id), papel="professor",
            escola_id=str(world.escola_id),
        )
    elif papel == "professor_outra":
        token, _ = encode_token(
            user_id=str(world.prof_outro_id), papel="professor",
            escola_id=str(world.escola_outra_id),
        )
    elif papel == "coord":
        token, _ = encode_token(
            user_id=str(world.coord_id), papel="coordenador",
            escola_id=str(world.escola_id),
        )
    else:
        raise ValueError(papel)
    return {"Authorization": f"Bearer {token}"}


# ──────────────────────────────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────────────────────────────

def test_pdf_dashboard_turma_gera(_engine, world):
    cli = _client()
    r = cli.post(f"/portal/pdfs/dashboard-turma/{world.turma_id}",
                 json={}, headers=_bearer(world, "professor"))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["tamanho_bytes"] > 1000, body
    assert body["download_url"].startswith("/portal/pdfs/")
    # Verifica magic do PDF no disco
    with Session(_engine) as s:
        pdf = s.get(PdfGerado, uuid.UUID(body["pdf_id"]))
    full = _PDF_STORAGE / pdf.arquivo_path
    assert full.exists()
    head = full.read_bytes()[:4]
    assert head == b"%PDF", f"magic incorreto: {head!r}"
    return f"PDF turma gerado: {body['tamanho_bytes']} bytes ✓"


def test_pdf_download_application_pdf(_engine, world):
    cli = _client()
    r1 = cli.post(f"/portal/pdfs/dashboard-turma/{world.turma_id}",
                  json={}, headers=_bearer(world, "professor"))
    pdf_id = r1.json()["pdf_id"]
    r = cli.get(f"/portal/pdfs/{pdf_id}/download",
                headers=_bearer(world, "professor"))
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.headers.get("content-disposition", "").startswith("attachment;")
    assert r.content[:4] == b"%PDF"
    return f"download retorna application/pdf ({len(r.content)} bytes) ✓"


def test_pdf_dashboard_escola_so_coord(_engine, world):
    cli = _client()
    # Prof tenta gerar PDF da escola → 403
    r1 = cli.post(f"/portal/pdfs/dashboard-escola/{world.escola_id}",
                  json={}, headers=_bearer(world, "professor"))
    assert r1.status_code == 403
    # Coord consegue
    r2 = cli.post(f"/portal/pdfs/dashboard-escola/{world.escola_id}",
                  json={}, headers=_bearer(world, "coord"))
    assert r2.status_code == 200
    return "PDF escola: prof 403, coord 200 ✓"


def test_pdf_evolucao_aluno(_engine, world):
    cli = _client()
    r = cli.post(
        f"/portal/pdfs/evolucao-aluno/{world.turma_id}/{world.aluno_id}",
        json={}, headers=_bearer(world, "professor"),
    )
    assert r.status_code == 200, r.text
    assert r.json()["tamanho_bytes"] > 800
    return f"PDF evolução aluno: {r.json()['tamanho_bytes']} bytes ✓"


def test_pdf_download_outra_escola_403(_engine, world):
    cli = _client()
    r1 = cli.post(f"/portal/pdfs/dashboard-turma/{world.turma_id}",
                  json={}, headers=_bearer(world, "professor"))
    pdf_id = r1.json()["pdf_id"]
    # Prof de outra escola tenta baixar
    r = cli.get(f"/portal/pdfs/{pdf_id}/download",
                headers=_bearer(world, "professor_outra"))
    assert r.status_code == 403, r.text
    return "download de PDF por prof de outra escola → 403 ✓"


def test_pdf_historico(_engine, world):
    cli = _client()
    # Gera 1 PDF
    cli.post(f"/portal/pdfs/dashboard-turma/{world.turma_id}",
             json={}, headers=_bearer(world, "professor"))
    r = cli.get("/portal/pdfs/historico",
                headers=_bearer(world, "professor"))
    assert r.status_code == 200
    items = r.json()
    assert len(items) >= 1
    assert all("download_url" in i for i in items)
    return f"histórico lista {len(items)} PDF(s) ✓"


def test_email_pdf_disponivel_dry_run(_engine, world):
    """Sem SENDGRID_API_KEY, manda pra emails_pendentes.jsonl."""
    pre_size = ES._PENDING_LOG.stat().st_size if ES._PENDING_LOG.exists() else 0
    ok, msg = ES.send_pdf_disponivel(
        to_email="prof@m.br", to_name="Prof M8",
        pdf_id="00000000-0000-0000-0000-000000000001",
        pdf_tipo="dashboard_turma",
    )
    assert ok, msg
    assert "dry-run" in msg
    post_size = ES._PENDING_LOG.stat().st_size
    assert post_size > pre_size, "esperava append no jsonl"
    # Verifica conteúdo
    last = ES._PENDING_LOG.read_text("utf-8").strip().split("\n")[-1]
    rec = json.loads(last)
    assert rec["to_email"] == "prof@m.br"
    assert "Dashboard da turma" in rec["subject"]
    return "email PDF disponível dry-run → jsonl ✓"


def test_trigger_atividade_encerrada(_engine, world):
    """Atividade encerrada com pendentes → email pendente jsonl."""
    pre = ES._PENDING_LOG.stat().st_size if ES._PENDING_LOG.exists() else 0
    ok = TR.trigger_atividade_encerrada(world.atividade_encerrada_id)
    assert ok, "trigger deveria disparar (atv encerrada com pendentes)"
    post = ES._PENDING_LOG.stat().st_size
    assert post > pre

    # 2ª chamada — idempotente, não envia de novo
    ok2 = TR.trigger_atividade_encerrada(world.atividade_encerrada_id)
    assert not ok2, "2ª chamada deveria ser idempotente (skip)"
    return "trigger atividade encerrada: 1ª envia, 2ª pula ✓"


def test_trigger_alunos_em_risco_rate_limit(_engine, world):
    """1ª chamada envia, 2ª (na mesma janela 7d) skipa."""
    pre = ES._PENDING_LOG.stat().st_size if ES._PENDING_LOG.exists() else 0
    ok = TR.trigger_alunos_em_risco(world.turma_id)
    assert ok, "esperava envio (Ana tem ≥3 missões insuficientes)"
    post = ES._PENDING_LOG.stat().st_size
    assert post > pre

    ok2 = TR.trigger_alunos_em_risco(world.turma_id)
    assert not ok2, "2ª chamada deve ser pulada por rate limit"
    return "trigger alunos em risco: 1ª envia, 2ª rate-limited ✓"


def test_admin_health_full(_engine, world):
    cli = _client()
    r = cli.get("/admin/health/full")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] in ("ok", "degraded")
    assert "checks" in body
    assert body["checks"]["db_ping"] is True
    assert body["checks"]["storage_pdfs_writable"] is True
    return f"/admin/health/full: status={body['status']}, db_ping=True ✓"


def test_admin_triggers_run(_engine, world):
    """Endpoint que cron externo chama. Reseta log primeiro pra
    isolar o teste dos triggers anteriores."""
    cli = _client()
    # Isola: reseta o log
    if TR._TRIGGERS_LOG.exists():
        TR._TRIGGERS_LOG.unlink()
    r = cli.post("/admin/triggers/run",
                 headers={"X-Admin-Token": os.environ["ADMIN_TOKEN"]})
    assert r.status_code == 200, r.text
    body = r.json()
    # A turma tem 4 atividades encerradas (atv_enc, atv_enc2, atv_enc3 + ativa
    # encerrou? não — só as 3 encerradas) e 1 turma com risco.
    # Mas atv_enc só tem 1 pendente (Carla); outras encerradas têm
    # diferentes envios. Pelo menos 1 trigger deve ter rodado.
    assert (body["encerradas_avisadas"] + body["risco_avisados"]) >= 1, body
    return (f"triggers/run: {body['encerradas_avisadas']} enc + "
            f"{body['risco_avisados']} risco ✓")


# ──────────────────────────────────────────────────────────────────────
# Runner
# ──────────────────────────────────────────────────────────────────────

TESTS = [
    test_pdf_dashboard_turma_gera,
    test_pdf_download_application_pdf,
    test_pdf_dashboard_escola_so_coord,
    test_pdf_evolucao_aluno,
    test_pdf_download_outra_escola_403,
    test_pdf_historico,
    test_email_pdf_disponivel_dry_run,
    test_trigger_atividade_encerrada,
    test_trigger_alunos_em_risco_rate_limit,
    test_admin_health_full,
    test_admin_triggers_run,
]


def main():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("ERRO: DATABASE_URL não configurada"); sys.exit(1)
    print(f"DATABASE_URL: {db_url}")
    print(f"Test schema : {TEST_SCHEMA}")
    print(f"PDF storage : {_PDF_STORAGE}\n")

    engine = create_engine(db_url, future=True)
    _setup_schema(engine)

    from redato_backend.portal import db as portal_db
    portal_db._engine = None
    portal_db.get_engine = lambda *a, **k: engine

    from sqlalchemy import event
    @event.listens_for(engine, "connect")
    def _set_search_path(dbapi_conn, _conn_record):
        with dbapi_conn.cursor() as cur:
            cur.execute(f'SET search_path TO "{TEST_SCHEMA}", public')

    world = _seed_world(engine)

    print(f"{'='*70}")
    failures = []
    try:
        for fn in TESTS:
            try:
                res = fn(engine, world)
                print(f"  ✓ {fn.__name__}: {res}")
            except AssertionError as exc:
                print(f"  ✗ {fn.__name__}: AssertionError: {exc}")
                failures.append((fn.__name__, str(exc)))
            except Exception as exc:
                print(f"  ✗ {fn.__name__}: {type(exc).__name__}: {exc}")
                import traceback
                traceback.print_exc()
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
