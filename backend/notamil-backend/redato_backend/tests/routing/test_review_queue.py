"""Testes do list_pending_reviews."""
from datetime import datetime, timezone

import pytest

from redato_backend.shared.constants import (
    CORRECTION_REVIEW_TABLE,
    ESSAYS_GRADED_TABLE,
    STUDENTS_TABLE,
)


@pytest.fixture
def seeded_store():
    """Reseta o store fake e popula com dados de fila."""
    from redato_backend.dev_offline import _LOCK, _STORE

    with _LOCK:
        # Snapshot pra restaurar depois
        snapshot = {
            CORRECTION_REVIEW_TABLE: list(_STORE.tables.get(CORRECTION_REVIEW_TABLE, [])),
            ESSAYS_GRADED_TABLE: list(_STORE.tables.get(ESSAYS_GRADED_TABLE, [])),
            STUDENTS_TABLE: list(_STORE.tables.get(STUDENTS_TABLE, [])),
        }
        _STORE.tables[CORRECTION_REVIEW_TABLE] = []
        _STORE.tables[ESSAYS_GRADED_TABLE] = []
        _STORE.tables[STUDENTS_TABLE] = [
            {"user_id": "stu-1", "teacher_id": "teach-A"},
            {"user_id": "stu-2", "teacher_id": "teach-B"},
        ]
        now = datetime.now(timezone.utc).isoformat()
        _STORE.tables[ESSAYS_GRADED_TABLE] = [
            {"essay_id": "ess-1", "user_id": "stu-1", "overall_grade": 720,
             "feedback": "fdbk1", "confidence_metadata": {"confidence_level": "low"}},
            {"essay_id": "ess-2", "user_id": "stu-2", "overall_grade": 800,
             "feedback": "fdbk2", "confidence_metadata": {"confidence_level": "low"}},
        ]
        _STORE.tables[CORRECTION_REVIEW_TABLE] = [
            {"id": "rev-1", "correction_id": "ess-1", "student_id": "stu-1",
             "activity_id": "RJ3-OF14-SIMFINAL1", "state": "pending_review",
             "flags": ["low_overall_agreement"], "confidence_level": "low",
             "created_at": "2026-04-25T10:00:00Z"},
            {"id": "rev-2", "correction_id": "ess-2", "student_id": "stu-2",
             "activity_id": "RJ3-OF09-SIM1", "state": "pending_review",
             "flags": ["high_spread_c3"], "confidence_level": "medium",
             "created_at": "2026-04-25T11:00:00Z"},
            # Already approved — should NOT be returned
            {"id": "rev-3", "correction_id": "ess-3", "student_id": "stu-1",
             "activity_id": "RJ3-OF14-SIMFINAL1", "state": "reviewed_approved",
             "flags": [], "confidence_level": "low",
             "created_at": "2026-04-25T09:00:00Z"},
        ]

    yield

    with _LOCK:
        for k, v in snapshot.items():
            _STORE.tables[k] = v


def test_lists_only_pending(seeded_store):
    from redato_backend.routing.review_queue import list_pending_reviews
    out = list_pending_reviews()
    assert len(out) == 2
    assert all(r["state"] == "pending_review" for r in out)


def test_filters_by_teacher(seeded_store):
    from redato_backend.routing.review_queue import list_pending_reviews
    teach_a = list_pending_reviews(teacher_id="teach-A")
    assert len(teach_a) == 1
    assert teach_a[0]["student_id"] == "stu-1"

    teach_b = list_pending_reviews(teacher_id="teach-B")
    assert len(teach_b) == 1
    assert teach_b[0]["student_id"] == "stu-2"


def test_orders_by_created_at_desc(seeded_store):
    from redato_backend.routing.review_queue import list_pending_reviews
    out = list_pending_reviews()
    assert out[0]["created_at"] >= out[1]["created_at"]


def test_includes_grading_metadata(seeded_store):
    from redato_backend.routing.review_queue import list_pending_reviews
    out = list_pending_reviews(teacher_id="teach-A")
    row = out[0]
    assert row["overall_grade"] == 720
    assert row["feedback"] == "fdbk1"
    assert row["confidence_metadata"] == {"confidence_level": "low"}
    assert row["activity_id"] == "RJ3-OF14-SIMFINAL1"
