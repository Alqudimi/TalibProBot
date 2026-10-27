import html
import uuid
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.app.bot.keyboards.inline import footer_keyboard, main_menu_keyboard, support_home_keyboard
from src.app.bot.keyboards.reply import cancel_reply_keyboard, persistent_reply_keyboard
from src.app.bot.states.fsm import TicketFSM
from src.app.modules.accounts.models import User
from src.app.modules.support.models import SupportTicket, SupportTicketMessage

router = Router(name="support")

FAQ_TEXT = """❓ <b>الأسئلة الشائعة حول المنصة:</b>

• <b>كيف يتم الدفع؟</b>
يتم الدفع رسمياً عبر نجوم تيليجرام (Telegram Stars) داخل المحادثة بأمان تام.

• <b>هل تقدمون حلولاً مباشرة للاختبارات؟</b>
لا؛ نحن نلتزم بمبادئ النزاهة الأكاديمية ونساعدك على فهم وتفكيك المفاهيم واكتساب المهارة بنفسك.

• <b>كم يستغرق تسليم الخدمات؟</b>
الخدمات الآلية الفورية تُسلّم خلال دقائق، والخدمات الخبيرة والمراجعات خلال 24-48 ساعة كما هو موضح في بطاقة كل خدمة.

• <b>كيف أتواصل مع المشرف أو المعلم؟</b>
يتم التواصل من خلال تذاكر الدعم أو روابط الجلسات المعتمدة المحجوزة."""


@router.message(Command("support"))
@router.message(F.text.in_(["🎧 الدعم", "دعم"]))
@router.callback_query(F.data == "home:support")
async def show_support_home(event: Message | CallbackQuery, state: FSMContext):
    await state.clear()
    text = (
        "🎧 <b>مركز الدعم الفني والأكاديمي</b>\n\n"
        "فريقنا متاح لمساعدتك في أي استفسار أو مشكلة متعلقة بالطلبات والمدفوعات والخدمات.\n"
        "اختر موضوع التذكرة للبدء:"
    )
    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, reply_markup=support_home_keyboard(), parse_mode="HTML")
        await event.answer()
    else:
        await event.answer(text, reply_markup=support_home_keyboard(), parse_mode="HTML")


@router.callback_query(F.data == "sup:faq")
async def cb_support_faq(callback: CallbackQuery):
    await callback.message.edit_text(FAQ_TEXT, reply_markup=footer_keyboard("home:support"), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "sup:mine")
async def cb_user_tickets(callback: CallbackQuery, current_user: User, session: AsyncSession):
    stmt = (
        select(SupportTicket)
        .where(SupportTicket.user_id == current_user.user_id)
        .order_by(SupportTicket.created_at.desc())
        .limit(8)
    )
    res = await session.execute(stmt)
    tickets = res.scalars().all()

    if not tickets:
        text = "📂 <b>سجل تذاكر الدعم الخاصة بك:</b>\n\nلا توجد تذاكر دعم سابقة لديك."
    else:
        text = f"📂 <b>تذاكر الدعم الخاصة بك ({len(tickets)} تذكرة):</b>\n\n"
        for t in tickets:
            ref = str(t.id)[:8].upper()
            status_ar = "مفتوحة" if t.status == "open" else "مغلقة"
            text += f"• <b>تذكرة #{ref}</b> — {t.subject[:30]}\n"
            text += f"  الحالة: {status_ar} | الفئة: {t.category}\n"
            text += f"  التاريخ: {t.created_at.strftime('%Y-%m-%d %H:%M')}\n\n"

    await callback.message.edit_text(text, reply_markup=footer_keyboard("home:support"), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("sup:topic:"))
async def cb_pick_ticket_topic(callback: CallbackQuery, state: FSMContext):
    topic = callback.data.split(":")[2]
    topic_labels = {
        "order": "مشكلة في تنفيذ أو تسليم طلب",
        "finance": "استفسار عن دفع أو طلب استرداد",
        "service": "سؤال أو توضيح حول خدمة معينة",
        "other": "استفسار أو اقتراح عام",
    }
    topic_categories = {
        "order": "delivery",
        "finance": "billing",
        "service": "service_quality",
        "other": "other",
    }
    label = topic_labels.get(topic, "استفسار")
    category = topic_categories.get(topic, "other")

    await state.set_state(TicketFSM.wait_text)
    await state.update_data(topic=category, topic_label=label)

    await callback.message.answer(
        f"🎧 <b>فتح تذكرة جديدة: {label}</b>\n\n"
        "أرسل الآن وصفاً تفصيلياً ومختصراً لمشكلتك (حتى 1000 حرف).\n"
        "سيقوم فريق الدعم بمراجعتها والرد عليك خلال 24 ساعة:",
        reply_markup=cancel_reply_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(TicketFSM.wait_text)
async def handle_ticket_text_submission(message: Message, state: FSMContext, current_user: User, session: AsyncSession):
    body = (message.text or "").strip()
    if not body:
        await message.answer("يرجى كتابة نص التذكرة بالتفصيل.")
        return

    data = await state.get_data()
    topic = data.get("topic", "technical")
    label = data.get("topic_label", "طلب دعم")
    await state.clear()

    ticket = SupportTicket(
        user_id=current_user.user_id,
        category=topic,
        subject=label,
        status="open",
        priority=3,
    )
    session.add(ticket)
    await session.flush()

    ticket_msg = SupportTicketMessage(
        ticket_id=ticket.id,
        sender_user_id=current_user.user_id,
        sender_kind="customer",
        body=body[:1000],
    )
    session.add(ticket_msg)
    await session.commit()

    ref = str(ticket.id)[:8].upper()
    await message.answer(
        f"✅ <b>تم إنشاء تذكرة الدعم بنجاح!</b>\n\n"
        f"رقم المرجع: <code>TK-{ref}</code>\n"
        f"الموضوع: {label}\n"
        f"الزمن المتوقع للرد: <b>خلال 24 ساعة</b>\n\n"
        "ستصلك إشعارات وتحديثات الرد هنا فور قيام فريق الدعم بمراجعة رسالتك.",
        reply_markup=persistent_reply_keyboard(),
        parse_mode="HTML",
    )
