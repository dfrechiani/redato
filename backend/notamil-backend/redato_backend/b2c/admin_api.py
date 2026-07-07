"""Endpoints admin do B2C — /admin/b2c/* (SPEC_B2C_REDATO.md §4 F9-F10).

Protegidos pelo mesmo `require_admin_token` (header X-Admin-Token) do
portal admin. No MVP:
- GET /admin/b2c/metricas?parceiro=<slug> : funil + operação + MRR.
- POST /admin/b2c/parceiros : onboarding de parceiro (kit técnico).

A parte financeira (MRR, repasse do parceiro) aparece SÓ aqui (admin) —
nunca em mensagem ao aluno (D4).
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from redato_backend.b2c import config, repo
from redato_backend.portal.admin_api import require_admin_token


router = APIRouter(prefix="/admin/b2c", tags=["admin-b2c"])


# ──────────────────────────────────────────────────────────────────────
# Funil (pura — testável sem DB)
# ──────────────────────────────────────────────────────────────────────

def computar_funil(estados: Dict[str, int]) -> Dict[str, int]:
    """Do dicionário estado→contagem monta o funil do parceiro."""
    def n(*chaves: str) -> int:
        return sum(estados.get(c, 0) for c in chaves)

    total = sum(estados.values())
    cadastros = total - n("novo", "aguardando_nome")
    degustacoes = n(
        "aguardando_cpf", "aguardando_pagamento", "ativo",
        "aguardando_cancelamento", "inadimplente", "bloqueado", "cancelado",
    )
    ativos = n("ativo", "aguardando_cancelamento")
    return {
        "entradas": total,
        "cadastros": cadastros,
        "degustacoes": degustacoes,
        "assinantes_ativos": ativos,
        "inadimplentes": n("inadimplente", "bloqueado"),
        "cancelados": n("cancelado"),
    }


def _percentil(valores: list, p: float) -> int:
    """Percentil simples (nearest-rank). `p` em 0..100."""
    if not valores:
        return 0
    ordenados = sorted(valores)
    k = max(0, min(len(ordenados) - 1,
                   int(round((p / 100) * (len(ordenados) - 1)))))
    return int(ordenados[k])


# ──────────────────────────────────────────────────────────────────────
# GET /admin/b2c/metricas
# ──────────────────────────────────────────────────────────────────────

@router.get("/metricas")
def metricas(
    parceiro: str,
    _: None = Depends(require_admin_token),
) -> Dict[str, Any]:
    p = repo.get_parceiro_por_slug(parceiro)
    if p is None:
        raise HTTPException(status_code=404, detail="parceiro não encontrado")

    estados = repo.contar_alunos_por_estado(p.id)
    funil = computar_funil(estados)
    envios = repo.metricas_envios(p.id)

    # Operação (§D11): custo médio por correção + P50/P95 por assinante.
    total_corr = envios["total_correcoes"]
    custo_total = envios["custo_estimado_centavos"]
    custo_medio = int(custo_total / total_corr) if total_corr else 0
    por_assinante = repo.correcoes_por_assinante_ativo(p.id)
    operacao = {
        **envios,
        "custo_medio_centavos": custo_medio,
        "correcoes_por_assinante_p50": _percentil(por_assinante, 50),
        "correcoes_por_assinante_p95": _percentil(por_assinante, 95),
        "fotos_bloqueadas": repo.contar_fotos_bloqueadas(p.id),
        "eventos_pendentes": repo.contar_eventos_pendentes(p.id),
        # §D9: mensagens de negócio que caíram no envio degradado (fora da
        # janela 24h, sem template aprovado) — provavelmente NÃO entregues.
        "envios_degradados": repo.contar_notificacoes_degradadas(p.id),
    }

    mrr_centavos = funil["assinantes_ativos"] * p.preco_centavos
    parte_parceiro_centavos = (
        int(mrr_centavos * (p.share_pct or 0) / 100)
        if p.share_pct is not None else 0
    )
    # Margem estimada = MRR − parte do parceiro − custo estimado do período.
    margem_centavos = mrr_centavos - parte_parceiro_centavos - custo_total
    return {
        "parceiro": {"slug": p.slug, "nome_publico": p.nome_publico},
        "funil": funil,
        "operacao": operacao,
        "financeiro": {
            "preco_centavos": p.preco_centavos,
            "mrr_centavos": mrr_centavos,
            "share_pct": float(p.share_pct) if p.share_pct is not None else None,
            "parte_parceiro_centavos": parte_parceiro_centavos,
            "custo_estimado_centavos": custo_total,
            "margem_estimada_centavos": margem_centavos,
        },
    }


# ──────────────────────────────────────────────────────────────────────
# POST /admin/b2c/parceiros (F9 — onboarding)
# ──────────────────────────────────────────────────────────────────────

class ParceiroIn(BaseModel):
    slug: str
    codigo_entrada: str
    nome_publico: str
    nome_professor: str
    wallet_id_asaas: Optional[str] = None
    share_pct: Optional[float] = Field(default=None, ge=0, le=100)
    preco_centavos: int = 3990
    branding: Optional[Dict[str, Any]] = None


@router.post("/parceiros", status_code=201)
def criar_parceiro(
    body: ParceiroIn,
    _: None = Depends(require_admin_token),
) -> Dict[str, Any]:
    from redato_backend.portal.db import get_session
    from redato_backend.portal.models import ParceiroB2C

    with get_session() as s:
        p = ParceiroB2C(
            slug=body.slug, codigo_entrada=body.codigo_entrada.upper(),
            nome_publico=body.nome_publico, nome_professor=body.nome_professor,
            wallet_id_asaas=body.wallet_id_asaas, share_pct=body.share_pct,
            preco_centavos=body.preco_centavos, branding=body.branding,
            ativo=True,
        )
        s.add(p)
        s.flush()
        pid = str(p.id)

    numero = config.numero_whatsapp()
    deep_link = (
        f"https://wa.me/{numero}?text=QUERO+{body.codigo_entrada.upper()}"
        if numero else None
    )
    return {
        "id": pid,
        "slug": body.slug,
        "codigo_entrada": body.codigo_entrada.upper(),
        "deep_link": deep_link,
    }
