"""Tool schema + serializador de blocks → XML.

Módulo separado pra que testes (e código novo) possam importar sem
puxar dependências de runtime de produção (cv2, google.cloud).
"""
from typing import Any, Dict, List


SUBMIT_TRANSCRIPTION_TOOL: Dict[str, Any] = {
    "name": "submit_transcription",
    "description": (
        "Submete a transcrição estruturada da redação manuscrita. Cada palavra "
        "(ou ponto de quebra) vira um bloco. Palavras lidas com certeza usam "
        "type='text'. Palavras com qualquer dúvida usam type='uncertain' com "
        "confidence e (idealmente) alternatives. Partes ilegíveis usam "
        "type='illegible'. Quebras de parágrafo usam type='paragraph_break'."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "theme": {
                "type": "string",
                "description": (
                    "Tema/título da redação — geralmente a primeira frase em "
                    "destaque manuscrita pelo aluno."
                ),
            },
            "blocks": {
                "type": "array",
                "description": (
                    "Sequência de blocos de texto da redação, na ordem em "
                    "que aparecem. Inclua o texto sem o tema."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "type": {
                            "type": "string",
                            "enum": ["text", "uncertain", "illegible", "paragraph_break"],
                        },
                        "text": {
                            "type": "string",
                            "description": (
                                "Texto do bloco. Vazio para 'illegible' e "
                                "'paragraph_break'."
                            ),
                        },
                        "confidence": {
                            "type": "string",
                            "enum": ["high", "medium", "low"],
                            "description": "Apenas para type='uncertain'.",
                        },
                        "alternatives": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": (
                                "Leituras alternativas plausíveis. Apenas "
                                "para type='uncertain'."
                            ),
                        },
                    },
                    "required": ["type", "text"],
                },
            },
        },
        "required": ["theme", "blocks"],
    },
}


def blocks_to_xml_string(blocks: List[Dict[str, Any]]) -> str:
    """Converte lista estruturada de blocks em string com tags XML
    (formato consumido pelo frontend hoje, em text/page.tsx).

    Preserva o contrato existente:
        <uncertain confidence='HIGH'>palavra</uncertain>
        <illegible/>
        \\n  (quebra de parágrafo)
        text livre (caso normal)

    `confidence` é maiúsculo no XML pra bater com o regex do frontend
    (linha ~80 de text/page.tsx).
    """
    parts: List[str] = []
    for block in blocks:
        btype = block.get("type")
        text = block.get("text", "") or ""
        if btype == "text":
            parts.append(text)
        elif btype == "uncertain":
            conf = (block.get("confidence") or "high").upper()
            parts.append(f"<uncertain confidence='{conf}'>{text}</uncertain>")
        elif btype == "illegible":
            parts.append("<illegible/>")
        elif btype == "paragraph_break":
            parts.append("\n")
        else:
            # Tipo desconhecido — preserva texto cru como fallback (defensivo).
            parts.append(text)
    return "".join(parts)
