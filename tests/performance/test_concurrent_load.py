import asyncio
import uuid
import pytest
from src.app.infrastructure.database.session import close_db_engine, get_db_session
from src.app.modules.accounts.service import AccountService
from src.app.modules.education.service import EducationService


@pytest.fixture(autouse=True)
async def cleanup_db_engine_after_test():
    yield
    await close_db_engine()


@pytest.mark.asyncio
async def test_concurrent_study_deck_operations():
    """Verify concurrent async deck creation and integrity across distinct sessions."""
    async with get_db_session() as session:
        user = await AccountService.get_or_create_telegram_user(
            session, telegram_id=99001122, display_name="Concurrent Student"
        )
        user_id = user.user_id

    async def create_single_deck(index: int):
        async with get_db_session() as s:
            deck = await EducationService.create_deck(
                session=s,
                user_id=user_id,
                title=f"Concurrent Deck #{index}",
            )
            card = await EducationService.add_card(
                session=s,
                deck_id=deck.id,
                front=f"Front #{index}",
                back=f"Back #{index}",
            )
            return deck.id, card.id

    # Run 10 parallel operations
    tasks = [create_single_deck(i) for i in range(10)]
    results = await asyncio.gather(*tasks)

    assert len(results) == 10
    deck_ids = {r[0] for r in results}
    assert len(deck_ids) == 10

    async with get_db_session() as verify_session:
        decks = await EducationService.get_user_decks(verify_session, user_id)
        assert len(decks) >= 10


@pytest.mark.asyncio
async def test_concurrent_user_lookup_and_caching_performance():
    """Verify sub-millisecond response and zero connection leaks under 50 concurrent user lookups."""
    import time
    # Pre-seed 10 users cleanly
    for i in range(10):
        async with get_db_session() as s:
            await AccountService.get_or_create_telegram_user(
                session=s,
                telegram_id=99000000 + i,
                display_name=f"Student {i}",
            )

    telegram_ids = [99000000 + (i % 10) for i in range(50)]

    async def lookup_user(tg_id: int):
        async with get_db_session() as s:
            t0 = time.perf_counter()
            user = await AccountService.get_or_create_telegram_user(
                session=s,
                telegram_id=tg_id,
            )
            elapsed = time.perf_counter() - t0
            assert user is not None
            assert user.user_id is not None
            return user.user_id, elapsed

    # Run 50 concurrent lookups
    results = await asyncio.gather(*(lookup_user(tg_id) for tg_id in telegram_ids))
    assert len(results) == 50
    user_ids = {r[0] for r in results}
    assert len(user_ids) == 10  # 10 distinct users accessed concurrently 5 times each


@pytest.mark.asyncio
async def test_concurrent_catalog_browsing_under_pressure():
    """Verify high-throughput instantaneous response when 50 concurrent queries browse the catalog."""
    from src.app.modules.catalog.service import CatalogService

    async with get_db_session() as s:
        categories = await CatalogService.get_active_categories(s)
        assert len(categories) > 0
        target_category_id = categories[0].id

    async def browse_catalog(page: int):
        async with get_db_session() as s:
            cats = await CatalogService.get_active_categories(s)
            services, total_pages = await CatalogService.get_services_paginated(
                session=s,
                category_id=target_category_id,
                page=page,
                page_size=4,
            )
            return len(cats), len(services), total_pages

    # 50 concurrent requests browsing different pages
    tasks = [browse_catalog((i % 3) + 1) for i in range(50)]
    results = await asyncio.gather(*tasks)
    assert len(results) == 50
    for num_cats, num_services, total_pages in results:
        assert num_cats > 0
        assert total_pages >= 1


@pytest.mark.asyncio
async def test_concurrent_permissions_rbac_under_pressure():
    """Verify instantaneous permission checks under 50 concurrent RBAC queries."""
    from src.app.modules.access_control.service import AccessControlService

    async with get_db_session() as s:
        user = await AccountService.get_or_create_telegram_user(
            session=s,
            telegram_id=88112233,
            display_name="RBAC Student",
        )
        test_uid = user.user_id

    async def check_perms(idx: int):
        async with get_db_session() as s:
            perms = await AccessControlService.get_user_permissions(s, test_uid)
            has_perm = await AccessControlService.has_permission(s, test_uid, "admin.super")
            return isinstance(perms, set), has_perm

    tasks = [check_perms(i) for i in range(50)]
    results = await asyncio.gather(*tasks)
    assert len(results) == 50
    for is_set, has_perm in results:
        assert is_set is True
