from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.models.user import User
from backend.models.merchant_settings import MerchantSettings
from backend.models.audit import AuditLog, AuditAction
from backend.core.security import hash_password, verify_password, create_access_token
from backend.core.exceptions import AuthenticationError, DuplicateError
from backend.schemas.auth import RegisterRequest, LoginRequest
import structlog

logger = structlog.get_logger(__name__)


async def register_user(db: AsyncSession, req: RegisterRequest, ip: str | None = None) -> tuple[User, str]:
    result = await db.execute(select(User).where(User.email == req.email.lower()))
    if result.scalar_one_or_none():
        raise DuplicateError("An account with this email already exists")

    user = User(
        email=req.email.lower(),
        hashed_password=hash_password(req.password),
        full_name=req.full_name,
        is_active=True,
        is_verified=False,
    )
    db.add(user)
    await db.flush()

    # Create default merchant settings
    settings_obj = MerchantSettings(user_id=user.id)
    db.add(settings_obj)

    # Audit log
    audit = AuditLog(
        user_id=user.id,
        action=AuditAction.USER_REGISTERED.value,
        resource_type="user",
        resource_id=str(user.id),
        description=f"User registered: {user.email}",
        ip_address=ip,
    )
    db.add(audit)
    await db.commit()
    await db.refresh(user)

    token = create_access_token(str(user.id))
    logger.info("user_registered", user_id=str(user.id), email=user.email)
    return user, token


async def login_user(db: AsyncSession, req: LoginRequest, ip: str | None = None) -> tuple[User, str]:
    result = await db.execute(select(User).where(User.email == req.email.lower()))
    user = result.scalar_one_or_none()
    if not user or not verify_password(req.password, user.hashed_password):
        raise AuthenticationError("Invalid email or password")
    if not user.is_active:
        raise AuthenticationError("Account is disabled")

    token = create_access_token(str(user.id))
    audit = AuditLog(
        user_id=user.id,
        action=AuditAction.USER_LOGGED_IN.value,
        resource_type="user",
        resource_id=str(user.id),
        description=f"User logged in from {ip}",
        ip_address=ip,
    )
    db.add(audit)
    await db.commit()
    logger.info("user_logged_in", user_id=str(user.id))
    return user, token
