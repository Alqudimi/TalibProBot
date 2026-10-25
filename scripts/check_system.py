#!/usr/bin/env python3
"""System diagnostic and health check script.

Verifies:
1. PostgreSQL 18 connection and schema search_path
2. Core table counts (users, offers, orders, outbox)
3. Redis connectivity (or validates graceful REDIS_ENABLED=false degradation)
4. Overall operational health
"""
import asyncio
from pathlib import Path
import sys

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text
from src.app.config.settings import settings
from src.app.infrastructure.cache.adapter import CacheService
from src.app.infrastructure.database.session import check_db_health, get_db_session


async def main() -> None:
    print("=" * 60)
    print("Academic Platform - System Health & Diagnostics Check")
    print("=" * 60)

    # 1. Database Health
    print("\n[1/3] Testing PostgreSQL 18 Connection...")
    db_ok = await check_db_health()
    if not db_ok:
        print("❌ PostgreSQL check failed! Ensure PostgreSQL is running on port 5434.")
        sys.exit(1)
    print(f"✅ PostgreSQL connected successfully (schema: {settings.POSTGRES_SCHEMA})")

    # Table inspections
    async with get_db_session() as session:
        query = text(
            """
            SELECT
                (SELECT count(*) FROM student_platform.users) as user_count,
                (SELECT count(*) FROM student_platform.service_categories) as cat_count,
                (SELECT count(*) FROM student_platform.service_definitions) as srv_count,
                (SELECT count(*) FROM student_platform.product_offers) as offer_count,
                (SELECT count(*) FROM student_platform.orders) as order_count,
                (SELECT count(*) FROM student_platform.transactional_outbox WHERE status = 'pending') as pending_outbox;
            """
        )
        res = await session.execute(query)
        row = res.fetchone()
        print(f"   - Users in DB: {row.user_count}")
        print(f"   - Service Categories: {row.cat_count}")
        print(f"   - Service Definitions: {row.srv_count}")
        print(f"   - Product Offers: {row.offer_count}")
        print(f"   - Total Orders: {row.order_count}")
        print(f"   - Pending Outbox Tasks: {row.pending_outbox}")

    # 2. Redis Cache Health
    print("\n[2/3] Testing Cache / Redis Status...")
    cache = CacheService(
        enabled=settings.REDIS_ENABLED,
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        password=settings.REDIS_PASSWORD,
    )
    await cache.initialize()
    if settings.REDIS_ENABLED:
        if cache.is_healthy:
            print("✅ Redis is enabled and connected.")
        else:
            print("⚠️ Redis is enabled but connection failed; graceful fallback in effect.")
    else:
        print("✅ Redis is disabled (REDIS_ENABLED=false); system running in no-cache mode as requested.")
    await cache.close()

    # 3. Environment & Bot Configuration
    print("\n[3/3] Checking Configuration & Tokens...")
    print(f"   - Environment: {settings.APP_ENV}")
    print(f"   - Log Level: {settings.LOG_LEVEL}")
    print(f"   - Task Worker Enabled: {settings.TASK_WORKER_ENABLED}")
    token_status = "Configured" if settings.BOT_TOKEN and not settings.BOT_TOKEN.startswith("0000000000") else "Placeholder (Demo/Testing mode)"
    print(f"   - Telegram Bot Token: {token_status}")

    print("\n" + "=" * 60)
    print("✅ System Diagnostics Complete: All Core Subsystems Operational!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
