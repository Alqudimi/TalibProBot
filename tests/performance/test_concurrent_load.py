import asyncio
import uuid
import pytest
from src.app.infrastructure.database.session import get_db_session
from src.app.modules.accounts.service import AccountService
from src.app.modules.education.service import EducationService


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
