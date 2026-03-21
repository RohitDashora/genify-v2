"""Request middleware for user identity extraction."""
import logging

from fastapi import Request

logger = logging.getLogger(__name__)


def get_current_user(request: Request) -> str:
    """Extract user email from Databricks Apps proxy header.

    Falls back to 'dev@local' for local development.
    """
    email = (
        request.headers.get("X-Forwarded-Email")
        or request.headers.get("X-Forwarded-User")
        or "dev@local"
    )
    return email.lower().strip()
