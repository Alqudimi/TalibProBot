import html
import uuid
from datetime import datetime, timezone
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.app.bot.keyboards.inline import footer_keyboard, main_menu_keyboard
from src.app.bot.ui.templates import ERROR_MESSAGES
from src.app.modules.accounts.models import User
from src.app.modules.bookings.models import Booking, BookingParticipant

router = Router(name="bookings")


@router.message(Command("bookings"))
@router.message(F.text == "مواعيدي")
@router.callback_query(F.data == "home:bookings")
async def show_user_bookings(event: Message | CallbackQuery, current_user: User, session: AsyncSession):
    now = datetime.now(timezone.utc)
    stmt = (
        select(Booking)
        .join(BookingParticipant, Booking.id == BookingParticipant.booking_id)
        .where(
            BookingParticipant.user_id == current_user.user_id,
            BookingParticipant.participant_status != "cancelled",
        )
        .order_by(Booking.starts_at.asc())
    )
    res = await session.execute(stmt)
    bookings = res.scalars().all()

    builder = InlineKeyboardBuilder()

    if not bookings:
        text = (
            "📅 <b>مواعيدك وجلساتك الدراسية</b>\n\n"
            "لا توجد لديك جلسات أو مواعيد محجوزة حالياً.\n"
            "يمكنك حجز جلسات تدريس فردية أو مراجعة بحثية مع المعلمين والخبراء عبر قسم الدروس الخصوصية."
        )
        builder.button(text="👨‍🏫 تصفح جلسات التدريس والخبراء", callback_data="cat:tutoring")
        builder.button(text="🏠 الرئيسية", callback_data="home:menu")
        builder.adjust(1)
    else:
        text = f"📅 <b>جلساتك ومواعيدك ({len(bookings)} جلسة):</b>\n\n"
        for b in bookings:
            ref = str(b.id)[:8].upper()
            status_ar = "مؤكد" if b.status == "confirmed" else "قيد التأكيد"
            start_str = b.starts_at.strftime("%Y-%m-%d %H:%M")
            text += (
                f"• <b>{html.escape(b.session_title)}</b> (#{ref})\n"
                f"  الموعد: {start_str} (بتوقيت {current_user.time_zone})\n"
                f"  الحالة: {status_ar}\n\n"
            )
            builder.button(text=f"إلغاء موعد #{ref}", callback_data=f"book:cancel:{b.id}")

        builder.button(text="➕ حجز جلسة جديدة", callback_data="cat:tutoring")
        builder.button(text="🏠 الرئيسية", callback_data="home:menu")
        builder.adjust(1)

    markup = builder.as_markup()
    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
        await event.answer()
    else:
        await event.answer(text, reply_markup=markup, parse_mode="HTML")


@router.callback_query(F.data.startswith("book:cancel:"))
async def cb_booking_cancel_prompt(callback: CallbackQuery, current_user: User, session: AsyncSession):
    try:
        booking_id = uuid.UUID(callback.data.split(":")[2])
    except (ValueError, IndexError):
        await callback.answer("معرّف الحجز غير صالح.", show_alert=True)
        return
    stmt = (
        select(Booking)
        .join(BookingParticipant, Booking.id == BookingParticipant.booking_id)
        .where(
            Booking.id == booking_id,
            BookingParticipant.user_id == current_user.user_id,
            BookingParticipant.participant_status != "cancelled",
        )
    )
    b = (await session.execute(stmt)).scalar_one_or_none()
    if not b:
        await callback.answer(ERROR_MESSAGES["E-02"], show_alert=True)
        return

    confirm_text = (
        f"تأكيد نهائي: إلغاء الجلسة '{b.session_title}'\n\n"
        f"الموعد المحجوز: {b.starts_at.strftime('%Y-%m-%d %H:%M')}.\n"
        "سيتم تحرير الفتحة للمدرس وإشعار الأطراف ذات الصلة.\n"
        "الإلغاء قبل 12 ساعة مجاني وفق سياسة المنصة."
    )
    builder = InlineKeyboardBuilder()
    builder.button(text="نعم، ألغِ الموعد", callback_data=f"book:confirm_cancel:{b.id}")
    builder.button(text="تراجع", callback_data="home:bookings")
    builder.adjust(2)

    await callback.message.edit_text(confirm_text, reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("book:confirm_cancel:"))
async def cb_booking_cancel_execute(callback: CallbackQuery, current_user: User, session: AsyncSession):
    try:
        booking_id = uuid.UUID(callback.data.split(":")[2])
    except (ValueError, IndexError):
        await callback.answer("معرّف الحجز غير صالح.", show_alert=True)
        return
    stmt = select(BookingParticipant).where(
        BookingParticipant.booking_id == booking_id,
        BookingParticipant.user_id == current_user.user_id,
    )
    bp = (await session.execute(stmt)).scalar_one_or_none()
    if not bp or bp.participant_status == "cancelled":
        await callback.answer("الحجز غير موجود أو لا تملك صلاحية إلغاء هذا الحجز.", show_alert=True)
        return
    bp.participant_status = "cancelled"
    bp.cancelled_at = datetime.now(timezone.utc)
    await session.commit()

    await callback.message.edit_text(
        "تم إلغاء الموعد بنجاح وتحرير الفتحة الزمنية.",
        reply_markup=main_menu_keyboard(),
    )
    await callback.answer()
