#!/usr/bin/env python3
"""Smoke das features de render (transcrição + faixas + handler ocr errado).

Executa offline (sem chamar API). Valida:
1. Render tem bloco de transcrição quando texto_transcrito é passado
2. Render tem bloco "Por critério" com ⚠️ no pior critério
3. Render permanece ≤800 chars
4. Detector "ocr errado" pega variantes corretas
5. Handler "ocr errado" invalida última interação válida + volta pra AWAITING_FOTO
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND))

# DB isolada
test_db = Path("/tmp/redato_smoke_render.db")
if test_db.exists():
    test_db.unlink()
os.environ["REDATO_WHATSAPP_DB"] = str(test_db)
os.environ.setdefault("REDATO_DEV_OFFLINE", "1")

from redato_backend.whatsapp import persistence as P  # noqa: E402
from redato_backend.whatsapp.render import render_aluno_whatsapp  # noqa: E402
from redato_backend.whatsapp.bot import (  # noqa: E402
    _is_ocr_errado, _handle_ocr_errado, InboundMessage, _set_pending_missao,
    AWAITING_FOTO, READY,
)


def assert_eq(a, b, msg):
    if a != b:
        raise AssertionError(f"{msg}: {a!r} != {b!r}")


def test_render_foco_c3_baixo():
    """Render foco_c3 com nota baixa, exemplo=15 (pior). Verifica ⚠️."""
    args = {
        "modo": "foco_c3",
        "nota_c3_enem": 40,
        "rubrica_rej": {"conclusao": 42, "premissa": 38, "exemplo": 15, "fluencia": 68},
        "flags": {},
        "feedback_aluno": {
            "acertos": ["O texto flui em parágrafo corrido."],
            "ajustes": ["A conclusão é genérica.", "Falta exemplo concreto."],
        },
    }
    transcript = "Diante da fome no Brasil, é fundamental que o Governo aja pra resolver"
    out = render_aluno_whatsapp(args, texto_transcrito=transcript)
    assert "📝 *Texto identificado:*" in out, "transcrição faltando"
    assert "Diante da fome" in out, "snippet faltando"
    assert "ocr errado" in out, "instrução de ocr errado faltando"
    assert "📊 *Por critério:*" in out, "bloco por critério faltando"
    assert "Conclusão: insuficiente ⚠️" in out, "⚠️ na 1ª insuficiente faltando"
    assert "Fluência: adequado" in out, "fluência adequado faltando"
    assert len(out) <= 800, f"out > 800 chars: {len(out)}"
    return f"render_foco_c3 baixo: {len(out)} chars OK"


def test_render_foco_c4_excelente():
    args = {
        "modo": "foco_c4",
        "nota_c4_enem": 200,
        "rubrica_rej": {"estrutura": 92, "conectivos": 88, "cadeia_logica": 85, "palavra_dia": 90},
        "flags": {},
        "feedback_aluno": {
            "acertos": ["As 4 peças encadeadas bem.", "Conectivos com função clara."],
            "ajustes": ["Próximo: explore mais variedade no exemplo."],
        },
    }
    out = render_aluno_whatsapp(args, texto_transcrito="texto do aluno aqui")
    assert "C4" in out and "200/200" in out
    assert "📊 *Por critério:*" in out
    # Todos os 4 scores ≥80 → todos "excelente" → ⚠️ no primeiro (Estrutura)
    assert "Estrutura: excelente ⚠️" in out, f"⚠️ no 1º excelente esperado, out:\n{out}"
    assert len(out) <= 800
    return f"render_foco_c4 excelente: {len(out)} chars OK"


def test_render_completo_parcial():
    args = {
        "modo": "completo_parcial",
        "notas_enem": {"c1": 200, "c2": 200, "c3": 160, "c4": 160, "c5": "não_aplicável"},
        "nota_total_parcial": 720,
        "rubrica_rej": {"topico_frasal": 90, "argumento": 88, "repertorio": 92, "coesao": 88},
        "flags": {},
        "feedback_aluno": {
            "acertos": ["Tópico frasal claro."],
            "ajustes": ["Próximo: detalhe ainda mais o repertório."],
        },
    }
    out = render_aluno_whatsapp(args, texto_transcrito="A educação pública...")
    assert "Correção completa parcial" in out
    assert "C1 200" in out and "C5 não se aplica" in out
    assert "📊 *Por critério:*" in out
    assert len(out) <= 800
    return f"render_completo_parcial: {len(out)} chars OK"


def test_ocr_errado_detector():
    cases = [
        ("ocr errado", True),
        ("OCR ERRADO", True),
        ("ocr errou", True),
        ("leitura errada", True),
        ("ocr incorreto", True),
        ("oi tudo bem", False),
        ("10", False),
        ("a Redato leu errado", False),  # sem palavra ocr/leitura adjacente
    ]
    for text, expected in cases:
        got = _is_ocr_errado(text)
        assert got == expected, f"_is_ocr_errado({text!r}): got {got}, expected {expected}"
    return f"detector ocr errado: {len(cases)} casos OK"


def test_handler_ocr_errado_invalida():
    P.init_db()
    phone = "+5511555ocr"
    P.upsert_aluno(phone, nome="Test", turma_id="t1", escola="E", estado=READY)

    # Simula: aluno teve 1 interação válida com missão OF10
    iid = P.save_interaction(
        aluno_phone=phone, turma_id="t1",
        missao_id="RJ1_OF10_MF",
        activity_id="RJ1·OF10·MF",
        foto_path="/tmp/foto1.jpg",
        foto_hash="abc123def4567890",
        texto_transcrito="texto errado",
        ocr_quality_issues=[],
        ocr_metrics={},
        redato_output={"modo": "foco_c3"},
        resposta_aluno="Avaliação X",
        elapsed_ms=1000,
    )

    # Aluno manda "ocr errado"
    msg = InboundMessage(phone=phone, text="ocr errado", image_path=None)
    aluno = P.get_aluno(phone)
    out = _handle_ocr_errado(msg, aluno)
    assert len(out) == 1
    assert "vou descartar" in out[0].text.lower()

    # Verifica que a interação foi invalidada
    with P._conn() as c:
        row = c.execute("SELECT invalidated_at FROM interactions WHERE id = ?",
                        (iid,)).fetchone()
    assert row["invalidated_at"] is not None, "interação não foi invalidada"

    # Verifica que estado foi setado pra AWAITING_FOTO|RJ1·OF10·MF
    a = P.get_aluno(phone)
    assert a["estado"].startswith(AWAITING_FOTO), f"estado inesperado: {a['estado']}"
    assert "RJ1·OF10·MF" in a["estado"], f"missão não preservada: {a['estado']}"

    # Verifica que find_duplicate não retorna mais essa interação
    dup = P.find_duplicate_interaction(phone, "RJ1_OF10_MF", "abc123def4567890")
    assert dup is None, f"duplicata não deveria mais aparecer (invalidated): {dup}"

    return "handler ocr errado: invalidação + estado AWAITING_FOTO + dedup ignora OK"


def test_handler_ocr_errado_sem_historico():
    P.init_db()
    phone = "+5511555nohist"
    P.upsert_aluno(phone, nome="Sem", turma_id="t1", escola="E", estado=READY)

    msg = InboundMessage(phone=phone, text="ocr errado", image_path=None)
    aluno = P.get_aluno(phone)
    out = _handle_ocr_errado(msg, aluno)
    assert len(out) == 1
    assert "não tenho correção recente" in out[0].text.lower()
    return "handler ocr errado sem histórico OK"


TESTS = [
    test_render_foco_c3_baixo,
    test_render_foco_c4_excelente,
    test_render_completo_parcial,
    test_ocr_errado_detector,
    test_handler_ocr_errado_invalida,
    test_handler_ocr_errado_sem_historico,
]


def main():
    print(f"DB: {os.environ['REDATO_WHATSAPP_DB']}")
    print(f"\n{'='*70}")
    failures = []
    for fn in TESTS:
        try:
            res = fn()
            print(f"  ✓ {fn.__name__}: {res}")
        except AssertionError as exc:
            print(f"  ✗ {fn.__name__}: {exc}")
            failures.append((fn.__name__, str(exc)))
        except Exception as exc:
            print(f"  ✗ {fn.__name__}: {type(exc).__name__}: {exc}")
            failures.append((fn.__name__, repr(exc)))
    print(f"\n{'='*70}")
    if failures:
        print(f"FALHA: {len(failures)}/{len(TESTS)}")
        sys.exit(1)
    print(f"OK: {len(TESTS)}/{len(TESTS)}")


if __name__ == "__main__":
    main()
