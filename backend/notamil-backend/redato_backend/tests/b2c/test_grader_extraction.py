"""D12 (ADENDO §6, critério de aceite 21): grader extraído pra
`redato_backend/grading/`, importado do MESMO módulo público por B2G e
B2C. dev_offline re-exporta por back-compat.
"""
from __future__ import annotations

import inspect


def test_dev_offline_reexporta_grader_de_grading():
    from redato_backend import dev_offline
    from redato_backend.grading import grade_essay_completo
    # A função re-exportada mora de fato em grading.essay.
    assert dev_offline._claude_grade_essay.__module__ == "redato_backend.grading.essay"
    assert dev_offline.grade_essay_completo is grade_essay_completo


def test_bot_e_b2c_importam_grader_do_modulo_publico():
    from redato_backend.whatsapp import bot
    from redato_backend.b2c import correction
    assert (
        "from redato_backend.grading import grade_essay_completo"
        in inspect.getsource(bot._process_photo)
    )
    assert (
        "from redato_backend.grading import grade_essay_completo"
        in inspect.getsource(correction._default_grader)
    )


def test_grader_reexportado_preserva_roteamento_ft():
    """Mesmo smoke de test_openai_ft_grader: a função re-exportada por
    dev_offline mantém o roteamento OF14→FT + rollback."""
    from redato_backend import dev_offline
    src = inspect.getsource(dev_offline._claude_grade_essay)
    for token in ("grade_of14_with_ft", "REDATO_OF14_BACKEND",
                  "COMPLETO_INTEGRAL"):
        assert token in src, f"{token!r} sumiu do grader re-exportado"


def test_grade_essay_completo_injeta_tema_via_grader(monkeypatch):
    """O `tema` chega no grader pelo MESMO campo `theme` do data dict
    (o que o B2G usa). Mockamos _claude_grade_essay pra capturar."""
    from redato_backend.grading import essay as E
    capturado = {}

    def _fake(data):
        capturado.update(data)
        return {"nota_total_enem": 900, "notas_enem": {}}

    monkeypatch.setattr(E, "_claude_grade_essay", _fake)
    E.grade_essay_completo("texto da redação", tema="Democracia digital",
                           activity_id=None)
    assert capturado["theme"] == "Democracia digital"
    assert capturado["content"] == "texto da redação"
    assert capturado["activity_id"] is None
