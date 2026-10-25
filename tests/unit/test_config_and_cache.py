import asyncio
import logging
import pytest
from src.app.config.settings import Settings
from src.app.infrastructure.cache.adapter import CacheService, MemoryCacheBackend
from src.app.observability.logging import SecretMaskingFormatter


@pytest.mark.asyncio
async def test_memory_cache_backend_ttl():
    cache = MemoryCacheBackend()
    await cache.set("test_key", {"data": 123}, ttl=1)
    val = await cache.get("test_key")
    assert val == {"data": 123}

    # Wait for TTL expiration
    await asyncio.sleep(1.1)
    expired_val = await cache.get("test_key")
    assert expired_val is None


@pytest.mark.asyncio
async def test_cache_service_fallback_when_disabled():
    cache_svc = CacheService(enabled=False)
    await cache_svc.initialize()
    await cache_svc.set("item_1", "hello_world", ttl=60)
    assert await cache_svc.get("item_1") == "hello_world"
    await cache_svc.delete("item_1")
    assert await cache_svc.get("item_1") is None
    await cache_svc.close()


def test_settings_admin_ids_parsing():
    s1 = Settings(ADMIN_TELEGRAM_IDS="111, 222, 333")
    assert s1.ADMIN_TELEGRAM_IDS == [111, 222, 333]

    s2 = Settings(ADMIN_TELEGRAM_IDS=[999])
    assert s2.ADMIN_TELEGRAM_IDS == [999]


def test_secret_masking_formatter():
    formatter = SecretMaskingFormatter("%(message)s")
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="Bot token: 123456789:ABCdefGHIjklMNOpqrsTUVwxyz1234567 and password: MySecretPassword",
        args=(),
        exc_info=None,
    )
    formatted = formatter.format(record)
    assert "MySecretPassword" not in formatted
    assert "123456789:ABCdefGHIjklMNOpqrsTUVwxyz1234567" not in formatted
    assert "***MASKED***" in formatted
