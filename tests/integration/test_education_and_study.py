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


@pytest.mark.asyncio
async def test_quizzes_and_study_groups(db_session):
    from sqlalchemy import text
    from src.app.modules.accounts.service import AccountService

    user = await AccountService.get_or_create_telegram_user(
        db_session, telegram_id=99887766, display_name="Group Explorer"
    )

    # 1. Verify study groups exist in db
    groups_res = await db_session.execute(text("SELECT id, name, invite_code FROM student_platform.study_groups"))
    groups = groups_res.fetchall()
    assert len(groups) >= 1

    # 2. Add student to a group and query membership
    target_group = groups[0]
    await db_session.execute(text("""
        INSERT INTO student_platform.study_group_members (group_id, user_id, member_role, status)
        VALUES (:gid, :uid, 'member', 'active')
        ON CONFLICT (group_id, user_id) DO UPDATE SET status = 'active'
    """), {"gid": target_group.id, "uid": user.user_id})
    await db_session.commit()

    my_groups = (await db_session.execute(text("""
        SELECT g.name FROM student_platform.study_group_members m
        JOIN student_platform.study_groups g ON g.id = m.group_id
        WHERE m.user_id = :uid AND m.status = 'active'
    """), {"uid": user.user_id})).fetchall()
    assert len(my_groups) >= 1

    # 3. Verify Quizzes and Options
    quizzes = (await db_session.execute(text("""
        SELECT q.id, q.title, count(qvi.id) as q_count
        FROM student_platform.quizzes q
        JOIN student_platform.quiz_versions qv ON qv.quiz_id = q.id
        JOIN student_platform.quiz_version_items qvi ON qvi.quiz_version_id = qv.id
        GROUP BY q.id, q.title
    """))).fetchall()
    assert len(quizzes) >= 1
    first_quiz = quizzes[0]
    assert first_quiz.q_count >= 1
