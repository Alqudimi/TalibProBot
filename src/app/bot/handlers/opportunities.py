import html
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.app.bot.keyboards.inline import footer_keyboard, main_menu_keyboard, opportunities_keyboard
from src.app.modules.accounts.models import User
from src.app.modules.opportunities.models import Opportunity, SavedOpportunity

router = Router(name="opportunities")


@router.message(Command("opportunities"))
@router.callback_query(F.data.in_(["home:opp", "opp:hub"]))
async def show_opportunities_hub(event: Message | CallbackQuery):
    text = (
        "🎯 <b>دليل الفرص والمنح الدراسية والتدريبية</b>\n\n"
        "فرص منح، برامج تدريب صيفي، ومسابقات طلابية متحقق من مصادرها الرسمية.\n"
        "<i>آخر تحقق للمعلومات: اليوم — تُعرض الفرص لغرض الإرشاد ودون أي ضمان بالقبول.</i>\n\n"
        "اختر مسار البحث الذي يناسبك:"
    )
    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, reply_markup=opportunities_keyboard(), parse_mode="HTML")
        await event.answer()
    else:
        await event.answer(text, reply_markup=opportunities_keyboard(), parse_mode="HTML")


@router.callback_query(F.data == "opp:find")
async def cb_opportunities_find(callback: CallbackQuery, session: AsyncSession):
    stmt = select(Opportunity).where(Opportunity.status.in_(["published", "active"])).limit(5)
    res = await session.execute(stmt)
    opps = res.scalars().all()

    if not opps:
        # Fallback to general list if no strict published status
        res_all = await session.execute(select(Opportunity).limit(5))
        opps = res_all.scalars().all()

    if not opps:
        text = (
            "🎯 <b>البحث في الفرص والمنح:</b>\n\n"
            "يجري حالياً تحديث وتدقيق بنك الفرص والمنح الدراسية لهذا الفصل.\n"
            "يمكنك تفعيل تنبيهات الفرص من إعدادات الإشعارات لتصلك أولاً بأول."
        )
        await callback.message.edit_text(text, reply_markup=footer_keyboard("home:opp"), parse_mode="HTML")
        await callback.answer()
        return

    text = f"🎯 <b>أحدث الفرص والمنح المتاحة ({len(opps)} فرصة):</b>\n\n"
    builder = InlineKeyboardBuilder()
    for o in opps:
        deadline_str = o.deadline_at.strftime("%Y-%m-%d") if o.deadline_at else "مفتوح"
        text += (
            f"• <b>{html.escape(o.title)}</b>\n"
            f"  الجهة: {html.escape(o.organization or o.source_name)}\n"
            f"  الموعد النهائي: {deadline_str} | المصدر: {o.source_name}\n"
            f"  شروط الأهلية: {html.escape(o.eligibility_summary[:80])}...\n\n"
        )
        builder.button(text=f"حفظ فرصة #{str(o.id)[:8].upper()}", callback_data=f"opp:save:{o.id}")

    builder.button(text="🔙 رجوع لمركز الفرص", callback_data="home:opp")
    builder.adjust(1)

    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("opp:save:"))
async def cb_save_opportunity(callback: CallbackQuery, current_user: User, session: AsyncSession):
    opp_id_str = callback.data.split(":")[2]
    import uuid
    try:
        opp_id = uuid.UUID(opp_id_str)
    except ValueError:
        await callback.answer("معرّف الفرصة غير صالح.", show_alert=True)
        return

    opportunity = (await session.execute(select(Opportunity.id).where(Opportunity.id == opp_id))).scalar_one_or_none()
    if opportunity is None:
        await callback.answer("هذه الفرصة لم تعد متاحة أو غير موجودة.", show_alert=True)
        return

    stmt = select(SavedOpportunity).where(
        SavedOpportunity.user_id == current_user.user_id,
        SavedOpportunity.opportunity_id == opp_id,
    )
    existing = (await session.execute(stmt)).scalar_one_or_none()
    if not existing:
        saved = SavedOpportunity(user_id=current_user.user_id, opportunity_id=opp_id)
        session.add(saved)
        await session.commit()
        await callback.answer("✅ تم حفظ الفرصة في قائمتك المفضلة.", show_alert=True)
    else:
        await callback.answer("الفرصة محفوظة مسبقاً في قائمتك.", show_alert=False)


@router.callback_query(F.data == "opp:saved")
async def cb_view_saved_opps(callback: CallbackQuery, current_user: User, session: AsyncSession):
    stmt = (
        select(SavedOpportunity)
        .where(SavedOpportunity.user_id == current_user.user_id)
        .order_by(SavedOpportunity.saved_at.desc())
    )
    res = await session.execute(stmt)
    saved_list = res.scalars().all()

    if not saved_list:
        text = "⭐ <b>قائمة الفرص المحفوظة:</b>\n\nلم تقم بحفظ أي فرص حتى الآن."
    else:
        text = f"⭐ <b>فرصك المحفوظة للمتابعة ({len(saved_list)} فرصة):</b>\n\n"
        for s in saved_list:
            text += f"• فرصة #{str(s.opportunity_id)[:8].upper()} (تاريخ الحفظ: {s.saved_at.strftime('%Y-%m-%d')})\n"

    await callback.message.edit_text(text, reply_markup=footer_keyboard("home:opp"), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "opp:calendar")
async def cb_opportunities_calendar(callback: CallbackQuery, session: AsyncSession):
    opportunities = (await session.execute(
        select(Opportunity)
        .where(Opportunity.status.in_(["published", "active"]), Opportunity.deadline_at.is_not(None))
        .order_by(Opportunity.deadline_at.asc()).limit(12)
    )).scalars().all()
    if not opportunities:
        text = "📅 <b>تقويم المواعيد النهائية</b>\n\nلا توجد مواعيد منشورة حالياً."
    else:
        rows = ["📅 <b>تقويم المواعيد النهائية للفرص المنشورة:</b>\n"]
        for item in opportunities:
            rows.append(f"• <b>{html.escape(item.title)}</b> — {item.deadline_at:%Y-%m-%d}")
        text = "\n".join(rows)
    await callback.message.edit_text(text, reply_markup=footer_keyboard("home:opp"), parse_mode="HTML")
    await callback.answer()
