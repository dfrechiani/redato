"""Webhook Asaas + split (SPEC_B2C_REDATO.md §7 critérios 4, 5, 7).

Payloads no formato do sandbox Asaas. Sem rede: `repo` é o FakeStore,
notificações são capturadas numa lista.
"""
from __future__ import annotations

import pytest

from redato_backend.billing.webhook import processar_webhook, handle_asaas_event
from redato_backend.billing.asaas import build_subscription_payload


def _seed_assinante(store, *, estado="aguardando_pagamento", sub_id="sub_x"):
    p = store.add_parceiro(preco_centavos=3990, wallet_id_asaas="w_1",
                           share_pct=30)
    a = store.add_aluno("+5511777", p.id, estado=estado, nome="Maria Silva")
    store.upsert_assinatura(a.id, valor_centavos=3990,
                            asaas_customer_id="cus_x",
                            asaas_subscription_id=sub_id, status="pendente")
    return p, a


def _payload(event, sub_id="sub_x", event_id="evt_1"):
    return {
        "id": event_id,
        "event": event,
        "payment": {
            "id": "pay_1", "subscription": sub_id,
            "status": "CONFIRMED",
            "invoiceUrl": "https://sandbox.asaas.com/i/pay_1",
        },
    }


# ──────────────────────────────────────────────────────────────────────
# Critério 4 — PAYMENT_CONFIRMED ativa + M5; duplicado não reprocessa
# ──────────────────────────────────────────────────────────────────────

def test_payment_confirmed_ativa_e_manda_M5(store):
    p, a = _seed_assinante(store)
    enviados = []
    res = processar_webhook(
        _payload("PAYMENT_CONFIRMED"),
        notificar=lambda phone, textos: enviados.append((phone, textos)),
    )
    assert res["status"] == "ok"
    assert store.get_aluno_por_telefone("+5511777").estado == "ativo"
    assert store.get_assinatura_por_aluno(a.id).status == "ativa"
    assert enviados and "ativa" in enviados[0][1][0].lower()


def test_evento_duplicado_nao_reprocessa(store):
    p, a = _seed_assinante(store)
    enviados = []
    notif = lambda phone, textos: enviados.append((phone, textos))
    p1 = _payload("PAYMENT_CONFIRMED", event_id="evt_dup")
    r1 = processar_webhook(p1, notificar=notif)
    r2 = processar_webhook(p1, notificar=notif)  # mesmo id
    assert r1["status"] == "ok"
    assert r2["status"] == "duplicate"
    assert len(enviados) == 1                     # M5 mandado uma vez só


# ──────────────────────────────────────────────────────────────────────
# Critério 5 — OVERDUE régua M8/M9/M10; pagamento reativa
# ──────────────────────────────────────────────────────────────────────

def test_overdue_d0_manda_so_M8_e_inicia_regua(store):
    """§D8: webhook OVERDUE = D0 (M8) + inicia régua. NÃO escala sozinho."""
    p, a = _seed_assinante(store, estado="ativo")
    enviados = []
    processar_webhook(_payload("PAYMENT_OVERDUE", event_id="o1"),
                      notificar=lambda ph, tx: enviados.append(tx[0]))
    assert len(enviados) == 1 and "renovar" in enviados[0].lower()  # M8
    sub = store.get_assinatura_por_aluno(a.id)
    assert sub.status == "atrasada" and sub.regua_estagio == 1
    assert sub.overdue_desde is not None
    # aluno segue ativo (carência até D+5)
    assert store.get_aluno_por_telefone("+5511777").estado == "ativo"


def test_daily_tick_regua_M9_e_bloqueio_idempotente(store):
    from datetime import timedelta
    from redato_backend.b2c.tick import rodar_tick

    p, a = _seed_assinante(store, estado="ativo")
    processar_webhook(_payload("PAYMENT_OVERDUE", event_id="o1"),
                      notificar=lambda *_: None)
    od = store.get_assinatura_por_aluno(a.id).overdue_desde

    # D+3 → M9 (estágio 2)
    enviados = []
    notif = lambda ph, tx: enviados.append(tx[0])
    rodar_tick(agora=od + timedelta(days=3), notificar=notif)
    assert len(enviados) == 1 and "2 dias" in enviados[0]           # M9
    assert store.get_assinatura_por_aluno(a.id).regua_estagio == 2

    # rodar de novo no MESMO dia → não repete M9 (idempotente)
    rodar_tick(agora=od + timedelta(days=3), notificar=notif)
    assert len(enviados) == 1

    # D+5 → bloqueia (estágio 3, estado inadimplente); sem nova mensagem
    rodar_tick(agora=od + timedelta(days=5), notificar=notif)
    assert len(enviados) == 1
    assert store.get_assinatura_por_aluno(a.id).regua_estagio == 3
    assert store.get_aluno_por_telefone("+5511777").estado == "inadimplente"


def test_pagamento_apos_overdue_zera_regua_e_reativa(store):
    from datetime import timedelta
    from redato_backend.b2c.tick import rodar_tick

    p, a = _seed_assinante(store, estado="ativo")
    processar_webhook(_payload("PAYMENT_OVERDUE", event_id="o1"),
                      notificar=lambda *_: None)
    od = store.get_assinatura_por_aluno(a.id).overdue_desde
    rodar_tick(agora=od + timedelta(days=5), notificar=lambda *_: None)
    assert store.get_aluno_por_telefone("+5511777").estado == "inadimplente"

    enviados = []
    processar_webhook(_payload("PAYMENT_RECEIVED", event_id="pay_ok"),
                      notificar=lambda ph, tx: enviados.append(tx[0]))
    sub = store.get_assinatura_por_aluno(a.id)
    assert store.get_aluno_por_telefone("+5511777").estado == "ativo"
    assert sub.status == "ativa" and sub.regua_estagio == 0
    assert sub.overdue_desde is None
    assert "ativa" in enviados[0].lower()                          # M5


def test_evento_desconhecido_fica_pendente(store):
    """§D13: evento não reconhecido → processado=false + eventos_pendentes."""
    p, a = _seed_assinante(store, estado="ativo")
    res = processar_webhook(
        {"id": "evt_x", "event": "PAYMENT_ANTICIPATED",
         "payment": {"id": "pay_9", "subscription": "sub_x"}},
        notificar=lambda *_: None,
    )
    assert res["resultado"]["handled"] is False
    assert store.contar_eventos_pendentes(p.id) == 1


def test_tick_registra_envio_degradado_visivel(store, monkeypatch):
    """§D9 mitigação: M9 fora da janela sem Content SID → freeform
    degradado. A régua AVANÇA, mas o degradado vira número (contador +
    aparece no retorno do tick)."""
    from datetime import datetime, timedelta, timezone
    from redato_backend.b2c import notify
    from redato_backend.b2c.tick import rodar_tick

    monkeypatch.delenv("TWILIO_CONTENT_SID_M9", raising=False)
    tentou = []
    monkeypatch.setattr(notify.TwilioSender, "freeform",
                        lambda self, ph, tx: tentou.append((ph, tx)))

    p = store.add_parceiro(preco_centavos=3990, wallet_id_asaas="w", share_pct=30)
    velho = datetime(2026, 1, 1, tzinfo=timezone.utc)  # fora da janela 24h
    a = store.add_aluno("+5511777", p.id, estado="ativo", nome="Ana",
                        ultima_inbound_at=velho)
    store.upsert_assinatura(a.id, valor_centavos=3990,
                            asaas_subscription_id="sub_x", status="pendente")
    processar_webhook(_payload("PAYMENT_OVERDUE", event_id="o1"),
                      notificar=lambda *_: None)
    od = store.get_assinatura_por_aluno(a.id).overdue_desde

    # tick D+3 SEM override → notify real → freeform degradado.
    resultados = rodar_tick(agora=od + timedelta(days=3))
    m9 = [r for r in resultados if r["acao"] == "M9"]
    assert m9 and m9[0]["degradado"] is True             # aparece no retorno
    assert store.contar_notificacoes_degradadas(p.id) == 1  # contador
    assert store.get_assinatura_por_aluno(a.id).regua_estagio == 2  # régua avançou
    assert tentou                                        # tentou freeform (não entrega)


def test_split_divergencia_marca_atencao(store):
    p, a = _seed_assinante(store, estado="ativo")
    processar_webhook(
        {"id": "evt_s", "event": "PAYMENT_SPLIT_DIVERGENCE_BLOCK",
         "payment": {"id": "pay_s", "subscription": "sub_x"}},
        notificar=lambda *_: None,
    )
    assert store.get_assinatura_por_aluno(a.id).status == "atencao_split"


def test_subscription_deleted_cancela(store):
    p, a = _seed_assinante(store, estado="ativo")
    payload = {"id": "evt_del", "event": "SUBSCRIPTION_DELETED",
               "subscription": {"id": "sub_x"}}
    res = processar_webhook(payload, notificar=lambda *_: None)
    assert res["status"] == "ok"
    assert store.get_aluno_por_telefone("+5511777").estado == "cancelado"
    assert store.get_assinatura_por_aluno(a.id).status == "cancelada"


def test_assinatura_desconhecida_nao_quebra(store):
    res = processar_webhook(_payload("PAYMENT_CONFIRMED", sub_id="sub_inexistente"),
                            notificar=lambda *_: None)
    assert res["status"] == "ok"
    assert res["resultado"]["handled"] is False


# ──────────────────────────────────────────────────────────────────────
# Critério 7 — split com walletId + % do parceiro no payload
# ──────────────────────────────────────────────────────────────────────

def test_build_subscription_payload_inclui_split():
    payload = build_subscription_payload(
        customer_id="cus_1", valor_centavos=3990,
        wallet_id="w_abc", share_pct=30,
    )
    assert payload["value"] == 39.90
    assert payload["cycle"] == "MONTHLY"
    assert payload["split"] == [{"walletId": "w_abc", "percentualValue": 30.0}]


def test_sem_wallet_nao_gera_split():
    payload = build_subscription_payload(
        customer_id="cus_1", valor_centavos=3990,
        wallet_id=None, share_pct=None,
    )
    assert "split" not in payload


def test_checkout_real_envia_split_pro_gateway(
    store, b2c_on, sem_b2g, fake_correcao, mock_asaas,
):
    """Caminho completo: degustação → paywall cria subscription no
    (mock) gateway com o split correto."""
    from redato_backend.b2c.router import maybe_route_b2c
    from redato_backend.whatsapp.bot import InboundMessage

    p = store.add_parceiro(preco_centavos=4990, wallet_id_asaas="w_luma",
                           share_pct=40)
    store.add_aluno("+5511777", p.id, estado="degustacao", nome="Maria")
    maybe_route_b2c(InboundMessage(
        phone="+5511777", text="Impactos da IA na educação brasileira",
        image_path="/tmp/f.jpg"))

    assert mock_asaas.subscriptions, "assinatura não foi criada no gateway"
    split = mock_asaas.subscriptions[0]["payload"]["split"]
    assert split == [{"walletId": "w_luma", "percentualValue": 40.0}]
