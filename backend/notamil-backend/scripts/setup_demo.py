#!/usr/bin/env python3
"""Setup do ambiente local de demo end-to-end.

Roda do zero contra Postgres rodando + DATABASE_URL configurada:

1. `alembic upgrade head` — aplica migrations M1-M8.
2. `seed_missoes` — popula 5 missões REJ 1S.
3. Importa `data/seeds/planilha_demo.csv` (1 escola, 1 coord, 1 prof,
   2 turmas).
4. Define senhas dos usuários DIRETO no DB (bypass do email de
   primeiro acesso) — só pra dev local.
5. Cria 3 alunos sintéticos em cada turma + 1 atividade ativa
   (RJ1·OF10·MF) na turma 1A.
6. Cria 2 envios com nota sintética pra que o dashboard tenha dados
   visíveis sem precisar passar por OCR/Claude.
7. Imprime URLs do portal, credenciais e código da turma.

Idempotente: rodar 2× não duplica. Se quer "do zero limpinho", limpe
o banco antes (`DROP DATABASE redato_portal_dev; CREATE DATABASE
redato_portal_dev;`).

Uso:
    cd backend/notamil-backend
    python scripts/setup_demo.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path


BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

# Carrega .env
_env = BACKEND / ".env"
if _env.exists():
    for line in _env.read_text().splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip()
            if not os.environ.get(k):
                os.environ[k] = v

# Defaults pra dev local
os.environ.setdefault(
    "JWT_SECRET_KEY",
    "demo_local_secret_64_chars_long_only_for_dev_NOT_for_production_ok",
)
os.environ.setdefault("ADMIN_TOKEN", "demo-admin-token")
os.environ.setdefault("PORTAL_URL", "http://localhost:3010")

if not os.environ.get("DATABASE_URL"):
    print("ERRO: DATABASE_URL não setada.")
    print("Sugestão: export DATABASE_URL=postgresql://"
          f"{os.environ.get('USER', 'user')}@localhost:5432/redato_portal_dev")
    sys.exit(1)

# Senha dos usuários demo (bypass do fluxo de email)
SENHA_DEMO = "demo123"


def banner(msg: str) -> None:
    print(f"\n{'─' * 70}")
    print(f"  {msg}")
    print(f"{'─' * 70}")


def run(cmd: list[str], **kw) -> None:
    print(f"$ {' '.join(cmd)}")
    subprocess.run(cmd, check=True, cwd=BACKEND, **kw)


def _ensure_env_var(key: str, value: str) -> None:
    """Garante que `.env` do backend tem `key=value`. Atualiza se diferente.

    Necessário porque `dev_offline.apply_patches()` chama
    `load_dotenv(override=True)` no bot — env do subprocess seria
    sobrescrito. Forçar via .env é o caminho confiável.
    """
    env_path = BACKEND / ".env"
    if not env_path.exists():
        env_path.write_text(f"{key}={value}\n")
        os.environ[key] = value
        return
    lines = env_path.read_text().splitlines()
    found = False
    new_lines = []
    for line in lines:
        if "=" in line and not line.strip().startswith("#"):
            k = line.split("=", 1)[0].strip()
            if k == key:
                new_lines.append(f"{key}={value}")
                found = True
                continue
        new_lines.append(line)
    if not found:
        new_lines.append(f"{key}={value}")
    env_path.write_text("\n".join(new_lines) + "\n")
    os.environ[key] = value


def main() -> None:
    banner("0/6 · Garantindo .env tem flags de dev local")
    # Sem essas flags, o bot exige assinatura HMAC do Twilio (403 em curl).
    _ensure_env_var("TWILIO_VALIDATE_SIGNATURE", "0")
    _ensure_env_var("REDATO_DEV_OFFLINE", "1")
    print("  TWILIO_VALIDATE_SIGNATURE=0  (curl direto no webhook)")
    print("  REDATO_DEV_OFFLINE=1          (stub do Claude e Twilio send)")

    banner("1/6 · Aplicando migrations Alembic")
    # cd na pasta do alembic.ini (portal/)
    portal = BACKEND / "redato_backend" / "portal"
    subprocess.run(
        ["alembic", "upgrade", "head"],
        check=True, cwd=portal,
    )

    banner("2/6 · Seed das 5 missões REJ 1S")
    run(["python", "-m", "redato_backend.portal.seed_missoes"])

    banner("3/6 · Importando planilha demo (1 escola, 1 coord, 1 prof, 2 turmas)")
    csv_path = BACKEND / "data" / "seeds" / "planilha_demo.csv"
    if not csv_path.exists():
        print(f"ERRO: planilha não encontrada em {csv_path}")
        sys.exit(1)
    run([
        "python", "-m", "redato_backend.portal.import_planilha",
        str(csv_path), "--commit",
    ])

    # Os passos seguintes precisam de imports do app (após DB pronto)
    from sqlalchemy import select
    from sqlalchemy.orm import Session

    from redato_backend.portal.auth.password import hash_senha
    from redato_backend.portal.db import get_engine
    from redato_backend.portal.models import (
        AlunoTurma, Atividade, Coordenador, Envio, Escola, Interaction,
        Missao, Professor, Turma,
    )

    engine = get_engine()
    with Session(engine) as session:
        banner("4/6 · Definindo senhas dos usuários demo (bypass email)")
        senha_hash = hash_senha(SENHA_DEMO)

        coord = session.execute(
            select(Coordenador).where(
                Coordenador.email == "coord@demo.redato",
            )
        ).scalar_one_or_none()
        if coord is None:
            print("ERRO: coordenador não encontrado após import.")
            sys.exit(1)
        coord.senha_hash = senha_hash
        coord.primeiro_acesso_token = None
        coord.primeiro_acesso_expira_em = None

        prof = session.execute(
            select(Professor).where(
                Professor.email == "prof@demo.redato",
            )
        ).scalar_one_or_none()
        if prof is None:
            print("ERRO: professor não encontrado após import.")
            sys.exit(1)
        prof.senha_hash = senha_hash
        prof.primeiro_acesso_token = None
        prof.primeiro_acesso_expira_em = None

        session.commit()
        print(f"  Coordenador: {coord.email}")
        print(f"  Professor  : {prof.email}")

        banner("5/6 · Criando alunos sintéticos + atividade ativa")
        turmas = session.execute(
            select(Turma).where(
                Turma.escola_id == coord.escola_id,
                Turma.deleted_at.is_(None),
            ).order_by(Turma.codigo)
        ).scalars().all()
        if not turmas:
            print("ERRO: nenhuma turma encontrada após import.")
            sys.exit(1)

        # Cria 3 alunos por turma — usa upsert por (turma, telefone)
        alunos_por_turma: dict[uuid.UUID, list[AlunoTurma]] = {}
        for turma in turmas:
            # Sem filtro de `ativo` — UNIQUE(turma_id, telefone)
            # bloqueia INSERT mesmo de aluno inativado por re-run.
            existentes = session.execute(
                select(AlunoTurma).where(
                    AlunoTurma.turma_id == turma.id,
                )
            ).scalars().all()
            ja_telefones = {a.telefone for a in existentes}
            sintéticos = [
                ("Ana Aluna Demo", "+5511900001111"),
                ("Bruno Aluno Demo", "+5511900002222"),
                ("Carla Aluna Demo", "+5511900003333"),
            ]
            criados: list[AlunoTurma] = list(existentes)
            for nome, tel in sintéticos:
                if tel in ja_telefones:
                    continue
                a = AlunoTurma(
                    turma_id=turma.id, nome=nome, telefone=tel,
                )
                session.add(a)
                session.flush()
                criados.append(a)
            alunos_por_turma[turma.id] = criados
            print(f"  Turma {turma.codigo}: {len(criados)} alunos "
                  f"({turma.codigo_join})")

        # Atividade ativa: RJ1·OF10·MF (Foco C3) na turma_a, dura 7 dias
        missao_c3 = session.execute(
            select(Missao).where(Missao.codigo == "RJ1·OF10·MF")
        ).scalar_one()
        agora = datetime.now(timezone.utc)
        turma_a = turmas[0]

        existing_ativ = session.execute(
            select(Atividade).where(
                Atividade.turma_id == turma_a.id,
                Atividade.missao_id == missao_c3.id,
                Atividade.deleted_at.is_(None),
            )
        ).scalar_one_or_none()
        if existing_ativ is None:
            ativ = Atividade(
                turma_id=turma_a.id, missao_id=missao_c3.id,
                data_inicio=agora - timedelta(hours=1),
                data_fim=agora + timedelta(days=7),
                criada_por_professor_id=prof.id,
            )
            session.add(ativ)
            session.flush()
        else:
            ativ = existing_ativ
            # Estende prazo se já estava encerrada
            ativ.data_fim = agora + timedelta(days=7)
        session.commit()
        print(f"  Atividade ativa: {missao_c3.codigo} em {turma_a.codigo} "
              f"até {ativ.data_fim.strftime('%d/%m')}")

        # Envios sintéticos: Ana com 160 ("Bom" em foco_c3),
        # Bruno com 60 ("Insuficiente"). Modo da missão é foco_c3 →
        # escala 0-200 (1 competência só). Notas em 0-1000 cairiam
        # todas no último bucket por clamp implícito de _bucket_foco.
        alunos = alunos_por_turma[turma_a.id]
        if alunos:
            ana = next((a for a in alunos if "Ana" in a.nome), None)
            bruno = next((a for a in alunos if "Bruno" in a.nome), None)
            # Transcrições sintéticas (curtas) — só pra demo. Em produção,
            # vem do OCR real (interaction.texto_transcrito).
            transcricao_demo = {
                160: (
                    "A questão do uso consciente da água no Brasil tem se "
                    "tornado cada vez mais relevante diante das mudanças "
                    "climáticas. Considerando o cenário atual, é "
                    "fundamental que medidas sejam tomadas para garantir "
                    "o acesso a esse recurso essencial.\n\n"
                    "Em primeiro lugar, deve-se observar que a escassez "
                    "hídrica afeta principalmente as populações de baixa "
                    "renda, evidenciando a desigualdade social. Em segundo "
                    "lugar, políticas públicas voltadas à conscientização "
                    "podem mudar comportamentos individuais.\n\n"
                    "Portanto, é necessário que o governo, em parceria "
                    "com a sociedade civil, promova campanhas educativas "
                    "e invista em infraestrutura. Apenas assim teremos "
                    "um futuro sustentável para as próximas gerações."
                ),
                60: (
                    "A água é muito importante. Todo mundo precisa de "
                    "água. Sem água a gente morre. O brasil tem muita "
                    "água mais ainda assim falta agua em alguns lugares.\n\n"
                    "As pessoas devem economizar agua. Tomar banho rapido "
                    "e fechar a torneira. O governo tem que fazer alguma "
                    "coisa pra ajudar."
                ),
            }
            for aluno, nota in [(ana, 160), (bruno, 60)]:
                if aluno is None:
                    continue
                ja = session.execute(
                    select(Envio).where(
                        Envio.atividade_id == ativ.id,
                        Envio.aluno_turma_id == aluno.id,
                    )
                ).scalar_one_or_none()
                if ja is not None:
                    continue
                # Em foco_c3, "nota" se refere à C3 (range 0-200).
                # Demais competências derivadas pra coerência interna,
                # mas o dashboard só lê nota_total + flags.
                interaction = Interaction(
                    aluno_phone=aluno.telefone,
                    aluno_turma_id=aluno.id, envio_id=None,
                    source="whatsapp_portal",
                    missao_id=missao_c3.codigo,
                    activity_id=str(uuid.uuid4()),
                    texto_transcrito=transcricao_demo[nota],
                    redato_output=json.dumps({
                        "nota_total": nota,
                        "C1": {"nota": min(nota, 200)},
                        "C2": {"nota": min(nota, 200)},
                        "C3": {"nota": min(nota, 200)},
                        "C4": {"nota": min(nota, 200)},
                        "C5": {"nota": min(nota, 200)},
                        "transcricao": transcricao_demo[nota],
                        "audit_pedagogico": (
                            f"Demo: aluno tirou {nota}/200 em C3."
                        ),
                        "flag_proposta_vaga": nota < 100,
                        "flag_repeticao_lexical": True,
                    }, ensure_ascii=False),
                    ocr_quality_issues="[]",
                )
                session.add(interaction)
                session.flush()
                envio = Envio(
                    atividade_id=ativ.id,
                    aluno_turma_id=aluno.id,
                    interaction_id=interaction.id,
                    enviado_em=agora - timedelta(hours=2),
                )
                session.add(envio)
                session.flush()
                interaction.envio_id = envio.id
            session.commit()
            print("  Envios sintéticos: Ana 160 (Bom), Bruno 60 (Insuficiente) — escala foco_c3 0-200")

        # Captura tudo pra imprimir no relatório
        coord_email = coord.email
        prof_email = prof.email
        escola_nome = session.get(Escola, coord.escola_id).nome
        turmas_info = [
            (t.codigo, t.codigo_join, t.id) for t in turmas
        ]

    # ────────────────────────────────────────────────────────────────
    banner("6/6 · Pronto. URLs e credenciais")
    print(f"""
Frontend (Next.js):       http://localhost:3010
Backend portal (FastAPI): http://localhost:8091
Bot WhatsApp (sandbox):   http://localhost:8090
Health full:              http://localhost:8091/admin/health/full

Credenciais (senha = '{SENHA_DEMO}'):
  Professora:   {prof_email}     → vê só turmas dela
  Coordenadora: {coord_email}    → vê escola toda + dashboard agregado

Escola:  {escola_nome}
Turmas:""")
    for codigo, codigo_join, _id in turmas_info:
        print(f"  {codigo}: código de cadastro de aluno = {codigo_join}")

    print(f"""
Pra simular fluxo do aluno (sem Twilio real), veja
redato_backend/portal/RUN_LOCAL.md seção "Simular bot via curl".

ADMIN_TOKEN (pra cron de triggers e admin endpoints): {os.environ['ADMIN_TOKEN']}
""")


if __name__ == "__main__":
    main()
