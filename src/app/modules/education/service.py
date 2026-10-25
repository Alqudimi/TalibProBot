import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from src.app.modules.education.models import Flashcard, FlashcardDeck, FocusSession, LearningPlan
from src.app.observability.logging import get_logger

logger = get_logger("education")


class EducationService:
    """Service handling self-learning tools: flashcards, focus sessions, and learning plans."""

    # Flashcards
    @staticmethod
    async def create_deck(
        session: AsyncSession,
        user_id: uuid.UUID,
        title: str,
        description: Optional[str] = None,
    ) -> FlashcardDeck:
        deck = FlashcardDeck(
            id=uuid.uuid4(),
            owner_user_id=user_id,
            title=title,
            description=description,
            visibility="private",
            access="private",
            status="active",
        )
        deck.cards = []
        session.add(deck)
        await session.flush()
        return deck

    @staticmethod
    async def add_card(
        session: AsyncSession,
        deck_id: uuid.UUID,
        front: str,
        back: str,
    ) -> Flashcard:
        card = Flashcard(
            id=uuid.uuid4(),
            deck_id=deck_id,
            front_text=front,
            back_text=back,
            explanation=None,
            sort_order=0,
            version_number=1,
            is_active=True,
        )
        session.add(card)
        await session.flush()
        # Expire deck cards relationship cache so card_count is updated
        stmt = select(FlashcardDeck).options(selectinload(FlashcardDeck.cards)).where(FlashcardDeck.id == deck_id)
        res = await session.execute(stmt)
        deck = res.scalar_one_or_none()
        if deck:
            await session.refresh(deck, ["cards"])
        return card

    @staticmethod
    async def get_user_decks(session: AsyncSession, user_id: uuid.UUID) -> List[FlashcardDeck]:
        stmt = (
            select(FlashcardDeck)
            .options(selectinload(FlashcardDeck.cards))
            .where(FlashcardDeck.owner_user_id == user_id)
            .order_by(FlashcardDeck.created_at.desc())
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    # Focus Sessions (Pomodoro)
    @staticmethod
    async def start_focus_session(
        session: AsyncSession,
        user_id: uuid.UUID,
        subject_name: Optional[str] = "مذاكرة عامة",
        planned_minutes: int = 25,
    ) -> FocusSession:
        fs = FocusSession(
            id=uuid.uuid4(),
            user_id=user_id,
            focus_minutes=planned_minutes,
            break_minutes=5,
            status="running",
            started_at=datetime.now(timezone.utc),
        )
        session.add(fs)
        await session.flush()
        return fs

    @staticmethod
    async def complete_focus_session(session: AsyncSession, session_id: uuid.UUID) -> Optional[FocusSession]:
        stmt = select(FocusSession).where(FocusSession.id == session_id)
        result = await session.execute(stmt)
        fs = result.scalar_one_or_none()
        if not fs:
            return None
        now = datetime.now(timezone.utc)
        fs.ended_at = now
        fs.status = "completed"
        await session.flush()
        return fs

    @staticmethod
    async def get_user_focus_stats(session: AsyncSession, user_id: uuid.UUID) -> dict:
        stmt = (
            select(
                func.count(FocusSession.id).label("total_sessions"),
                func.coalesce(func.sum(FocusSession.focus_minutes), 0).label("total_minutes"),
            )
            .where(FocusSession.user_id == user_id, FocusSession.status == "completed")
        )
        result = await session.execute(stmt)
        row = result.fetchone()
        return {
            "total_sessions": row[0] if row else 0,
            "total_minutes": row[1] if row else 0,
        }

