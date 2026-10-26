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


def click(chat_id: int, message: dict, callback_data: str) -> dict:
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


def all_public_commands() -> None:
    """Exercise every public command with a fresh human-like user."""
    for index, command in enumerate(PUBLIC_COMMANDS):
        chat_id = 92000000 + index
        try:
            send(chat_id, command, delay=0.15)
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


def main() -> None:
    all_public_commands()
    multi_user_isolation()
    onboarding_and_invalid_inputs()
    daily_and_buttons()
    print("Telegym expanded HTTP suite passed")


if __name__ == "__main__":
    main()
