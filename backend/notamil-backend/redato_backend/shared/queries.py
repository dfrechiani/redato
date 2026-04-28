from redato_backend.shared.constants import (
    ESSAYS_DETAILED_TABLE,
    ESSAYS_ERRORS_TABLE,
    ESSAYS_GRADED_TABLE,
)

ESSAY_ANALYSIS_QUERY = f"""
    SELECT
        eg.essay_id,
        overall_grade,
        ed.competency,
        feedback,
        grade,
        justification,
        description,
        snippet,
        error_type,
        suggestion,
        ee.competency as error_competency
    FROM `{ESSAYS_GRADED_TABLE}` AS eg
        INNER JOIN `{ESSAYS_DETAILED_TABLE}` AS ed
        ON ed.essay_id = eg.essay_id
        LEFT JOIN `{ESSAYS_ERRORS_TABLE}` AS ee
        ON ee.essay_id = eg.essay_id
        AND ee.competency = ed.competency
    WHERE eg.essay_id = '{{0}}'
"""  # noqa: E501
