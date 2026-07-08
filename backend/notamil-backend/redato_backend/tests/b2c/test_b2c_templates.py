"""Templates WhatsApp — fonte de verdade + cross-check posicional.

Garante que o builder de ContentVariables monta as variáveis na ordem
declarada, e que os call-sites (webhook M5/M8, tick M9) preenchem as
variáveis certas — mata o bug "variável na posição errada" que só se
manifestaria em produção fora da janela de 24h.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from redato_backend.b2c import templates as T
from redato_backend.b2c import notify


# ── Fonte de verdade: {{N}} no corpo == ordem declarada em vars ─────────

@pytest.mark.parametrize("key", list(T.TEMPLATES))
def test_corpo_bate_com_vars(key):
    spec = T.TEMPLATES[key]
    idx = T.indices_no_corpo(spec["body"])
    assert idx == list(range(1, len(spec["vars"]) + 1)), (
        f"{key}: {{{{N}}}} no corpo {idx} não bate com {len(spec['vars'])} vars"
    )


def test_M5_tem_2_vars_M8_M9_tem_3():
    assert T.TEMPLATES["M5"]["vars"] == ["nome", "nome_publico"]
    assert T.TEMPLATES["M8"]["vars"] == ["nome", "nome_publico", "link_fatura"]
    assert T.TEMPLATES["M9"]["vars"] == ["nome", "nome_publico", "link_fatura"]


def test_nomes_meta_dos_templates():
    assert T.TEMPLATES["M5"]["nome_meta"] == "redato_m5_assinatura_ativa"
    assert T.TEMPLATES["M8"]["nome_meta"] == "redato_m8_renovacao_falhou"
    assert T.TEMPLATES["M9"]["nome_meta"] == "redato_m9_acesso_vence"


# ── build_content_variables: ordem vem da spec, não do caller ───────────

def test_build_content_variables_ordem_da_spec():
    cv = T.build_content_variables("M9", {
        "link_fatura": "https://x", "nome": "Maria", "nome_publico": "Correção Luma",
    })
    # posição 2 é nome_publico mesmo o dict vindo desordenado
    assert cv == {"1": "Maria", "2": "Correção Luma", "3": "https://x"}


def test_build_content_variables_var_faltando_estoura():
    with pytest.raises(KeyError):
        T.build_content_variables("M8", {"nome": "Maria"})  # faltam 2


# ── Wiring real: o call-site preenche a variável certa ──────────────────

class _SpySender:
    def __init__(self):
        self.templates = []
        self.freeforms = []

    def freeform(self, phone, texto):
        self.freeforms.append((phone, texto))

    def template(self, phone, content_sid, content_variables):
        self.templates.append((phone, content_sid, content_variables))


def _spy(monkeypatch):
    spy = _SpySender()
    monkeypatch.setattr(notify, "TwilioSender", lambda: spy)
    return spy


def test_tick_M9_preenche_nome_publico_nao_vazio(store, monkeypatch):
    """Regressão do bug traiçoeiro: M9 posição 2 = nome_publico, NÃO ''."""
    from redato_backend.billing.webhook import processar_webhook
    from redato_backend.b2c.tick import rodar_tick
    monkeypatch.setenv("TWILIO_CONTENT_SID_M9", "HXm9")
    spy = _spy(monkeypatch)

    p = store.add_parceiro(nome_publico="Correção Luma", preco_centavos=3990,
                           wallet_id_asaas="w", share_pct=30)
    velho = datetime(2026, 1, 1, tzinfo=timezone.utc)
    a = store.add_aluno("+5511777", p.id, estado="ativo", nome="Maria Silva",
                        ultima_inbound_at=velho)
    store.upsert_assinatura(a.id, valor_centavos=3990,
                            asaas_subscription_id="sub_x", status="pendente")
    processar_webhook({"id": "o1", "event": "PAYMENT_OVERDUE",
                       "payment": {"id": "p1", "subscription": "sub_x"}},
                      notificar=lambda *_: None)
    od = store.get_assinatura_por_aluno(a.id).overdue_desde

    rodar_tick(agora=od + timedelta(days=3))  # produção → template
    assert spy.templates, "M9 não foi via template"
    _, sid, cv = spy.templates[0]
    assert sid == "HXm9"
    assert cv == {"1": "Maria", "2": "Correção Luma", "3": f"https://sandbox.asaas.com/i/sub_x"}


def test_webhook_M5_manda_exatamente_2_vars(store, monkeypatch):
    from redato_backend.billing.webhook import processar_webhook
    monkeypatch.setenv("TWILIO_CONTENT_SID_M5", "HXm5")
    spy = _spy(monkeypatch)

    p = store.add_parceiro(nome_publico="Correção Luma")
    velho = datetime(2026, 1, 1, tzinfo=timezone.utc)
    a = store.add_aluno("+5511777", p.id, estado="aguardando_pagamento",
                        nome="Maria Silva", ultima_inbound_at=velho)
    store.upsert_assinatura(a.id, valor_centavos=3990,
                            asaas_subscription_id="sub_x", status="pendente")
    processar_webhook({"id": "c1", "event": "PAYMENT_CONFIRMED",
                       "payment": {"id": "p1", "subscription": "sub_x"}},
                      notificar=None)
    assert spy.templates, "M5 não foi via template"
    _, sid, cv = spy.templates[0]
    assert sid == "HXm5"
    assert set(cv) == {"1", "2"}                       # 2 vars, não 3
    assert cv == {"1": "Maria", "2": "Correção Luma"}
