"""Telegym high-concurrency load test: 5,000 simultaneous users."""
from __future__ import annotations

import asyncio
import os
import statistics
import time
from dataclasses import dataclass

import aiohttp

MOCK = os.getenv("TELEGYM_MOCK_URL", "http://127.0.0.1:5678")
TOKEN = os.getenv("TELEGYM_BOT_TOKEN", "1234567890:telegym_test_token_xxxxxxxx")
USERS = int(os.getenv("TELEGYM_USERS", "5000"))
COMMAND = os.getenv("TELEGYM_LOAD_COMMAND", "/help")
COMMANDS = [item.strip() for item in os.getenv("TELEGYM_LOAD_COMMANDS", "").split(",") if item.strip()]
CHAT_BASE = int(os.getenv("TELEGYM_CHAT_BASE", "93000000"))
REQUEST_TIMEOUT = float(os.getenv("TELEGYM_REQUEST_TIMEOUT", "30"))


@dataclass
class Result:
    chat_id: int
    injected: bool
    inject_ms: float
    error: str = ""


async def post_json(session: aiohttp.ClientSession, path: str, payload: dict) -> tuple[int, dict]:
    async with session.post(MOCK + path, json=payload) as response:
        return response.status, await response.json(content_type=None)


async def inject_one(session: aiohttp.ClientSession, chat_id: int, command: str) -> Result:
    started = time.perf_counter()
    try:
        status, body = await post_json(
            session,
            "/debug/inject/update",
            {"token": TOKEN, "user_id": chat_id, "chat_id": chat_id, "text": command},
        )
        elapsed = (time.perf_counter() - started) * 1000
        if status != 200 or not body.get("ok"):
            return Result(chat_id, False, elapsed, f"inject status={status} body={body}")
        return Result(chat_id, True, elapsed)
    except Exception as exc:
        return Result(chat_id, False, (time.perf_counter() - started) * 1000,
                      f"{type(exc).__name__}: {exc}")


async def collect_replies(session: aiohttp.ClientSession, target_ids: set[int]) -> tuple[set[int], float]:
    """Poll one aggregate endpoint, not 5,000 per-chat endpoints."""
    deadline = time.perf_counter() + REQUEST_TIMEOUT
    first_seen_at: float | None = None
    while time.perf_counter() < deadline:
        async with session.get(
            MOCK + f"/debug/messages/{TOKEN}?chat_id=0&limit={max(USERS + 100, 10000)}"
        ) as response:
            data = await response.json(content_type=None)
        seen = {
            int(message.get("chat", {}).get("id"))
            for message in data.get("messages", [])
            if int(message.get("chat", {}).get("id", -1)) in target_ids
        }
        if seen and first_seen_at is None:
            first_seen_at = time.perf_counter()
        if len(seen) >= len(target_ids):
            return seen, (time.perf_counter() - first_seen_at) * 1000 if first_seen_at else 0.0
        await asyncio.sleep(0.2)
    return seen, (time.perf_counter() - first_seen_at) * 1000 if first_seen_at else REQUEST_TIMEOUT * 1000


async def main() -> None:
    commands = COMMANDS or [COMMAND]
    connector = aiohttp.TCPConnector(limit=max(USERS + 100, 1000), limit_per_host=0)
    timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT + 10, connect=10)
    started = time.perf_counter()
    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        results = await asyncio.gather(
            *(inject_one(session, CHAT_BASE + index, commands[index % len(commands)])
              for index in range(USERS))
        )
        injected_ids = {result.chat_id for result in results if result.injected}
        replied_ids, reply_window_ms = await collect_replies(session, injected_ids)
    elapsed_ms = (time.perf_counter() - started) * 1000
    injected = [result for result in results if result.injected]
    inject_latencies = [result.inject_ms for result in results]
    errors = [result.error for result in results if result.error]
    print(f"users={USERS} commands={','.join(commands)} burst_elapsed_ms={elapsed_ms:.1f}")
    print(f"injected={len(injected)}/{USERS} ({len(injected) / USERS:.2%})")
    print(f"replied={len(replied_ids)}/{USERS} ({len(replied_ids) / USERS:.2%})")
    print(f"aggregate_reply_window_ms={reply_window_ms:.1f}")
    if inject_latencies:
        print(f"inject_ms p50={statistics.median(inject_latencies):.1f} max={max(inject_latencies):.1f}")
    if errors:
        print("sample_errors:")
        for error in errors[:10]:
            print(f"  {error}")
    assert len(injected) >= int(USERS * 0.99), f"injection SLO failed: {len(injected)}/{USERS}"
    assert len(replied_ids) >= int(USERS * 0.99), f"reply SLO failed: {len(replied_ids)}/{USERS}"
    print("Telegym 5000-user concurrent load suite passed")


if __name__ == "__main__":
    asyncio.run(main())
