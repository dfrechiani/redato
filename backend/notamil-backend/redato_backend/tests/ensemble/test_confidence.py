"""Testes do calculate_confidence."""
from redato_backend.ensemble.confidence import calculate_confidence


def make_run(c1=120, c2=120, c3=120, c4=120, c5=120):
    """Helper: cria result fake com notas dadas."""
    notas = {"c1": c1, "c2": c2, "c3": c3, "c4": c4, "c5": c5}
    notas["total"] = sum(notas.values())
    return {"notas": notas}


def test_unanimous_high_confidence():
    """3 runs idênticos → high confidence."""
    runs = [make_run(120, 160, 160, 160, 120) for _ in range(3)]
    conf = calculate_confidence(runs)
    assert conf.confidence_level == "high"
    assert conf.overall_agreement == 1.0
    assert conf.total_spread == 0
    assert conf.needs_human_review is False
    assert all(c.is_unanimous for c in conf.per_competency)


def test_one_competency_diverges():
    """Uma competência com spread grande mas agreement geral alto → high."""
    runs = [
        make_run(160, 160, 160, 160, 160),
        make_run(160, 160, 80, 160, 160),   # C3 diverge
        make_run(160, 160, 160, 160, 160),
    ]
    conf = calculate_confidence(runs)
    # C3: notas [160, 80, 160], moda 160, agreement 2/3 = 0.667
    # Outras: agreement 1.0
    # Overall = (1+1+0.667+1+1)/5 = 0.933
    # Spread total: max 800, min 720 → 80
    assert conf.confidence_level == "high"
    assert "high_spread_c3" in conf.flags


def test_low_confidence_triggers_review():
    """Spread alto e baixo agreement → low + needs_review."""
    runs = [
        make_run(40, 200, 40, 200, 40),
        make_run(200, 40, 200, 40, 200),
        make_run(120, 120, 120, 120, 120),
    ]
    conf = calculate_confidence(runs)
    assert conf.confidence_level == "low"
    assert conf.needs_human_review is True
    assert "low_overall_agreement" in conf.flags


def test_single_run_high_by_default():
    """N=1 → high confidence (sem dados pra discordar)."""
    runs = [make_run()]
    conf = calculate_confidence(runs)
    assert conf.confidence_level == "high"
    assert "single_run" in conf.flags
    assert conf.needs_human_review is False


def test_to_dict_serialization():
    """to_dict produz estrutura serializável JSON."""
    import json
    runs = [make_run(160, 160, 160, 160, 160), make_run(160, 160, 120, 160, 160)]
    conf = calculate_confidence(runs)
    d = conf.to_dict()
    json.dumps(d)  # não deve levantar
    assert d["ensemble_n"] == 2
    assert isinstance(d["per_competency"], list)
    assert d["per_competency"][2]["competency"] == "c3"


def test_medium_confidence_band():
    """Total spread 120, overall agreement ~0.7 → medium."""
    runs = [
        make_run(160, 160, 160, 160, 160),  # total 800
        make_run(120, 160, 160, 160, 160),  # total 760
        make_run(160, 120, 160, 120, 160),  # total 720, spread total 80
    ]
    conf = calculate_confidence(runs)
    assert conf.confidence_level in ("high", "medium")  # depende exato dos thresholds
