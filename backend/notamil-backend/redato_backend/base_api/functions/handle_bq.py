from typing import Optional, Tuple, List, Dict, Any

from datetime import datetime
from uuid import uuid4

import pytz
from redato_backend.base_api.api_routes.models import (
    UploadEssay,
)
from fastapi import HTTPException
from redato_backend.base_api.functions.models import (
    UserCreate,
    StudentCreate,
    ProfessorCreate,
    ClassCreate,
)

from redato_backend.shared.bigquery import BigQueryClient
from redato_backend.shared.constants import (
    ESSAYS_RAW_TABLE,
    USERS_TABLE,
    STUDENTS_TABLE,
)

from redato_backend.shared.logger import logger
from redato_backend.base_api.functions.queries import (
    SCHOOL_ID_QUERY,
    OCR_QUERY,
    USER_QUERY,
    LIST_PROFESSORS_QUERY,
    THEMES_QUERY,
    DELETE_CLASS_QUERY,
    DELETE_PROFESSOR_QUERY,
    DELETE_THEME_QUERY,
    CLASSES_QUERY,
    UPDATE_CLASS_PROFESSOR_QUERY,
    STUDENTS_QUERY,
    DELETE_STUDENT_QUERY,
    INSERT_THEME_QUERY,
    INSERT_PROFESSOR_QUERY,
    INSERT_CLASS_QUERY,
    CLASS_ID_QUERY,
)

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    RetryError,
)

from redato_backend.shared.firebase import FirebaseService


def log_before_retry(retry_state):
    logger.warning(
        f"Retrying BQ DML operation. Attempt: {retry_state.attempt_number}. Waited: {retry_state.outcome_timestamp - retry_state.start_time:.2f}s. Error: {retry_state.outcome}"  # noqa: E501
    )


retry_on_bq_error = retry(
    wait=wait_exponential(multiplier=1, min=2, max=8),
    stop=stop_after_attempt(3),
    before_sleep=log_before_retry,
    reraise=True,
)


def insert_user_into_bq(user: UserCreate, login_id: str) -> None:
    bq_client = BigQueryClient()
    user_to_insert = {
        "name": user.name,
        "email": user.email,
        "login_id": login_id,
        "role": user.role,
        "created_at": datetime.now(pytz.UTC).isoformat(),
    }
    try:
        bq_client.insert(USERS_TABLE, [user_to_insert])
    except Exception as e:
        logger.error(f"Error when saving user into bq: {e}")
        raise e


def get_user_info(email: str) -> Optional[Tuple[str, str]]:
    bq_client = BigQueryClient()

    try:
        user_info = bq_client.select(USER_QUERY.format(email))
        for row in user_info:
            return str(row.login_id), str(row.name)

        logger.warning(f"No user found for email: {email}")
        return None
    except Exception as e:
        logger.error(f"Failed to retrieve user_id: {e}")
        raise e


def _lookup_original_ocr_content(ocr_id: Optional[str]) -> Optional[str]:
    """Fetch the raw OCR transcription for an essay submission.

    Returns None when the essay wasn't derived from an OCR flow (e.g. the
    sentinel "text" value used for manually typed essays) or when the OCR
    row can't be found. Failure here is non-fatal — it just leaves the
    original_ocr_content column NULL for that essay.
    """
    if not ocr_id or ocr_id == "text":
        return None
    try:
        ocr_row = get_ocr_from_bq(ocr_id)
    except Exception as e:
        logger.warning(f"Failed to look up OCR content for {ocr_id}: {e}")
        return None
    if not ocr_row:
        return None
    return ocr_row.get("content")


def insert_essay_into_bq(essay: UploadEssay, essay_id: Optional[str] = None) -> str:
    bq_client = BigQueryClient()
    if essay_id is None:
        essay_id = str(uuid4())
    essay_to_insert = {
        "id": essay_id,
        "content": essay.content,
        "user_id": essay.user_id,
        "theme": essay.theme,
        "created_at": datetime.now(pytz.UTC).isoformat(),
        "ocr_id": essay.ocr_id,
        "theme_id": essay.theme_id,
        "original_ocr_content": _lookup_original_ocr_content(essay.ocr_id),
    }
    try:
        bq_client.insert(ESSAYS_RAW_TABLE, [essay_to_insert])
        logger.info(
            f"Essay successfully inserted for user {essay.user_id}, Essay ID: {essay_id}"
        )
        return essay_id
    except ValueError as ve:
        logger.error(f"BigQuery insertion error for ESSAYS_RAW_TABLE: {ve}")
        raise HTTPException(
            status_code=500, detail="Failed to insert essay_function into raw table."
        )
    except Exception as e:
        logger.exception(f"Unexpected error when saving essay_function into BQ: {e}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred.")


def get_ocr_from_bq(request_id: str):
    bq_client = BigQueryClient()

    results = bq_client.select(OCR_QUERY.format(request_id))

    for row in results:
        return {
            "ocr_id": row.ocr_id,
            "theme": row.theme,
            "content": row.content,
            "accuracy": row.accuracy,
        }


def insert_student_into_bq(student: StudentCreate) -> str:
    bq_client = BigQueryClient()
    student_to_insert = {
        "id": student.user_id,
        "created_at": datetime.now(pytz.UTC).isoformat(),
        "user_id": student.user_id,
        "class_id": student.class_id,
        "school_id": student.school_id,
    }
    try:
        bq_client.insert(STUDENTS_TABLE, [student_to_insert])
    except Exception as e:
        logger.error(f"Error when saving student into bq: {e}")


def insert_professor_into_bq(professor_data: ProfessorCreate) -> str:  # noqa: C901
    bq_client = BigQueryClient()
    created_at_iso = datetime.now(pytz.UTC).isoformat()

    insert_query = INSERT_PROFESSOR_QUERY.format(
        professor_data.user_id,
        professor_data.user_id,
        created_at_iso,
        professor_data.school_id,
    )

    @retry_on_bq_error
    def _update_class_table():
        update_query = UPDATE_CLASS_PROFESSOR_QUERY.format(
            professor_data.user_id, professor_data.class_id
        )
        bq_client.execute_query(update_query)
        logger.info(
            f"CLASSES_TABLE updated for class_id: {professor_data.class_id} with professor_id: {professor_data.user_id}"  # noqa: E501
        )

    try:
        bq_client.execute_query(insert_query)
        logger.info(
            f"Professor record inserted via SQL into PROFESSORS_TABLE with user_id: {professor_data.user_id}"  # noqa: E501
        )

        if professor_data.class_id and professor_data.user_id:
            try:
                _update_class_table()
            except RetryError as retry_err:
                logger.error(
                    f"Failed to update CLASSES_TABLE for class {professor_data.class_id} with prof {professor_data.user_id} after multiple retries: {retry_err}"  # noqa: E501
                )
                raise HTTPException(
                    status_code=500,
                    detail="Failed to update class assignment after multiple retries due to transient BigQuery errors.",  # noqa: E501
                ) from retry_err
            except Exception as e_update:
                logger.error(
                    f"Failed to update CLASSES_TABLE for class {professor_data.class_id} with prof {professor_data.user_id}: {e_update}"  # noqa: E501
                )
                raise HTTPException(
                    status_code=500, detail="Failed to update class assignment."
                ) from e_update
        else:
            logger.warning(
                f"Skipping CLASSES_TABLE update for professor user_id {professor_data.user_id} due to missing class_id or user_id."  # noqa: E501
            )

        return professor_data.user_id

    except Exception as e:
        logger.error(f"Error during professor SQL insertion/class update process: {e}")
        if not isinstance(e, HTTPException):
            raise HTTPException(
                status_code=500, detail="Failed to process professor assignment via SQL."
            ) from e
        else:
            raise


def get_school_id(login_id: str) -> str:
    bq_client = BigQueryClient()
    try:
        results = bq_client.select(SCHOOL_ID_QUERY.format(login_id))
        for row in results:
            return str(row.school_id)
    except Exception as e:
        logger.error(f"Error when getting school_id from bq: {e}")
        raise e


def get_professors_from_bq(school_id: str) -> list:
    bq_client = BigQueryClient()
    try:
        results = bq_client.select(LIST_PROFESSORS_QUERY.format(school_id))

        professors = []
        for row in results:
            professors.append(
                {
                    "professor_id": row.user_id,
                    "name": row.name,
                    "email": row.email,
                }
            )

        return professors
    except Exception as e:
        logger.error(f"Error when fetching professors from BigQuery: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch professors.")


def insert_theme_into_bq(theme: str, description: str, class_id: str):
    bq_client = BigQueryClient()
    theme_id = str(uuid4())
    created_at_iso = datetime.now(pytz.UTC).isoformat()

    safe_theme = theme.replace("'", "\\'")
    safe_description = description.replace("'", "\\'")

    insert_query = INSERT_THEME_QUERY.format(
        theme_id, created_at_iso, safe_theme, safe_description, class_id
    )

    try:
        bq_client.execute_query(insert_query)
        logger.info(f"Theme {theme_id} inserted via SQL for class {class_id}")
    except Exception as e:
        logger.error(f"Error when saving theme into bq via SQL: {e}")


def get_themes_from_bq(class_id: str) -> List[Dict[str, Any]]:
    bq_client = BigQueryClient()
    try:
        results = bq_client.select(THEMES_QUERY.format(class_id))
        themes = []
        for row in results:
            themes.append(
                {
                    "id": row.id,
                    "name": row.name,
                    "description": row.description,
                    "class_id": row.class_id,
                }
            )
        return themes
    except Exception as e:
        logger.error(f"Error when fetching themes from bq: {e}")


def insert_class_into_bq(class_data: ClassCreate) -> str:
    bq_client = BigQueryClient()
    class_id = str(uuid4())
    created_at_iso = datetime.now(pytz.UTC).isoformat()

    safe_name = class_data.name.replace("'", "\\'")

    sql_professor_id = (
        f"'{class_data.professor_id}'" if class_data.professor_id else "NULL"
    )

    insert_query = INSERT_CLASS_QUERY.format(
        class_id, safe_name, class_data.school_id, sql_professor_id, created_at_iso
    )

    try:
        bq_client.execute_query(insert_query)
        logger.info(f"Class successfully inserted via SQL: {class_id}")
        return class_id
    except Exception as e:
        logger.error(f"Error when saving class into bq via SQL: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to insert class via SQL."
        ) from e


@retry_on_bq_error
def delete_class_from_bq(class_id: str) -> None:
    bq_client = BigQueryClient()
    try:
        bq_client.execute_query(DELETE_CLASS_QUERY.format(class_id))
        logger.info(f"Class successfully deleted: {class_id}")
    except RetryError as retry_err:  # Catch tenacity error specifically
        logger.error(
            f"Failed to delete class {class_id} after multiple retries: {retry_err}"
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to delete class after multiple retries due to transient BigQuery errors.",  # noqa: E501
        ) from retry_err
    except Exception as e:
        logger.error(f"Error when deleting class {class_id}: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to delete class from table."
        ) from e


@retry_on_bq_error
def delete_professor_from_bq(  # noqa: C901
    professor_id: str, firebase_service: FirebaseService
) -> None:
    bq_client = BigQueryClient()
    try:
        bq_client.execute_query(DELETE_PROFESSOR_QUERY.format(professor_id))
        logger.info(
            f"Professor successfully deleted from BigQuery, user_id: {professor_id}"  # noqa: E501
        )

        try:
            firebase_service.delete_user(professor_id)
        except HTTPException as fb_http_exc:
            logger.error(
                f"Failed to delete professor {professor_id} from Firebase after deleting from BQ: {fb_http_exc.detail}"  # noqa: E501
            )
        except Exception as fb_exc:
            logger.error(
                f"Unexpected error deleting professor {professor_id} from Firebase: {fb_exc}"  # noqa: E501
            )

    except RetryError as retry_err:
        logger.error(
            f"Failed to delete professor (BQ ID {professor_id}) from BigQuery after multiple retries: {retry_err}"  # noqa: E501
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to delete professor from BigQuery after multiple retries due to transient BigQuery errors.",  # noqa: E501
        ) from retry_err
    except Exception as e:
        logger.error(
            f"Error during professor deletion process (BQ ID {professor_id}): {e}"
        )
        if not isinstance(e, HTTPException):
            raise HTTPException(
                status_code=500, detail="Failed to delete professor data."
            ) from e
        else:
            raise


@retry_on_bq_error
def delete_theme_from_bq(theme_id: str) -> None:
    bq_client = BigQueryClient()
    try:
        bq_client.execute_query(DELETE_THEME_QUERY.format(theme_id))
        logger.info(f"Theme successfully deleted: {theme_id}")
    except RetryError as retry_err:
        logger.error(
            f"Failed to delete theme {theme_id} after multiple retries: {retry_err}"
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to delete theme after multiple retries due to transient BigQuery errors.",  # noqa: E501
        ) from retry_err
    except Exception as e:
        logger.error(f"Error when deleting theme {theme_id}: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to delete theme from table."
        ) from e


def get_classes_from_bq(school_id: str) -> List[Dict[str, Any]]:
    bq_client = BigQueryClient()
    try:
        results = bq_client.select(CLASSES_QUERY.format(school_id))
        classes = []
        for row in results:
            classes.append(
                {
                    "class_id": row.id,
                    "name": row.name,
                    "created_at": row.created_at,
                    "professor_id": row.professor_id,
                    "professor_name": row.professor_name,
                    "professor_email": row.professor_email,
                }
            )
        return classes
    except Exception as e:
        logger.error(f"Error when fetching classes from bq: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch classes.")


def get_students_from_bq(school_id: str) -> List[Dict[str, Any]]:
    bq_client = BigQueryClient()
    try:
        results = bq_client.select(STUDENTS_QUERY.format(school_id))
        students = []
        for row in results:
            students.append(
                {
                    "student_id": row.user_id,
                    "name": row.name,
                    "email": row.email,
                    "class_id": row.class_id,
                    "class_name": row.class_name,
                    "created_at": row.created_at,
                }
            )
        return students
    except Exception as e:
        logger.error(f"Error when fetching students from bq: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch students.")


@retry_on_bq_error
def delete_student_from_bq(  # noqa: C901
    student_id: str, firebase_service: FirebaseService
) -> None:
    bq_client = BigQueryClient()
    try:
        bq_client.execute_query(DELETE_STUDENT_QUERY.format(student_id))
        logger.info(f"Student successfully deleted from BigQuery: User ID {student_id}")

        try:
            firebase_service.delete_user(student_id)
        except HTTPException as fb_http_exc:
            logger.error(
                f"Failed to delete student {student_id} from Firebase after deleting from BQ: {fb_http_exc.detail}"  # noqa: E501
            )
        except Exception as fb_exc:
            logger.error(
                f"Unexpected error deleting student {student_id} from Firebase: {fb_exc}"
            )

    except RetryError as retry_err:
        logger.error(
            f"Failed to delete student {student_id} from BigQuery after multiple retries: {retry_err}"  # noqa: E501
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to delete student from BigQuery after multiple retries due to transient BigQuery errors.",  # noqa: E501
        ) from retry_err
    except Exception as e:
        logger.error(f"Error during student deletion process (User ID {student_id}): {e}")
        if not isinstance(e, HTTPException):
            raise HTTPException(
                status_code=500, detail="Failed to delete student data."
            ) from e
        else:
            raise


@retry_on_bq_error
def update_professor_in_class(class_id: str, professor_id: str) -> None:
    bq_client = BigQueryClient()
    try:
        update_query = UPDATE_CLASS_PROFESSOR_QUERY.format(professor_id, class_id)
        bq_client.execute_query(update_query)
        logger.info(f"Professor {professor_id} successfully updated in class: {class_id}")
    except RetryError as retry_err:
        logger.error(
            f"Failed to update professor {professor_id} in class {class_id} after multiple retries: {retry_err}"  # noqa: E501
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to update professor in class after multiple retries due to transient BigQuery errors.",  # noqa: E501
        ) from retry_err
    except Exception as e:
        logger.error(
            f"Error when updating professor {professor_id} in class {class_id}: {e}"
        )
        raise HTTPException(
            status_code=500, detail="Failed to update professor in class."
        ) from e


def get_class_id(login_id: str) -> str:
    bq_client = BigQueryClient()
    try:
        results = bq_client.select(CLASS_ID_QUERY.format(login_id))
        for row in results:
            return str(row.class_id)
    except Exception as e:
        logger.error(f"Error when getting class_id from bq: {e}")
        raise HTTPException(status_code=500, detail="Failed to get class_id.")
