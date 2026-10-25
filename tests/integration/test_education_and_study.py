import uuid
import pytest
from src.app.modules.accounts.service import AccountService
from src.app.modules.education.service import EducationService


@pytest.mark.asyncio
async def test_education_focus_and_flashcards(db_session):
    # 1. Setup user
    user = await AccountService.get_or_create_telegram_user(
        db_session, telegram_id=554433221, display_name="Study Student"
    )

    # 2. Flashcard deck creation and cards adding
    deck = await EducationService.create_deck(
        session=db_session,
        user_id=user.user_id,
        title="مصطلحات الإحصاء الأكاديمي",
    )
    assert deck.id is not None
    assert deck.card_count == 0

    c1 = await EducationService.add_card(
        session=db_session,
        deck_id=deck.id,
        front="الانحراف المعياري (Standard Deviation)",
        back="مقياس لمدى تشتت أو تباعد قيم مجموعة البيانات عن وسطها الحسابي.",
    )
    assert c1.id is not None
    assert deck.card_count == 1

    # 3. Focus Session (Pomodoro)
    fs = await EducationService.start_focus_session(
        session=db_session,
        user_id=user.user_id,
        subject_name="إحصاء 101",
        planned_minutes=25,
    )
    assert fs.status == "running"
    assert fs.focus_minutes == 25

    completed_fs = await EducationService.complete_focus_session(db_session, fs.id)
    assert completed_fs.status == "completed"
    assert completed_fs.focus_minutes >= 25

    # 4. Check user focus statistics
    stats = await EducationService.get_user_focus_stats(db_session, user.user_id)
    assert stats["total_sessions"] >= 1
    assert stats["total_minutes"] >= 25
