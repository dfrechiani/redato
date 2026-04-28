"""Serviço de email transacional pro portal (M2).

SendGrid via REST API v3 (sem SDK) quando `SENDGRID_API_KEY` setada.
Sem a key, modo "dry-run de email" — registra o que seria enviado em
`data/portal/emails_pendentes.jsonl` pra inspeção.

Templates HTML em `email_templates/`. Variáveis substituídas via
str.format simples (não usa Jinja2 pra evitar dep extra).
"""
from __future__ import annotations

import json
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, List, Optional

import requests
from sqlalchemy import select
from sqlalchemy.orm import Session

from redato_backend.portal.models import Coordenador, Professor


_BACKEND = Path(__file__).resolve().parents[2]
_TEMPLATES_DIR = Path(__file__).parent / "email_templates"
_PENDING_LOG = _BACKEND / "data" / "portal" / "emails_pendentes.jsonl"

PRIMEIRO_ACESSO_VALID_DAYS = 7
PORTAL_URL_DEFAULT = "https://portal.redato.app"


@dataclass
class EmailEnvelope:
    """Tudo que precisa pra enviar 1 email."""
    to_email: str
    to_name: str
    subject: str
    html: str
    text_fallback: str

    def to_dict(self) -> dict:
        return {
            "to_email": self.to_email, "to_name": self.to_name,
            "subject": self.subject, "html": self.html,
            "text_fallback": self.text_fallback,
        }


@dataclass
class SendResult:
    enviados: int = 0
    falhados: int = 0
    ja_tinham_senha: int = 0
    erros: List[str] = None  # type: ignore[assignment]

    def __post_init__(self):
        if self.erros is None:
            self.erros = []

    def to_dict(self) -> dict:
        return {
            "enviados": self.enviados, "falhados": self.falhados,
            "ja_tinham_senha": self.ja_tinham_senha, "erros": self.erros,
        }


# ──────────────────────────────────────────────────────────────────────
# Token + URL
# ──────────────────────────────────────────────────────────────────────

def _gerar_token() -> str:
    """32 bytes hex = 64 chars. Caber em VARCHAR(64) do schema."""
    return secrets.token_hex(32)


def _expira_em() -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=PRIMEIRO_ACESSO_VALID_DAYS)


def _portal_url() -> str:
    return os.getenv("PORTAL_URL", PORTAL_URL_DEFAULT).rstrip("/")


# ──────────────────────────────────────────────────────────────────────
# Templates
# ──────────────────────────────────────────────────────────────────────

def _load_template(name: str) -> str:
    path = _TEMPLATES_DIR / name
    return path.read_text(encoding="utf-8")


def _render(template: str, **vars: str) -> str:
    """Substituição simples {var}. Variáveis ausentes ficam literais."""
    out = template
    for k, v in vars.items():
        out = out.replace("{" + k + "}", str(v))
    return out


def _envelope_coordenador(coord: Coordenador, token: str) -> EmailEnvelope:
    portal = _portal_url()
    link = f"{portal}/primeiro-acesso?token={token}"
    primeiro_nome = (coord.nome or "").split()[0] or coord.nome or "coordenador"
    html = _render(
        _load_template("welcome_coordenador.html"),
        nome=coord.nome or "", primeiro_nome=primeiro_nome, link=link,
        validade_dias=str(PRIMEIRO_ACESSO_VALID_DAYS),
    )
    text = (
        f"Olá, {primeiro_nome},\n\n"
        f"Você foi cadastrado como coordenador no portal Redato. "
        f"Pra acessar pela primeira vez, abra:\n\n{link}\n\n"
        f"O link vale por {PRIMEIRO_ACESSO_VALID_DAYS} dias.\n\n"
        f"Equipe Redato"
    )
    return EmailEnvelope(
        to_email=coord.email, to_name=coord.nome or "",
        subject="Acesso ao portal Redato — primeiro login",
        html=html, text_fallback=text,
    )


def _envelope_professor(prof: Professor, token: str) -> EmailEnvelope:
    portal = _portal_url()
    link = f"{portal}/primeiro-acesso?token={token}"
    primeiro_nome = (prof.nome or "").split()[0] or prof.nome or "professor"
    html = _render(
        _load_template("welcome_professor.html"),
        nome=prof.nome or "", primeiro_nome=primeiro_nome, link=link,
        validade_dias=str(PRIMEIRO_ACESSO_VALID_DAYS),
    )
    text = (
        f"Olá, {primeiro_nome},\n\n"
        f"Você foi cadastrado como professor no portal Redato. "
        f"Pra acessar pela primeira vez, abra:\n\n{link}\n\n"
        f"O link vale por {PRIMEIRO_ACESSO_VALID_DAYS} dias.\n\n"
        f"Equipe Redato"
    )
    return EmailEnvelope(
        to_email=prof.email, to_name=prof.nome or "",
        subject="Acesso ao portal Redato — primeiro login",
        html=html, text_fallback=text,
    )


# ──────────────────────────────────────────────────────────────────────
# Envio (SendGrid v3 ou dry-run jsonl)
# ──────────────────────────────────────────────────────────────────────

def _send_via_sendgrid(env: EmailEnvelope) -> tuple[bool, str]:
    """Retorna (ok, msg). Sem SDK — usa requests direto."""
    api_key = os.getenv("SENDGRID_API_KEY")
    if not api_key:
        return False, "SENDGRID_API_KEY ausente"
    from_email = os.getenv("SENDGRID_FROM_EMAIL", "noreply@redato.app")
    from_name = os.getenv("SENDGRID_FROM_NAME", "Redato")
    payload = {
        "personalizations": [{
            "to": [{"email": env.to_email, "name": env.to_name}],
            "subject": env.subject,
        }],
        "from": {"email": from_email, "name": from_name},
        "content": [
            {"type": "text/plain", "value": env.text_fallback},
            {"type": "text/html", "value": env.html},
        ],
    }
    try:
        resp = requests.post(
            "https://api.sendgrid.com/v3/mail/send",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload, timeout=15,
        )
        if 200 <= resp.status_code < 300:
            return True, f"SendGrid {resp.status_code}"
        return False, f"SendGrid {resp.status_code}: {resp.text[:200]}"
    except Exception as exc:  # noqa: BLE001
        return False, f"SendGrid exception: {type(exc).__name__}: {exc}"


def _log_pending(env: EmailEnvelope) -> None:
    """Modo dry-run: append no jsonl pra inspeção offline."""
    _PENDING_LOG.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        **env.to_dict(),
    }
    with _PENDING_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _send(env: EmailEnvelope) -> tuple[bool, str]:
    """Despacha pra SendGrid se key disponível, senão dry-run jsonl."""
    if os.getenv("SENDGRID_API_KEY"):
        return _send_via_sendgrid(env)
    _log_pending(env)
    return True, "dry-run (logged in emails_pendentes.jsonl)"


# ──────────────────────────────────────────────────────────────────────
# M8 — Emails transacionais formais
# ──────────────────────────────────────────────────────────────────────

_TIPO_LABELS = {
    "dashboard_turma": "Dashboard da turma",
    "dashboard_escola": "Dashboard da escola",
    "evolucao_aluno": "Evolução do aluno",
    "atividade_detalhe": "Detalhe da atividade",
}


def send_pdf_disponivel(
    *, to_email: str, to_name: str, pdf_id: str, pdf_tipo: str,
) -> tuple[bool, str]:
    """Notifica que um PDF está disponível pra download no portal.

    Por design, o email NÃO anexa o PDF — manda link pra abrir no
    portal autenticado. Mantém LGPD (PDF só baixado por user logado da
    mesma escola)."""
    portal = _portal_url()
    link = f"{portal}/api/portal/pdfs/{pdf_id}/download"
    primeiro_nome = (to_name or "").split()[0] or to_name or "professor"
    tipo_label = _TIPO_LABELS.get(pdf_tipo, pdf_tipo)
    try:
        tpl = _load_template("pdf_disponivel.html")
        html = _render(
            tpl, primeiro_nome=primeiro_nome, link=link, tipo_label=tipo_label,
        )
    except FileNotFoundError:
        html = (f"<p>Olá, {primeiro_nome}.</p>"
                f"<p>{tipo_label} disponível: "
                f"<a href='{link}'>{link}</a></p>")
    text = (
        f"Olá, {primeiro_nome}.\n\n"
        f"{tipo_label} pronto pra consulta no portal Redato:\n"
        f"{link}\n\n"
        f"Equipe Redato"
    )
    env = EmailEnvelope(
        to_email=to_email, to_name=to_name,
        subject=f"Redato — {tipo_label} pronto",
        html=html, text_fallback=text,
    )
    return _send(env)


def send_atividade_encerrada_pendentes(
    *, to_email: str, to_name: str,
    turma_codigo: str, missao_codigo: str, missao_titulo: str,
    atividade_id: str, n_pendentes: int,
    oficina_numero: Optional[int] = None,
    modo_correcao: Optional[str] = None,
) -> tuple[bool, str]:
    """Aviso ao professor: atividade encerrada com N alunos sem envio."""
    from redato_backend.portal.formatters import format_missao_label_humana

    portal = _portal_url()
    link = f"{portal}/atividade/{atividade_id}"
    primeiro_nome = (to_name or "").split()[0] or to_name or "professor"
    label_missao = format_missao_label_humana(
        oficina_numero=oficina_numero, titulo=missao_titulo,
        modo_correcao=modo_correcao,
    ) or missao_titulo or missao_codigo
    try:
        tpl = _load_template("atividade_encerrada.html")
        html = _render(
            tpl, primeiro_nome=primeiro_nome,
            turma_codigo=turma_codigo,
            missao_codigo=missao_codigo,        # mantido pra backcompat
            missao_titulo=missao_titulo,        # mantido pra backcompat
            missao_label=label_missao,          # novo
            n_pendentes=str(n_pendentes), link=link,
        )
    except FileNotFoundError:
        html = (f"<p>Olá, {primeiro_nome}.</p>"
                f"<p>Atividade {label_missao} ({turma_codigo}) "
                f"encerrada com {n_pendentes} pendente(s). "
                f"<a href='{link}'>Ver no portal</a></p>")
    text = (
        f"Olá, {primeiro_nome}.\n\n"
        f"A atividade {label_missao} da turma {turma_codigo} foi "
        f"encerrada. {n_pendentes} aluno(s) ficaram sem enviar "
        f"redação.\n\n"
        f"Veja no portal: {link}\n\n"
        f"Equipe Redato"
    )
    env = EmailEnvelope(
        to_email=to_email, to_name=to_name,
        subject=f"Redato — {label_missao} encerrada com {n_pendentes} pendente(s)",
        html=html, text_fallback=text,
    )
    return _send(env)


def send_alunos_em_risco_alert(
    *, to_email: str, to_name: str,
    turma_id: str, turma_codigo: str,
    alunos: List[dict],
) -> tuple[bool, str]:
    """Alerta semanal pro professor: alunos com 3+ missões insuficientes.

    `alunos` = lista de dicts com `nome` e `n_missoes_baixa`. Caller
    aplica rate limit (1× por semana) — esse send NÃO valida idem.
    """
    portal = _portal_url()
    link = f"{portal}/turma/{turma_id}"
    primeiro_nome = (to_name or "").split()[0] or to_name or "professor"
    lista_str = "\n".join(
        f"- {a['nome']} ({a['n_missoes_baixa']} missões abaixo)"
        for a in alunos
    )
    try:
        tpl = _load_template("alunos_risco.html")
        html = _render(
            tpl, primeiro_nome=primeiro_nome,
            n_alunos=str(len(alunos)),
            turma_codigo=turma_codigo,
            lista_alunos=lista_str, link=link,
        )
    except FileNotFoundError:
        html = (f"<p>Olá, {primeiro_nome}.</p>"
                f"<p>{len(alunos)} aluno(s) em risco na turma "
                f"{turma_codigo}.</p>"
                f"<pre>{lista_str}</pre>"
                f"<p><a href='{link}'>Ver no portal</a></p>")
    text = (
        f"Olá, {primeiro_nome}.\n\n"
        f"{len(alunos)} aluno(s) em risco na turma {turma_codigo}:\n\n"
        f"{lista_str}\n\n"
        f"Veja a evolução de cada um no portal: {link}\n\n"
        f"Equipe Redato"
    )
    env = EmailEnvelope(
        to_email=to_email, to_name=to_name,
        subject=f"Redato — {len(alunos)} aluno(s) em risco em {turma_codigo}",
        html=html, text_fallback=text,
    )
    return _send(env)


# ──────────────────────────────────────────────────────────────────────
# API pública
# ──────────────────────────────────────────────────────────────────────

def filter_pending_users(
    session: Session,
    *,
    escola_id: Optional[str] = None,
    coordenador_emails: Optional[Iterable[str]] = None,
    professor_emails: Optional[Iterable[str]] = None,
    only_no_password: bool = True,
) -> tuple[List[Coordenador], List[Professor]]:
    """Função compartilhada (M4 refactor). Aplica filtros idênticos aos
    usados em count + send pra evitar drift entre eles.

    `only_no_password=True` filtra users com `senha_hash IS NULL`
    (semântica de "ainda não fez primeiro acesso"). Quando False,
    inclui todos (usado quando `overwrite_existing_token`).
    """
    coord_set = (
        {e.lower() for e in coordenador_emails} if coordenador_emails else None
    )
    prof_set = (
        {e.lower() for e in professor_emails} if professor_emails else None
    )

    coord_query = select(Coordenador).where(Coordenador.ativo.is_(True))
    if escola_id is not None:
        coord_query = coord_query.where(Coordenador.escola_id == escola_id)
    if coord_set is not None:
        coord_query = coord_query.where(Coordenador.email.in_(coord_set))
    if only_no_password:
        coord_query = coord_query.where(Coordenador.senha_hash.is_(None))
    coords = list(session.execute(coord_query).scalars())

    prof_query = select(Professor).where(Professor.ativo.is_(True))
    if escola_id is not None:
        prof_query = prof_query.where(Professor.escola_id == escola_id)
    if prof_set is not None:
        prof_query = prof_query.where(Professor.email.in_(prof_set))
    if only_no_password:
        prof_query = prof_query.where(Professor.senha_hash.is_(None))
    profs = list(session.execute(prof_query).scalars())
    return coords, profs


def send_welcome_emails(
    session: Session,
    *,
    escola_id: Optional[str] = None,
    coordenador_emails: Optional[Iterable[str]] = None,
    professor_emails: Optional[Iterable[str]] = None,
    overwrite_existing_token: bool = False,
) -> SendResult:
    """Dispara emails de boas-vindas.

    Filtros (combinam com OR; se nenhum: TODOS sem senha):
    - `escola_id`: só usuários dessa escola.
    - `coordenador_emails`/`professor_emails`: lista específica.

    Pra cada usuário sem senha definida: gera token + envia. Se já tem
    senha (`senha_hash IS NOT NULL`) e `overwrite=False`, pula e
    incrementa `ja_tinham_senha`.
    """
    result = SendResult()

    # M4 refactor: count e send usam filter_pending_users compartilhado.
    # Pra `send`, precisamos saber `ja_tinham_senha`, então buscamos
    # TODOS (only_no_password=False) e contamos no loop.
    coords, profs = filter_pending_users(
        session,
        escola_id=escola_id,
        coordenador_emails=coordenador_emails,
        professor_emails=professor_emails,
        only_no_password=False,
    )

    for coord in coords:
        if coord.senha_hash and not overwrite_existing_token:
            result.ja_tinham_senha += 1
            continue
        coord.primeiro_acesso_token = _gerar_token()
        coord.primeiro_acesso_expira_em = _expira_em()
        envelope = _envelope_coordenador(coord, coord.primeiro_acesso_token)
        ok, msg = _send(envelope)
        if ok:
            result.enviados += 1
        else:
            result.falhados += 1
            result.erros.append(f"{coord.email}: {msg}")

    for prof in profs:
        if prof.senha_hash and not overwrite_existing_token:
            result.ja_tinham_senha += 1
            continue
        prof.primeiro_acesso_token = _gerar_token()
        prof.primeiro_acesso_expira_em = _expira_em()
        envelope = _envelope_professor(prof, prof.primeiro_acesso_token)
        ok, msg = _send(envelope)
        if ok:
            result.enviados += 1
        else:
            result.falhados += 1
            result.erros.append(f"{prof.email}: {msg}")

    session.commit()
    return result
