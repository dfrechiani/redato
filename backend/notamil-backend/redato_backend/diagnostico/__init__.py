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
from redato_backend.diagnostico.sugestoes_pedagogicas import (
    get_sugestao_pedagogica,
    get_definicao_curta,
)
from redato_backend.diagnostico.agregacao import (
    agregar_diagnosticos_turma,
    calcular_top_lacunas,
    THRESHOLD_TOP_LACUNAS_PERCENT,
    THRESHOLD_HEATMAP_AMARELO,
    THRESHOLD_HEATMAP_VERMELHO,
    THRESHOLD_COBERTURA_AVISO,
    MAX_TOP_LACUNAS,
)
from redato_backend.diagnostico.oficinas_livro import (
    OficinaLivroSugerida,
    sugerir_oficinas_livro,
    sugestoes_to_dicts as sugestoes_livro_to_dicts,
    status_mapeamento as status_mapeamento_livros,
    carregar_mapeamento,
)
from redato_backend.diagnostico.narrativa import (
    NarrativaTurma,
    CardAcao,
    gerar_narrativa_turma,
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
    # Fix Fase 3 — sugestões pedagógicas (cards de lacuna)
    "get_sugestao_pedagogica",
    "get_definicao_curta",
    # Fase 4 — agregação por turma
    "agregar_diagnosticos_turma",
    "calcular_top_lacunas",
    "THRESHOLD_TOP_LACUNAS_PERCENT",
    "THRESHOLD_HEATMAP_AMARELO",
    "THRESHOLD_HEATMAP_VERMELHO",
    "THRESHOLD_COBERTURA_AVISO",
    "MAX_TOP_LACUNAS",
    # Fase 5A.1 — mapeamento livro → descritores (rascunho LLM)
    "OficinaLivroSugerida",
    "sugerir_oficinas_livro",
    "sugestoes_livro_to_dicts",
    "status_mapeamento_livros",
    "carregar_mapeamento",
    # Fix UX Fase 4 (proposta D) — storytelling + ações
    "NarrativaTurma",
    "CardAcao",
    "gerar_narrativa_turma",
]
