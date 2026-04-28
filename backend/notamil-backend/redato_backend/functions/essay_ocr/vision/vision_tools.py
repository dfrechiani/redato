import imghdr
import base64

# cv2 só é usado em ImageDecoder (decode/encode de imagem). Mantemos como
# import lazy pra que SUBMIT_TRANSCRIPTION_TOOL/blocks_to_xml_string
# possam ser importados/testados sem opencv instalado (dev-offline).
import numpy as np

from redato_backend.shared.logger import logger
from redato_backend.functions.essay_ocr.vision.models import (
    ImageDecodingError,
    JSONProcessingError,
    AccuracyModel,
)
from redato_backend.functions.essay_ocr.vision.format_specs.models import (
    ImageFormat,
    FORMAT_SPECS,
    IMGHDR_TO_FORMAT,
    FormatSpec,
)

import json
import re
from typing import Any, Dict, List, Union, Optional, Tuple

# Re-export pra ergonomia: SUBMIT_TRANSCRIPTION_TOOL e blocks_to_xml_string
# vivem em transcription_blocks.py (livre de deps GCP/cv2). Manter aqui
# o mesmo nome de import que o anthropic_vision.py espera.
from redato_backend.functions.essay_ocr.vision.transcription_blocks import (
    SUBMIT_TRANSCRIPTION_TOOL,
    blocks_to_xml_string,
)


class JSONProcessor:
    """Parser do JSON com tags XML embutidas vindo do Claude Vision.

    Em campo (n=5/5 redações), o modelo emite literais `\\n` não escapados
    dentro do campo `transcription`. Por isso `extract_json` usa
    `json.loads(strict=False)` por padrão — aceita control chars em strings.
    Mudança 4 (tool_use estruturado) foi avaliada e revertida em 2026-04-25
    por induzir hipersensibilidade. Infra do tool_use preservada em
    `transcription_blocks.py` para retomada futura com dataset real.
    """

    @staticmethod
    def escape_control_characters(json_str: str) -> str:
        def replacer(match: re.Match) -> str:
            # match.group(0) is the full quoted string; group(1) is its content.
            content = match.group(1)
            # Replace literal newlines and carriage returns with escaped versions.
            content = content.replace("\n", "\\n").replace("\r", "\\r")
            return f'"{content}"'

        # This regex matches a JSON string literal.
        return re.sub(r'"((?:\\.|[^"\\])*)"', replacer, json_str)

    @staticmethod
    def preprocess_json_string(json_str: str) -> str:
        def escape_xml_attributes(match: re.Match) -> str:
            tag = match.group(0)
            return re.sub(
                r'confidence="([^"]*)"', lambda m: f'confidence=\\"{m.group(1)}\\"', tag
            )

        json_str = re.sub(r',\s*\n\s*"', ', "', json_str)

        # Handle XML tags
        json_str = re.sub(
            r"<uncertain[^>]+>[^<]+</uncertain>", escape_xml_attributes, json_str
        )

        processed_chars = []
        in_transcription = False
        current_token = ""

        for char in json_str:
            if current_token.endswith('"transcription": "'):
                in_transcription = True
            elif in_transcription and char == '"' and not current_token.endswith("\\"):
                in_transcription = False

            if in_transcription and char == '"' and not current_token.endswith("\\"):
                processed_chars.append('\\"')
            else:
                processed_chars.append(char)
            current_token += char

        return "".join(processed_chars)

    @staticmethod
    def extract_json(response: str) -> Dict[str, Any]:  # noqa: C901
        try:
            match = re.search(r"(\{[\s\S]*\})", response.strip())
            if not match:
                raise JSONProcessingError("No JSON object found in response")

            json_str = match.group(1)
            json_str = JSONProcessor.escape_control_characters(json_str)

            # strict=False: aceita control chars (\n, \t literal) dentro de
            # strings JSON. Modelo emite \n não-escapados na transcription
            # com frequência. Sem isso, ~5/5 redações falham parse.
            try:
                data = json.loads(json_str, strict=False)
            except json.JSONDecodeError:
                processed_json = JSONProcessor.preprocess_json_string(json_str)
                try:
                    data = json.loads(processed_json, strict=False)
                except json.JSONDecodeError:
                    cleaned_json = re.sub(r"[ \t]+", " ", processed_json)
                    data = json.loads(cleaned_json, strict=False)
            return data

        except Exception as e:
            raise JSONProcessingError(
                f"Failed to parse JSON: {str(e)}\nResponse text: {response[:200]}..."
            )


class ImageDecoder:
    """
    Enhanced image decoder/encoder with support for multiple image formats.
    """

    BASE64_HEADER_PATTERN = re.compile(r"^data:image/([a-zA-Z0-9+.-]+);base64,")

    @classmethod
    def get_format_spec(cls, fmt: Union[str, ImageFormat]) -> FormatSpec:
        """
        Get format specification for a format.

        Args:
            fmt: Format string or enum

        Returns:
            FormatSpec object
        """
        if isinstance(fmt, str):
            fmt = ImageFormat.from_string(fmt)

        return FORMAT_SPECS.get(fmt, FORMAT_SPECS[ImageFormat.JPEG])

    @classmethod
    def detect_format_from_base64(cls, image_encoded: str) -> ImageFormat:  # noqa: C901
        """
        Detect image format from base64 string header or content.

        Args:
            image_encoded: Base64 encoded image

        Returns:
            Detected ImageFormat
        """
        header_match = cls.BASE64_HEADER_PATTERN.match(image_encoded)
        if header_match:
            mime_format = header_match.group(1).lower()
            base64_data = image_encoded[header_match.end() :]  # noqa: E203

            for fmt, spec in FORMAT_SPECS.items():
                if spec.mime_type.endswith(f"/{mime_format}"):
                    return fmt
        else:
            base64_data = image_encoded

        try:
            binary_data = base64.b64decode(base64_data)

            detected = imghdr.what(None, h=binary_data)
            if detected and detected in IMGHDR_TO_FORMAT:
                return IMGHDR_TO_FORMAT[detected]
        except Exception as e:
            logger.error(f"ImageDecoder Error: {e}")
            pass

        return ImageFormat.JPEG

    @classmethod
    def decode_base64(cls, image_encoded: str) -> Tuple[np.ndarray, ImageFormat]:
        """
        Decode a base64-encoded image to OpenCV format while detecting its format.

        Args:
            image_encoded: Base64 encoded image string

        Returns:
            Tuple of (decoded_image, detected_format)
        """
        try:
            header_match = cls.BASE64_HEADER_PATTERN.match(image_encoded)
            if header_match:
                base64_data = image_encoded[header_match.end() :]  # noqa: E203
            else:
                base64_data = image_encoded

            detected_format = cls.detect_format_from_base64(image_encoded)

            binary_data = base64.b64decode(base64_data)

            import cv2  # lazy: só carrega no caminho que usa
            np_arr = np.frombuffer(binary_data, np.uint8)
            image = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

            if image is None:
                raise ImageDecodingError("Failed to decode image from base64 string")

            return image, detected_format

        except Exception as e:
            if isinstance(e, ImageDecodingError):
                raise
            raise ImageDecodingError(f"Failed to decode image: {str(e)}")

    @classmethod
    def encode_image(
        cls,
        image: np.ndarray,
        fmt: Union[str, ImageFormat] = ImageFormat.JPEG,
        quality: Optional[int] = None,
    ) -> str:
        """
        Encode an OpenCV image to base64 in the specified format.

        Args:
            image: OpenCV image as numpy array
            fmt: Format to encode as (enum or string)
            quality: Optional quality setting (overrides default)

        Returns:
            Base64-encoded image string
        """
        try:
            if isinstance(fmt, str):
                fmt = ImageFormat.from_string(fmt)

            format_spec = cls.get_format_spec(fmt)

            encode_params = format_spec.get_encoding_params(quality)

            import cv2  # lazy
            success, encoded_image = cv2.imencode(
                format_spec.extension, image, encode_params
            )

            if not success:
                raise ImageDecodingError(f"Failed to encode image to {fmt}")

            return base64.b64encode(encoded_image.tobytes()).decode("utf-8")

        except Exception as e:
            if isinstance(e, ImageDecodingError):
                raise
            raise ImageDecodingError(f"Failed to encode image: {str(e)}")

    @classmethod
    def get_mime_type(cls, fmt: Union[str, ImageFormat]) -> str:
        """
        Get the MIME type for a format.

        Args:
            fmt: Format enum or string

        Returns:
            MIME type string
        """
        format_spec = cls.get_format_spec(fmt)
        return format_spec.mime_type


def calculate_accuracy(transcription: str) -> AccuracyModel:
    words = transcription.split()
    total_words = len(words)

    uncertain_word_count = len(re.findall(r"<uncertain\b", transcription))

    if total_words == 0:
        computed_accuracy = 0.0
    else:
        computed_accuracy = ((total_words - uncertain_word_count) / total_words) * 100

    return AccuracyModel(
        uncertain_word_count=uncertain_word_count,
        total_word_count=total_words,
        accuracy=computed_accuracy,
    )
