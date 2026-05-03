"""Persistência do diagnóstico cognitivo em ``envios.diagnostico``.

Helper minimalista — UPDATE isolado, sessão própria. Não toca em
``criar_interaction_e_envio_postgres`` (mantém aquele write como
single-purpose).
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from redato_backend.portal.db import get_engine
from redato_backend.portal.models import Envio

logger = logging.getLogger(__name__)


def persistir_diagnostico_envio(
    envio_id: uuid.UUID, diagnostico: Dict[str, Any],
) -> bool:
    """UPDATE envios.diagnostico = :data WHERE id = :envio_id.

    Retorna True se o UPDATE persistiu, False se o envio não existe
    ou houve erro. NÃO levanta — caller já trata diagnostico como
    operação não-bloqueante.

    Sessão própria (curta) pra não estender transação do bot —
    evita lock contention no Postgres em pico de uso.
    """
    if not isinstance(diagnostico, dict):
        logger.error(
            "persistir_diagnostico: tipo inválido %s",
            type(diagnostico).__name__,
        )
        return False
    try:
        with Session(get_engine()) as session:
            envio = session.get(Envio, envio_id)
            if envio is None:
                logger.warning(
                    "persistir_diagnostico: envio %s não existe", envio_id,
                )
                return False
            envio.diagnostico = diagnostico
            session.commit()
        return True
    except Exception:  # noqa: BLE001
        logger.exception(
            "persistir_diagnostico: falha em UPDATE pra envio %s",
            envio_id,
        )
        return False


def diagnosticar_e_persistir_envio(
    *,
    envio_id: uuid.UUID,
    texto_redacao: str,
    redato_output: Optional[Dict[str, Any]],
    tema: str,
) -> Optional[Dict[str, Any]]:
    """Helper end-to-end: roda inferência + persiste em uma chamada.

    Wrapper conveniente pra integração do bot (1 try/except no caller
    em vez de 2). Retorna o diagnóstico persistido ou None se falhou
    em qualquer etapa.

    NÃO levanta — ambas falhas (inferência e persistência) são logadas
    e o caller continua sem diagnóstico.
    """
    from redato_backend.diagnostico.inferencia import (
        diagnostico_habilitado, inferir_diagnostico,
    )

    # Log de entry — primeiro evento observável. Daniel grepa
    # "[diag] iniciando" pra encontrar todos os envios em que o
    # helper foi chamado, mesmo se inferência errou cedo.
    logger.info(
        "[diag] iniciando para envio %s (texto_chars=%d, has_redato=%s)",
        envio_id, len(texto_redacao or ""), bool(redato_output),
    )

    if not diagnostico_habilitado():
        logger.warning(
            "[diag] DESABILITADO (REDATO_DIAGNOSTICO_HABILITADO) "
            "— pulando envio %s", envio_id,
        )
        return None

    try:
        diagnostico = inferir_diagnostico(
            texto_redacao=texto_redacao,
            redato_output=redato_output or {},
            tema=tema,
        )
    except Exception:  # noqa: BLE001
        # `inferir_diagnostico` já tem try/except interno e retorna
        # None em falha. Esse catch é defesa em profundidade.
        logger.exception(
            "[diag] exceção não-tratada em inferir_diagnostico "
            "pra envio %s", envio_id,
        )
        return None

    if diagnostico is None:
        logger.error(
            "[diag] inferir_diagnostico retornou None pra envio %s "
            "— procure no log o último '[diag]' antes desse pra "
            "causa raiz (timeout, key, schema, validação)",
            envio_id,
        )
        return None

    ok = persistir_diagnostico_envio(envio_id, diagnostico)
    if not ok:
        logger.error(
            "[diag] inferência ok mas UPDATE falhou pra envio %s",
            envio_id,
        )
        return None

    logger.info(
        "[diag] persistido com sucesso em envios.diagnostico "
        "(envio=%s, modelo=%s, lacunas=%d, custo=$%.4f)",
        envio_id,
        diagnostico.get("modelo_usado"),
        sum(1 for d in diagnostico.get("descritores", [])
            if d.get("status") == "lacuna"),
        diagnostico.get("custo_estimado_usd", 0),
    )
    return diagnostico
