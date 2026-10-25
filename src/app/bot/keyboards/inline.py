import uuid
from typing import List, Optional
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from src.app.modules.catalog.models import ProductOffer, ServiceCategory, ServiceDefinition


def main_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📚 دليل الخدمات والكتالوج", callback_data="menu:catalog")
    builder.button(text="🔍 بحث عن خدمة", callback_data="menu:search")
    builder.button(text="⏱️ مؤقت التركيز (Pomodoro)", callback_data="menu:focus")
    builder.button(text="🃏 بطاقات المذاكرة (Flashcards)", callback_data="menu:flashcards")
    builder.button(text="📦 طلباتي وسجل المشتريات", callback_data="menu:orders")
    builder.button(text="👤 ملفي الدراسي والإعدادات", callback_data="menu:profile")
    builder.button(text="🛡️ سياسة النزاهة والخصوصية", callback_data="menu:privacy")
    builder.adjust(2, 2, 2, 1)
    return builder.as_markup()


def categories_keyboard(categories: List[ServiceCategory]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for cat in categories:
        builder.button(text=f"📁 {cat.name_ar}", callback_data=f"cat:{cat.id}")
    builder.button(text="🔙 القائمة الرئيسية", callback_data="nav:home")
    builder.adjust(2)
    return builder.as_markup()


def services_keyboard(services: List[ServiceDefinition], category_id: Optional[uuid.UUID] = None) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for s in services:
        builder.button(text=s.title_ar, callback_data=f"srv:{s.id}")
    if category_id:
        builder.button(text="🔙 رجوع للتصنيفات", callback_data="menu:catalog")
    builder.button(text="🏠 الرئيسية", callback_data="nav:home")
    builder.adjust(1)
    return builder.as_markup()


def service_card_keyboard(service_id: uuid.UUID, offers: List[ProductOffer]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for offer in offers:
        price_text = "طلب الآن"
        if offer.prices:
            first_price = offer.prices[0]
            price_text = f"شراء ({first_price.price_minor} {first_price.currency_code})"
        builder.button(text=f"🛒 {offer.title_ar} - {price_text}", callback_data=f"buy:{offer.id}")

    builder.button(text="🔙 العودة للخدمات", callback_data="menu:catalog")
    builder.button(text="🏠 الرئيسية", callback_data="nav:home")
    builder.adjust(1)
    return builder.as_markup()


def order_review_keyboard(order_id: uuid.UUID, payment_required: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if payment_required:
        builder.button(text="💳 متابعة للدفع (Telegram Stars)", callback_data=f"pay:{order_id}")
    else:
        builder.button(text="🚀 تأكيد وتفعيل الطلب (مجاني)", callback_data=f"confirm_free:{order_id}")
    builder.button(text="❌ إلغاء الطلب", callback_data=f"cancel_order:{order_id}")
    builder.button(text="🏠 القائمة الرئيسية", callback_data="nav:home")
    builder.adjust(1)
    return builder.as_markup()


def focus_session_keyboard(session_id: uuid.UUID) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ إنهاء الجلسة واحتساب الوقت", callback_data=f"focus_end:{session_id}")
    builder.button(text="🏠 القائمة الرئيسية", callback_data="nav:home")
    builder.adjust(1)
    return builder.as_markup()
