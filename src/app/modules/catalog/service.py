import uuid
from typing import List, Optional, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from src.app.modules.catalog.models import OfferPrice, ProductOffer, ServiceCategory, ServiceDefinition
from src.app.observability.logging import get_logger

logger = get_logger("catalog")


class CatalogService:
    """Service for discovering and managing educational services, categories and pricing."""

    @staticmethod
    async def get_active_categories(session: AsyncSession) -> List[ServiceCategory]:
        stmt = (
            select(ServiceCategory)
            .where(ServiceCategory.is_active == True)
            .order_by(ServiceCategory.sort_order.asc())
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_services_by_category(
        session: AsyncSession, category_id: uuid.UUID, only_published: bool = True
    ) -> List[ServiceDefinition]:
        stmt = select(ServiceDefinition).where(ServiceDefinition.category_id == category_id)
        if only_published:
            stmt = stmt.where(ServiceDefinition.lifecycle_status == "published")
        stmt = stmt.order_by(ServiceDefinition.title_ar.asc())
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_published_services(session: AsyncSession, limit: int = 50) -> List[ServiceDefinition]:
        stmt = (
            select(ServiceDefinition)
            .where(ServiceDefinition.lifecycle_status == "published")
            .limit(limit)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def search_services(session: AsyncSession, query_str: str) -> List[ServiceDefinition]:
        pattern = f"%{query_str.strip()}%"
        stmt = (
            select(ServiceDefinition)
            .where(
                (ServiceDefinition.lifecycle_status == "published")
                & (
                    ServiceDefinition.title_ar.ilike(pattern)
                    | ServiceDefinition.summary_ar.ilike(pattern)
                )
            )
            .limit(20)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_service_details(
        session: AsyncSession, service_id: uuid.UUID
    ) -> Optional[Tuple[ServiceDefinition, List[ProductOffer]]]:
        stmt = (
            select(ServiceDefinition)
            .options(
                selectinload(ServiceDefinition.category),
                selectinload(ServiceDefinition.offers).selectinload(ProductOffer.prices),
            )
            .where(ServiceDefinition.id == service_id)
        )
        result = await session.execute(stmt)
        service = result.scalar_one_or_none()
        if not service:
            return None
        return service, service.offers

    @staticmethod
    async def get_offer_by_id(session: AsyncSession, offer_id: uuid.UUID) -> Optional[ProductOffer]:
        stmt = (
            select(ProductOffer)
            .options(
                selectinload(ProductOffer.prices),
                selectinload(ProductOffer.primary_service),
            )
            .where(ProductOffer.id == offer_id)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_category_by_code_or_id(
        session: AsyncSession, identifier: str
    ) -> Optional[ServiceCategory]:
        """Looks up a category by code string or UUID string."""
        stmt = select(ServiceCategory)
        try:
            val_uuid = uuid.UUID(identifier)
            stmt = stmt.where(ServiceCategory.id == val_uuid)
        except ValueError:
            stmt = stmt.where(ServiceCategory.code == identifier)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_services_paginated(
        session: AsyncSession,
        category_id: uuid.UUID,
        page: int = 1,
        page_size: int = 6,
        only_published: bool = True,
    ) -> Tuple[List[ServiceDefinition], int]:
        """Returns paginated services inside category and total page count."""
        base_stmt = select(ServiceDefinition).where(ServiceDefinition.category_id == category_id)
        if only_published:
            base_stmt = base_stmt.where(ServiceDefinition.lifecycle_status == "published")

        from sqlalchemy import func
        count_stmt = select(func.count()).select_from(base_stmt.subquery())
        total_count = (await session.execute(count_stmt)).scalar() or 0
        total_pages = max(1, (total_count + page_size - 1) // page_size)

        offset = max(0, (page - 1) * page_size)
        items_stmt = base_stmt.order_by(ServiceDefinition.title_ar.asc()).offset(offset).limit(page_size)
        items = (await session.execute(items_stmt)).scalars().all()
        return list(items), total_pages

    @staticmethod
    async def get_popular_services(session: AsyncSession, limit: int = 10) -> List[ServiceDefinition]:
        """Returns top published services §7.2.1."""
        stmt = (
            select(ServiceDefinition)
            .where(ServiceDefinition.lifecycle_status == "published")
            .limit(limit)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())
