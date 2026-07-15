from __future__ import annotations

from flask import jsonify

API_ROOT_PREFIX = "/api"
API_V1_PREFIX = f"{API_ROOT_PREFIX}/v1"


def is_api_path(path: str) -> bool:
    return path == API_ROOT_PREFIX or path.startswith(f"{API_ROOT_PREFIX}/")


def error_response(
    code: str,
    message: str,
    status: int,
    details: dict | None = None,
):
    return (
        jsonify(
            {
                "error": {
                    "code": code,
                    "message": message,
                    "details": details or {},
                }
            }
        ),
        status,
    )
