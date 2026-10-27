from aiogram import F, Router
from aiogram.filters import Command
import uuid
from datetime import datetime, time, timedelta, timezone

from aiogram.types import CallbackQuery, Message
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from src.app.bot.keyboards.inline import footer_keyboard, main_menu_keyboard
from src.app.bot.ui.templates import ERROR_MESSAGES
from src.app.modules.access_control.service import AccessControlService
from src.app.modules.accounts.models import User
from src.app.modules.providers.models import ProviderAvailabilityRule, ProviderProfile
from src.app.modules.bookings.models import Booking
from src.app.modules.reviews.models import ProviderReview

router = Router(name="provider")


async def _check_provider_permission(session: AsyncSession, user: User) -> bool:
    perms = await AccessControlService.get_user_permissions(session, user.user_id)
    return "service.provide" in perms or "admin.super" in perms


@router.message(Command("provider"))
@router.callback_query(F.data == "prov:home")
async def show_provider_dashboard(event: Message | CallbackQuery, current_user: User, session: AsyncSession):
    is_prov = await _check_provider_permission(session, current_user)
    if not is_prov:
        msg_text = "⛔ هذا القسم مخصص للمعلمين ومقدمي الخدمات المعتمدين في المنصة."
        if isinstance(event, CallbackQuery):
            await event.answer(msg_text, show_alert=True)
        else:
            await event.answer(msg_text)
        return

    profile = (await session.execute(select(ProviderProfile).where(ProviderProfile.user_id == current_user.user_id))).scalar_one_or_none()
    pending_count = 0
    today_count = 0
    average = 0.0
    if profile:
        pending_count = (await session.execute(
            select(func.count(Booking.id)).where(Booking.provider_id == profile.id, Booking.status == "pending")
        )).scalar() or 0
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)
        today_count = (await session.execute(
            select(func.count(Booking.id)).where(
                Booking.provider_id == profile.id,
                Booking.starts_at >= today_start,
                Booking.starts_at < today_end,
            )
        )).scalar() or 0
        average = float((await session.execute(
            select(func.coalesce(func.avg(ProviderReview.rating), 0)).join(Booking, Booking.id == ProviderReview.booking_id).where(
                Booking.provider_id == profile.id, ProviderReview.moderation_status == "approved"
            )
        )).scalar() or 0)
    text = (
        "🧑‍🏫 <b>لوحة تحكم مقدم الخدمة والمعلم</b>\n\n"
        f"• الطلبات بانتظار المراجعة والقبول: <b>{pending_count}</b> طلبات\n"
        f"• جلسات التدريس المحجوزة لليوم: <b>{today_count}</b> جلسات\n"
        "• الأرباح المعلقة للتسوية: <b>0.00 XTR</b>\n"
        f"• متوسط تقييم الطلاب: <b>{average:.1f} / 5.0</b> ⭐\n\n"
        "الأوامر السريعة المتاحة:\n"
        "• /provider_requests — مراجعة وتأكيد الطلبات الموجهة لك\n"
        "• /provider_hours — ضبط فتحات التوافر الأسبوعية والإجازات"
    )

    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, reply_markup=footer_keyboard("home:menu"), parse_mode="HTML")
        await event.answer()
    else:
        await event.answer(text, reply_markup=footer_keyboard("home:menu"), parse_mode="HTML")


@router.message(Command("provider_requests"))
async def cmd_provider_requests(message: Message, current_user: User, session: AsyncSession):
    is_prov = await _check_provider_permission(session, current_user)
    if not is_prov:
        await message.answer(ERROR_MESSAGES["E-12"])
        return

    await message.answer(
        "📋 <b>الطلبات الموجهة لك للتنفيذ:</b>\n\n"
        "لا توجد طلبات جديدة بانتظار قبولك حالياً.",
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML",
    )


@router.message(Command("provider_hours"))
async def cmd_provider_hours(message: Message, current_user: User, session: AsyncSession):
    is_prov = await _check_provider_permission(session, current_user)
    if not is_prov:
        await message.answer(ERROR_MESSAGES["E-12"])
        return

    profile = (await session.execute(select(ProviderProfile).where(ProviderProfile.user_id == current_user.user_id))).scalar_one_or_none()
    if not profile:
        await message.answer("لا يوجد ملف مقدم خدمة مرتبط بحسابك.")
        return
    parts = (message.text or "").split()
    if len(parts) == 1:
        rules = (
            await session.execute(
                select(ProviderAvailabilityRule)
                .where(ProviderAvailabilityRule.provider_id == profile.id, ProviderAvailabilityRule.is_active.is_(True))
                .order_by(ProviderAvailabilityRule.weekday, ProviderAvailabilityRule.local_start)
            )
        ).scalars().all()
        if not rules:
            body = "لا توجد قواعد توافر مسجلة حالياً."
        else:
            body = "\n".join(f"• اليوم {r.weekday}: {r.local_start:%H:%M}–{r.local_end:%H:%M} ({r.time_zone})" for r in rules)
        await message.answer(
            "⏰ <b>قواعد التوافر الحالية</b>\n\n" + body +
            "\n\nللإضافة: <code>/provider_hours اليوم HH:MM HH:MM</code> حيث اليوم من 0 إلى 6.",
            reply_markup=main_menu_keyboard(), parse_mode="HTML",
        )
        return
    if len(parts) != 4:
        await message.answer("الاستخدام: /provider_hours <0-6> <HH:MM> <HH:MM>")
        return
    try:
        weekday = int(parts[1])
        start = time.fromisoformat(parts[2])
        end = time.fromisoformat(parts[3])
    except (ValueError, TypeError):
        await message.answer("صيغة اليوم أو الوقت غير صحيحة.")
        return
    if weekday not in range(7) or start >= end:
        await message.answer("اليوم يجب أن يكون من 0 إلى 6، ويجب أن يكون وقت النهاية بعد البداية.")
        return
    rule = ProviderAvailabilityRule(
        id=uuid.uuid4(), provider_id=profile.id, weekday=weekday,
        local_start=start, local_end=end, time_zone=profile.default_time_zone, is_active=True,
    )
    session.add(rule)
    await session.commit()
    await message.answer("تم حفظ فترة التوافر بنجاح.", reply_markup=main_menu_keyboard())
