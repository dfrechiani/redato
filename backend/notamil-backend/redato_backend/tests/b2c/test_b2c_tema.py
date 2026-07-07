"""Fluxo do tema (ADENDO §D7) + LGPD versionado + bloqueio de inadimplente.
Critérios de aceite 11–15, 18, 19, 22, 23.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from redato_backend.b2c.router import maybe_route_b2c
from redato_backend.b2c import correction as C


def _msg(phone="+5511777", text=None, image_path=None):
    from redato_backend.whatsapp.bot import InboundMessage
    return InboundMessage(phone=phone, text=text, image_path=image_path)


@pytest.fixture
def cap_tema(monkeypatch):
    """OCR ok + captura o tema efetivamente passado ao grader."""
    capturado = {}

    class _Ocr:
        text = "Redação de teste com conteúdo suficiente pra corrigir."
        rejected = False
        quality_issues = []

    monkeypatch.setattr(C, "transcrever", lambda p: _Ocr())

    def _corr(texto, *, tema=None, grader=None):
        capturado["tema"] = tema
        capturado["texto"] = texto
        return C.ResultadoCorrecao(
            nota_total=880, notas={"c1": 200, "c2": 120, "c3": 160, "c4": 200, "c5": 160},
            ponto_forte="tese clara", foco_melhoria="repertório na C2", raw={},
        )

    monkeypatch.setattr(C, "corrigir_texto", _corr)
    return capturado


# ── 11: foto + legenda ≥15 → corrige; tema no grader ────────────────────

def test_foto_legenda_corrige_e_tema_no_grader(store, b2c_on, sem_b2g, cap_tema):
    p = store.add_parceiro()
    store.add_aluno("+5511777", p.id, estado="ativo", nome="Ana")
    tema = "Impactos das mudanças climáticas no semiárido brasileiro"
    replies = maybe_route_b2c(_msg(text=tema, image_path="/tmp/f.jpg"))
    assert cap_tema["tema"] == tema             # mesmo campo que o B2G usa
    assert "📝 Tema:" in replies[0].text and tema in replies[0].text


# ── 12: foto sem legenda → M16 → texto vira tema ────────────────────────

def test_foto_sem_legenda_pede_e_resolve(store, b2c_on, sem_b2g, cap_tema):
    p = store.add_parceiro()
    a = store.add_aluno("+5511777", p.id, estado="ativo", nome="Ana")
    r1 = maybe_route_b2c(_msg(image_path="/tmp/f.jpg"))
    assert "tema" in r1[0].text.lower()          # M16
    assert store.get_envio_pendente(a.id) is not None
    tema = "A importância da ampliação da vacinação no Brasil"
    r2 = maybe_route_b2c(_msg(text=tema))
    assert cap_tema["tema"] == tema
    assert "📝 Tema:" in r2[0].text
    assert store.get_envio_pendente(a.id) is None  # pendência resolvida


# ── 13: legenda 1–14 → M16b; SIM usa caption; texto diferente vira tema ──

def test_legenda_curta_M16b_sim_usa_caption(store, b2c_on, sem_b2g, cap_tema):
    p = store.add_parceiro()
    store.add_aluno("+5511777", p.id, estado="ativo", nome="Ana")
    r1 = maybe_route_b2c(_msg(text="clima", image_path="/tmp/f.jpg"))
    assert "clima" in r1[0].text                 # M16b
    maybe_route_b2c(_msg(text="SIM"))
    assert cap_tema["tema"] == "clima"


def test_legenda_curta_texto_diferente_vira_tema(store, b2c_on, sem_b2g, cap_tema):
    p = store.add_parceiro()
    store.add_aluno("+5511777", p.id, estado="ativo", nome="Ana")
    maybe_route_b2c(_msg(text="clima", image_path="/tmp/f.jpg"))
    tema = "Desmatamento na Amazônia e as políticas públicas atuais"
    maybe_route_b2c(_msg(text=tema))
    assert cap_tema["tema"] == tema


# ── 14: tema sorteado <48h + foto sem legenda → M16a; SIM usa sorteado ───

def test_tema_sorteado_recente_M16a_sim(store, b2c_on, sem_b2g, cap_tema):
    p = store.add_parceiro()
    store.add_aluno("+5511777", p.id, estado="ativo", nome="Ana",
                    ultimo_tema_sorteado="O papel das juventudes na política",
                    ultimo_tema_sorteado_at=datetime.now(timezone.utc))
    r1 = maybe_route_b2c(_msg(image_path="/tmp/f.jpg"))
    assert "juventudes" in r1[0].text            # M16a
    maybe_route_b2c(_msg(text="SIM"))
    assert cap_tema["tema"] == "O papel das juventudes na política"


# ── 15: comando durante pendência → executa e MANTÉM a pendência ────────

def test_comando_durante_pendencia_mantem(store, b2c_on, sem_b2g, cap_tema):
    p = store.add_parceiro()
    a = store.add_aluno("+5511777", p.id, estado="ativo", nome="Ana")
    maybe_route_b2c(_msg(image_path="/tmp/f.jpg"))   # cria pendente + M16
    assert store.get_envio_pendente(a.id) is not None
    r = maybe_route_b2c(_msg(text="ajuda"))
    assert "Comandos" in r[0].text                   # M13
    assert store.get_envio_pendente(a.id) is not None  # pendência intacta
    assert "tema" not in cap_tema                     # não corrigiu


def test_anti_loop_M17_aceita_segunda_curta(store, b2c_on, sem_b2g, cap_tema):
    p = store.add_parceiro()
    store.add_aluno("+5511777", p.id, estado="ativo", nome="Ana")
    maybe_route_b2c(_msg(image_path="/tmp/f.jpg"))    # M16 (pendente tema=None)
    r1 = maybe_route_b2c(_msg(text="ok"))             # curto sem atalho → M17
    assert "enunciado" in r1[0].text.lower()
    maybe_route_b2c(_msg(text="ok"))                  # 2ª curta → vira tema
    assert cap_tema["tema"] == "ok"


# ── 18: M6 sem bloco de evolução quando <2 corrigidos ───────────────────

def test_M6_sem_evolucao_no_primeiro(store, b2c_on, sem_b2g, cap_tema):
    p = store.add_parceiro()
    store.add_aluno("+5511777", p.id, estado="ativo", nome="Ana")
    tema = "A ética no uso de dados pessoais pelas plataformas"
    r = maybe_route_b2c(_msg(text=tema, image_path="/tmp/f.jpg"))
    assert "evolução" not in r[0].text.lower()        # 1º corrigido → sem evolução


# ── 19: nenhuma copy contém ** (negrito é asterisco simples) ────────────

def test_nenhuma_copy_tem_asterisco_duplo():
    from redato_backend.b2c import messages as M
    for k, v in vars(M).items():
        if k.isupper() and isinstance(v, str):
            assert "**" not in v, f"{k} contém ** (negrito WhatsApp é * simples)"


# ── 22: aceite LGPD grava consent_version ───────────────────────────────

def test_consent_version_gravada_no_aceite(store, b2c_on, sem_b2g):
    from redato_backend.b2c import config
    p = store.add_parceiro()
    store.add_aluno("+5511777", p.id, estado="aguardando_nome")
    maybe_route_b2c(_msg(text="Ana Souza"))
    a = store.get_aluno_por_telefone("+5511777")
    assert a.consent_version == config.CONSENT_VERSION
    assert a.consent_lgpd_at is not None


# ── 23: foto de inadimplente → bloqueado SEM OCR/grader ─────────────────

def test_inadimplente_bloqueia_sem_ocr_nem_grader(store, b2c_on, sem_b2g, monkeypatch):
    chamou = {"ocr": 0, "grader": 0}
    monkeypatch.setattr(C, "transcrever",
                        lambda p: chamou.__setitem__("ocr", chamou["ocr"] + 1))
    monkeypatch.setattr(C, "corrigir_texto",
                        lambda *a, **k: chamou.__setitem__("grader", chamou["grader"] + 1))
    p = store.add_parceiro()
    a = store.add_aluno("+5511777", p.id, estado="inadimplente", nome="Ana")
    store.upsert_assinatura(a.id, valor_centavos=3990,
                            asaas_subscription_id="sub_1", status="atrasada")
    r = maybe_route_b2c(_msg(image_path="/tmp/f.jpg"))
    assert "regulariza" in r[0].text.lower()          # M10
    assert chamou == {"ocr": 0, "grader": 0}          # não chamou OCR nem grader
    bloq = [e for e in store.envios if e["aluno_id"] == a.id and e.get("status") == "bloqueado"]
    assert len(bloq) == 1
    assert store.contar_fotos_bloqueadas(p.id) == 1
