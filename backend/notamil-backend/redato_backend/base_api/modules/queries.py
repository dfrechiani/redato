from redato_backend.shared.constants import (
    ESSAYS_GRADED_TABLE,
    USERS_TABLE,
    ESSAYS_DETAILED_TABLE,
    ESSAYS_RAW_TABLE,
    CLASSES_TABLE,
    STUDENTS_TABLE,
    PROFESSORS_TABLE,
    COMPETENCIES_TABLE,
)

USER_DASHBOARD_QUERY = f"""
    WITH latest_15_essays AS (
        SELECT DISTINCT eg.essay_id, eg.graded_at
        FROM `{USERS_TABLE}` as u
            INNER JOIN `{ESSAYS_GRADED_TABLE}` as eg
                ON eg.user_id = u.login_id
        WHERE u.login_id = '{{login_id}}'
        ORDER BY eg.graded_at DESC
        LIMIT 15
    )
    SELECT
        eg.essay_id,
        eg.graded_at,
        theme,
        eg.overall_grade,
        ed.competency,
        c.name as competency_name,
        ed.grade
    FROM `{USERS_TABLE}` as u
        INNER JOIN `{ESSAYS_GRADED_TABLE}` as eg
            ON eg.user_id = u.login_id
        LEFT JOIN `{ESSAYS_DETAILED_TABLE}` as ed
            ON ed.essay_id = eg.essay_id
        INNER JOIN `{ESSAYS_RAW_TABLE}` as ew
            ON ew.id = eg.essay_id
        LEFT JOIN `{COMPETENCIES_TABLE}` as c
            ON ed.competency = c.id
    WHERE u.login_id = '{{login_id}}'
        AND eg.essay_id IN (SELECT essay_id FROM latest_15_essays)
    ORDER BY eg.graded_at DESC
"""  # noqa: E501

GET_CLASS_STUDENTS_QUERY = f"""
    SELECT
        u.login_id,
        u.name,
        COALESCE(AVG(eg.overall_grade), 0) AS average_grade,
    FROM `{USERS_TABLE}` AS u
    INNER JOIN `{STUDENTS_TABLE}` AS s ON s.user_id = u.login_id
    INNER JOIN `{CLASSES_TABLE}` AS c ON s.class_id = c.id
    LEFT JOIN `{ESSAYS_GRADED_TABLE}` AS eg ON s.user_id = eg.user_id
    LEFT JOIN `{ESSAYS_RAW_TABLE}` AS ew ON eg.essay_id = ew.id
    WHERE c.id = '{{class_id}}'
    GROUP BY u.login_id, u.name
    ORDER BY average_grade DESC;
"""  # noqa: E501

GET_PROFESSOR_GENERAL_PERFORMANCE_QUERY = f"""
    WITH professor_classes AS (
        SELECT
            c.id AS class_id
        FROM `{CLASSES_TABLE}` AS c
        INNER JOIN `{PROFESSORS_TABLE}` AS p ON p.user_id = c.professor_id
        WHERE p.user_id = '{{user_id}}'
    ),
    class_students AS (
        SELECT
            s.class_id,
            s.user_id
        FROM `{STUDENTS_TABLE}` AS s
        INNER JOIN professor_classes AS pc ON s.class_id = pc.class_id
    ),
    student_averages AS (
        SELECT
            s.class_id,
            s.user_id,
            COALESCE(AVG(eg.overall_grade), 0) AS student_avg_grade
        FROM class_students AS s
        LEFT JOIN `{ESSAYS_GRADED_TABLE}` AS eg ON eg.user_id = s.user_id
        GROUP BY s.class_id, s.user_id
    )

    SELECT
        c.id,
        c.name,
        ROUND(AVG(sa.student_avg_grade)) AS average_grade
        FROM `{CLASSES_TABLE}` AS c
        INNER JOIN `{PROFESSORS_TABLE}` AS p ON p.user_id = c.professor_id
        INNER JOIN student_averages AS sa ON sa.class_id = c.id
        WHERE p.user_id = '{{user_id}}'
        GROUP BY c.id, c.name
"""  # noqa: E501

GET_PROFESSOR_COMPETENCY_PERFORMANCE_QUERY = f"""
    WITH professor_classes AS (
        SELECT
            c.id AS class_id
        FROM `{CLASSES_TABLE}` AS c
        INNER JOIN `{PROFESSORS_TABLE}` AS p ON p.user_id = c.professor_id
        WHERE p.user_id = '{{user_id}}'
    ),
    class_students AS (
        SELECT
            s.class_id,
            s.user_id
        FROM `{STUDENTS_TABLE}` AS s
        INNER JOIN professor_classes AS pc ON s.class_id = pc.class_id
    ),
    student_competency_grades AS (
        SELECT
            s.class_id,
            ed.competency,
            s.user_id,
            COALESCE(AVG(ed.grade), 0) AS competency_grade
        FROM class_students AS s
        LEFT JOIN `{ESSAYS_GRADED_TABLE}` AS eg ON eg.user_id = s.user_id
        LEFT JOIN `{ESSAYS_DETAILED_TABLE}` AS ed ON eg.essay_id = ed.essay_id
        GROUP BY s.class_id, ed.competency, s.user_id
    )

    SELECT
        c.id,
        c.name,
        scg.competency,
        comp.name as competency_name,
        AVG(scg.competency_grade) AS average_grade
    FROM `{CLASSES_TABLE}` AS c
    INNER JOIN `{PROFESSORS_TABLE}` AS p ON p.user_id = c.professor_id
    LEFT JOIN student_competency_grades AS scg ON scg.class_id = c.id
    LEFT JOIN `{COMPETENCIES_TABLE}` AS comp ON scg.competency = comp.id
    WHERE p.user_id = '{{user_id}}' AND scg.competency IS NOT NULL
    GROUP BY c.id, c.name, scg.competency, comp.name
    ORDER BY average_grade DESC;
"""  # noqa: E501

GET_CLASS_COMPETENCY_PERFORMANCE_QUERY = f"""
    WITH class_students AS (
        SELECT
            user_id
        FROM `{STUDENTS_TABLE}`
        WHERE class_id = '{{class_id}}'
    ),
    all_competencies AS (
        SELECT DISTINCT competency
        FROM `{ESSAYS_DETAILED_TABLE}`
    ),
    student_competency_matrix AS (
        SELECT
            cs.user_id,
            ac.competency
        FROM class_students cs
        CROSS JOIN all_competencies ac
    ),
    student_competency_grades AS (
        SELECT
            scm.competency,
            scm.user_id,
            COALESCE(AVG(ed.grade), 0) AS competency_grade
        FROM student_competency_matrix scm
        LEFT JOIN `{ESSAYS_GRADED_TABLE}` AS eg ON eg.user_id = scm.user_id
        LEFT JOIN `{ESSAYS_DETAILED_TABLE}` AS ed
            ON eg.essay_id = ed.essay_id AND ed.competency = scm.competency
        GROUP BY scm.competency, scm.user_id
    )

    SELECT
        '{{class_id}}' AS id,
        scg.competency,
        comp.name as competency_name,
        AVG(scg.competency_grade) AS average_grade
    FROM student_competency_grades AS scg
    LEFT JOIN `{COMPETENCIES_TABLE}` AS comp ON scg.competency = comp.id
    GROUP BY scg.competency, comp.name
    ORDER BY average_grade DESC;
"""  # noqa: E501
