#!/usr/bin/env python3
"""Seeds sample product offers and prices into the database for demonstration and testing."""
import asyncio
from pathlib import Path
import sys
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select
from src.app.infrastructure.database.session import get_db_session
from src.app.modules.catalog.models import OfferPrice, ProductOffer, ServiceCategory, ServiceDefinition


async def main() -> None:
    print("Seeding sample catalog offers...")
    async with get_db_session() as session:
        # Find first published service
        stmt = select(ServiceDefinition).limit(3)
        res = await session.execute(stmt)
        services = list(res.scalars().all())

        if not services:
            print("No service definitions found in database.")
            return

        for srv in services:
            offer_code = f"offer-{srv.code}"
            existing = await session.execute(select(ProductOffer).where(ProductOffer.code == offer_code))
            if existing.scalar_one_or_none():
                continue

            offer = ProductOffer(
                id=uuid.uuid4(),
                code=offer_code,
                primary_service_id=srv.id,
                title_ar=f"عرض: {srv.title_ar}",
                offer_type="service",
                status="published",
            )
            session.add(offer)
            await session.flush()

            # Add Telegram Stars price (15 Stars) and SAR price (25 SAR)
            session.add(OfferPrice(offer_id=offer.id, currency_code="XTR", amount_minor=15))
            session.add(OfferPrice(offer_id=offer.id, currency_code="SAR", amount_minor=2500))
            await session.flush()
            print(f"Created offer: {offer.title_ar} (XTR: 15, SAR: 25.00)")

    print("✅ Catalog seeding completed successfully.")


if __name__ == "__main__":
    asyncio.run(main())
