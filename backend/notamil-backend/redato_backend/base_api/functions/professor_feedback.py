from typing import Any, Dict, Optional

from google.cloud import bigquery

from redato_backend.shared.bigquery import BigQueryClient
from redato_backend.shared.constants import PROFESSOR_CORRECTIONS_TABLE
from redato_backend.shared.logger import logger


def upsert_professor_feedback(
    essay_id: str, professor_id: str, feedback_text: str
) -> None:
    """Insert or update the professor feedback row for a given essay.

    Uses a parameterized MERGE so the essay ends up with exactly one active
    feedback row. Parameters avoid SQL-injection from free-text feedback.
    """
    bq_client = BigQueryClient()
    query = f"""
        MERGE `{PROFESSOR_CORRECTIONS_TABLE}` AS T
        USING (
            SELECT
                @essay_id AS essay_id,
                @professor_id AS professor_id,
                @feedback_text AS feedback_text,
                CURRENT_TIMESTAMP() AS now
        ) AS S
        ON T.essay_id = S.essay_id
        WHEN MATCHED THEN
            UPDATE SET
                feedback_text = S.feedback_text,
                professor_id = S.professor_id,
                updated_at = S.now
        WHEN NOT MATCHED THEN
            INSERT (id, essay_id, professor_id, feedback_text, created_at, updated_at)
            VALUES (
                GENERATE_UUID(),
                S.essay_id,
                S.professor_id,
                S.feedback_text,
                S.now,
                S.now
            )
    """
    params = [
        bigquery.ScalarQueryParameter("essay_id", "STRING", essay_id),
        bigquery.ScalarQueryParameter("professor_id", "STRING", professor_id),
        bigquery.ScalarQueryParameter("feedback_text", "STRING", feedback_text),
    ]
    bq_client.execute_query(query, query_params=params)
    logger.info(
        f"Upserted professor feedback for essay {essay_id} by professor {professor_id}"
    )


def get_professor_feedback(essay_id: str) -> Optional[Dict[str, Any]]:
    """Return the current feedback row for an essay, or None if none exists."""
    bq_client = BigQueryClient()
    query = f"""
        SELECT
            essay_id,
            professor_id,
            feedback_text,
            created_at,
            updated_at
        FROM `{PROFESSOR_CORRECTIONS_TABLE}`
        WHERE essay_id = @essay_id
        LIMIT 1
    """
    params = [bigquery.ScalarQueryParameter("essay_id", "STRING", essay_id)]
    try:
        results = bq_client.select_with_params(query, params)
        for row in results:
            return {
                "essay_id": row.essay_id,
                "professor_id": row.professor_id,
                "feedback_text": row.feedback_text,
                "created_at": (
                    row.created_at.isoformat() if row.created_at else None
                ),
                "updated_at": (
                    row.updated_at.isoformat() if row.updated_at else None
                ),
            }
    except Exception as e:
        logger.error(f"Error fetching professor feedback for {essay_id}: {e}")
        raise
    return None
