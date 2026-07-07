"""Grader completo de redação (5 competências ENEM) — motor público.

Movido de `dev_offline._claude_grade_essay` (D12). A ORQUESTRAÇÃO da
correção vive aqui: roteamento REJ (Foco/Parcial → missions; Completo
Integral → FT/Claude v2), montagem do prompt, self-critique, derivação
mecânica e persistência. A PLUMBING de baixo nível de LLM
(`_call_claude_with_tool`, `_run_self_critique`,
`_derive_notas_mechanically`, `_persist_grading_to_bq`) continua em
`dev_offline` e é chamada por referência lazy — evita mover o cluster
inteiro (e seus schemas/constantes) num passo só e mantém o
stubbing offline intacto.

Sem import de `dev_offline` em nível de módulo: a referência é lazy
(dentro da função) pra não criar ciclo com o re-export que o
dev_offline faz deste módulo.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional


logger = logging.getLogger(__name__)


def _claude_grade_essay(data: Dict[str, Any]) -> Dict[str, Any]:
    """Grade the essay using the real Claude API + audit-first schema.

    Returns the full ``tool_args`` dict from Claude (the audit output) so
    callers like the calibration eval script can inspect the raw reasoning.

    Assinatura por `data` dict preservada (back-compat: dev_offline
    re-exporta esta função com o nome antigo, e ~8 call-sites + 2 testes
    de getsource dependem dela).
    """
    # Plumbing de baixo nível ainda em dev_offline — import lazy (runtime)
    # pra não colidir com o re-export que dev_offline faz deste módulo.
    from redato_backend import dev_offline as _do

    try:
        import anthropic
    except ImportError as e:
        raise RuntimeError(
            "Anthropic SDK not installed. Add `anthropic` to requirements-dev.txt "
            "or unset ANTHROPIC_API_KEY to use the deterministic stub."
        ) from e

    essay_id = data["request_id"]
    content = (data.get("content") or "").strip()
    theme = (data.get("theme") or "").strip() or "Tema livre"
    user_id = data.get("user_id")
    activity_id = data.get("activity_id")

    # Roteamento REJ 1S: missões Foco e Completo Parcial usam pipelines
    # próprios em redato_backend.missions. Modo Completo Integral (OF14)
    # cai no fluxo v2 padrão abaixo, mas com preâmbulo REJ no user_msg.
    from redato_backend.missions import (
        MissionMode, resolve_mode, grade_mission,
    )
    from redato_backend.missions.prompts import (
        OF14_REJ_PREAMBLE, feedback_aluno_registro_block,
    )

    _mission_mode = resolve_mode(activity_id)
    if _mission_mode is not None and _mission_mode != MissionMode.COMPLETO_INTEGRAL:
        return grade_mission(data)

    # OF14 (completo_integral) usa GPT-FT BTBOS5VF como backend padrão desde
    # 2026-04-30. Rollback rápido: REDATO_OF14_BACKEND=claude (1 env var, sem
    # deploy). Fallback automático: se FT falha, cai pro Claude path abaixo.
    if (
        _mission_mode == MissionMode.COMPLETO_INTEGRAL
        and os.getenv("REDATO_OF14_BACKEND", "ft") == "ft"
    ):
        try:
            from redato_backend.missions.openai_ft_grader import (
                grade_of14_with_ft,
            )
            tool_args = grade_of14_with_ft(content=content, theme=theme)
            logger.info(
                "OF14 graded via FT BTBOS5VF (request_id=%s)", essay_id,
            )
            _do._persist_grading_to_bq(
                tool_args=tool_args,
                essay_id=essay_id,
                user_id=user_id,
                content=content,
                activity_id=data.get("activity_id"),
            )
            try:
                from redato_backend.shared.job_tracker import EssayJobTracker
                tracker = EssayJobTracker()
                tracker._collection.document(essay_id).set(  # type: ignore[union-attr]
                    {"raw_audit": tool_args, "updated_at": datetime.now(timezone.utc)},
                    merge=True,
                )
            except (ImportError, ModuleNotFoundError) as exc:
                logger.warning(
                    "Firestore stash skipped for %s — google-cloud "
                    "unavailable (%s)", essay_id, exc,
                )
            except Exception:  # noqa: BLE001
                logger.exception(
                    "could not stash raw_audit for %s", essay_id,
                )
            return tool_args
        except Exception:  # noqa: BLE001
            # Mantém literal "falling back to Claude" pro
            # test_dev_offline_tem_roteamento_of14_ft_com_rollback
            # detectar refactors que removem o fallback.
            logger.exception(
                "OF14 FT path failed for %s — falling back to Claude "
                "Sonnet 4.6 v2 (graceful degradation; set "
                "REDATO_OF14_BACKEND=claude to silence this fallback)",
                essay_id,
            )
            # Cai pro Claude path abaixo.

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    model = os.getenv("REDATO_CLAUDE_MODEL", "claude-sonnet-4-6")

    rej_preamble = (
        f"{OF14_REJ_PREAMBLE}\n---\n\n"
        if _mission_mode == MissionMode.COMPLETO_INTEGRAL
        else ""
    )

    registro_block = feedback_aluno_registro_block()

    user_msg = (
        f"{rej_preamble}"
        f"{registro_block}\n\n"
        f"---\n\n"
        f"TEMA: {theme}\n\n"
        f"REDAÇÃO DO ALUNO:\n\"\"\"\n{content}\n\"\"\"\n\n"
        "Avalie a redação acima pelas 5 competências ENEM, aplicando a "
        "calibração da Seção 6 (incluindo os adendos 6.5.1 C5 e 6.5.2 C1). "
        "Chame `submit_correction` preenchendo TODOS os campos de auditoria."
    )

    # Pré-flag mecânico de repetição lexical — default OFF (A/B REVERT).
    if os.getenv("REDATO_REPETITION_FLAG", "0") == "1":
        from redato_backend.audits.lexical_repetition_detector import (
            maybe_inject_repetition_addendum,
        )
        user_msg = maybe_inject_repetition_addendum(user_msg, content)

    tool_args = _do._call_claude_with_tool(client, model, user_msg)
    # _confidence é anexado por _merge_ensemble_results e precisa sobreviver
    # ao self-critique, que devolve um dict limpo da chamada de revisão.
    confidence_metadata = tool_args.get("_confidence") if isinstance(tool_args, dict) else None

    rubrica = os.getenv("REDATO_RUBRICA", "v2")
    is_v3 = rubrica == "v3"

    if not is_v3 and os.getenv("REDATO_SELF_CRITIQUE") == "1":
        tool_args = _do._run_self_critique(client, model, user_msg, tool_args)
        if confidence_metadata is not None and isinstance(tool_args, dict):
            tool_args["_confidence"] = confidence_metadata

    if not is_v3 and os.getenv("REDATO_TWO_STAGE", "1") != "0":
        derived = _do._derive_notas_mechanically(tool_args)
        for key in ("c1", "c2", "c3", "c4", "c5"):
            audit = tool_args.get(f"{key}_audit")
            if isinstance(audit, dict):
                old_nota = audit.get("nota")
                audit["nota"] = derived[key]
                if old_nota != derived[key]:
                    print(
                        f"[grading] {key}: LLM said {old_nota}, mechanical={derived[key]}"
                    )

    if not is_v3:
        _do._persist_grading_to_bq(
            tool_args=tool_args,
            essay_id=essay_id,
            user_id=user_id,
            content=content,
            activity_id=data.get("activity_id"),
        )

    try:
        from redato_backend.shared.job_tracker import EssayJobTracker
        tracker = EssayJobTracker()
        tracker._collection.document(essay_id).set(  # type: ignore[union-attr]
            {"raw_audit": tool_args, "updated_at": datetime.now(timezone.utc)},
            merge=True,
        )
    except (ImportError, ModuleNotFoundError) as exc:
        logger.warning(
            "Firestore stash skipped for %s — google-cloud unavailable "
            "(%s)", essay_id, exc,
        )
    except Exception:  # noqa: BLE001
        logger.exception(
            "could not stash raw_audit for %s", essay_id,
        )

    return tool_args


def grade_essay_completo(
    texto: str,
    tema: str,
    *,
    activity_id: Optional[str] = None,
    request_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Ponto público único do grader completo (5 competências ENEM).

    `tema` é injetado no MESMO campo que o B2G usa historicamente — o
    `theme` do prompt do grader (ver `_claude_grade_essay`: `TEMA:
    {theme}` no user_msg, e `grade_of14_with_ft(theme=...)` no path FT).
    Nunca passar tema vazio: quem chama garante um tema real.

    bot.py (B2G) e b2c/correction.py importam ESTA função.
    """
    import time
    data = {
        "request_id": request_id or f"essay_{int(time.time())}",
        "user_id": user_id,
        "activity_id": activity_id,
        "theme": tema,
        "content": texto,
    }
    return _claude_grade_essay(data)
