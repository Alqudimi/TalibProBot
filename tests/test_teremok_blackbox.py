"""Black-box Telegram update tests powered by teremok.

The real aiogram routers and middlewares receive synthetic Telegram updates,
while teremok captures every outgoing Bot API method and validates payloads.
"""
import pytest
import pytest_asyncio
from aiogram.types import User
from teremok import MockBot, MockCallbackQuery, MockMessageText

from src.app.bootstrap.app import Application
from src.app.bot.middlewares.db import DatabaseSessionMiddleware
from src.app.bot.middlewares.user import UserRegistrationMiddleware
from src.app.infrastructure.database.session import close_db_engine

pytestmark = pytest.mark.asyncio(loop_scope="module")


PUBLIC_COMMANDS = [
    "/help", "/terms", "/menu", "/services", "/orders", "/downloads",
    "/subscriptions", "/bookings", "/edu", "/plan", "/timer", "/daily",
    "/opportunities", "/groups", "/profile", "/notifications", "/language",
    "/support", "/privacy", "/id", "/cancel",
]


@pytest.fixture(scope="module")
def dispatcher():
    app = Application()
    # Keep the real DB and account-registration middlewares. The production
    # throttler is intentionally omitted here so a test can model several
    # user actions in one event loop without waiting between Telegram updates.
    app.dp.message.middleware(DatabaseSessionMiddleware())
    app.dp.callback_query.middleware(DatabaseSessionMiddleware())
    app.dp.message.middleware(UserRegistrationMiddleware())
    app.dp.callback_query.middleware(UserRegistrationMiddleware())
    app.register_routers()
    return app.dp


@pytest_asyncio.fixture
async def blackbox_bot(dispatcher):
    # Routers are module-global in the production bot, so only the transport
    # is recreated per test. This also prevents request capture from leaking.
    bot = MockBot(dispatcher, validate=True)
    try:
        yield bot
    finally:
        await close_db_engine()


def _test_user(user_id: int = 41000001) -> User:
    return User(id=user_id, is_bot=False, first_name="E2E", last_name="Student", username=f"e2e_{user_id}")


@pytest.mark.asyncio
@pytest.mark.parametrize("command", PUBLIC_COMMANDS)
async def test_every_public_command_is_handled_by_real_routers(blackbox_bot, command):
    result = await blackbox_bot.dispatch(
        MockMessageText(command, user=_test_user(41001000 + PUBLIC_COMMANDS.index(command)))
    )
    assert result.handled, command
    assert blackbox_bot.requests.all, f"No Bot API response captured for {command}"


@pytest.mark.asyncio
async def test_daily_quiz_success_and_failure_buttons(blackbox_bot):
    user = _test_user(41000002)
    result = await blackbox_bot.dispatch(MockMessageText("/daily", user=user))
    assert result.handled
    await blackbox_bot.dispatch(MockCallbackQuery("edu:daily:ans:correct", user=user))
    await blackbox_bot.dispatch(MockCallbackQuery("edu:daily:ans:wrong", user=user))
    assert len(blackbox_bot.requests.all) >= 3


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "callback_data",
    [
        "home:menu", "home:services", "home:my", "home:subs", "home:bookings",
        "home:edu", "home:opp", "home:support", "home:profile", "home:privacy",
        "edu:hub", "edu:timer", "edu:flashcards", "edu:plan", "edu:quizzes",
        "edu:groups", "opp:find", "opp:saved", "opp:calendar", "grp:mine",
        "grp:join", "grp:request", "sup:faq", "sup:mine", "prof:edu",
        "prof:tz", "prof:notif", "priv:retention", "priv:consents", "ent:status",
    ],
)
async def test_navigation_button_callbacks_are_dispatchable(blackbox_bot, callback_data):
    result = await blackbox_bot.dispatch(
        MockCallbackQuery(callback_data, user=_test_user(41002000 + hash(callback_data) % 1000))
    )
    assert result.handled, callback_data
    assert blackbox_bot.requests.all, f"No response captured for {callback_data}"


@pytest.mark.asyncio
async def test_onboarding_and_fsm_input_round_trip(blackbox_bot):
    user = _test_user(41000004)
    await blackbox_bot.dispatch(MockMessageText("/start", user=user))
    await blackbox_bot.dispatch(MockCallbackQuery("terms:read", user=user))
    await blackbox_bot.dispatch(MockCallbackQuery("priv:read", user=user))
    await blackbox_bot.dispatch(MockCallbackQuery("onboard:agree", user=user))
    await blackbox_bot.dispatch(MockCallbackQuery("onboard:level:university", user=user))
    await blackbox_bot.dispatch(MockCallbackQuery("onboard:tz:Asia/Riyadh", user=user))
    assert len(blackbox_bot.requests.all) >= 6


@pytest.mark.asyncio
async def test_search_and_support_fsm_paths_accept_user_text(blackbox_bot):
    user = _test_user(41000005)
    await blackbox_bot.dispatch(MockMessageText("/search", user=user))
    await blackbox_bot.dispatch(MockMessageText("رياضيات", user=user))
    await blackbox_bot.dispatch(MockMessageText("/support", user=user))
    await blackbox_bot.dispatch(MockCallbackQuery("sup:topic:other", user=user))
    await blackbox_bot.dispatch(MockMessageText("أحتاج مساعدة في طلب تجريبي", user=user))
    assert blackbox_bot.requests.all


@pytest.mark.asyncio
async def test_sensitive_callback_inputs_do_not_crash_and_are_captured(blackbox_bot):
    user = _test_user(41000006)
    dynamic_callbacks = [
        "cat:instant_auto", "cat:instant_auto:p1", "cat:popular",
        "svc:view:00000000-0000-0000-0000-000000000000",
        "svc:how:00000000-0000-0000-0000-000000000000",
        "svc:inputs:00000000-0000-0000-0000-000000000000",
        "svc:terms:00000000-0000-0000-0000-000000000000",
        "ord:cancel:00000000-0000-0000-0000-000000000000",
        "sub:cancel:00000000-0000-0000-0000-000000000000",
        "book:cancel:00000000-0000-0000-0000-000000000000",
        "opp:save:00000000-0000-0000-0000-000000000000",
        "focus_end:00000000-0000-0000-0000-000000000000",
    ]
    for callback_data in dynamic_callbacks:
        result = await blackbox_bot.dispatch(MockCallbackQuery(callback_data, user=user))
        assert result.handled, callback_data
    assert blackbox_bot.requests.all
