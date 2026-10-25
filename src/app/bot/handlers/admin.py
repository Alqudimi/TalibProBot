from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from src.app.config.settings import settings
from src.app.infrastructure.database.session import check_db_health
from src.app.modules.accounts.models import User
from src.app.modules.orders.models import Order
from src.app.modules.payments.models import PaymentTransaction

router = Router(name="admin")


@router.message(Command("admin"))
async def cmd_admin_dashboard(message: Message, session: AsyncSession):
    user_id = message.from_user.id
    admin_ids = settings.ADMIN_TELEGRAM_IDS
    if isinstance(admin_ids, list) and user_id not in admin_ids:
        await message.answer("⛔ عذراً، لا تملك صلاحية الوصول إلى هذه اللوحة.")
        return

    # 1. Total users
    res_users = await session.execute(select(func.count(User.user_id)))
    total_users = res_users.scalar() or 0

    # 2. Total orders and volume
    res_orders = await session.execute(select(func.count(Order.id)))
    total_orders = res_orders.scalar() or 0

    res_revenue = await session.execute(
        select(func.coalesce(func.sum(PaymentTransaction.amount_minor), 0)).where(
            PaymentTransaction.status == "succeeded"
        )
    )
    total_revenue_minor = res_revenue.scalar() or 0

    # 3. Outbox status
    res_outbox = await session.execute(
        text(
            """
            SELECT status, count(*)
            FROM student_platform.transactional_outbox
            GROUP BY status;
            """
        )
    )
    outbox_stats = {row[0]: row[1] for row in res_outbox.fetchall()}

    # 4. DB Health
    db_ok = await check_db_health()

    text_msg = (
        "🛠️ <b>لوحة التحكم والتشغيل الإدارية</b>\n\n"
        f"• حالة قاعدة البيانات: {'🟢 متصلة ومستقرة' if db_ok else '🔴 غير متصلة'}\n"
        f"• محرك الكاش (Redis): {'🟢 مفعّل' if settings.REDIS_ENABLED else '⚪ معطّل (ذاكرة محلية)'}\n"
        f"• عدد الطلاب المسجلين: <b>{total_users}</b> طالب\n"
        f"• إجمالي الطلبات: <b>{total_orders}</b> طلب\n"
        f"• إجمالي المدفوعات الناجحة: <b>{total_revenue_minor} XTR</b>\n\n"
        "📊 <b>طابور المهام الخلفية (Outbox Queue):</b>\n"
    )
    for st, count in outbox_stats.items():
        text_msg += f"• {st}: <b>{count}</b> مهمة\n"

    await message.answer(text_msg, parse_mode="HTML")
