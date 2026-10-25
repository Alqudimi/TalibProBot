import uuid
from datetime import datetime, timezone, timedelta
import pytest
from src.app.modules.access_control.models import Permission, Role, RolePermission
from src.app.modules.access_control.service import AccessControlService
from src.app.modules.accounts.service import AccountService


@pytest.mark.asyncio
async def test_rbac_and_permission_enforcement(db_session):
    # 1. Setup user
    user = await AccountService.get_or_create_telegram_user(
        db_session, telegram_id=88223344, display_name="RBAC User"
    )

    # 2. Check no default administrative permissions
    has_admin = await AccessControlService.has_permission(db_session, user.user_id, "admin.catalog.write")
    assert has_admin is False

    # 3. Create a custom role and permission
    perm = Permission(
        id=uuid.uuid4(),
        code=f"service.catalog.manage_{uuid.uuid4().hex[:6]}",
        module="catalog",
        description="Permission to update catalog",
    )
    db_session.add(perm)

    role = Role(
        id=uuid.uuid4(),
        code=f"catalog_manager_{uuid.uuid4().hex[:6]}",
        name_ar="مدير الكتالوج",
        scope="platform",
    )
    db_session.add(role)
    await db_session.flush()

    rp = RolePermission(role_id=role.id, permission_id=perm.id)
    db_session.add(rp)
    await db_session.flush()

    # 4. Assign role to user
    await AccessControlService.assign_role(
        session=db_session,
        user_id=user.user_id,
        role_code=role.code,
    )

    # 5. Check permission granted
    has_perm = await AccessControlService.has_permission(db_session, user.user_id, perm.code)
    assert has_perm is True

    # 6. Check expired role
    expired_role = Role(
        id=uuid.uuid4(),
        code=f"temporary_role_{uuid.uuid4().hex[:6]}",
        name_ar="دور مؤقت",
        scope="platform",
    )
    db_session.add(expired_role)
    await db_session.flush()

    temp_perm = Permission(
        id=uuid.uuid4(),
        code=f"temp.access_{uuid.uuid4().hex[:6]}",
        module="general",
        description="Temporary access",
    )
    db_session.add(temp_perm)
    await db_session.flush()

    db_session.add(RolePermission(role_id=expired_role.id, permission_id=temp_perm.id))
    await db_session.flush()

    # Assign role that was granted in the past and has since expired
    from src.app.modules.access_control.models import UserRoleAssignment
    past_assigned = datetime.now(timezone.utc) - timedelta(days=2)
    past_expired = datetime.now(timezone.utc) - timedelta(days=1)
    assignment = UserRoleAssignment(
        user_id=user.user_id,
        role_id=expired_role.id,
        assigned_at=past_assigned,
        expires_at=past_expired,
    )
    db_session.add(assignment)
    await db_session.flush()

    has_temp = await AccessControlService.has_permission(db_session, user.user_id, temp_perm.code)
    assert has_temp is False
