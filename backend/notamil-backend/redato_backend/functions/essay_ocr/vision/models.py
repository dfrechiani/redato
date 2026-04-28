from dataclasses import dataclass
from typing import Dict, List, Literal, Optional, TypedDict

import numpy as np
from pydantic import BaseModel


class VisionRequest(BaseModel):
    image: str
    user_id: str
    request_id: str
    callback_url: str


class AccuracyModel(BaseModel):
    uncertain_word_count: int
    total_word_count: int
    accuracy: float


class VisionResponse(BaseModel):
    theme: str
    transcription: str

    def to_dict(self) -> Dict:
        return self.model_dump()


class ImageContent(TypedDict):
    type: str
    source: Dict[str, str]


class ImageTranscript(TypedDict):
    image_type: str
    transcript: str


@dataclass
class ProcessedImage:
    original: np.ndarray
    # Mudança 6: pencil/pen ficam opcionais. Quando OCR_USE_ENHANCED_IMAGES=0,
    # AnthropicVisionAgent só popula `original` e items() filtra os None.
    pencil: Optional[np.ndarray] = None
    pen: Optional[np.ndarray] = None

    def items(self):
        out = {"original": self.original}
        if self.pencil is not None:
            out["pencil"] = self.pencil
        if self.pen is not None:
            out["pen"] = self.pen
        return out.items()


class VisionProcessingError(Exception):
    """Base exception for vision processing errors."""

    pass


class ImageDecodingError(VisionProcessingError):
    """Raised when image decoding fails."""

    pass


class OCRProcessingError(VisionProcessingError):
    """Raised when OCR processing fails."""


class JSONProcessingError(VisionProcessingError):
    """Raised when JSON processing fails."""

    pass


class OpusPlaceholderError(VisionProcessingError):
    """Raised when Opus emits literal `$PARAMETER_NAME` placeholder instead
    of real values in the tool_use input.

    Known issue with Opus 4.x in deeply-nested tool schemas. We fail fast
    and log rather than silently letting placeholder text reach downstream.
    """

    pass


@dataclass
class TranscriptionBlock:
    """One element of the structured transcription returned via tool call.

    Schema parallel to vision_tools.SUBMIT_TRANSCRIPTION_TOOL. Used for
    typing and round-trip serialization (blocks_to_xml_string).
    """
    type: Literal["text", "uncertain", "illegible", "paragraph_break"]
    text: str = ""
    confidence: Optional[Literal["high", "medium", "low"]] = None
    alternatives: Optional[List[str]] = None
