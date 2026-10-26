import json
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import BufferedInputFile, CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.app.bot.keyboards.inline import footer_keyboard, main_menu_keyboard, privacy_home_keyboard
from src.app.bot.ui.templates import HIGH_RISK_CONFIRM_TEMPLATE
from src.app.modules.accounts.models import ConsentDocument, User, UserConsent
from src.app.modules.orders.models import Order

router = Router(name="privacy")

RETENTION_POLICY_TEXT = """📜 <b>سياسة الاحتفاظ بالبيانات والخصوصية:</b>

• <b>بيانات الحساب:</b> نحتفظ فقط بمعرّف تيليجرام والاسم الظاهر والمرحلة الدراسية لتشغيل الخدمة.
• <b>الملفات المرفوعة:</b> تُستخدم لمعالجة طلبك فقط، وتُحذف تلقائياً من خوادمنا بعد 30 يوماً من إتمام التسليم.
• <b>السجلات المالية:</b> نحتفظ ببيانات الفواتير غير الحساسة بالقدر الذي يتطلبه القانون والتدقيق المحاسبي.
• <b>حق الحذف:</b> يمكنك طلب حذف حسابك في أي وقت مع فترة تهدئة 7 أيام للتراجع."""


@router.message(Command("privacy"))
@router.callback_query(F.data.in_(["home:privacy", "priv:home"]))
async def show_privacy_home(event: Message | CallbackQuery):
    text = (
        "🛡️ <b>مركز الخصوصية وإدارة بيانات الحساب</b>\n\n"
        "نحن نلتزم بجمع الحد الأدنى من البيانات، وتمكينك من التحكم الكامل في معلوماتك وحقوقك الرقمية.\n"
        "اختر الإجراء المطلوب أدناه:"
    )
    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, reply_markup=privacy_home_keyboard(), parse_mode="HTML")
        await event.answer()
    else:
        await event.answer(text, reply_markup=privacy_home_keyboard(), parse_mode="HTML")


@router.callback_query(F.data == "priv:retention")
async def cb_privacy_retention(callback: CallbackQuery):
    await callback.message.edit_text(RETENTION_POLICY_TEXT, reply_markup=footer_keyboard("home:privacy"), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "priv:consents")
async def cb_user_consents(callback: CallbackQuery, current_user: User, session: AsyncSession):
    stmt = (
        select(UserConsent)
        .where(UserConsent.user_id == current_user.user_id)
        .order_by(UserConsent.decided_at.desc())
    )
    res = await session.execute(stmt)
    consents = res.scalars().all()

    if not consents:
        text = "📋 <b>الموافقات المسجلة:</b>\n\nلا توجد موافقات إضافية مسجلة لحسابك."
    else:
        text = "📋 <b>الموافقات المسجلة بحسابك:</b>\n\n"
        for c in consents:
            text += f"• موافقة #{str(c.id)[:8].upper()} — الحالة: <b>{c.decision}</b> ({c.decided_at.strftime('%Y-%m-%d')})\n"

    await callback.message.edit_text(text, reply_markup=footer_keyboard("home:privacy"), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "priv:export")
async def cb_export_data(callback: CallbackQuery, current_user: User, session: AsyncSession):
    # Prepare export JSON package
    orders_res = await session.execute(select(Order).where(Order.user_id == current_user.user_id))
    orders = orders_res.scalars().all()

    export_payload = {
        "user_id": str(current_user.user_id),
        "display_name": current_user.display_name,
        "preferred_language": current_user.preferred_language,
        "time_zone": current_user.time_zone,
        "created_at": current_user.created_at.isoformat() if current_user.created_at else None,
        "total_orders_count": len(orders),
        "orders_summary": [
            {
                "order_id": str(o.id),
                "status": o.status,
                "amount": o.total_minor,
                "currency": o.currency_code,
                "created_at": o.created_at.isoformat() if o.created_at else None,
            }
            for o in orders
        ],
    }

    json_bytes = json.dumps(export_payload, ensure_ascii=False, indent=2).encode("utf-8")
    doc_file = BufferedInputFile(json_bytes, filename=f"academic_user_data_{str(current_user.user_id)[:8]}.json")

    await callback.message.answer_document(
        doc_file,
        caption="📦 <b>نسخة بيانات حسابك الرسمية (JSON)</b>\nتم تجهيز وتصدير بياناتك وفق مبادئ الخصوصية وحق الوصول.",
        parse_mode="HTML",
    )
    await callback.answer("تم تصدير البيانات بنجاح.")


@router.callback_query(F.data == "priv:delete_start")
async def cb_delete_start(callback: CallbackQuery, current_user: User):
    # Strict §6.7 High-Risk Confirmation (NO EMOJIS)
    confirm_text = (
        "تأكيد نهائي: طلب حذف الحساب والبيانات\n\n"
        "سيتم جدولة حذف بياناتك بعد فترة تهدئة مدتها 7 أيام.\n"
        "ما يلزمه القانون والأنظمة من سجلات مالية ومحاسبية يبقى مع إخفاء هويتك تماماً.\n\n"
        "هذا الإجراء قابل للتراجع خلال فترة التهدئة (7 أيام)."
    )
    builder = InlineKeyboardBuilder()
    builder.button(text="نعم، جدول حذف الحساب", callback_data="priv:delete_confirm")
    builder.button(text="تراجع", callback_data="home:privacy")
    builder.adjust(2)

    await callback.message.edit_text(confirm_text, reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data == "priv:delete_confirm")
async def cb_delete_confirm(callback: CallbackQuery, current_user: User, session: AsyncSession):
    current_user.account_status = "pending_deletion"
    await session.commit()

    await callback.message.edit_text(
        "تم تسجيل طلب جدولة حذف الحساب بنجاح مع فترة تهدئة 7 أيام.\n"
        "يمكنك إلغاء هذا الطلب في أي وقت بالتواصل مع الدعم الفني.",
        reply_markup=main_menu_keyboard(),
    )
    await callback.answer()
