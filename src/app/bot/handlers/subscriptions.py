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
from src.app.bot.ui.templates import HIGH_RISK_CONFIRM_TEMPLATE
from src.app.modules.accounts.models import User
from src.app.modules.entitlements.models import EntitlementGrant
from src.app.modules.subscriptions.models import Subscription

router = Router(name="subscriptions")


@router.message(Command("subscriptions"))
@router.callback_query(F.data == "home:subs")
async def show_user_subscriptions(event: Message | CallbackQuery, current_user: User, session: AsyncSession):
    now = datetime.now(timezone.utc)
    stmt = (
        select(Subscription)
        .where(
            Subscription.user_id == current_user.user_id,
            Subscription.status == "active",
        )
        .order_by(Subscription.created_at.desc())
    )
    res = await session.execute(stmt)
    subs = res.scalars().all()

    builder = InlineKeyboardBuilder()

    if not subs:
        text = (
            "🔁 <b>اشتراكاتك التعليمية</b>\n\n"
            "لا توجد لديك اشتراكات مفعّلة حالياً.\n"
            "الاشتراكات تمنحك وصولاً متجدداً لبنوك الأسئلة، المراجعات الأسبوعية، ونوادي المذاكرة."
        )
        builder.button(text="🔁 تصفح باقات الاشتراكات", callback_data="cat:subscriptions")
        builder.button(text="🏠 الرئيسية", callback_data="home:menu")
        builder.adjust(1)
    else:
        text = f"🔁 <b>اشتراكاتك المفعّلة ({len(subs)} اشتراك):</b>\n\n"
        for s in subs:
            ref = str(s.id)[:8].upper()
            end_date = s.current_period_end.strftime("%Y-%m-%d") if s.current_period_end else "مفتوح"
            days_left = (s.current_period_end - now).days if s.current_period_end else 30
            text += (
                f"• <b>اشتراك #{ref}</b>\n"
                f"  صالح حتى: {end_date} (متبقٍ {max(0, days_left)} يوماً)\n"
                f"  حالة التجديد: يدوي\n\n"
            )
            builder.button(text=f"إلغاء اشتراك #{ref}", callback_data=f"sub:cancel:{s.id}")

        builder.button(text="📊 عرض تفاصيل وحصص الاستحقاق", callback_data="ent:status")
        builder.button(text="🏠 الرئيسية", callback_data="home:menu")
        builder.adjust(1)

    markup = builder.as_markup()
    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
        await event.answer()
    else:
        await event.answer(text, reply_markup=markup, parse_mode="HTML")


@router.callback_query(F.data == "ent:status")
async def cb_entitlement_status(callback: CallbackQuery, current_user: User, session: AsyncSession):
    now = datetime.now(timezone.utc)
    stmt = (
        select(EntitlementGrant)
        .where(
            EntitlementGrant.user_id == current_user.user_id,
            EntitlementGrant.status == "active",
        )
        .order_by(EntitlementGrant.starts_at.desc())
    )
    res = await session.execute(stmt)
    grants = res.scalars().all()

    if not grants:
        text = (
            "📊 <b>سجل الاستحقاقات والحصص</b>\n\n"
            "ليس لديك حصص أو استحقاقات مفعلة في الوقت الحالي. عند الاشتراك في أي باقة يتم تفعيل الاستحقاقات تلقائياً."
        )
    else:
        text = "📊 <b>استحقاقاتك المفعلة من قاعدة البيانات:</b>\n\n"
        for g in grants:
            limit_str = f"{g.limit_amount} استخدام" if g.limit_amount else "وصول غير محدود"
            text += f"• <b>حق #{str(g.id)[:8].upper()}</b>\n"
            text += f"  الحد الأقصى: {limit_str}\n"
            text += f"  تاريخ البدء: {g.starts_at.strftime('%Y-%m-%d')}\n\n"

    await callback.message.edit_text(text, reply_markup=footer_keyboard("home:subs"), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("sub:cancel:"))
async def cb_sub_cancel_prompt(callback: CallbackQuery, session: AsyncSession):
    sub_id = uuid.UUID(callback.data.split(":")[2])
    stmt = select(Subscription).where(Subscription.id == sub_id)
    sub = (await session.execute(stmt)).scalar_one_or_none()
    if not sub:
        await callback.answer()
        return

    # High-Risk Confirm Dialog §6.7 (NO EMOJIS)
    end_date_text = sub.current_period_end.strftime("%Y-%m-%d") if sub.current_period_end else "نهاية الدورة"
    confirm_text = (
        f"تأكيد نهائي: إلغاء الاشتراك #{str(sub.id)[:8].upper()}\n\n"
        f"يستمر وصولك إلى المزايا حتى {end_date_text} ثم يتوقف تلقائيًا.\n"
        "المبالغ المدفوعة لا تُسترد، ولن يتم إرسال أي تذكير بالتجديد.\n\n"
        "هذا الإجراء قابل للتراجع قبل انتهاء الفترة."
    )

    builder = InlineKeyboardBuilder()
    builder.button(text="نعم، ألغِ الاشتراك", callback_data=f"sub:confirm_cancel:{sub.id}")
    builder.button(text="تراجع", callback_data="home:subs")
    builder.adjust(2)

    await callback.message.edit_text(confirm_text, reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("sub:confirm_cancel:"))
async def cb_sub_cancel_execute(callback: CallbackQuery, session: AsyncSession):
    sub_id = uuid.UUID(callback.data.split(":")[2])
    stmt = select(Subscription).where(Subscription.id == sub_id)
    sub = (await session.execute(stmt)).scalar_one_or_none()
    if sub:
        sub.status = "cancelled"
        sub.cancelled_at = datetime.now(timezone.utc)
        await session.commit()

    await callback.message.edit_text(
        f"تم إلغاء الاشتراك #{str(sub_id)[:8].upper()} بنجاح.\n"
        "لن يتم تجديد الاشتراك وسيتوقف الوصول بنهاية الفترة الحالية.",
        reply_markup=main_menu_keyboard(),
    )
    await callback.answer()
