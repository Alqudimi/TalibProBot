"""Exhaustive contract tests for the complete bot surface.

These tests intentionally exercise every registered academic service and every
keyboard factory, then validate the invariants shared by all user journeys.
"""
import inspect
import re
import uuid
from types import SimpleNamespace
from pathlib import Path

import pytest

from src.app.bot.keyboards import inline as inline_keyboards
from src.app.bot.keyboards import reply as reply_keyboards
from src.app.modules.academic_services.engine import AcademicServiceEngine
from src.app.modules.academic_services.schemas import ServiceInput, ServiceExecutionResult


@pytest.mark.parametrize("service_code", [f"{i:03d}" for i in range(1, 154)])
def test_every_registered_academic_service_executes(service_code):
    """Every advertised service must be routable and return a valid contract."""
    engine = AcademicServiceEngine()
    assert service_code in engine._processors, f"Missing processor registration: {service_code}"

    result = engine._processors[service_code](
        ServiceInput(
            service_code=service_code,
            user_id=str(uuid.uuid4()),
            content="اشرح المفهوم بطريقة تعليمية مع مثال مبسط",
            parameters={"subject": "general", "level": "university"},
        )
    )
    assert isinstance(result, ServiceExecutionResult)
    assert result.service_code == service_code
    assert result.service_name.strip()
    assert result.summary.strip()
    assert result.rendered_output.strip()
    assert result.success is True
    assert result.status.strip()


def _keyboard_factories():
    for name, fn in inspect.getmembers(inline_keyboards, inspect.isfunction):
        if not name.endswith("_keyboard"):
            continue
        signature = inspect.signature(fn)
        kwargs = {}
        for param in signature.parameters.values():
            if param.default is not inspect.Parameter.empty:
                continue
            if param.name.endswith("_id"):
                kwargs[param.name] = uuid.uuid4()
            elif param.name in {"services", "offers"}:
                kwargs[param.name] = []
            elif param.name == "service":
                kwargs[param.name] = SimpleNamespace(
                    service_id=uuid.uuid4(), id=uuid.uuid4(), title_ar="خدمة اختبار",
                    description_ar="وصف اختبار", category_code="general"
                )
            elif param.name == "preferences":
                kwargs[param.name] = {"marketing": True, "orders": True, "study": True}
            elif param.name == "category_code":
                kwargs[param.name] = "instant_auto"
            elif param.name == "cat_code":
                kwargs[param.name] = "instant_auto"
            elif param.name == "page":
                kwargs[param.name] = 1
            elif param.name == "total_pages":
                kwargs[param.name] = 1
            elif param.name == "svc_id":
                kwargs[param.name] = uuid.uuid4()
            else:
                raise AssertionError(f"Unhandled keyboard parameter in {name}: {param.name}")
        yield name, fn, kwargs


def test_every_inline_keyboard_factory_is_constructible_and_safe():
    """All inline layouts must serialize, fit Telegram callback limits, and avoid duplicates."""
    seen_factories = 0
    for name, fn, kwargs in _keyboard_factories():
        keyboard = fn(**kwargs)
        seen_factories += 1
        assert keyboard.inline_keyboard, f"Empty keyboard: {name}"
        callbacks = [
            button.callback_data
            for row in keyboard.inline_keyboard
            for button in row
            if button.callback_data is not None
        ]
        assert callbacks, f"No callbacks in keyboard: {name}"
        assert all(len(callback.encode("utf-8")) <= 64 for callback in callbacks), name
        actionable = [callback for callback in callbacks if callback not in {"sys:noop", "home:menu"}]
        assert len(actionable) == len(set(actionable)), f"Duplicate actionable callback in {name}"
    assert seen_factories >= 15


def test_reply_keyboard_factories_are_constructible():
    for name, fn in inspect.getmembers(reply_keyboards, inspect.isfunction):
        if name.endswith("_keyboard"):
            keyboard = fn()
            assert keyboard.keyboard
            assert all(button.text.strip() for row in keyboard.keyboard for button in row)


def test_all_handler_commands_are_unique_and_have_source_handlers():
    command_files = list(Path("src/app/bot/handlers").glob("*.py"))
    commands = {}
    for path in command_files:
        text = path.read_text()
        for command in re.findall(r"Command(?:Start)?\([\"']([^\"']+)", text):
            commands.setdefault(command, []).append(path.name)
    assert commands
    duplicated = {command: files for command, files in commands.items() if len(files) > 1}
    assert not duplicated, duplicated
    expected = {
        "cancel", "help", "terms", "id", "menu", "services", "search",
        "orders", "downloads", "subscriptions", "bookings", "edu", "timer", "plan",
        "daily", "groups", "opportunities", "support", "profile", "privacy",
        "notifications", "language", "service", "explain", "provider", "provider_hours",
        "provider_requests", "admin", "admin_catalog", "admin_orders", "admin_finance",
        "admin_support", "admin_users", "admin_broadcast", "admin_disputes", "admin_health",
        "admin_audit",
    }
    assert expected <= set(commands)


def test_all_handler_files_are_importable():
    import importlib

    for path in Path("src/app/bot/handlers").glob("*.py"):
        module = importlib.import_module(f"src.app.bot.handlers.{path.stem}")
        assert hasattr(module, "router"), path
        assert module.router is not None
