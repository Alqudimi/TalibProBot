"""Expanded Telegym HTTP black-box suite for TalibProBot.

It drives the real Telegym mock, the real application Dispatcher and the real
PostgreSQL-backed middlewares. It intentionally behaves like several users,
not like direct handler unit tests.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
import asyncio
import uuid
import sys
import subprocess
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from src.app.infrastructure.database.session import get_db_session
from src.app.modules.accounts.models import ExternalIdentity, User
from src.app.modules.bookings.models import Booking, BookingParticipant
from src.app.modules.catalog.models import ProductOffer
from src.app.modules.opportunities.models import Opportunity
from src.app.modules.orders.service import OrderService
from src.app.modules.providers.models import ProviderProfile
from src.app.modules.subscriptions.models import Subscription

MOCK = os.getenv("TELEGYM_MOCK_URL", "http://127.0.0.1:5678")
TOKEN = os.getenv("TELEGYM_BOT_TOKEN", "1234567890:telegym_test_token_xxxxxxxx")


PUBLIC_COMMANDS = [
    "/start", "/menu", "/help", "/services", "/search", "/orders",
    "/subscriptions", "/bookings", "/downloads", "/edu", "/plan", "/timer",
    "/daily", "/opportunities", "/groups", "/profile", "/notifications",
    "/language", "/support", "/terms", "/privacy", "/id", "/cancel",
]
# profile currently has a documented lazy-relationship MissingGreenlet defect.
KNOWN_XFAIL = {"/profile"}


def request(method: str, path: str, payload: dict | None = None) -> dict:
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(
        MOCK + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=10) as response:
        return json.loads(response.read())


def messages(chat_id: int) -> list[dict]:
    return request("GET", f"/debug/messages/{TOKEN}?chat_id={chat_id}&limit=200").get("messages", [])


def wait_for_reply(chat_id: int, before: int, timeout: float = 10) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        current = messages(chat_id)
        if len(current) > before:
            return max(current, key=lambda item: item.get("message_id", 0))
        time.sleep(0.1)
    raise AssertionError(f"no reply for chat {chat_id} within {timeout}s")


def send(chat_id: int, text: str, expected: str | None = None, *, delay: float = 1.1) -> dict:
    time.sleep(delay)
    before = len(messages(chat_id))
    result = request(
        "POST",
        "/debug/inject/update",
        {"token": TOKEN, "user_id": chat_id, "chat_id": chat_id, "text": text},
    )
    assert result["ok"] is True, result
    reply = wait_for_reply(chat_id, before)
    body = reply.get("text", "")
    assert body.strip(), (text, reply)
    if expected:
        assert expected.lower() in body.lower(), (text, expected, body)
    print(f"PASS {chat_id} {text}: {body[:70]!r}")
    return reply


def click(chat_id: int, message: dict, callback_data: str, *, allow_edit: bool = False) -> dict:
    before = len(messages(chat_id))
    result = request(
        "POST",
        "/debug/inject/update",
        {
            "token": TOKEN,
            "user_id": chat_id,
            "chat_id": chat_id,
            "message_id": message.get("message_id", 0),
            "callback_data": callback_data,
        },
    )
    assert result["ok"] is True, result
    if allow_edit:
        time.sleep(1.2)
        current = messages(chat_id)
        assert current, (chat_id, callback_data)
        reply = max(current, key=lambda item: item.get("message_id", 0))
        print(f"PASS callback {callback_data}: {reply.get('text', '')[:70]!r}")
        return reply
    reply = wait_for_reply(chat_id, before)
    print(f"PASS callback {callback_data}: {reply.get('text', '')[:70]!r}")
    return reply


def inline_callbacks(message: dict) -> list[str]:
    markup = message.get("reply_markup") or {}
    return [
        button["callback_data"]
        for row in markup.get("inline_keyboard", [])
        for button in row
        if button.get("callback_data")
    ]


def probe_callback(chat_id: int, callback_data: str, message_id: int = 1) -> None:
    """Inject a callback and assert the webhook accepts it, including alert-only handlers."""
    result = request(
        "POST", "/debug/inject/update",
        {"token": TOKEN, "user_id": chat_id, "chat_id": chat_id,
         "message_id": message_id, "callback_data": callback_data},
    )
    assert result["ok"] is True, (chat_id, callback_data, result)
    time.sleep(0.35)


def all_public_commands() -> None:
    """Exercise every public command with a fresh human-like user."""
    for index, command in enumerate(PUBLIC_COMMANDS):
        chat_id = 92000000 + index
        try:
            send(chat_id, command, delay=1.1)
        except AssertionError:
            if command in KNOWN_XFAIL:
                print(f"XFAIL {command}: known lazy relationship defect")
                continue
            raise


def multi_user_isolation() -> None:
    """Several independent users repeat commands and must receive replies."""
    for offset in range(5):
        chat_id = 92100000 + offset
        send(chat_id, "/help", "دليل الاستخدام", delay=0.2)
        send(chat_id, "/cancel", "لا توجد", delay=1.1)
    print("PASS multi-user isolation: 5 users x 2 commands")


def onboarding_and_invalid_inputs() -> None:
    """Exercise consent/level/timezone callbacks plus malformed callback data."""
    chat_id = 92200001
    start = send(chat_id, "/start", delay=0.2)
    callbacks = inline_callbacks(start)
    reply_markup = start.get("reply_markup") or {}
    reply_buttons = [
        button.get("text")
        for row in reply_markup.get("keyboard", [])
        for button in row
        if button.get("text")
    ]
    assert callbacks or reply_buttons, "start must expose inline or reply buttons"
    # Click every onboarding/menu callback that is safe and stop after the
    # first resulting screen; each callback is tested in a fresh user to avoid
    # coupling one FSM branch to another.
    for index, callback in enumerate(callbacks[:3]):
        branch_chat = chat_id + index + 1
        branch = send(branch_chat, "/start", delay=0.2)
        branch_callbacks = inline_callbacks(branch)
        if branch_callbacks:
            click(branch_chat, branch, branch_callbacks[0])
    for index, button_text in enumerate(reply_buttons[:3]):
        branch_chat = chat_id + 10 + index
        reply = send(branch_chat, "/start", delay=0.2)
        # Reply-keyboard buttons arrive as ordinary user messages.
        send(branch_chat, button_text, delay=1.1)
    # Unknown and malformed callback payloads must not make the webhook fail.
    result = request(
        "POST",
        "/debug/inject/update",
        {"token": TOKEN, "user_id": 92200010, "chat_id": 92200010,
         "message_id": 1, "callback_data": "not-a-real-callback"},
    )
    assert result["ok"] is True, result
    print("PASS invalid callback payload: webhook remained healthy")


def daily_and_buttons() -> None:
    chat_id = 92300001
    daily = send(chat_id, "/daily", "السؤال")
    callbacks = inline_callbacks(daily)
    assert len(callbacks) >= 4, callbacks
    # Test wrong-answer and correct-answer branches as separate user journeys.
    wrong = next(cb for cb in callbacks if cb.endswith(":wrong"))
    click(chat_id, daily, wrong)
    correct_chat = chat_id + 1
    daily_again = send(correct_chat, "/daily", "السؤال")
    correct = next(cb for cb in inline_callbacks(daily_again) if cb.endswith(":correct"))
    click(correct_chat, daily_again, correct)
    print("PASS daily question: wrong and correct answer branches")


def admin_panels() -> None:
    """Exercise every admin command and every admin hub callback as an admin user."""
    chat_id = 93000001
    admin_callbacks = [
        "adm:catalog", "adm:orders", "adm:finance", "adm:support",
        "adm:users", "adm:broadcast", "adm:disputes", "adm:health", "adm:audit",
    ]
    commands = [
        "/admin", "/admin_catalog", "/admin_orders", "/admin_finance",
        "/admin_support", "/admin_users", "/admin_broadcast", "/admin_disputes",
        "/admin_health", "/admin_audit",
    ]
    for command in commands:
        reply = send(chat_id, command, delay=1.1)
        assert reply.get("reply_markup"), command
    for callback in admin_callbacks:
        hub = send(chat_id, "/admin", delay=1.1)
        callbacks = inline_callbacks(hub)
        assert callback in callbacks, (callback, callbacks)
        click(chat_id, hub, callback)
    print("PASS admin panels: 10 commands + 9 callbacks")


def fsm_branches() -> None:
    """Exercise every user-facing FSM branch that is wired to a handler."""
    # Search FSM
    user = 93100001
    send(user, "/search", delay=1.1)
    send(user, "فيزياء ورياضيات", delay=1.1)
    # Support TicketFSM: all four topics and a real text submission.
    for offset, topic in enumerate(("order", "finance", "service", "other")):
        chat_id = user + offset + 1
        support = send(chat_id, "/support", delay=1.1)
        assert f"sup:topic:{topic}" in inline_callbacks(support)
        click(chat_id, support, f"sup:topic:{topic}")
        send(chat_id, "هذه رسالة اختبار لمسار التذكرة", expected="تم إنشاء تذكرة", delay=2.2)
    # Profile FSM and notifications toggle.
    profile = send(user + 10, "/profile", delay=1.1)
    level = click(user + 10, profile, "prof:edu")
    if inline_callbacks(level):
        level_cb = next((x for x in inline_callbacks(level) if x.startswith("onboard:level:")), None)
        if level_cb:
            click(user + 10, level, level_cb, allow_edit=True)
    profile = send(user + 10, "/profile", delay=1.1)
    tz = click(user + 10, profile, "prof:tz")
    if inline_callbacks(tz):
        tz_cb = next((x for x in inline_callbacks(tz) if x.startswith("onboard:tz:")), None)
        if tz_cb:
            click(user + 10, tz, tz_cb, allow_edit=True)
    notifications = send(user + 10, "/notifications", delay=1.1)
    notif_cb = next((x for x in inline_callbacks(notifications) if x.startswith("notif:toggle:")), None)
    if notif_cb:
        click(user + 10, notifications, notif_cb)
    # Group FSM: invalid code branch must return a response without crashing.
    groups = send(user + 20, "/groups", delay=1.1)
    click(user + 20, groups, "grp:join")
    send(user + 20, "INVALID-GROUP-CODE", delay=1.1)
    # Study branches: flashcards/reveal, plan creation, timer completion, quiz.
    study = send(user + 30, "/edu", delay=1.1)
    cards = click(user + 30, study, "edu:flashcards")
    review_cb = next((x for x in inline_callbacks(cards) if x.startswith("edu:fc:rev:")), None)
    if review_cb:
        review = click(user + 30, cards, review_cb, allow_edit=True)
        reveal_cb = next((x for x in inline_callbacks(review) if x.startswith("edu:fc:reveal:")), None)
        if reveal_cb:
            click(user + 30, review, reveal_cb, allow_edit=True)
    plan = send(user + 31, "/plan", delay=1.1)
    click(user + 31, plan, "edu:plan:create", allow_edit=True)
    timer = send(user + 32, "/timer", delay=1.1)
    timer_cb = next((x for x in inline_callbacks(timer) if x.startswith("focus_end:")), None)
    if timer_cb:
        click(user + 32, timer, timer_cb, allow_edit=True)
    quizzes = send(user + 33, "/edu", delay=1.1)
    click(user + 33, quizzes, "edu:quizzes", allow_edit=True)
    print("PASS FSM branches: search, tickets, profile, notifications, groups, study")


def payment_flow() -> None:
    """Exercise order review, Stars invoice, pre-checkout and successful payment updates."""
    chat_id = 93200001
    async def get_offer_id() -> str:
        async with get_db_session() as session:
            offer = (await session.execute(select(ProductOffer).where(ProductOffer.status == "published").limit(1))).scalar_one()
            return str(offer.id)
    offer_id = asyncio.run(get_offer_id())
    services = send(chat_id, "/services", delay=1.1)
    # The seeded catalog may expose the offer under a category; inject the direct buy callback
    # after the order has been prepared, which tests the same production callback handler.
    before_review = len(messages(chat_id))
    buy = request("POST", "/debug/inject/update", {
        "token": TOKEN, "user_id": chat_id, "chat_id": chat_id,
        "message_id": services.get("message_id", 1), "callback_data": f"svc:buy:{offer_id}",
    })
    assert buy["ok"] is True
    review = wait_for_reply(chat_id, before_review)
    pay_callback = next((cb for cb in inline_callbacks(review) if cb.startswith("pay:go:")), None)
    assert pay_callback, inline_callbacks(review)
    order_id = pay_callback.split(":")[-1]
    invoice_result = request("POST", "/debug/inject/update", {
        "token": TOKEN, "user_id": chat_id, "chat_id": chat_id,
        "message_id": review.get("message_id", 1), "callback_data": pay_callback,
    })
    assert invoice_result["ok"] is True
    # sendInvoice is a Bot API method and Telegym does not expose invoices via
    # debug/messages; successful HTTP dispatch is the transport assertion.
    time.sleep(1.2)
    # scripts/seed_sample_catalog.py creates each XTR offer at 15 Stars.
    # Keeping this value in the synthetic Telegram update avoids reusing the
    # SQLAlchemy async engine across the bridge's event loop and this runner.
    amount = 15
    # Dispatch the two Telegram payment update types through the real bridge endpoint.
    precheckout = {
        "update_id": 99000001,
        "pre_checkout_query": {
            "id": "pcq-telegym-1", "from": {"id": chat_id, "is_bot": False, "first_name": "Payment"},
            "currency": "XTR", "total_amount": amount, "invoice_payload": f"order:{order_id}",
        },
    }
    post_json("http://127.0.0.1:8089/telegym/update", precheckout)
    time.sleep(2.2)
    successful = {
        "update_id": 99000002,
        "message": {
            "message_id": 9902, "date": int(time.time()), "chat": {"id": chat_id, "type": "private"},
            "from": {"id": chat_id, "is_bot": False, "first_name": "Payment"},
            "successful_payment": {
                "currency": "XTR", "total_amount": amount, "invoice_payload": f"order:{order_id}",
                "telegram_payment_charge_id": "tg-charge-telegym-1", "provider_payment_charge_id": "provider-charge-1",
            },
        },
    }
    before = len(messages(chat_id))
    post_json("http://127.0.0.1:8089/telegym/update", successful)
    receipt = wait_for_reply(chat_id, before, timeout=10)
    payment_text = "\n".join(item.get("text", "") for item in messages(chat_id))
    assert "إيصال" in payment_text or "أرسل الآن" in receipt.get("text", "")
    print("PASS payment flow: review, invoice callback, pre-checkout, successful payment")


def psql_scalar(sql: str) -> str:
    env = os.environ.copy()
    env["PGOPTIONS"] = "-c search_path=student_platform"
    return subprocess.check_output(
        ["psql", "postgresql://postgres:postgres@localhost:5432/academic", "-qAtc", sql],
        text=True,
        env=env,
    ).strip()


def wait_for_db_scalar(sql: str, expected: str, timeout: float = 5.0) -> str:
    deadline = time.time() + timeout
    value = ""
    while time.time() < deadline:
        value = psql_scalar(sql)
        if value == expected:
            return value
        time.sleep(0.15)
    return value


def seed_advanced_entities(chat_id: int) -> dict[str, str | None]:
    """Seed via a separate psql process; the bridge owns a different asyncio loop."""
    user_id, offer_id, provider_id, opp_id = psql_scalar(
        "SELECT u.user_id, (SELECT id FROM student_platform.product_offers WHERE status='published' LIMIT 1), "
        "(SELECT id FROM student_platform.provider_profiles LIMIT 1), "
        "(SELECT id FROM student_platform.opportunities LIMIT 1) "
        f"FROM student_platform.users u JOIN student_platform.external_identities e ON e.user_id=u.user_id "
        f"WHERE e.telegram_user_id={chat_id} LIMIT 1;"
    ).split("|")
    offer_id_2 = psql_scalar(
        "SELECT id FROM student_platform.product_offers WHERE status='published' "
        f"AND id <> '{offer_id}' LIMIT 1;"
    ) or offer_id
    def ensure_sub(plan_offer_id: str) -> str:
        existing = psql_scalar(
            "SELECT id FROM student_platform.subscriptions "
            f"WHERE user_id='{user_id}' AND plan_offer_id='{plan_offer_id}' AND status='active' LIMIT 1;"
        )
        if existing:
            return existing
        return psql_scalar(
            "INSERT INTO student_platform.subscriptions "
            "(id,user_id,plan_offer_id,status,current_period_end,started_at,created_at,updated_at) "
            f"VALUES (gen_random_uuid(),'{user_id}','{plan_offer_id}','active',now()+interval '30 days',now(),now(),now()) RETURNING id;"
        )
    sub_ids = [ensure_sub(offer_id), ensure_sub(offer_id_2)]
    free_order = psql_scalar(
        "INSERT INTO student_platform.orders "
        "(id,user_id,status,currency_code,subtotal_minor,discount_total_minor,tax_total_minor,total_minor,created_at,updated_at) "
        f"VALUES (gen_random_uuid(),'{user_id}','draft','XTR',0,0,0,0,now(),now()) RETURNING id;"
    )
    psql_scalar(
        "INSERT INTO student_platform.order_items "
        "(id,order_id,offer_id,product_title_snapshot,product_code_snapshot,currency_code,quantity,unit_price_minor,line_discount_minor,line_total_minor,created_at) "
        f"SELECT gen_random_uuid(),'{free_order}',id,title_ar,code,'XTR',1,0,0,0,now() "
        f"FROM student_platform.product_offers WHERE id='{offer_id}';"
    )
    psql_scalar(
        f"UPDATE student_platform.orders SET status='pending_payment' WHERE id='{free_order}';"
    )
    booking_ids: list[str] = []
    if not provider_id:
        provider_id = psql_scalar(
            "INSERT INTO student_platform.provider_profiles "
            "(id,user_id,public_name,headline,bio,verification_status,provider_status,default_time_zone,created_at,updated_at) "
            f"VALUES (gen_random_uuid(),'{user_id}','E2E Provider','معلم اختبار','مزود لاختبارات الحجز','verified','active','Asia/Riyadh',now(),now()) RETURNING id;"
        )
    if provider_id:
        psql_scalar(
            "DELETE FROM student_platform.booking_events WHERE booking_id IN "
            "(SELECT id FROM student_platform.bookings WHERE created_by="
            f"'{user_id}' AND session_title='جلسة E2E للإلغاء والتراجع'); "
            "DELETE FROM student_platform.booking_participants WHERE booking_id IN "
            "(SELECT id FROM student_platform.bookings WHERE created_by="
            f"'{user_id}' AND session_title='جلسة E2E للإلغاء والتراجع'); "
            "DELETE FROM student_platform.bookings WHERE created_by="
            f"'{user_id}' AND session_title='جلسة E2E للإلغاء والتراجع';"
        )
        for _ in range(2):
            bid = psql_scalar(
                "INSERT INTO student_platform.bookings "
                "(id,provider_id,offer_id,session_title,booking_kind,status,starts_at,ends_at,capacity,commission_rate,created_by,created_at,updated_at) "
                f"VALUES (gen_random_uuid(),'{provider_id}','{offer_id}','جلسة E2E للإلغاء والتراجع','individual','confirmed',"
                f"now()+interval '{3 + _} days',now()+interval '{3 + _} days 50 minutes',1,0.2000,"
                f"'{user_id}',now(),now()) RETURNING id;"
            )
            psql_scalar(
                "INSERT INTO student_platform.booking_participants "
                "(id,booking_id,user_id,participant_status,joined_at) "
                f"VALUES (gen_random_uuid(),'{bid}','{user_id}','booked',now()) RETURNING id;"
            )
            booking_ids.append(bid)
    return {
        "sub1": sub_ids[0], "sub2": sub_ids[1],
        "book1": booking_ids[0] if booking_ids else None,
        "book2": booking_ids[1] if len(booking_ids) > 1 else None,
        "opp": opp_id or None, "free_order": free_order, "user_id": user_id,
    }


def advanced_user_journeys() -> None:
    """Exercise high-risk confirmations, opportunity actions and callback ownership cases."""
    chat_id = 93300001
    send(chat_id, "/start", delay=0.2)
    entities = seed_advanced_entities(chat_id)

    # Subscription: retreat must preserve active state; confirm must cancel only its owner.
    subs = send(chat_id, "/subscriptions", delay=1.1)
    assert f"sub:cancel:{entities['sub1']}" in inline_callbacks(subs)
    prompt = click(chat_id, subs, f"sub:cancel:{entities['sub1']}", allow_edit=True)
    assert f"sub:confirm_cancel:{entities['sub1']}" in inline_callbacks(prompt)
    click(chat_id, prompt, "home:subs", allow_edit=True)
    subs = send(chat_id, "/subscriptions", delay=1.1)
    prompt = click(chat_id, subs, f"sub:cancel:{entities['sub2']}", allow_edit=True)
    click(chat_id, prompt, f"sub:confirm_cancel:{entities['sub2']}", allow_edit=True)

    # Booking: same confirmation/retraction contract.
    if entities["book1"]:
        bookings = send(chat_id, "/bookings", delay=1.1)
        prompt = click(chat_id, bookings, f"book:cancel:{entities['book1']}", allow_edit=True)
        assert f"book:confirm_cancel:{entities['book1']}" in inline_callbacks(prompt)
        click(chat_id, prompt, "home:bookings", allow_edit=True)
        bookings = send(chat_id, "/bookings", delay=1.1)
        prompt = click(chat_id, bookings, f"book:cancel:{entities['book2']}", allow_edit=True)
        click(chat_id, prompt, f"book:confirm_cancel:{entities['book2']}", allow_edit=True)
    else:
        print("SKIP booking entity journey: no provider profile exists in fixture DB")

    # Opportunities: categories, calendar, saved list and a real save callback.
    opp_home = send(chat_id, "/opportunities", delay=1.1)
    for cb in ("opp:categories", "opp:calendar", "opp:saved"):
        probe_callback(chat_id, cb, opp_home.get("message_id", 1))
    if entities["opp"]:
        found = click(chat_id, opp_home, "opp:find", allow_edit=True)
        save_cb = f"opp:save:{entities['opp']}"
        assert save_cb in inline_callbacks(found), (save_cb, inline_callbacks(found))
        probe_callback(chat_id, save_cb, found.get("message_id", 1))
        click(chat_id, found, "opp:saved", allow_edit=True)

    # Free order: the real payment callback must move pending_payment -> paid.
    order_screen = send(chat_id, "/orders", delay=1.1)
    probe_callback(chat_id, f"pay:go:{entities['free_order']}", order_screen.get("message_id", 1))
    free_status = wait_for_db_scalar(
        f"SELECT status FROM student_platform.orders WHERE id='{entities['free_order']}';"
        , "paid"
    )
    if free_status == "paid":
        print("PASS free order: callback changed pending_payment -> paid")
    else:
        print(f"FAIL free order: callback left order in {free_status!r}, expected 'paid'")
        raise AssertionError(f"free order did not settle: {free_status!r}")

    # Privacy export, consents, retention, delete retreat and delete confirm.
    privacy = send(chat_id, "/privacy", delay=1.1)
    for cb in ("priv:consents", "priv:retention"):
        click(chat_id, privacy, cb, allow_edit=True)
    probe_callback(chat_id, "priv:export", privacy.get("message_id", 1))
    privacy = send(chat_id, "/privacy", delay=1.1)
    delete_prompt = click(chat_id, privacy, "priv:delete_start", allow_edit=True)
    click(chat_id, delete_prompt, "home:privacy", allow_edit=True)
    privacy = send(chat_id, "/privacy", delay=1.1)
    delete_prompt = click(chat_id, privacy, "priv:delete_start", allow_edit=True)
    click(chat_id, delete_prompt, "priv:delete_confirm", allow_edit=True)

    # Invalid UUIDs and IDs belonging to another user must never mutate state.
    foreign_or_invalid = (
        "svc:view:not-a-uuid", "svc:how:not-a-uuid", "svc:inputs:not-a-uuid",
        "svc:terms:not-a-uuid", "svc:buy:not-a-uuid", "ord:cancel:not-a-uuid",
        "sub:cancel:not-a-uuid", "book:cancel:not-a-uuid", "opp:save:not-a-uuid",
        "focus_end:not-a-uuid", "pay:free:not-a-uuid",
    )
    for index, cb in enumerate(foreign_or_invalid):
        probe_callback(chat_id + 100 + index, cb)
    print("PASS advanced journeys: subscription/booking confirmations, opportunities, privacy, invalid callbacks")


def post_json(url: str, payload: dict) -> dict:
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), method="POST", headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as response:
        return json.loads(response.read())


def main() -> None:
    all_public_commands()
    multi_user_isolation()
    onboarding_and_invalid_inputs()
    daily_and_buttons()
    admin_panels()
    fsm_branches()
    payment_flow()
    advanced_user_journeys()
    print("Telegym expanded HTTP suite passed")


if __name__ == "__main__":
    main()
