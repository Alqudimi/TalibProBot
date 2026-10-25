import uuid
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from src.app.modules.institutions.models import Organization, OrganizationMember
from src.app.observability.logging import get_logger

logger = get_logger("institutions")


class InstitutionService:
    """Service managing university/school organizations, member invitations, and enterprise licenses."""

    @staticmethod
    async def create_organization(
        session: AsyncSession,
        slug: str,
        name: str,
        organization_type: str = "university",
        country_code: Optional[str] = "SA",
        billing_email: Optional[str] = None,
    ) -> Organization:
        org = Organization(
            id=uuid.uuid4(),
            slug=slug,
            name=name,
            organization_type=organization_type,
            status="active",
            country_code=country_code,
            billing_email=billing_email,
        )
        session.add(org)
        await session.flush()
        logger.info(f"Created organization {org.id} ({slug})")
        return org

    @staticmethod
    async def add_member(
        session: AsyncSession,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        invited_by: Optional[uuid.UUID] = None,
    ) -> OrganizationMember:
        member = OrganizationMember(
            id=uuid.uuid4(),
            organization_id=organization_id,
            user_id=user_id,
            member_status="active",
            invited_by=invited_by,
        )
        session.add(member)
        await session.flush()
        logger.info(f"Added member {user_id} to organization {organization_id}")
        return member

    @staticmethod
    async def list_user_organizations(session: AsyncSession, user_id: uuid.UUID) -> List[Organization]:
        stmt = (
            select(Organization)
            .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
            .where(OrganizationMember.user_id == user_id, OrganizationMember.member_status == "active")
        )
        res = await session.execute(stmt)
        return list(res.scalars().all())
