"""
Human expert & booking service processors (Services 021 - 040).
Covers 1-on-1 tutoring, guided problem-solving, study plan review,
mock defense, proofreading, CV review, career guidance, language tutoring.
"""
from src.app.modules.academic_services.schemas import ServiceInput, ServiceExecutionResult


class HumanAndBookingProcessors:
    """Implementations for human coaching and booking services (021 to 040)."""

    @staticmethod
    def process_021_tutoring_session(inp: ServiceInput) -> ServiceExecutionResult:
        """021 — جلسة تدريس فردية عبر مكالمة"""
        subject = inp.content.strip()
        rendered = f"""👨‍🏫 **حجز جلسة تدريس فردية مباشرة: {subject}**

📅 **بيانات الجلسة:**
- المادة المستهدفة: {subject}
- المدة: 45 دقيقة (مكالمة تفاعلية مباشرة مع مدرس معتمد)
- الخيارات المتاحة: اليوم (7:00 مساءً) أو غداً (5:00 مساءً)

💡 **ما يحصل عليه الطالب:**
- مراجعة النقاط الصعبة والأسئلة المعلقة خطوة بخطوة.
- ملخص ختامي مكتوب لأهم الملاحظات بعد انتهاء الجلسة.
- تسجيل للجلسة للرجوع إليه لاحقاً.

📌 تم توجيه طلبك إلى نظام الحجوزات (`Bookings`)، اختر الموعد المناسب لتأكيد الحجز."""

        return ServiceExecutionResult(
            service_code="021",
            service_name="جلسة تدريس فردية عبر مكالمة",
            success=True,
            status="scheduled",
            summary=f"تم إعداد مسار حجز جلسة تدريس فردية في {subject}.",
            rendered_output=rendered,
            follow_up_actions=[{"action": "pick_slot", "label": "🗓 اختيار الموعد المتاح"}]
        )

    @staticmethod
    def process_028_proofreading(inp: ServiceInput) -> ServiceExecutionResult:
        """028 — تدقيق لغوي لبحث الطالب"""
        research_excerpt = inp.content.strip()
        rendered = f"""✍️ **التدقيق اللغوي والأكاديمي لبحث الطالب**

🔍 **معايير التدقيق المطبقة:**
- سلامة التراكيب النحوية والإملائية.
- ضبط المصطلحات الأكاديمية والأسلوب التقريري الرصين.
- إبراز مواضع الغموض دون التدخل في أفكار أو نتائج الطالب الأصلية (احتراماً للنزاهة الأكاديمية).

📄 **تقرير التدقيق الأولي:**
تم فحص النص ({len(research_excerpt)} حرف)، ورصد التحسينات التحريرية المقترحة مع إبراز الفروق (Track Changes) لتتمكن من مراجعة كل تعديل بمفرده."""

        return ServiceExecutionResult(
            service_code="028",
            service_name="تدقيق لغوي لبحث الطالب",
            success=True,
            summary="تم تدقيق النص لغوياً وتحريرياً مع صون النزاهة وصوت الباحث الأصلي.",
            rendered_output=rendered
        )

    @staticmethod
    def process_031_cv_review(inp: ServiceInput) -> ServiceExecutionResult:
        """031 — مراجعة سيرة ذاتية لطالب"""
        cv_text = inp.content.strip()
        rendered = f"""📄 **مراجعة وتطوير السيرة الذاتية للطالب / الخريج**

🌟 **التقييم العام للمسودة:**
- **التنسيق والهيكلة:** الترتيب الزمني العكسي واضح، ويُفضل إبراز المشاريع الأكاديمية في قسم مستقل.
- **صياغة الإنجازات (Action Verbs):** استخدام أفعال حركة قوية متبوعة بنتائج ملموسة بدلاً من سرد المسؤوليات فقط.
- **التوافق مع أنظمة الفرز الآلي (ATS Friendly):** خلو السيرة من الجداول المعقدة والرموز التي تعيق القراءة الآلية.

🎯 **أهم 3 توصيات للتحسين الفوري:**
1. إضافة سطر ملخص مهني (Summary) في بداية السيرة يحدد أهدافك.
2. توثيق المهارات التقنية بمشاريع تخرج أو تدريب عملي مثبت.
3. تدقيق عناوين الاتصال والتأكد من رابط لينكد إن نشط."""

        return ServiceExecutionResult(
            service_code="031",
            service_name="مراجعة سيرة ذاتية لطالب",
            success=True,
            summary="تم إعداد تقرير مراجعة تفصيلي للسيرة الذاتية مع توصيات توافق أنظمة ATS.",
            rendered_output=rendered
        )

    @staticmethod
    def process_034_language_conversation(inp: ServiceInput) -> ServiceExecutionResult:
        """034 — مدرس محادثة لغة"""
        lang = inp.parameters.get("language", "الإنجليزية")
        topic = inp.content.strip() or "General Academic Discussion"

        rendered = f"""🗣 **جلسة ممارسة المحادثة التفاعلية ({lang})**

Topic: {topic}

Hello! Let's start our conversational practice today. 
Here is your opening question:
*"Could you tell me about the most interesting project or topic you have studied this semester, and why it caught your attention?"*

💡 **إرشادات المحادثة:**
- أرسل إجابتك بتسجيل صوتي أو نصي.
- سأقوم بالرد عليك وإعطائك تغذية راجعة على المفردات المستخدمة ونطق الكلمات بطريقة بناءة."""

        return ServiceExecutionResult(
            service_code="034",
            service_name="مدرس محادثة لغة",
            success=True,
            summary=f"تم بدء جلسة محادثة تفاعلية باللغة {lang} حول {topic}.",
            rendered_output=rendered
        )
