from redato_backend.shared.constants import (
    USERS_TABLE,
    SCHOOLS_TABLE,
    ESSAYS_OCR_TABLE,
    PROFESSORS_TABLE,
    THEMES_TABLE,
    CLASSES_TABLE,
    STUDENTS_TABLE,
)

SCHOOL_ID_QUERY = f"""
    SELECT
        s.id as school_id
    FROM `{SCHOOLS_TABLE}` s
    WHERE s.user_id = '{{0}}'
    LIMIT 1
"""

OCR_QUERY = f"""
    SELECT
        ocr_id,
        theme,
        content,
        accuracy

    FROM `{ESSAYS_OCR_TABLE}`
    WHERE ocr_id = '{{0}}'
    LIMIT 1
"""

USER_QUERY = f"SELECT login_id, name FROM `{USERS_TABLE}` WHERE email = '{{0}}'"

LIST_PROFESSORS_QUERY = f"""
    SELECT p.user_id, u.name, u.email
    FROM `{USERS_TABLE}` u
    INNER JOIN `{PROFESSORS_TABLE}` p
    ON u.login_id = p.user_id
    WHERE p.school_id = '{{0}}'
"""

THEMES_QUERY = f"""
    SELECT
        id,
        name,
        description,
        class_id
    FROM `{THEMES_TABLE}`
    WHERE class_id = '{{0}}'
"""

DELETE_CLASS_QUERY = f"""
    DELETE FROM `{CLASSES_TABLE}`
    WHERE id = '{{0}}'
"""

DELETE_PROFESSOR_QUERY = f"""
    DELETE FROM `{PROFESSORS_TABLE}`
    WHERE user_id = '{{0}}'
"""

DELETE_THEME_QUERY = f"""
    DELETE FROM `{THEMES_TABLE}`
    WHERE id = '{{0}}'
"""

CLASSES_QUERY = f"""
    SELECT
        c.id,
        c.name,
        c.created_at,
        p.user_id as professor_id,
        u.name as professor_name,
        u.email as professor_email
    FROM `{CLASSES_TABLE}` c
    LEFT JOIN `{PROFESSORS_TABLE}` p
        ON p.user_id = c.professor_id
    LEFT JOIN `{USERS_TABLE}` u
        ON u.login_id = p.user_id
    WHERE c.school_id = '{{0}}'
    ORDER BY c.created_at DESC
"""

UPDATE_CLASS_PROFESSOR_QUERY = f"""
    UPDATE `{CLASSES_TABLE}`
    SET professor_id = '{{0}}'
    WHERE id = '{{1}}'
"""

STUDENTS_QUERY = f"""
    SELECT
        s.user_id,
        s.created_at,
        u.name,
        u.email,
        c.name as class_name,
        c.id as class_id
    FROM `{STUDENTS_TABLE}` s
        INNER JOIN `{USERS_TABLE}` u
        ON u.login_id = s.user_id
        INNER JOIN `{CLASSES_TABLE}` c
        ON c.id = s.class_id
    WHERE s.school_id = '{{0}}'
    ORDER BY s.created_at DESC
"""

DELETE_STUDENT_QUERY = f"""
    DELETE FROM `{STUDENTS_TABLE}`
    WHERE user_id = '{{0}}'
"""

# --- INSERT Queries ---

INSERT_THEME_QUERY = f"""
    INSERT INTO {THEMES_TABLE} (id, created_at, name, description, class_id)
    VALUES ('{{0}}', TIMESTAMP('{{1}}'), '{{2}}', '{{3}}', '{{4}}')
"""

INSERT_PROFESSOR_QUERY = f"""
    INSERT INTO {PROFESSORS_TABLE} (id, user_id, created_at, school_id)
    VALUES ('{{0}}', '{{1}}', TIMESTAMP('{{2}}'), '{{3}}')
"""

INSERT_CLASS_QUERY = f"""
    INSERT INTO {CLASSES_TABLE} (id, name, school_id, professor_id, created_at)
    VALUES ('{{0}}', '{{1}}', '{{2}}', {{3}}, TIMESTAMP('{{4}}'))
"""


CLASS_ID_QUERY = f"""
    SELECT
        class_id
    FROM `{STUDENTS_TABLE}`
    WHERE user_id = '{{0}}'
    LIMIT 1
"""
