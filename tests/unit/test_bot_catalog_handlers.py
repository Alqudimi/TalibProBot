import uuid
import pytest
from src.app.bot.keyboards.inline import service_card_keyboard, order_review_keyboard
from src.app.modules.catalog.models import ServiceDefinition, ProductOffer, OfferPrice
from src.app.modules.orders.models import Order


def test_service_card_keyboard_with_offer_prices():
    service_id = uuid.uuid4()
    offer = ProductOffer(
        id=uuid.uuid4(),
        code="OFFER_TEST",
        title_ar="عرض اختباري",
        status="published",
    )
    price = OfferPrice(
        id=uuid.uuid4(),
        offer_id=offer.id,
        currency_code="XTR",
        amount_minor=5000,
    )
    offer.prices = [price]

    kb = service_card_keyboard(service_id, [offer])
    assert kb is not None
    assert len(kb.inline_keyboard) >= 2
    button_text = kb.inline_keyboard[0][0].text
    assert "50.00 XTR" in button_text or "عرض اختباري" in button_text


def test_order_payment_required_property():
    order = Order(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        status="draft",
        total_minor=1000,
    )
    assert order.payment_required is True

    paid_order = Order(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        status="paid",
        total_minor=1000,
    )
    assert paid_order.payment_required is False

    free_order = Order(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        status="draft",
        total_minor=0,
    )
    assert free_order.payment_required is False

    kb = order_review_keyboard(order.id, order.payment_required)
    assert kb is not None
    assert any("دفع" in btn.text for row in kb.inline_keyboard for btn in row)
