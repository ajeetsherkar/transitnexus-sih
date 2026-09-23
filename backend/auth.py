import hashlib
import os
from typing import Optional

from fastapi import Header, HTTPException
from sqlalchemy.orm import Session

from backend.models import Bus


def hash_api_key(api_key: str) -> str:
    """Return the SHA-256 hash of a bus API key."""
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def get_bus_from_api_key(
    x_api_key: Optional[str] = Header(default=None),
    db: Session = None,
) -> Bus:
    """Authenticate a bus using the X-API-Key header."""
    if not x_api_key:
        raise HTTPException(
            status_code=401,
            detail="Missing X-API-Key",
        )

    bus = db.query(Bus).filter(
        Bus.api_key_hash == hash_api_key(x_api_key)
    ).first()

    if bus is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid X-API-Key",
        )

    return bus


def require_read_token(
    x_read_token: Optional[str] = Header(default=None),
) -> None:
    """Protect read endpoints with READ_TOKEN."""
    expected = os.getenv("READ_TOKEN")

    if not expected:
        raise HTTPException(
            status_code=500,
            detail="READ_TOKEN is not configured",
        )

    if x_read_token != expected:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing read token",
        )


def require_admin_token(
    x_admin_token: Optional[str] = Header(default=None),
) -> None:
    """Protect admin endpoints with ADMIN_TOKEN."""
    expected = os.getenv("ADMIN_TOKEN")

    if not expected:
        raise HTTPException(
            status_code=500,
            detail="ADMIN_TOKEN is not configured",
        )

    if x_admin_token != expected:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing admin token",
        )
