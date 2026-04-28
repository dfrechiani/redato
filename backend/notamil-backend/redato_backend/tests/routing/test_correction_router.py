"""Testes do route_correction."""
from redato_backend.routing.correction_router import route_correction, HIGH_STAKES_ACTIVITIES


def _correction_with_conf(level: str, ensemble_n: int = 3, flags=None):
    return {
        "_confidence": {
            "confidence_level": level,
            "ensemble_n": ensemble_n,
            "flags": flags or [],
        }
    }


def test_no_confidence_means_auto_delivered():
    out = route_correction({}, student_id="s1", activity_id="RJ1-OF12-MF")
    assert out["state"] == "auto_delivered"
    assert out["visible_to_student"] is True
    assert out["review_record"] is None


def test_single_run_auto_delivered():
    corr = _correction_with_conf("low", ensemble_n=1)
    out = route_correction(corr, student_id="s1", activity_id="RJ3-OF14-SIMFINAL1")
    assert out["state"] == "auto_delivered"


def test_high_confidence_auto_delivered():
    corr = _correction_with_conf("high")
    out = route_correction(corr, student_id="s1", activity_id="RJ3-OF14-SIMFINAL1")
    assert out["state"] == "auto_delivered"
    assert out["review_record"] is None


def test_medium_low_stakes_auto_delivered():
    corr = _correction_with_conf("medium")
    out = route_correction(corr, student_id="s1", activity_id="RJ1-OF11-MF")
    assert out["state"] == "auto_delivered"


def test_medium_high_stakes_pending():
    corr = _correction_with_conf("medium", flags=["high_spread_c3"])
    out = route_correction(corr, student_id="s1", activity_id="RJ3-OF14-SIMFINAL1")
    assert out["state"] == "pending_review"
    assert out["visible_to_student"] is False
    assert out["review_record"]["confidence_level"] == "medium"
    assert "high_spread_c3" in out["review_record"]["flags"]


def test_low_confidence_always_pending():
    corr = _correction_with_conf("low", flags=["low_overall_agreement"])
    # Mesmo em atividade de baixo stake
    out = route_correction(corr, student_id="s1", activity_id="RJ1-OF11-MF")
    assert out["state"] == "pending_review"
    assert out["review_record"]["student_id"] == "s1"
    assert out["review_record"]["activity_id"] == "RJ1-OF11-MF"


def test_high_stakes_set_includes_simulados():
    assert "RJ3-OF09-SIM1" in HIGH_STAKES_ACTIVITIES
    assert "RJ3-OF14-SIMFINAL1" in HIGH_STAKES_ACTIVITIES
    assert "RJ3-OF15-SIMFINAL2" in HIGH_STAKES_ACTIVITIES
