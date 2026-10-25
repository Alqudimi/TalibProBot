from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession
from src.app.bot.keyboards.inline import main_menu_keyboard
from src.app.modules.accounts.models import User
from src.app.modules.education.service import EducationService

router = Router(name="start")

WELCOME_TEXT = """
🎓 <b>أهلاً بك في منصة الخدمات التعليمية والأكاديمية الذكية</b>

نحن نساعدك على:
• 📖 <b>شرح وتفكيك المفاهيم الدراسية الصعبة</b> بخطوات إرشادية واضحة.
• 📊 <b>بناء خطط دراسية مخصصة</b> وجداول مراجعة قبل الاختبارات.
• ⏱️ <b>تنظيم وقت المذاكرة</b> بنظام جلسات التركيز (Pomodoro).
• 🃏 <b>مراجعة وحفظ المعلومات</b> بنظام البطاقات التكرارية (Flashcards).
• 📚 <b>الاستفادة من بنوك الأسئلة</b> والاختبارات التجريبية.

🛡️ <i>تنبيه النزاهة الأكاديمية: نلتزم بمساعدتك على الفهم والتعلم واكتساب المهارة، ولا نقوم بحل الاختبارات الرسمية نيابة عنك.</i>

اختر من القائمة أدناه ما يناسب هدفك الدراسي:
"""

PRIVACY_TEXT = """
🛡️ <b>سياسة الخصوصية والنزاهة الأكاديمية</b>

1. <b>حماية بيانات الطالب:</b>
نحتفظ بالحد الأدنى اللازم من البيانات لإدارة حسابك وتقديم خدماتك. لا نشارك بياناتك مع أطراف ثالثة لأغراض دعائية.

2. <b>أمان الملفات:</b>
الملفات والملاحظات التي ترفعها تُستخدم فقط لتحليل طلبك الحالي واستخراج التلخيصات أو خطط المذاكرة.

3. <b>النزاهة الأكاديمية:</b>
نحن مساعد دراسي يهدف إلى ترسيخ الفهم؛ نعتذر عن أي طلبات تستهدف الغش أو حل الامتحانات المباشرة.

يمكنك طلب تصدير بياناتك أو حذف حسابك في أي وقت بالتواصل مع الإدارة.
"""


@router.message(CommandStart())
async def cmd_start(message: Message, current_user: User, session: AsyncSession):
    stats = await EducationService.get_user_focus_stats(session, current_user.user_id)
    user_greeting = f"مرحباً بك <b>{current_user.display_name or 'صديقنا الطالب'}</b>! 👋\n"
    if stats["total_sessions"] > 0:
        user_greeting += f"⚡ إنجازك حتى الآن: <b>{stats['total_sessions']}</b> جلسة تركيز ({stats['total_minutes']} دقيقة مذاكرة).\n"

    await message.answer(
        user_greeting + WELCOME_TEXT,
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "nav:home")
async def cb_nav_home(callback: CallbackQuery, current_user: User, session: AsyncSession):
    stats = await EducationService.get_user_focus_stats(session, current_user.user_id)
    header = f"مرحباً بك مجدداً <b>{current_user.display_name or ''}</b>\n"
    if stats["total_sessions"] > 0:
        header += f"⏱️ إجمالي المذاكرة: <b>{stats['total_minutes']}</b> دقيقة.\n"
    await callback.message.edit_text(
        header + WELCOME_TEXT,
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "menu:privacy")
async def cb_privacy(callback: CallbackQuery):
    await callback.message.edit_text(
        PRIVACY_TEXT,
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()
