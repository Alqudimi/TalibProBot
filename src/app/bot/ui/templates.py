"""UI/UX text templates, error messages, and emoji definitions complying strictly with UI-UX.md."""

from typing import Dict, Any


# 2.4 Approved Category and Feature Emojis (No unauthorized emojis)
CATEGORY_EMOJIS: Dict[str, str] = {
    "instant_auto": "⚡",
    "human_expert": "🧑‍🏫",
    "subscriptions": "🔁",
    "digital_goods": "📦",
    "institutional": "🏛️",
    "ai_skills": "🤖",
    "employment": "💼",
    "scholarships": "🎓",
    "tutoring": "👨‍🏫",
    "wellbeing": "🧘",
    "home": "🏠",
    "catalog": "📚",
    "orders": "🗂️",
    "bookings": "📅",
    "quizzes": "🧪",
    "flashcards": "🃏",
    "plans": "🗓️",
    "timer": "⏱️",
    "daily": "💡",
    "opportunities": "🎯",
    "groups": "👥",
    "support": "🎧",
    "notifications": "🔔",
    "profile": "👤",
    "privacy": "🛡️",
}


# 6.1 Onboarding Welcome
WELCOME_NEW_USER = """أهلاً {first_name} 👋
أنا مساعدك الدراسي داخل تيليجرام: أشرح المفاهيم، أساعدك في المذاكرة، أراجع أعمالك بأسلوب يطوّر مهاراتك، وأقدم لك 153 خدمة دراسية.

قبل البدء نحتاج ثلاث خطوات سريعة:
1. تأكيد الموافقة على الشروط وسياسة الخصوصية.
2. مرحلتك الدراسية (لتخصيص المحتوى).
3. المنطقة الزمنية (لتوقيت التذكيرات).

لنبدأ 👇"""


# 4.1 Main Menu
MAIN_MENU_TEXT = """{first_name}، أهلاً بك في «منصة الأكاديمية» 🏠
مساعدك الدراسي: 153 خدمة — من شرح المفاهيم إلى المنح والمهارات.

ماذا تحتاج اليوم؟"""


# 6.2 Service Card Template
SERVICE_CARD_TEMPLATE = """<b>{service_title}</b> {category_emoji}
{summary_ar}

<b>الشكل:</b> {delivery_shape}
<b>مدة التسليم المعلنة:</b> {sla_text}
<b>السعر:</b> {price_display}
<b>مناسب لـ:</b> {audience_hint}
{integrity_line}"""


# 6.3 Pre-payment Order Review (Financial, NO EMOJIS)
ORDER_REVIEW_TEMPLATE = """مراجعة الطلب
──────────
الخدمة: {service_title}
العرض: {offer_title}
المبلغ: {amount} {currency_symbol_or_stars}
الشروط: {terms_summary}
التسليم خلال {sla_text}."""


# 6.4 Successful Payment Receipt (NO EMOJIS)
PAYMENT_RECEIPT_TEMPLATE = """تم تأكيد الدفع.

رقم الطلب: {order_ref}
الخدمة: {service_title}
المبلغ المدفوع: {amount} ⭐
رقم العملية لدى تيليجرام: {telegram_payment_charge_id}

الخطوة التالية: {next_step_text}

يمكنك متابعة الطلب من: /orders"""


# 6.5 Acknowledgement Card
ACKNOWLEDGEMENT_CARD_TEMPLATE = """استلمنا طلبك وبدأ التجهيز.

مرجع الطلب: {order_ref}
الحالة: {status_ar}
الزمن المتوقع: {sla_text}"""


# 6.6 Delivery Card
DELIVERY_CARD_TEMPLATE = """جاهز — تم تسليم طلبك.

الطلب: {order_ref} — {service_title}
{delivery_body}"""


# 6.7 High-Risk Confirm (NO EMOJIS)
HIGH_RISK_CONFIRM_TEMPLATE = """تأكيد نهائي: {action_label}
{consequence_summary}
هذا الإجراء {reversible_label}: {window}."""


# 6.9 System Mini Responses
SYSTEM_RESPONSES = {
    "active_flow": "لديك عملية جارية: {flow_label}. أكملها أو ألغِها بأمر /cancel.",
    "missing_profile": "تحتاج هذه الخدمة إلى {missing_field}. أضيفيها الآن؟",
    "timeout": "انتهت مهلة الجلسة حفاظًا على بياناتك. لم يُفقد ما كتبته — تجده في طلباتك تحت حالته.",
    "subscription_required": "هذه الميزة ضمن اشتراك {plan_title}.",
    "no_cancellable_flow": "لا توجد عملية جارية للإلغاء.",
}


# 11. Error Matrix (E-01 to E-20, NO EMOJIS)
ERROR_MESSAGES: Dict[str, str] = {
    "E-01": "لم يقبل {field}: {reason_short}. الحد: {limit_text}. جرّب مرة أخرى أو عدل الإدخال.",
    "E-02": "هذه اللوحة قديمة ولم تعد صالحة. افتح الحالة الحالية من طلباتك.",
    "E-03": "هذه الخدمة غير متاحة حاليًا. يمكنك تصفح خدمات مشابهة من التصنيف.",
    "E-04": "تعذر إكمال طلبك الآن بسبب مشكلة تقنية مؤقتة. لم يُهدر حقك — سنعيد المحاولة تلقائيًا، وستصلك النتيجة أو نقبل استردادًا إن فشل نهائيًا.",
    "E-05": "الشراء متوقف مؤقتًا للصيانة ({until}). الطلبات القائمة تُنفذ كالمعتاد.",
    "E-06": "انتهت مهلة الجلسة حفاظًا على سلامة بياناتك. ما كتبته محفوظ في مسودة الطلب.",
    "E-07": "الجزء {i}/{n}",
    "E-08": "انتهى حد {ent_name} المتاح لك ({total}/{unit}). يتجدد مع {renew_text} أو يمكنك الشراء الآن.",
    "E-09": "لا توجد عملية جارية للإلغاء.",
    "E-10": "لم أفهم الأمر. أوامر شائعة: /services, /orders, /support — أو افتح القائمة.",
    "E-11": "تعارض الحجز مع حجز آخر أُكمل قبلك (هذا يحمي الجميع). الفتحات المتاحة الآن أمامك.",
    "E-12": "غير مصرح.",
    "E-13": "بدأ تنفيذ طلبك فلا يُلغى تلقائيًا. الحالات المسموح بها تُدار من الدعم: سنراجع ويُرد إليك خلال {ticket_sla}.",
    "E-14": "هذه اللوحة لا تنتمي لجلستك.",
    "E-15": "أرسلت طلبات متقاربة أكثر من اللازم. انتظر {cooldown} ثم أعد المحاولة — هذا يحمي الخدمة للجميع.",
    "E-16": "الملف غير مقبول: {reason}. الحدود: {limits_text}.",
    "E-17": "لم أستطع قراءة المحتوى بوضوح كافٍ. جرّب صورة أوضح بإضاءة أفضل أو أرسل نصًا.",
    "E-18": "قُدّمت العملية من جهاز آخر/جلسة موازية للتو. لن تكرر أثرها — هذه حالتها الحالية: {status}",
    "E-19": "هذا خارج ما أستطيع مساعدتك فيه بأمان. قائمة مرافق الدعم المتخصصة الموثوقة: {referral_text}. إن كان خطرًا عاجلًا فتواصل مع {emergency_text} فورًا.",
    "E-20": "ميزة {feature} غير متاحة مؤقتًا، وأكملنا ما عداها. سيصل إشعار عودتها.",
}


# 11. Academic Integrity Matrix (AC-01 to AC-05)
ACADEMIC_INTEGRITY_MESSAGES: Dict[str, str] = {
    "AC-01": "لا أقدّم إجابات اختبارات أو واجبات جارية — هذا يخالف النزاهة الأكاديمية ويضر تعلمك. بدائل تساعدك الآن: شرح المفهوم (001)، تفكيك سؤال مشابه (002)، تدريب على موضوع (004).",
    "AC-02": "لا أكتب بحثك عنك، لكن أساعدك فعليًا: مخطط البحث، مراجعة بنية، تدقيق لغوي يحفظ أسلوبك. لنبدأ بأي منها؟",
    "AC-03": "تسليم مشروع جاهز للاعتماد يخالف شروطي. أرشدك بدلًا: شرح البنية، مراجعة كود، وتمارين للنقاط الصعبة — حتى تسلّمه بفهمه.",
    "AC-04": "لا أختلق مصادر أو بيانات. سأتحقق من ما أوردته أنت وأصحح الاستشهادات، وأرشدك لقواعد التوثيق.",
    "AC-05": "لا أقدم هذا النوع من المحتوى. إن كان سياقك تعليميًا مصرحًا، فالمسار الآمن: مختبرات تدريب معتمدة.",
}
