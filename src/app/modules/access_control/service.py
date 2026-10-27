import uuid
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from src.app.modules.access_control.models import Permission, Role, RolePermission, UserRoleAssignment
from src.app.observability.logging import get_logger

import time

logger = get_logger("access_control")
_user_permissions_cache: dict[uuid.UUID, tuple[float, set[str]]] = {}


class AccessControlService:
    """Service managing role-based access control (RBAC), permissions, and role assignments."""

    @staticmethod
    async def get_user_permissions(session: AsyncSession, user_id: uuid.UUID) -> set[str]:
        """Returns the set of permission codes currently held by the user."""
        now_ts = time.monotonic()
        cached = _user_permissions_cache.get(user_id)
        if cached and (now_ts < cached[0]):
            return cached[1]

        now = datetime.now(timezone.utc)
        stmt = (
            select(Permission.code)
            .join(RolePermission, Permission.id == RolePermission.permission_id)
            .join(Role, Role.id == RolePermission.role_id)
            .join(UserRoleAssignment, UserRoleAssignment.role_id == Role.id)
            .where(
                UserRoleAssignment.user_id == user_id,
                (UserRoleAssignment.expires_at.is_(None)) | (UserRoleAssignment.expires_at > now),
            )
        )
        result = await session.execute(stmt)
        perms = set(result.scalars().all())
        _user_permissions_cache[user_id] = (now_ts + 120.0, perms)
        return perms

    @staticmethod
    async def has_permission(session: AsyncSession, user_id: uuid.UUID, permission_code: str) -> bool:
        """Checks if a user has a specific permission."""
        permissions = await AccessControlService.get_user_permissions(session, user_id)
        return permission_code in permissions or "admin.super" in permissions

    @staticmethod
    async def assign_role(
        session: AsyncSession,
        user_id: uuid.UUID,
        role_code: str,
        assigned_by: Optional[uuid.UUID] = None,
        expires_at: Optional[datetime] = None,
    ) -> UserRoleAssignment:
        """Assigns a role to a user."""
        stmt = select(Role).where(Role.code == role_code)
        res = await session.execute(stmt)
        role = res.scalar_one_or_none()
        if not role:
            raise ValueError(f"Role '{role_code}' does not exist.")

        existing_stmt = select(UserRoleAssignment).where(
            UserRoleAssignment.user_id == user_id,
            UserRoleAssignment.role_id == role.id,
        )
        existing = (await session.execute(existing_stmt)).scalar_one_or_none()
        if existing:
            existing.assigned_by = assigned_by
            existing.expires_at = expires_at
            await session.flush()
            return existing

        assignment = UserRoleAssignment(
            user_id=user_id,
            role_id=role.id,
            assigned_by=assigned_by,
            expires_at=expires_at,
        )
        session.add(assignment)
        await session.flush()
        _user_permissions_cache.pop(user_id, None)
        logger.info(f"Assigned role '{role_code}' to user {user_id}")
        return assignment
