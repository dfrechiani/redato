from datetime import datetime
from redato_backend.base_api.api_routes.deps import require_admin
from redato_backend.base_api.api_routes.models import Token
from redato_backend.base_api.functions.register import (
    register_user,
    bulk_register_users,
)
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.security import OAuth2PasswordBearer
from fastapi.responses import StreamingResponse
from redato_backend.shared.firebase import FirebaseService
from redato_backend.base_api.functions.handle_bq import (
    get_user_info,
    get_school_id,
    get_class_id,
)
from redato_backend.base_api.functions.models import UserCreate, UserRole
import pandas as pd
from io import BytesIO
from redato_backend.shared.logger import logger

router = APIRouter(prefix="/auth", tags=["authentication"])
firebase_service = FirebaseService()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


_VALID_ROLES = {r.value.lower() for r in UserRole}


@router.post("/login", response_model=Token)
def login(token: str = Depends(oauth2_scheme)):
    decoded_token = firebase_service.verify_token(token)
    user_email = decoded_token.get("email")
    raw_role = decoded_token.get("role")
    logger.info(f"Received request for user login: {user_email}")

    if not raw_role:
        logger.error(f"Login rejected: token for {user_email} has no role claim.")
        raise HTTPException(
            status_code=401,
            detail="Seu usuário não tem um perfil atribuído. Contate o administrador.",
        )

    user_role = raw_role.lower()
    if user_role not in _VALID_ROLES:
        logger.error(
            f"Login rejected: token for {user_email} has invalid role {raw_role!r}."
        )
        raise HTTPException(
            status_code=401, detail=f"Perfil de usuário inválido: {raw_role!r}."
        )

    try:
        login_id, username = get_user_info(user_email)
    except Exception as e:
        logger.error(f"Error looking up user {user_email}: {e}")
        raise HTTPException(status_code=500, detail="Falha ao buscar informações do usuário.")

    if not user_email or not login_id:
        logger.error("Login failed: Invalid token, email or uid not found")
        raise HTTPException(status_code=401, detail="Token inválido")

    school_id = None
    if user_role == UserRole.SCHOOL_ADMIN.value.lower():
        school_id = get_school_id(login_id)

    class_id = None
    if user_role == UserRole.STUDENT.value.lower():
        class_id = get_class_id(login_id)

    logger.info(f"User {user_email} successfully logged in with role: {user_role}")

    return {
        "access_token": token,
        "token_type": "bearer",
        "user_id": login_id,
        "username": username,
        "role": user_role,
        "school_id": school_id,
        "class_id": class_id,
    }


@router.post("/register")
def register(user: UserCreate):
    logger.info("Received request for /register")
    try:
        user = register_user(user, firebase_service)
        return user
    except Exception as e:
        logger.error(f"Error during user registration: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/bulk-register", dependencies=[Depends(require_admin)])
async def bulk_register(class_id: str, school_id: str, file: UploadFile = File(...)):
    """
    Bulk register users from a CSV or XLSX file.
    The file should contain at least an 'email' column.
    Optional columns: 'name', 'role' (defaults to 'student' if not provided)
    Returns a CSV file with user credentials.
    """
    try:
        content = await file.read()
        filename = file.filename.lower()

        # Validate file type
        if filename.endswith(".csv"):
            df = pd.read_csv(BytesIO(content))
        elif filename.endswith((".xlsx", ".xls")):
            df = pd.read_excel(BytesIO(content))
        else:
            logger.error(f"Invalid file type uploaded: {file.filename}")
            raise HTTPException(
                status_code=400,
                detail="Invalid file type. Only CSV and Excel (.xlsx, .xls) files are accepted.",  # noqa: E501
            )

        # Validate required columns
        required_columns = {"name", "email", "role"}
        actual_columns = set(df.columns)

        if not required_columns.issubset(actual_columns):
            missing_columns = required_columns - actual_columns
            logger.error(f"Missing required columns in uploaded file: {missing_columns}")
            raise HTTPException(
                status_code=400,
                detail=f"File must contain the following columns: {', '.join(required_columns)}. Missing: {', '.join(missing_columns)}",  # noqa: E501
            )

        # Existing logic proceeds if validation passes
        users = bulk_register_users(df, firebase_service, class_id, school_id)

        credentials_df = pd.DataFrame(users)

        output = BytesIO()

        output.write(b"\xef\xbb\xbf")
        credentials_df.to_csv(output, index=False, sep=",", encoding="utf-8")
        output.seek(0)

        return StreamingResponse(
            output,
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": f"attachment; filename=users_{datetime.now().isoformat()}.csv",  # noqa: E501
                "Content-Type": "text/csv; charset=utf-8",
            },
        )

    except Exception as e:
        logger.error(f"Error during bulk registration: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred during bulk registration: {str(e)}",
        )


@router.post("/recover-password")
def recover_password(email: str):
    logger.info(f"Received password recovery request for email: {email}")
    try:
        firebase_service.send_password_reset_email(email)
        return {"message": "Password reset email sent successfully.", "email": email}
    except Exception as e:
        logger.error(f"Error sending password reset email for {email}: {e}")
        raise HTTPException(
            status_code=500,
            detail="An error occurred while sending the password reset email.",
        )
