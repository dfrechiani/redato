import asyncio
import json
import urllib.error
import urllib.request

from typing import Any, Dict

from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2 import id_token
from redato_backend.shared.logger import logger


async def get_id_token_async(function_url: str) -> str:
    loop = asyncio.get_running_loop()
    token = await loop.run_in_executor(
        None, id_token.fetch_id_token, GoogleRequest(), function_url
    )
    return token


async def call_cloud_function(  # noqa: C901
    function_url: str, data: Dict[str, Any]
) -> Dict[str, Any]:
    try:
        if not function_url:
            raise ValueError(
                "Function URL (audience) must be provided and cannot be empty."
            )

        # Retrieve the ID token using the function URL as the audience.
        token = await get_id_token_async(function_url)

        req_data = json.dumps(data).encode("utf-8")
        req = urllib.request.Request(function_url, data=req_data, method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("Authorization", f"Bearer {token}")

        try:
            with urllib.request.urlopen(req) as response:
                status_code = response.getcode()
                response_body = response.read().decode("utf-8")
                try:
                    response_json = json.loads(response_body) if response_body else {}
                except ValueError:
                    # Handle non-JSON responses gracefully.
                    response_json = {}
                return {
                    "status_code": status_code,
                    "text": response_body,
                    "json": response_json,
                }
        except urllib.error.HTTPError as e:
            error_text = e.read().decode("utf-8")
            try:
                error_json = json.loads(error_text) if error_text else {}
            except ValueError:
                error_json = {}
            return {
                "status_code": e.code,
                "text": error_text,
                "json": error_json,
            }
    except Exception as e:
        logger.error(f"Error calling cloud function: {str(e)}")
        return {
            "status_code": 500,
            "text": str(e),
            "json": {},
        }
