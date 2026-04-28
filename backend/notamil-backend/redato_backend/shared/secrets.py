import os
import re

from typing import Match, Optional

from google.cloud.secretmanager import SecretManagerServiceClient


def _match_secret(string: str) -> Optional[Match[str]]:
    """
    Check if string matches secret pattern
    """

    secret_pattern = r"^{(?P<secret_id>[A-Z_]+):(?P<secret_version>([0-9]+|latest))}$"

    return re.match(secret_pattern, string)


def get_config(
    config_name: str,
    default: str = "",
    should_have_value: bool = True,
    try_to_get_secret: bool = False,
    project_id: Optional[str] = None,
) -> str:
    """
    Get configuration from environment environment variable.
    """

    config = os.getenv(config_name, default)

    if should_have_value and not config:
        raise RuntimeError(f"'{config_name}' does not have a value")

    secret_matches = _match_secret(config)

    if secret_matches and try_to_get_secret:
        assert project_id, "'project_id' can not be null if you want to get from secrets"
        return _get_secret(
            secret_matches["secret_id"],
            secret_matches["secret_version"],
            project_id,
        )

    return config


def _get_secret(secret_id: str, version_id: str, project_id: str) -> str:
    """
    Call secret manager API to get configuration
    """

    client = get_secret_manager_client()

    # Build the resource name of the secret version.
    name = f"projects/{project_id}/secrets/{secret_id}/versions/{version_id}"
    response = client.access_secret_version(request={"name": name})

    return response.payload.data.decode("UTF-8")


def get_secret_manager_client() -> SecretManagerServiceClient:
    """
    Build secret manager client
    """

    return SecretManagerServiceClient()
