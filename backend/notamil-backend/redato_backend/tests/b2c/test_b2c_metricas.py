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


def test_metricas_operacao_e_margem(store):
    """§D11: custo médio, P50/P95, fotos bloqueadas, eventos pendentes e
    margem estimada."""
    p = store.add_parceiro(slug="demo", codigo_entrada="DEMO",
                           preco_centavos=3990, share_pct=30)
    a1 = store.add_aluno("+551", p.id, estado="ativo")
    a2 = store.add_aluno("+552", p.id, estado="ativo")
    # a1: 3 correções, a2: 1 — custo 35 centavos cada
    for _ in range(3):
        store.registrar_envio(a1.id, p.id, nota_total=800,
                              custo_estimado_centavos=35, status="corrigido")
    store.registrar_envio(a2.id, p.id, nota_total=700,
                          custo_estimado_centavos=35, status="corrigido")
    store.registrar_envio_bloqueado(a2.id, p.id)  # foto bloqueada

    out = metricas("demo", _=None)
    op = out["operacao"]
    assert op["custo_medio_centavos"] == 35
    assert op["correcoes_por_assinante_p50"] >= 1
    assert op["correcoes_por_assinante_p95"] == 3
    assert op["fotos_bloqueadas"] == 1
    assert "eventos_pendentes" in op
    fin = out["financeiro"]
    # MRR = 2*3990; parte parceiro 30%; custo 4*35
    assert fin["mrr_centavos"] == 2 * 3990
    assert fin["margem_estimada_centavos"] == 2 * 3990 - int(2 * 3990 * 0.30) - 4 * 35
