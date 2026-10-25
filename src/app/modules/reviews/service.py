import uuid
from typing import List, Optional
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from src.app.modules.reviews.models import ProviderReview, ServiceReview
from src.app.observability.logging import get_logger

logger = get_logger("reviews")


class ReviewService:
    """Service managing quality reviews, ratings, and content moderation."""

    @staticmethod
    async def create_service_review(
        session: AsyncSession,
        user_id: uuid.UUID,
        rating: int,
        review_text: Optional[str] = None,
        order_item_id: Optional[uuid.UUID] = None,
        booking_id: Optional[uuid.UUID] = None,
    ) -> ServiceReview:
        if not (1 <= rating <= 5):
            raise ValueError("Rating must be between 1 and 5.")
        if bool(order_item_id) == bool(booking_id):
            raise ValueError("Review must reference exactly one of order_item_id or booking_id.")

        review = ServiceReview(
            id=uuid.uuid4(),
            user_id=user_id,
            order_item_id=order_item_id,
            booking_id=booking_id,
            rating=rating,
            review_text=review_text,
            moderation_status="approved",
        )
        session.add(review)
        await session.flush()
        logger.info(f"Created review {review.id} by user {user_id} (rating={rating})")
        return review

    @staticmethod
    async def get_average_rating(
        session: AsyncSession,
        provider_id: Optional[uuid.UUID] = None,
    ) -> dict:
        stmt = select(
            func.count(ProviderReview.id).label("total_reviews"),
            func.coalesce(func.avg(ProviderReview.rating), 0.0).label("avg_rating"),
        ).where(ProviderReview.moderation_status == "approved")
        res = await session.execute(stmt)
        row = res.fetchone()
        return {
            "total_reviews": row[0] if row else 0,
            "avg_rating": float(row[1]) if row else 0.0,
        }
