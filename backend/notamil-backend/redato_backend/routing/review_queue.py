"""Lê a fila de correções pendentes de revisão do professor.

Ponto de leitura para o futuro endpoint /professor/revisao. UI fica em sprint
separada — esta função apenas devolve os dados estruturados.
"""
from typing import Any, Dict, List, Optional


def list_pending_reviews(
    teacher_id: Optional[str] = None,
    *,
    school_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Retorna correções com state='pending_review', ordenadas por created_at desc.

    Args:
        teacher_id: filtra a fila por professor responsável. Se None, lista
            todas as pendentes (uso admin).
        school_id: filtragem futura por escola (não implementado ainda).

    Returns:
        Lista de dicts com:
            - correction_id, student_id, activity_id
            - state, flags, confidence_level, ensemble_n
            - notas (do essay_analysis), feedback
            - created_at
    """
    # Import tardio pra não criar import circular nem custo no startup
    # (este módulo é caminho frio, só carrega quando o professor abre a fila).
    from redato_backend.shared.constants import (
        CORRECTION_REVIEW_TABLE,
        ESSAYS_GRADED_TABLE,
        STUDENTS_TABLE,
    )
    from redato_backend.dev_offline import _LOCK, _STORE

    with _LOCK:
        review_rows = list(_STORE.tables.get(CORRECTION_REVIEW_TABLE, []))
        graded_rows = list(_STORE.tables.get(ESSAYS_GRADED_TABLE, []))
        students_rows = list(_STORE.tables.get(STUDENTS_TABLE, []))

    graded_by_id: Dict[str, Dict[str, Any]] = {
        r["essay_id"]: r for r in graded_rows if r.get("essay_id")
    }
    student_to_teacher: Dict[str, Optional[str]] = {
        s.get("user_id"): s.get("teacher_id") for s in students_rows
    }

    out: List[Dict[str, Any]] = []
    for row in review_rows:
        if row.get("state") != "pending_review":
            continue
        if teacher_id is not None:
            assigned = student_to_teacher.get(row.get("student_id"))
            if assigned and assigned != teacher_id:
                continue

        graded = graded_by_id.get(row.get("correction_id")) or {}
        out.append({
            "correction_id": row.get("correction_id"),
            "student_id": row.get("student_id"),
            "activity_id": row.get("activity_id"),
            "state": row.get("state"),
            "flags": row.get("flags") or [],
            "confidence_level": row.get("confidence_level"),
            "confidence_metadata": graded.get("confidence_metadata"),
            "overall_grade": graded.get("overall_grade"),
            "feedback": graded.get("feedback"),
            "created_at": row.get("created_at"),
        })

    out.sort(key=lambda r: r.get("created_at") or "", reverse=True)
    return out
