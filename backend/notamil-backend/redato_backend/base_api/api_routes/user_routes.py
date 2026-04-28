from redato_backend.base_api.api_routes.models import UserOut
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer

from redato_backend.shared.firebase import FirebaseService
from redato_backend.shared.logger import logger

router = APIRouter(prefix="/users", tags=["users"])
firebase_service = FirebaseService()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


@router.get("/me", response_model=UserOut)
def read_users_me(token: str = Depends(oauth2_scheme)):
    logger.info("Received request for /users/me")
    try:
        decoded_token = firebase_service.verify_token(token)
        logger.info(f"Token successfully decoded: {decoded_token}")

        user_email = decoded_token.get("email")
        if not user_email:
            logger.error("Token is valid but does not contain an email")
            raise HTTPException(status_code=401, detail="Invalid token: email not found")

        logger.info(f"Request successfully processed for user: {user_email}")
        return {"email": user_email}
    except Exception as e:
        logger.error(f"Error in /users/me: {str(e)}")
        raise HTTPException(status_code=401, detail="Token validation failed")


@router.put("/{user_id}")
def edit_user(user_id: str, username: str = None, password: str = None):
    logger.info(f"Received request to update user: {user_id}")
    try:
        updated_user_info = firebase_service.edit_user(
            user_id=user_id, username=username, password=password
        )
        return updated_user_info
    except Exception as e:
        logger.error(f"Error during user update: {str(e)}")
        raise HTTPException(
            status_code=500, detail="An error occurred while updating user information."
        )
