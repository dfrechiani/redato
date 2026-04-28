"""Testes round-trip blocks → XML (Mudança 4 OCR).

Validam byte-a-byte que o serializer produz exatamente o formato que o
frontend (text/page.tsx, regex em ~linha 80) espera consumir. Falha
qualquer um destes = frontend quebra silenciosamente em produção.
"""
from redato_backend.functions.essay_ocr.vision.transcription_blocks import (
    blocks_to_xml_string,
)


def test_text_only():
    blocks = [{"type": "text", "text": "O documento está claro."}]
    assert blocks_to_xml_string(blocks) == "O documento está claro."


def test_uncertain_high_confidence():
    blocks = [
        {"type": "text", "text": "O "},
        {"type": "uncertain", "text": "documento", "confidence": "high"},
        {"type": "text", "text": " está claro."},
    ]
    expected = "O <uncertain confidence='HIGH'>documento</uncertain> está claro."
    assert blocks_to_xml_string(blocks) == expected


def test_uncertain_medium_confidence():
    blocks = [
        {"type": "uncertain", "text": "talvez", "confidence": "medium"},
    ]
    assert blocks_to_xml_string(blocks) == "<uncertain confidence='MEDIUM'>talvez</uncertain>"


def test_uncertain_low_confidence():
    blocks = [
        {"type": "uncertain", "text": "ilegível?", "confidence": "low"},
    ]
    assert blocks_to_xml_string(blocks) == "<uncertain confidence='LOW'>ilegível?</uncertain>"


def test_illegible_self_closing():
    blocks = [
        {"type": "text", "text": "antes "},
        {"type": "illegible", "text": ""},
        {"type": "text", "text": " depois."},
    ]
    assert blocks_to_xml_string(blocks) == "antes <illegible/> depois."


def test_paragraph_break_emits_newline():
    blocks = [
        {"type": "text", "text": "Primeiro."},
        {"type": "paragraph_break", "text": ""},
        {"type": "text", "text": "Segundo."},
    ]
    assert blocks_to_xml_string(blocks) == "Primeiro.\nSegundo."


def test_composite_realistic_essay_fragment():
    """Caso composto: tudo junto, simulando um parágrafo real."""
    blocks = [
        {"type": "text", "text": "A "},
        {"type": "uncertain", "text": "exclusão", "confidence": "high"},
        {"type": "text", "text": " digital "},
        {"type": "uncertain", "text": "afeta", "confidence": "medium",
         "alternatives": ["afeito", "afeta"]},
        {"type": "text", "text": " "},
        {"type": "illegible", "text": ""},
        {"type": "text", "text": " regiões periféricas."},
        {"type": "paragraph_break", "text": ""},
        {"type": "text", "text": "Cabe ao Estado agir."},
    ]
    expected = (
        "A <uncertain confidence='HIGH'>exclusão</uncertain> digital "
        "<uncertain confidence='MEDIUM'>afeta</uncertain> <illegible/> "
        "regiões periféricas.\nCabe ao Estado agir."
    )
    assert blocks_to_xml_string(blocks) == expected


def test_confidence_default_when_missing():
    """Se confidence não vier (modelo bobeia), assume 'high' — não quebra."""
    blocks = [{"type": "uncertain", "text": "x"}]
    assert blocks_to_xml_string(blocks) == "<uncertain confidence='HIGH'>x</uncertain>"


def test_unknown_type_falls_back_to_text():
    """Defensivo: tipo desconhecido vira texto cru."""
    blocks = [{"type": "weird_future_type", "text": "fallback"}]
    assert blocks_to_xml_string(blocks) == "fallback"
