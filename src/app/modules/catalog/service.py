import time
import uuid
from typing import List, Optional, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from src.app.modules.catalog.models import OfferPrice, ProductOffer, ServiceCategory, ServiceDefinition
from src.app.observability.logging import get_logger

logger = get_logger("catalog")

_categories_cache: Optional[Tuple[float, List[ServiceCategory]]] = None
_popular_services_cache: Optional[Tuple[float, List[ServiceDefinition]]] = None
_category_lookup_cache: dict[str, Tuple[float, Optional[ServiceCategory]]] = {}
_service_details_cache: dict[uuid.UUID, Tuple[float, Optional[Tuple[ServiceDefinition, List[ProductOffer]]]]] = {}
_paginated_services_cache: dict[Tuple[uuid.UUID, int, int, bool], Tuple[float, List[ServiceDefinition], int]] = {}


class CatalogService:
    """Service for discovering and managing educational services, categories and pricing."""

    @staticmethod
    async def get_active_categories(session: AsyncSession) -> List[ServiceCategory]:
        global _categories_cache
        now = time.monotonic()
        if _categories_cache and (now - _categories_cache[0]) < 300.0:
            return _categories_cache[1]

        stmt = (
            select(ServiceCategory)
            .where(ServiceCategory.is_active == True)
            .order_by(ServiceCategory.sort_order.asc())
        )
        result = await session.execute(stmt)
        categories = list(result.scalars().all())
        _categories_cache = (now, categories)
        return categories

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
        global _service_details_cache
        now = time.monotonic()
        if service_id in _service_details_cache and (now - _service_details_cache[service_id][0]) < 120.0:
            return _service_details_cache[service_id][1]

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
            _service_details_cache[service_id] = (now, None)
            return None
        details = (service, service.offers)
        _service_details_cache[service_id] = (now, details)
        return details

    @staticmethod
    async def get_popular_services(session: AsyncSession, limit: int = 10) -> List[ServiceDefinition]:
        global _popular_services_cache
        now = time.monotonic()
        if _popular_services_cache and (now - _popular_services_cache[0]) < 60.0:
            return _popular_services_cache[1][:limit]

        stmt = (
            select(ServiceDefinition)
            .where(ServiceDefinition.lifecycle_status == "published")
            .limit(limit)
        )
        result = await session.execute(stmt)
        services = list(result.scalars().all())
        _popular_services_cache = (now, services)
        return services

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
        """Looks up a category by code string or UUID string with caching."""
        global _category_lookup_cache
        now = time.monotonic()
        if identifier in _category_lookup_cache and (now - _category_lookup_cache[identifier][0]) < 300.0:
            return _category_lookup_cache[identifier][1]

        stmt = select(ServiceCategory)
        try:
            val_uuid = uuid.UUID(identifier)
            stmt = stmt.where(ServiceCategory.id == val_uuid)
        except ValueError:
            stmt = stmt.where(ServiceCategory.code == identifier)
        result = await session.execute(stmt)
        cat = result.scalar_one_or_none()
        _category_lookup_cache[identifier] = (now, cat)
        return cat

    @staticmethod
    async def get_services_paginated(
        session: AsyncSession,
        category_id: uuid.UUID,
        page: int = 1,
        page_size: int = 6,
        only_published: bool = True,
    ) -> Tuple[List[ServiceDefinition], int]:
        """Returns paginated services inside category and total page count with in-memory caching."""
        global _paginated_services_cache
        now = time.monotonic()
        cache_key = (category_id, page, page_size, only_published)
        if cache_key in _paginated_services_cache and (now - _paginated_services_cache[cache_key][0]) < 120.0:
            cached_val = _paginated_services_cache[cache_key]
            return cached_val[1], cached_val[2]

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
        result_list = list(items)
        _paginated_services_cache[cache_key] = (now, result_list, total_pages)
        return result_list, total_pages
