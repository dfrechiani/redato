"""Métricas do parceiro (SPEC_B2C_REDATO.md §7 critério 10, F10)."""
from __future__ import annotations

import pytest

from redato_backend.b2c.admin_api import computar_funil, metricas


def test_computar_funil_puro():
    estados = {
        "novo": 2, "aguardando_nome": 1, "degustacao": 3,
        "aguardando_pagamento": 4, "ativo": 5, "inadimplente": 2,
        "cancelado": 1,
    }
    f = computar_funil(estados)
    assert f["entradas"] == 18
    assert f["cadastros"] == 18 - 2 - 1
    assert f["assinantes_ativos"] == 5
    assert f["inadimplentes"] == 2
    assert f["cancelados"] == 1
    # degustações = quem passou da degustação (pagamento+ativo+inad+cancel)
    assert f["degustacoes"] == 4 + 5 + 2 + 1


def test_metricas_endpoint_com_seed(store):
    p = store.add_parceiro(slug="demo", codigo_entrada="DEMO",
                           preco_centavos=3990, share_pct=30)
    for i, estado in enumerate(("novo", "degustacao", "ativo", "ativo", "inadimplente")):
        store.add_aluno(f"+55000{i}", p.id, estado=estado)
    store.registrar_envio("x", p.id, nota_total=800)

    out = metricas("demo", _=None)
    assert out["parceiro"]["slug"] == "demo"
    assert out["funil"]["assinantes_ativos"] == 2
    assert out["funil"]["entradas"] == 5
    # MRR = 2 ativos * 3990 ; parte parceiro = 30%
    assert out["financeiro"]["mrr_centavos"] == 2 * 3990
    assert out["financeiro"]["parte_parceiro_centavos"] == int(2 * 3990 * 0.30)
    assert out["operacao"]["total_correcoes"] == 1


def test_metricas_parceiro_inexistente(store):
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        metricas("nao-existe", _=None)
    assert exc.value.status_code == 404
