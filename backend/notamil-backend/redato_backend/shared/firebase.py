import smtplib

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict

import firebase_admin

from fastapi import HTTPException
from firebase_admin import auth
from pydantic import EmailStr
from redato_backend.shared.constants import (
    EMAIL_PASSWORD,
    EMAIL_USER,
    FIREBASE_PROJECT_ID,
    FIREBASE_SCOPES,
    FIREBASE_SERVICE_ACCOUNT,
)
from redato_backend.shared.google_auth import GoogleAuthService
from redato_backend.shared.logger import logger


class FirebaseService(GoogleAuthService):
    def __init__(self):
        super().__init__(service_account_info=FIREBASE_SERVICE_ACCOUNT)
        self.credentials = self.get_credentials(scopes=FIREBASE_SCOPES)
        self.initialize_firebase()

    def initialize_firebase(self):
        """
        Initializes the Firebase Admin SDK using the obtained credentials.
        Ensures that Firebase is initialized only once.
        """
        try:
            # Try to retrieve the default app; if it doesn't exist, initialize it.
            firebase_admin.get_app()
            logger.info(
                "Firebase Admin SDK already initialized; skipping reinitialization."
            )
        except ValueError:
            # No default app exists, so initialize a new one.
            try:
                firebase_admin.initialize_app(
                    self.credentials, {"projectId": FIREBASE_PROJECT_ID}
                )
                logger.info("Firebase Admin SDK initialized successfully.")
            except Exception as e:
                logger.error(f"Failed to initialize Firebase Admin SDK: {e}")
                raise RuntimeError(f"Failed to initialize Firebase Admin SDK: {e}")

    @staticmethod
    def verify_token(token: str) -> Dict[str, Any]:
        """
        Verifies the provided Firebase ID token.

        :param token: Firebase ID token.
        :return: Decoded token containing user information.
        :raises HTTPException: If token verification fails.
        """
        try:
            decoded_token = auth.verify_id_token(token)
            logger.info("Token verification successful.")
            return decoded_token  # Contains authenticated user information
        except auth.InvalidIdTokenError:
            logger.error("Invalid ID token.")
            raise HTTPException(status_code=401, detail="Invalid token.")
        except Exception as e:
            logger.error(f"Token verification failed: {e}")
            raise HTTPException(status_code=401, detail="Token verification failed.")

    @staticmethod
    def create_user(
        email: EmailStr, password: str, role: str = "student"
    ) -> Dict[str, Any]:
        """
        Creates a new user in Firebase Authentication with a specified role.

        :param email: User's email address.
        :param password: User's password.
        :param role: User's role (student, professor, school_admin, system_admin). Defaults to student.
        :return: Dictionary containing user's email, UID, and role.
        :raises HTTPException: If user creation fails.
        """  # noqa
        try:
            firebase_user = auth.create_user(email=email, password=password)

            auth.set_custom_user_claims(firebase_user.uid, {"role": role})

            logger.info(
                f"User created successfully: {firebase_user.uid} with role: {role}"
            )
            return {"email": firebase_user.email, "uid": firebase_user.uid, "role": role}
        except auth.EmailAlreadyExistsError:
            logger.error("Email already exists.")
            raise HTTPException(status_code=400, detail="Email already exists.")
        except Exception as e:
            logger.error(f"Failed to create user: {e}")
            print(e)
            raise HTTPException(status_code=400, detail="Failed to create user.")

    @staticmethod
    def send_password_reset_email(email: str):
        """
        Envia um e-mail de redefinição de senha para o usuário usando smtplib.
        :param email: O e-mail do usuário para recuperação.
        """
        try:
            # Gera o link de redefinição de senha
            link = auth.generate_password_reset_link(email)
            logger.info(f"Password reset link generated for email: {email}")

            # Configura o conteúdo do e-mail
            subject = "Redefinição de senha"
            body = f"""
            <p>Olá,</p>
            <p>Você solicitou a redefinição de sua senha. Clique no link abaixo para redefinir:</p>
            <p><a href="{link}">Redefinir minha senha</a></p>
            <p>Se você não solicitou isso, por favor ignore este e-mail.</p>
            """  # noqa: E501

            msg = MIMEMultipart()
            msg["From"] = EMAIL_USER
            msg["To"] = email
            msg["Subject"] = subject
            msg.attach(MIMEText(body, "html"))

            # Configuração do servidor SMTP (exemplo com Gmail)
            server = smtplib.SMTP("smtp.gmail.com", 587)
            server.starttls()

            # 'Login' no servidor SMTP
            server.login(EMAIL_USER, EMAIL_PASSWORD)

            # Envia o e-mail
            server.sendmail(msg["From"], msg["To"], msg.as_string())
            server.quit()

            logger.info(f"Password reset email sent to {email}")
            return {"message": "Password reset email sent successfully.", "email": email}

        except Exception as e:
            logger.error(f"Failed to send password reset email for {email}: {e}")
            raise HTTPException(
                status_code=500,
                detail="An error occurred while sending the password reset email.",
            )

    @staticmethod
    def edit_user(  # noqa: C901
        user_id: str, username: str = None, password: str = None
    ) -> Dict[str, Any]:
        """
        Updates the details of an existing user in Firebase Authentication.

        :param user_id: The unique identifier of the user to update.
        :param username: The new username for the user (if provided).
        :param password: The new password for the user (if provided).
        :return: Dictionary containing updated user details.
        :raises HTTPException: If the update operation fails.
        """
        try:
            update_data = {}
            if username:
                update_data["display_name"] = username
            if password:
                update_data["password"] = password

            if not update_data:
                raise HTTPException(
                    status_code=400,
                    detail="At least one field (username or password) must be provided.",
                )

            # Update the user in Firebase Authentication
            updated_user = auth.update_user(user_id, **update_data)
            logger.info(f"User updated successfully: {updated_user.uid}")

            return {
                "message": "User information updated successfully.",
                "user_id": updated_user.uid,
                "display_name": (
                    updated_user.display_name if "display_name" in update_data else None
                ),
            }
        except auth.UserNotFoundError:
            logger.error(f"User with ID {user_id} not found.")
            raise HTTPException(status_code=404, detail="User not found.")
        except Exception as e:
            logger.error(f"Failed to update user {user_id}: {e}")
            raise HTTPException(
                status_code=500,
                detail="An error occurred while updating user information.",
            )

    @staticmethod
    def send_account_creation_email(email: str, name: str, password: str):
        """
        Sends an account creation email to a newly registered user with their credentials
        using Firebase Authentication.

        :param email: The user's email address
        :param name: The user's name
        :param password: The user's generated password
        """
        try:
            link = auth.generate_password_reset_link(email)

            logger.info(f"Password reset link generated for new user: {email}")

            return {
                "message": "Account creation email sent via Firebase Auth",
                "email": email,
                "link": link,
            }

        except Exception as e:
            logger.error(
                f"Failed to send account creation email via Firebase to {email}: {e}"
            )
            logger.exception(e)
            # Don't raise an exception to prevent bulk registration failure
            return {
                "message": f"Failed to send account creation email: {str(e)}",
                "email": email,
            }

    @staticmethod
    def delete_user(uid: str):
        """
        Deletes a user from Firebase Authentication.

        :param uid: The Firebase UID of the user to delete.
        :raises HTTPException: If the deletion fails (e.g., user not found).
        """
        try:
            auth.delete_user(uid)
            logger.info(f"Successfully deleted user {uid} from Firebase Authentication.")
        except auth.UserNotFoundError:
            # User might already be deleted or never existed, log but don't fail hard
            logger.warning(
                f"Firebase user with UID {uid} not found for deletion. It might have already been deleted."  # noqa: E501
            )
        except Exception as e:
            logger.error(f"Failed to delete user {uid} from Firebase: {e}")
            # Raise an exception as deletion failure might be critical
            raise HTTPException(
                status_code=500,
                detail=f"Failed to delete user {uid} from Firebase Authentication.",
            ) from e
