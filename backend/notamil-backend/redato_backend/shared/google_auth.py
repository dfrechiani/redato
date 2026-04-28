import base64
import json

from typing import Any, Dict, Union

from google.oauth2 import service_account
from googleapiclient.discovery import build
from redato_backend.shared.logger import logger


class GoogleAuthService:
    def __init__(
        self, service_account_info: Union[str, Dict[str, Any]], delegated_user: str = None
    ):
        self.delegated_user = delegated_user
        self.service_account = service_account_info

    def get_credentials(self, scopes: list) -> service_account.Credentials:  # noqa: C901
        """
        Authenticates and returns Google API credentials using a service account.

        :param scopes: List of scopes for the desired Google API.
        :return: Credentials object.
        """
        try:
            if self.service_account:
                if isinstance(self.service_account, str):
                    try:
                        decoded_key = base64.b64decode(self.service_account).decode(
                            "utf-8"
                        )
                        service_account_info = json.loads(decoded_key)
                        logger.info(
                            "Decodificação da chave de conta de serviço bem-sucedida."
                        )
                    except (base64.binascii.Error, UnicodeDecodeError) as decode_err:
                        logger.error(f"Falha na decodificação base64: {decode_err}")
                        raise RuntimeError(f"Falha na decodificação base64: {decode_err}")
                    except json.JSONDecodeError as json_err:
                        logger.error(
                            f"Falha ao analisar JSON da chave "
                            f"de conta de serviço: {json_err}"
                        )
                        raise RuntimeError(
                            f"Falha ao analisar JSON da chave "
                            f"de conta de serviço: {json_err}"
                        )
                else:
                    raise TypeError(
                        "service_account_info must be a JSON string or a dictionary."
                    )

                credentials = service_account.Credentials.from_service_account_info(
                    service_account_info, scopes=scopes
                )
                logger.info("Authenticated using SERVICE_ACCOUNT_INFO.")
            else:
                raise ValueError("No service account information provided.")

            if self.delegated_user:
                credentials = credentials.with_subject(self.delegated_user)
                logger.info(f"Delegated credentials to user: {self.delegated_user}")

        except json.JSONDecodeError as e:
            logger.error(f"JSON decoding failed: {e}")
            raise RuntimeError(f"Invalid JSON for service account info: {e}")
        except TypeError as e:
            logger.error(f"Type error: {e}")
            raise RuntimeError(f"Invalid type for service_account_info: {e}")
        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            raise RuntimeError(f"Failed to authenticate with Google API: {e}")

        return credentials

    def build_service(self, api_name: str, api_version: str, scopes: list) -> build:
        """
        Builds and returns a Google API service object.

        :param api_name: Name of the Google API (e.g., 'sheets', 'calendar').
        :param api_version: Version of the Google API (e.g., 'v4', 'v3').
        :param scopes: List of scopes for the desired Google API.
        :return: Google API service object.
        """
        credentials = self.get_credentials(scopes)
        try:
            service = build(api_name, api_version, credentials=credentials)
            logger.info(f"Google {api_name.capitalize()} service built successfully.")
            return service
        except Exception as e:
            logger.error(f"Building Google {api_name.capitalize()} service failed: {e}")
            raise RuntimeError(
                f"Failed to build Google {api_name.capitalize()} service: {e}"
            )
