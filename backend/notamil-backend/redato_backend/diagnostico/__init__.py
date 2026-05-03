"""Diagnóstico cognitivo de redação ENEM (Fase 2).

Lê os 40 descritores observáveis (Fase 1, commit 010686c) em
``docs/redato/v3/diagnostico/descritores.yaml`` e gera, pra cada
envio com correção bem-sucedida, um JSON estruturado com status
(dominio/lacuna/incerto) por descritor + lacunas prioritárias +
resumo qualitativo.

Pipeline:
    [redato_output + texto + tema]
        → inferir_diagnostico() — chama GPT-4.1 com tool schema
        → 40 descritores classificados + lacunas + resumo
        → persistido em envios.diagnostico (JSONB)

Visibilidade:
    - Aluno: invisível (frontend ignora coluna).
    - Professor: visível no perfil do aluno (Fase 3).

Falhas não bloqueiam:
    Pipeline principal de correção continua entregando feedback ao
    aluno mesmo se diagnóstico falhar (timeout OpenAI, parser não
    casa, key missing). Erro é logado via logger.exception, e
    coluna `envios.diagnostico` fica NULL.

Reprocessar:
    POST /portal/envios/{id}/diagnosticar reroda inferência sob
    demanda — útil pra envios pré-Fase 2 (NULL) e pra atualizar
    quando descritores.yaml ganhar versão nova.
"""
from __future__ import annotations

from redato_backend.diagnostico.descritores import (
    Descritor,
    DEFAULT_YAML_PATH,
    load_descritores,
    descritores_por_id,
    descritor_ids,
)
from redato_backend.diagnostico.metas import (
    Meta,
    MAX_METAS,
    gerar_metas_aluno,
    metas_to_dicts,
    render_metas_whatsapp,
)
from redato_backend.diagnostico.sugestoes import (
    OficinaSugerida,
    MAX_POR_LACUNA,
    sugerir_oficinas,
    sugestoes_to_dicts,
)

__all__ = [
    # Fase 1 — descritores
    "Descritor",
    "DEFAULT_YAML_PATH",
    "load_descritores",
    "descritores_por_id",
    "descritor_ids",
    # Fase 3 — metas (aluno) e sugestões (professor)
    "Meta",
    "MAX_METAS",
    "gerar_metas_aluno",
    "metas_to_dicts",
    "render_metas_whatsapp",
    "OficinaSugerida",
    "MAX_POR_LACUNA",
    "sugerir_oficinas",
    "sugestoes_to_dicts",
]
