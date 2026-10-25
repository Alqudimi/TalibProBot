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
