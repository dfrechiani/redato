"""Roteador que decide se a correção vai direto pro aluno ou pra revisão."""
from typing import Literal, Optional, Any

ReviewState = Literal[
    "auto_delivered",
    "pending_review",
    "reviewed_approved",
    "reviewed_rejected",
]

# Atividades de alto stake — sempre acionam revisão em confidence média ou baixa.
# IDs alinhados com o catálogo de atividades dos livros (Redação em Jogo).
HIGH_STAKES_ACTIVITIES = {
    # Redações completas / simulados
    "RJ1-OF14-MF",
    "RJ2-OF13-MF",
    "RJ3-OF01-MF",
    "RJ3-OF09-SIM1",
    "RJ3-OF11-SIM2",
    "RJ3-OF12-MF",
    "RJ3-OF13-MF",
    "RJ3-OF14-SIMFINAL1",
    "RJ3-OF15-SIMFINAL2",
}


def route_correction(
    correction: dict,
    *,
    student_id: str,
    activity_id: str,
) -> dict:
    """Decide se a correção vai direto pro aluno ou pra fila de revisão.

    Returns:
        {
            "state": ReviewState,
            "visible_to_student": bool,
            "review_record": Optional[dict],
        }
    """
    conf = correction.get("_confidence") if isinstance(correction, dict) else None

    # Sem ensemble (N<2) → vai direto.
    if not isinstance(conf, dict) or conf.get("ensemble_n", 1) < 2:
        return {
            "state": "auto_delivered",
            "visible_to_student": True,
            "review_record": None,
        }

    is_high_stakes = activity_id in HIGH_STAKES_ACTIVITIES
    level = conf.get("confidence_level", "high")

    if level == "high":
        return {
            "state": "auto_delivered",
            "visible_to_student": True,
            "review_record": None,
        }

    if level == "medium" and not is_high_stakes:
        return {
            "state": "auto_delivered",
            "visible_to_student": True,
            "review_record": None,
        }

    return {
        "state": "pending_review",
        "visible_to_student": False,
        "review_record": {
            "student_id": student_id,
            "activity_id": activity_id,
            "state": "pending_review",
            "flags": list(conf.get("flags", [])),
            "confidence_level": level,
            "ensemble_n": int(conf.get("ensemble_n", 0)),
        },
    }
