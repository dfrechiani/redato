import hashlib

from typing import Optional

from redato_backend.shared.bigquery import BigQueryClient
from redato_backend.shared.constants import (
    COMPETENCIES,
    ESSAYS_GRADED_TABLE,
    ESSAYS_RAW_TABLE,
)
from redato_backend.shared.logger import logger
from redato_backend.shared.queries import ESSAY_ANALYSIS_QUERY


def get_analysis_from_bq(request_id: str):  # noqa: C901
    bq_client = BigQueryClient()

    results = bq_client.select(ESSAY_ANALYSIS_QUERY.format(request_id))

    grouped = {}
    overall_grade = None
    feedback = None

    for row in results:
        overall_grade = row.overall_grade
        feedback = row.feedback
        comp_key = row.competency

        if comp_key not in grouped:
            grouped[comp_key] = {
                "grade": row.grade,
                "justification": row.justification,
                "errors": [],
            }

        if row.error_type:
            error_item = {
                "description": row.description,
                "snippet": row.snippet,
                "error_type": row.error_type,
                "suggestion": row.suggestion,
            }
            grouped[comp_key]["errors"].append(error_item)

    competencies_list = []
    for key, data in grouped.items():
        mapped_name = COMPETENCIES.get(key, key)
        competencies_list.append(
            {
                "competency": mapped_name,
                "grade": data["grade"],
                "justification": data["justification"],
                "errors": data["errors"],
            }
        )

    desired_order = [
        "Domínio da Norma Culta",
        "Compreensão do Tema",
        "Seleção e Organização das Informações",
        "Conhecimento dos Mecanismos Linguísticos",
        "Proposta de Intervenção",
    ]

    competencies_list.sort(
        key=lambda x: (
            desired_order.index(x["competency"])
            if x["competency"] in desired_order
            else float("inf")
        )
    )

    return {
        "request_id": request_id,
        "overall_grade": overall_grade,
        "detailed_analysis": feedback,
        "competencies": competencies_list,
    }


def get_essay_from_bq(essay_id: str):
    bq_client = BigQueryClient()

    query = f"""
        SELECT
            id,
            created_at,
            theme,
            content,
            original_ocr_content
        FROM `{ESSAYS_RAW_TABLE}`
        WHERE id = '{essay_id}'
        LIMIT 1
    """

    results = bq_client.select(query)
    for row in results:
        return {
            "content": row.content,
            "theme": row.theme,
            "created_at": row.created_at,
            "original_ocr_content": row.original_ocr_content,
        }


def generate_essay_hash(content: str) -> str:
    essay_hash = hashlib.sha256(content.strip().lower().encode("utf-8")).hexdigest()
    return str(essay_hash)


def get_graded_essay_by_hash(essay_content: str) -> Optional[str]:
    """
    Compute the essay hash from the content and query BigQuery for an existing analysis.
    """
    essay_hash = generate_essay_hash(essay_content)

    bq_client = BigQueryClient()
    query = f"""
        SELECT essay_id
        FROM `{ESSAYS_GRADED_TABLE}` as eg
        WHERE eg.hash = '{essay_hash}'
        LIMIT 1
    """
    try:
        results = bq_client.select(query)
        for row in results:
            # Return only the essay_id from the graded analysis.
            return row.essay_id
    except Exception as e:
        logger.error(f"Error querying essay by hash: {e}")

    return None
