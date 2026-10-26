import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.app.config.settings import settings
from src.app.modules.accounts.models import (
    ConsentDocument,
    ExternalIdentity,
    User,
    UserConsent,
    UserLearningProfile,
)
from src.app.observability.logging import get_logger

logger = get_logger("accounts")
_terms_document_cache: tuple[uuid.UUID, str] | None = None


class AccountService:
    """Service handling user accounts, telegram identity mapping, profiles and privacy."""

    @staticmethod
    async def get_or_create_telegram_user(
        session: AsyncSession,
        telegram_id: int,
        username: str | None = None,
        display_name: str | None = None,
        language_code: str | None = "ar",
    ) -> User:
        """Finds existing user by telegram_id or creates a new user and identity atomically."""
        stmt = (
            select(User)
            .options(selectinload(User.learning_profile))
            .join(ExternalIdentity, User.user_id == ExternalIdentity.user_id)
            .where(
                ExternalIdentity.provider == "telegram",
                ExternalIdentity.telegram_user_id == telegram_id,
            )
        )
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if user:
            # Keep a bounded activity heartbeat instead of updating this hot
            # row and committing on every Telegram update.
            now = datetime.now(UTC)
            if user.last_seen_at is None or (now - user.last_seen_at).total_seconds() >= 60:
                if settings.REDIS_ENABLED and settings.TASK_WORKER_ENABLED:
                    from src.app.infrastructure.tasks.tasks import (
                        persist_user_heartbeat,
                    )

                    persist_user_heartbeat.delay(str(user.user_id))
                else:
                    user.last_seen_at = now
            if display_name and not user.display_name:
                user.display_name = display_name[:200]
            logger.debug(f"Existing user retrieved: {user.user_id} (telegram_id={telegram_id})")
            return user

        # Create new user
        new_user = User(
            user_id=uuid.uuid4(),
            display_name=(display_name or f"User {telegram_id}")[:200],
            preferred_language="ar",
            last_seen_at=datetime.now(UTC),
        )
        session.add(new_user)

        # Link external identity
        identity = ExternalIdentity(
            id=uuid.uuid4(),
            user_id=new_user.user_id,
            provider="telegram",
            provider_subject=str(telegram_id),
            telegram_user_id=telegram_id,
            provider_username=username,
            metadata_={"initial_first_name": display_name},
        )
        session.add(identity)

        # Create default learning profile
        profile = UserLearningProfile(
            user_id=new_user.user_id,
            education_level_id=3,
            major_or_track="عام",
            goals="تحسين التحصيل الدراسي والإنتاجية",
            preferences={"interests": []},
        )
        session.add(profile)
        # Keep the relationship populated for the current request. The new
        # object has not been round-tripped through selectinload yet, and a
        # synchronous attribute access in a handler must never trigger async
        # lazy IO (MissingGreenlet).
        new_user.learning_profile = profile

        # Record initial implicit terms consent
        global _terms_document_cache
        doc: ConsentDocument | None = None
        if _terms_document_cache is not None:
            doc_id, doc_version = _terms_document_cache
            doc = ConsentDocument(
                id=doc_id,
                consent_type="terms_of_service",
                version=doc_version,
                title="شروط الاستخدام العامة للمنصة",
            )
        else:
            stmt_doc = (
                select(ConsentDocument)
                .where(ConsentDocument.consent_type == "terms_of_service", ConsentDocument.retired_at.is_(None))
                .order_by(ConsentDocument.effective_at.desc())
                .limit(1)
            )
            doc_res = await session.execute(stmt_doc)
            doc = doc_res.scalars().first()
            if doc:
                _terms_document_cache = (doc.id, doc.version)
        if not doc:
            doc = ConsentDocument(
                id=uuid.uuid4(),
                consent_type="terms_of_service",
                version="1.0",
                title="شروط الاستخدام العامة للمنصة",
                effective_at=datetime.now(UTC),
            )
            session.add(doc)
            await session.flush()
            _terms_document_cache = (doc.id, doc.version)

        consent = UserConsent(
            id=uuid.uuid4(),
            user_id=new_user.user_id,
            consent_document_id=doc.id,
            decision="granted",
            context={"channel": "telegram_start", "version": doc.version},
        )
        session.add(consent)

        logger.debug(f"Created new user {new_user.user_id} for telegram_id={telegram_id}")
        return new_user

    @staticmethod
    async def get_user_by_telegram_id(session: AsyncSession, telegram_id: int) -> User | None:
        stmt = (
            select(User)
            .join(ExternalIdentity, User.user_id == ExternalIdentity.user_id)
            .where(
                ExternalIdentity.provider == "telegram",
                ExternalIdentity.telegram_user_id == telegram_id,
            )
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def record_consent(
        session: AsyncSession,
        user_id: uuid.UUID,
        consent_document_id: uuid.UUID,
        decision: str = "granted",
        context: dict | None = None,
        action: str | None = None,
    ) -> UserConsent:
        dec = decision if decision in ("granted", "withdrawn") else ("granted" if action == "agree" else "withdrawn")
        consent = UserConsent(
            id=uuid.uuid4(),
            user_id=user_id,
            consent_document_id=consent_document_id,
            decision=dec,
            context=context or {},
        )
        session.add(consent)
        await session.flush()
        return consent

    @staticmethod
    async def upsert_learning_profile(
        session: AsyncSession,
        user_id: uuid.UUID,
        university: str | None = None,
        major: str | None = None,
        education_level_id: int | None = None,
        goals: str | None = None,
    ) -> UserLearningProfile:
        stmt = select(UserLearningProfile).where(UserLearningProfile.user_id == user_id)
        res = await session.execute(stmt)
        profile = res.scalar_one_or_none()
        if not profile:
            profile = UserLearningProfile(user_id=user_id)
            session.add(profile)
        if university:
            profile.institution_name = university
        if major:
            profile.major_or_track = major
        if education_level_id:
            profile.education_level_id = education_level_id
        if goals:
            profile.goals = goals
        await session.flush()
        return profile
