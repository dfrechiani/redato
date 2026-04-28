from redato_backend.base_api.functions.models import (
    StudentCreate,
    UserCreate,
    ProfessorCreate,
    UserRole,
)
from redato_backend.base_api.functions.utils import generate_password
import pandas as pd

from redato_backend.shared.logger import logger
from redato_backend.shared.firebase import FirebaseService
from redato_backend.base_api.functions.handle_bq import (
    insert_user_into_bq,
    insert_student_into_bq,
    insert_professor_into_bq,
)


def register_user(user: UserCreate, firebase_service: FirebaseService) -> str:
    try:

        firebase_user = firebase_service.create_user(
            email=user.email, password=user.password, role=user.role
        )

        insert_user_into_bq(user, firebase_user["uid"])
        logger.info(
            f"User successfully created with email: {firebase_user['email']} "
            f"and role: {firebase_user['role']}"
        )

        return firebase_user["uid"]
    except Exception as e:
        logger.error(f"Error when registering user: {e}")
        raise e


def bulk_register_users(  # noqa: C901
    df: pd.DataFrame, firebase_service: FirebaseService, class_id: str, school_id: str
):
    results = []

    if "role" in df.columns:
        professor_count = df[df["role"].str.lower() == UserRole.PROFESSOR.value].shape[0]
        if professor_count > 1:
            logger.error(
                f"Bulk registration failed for class {class_id}: File contains {professor_count} professors. Only one professor per class is allowed."  # noqa: E501
            )
            raise ValueError(
                "The uploaded file contains more than one professor. Only one professor can be assigned to a class during bulk registration."  # noqa: E501
            )
    else:
        logger.warning(
            "Bulk registration: 'role' column missing, assuming all users are students."
        )

    for _, row in df.iterrows():
        try:

            user_data = {
                "email": row["email"],
                "password": generate_password(),
                "name": row.get("name", row["email"].split("@")[0]),
                "role": row.get("role", "student"),
            }

            user = UserCreate(**user_data)

            registered_user_id = register_user(user, firebase_service)

            if registered_user_id:
                if user_data["role"] == UserRole.PROFESSOR.value:
                    professor_data = ProfessorCreate(
                        user_id=registered_user_id,
                        school_id=school_id,
                        class_id=class_id,
                    )
                    insert_professor_into_bq(professor_data)
                    logger.info(
                        f"Professor successfully created and assigned with user_id: {registered_user_id} to class {class_id}"  # noqa: E501
                    )
                else:
                    student_data = StudentCreate(
                        user_id=registered_user_id,
                        class_id=class_id,
                        school_id=school_id,
                    )
                    insert_student_into_bq(student_data)
                    logger.info(
                        f"Student successfully created with user_id: {registered_user_id}"
                    )

                try:
                    email_result = firebase_service.send_account_creation_email(
                        email=user_data["email"],
                        name=user_data["name"],
                        password=user_data["password"],
                    )
                    logger.info(f"Account creation email sent to {user_data['email']}")
                    email_status = "email_sent"

                    password_reset_link = email_result.get("link", "")
                except Exception as email_error:
                    logger.error(
                        f"Failed to send email to {user_data['email']}: {str(email_error)}"  # noqa: E501
                    )
                    email_status = "email_failed"
                    password_reset_link = ""

                results.append(
                    {
                        "user_id": registered_user_id,
                        "name": user_data["name"],
                        "email": user_data["email"],
                        "temp_password": user_data["password"],
                        "password_reset_link": password_reset_link,
                        "status": "success",
                        "email_status": email_status,
                    }
                )

        except Exception as e:
            logger.error(f"email {row['email']} 'error': {str(e)}")
            results.append({"email": row["email"], "status": "failed", "error": str(e)})

    return results
