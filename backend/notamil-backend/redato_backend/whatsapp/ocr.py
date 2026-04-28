"""OCR via Claude Sonnet 4.6 multimodal + checks de qualidade da foto.

Distinto do pipeline OCR de produção (Cloud Vision + 3 imagens enhanced
+ Opus). Aqui é fluxo de aluno via celular, simples e barato:
- 1 imagem
- Sonnet 4.6 (5x mais barato que Opus)
- Sem JSONProcessor estruturado (texto puro)

Quality checks executam ANTES de chamar a API: foto escura/borrada/curta
demais é rejeitada localmente, evitando gasto.
"""
from __future__ import annotations

import base64
import io
import os
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from PIL import Image, ImageFilter, ImageOps


# ──────────────────────────────────────────────────────────────────────
# Quality thresholds (tunable via env)
# ──────────────────────────────────────────────────────────────────────

# Brilho médio em [0, 255]. Foto escura demais → não dá pra ler.
MIN_BRIGHTNESS = float(os.getenv("REDATO_OCR_MIN_BRIGHTNESS", "60"))

# Variance do filtro Laplaciano. Heurística clássica de blur:
# https://pyimagesearch.com/2015/09/07/blur-detection-with-opencv/
# Threshold calibrado em uso real (2026-04-27): foto HD de iPhone com
# papel pautado + caneta esferográfica + compressão WhatsApp dá
# laplacian_var ~70-90. 40 é piso conservador — borrada de verdade
# (mão tremida) fica < 30.
MIN_LAPLACIAN_VAR = float(os.getenv("REDATO_OCR_MIN_LAPLACIAN_VAR", "40"))

# Mínimo de chars transcritos. Foto que não pegou redação produz output
# tipo "[ilegível]" ou 1 linha curta.
MIN_TRANSCRIBED_CHARS = int(os.getenv("REDATO_OCR_MIN_CHARS", "50"))


@dataclass
class OcrResult:
    """Resultado do OCR + quality check."""
    text: str                       # texto transcrito (vazio se rejected)
    metrics: Dict[str, Any]         # brightness, laplacian_var, n_chars
    quality_issues: List[str]       # ["foto_escura", "foto_borrada", "texto_curto"]
    rejected: bool                  # True se algum issue impede pipeline


# ──────────────────────────────────────────────────────────────────────
# Quality checks — locais, sem API
# ──────────────────────────────────────────────────────────────────────

_LAPLACIAN_KERNEL = ImageFilter.Kernel(
    (3, 3),
    [0, 1, 0, 1, -4, 1, 0, 1, 0],
    scale=1, offset=0,
)


def _compute_metrics(image: Image.Image) -> Dict[str, float]:
    """Computa brightness médio + variance do Laplaciano em escala de cinza."""
    gray = image.convert("L")
    arr = np.asarray(gray, dtype=np.float32)
    brightness = float(arr.mean())
    edges = gray.filter(_LAPLACIAN_KERNEL)
    edge_arr = np.asarray(edges, dtype=np.float32)
    laplacian_var = float(edge_arr.var())
    return {
        "brightness": round(brightness, 2),
        "laplacian_var": round(laplacian_var, 2),
        "width": gray.width,
        "height": gray.height,
    }


def check_image_quality(image: Image.Image) -> Tuple[Dict[str, float], List[str]]:
    metrics = _compute_metrics(image)
    issues: List[str] = []
    if metrics["brightness"] < MIN_BRIGHTNESS:
        issues.append("foto_escura")
    if metrics["laplacian_var"] < MIN_LAPLACIAN_VAR:
        issues.append("foto_borrada")
    return metrics, issues


# ──────────────────────────────────────────────────────────────────────
# Claude OCR call
# ──────────────────────────────────────────────────────────────────────

_OCR_PROMPT = """\
Transcreva o que está escrito à mão (ou digitado) nesta foto de redação \
de aluno. Regras:

1. **A foto pode estar em qualquer orientação** (retrato, paisagem, \
de cabeça pra baixo, deitada). Identifique a orientação correta da \
escrita ANTES de transcrever — leia o texto na direção em que faz \
sentido como português.
2. Não corrija erros de gramática, ortografia ou pontuação — transcreva \
literalmente o que o aluno escreveu, mesmo se errado.
3. Se houver palavra ilegível, marque [ilegível] no lugar.
4. Se a foto não tem redação visível (capa do livro, página em branco, \
foto desfocada do teto), responda apenas: SEM_REDACAO.
5. Mantenha as quebras de parágrafo do original.
6. Não adicione comentário, cabeçalho ou rodapé seu — só o texto \
transcrito.
"""


def _image_to_base64(image: Image.Image, fmt: str = "JPEG") -> str:
    buf = io.BytesIO()
    rgb = image.convert("RGB")
    rgb.save(buf, format=fmt, quality=85)
    return base64.standard_b64encode(buf.getvalue()).decode("ascii")


_DETECT_ROTATION_PROMPT = """\
Esta foto contém um texto manuscrito ou digitado. Em quantos graus eu \
preciso rotacionar a foto (sentido horário) pra que o texto fique \
legível na orientação normal de leitura (esquerda pra direita, topo \
para baixo)?

Responda APENAS um único número entre as opções: 0, 90, 180 ou 270.
- 0 = já está na orientação correta
- 90 = girar 90° horário
- 180 = girar 180° (de cabeça pra baixo)
- 270 = girar 270° horário (= 90° anti-horário)

Não escreva nada além do número.
"""


def _detect_rotation(image: Image.Image) -> int:
    """Pergunta a Sonnet qual rotação aplicar. Retorna 0/90/180/270.

    Default é Sonnet (mais confiável que Haiku em fotos com pouco
    contraste e letra cursiva). Override via REDATO_WHATSAPP_ROTATION_MODEL.
    Custo ~$0.005. Cai no fallback 0 se a resposta vier sem dígito.
    """
    import re as _re
    import anthropic
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    model = os.getenv("REDATO_WHATSAPP_ROTATION_MODEL", "claude-sonnet-4-6")
    b64 = _image_to_base64(image)
    try:
        msg = client.messages.create(
            model=model,
            max_tokens=10,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64",
                                                 "media_type": "image/jpeg",
                                                 "data": b64}},
                    {"type": "text", "text": _DETECT_ROTATION_PROMPT},
                ],
            }],
        )
        text = ""
        for block in msg.content:
            if getattr(block, "type", None) == "text":
                text += getattr(block, "text", "") or ""
        m = _re.search(r"\b(0|90|180|270)\b", text)
        return int(m.group(1)) if m else 0
    except Exception as exc:
        # Fallback silencioso: se Haiku falhar, segue sem rotação.
        import logging as _logging
        _logging.getLogger(__name__).warning(
            "Detector de rotação falhou (%r); usando 0°.", exc
        )
        return 0


# Limiar de [ilegível] que dispara fallback de rotação. Com >3 marcações,
# Haiku provavelmente errou a orientação OU a foto está realmente ruim —
# vale a pena testar a rotação oposta antes de aceitar.
_MAX_ILEGIVEL_ANTES_DE_FALLBACK = int(os.getenv("REDATO_OCR_MAX_ILEGIVEL", "3"))


def _call_sonnet_ocr(image: Image.Image) -> str:
    """Single Sonnet OCR call. Não rotaciona."""
    import anthropic
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    model = os.getenv("REDATO_WHATSAPP_OCR_MODEL", "claude-sonnet-4-6")
    b64 = _image_to_base64(image)
    message = client.messages.create(
        model=model,
        max_tokens=2000,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64",
                                             "media_type": "image/jpeg",
                                             "data": b64}},
                {"type": "text", "text": _OCR_PROMPT},
            ],
        }],
    )
    chunks: List[str] = []
    for block in message.content:
        if getattr(block, "type", None) == "text":
            chunks.append(getattr(block, "text", "") or "")
    return "".join(chunks).strip()


def _ocr_quality_score(text: str) -> tuple[int, int]:
    """Retorna (n_ilegivel, len_text). Menor n_ilegivel = melhor."""
    return text.count("[ilegível]"), len(text)


def _claude_transcribe(image: Image.Image) -> str:
    """Pipeline: Haiku detecta rotação → Sonnet transcreve. Se transcrição
    tem muitos [ilegível], tenta rotação oposta (Haiku às vezes erra
    +90° vs -90°). Pega a melhor entre as candidatas.

    Custo no caso feliz: 1 Haiku + 1 Sonnet (~$0.006).
    Custo no caso ruim (foto difícil): 1 Haiku + 3 Sonnet (~$0.02).
    """
    rotation = _detect_rotation(image)
    # PIL.Image.rotate é anti-horário; negamos pra rotação horária.
    rot_img = image.rotate(-rotation, expand=True) if rotation else image

    text = _call_sonnet_ocr(rot_img)
    n_ileg, _ = _ocr_quality_score(text)

    if n_ileg <= _MAX_ILEGIVEL_ANTES_DE_FALLBACK:
        return text

    # Fallback: testa rotação oposta (rotation+180) e 0° (sem rotação).
    # Pega a que tem menos [ilegível]. Empate desempata por mais chars.
    candidates = [(rotation, text, n_ileg, len(text))]

    opposite = (rotation + 180) % 360
    rot_opp = image.rotate(-opposite, expand=True) if opposite else image
    text_opp = _call_sonnet_ocr(rot_opp)
    n_opp, _ = _ocr_quality_score(text_opp)
    candidates.append((opposite, text_opp, n_opp, len(text_opp)))

    if rotation != 0:
        text_zero = _call_sonnet_ocr(image)
        n_zero, _ = _ocr_quality_score(text_zero)
        candidates.append((0, text_zero, n_zero, len(text_zero)))

    # Ordena por (menor ilegível, maior len). Pega a melhor.
    candidates.sort(key=lambda c: (c[2], -c[3]))
    return candidates[0][1]


# ──────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────

def transcribe_with_quality_check(image_path: Path | str) -> OcrResult:
    """Pipeline completo: abre imagem, valida qualidade, chama OCR.

    Quality issues que impedem pipeline (rejected=True):
    - foto_escura: brilho < threshold
    - foto_borrada: variance Laplaciano < threshold
    - sem_redacao: LLM detectou que não há redação
    - texto_curto: transcrição < MIN_TRANSCRIBED_CHARS

    Aplica `ImageOps.exif_transpose` antes de tudo: iPhone salva fotos
    com orientação na tag EXIF em vez de rotacionar os pixels — sem
    isso, redação tirada em paisagem chega de lado pro Claude e o OCR
    sai corrompido.
    """
    p = Path(image_path)
    image = Image.open(p)
    image = ImageOps.exif_transpose(image)  # normaliza rotação EXIF
    metrics, issues = check_image_quality(image)

    # Rejeições locais antes de gastar API
    if "foto_escura" in issues or "foto_borrada" in issues:
        return OcrResult(
            text="",
            metrics=metrics,
            quality_issues=issues,
            rejected=True,
        )

    text = _claude_transcribe(image)

    if text.strip() == "SEM_REDACAO":
        issues.append("sem_redacao")
        return OcrResult(text="", metrics={**metrics, "n_chars": 0},
                         quality_issues=issues, rejected=True)

    n_chars = len(text)
    metrics["n_chars"] = n_chars
    if n_chars < MIN_TRANSCRIBED_CHARS:
        issues.append("texto_curto")
        return OcrResult(text=text, metrics=metrics,
                         quality_issues=issues, rejected=True)

    return OcrResult(text=text, metrics=metrics,
                     quality_issues=issues, rejected=False)


def quality_issues_to_message(issues: List[str]) -> str:
    """Mensagem WhatsApp pro aluno explicando o problema."""
    if not issues:
        return ""
    parts: List[str] = []
    if "foto_escura" in issues:
        parts.append("a foto ficou muito escura")
    if "foto_borrada" in issues:
        parts.append("a foto ficou borrada")
    if "sem_redacao" in issues:
        parts.append("não consegui ver a redação na foto")
    if "texto_curto" in issues:
        parts.append("a foto não pegou todo o texto")
    listing = ", ".join(parts) if len(parts) > 1 else parts[0]
    return (
        f"Olha, {listing}. Tira outra foto da redação inteira, "
        f"com boa luz e o celular firme. Tenta encaixar o parágrafo todo "
        f"no enquadramento."
    )
