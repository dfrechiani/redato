import json
from typing import List, Optional, Tuple, Union

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from anthropic import Anthropic
from redato_backend.functions.essay_ocr.vision.image_processor import ImageProcessor
from redato_backend.functions.essay_ocr.vision.format_specs.models import ImageFormat
from redato_backend.functions.essay_ocr.vision.models import (
    ImageContent,
    ImageDecodingError,
    ImageTranscript,
    OCRProcessingError,
    ProcessedImage,
    VisionProcessingError,
    VisionResponse,
    AccuracyModel,
)
from redato_backend.functions.essay_ocr.vision.prompts import (
    VISION_SYSTEM_PROMPT,
    VISION_USER_PROMPT,
)
from redato_backend.functions.essay_ocr.vision.vision_tools import (
    ImageDecoder,
    JSONProcessor,
    calculate_accuracy,
)

from redato_backend.shared.constants import (
    ANTHROPIC_API_KEY,
    ANTHROPIC_CLAUDE_MODEL,
    OCR_USE_CLOUD_VISION,
    OCR_USE_ENHANCED_IMAGES,
)
from redato_backend.shared.logger import logger

# Import lazy: só carrega o SDK do Cloud Vision se a flag estiver ativa.
# Default OFF (Mudança 5) — evita peso desnecessário em dev/CI sem GCP.
if OCR_USE_CLOUD_VISION:
    from google.cloud import vision  # noqa: F401  (usado por OCRProcessor abaixo)


class OCRProcessor:
    # Type annotation com string evita avaliar `vision.ImageAnnotatorClient`
    # quando OCR_USE_CLOUD_VISION=False (módulo `vision` não foi importado).
    def __init__(self, vision_client: "vision.ImageAnnotatorClient"):
        self.vision_client = vision_client

    def process_image(self, image_input: str) -> str:
        """
        Process an image with Google Cloud Vision OCR.

        Args:
            image_input: Base64 encoded image

        Returns:
            Extracted text from the image
        """
        if not image_input:
            raise OCRProcessingError("OCRProcessor: Image input is required")

        try:
            image = vision.Image(content=image_input)
            response = self.vision_client.text_detection(image=image)

            if not response:
                raise OCRProcessingError("No response from Cloud Vision API")

            texts = response.text_annotations
            if not texts:
                logger.warning("No text detected in image")
                return ""

            return texts[0].description if texts else ""

        except Exception as e:
            logger.error(f"Unexpected error in OCR processing: {str(e)}")
            raise OCRProcessingError("Failed to process image with OCR") from e


class AnthropicVisionAgent:
    def __init__(
        self, image_encoded: str, image_format: Optional[Union[str, ImageFormat]] = None
    ):
        """
        Initialize the Anthropic Vision Agent.

        Args:
            image_encoded: Base64 encoded image
            image_format: Optional format override (string or ImageFormat enum)
        """
        self.anthropic = Anthropic(api_key=ANTHROPIC_API_KEY)
        # Mudança 5: só instancia Cloud Vision quando OCR_USE_CLOUD_VISION=1.
        # No default (=0), pula o setup pra evitar carregar SDK e exigir creds.
        if OCR_USE_CLOUD_VISION:
            self.cloud_vision = vision.ImageAnnotatorClient()
            self.ocr_processor = OCRProcessor(self.cloud_vision)
        else:
            self.cloud_vision = None
            self.ocr_processor = None
        self.json_processor = JSONProcessor()
        self.image_decoder = ImageDecoder()

        try:
            original_image, detected_format = self.image_decoder.decode_base64(
                image_encoded
            )

            if image_format is not None:
                if isinstance(image_format, str):
                    self.image_format = ImageFormat.from_string(image_format)
                else:
                    self.image_format = image_format
            else:
                self.image_format = detected_format

            # Mudança 6: só gera enhanced versions quando flag=1. Default "1"
            # mantém comportamento atual; A/B define se vale o custo
            # (latência 3× nas chamadas Claude por enviar 3 imagens).
            if OCR_USE_ENHANCED_IMAGES:
                img_processor = ImageProcessor()
                self.processed_images = ProcessedImage(
                    original=original_image,
                    pencil=img_processor.enhance_for_pencil(original_image.copy()),
                    pen=img_processor.enhance_for_pen(original_image.copy()),
                )
            else:
                self.processed_images = ProcessedImage(original=original_image)

            logger.info(
                f"Processed image with format: {self.image_format}, "
                f"enhanced={OCR_USE_ENHANCED_IMAGES}"
            )

        except Exception as e:
            logger.error(f"Failed to initialize image processing: {str(e)}")
            raise ImageDecodingError("Failed to initialize image processing") from e

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception),
        before_sleep=lambda retry_state: logger.info(
            f"Retry attempt {retry_state.attempt_number} after error, "
            f"waiting {retry_state.next_action.sleep} seconds..."
        ),
    )
    def _call_vision_api(self, user_content):
        """
        Call the vision API with retry logic using tenacity.

        Args:
            user_content: The content to send to the vision model

        Returns:
            The model response
        """
        logger.info(f"Calling Anthropic Vision API with model: {ANTHROPIC_CLAUDE_MODEL}")
        try:
            kwargs = dict(
                model=ANTHROPIC_CLAUDE_MODEL,
                max_tokens=4096,
                system=VISION_SYSTEM_PROMPT,
                messages=[
                    {
                        "role": "user",
                        "content": user_content,
                    }
                ],
            )
            # temperature foi descontinuada para Opus 4+. Manter apenas em modelos
            # que ainda aceitam (Sonnet/Haiku 4.x). Opus rejeita com 400.
            if not ANTHROPIC_CLAUDE_MODEL.startswith("claude-opus-4"):
                kwargs["temperature"] = 0
            response = self.anthropic.messages.create(**kwargs)
        except Exception as e:
            logger.error(f"Error calling Anthropic Vision API: {str(e)}")
            raise e

        if not response or not response.content:
            raise VisionProcessingError("Empty response from Claude")

        stop_reason = getattr(response, "stop_reason", "?")
        usage = getattr(response, "usage", None)
        in_tok = getattr(usage, "input_tokens", "?") if usage else "?"
        out_tok = getattr(usage, "output_tokens", "?") if usage else "?"
        logger.info(
            f"Anthropic Vision response: stop_reason={stop_reason} "
            f"input_tokens={in_tok} output_tokens={out_tok}"
        )
        if stop_reason == "max_tokens":
            logger.warning(
                "Vision call hit max_tokens — output truncated. "
                "Consider raising max_tokens or splitting input."
            )

        return response

    def process_with_claude(
        self,
        image_contents: List[ImageContent],
        images_transcripts: List[ImageTranscript],
    ) -> VisionResponse:
        """
        Process images with Claude Vision API using tenacity retry.

        Args:
            image_contents: List of image content objects
            images_transcripts: List of image transcript objects

        Returns:
            Claude Vision API response
        """
        if not image_contents or not images_transcripts:
            raise VisionProcessingError("No image content or transcripts provided")

        user_content = [
            {
                "type": "text",
                "text": VISION_USER_PROMPT.format(
                    transcript=json.dumps(images_transcripts, indent=2)
                ),
            },
            *image_contents,
        ]

        try:
            response = self._call_vision_api(user_content)
            return VisionResponse(
                **self.json_processor.extract_json(response.content[0].text)
            )
        except Exception as e:
            logger.error(f"Claude Vision API processing failed after retries: {str(e)}")
            raise VisionProcessingError(
                f"Failed to process with Claude Vision API: {str(e)}"
            ) from e

    def deploy(self) -> Tuple[VisionResponse, AccuracyModel]:
        """
        Deploy the vision processing pipeline.

        Returns:
            Tuple of (VisionResponse, AccuracyModel)
        """
        try:
            image_contents: List[ImageContent] = []
            images_transcripts: List[ImageTranscript] = []

            # Mantemos VISION_USER_PROMPT (com placeholder {transcript}) mesmo
            # quando Cloud Vision está OFF. A/B Mudança 5 (n=2 × 5 redações)
            # mostrou que esse prompt comparativo, mesmo com transcript vazio,
            # produz resultados melhores que VISION_USER_PROMPT_SOLO (-1.6 pts
            # médio em 4/5 redações). Hipótese: detalhe + exemplos no prompt
            # comparativo calibram o modelo mesmo sem OCR de referência real.
            for image_type, image in self.processed_images.items():
                encoded = self.image_decoder.encode_image(image, self.image_format)

                if OCR_USE_CLOUD_VISION:
                    cloud_vision_response = self.ocr_processor.process_image(encoded)
                else:
                    cloud_vision_response = ""

                images_transcripts.append(
                    {"image_type": image_type, "transcript": cloud_vision_response}
                )

                media_type = self.image_decoder.get_mime_type(self.image_format)

                image_contents.append(
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": encoded,
                        },
                    }
                )

            transcription = self.process_with_claude(image_contents, images_transcripts)
            ocr_accuracy = calculate_accuracy(transcription.transcription)

            return transcription, ocr_accuracy

        except Exception as e:
            logger.error(f"Unexpected error in vision processing pipeline: {str(e)}")
            raise VisionProcessingError(f"Vision processing failed: {str(e)}")
