#!/usr/bin/env python3
"""Smoke M7 — dashboards de turma, escola e evolução do aluno.

Testa contratos HTTP dos novos endpoints contra Postgres em schema
isolado. Cobre os critérios de sucesso de M7:

- Estrutura completa do dashboard de turma com dados sintéticos
- Dashboard de turma sem envios → estrutura vazia válida (não crasha)
- Dashboard de escola só pra coordenador (professor → 403)
- Dashboard de escola com 1 turma: comparacao_turmas vazia
- Dashboard de escola com ≥ 2 turmas: comparacao populada
- Evolução de aluno com 0 missões: lista vazia
- Evolução de aluno com 5 missões: chart populado
- Buckets de Foco (0-200) e Completo (0-1000) separados corretamente
- Detectores desconhecidos vão pro contador "outros"
- Detectores canônicos aparecem no top-N com nome humano
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
    "test_secret_at_least_32_chars_for_smoke_m7_dashboard_xx_yy_zz",
)
os.environ.setdefault("ADMIN_TOKEN", "test-admin-token-m7")
os.environ.pop("SENDGRID_API_KEY", None)
os.environ.pop("TWILIO_ACCOUNT_SID", None)

TEST_SCHEMA = f"m7_test_{uuid.uuid4().hex[:8]}"

from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from redato_backend.portal.db import Base  # noqa: E402
from redato_backend.portal import models  # noqa: F401, E402
from redato_backend.portal import portal_api  # noqa: E402
from redato_backend.portal.auth.jwt_service import encode_token  # noqa: E402
from redato_backend.portal.auth.password import hash_senha  # noqa: E402
from redato_backend.portal.models import (  # noqa: E402
    AlunoTurma, Atividade, Coordenador, Envio, Escola, Interaction,
    Missao, Professor, Turma,
)
from redato_backend.portal.seed_missoes import seed_missoes  # noqa: E402


_test_audit = Path(tempfile.mkdtemp(prefix="m7audit_")) / "audit.jsonl"
portal_api._AUDIT_LOG = _test_audit


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


def _redato_output(nota_total: int, *, detectores: dict | None = None) -> str:
    base = {
        "nota_total": nota_total,
        "C1": {"nota": min(nota_total // 5, 200)},
        "C2": {"nota": min(nota_total // 5, 200)},
        "C3": {"nota": min(nota_total // 5, 200)},
        "C4": {"nota": min(nota_total // 5, 200)},
        "C5": {"nota": min(nota_total // 5, 200)},
        "audit_pedagogico": "Texto de teste.",
    }
    if detectores:
        base.update(detectores)
    return json.dumps(base, ensure_ascii=False)


def _criar_envio(session, *, atividade, aluno, nota, detectores=None,
                 enviado_em=None):
    """Helper: cria Interaction + Envio + cross-link."""
    interaction = Interaction(
        aluno_phone=aluno.telefone, aluno_turma_id=aluno.id, envio_id=None,
        source="whatsapp_portal", missao_id="STUB",
        activity_id=str(uuid.uuid4()),
        redato_output=_redato_output(nota, detectores=detectores),
        ocr_quality_issues="[]",
    )
    session.add(interaction); session.flush()
    envio = Envio(
        atividade_id=atividade.id, aluno_turma_id=aluno.id,
        interaction_id=interaction.id,
        enviado_em=enviado_em or datetime.now(timezone.utc),
    )
    session.add(envio); session.flush()
    interaction.envio_id = envio.id
    return interaction, envio


# ──────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────

class World:
    def __init__(self):
        self.escola_id = None
        self.escola_outra_id = None
        self.coord_id = None
        self.prof_id = None
        self.prof_outro_id = None
        self.turma_id = None         # turma A — populada com envios
        self.turma_vazia_id = None   # turma B — sem envios
        self.aluno1_id = None
        self.aluno2_id = None
        self.aluno_pendente_id = None
        self.atividade_foco_id = None
        self.atividade_completo_id = None


def _seed_world(engine) -> World:
    w = World()
    with Session(engine) as session:
        seed_missoes(session); session.commit()

        e1 = Escola(codigo=f"E-CE-{uuid.uuid4().hex[:6]}", nome="Escola Alfa",
                    estado="CE", municipio="Fortaleza")
        e2 = Escola(codigo=f"E-CE-{uuid.uuid4().hex[:6]}", nome="Escola Beta",
                    estado="CE", municipio="Fortaleza")
        session.add_all([e1, e2]); session.flush()

        coord = Coordenador(escola_id=e1.id, nome="Coord Alfa",
                            email=f"coord-{uuid.uuid4().hex[:4]}@a.br",
                            senha_hash=hash_senha("Senha123"))
        prof = Professor(escola_id=e1.id, nome="Prof Alfa",
                         email=f"prof-{uuid.uuid4().hex[:4]}@a.br",
                         senha_hash=hash_senha("Senha123"))
        prof2 = Professor(escola_id=e1.id, nome="Prof Outro",
                          email=f"prof2-{uuid.uuid4().hex[:4]}@a.br",
                          senha_hash=hash_senha("Senha123"))
        session.add_all([coord, prof, prof2]); session.flush()

        turma = Turma(escola_id=e1.id, professor_id=prof.id,
                      codigo="1A", serie="1S",
                      codigo_join=f"TURMA-A-{uuid.uuid4().hex[:4]}-2026",
                      ano_letivo=2026)
        # 2ª turma na mesma escola, com outro prof — pra comparação
        turma2 = Turma(escola_id=e1.id, professor_id=prof2.id,
                       codigo="1B", serie="1S",
                       codigo_join=f"TURMA-B-{uuid.uuid4().hex[:4]}-2026",
                       ano_letivo=2026)
        session.add_all([turma, turma2]); session.flush()

        a1 = AlunoTurma(turma_id=turma.id, nome="Ana Aluna",
                        telefone=f"+5511{uuid.uuid4().hex[:8]}")
        a2 = AlunoTurma(turma_id=turma.id, nome="Bruno Aluno",
                        telefone=f"+5511{uuid.uuid4().hex[:8]}")
        a_pendente = AlunoTurma(turma_id=turma.id, nome="Cíntia Aluna",
                                telefone=f"+5511{uuid.uuid4().hex[:8]}")
        # Aluno na turma 2 também
        b1 = AlunoTurma(turma_id=turma2.id, nome="Diego Aluno",
                        telefone=f"+5511{uuid.uuid4().hex[:8]}")
        session.add_all([a1, a2, a_pendente, b1]); session.flush()

        # Missões
        m_foco_c3 = session.execute(
            text(f"SELECT id FROM \"{TEST_SCHEMA}\".missoes "
                 f"WHERE codigo = 'RJ1·OF10·MF'")
        ).scalar()
        m_completo = session.execute(
            text(f"SELECT id FROM \"{TEST_SCHEMA}\".missoes "
                 f"WHERE codigo = 'RJ1·OF14·MF'")
        ).scalar()
        m_foco_c4 = session.execute(
            text(f"SELECT id FROM \"{TEST_SCHEMA}\".missoes "
                 f"WHERE codigo = 'RJ1·OF11·MF'")
        ).scalar()

        agora = datetime.now(timezone.utc)
        atv_foco = Atividade(
            turma_id=turma.id, missao_id=m_foco_c3,
            data_inicio=agora - timedelta(days=10),
            data_fim=agora - timedelta(days=3),  # encerrada
            criada_por_professor_id=prof.id,
        )
        atv_completo = Atividade(
            turma_id=turma.id, missao_id=m_completo,
            data_inicio=agora - timedelta(days=2),
            data_fim=agora + timedelta(days=5),  # ativa
            criada_por_professor_id=prof.id,
        )
        atv_pendente = Atividade(
            turma_id=turma.id, missao_id=m_foco_c4,
            data_inicio=agora - timedelta(days=1),
            data_fim=agora + timedelta(days=3),  # ativa, sem envios
            criada_por_professor_id=prof.id,
        )
        # Atividade na turma 2
        atv_t2 = Atividade(
            turma_id=turma2.id, missao_id=m_completo,
            data_inicio=agora - timedelta(days=5),
            data_fim=agora + timedelta(days=2),
            criada_por_professor_id=prof2.id,
        )
        session.add_all([atv_foco, atv_completo, atv_pendente, atv_t2])
        session.flush()

        # Envios na turma A:
        # Ana fez foco_c3 com nota 60 (insuficiente em foco)
        # Ana fez completo com nota 320 (insuficiente em completo)
        # → 2 missões insuficientes → em risco
        _criar_envio(
            session, atividade=atv_foco, aluno=a1, nota=60,
            detectores={
                "flag_proposta_vaga": True,
                "flag_repeticao_lexical": True,
                "flag_inventado_xyz": True,  # NÃO canônico → "outros"
            },
            enviado_em=agora - timedelta(days=4),
        )
        _criar_envio(
            session, atividade=atv_completo, aluno=a1, nota=320,
            detectores={"flag_proposta_vaga": True},
            enviado_em=agora - timedelta(days=1),
        )
        # Bruno fez foco_c3 com nota 160 (excelente)
        _criar_envio(
            session, atividade=atv_foco, aluno=a2, nota=160,
            detectores={"flag_repeticao_lexical": True},
            enviado_em=agora - timedelta(days=4),
        )
        # Bruno fez completo com nota 720 (bom)
        _criar_envio(
            session, atividade=atv_completo, aluno=a2, nota=720,
            detectores={},
            enviado_em=agora - timedelta(days=1),
        )

        # Envio na turma 2 — pra ter 2 turmas com dados (escola dashboard)
        _criar_envio(
            session, atividade=atv_t2, aluno=b1, nota=600,
            detectores={"flag_proposta_vaga": True},
            enviado_em=agora - timedelta(days=2),
        )

        session.commit()

        w.escola_id = e1.id
        w.escola_outra_id = e2.id
        w.coord_id = coord.id
        w.prof_id = prof.id
        w.prof_outro_id = prof2.id
        w.turma_id = turma.id
        w.turma_vazia_id = turma2.id  # tem 1 envio mas é "outra turma"
        w.aluno1_id = a1.id
        w.aluno2_id = a2.id
        w.aluno_pendente_id = a_pendente.id
        w.atividade_foco_id = atv_foco.id
        w.atividade_completo_id = atv_completo.id
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

def test_dashboard_turma_estrutura(_engine, world):
    cli = _client()
    r = cli.get(f"/portal/turmas/{world.turma_id}/dashboard",
                headers=_bearer(world, "professor"))
    assert r.status_code == 200, r.text
    body = r.json()

    assert body["turma"]["codigo"] == "1A"
    assert body["turma"]["n_alunos_ativos"] == 3  # Ana, Bruno, Cíntia

    assert body["atividades_total"] == 3
    assert body["atividades_ativas"] == 2  # completo + pendente
    assert body["atividades_encerradas"] == 1  # foco

    # Distribuição por modo: foco e completo populados separadamente
    foco = body["distribuicao_notas"]["foco"]
    completo = body["distribuicao_notas"]["completo"]
    # Ana 60 → 41-80, Bruno 160 → 121-160 (foco)
    assert foco["41-80"] == 1, f"foco 41-80: {foco}"
    assert foco["121-160"] == 1, f"foco 121-160: {foco}"
    # Ana 320 → 201-400, Bruno 720 → 601-800 (completo)
    assert completo["201-400"] == 1, f"completo: {completo}"
    assert completo["601-800"] == 1, f"completo: {completo}"

    # Top detectores: proposta_vaga (2x) + repeticao_lexical (2x) entre os top
    codigos_top = {d["codigo"] for d in body["top_detectores"]}
    assert "proposta_vaga" in codigos_top
    assert "repeticao_lexical" in codigos_top
    # Detector inventado NÃO entra no top — vai pra outros
    assert "flag_inventado_xyz" not in codigos_top
    assert body["outros_detectores"] >= 1, \
        f"esperava ≥ 1 outros, got {body['outros_detectores']}"

    # Aluno em risco: Ana com 2 missões insuficientes
    em_risco_ids = {a["aluno_id"] for a in body["alunos_em_risco"]}
    assert str(world.aluno1_id) in em_risco_ids, \
        f"Ana deveria estar em risco. got={body['alunos_em_risco']}"
    assert str(world.aluno2_id) not in em_risco_ids, \
        "Bruno não deveria estar em risco"

    # Evolução: 2 atividades com envios
    assert len(body["evolucao_turma"]) == 2
    assert body["n_envios_total"] == 4
    return f"dashboard turma: estrutura completa ✓ ({body['n_envios_total']} envios)"


def test_dashboard_turma_vazia(_engine, world):
    """Turma sem nenhum envio retorna estrutura vazia válida (não crasha).

    Criamos uma 3ª turma na escola só pra esse teste.
    """
    cli = _client()
    with Session(_engine) as s:
        prof = s.get(Professor, world.prof_id)
        nova = Turma(escola_id=prof.escola_id, professor_id=prof.id,
                     codigo="1Z", serie="1S",
                     codigo_join=f"TURMA-Z-{uuid.uuid4().hex[:4]}-2026",
                     ano_letivo=2026)
        s.add(nova); s.commit()
        nova_id = nova.id

    r = cli.get(f"/portal/turmas/{nova_id}/dashboard",
                headers=_bearer(world, "professor"))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["n_envios_total"] == 0
    assert body["alunos_em_risco"] == []
    assert body["evolucao_turma"] == []
    assert body["top_detectores"] == []
    # Distribuição vazia mas keys presentes
    assert all(v == 0 for v in body["distribuicao_notas"]["foco"].values())
    return "dashboard turma vazia: estrutura válida sem crash ✓"


def test_dashboard_escola_403_pra_professor(_engine, world):
    cli = _client()
    r = cli.get(f"/portal/escolas/{world.escola_id}/dashboard",
                headers=_bearer(world, "professor"))
    assert r.status_code == 403
    return "dashboard escola: professor → 403 ✓"


def test_dashboard_escola_coord_2_turmas(_engine, world):
    """Coord vê turmas da escola com dados → comparacao_turmas populada."""
    cli = _client()
    r = cli.get(f"/portal/escolas/{world.escola_id}/dashboard",
                headers=_bearer(world, "coord"))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["escola"]["nome"] == "Escola Alfa"
    # Pode ter ≥2 turmas (depende da ordem dos testes — outros podem
    # criar turmas extras na mesma escola). Importante: ambas com dados
    # entram na comparação.
    assert body["escola"]["n_turmas"] >= 2, body["escola"]
    assert len(body["turmas_resumo"]) >= 2
    # ≥ 2 turmas com média → comparação populada (turmas sem envios
    # ficam fora da comparação)
    assert len(body["comparacao_turmas"]) >= 2, body["comparacao_turmas"]
    codigos = {c["turma_codigo"] for c in body["comparacao_turmas"]}
    assert {"1A", "1B"}.issubset(codigos), codigos
    # Top detectores: proposta_vaga deve aparecer (3 vezes total)
    codigos_top = {d["codigo"] for d in body["top_detectores_escola"]}
    assert "proposta_vaga" in codigos_top
    return f"dashboard escola coord 2 turmas: comparação populada ✓"


def test_dashboard_escola_1_turma_comparacao_vazia(_engine, world):
    """Escola com só 1 turma (criada limpa) → comparacao_turmas vazia."""
    cli = _client()
    # Escola Beta foi criada vazia; precisa de coord nela pra testar
    with Session(_engine) as s:
        coord_b = Coordenador(
            escola_id=world.escola_outra_id, nome="Coord Beta",
            email=f"coord-b-{uuid.uuid4().hex[:4]}@b.br",
            senha_hash=hash_senha("Senha123"),
        )
        prof_b = Professor(
            escola_id=world.escola_outra_id, nome="Prof Beta",
            email=f"prof-b-{uuid.uuid4().hex[:4]}@b.br",
            senha_hash=hash_senha("Senha123"),
        )
        s.add_all([coord_b, prof_b]); s.flush()
        turma_b = Turma(
            escola_id=world.escola_outra_id, professor_id=prof_b.id,
            codigo="1A", serie="1S",
            codigo_join=f"TURMA-B-S-{uuid.uuid4().hex[:4]}-2026",
            ano_letivo=2026,
        )
        s.add(turma_b); s.commit()
        coord_b_id = coord_b.id

    token, _ = encode_token(
        user_id=str(coord_b_id), papel="coordenador",
        escola_id=str(world.escola_outra_id),
    )
    r = cli.get(f"/portal/escolas/{world.escola_outra_id}/dashboard",
                headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["escola"]["n_turmas"] == 1
    # Sem envios → comparacao vazia
    assert body["comparacao_turmas"] == []
    return "dashboard escola com 1 turma: comparacao vazia ✓"


def test_dashboard_escola_403_outra_escola(_engine, world):
    """Coord de outra escola não pode ver dashboard da Escola A."""
    cli = _client()
    token, _ = encode_token(
        user_id=str(world.coord_id), papel="coordenador",
        escola_id=str(world.escola_id),
    )
    # Tenta acessar dashboard da escola_outra_id com token da escola A
    r = cli.get(f"/portal/escolas/{world.escola_outra_id}/dashboard",
                headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403
    return "dashboard escola: coord de outra escola → 403 ✓"


def test_evolucao_aluno_com_envios(_engine, world):
    cli = _client()
    r = cli.get(
        f"/portal/turmas/{world.turma_id}/alunos/{world.aluno1_id}/evolucao",
        headers=_bearer(world, "professor"),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["aluno"]["nome"] == "Ana Aluna"
    assert body["n_missoes_realizadas"] == 2
    assert len(body["evolucao_chart"]) == 2
    assert len(body["envios"]) == 2
    # Envios devem ter nomes humanizados de detectores (não códigos crus)
    nomes_detectores = []
    for e in body["envios"]:
        nomes_detectores.extend(e["detectores"])
    assert any("Proposta" in n for n in nomes_detectores), \
        f"esperava 'Proposta de intervenção vaga' nos detectores, got {nomes_detectores}"
    # Pelo menos uma missão pendente (Cíntia? não, é Ana). Ana tem
    # atividade pendente (atv_pendente)
    assert len(body["missoes_pendentes"]) >= 1
    return "evolução aluno com envios: chart + missões pendentes ✓"


def test_evolucao_aluno_sem_envios(_engine, world):
    cli = _client()
    r = cli.get(
        f"/portal/turmas/{world.turma_id}/alunos/{world.aluno_pendente_id}/evolucao",
        headers=_bearer(world, "professor"),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["n_missoes_realizadas"] == 0
    assert body["envios"] == []
    assert body["evolucao_chart"] == []
    # Cíntia tem 3 atividades pendentes (foco encerrada não conta)
    # foco está encerrada → não pendente. completo + pendente = 2.
    assert len(body["missoes_pendentes"]) == 2
    return "evolução aluno sem envios: lista vazia ✓"


def test_evolucao_aluno_403_outra_escola(_engine, world):
    cli = _client()
    token, _ = encode_token(
        user_id=str(world.prof_outro_id), papel="professor",
        escola_id=str(world.escola_id),
    )
    # Prof outro não é responsável pela turma de Ana
    r = cli.get(
        f"/portal/turmas/{world.turma_id}/alunos/{world.aluno1_id}/evolucao",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 403
    return "evolução aluno: prof errado → 403 ✓"


def test_detectores_canonical_humanizados(_engine, world):
    """O top_detectores devolve nome humano, não código cru."""
    cli = _client()
    r = cli.get(f"/portal/turmas/{world.turma_id}/dashboard",
                headers=_bearer(world, "professor"))
    body = r.json()
    nomes = [d["nome"] for d in body["top_detectores"]]
    assert "Proposta de intervenção vaga" in nomes, f"got {nomes}"
    assert "Repetição lexical" in nomes
    return "detectores canônicos humanizados no top ✓"


# ──────────────────────────────────────────────────────────────────────
# Runner
# ──────────────────────────────────────────────────────────────────────

TESTS = [
    test_dashboard_turma_estrutura,
    test_dashboard_turma_vazia,
    test_dashboard_escola_403_pra_professor,
    test_dashboard_escola_coord_2_turmas,
    test_dashboard_escola_1_turma_comparacao_vazia,
    test_dashboard_escola_403_outra_escola,
    test_evolucao_aluno_com_envios,
    test_evolucao_aluno_sem_envios,
    test_evolucao_aluno_403_outra_escola,
    test_detectores_canonical_humanizados,
]


def main():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("ERRO: DATABASE_URL não configurada")
        sys.exit(1)
    print(f"DATABASE_URL: {db_url}")
    print(f"Test schema : {TEST_SCHEMA}\n")

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
