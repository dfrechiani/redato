from datetime import datetime
from typing import Any, Dict, List

import pytz
from fastapi import HTTPException

from redato_backend.functions.essay_function.analyzer.enforcer import Enforcer
from redato_backend.functions.essay_function.models import EssayRequestModel
from redato_backend.shared.bigquery import BigQueryClient
from redato_backend.shared.constants import (
    ESSAYS_DETAILED_TABLE,
    ESSAYS_ERRORS_TABLE,
    ESSAYS_GRADED_TABLE,
)
from redato_backend.shared.logger import logger
from redato_backend.shared.models import AnalysisResultsModel


def get_error_field(error, field, default=""):
    """
    Retrieve a field from an error object. If error is a dict, use get();
    otherwise, use getattr(). If the field is missing, return the default.
    """
    if isinstance(error, dict):
        return error.get(field, default)
    return getattr(error, field, default)


def prepare_essay_graded_row(
    essay_id: str,
    user_id: str,
    overall_grade: int,
    timestamp: str,
    feedback: str,
    essay_hash: str,
) -> Dict[str, Any]:
    return {
        "essay_id": essay_id,
        "user_id": user_id,
        "overall_grade": overall_grade,
        "graded_at": timestamp,
        "feedback": feedback,
        "hash": essay_hash,
    }


def prepare_detailed_rows(
    essay_id: str, analysis: AnalysisResultsModel, timestamp: str
) -> List[Dict[str, Any]]:
    rows = []
    for competency_id, detailed_analysis in analysis.detailed_analysis.items():
        row = {
            "essay_id": essay_id,
            "competency": competency_id,
            "detailed_analysis": detailed_analysis,
            "grade": analysis.grades.get(competency_id),
            "justification": analysis.justifications.get(competency_id, ""),
            "graded_at": timestamp,
        }
        rows.append(row)
    return rows


def prepare_specific_errors_rows(
    essay_id: str, analysis: AnalysisResultsModel, timestamp: str
) -> List[Dict[str, Any]]:
    rows = []
    for competency_id, errors_list in analysis.errors.items():
        for error in errors_list:
            row = {
                "essay_id": essay_id,
                "competency": competency_id,
                "snippet": get_error_field(error, "snippet", ""),
                "error_type": get_error_field(error, "error_type", ""),
                "description": get_error_field(error, "description", ""),
                "suggestion": get_error_field(error, "suggestion", ""),
                "graded_at": timestamp,
            }
            rows.append(row)
    return rows


def insert_essay_graded_into_bq(
    essay_id: str,
    essay_graded: AnalysisResultsModel,
    user_id: str,
    feedback: str,
    essay_hash: str,
) -> None:
    bq_client = BigQueryClient()
    try:
        timestamp = datetime.now(pytz.UTC).isoformat()
        essays_graded_row = prepare_essay_graded_row(
            essay_id,
            user_id,
            essay_graded.overall_grade,
            timestamp,
            feedback,
            essay_hash,
        )
        detailed_rows = prepare_detailed_rows(essay_id, essay_graded, timestamp)
        specific_errors_rows = prepare_specific_errors_rows(
            essay_id, essay_graded, timestamp
        )

        insert_operations = [
            (ESSAYS_GRADED_TABLE, [essays_graded_row]),
            (ESSAYS_DETAILED_TABLE, detailed_rows) if detailed_rows else None,
            (ESSAYS_ERRORS_TABLE, specific_errors_rows) if specific_errors_rows else None,
        ]

        insert_operations = [op for op in insert_operations if op is not None]

        for table_id, rows in insert_operations:
            bq_client.insert(table_id, rows)
            logger.info(
                f"Inserted {len(rows)} rows into {table_id} for Essay ID: {essay_id}"
            )

        logger.info("All essay_function graded data inserted successfully.")
    except ValueError as ve:
        logger.error(f"BigQuery insertion error: {ve}")
        raise HTTPException(
            status_code=500, detail="Failed to insert graded essay_function data."
        )
    except Exception as e:
        logger.exception(f"Unexpected error during graded essay_function insertion: {e}")
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred during graded essay_function insertion.",
        )


def validate_and_callback(data: EssayRequestModel) -> bool:
    enforcer = Enforcer()
    if not enforcer.is_essay_valid(data.content, data.theme):
        return False
    return True
