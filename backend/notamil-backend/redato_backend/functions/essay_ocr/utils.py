from datetime import datetime

from redato_backend.shared.logger import logger
from redato_backend.shared.constants import ESSAYS_OCR_TABLE
from redato_backend.shared.bigquery import BigQueryClient
from redato_backend.functions.essay_ocr.vision.models import VisionResponse


def insert_ocr_into_bq(data: VisionResponse, user_id: str, ocr_id: str, accuracy) -> None:
    bq_client = BigQueryClient()

    data_to_insert = {
        "ocr_id": ocr_id,
        "content": data.transcription,
        "theme": data.theme,
        "accuracy": accuracy,
        "user_id": user_id,
        "loaded_at": datetime.now().date().isoformat(),
    }

    try:
        bq_client.insert(ESSAYS_OCR_TABLE, [data_to_insert])
    except Exception as e:
        logger.error(f"Failed to insert OCR into BigQuery table: {e}")
        raise e
