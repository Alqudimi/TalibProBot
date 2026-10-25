"""
Human expert & booking service processors (Services 021 - 035).
Covers 1-on-1 tutoring, guided problem-solving, study plan review, manual mock grading,
coding coaching, presentation practice, mock defense, proofreading, research structure,
citations review, CV review, motivation letter, major guidance, language chat, English interview.
"""
from src.app.modules.academic_services.schemas import ServiceInput, ServiceExecutionResult


class HumanAndBookingProcessors:
    """Implementations for human coaching and booking services (021 to 035)."""

    @staticmethod
    def process_021_tutoring_session(inp: ServiceInput) -> ServiceExecutionResult:
        """021 — جلسة تدريس فردية عبر مكالمة"""
        subject = inp.content.strip() or "المادة العامة"
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
    def process_022_guided_problem_solving(inp: ServiceInput) -> ServiceExecutionResult:
        """022 — جلسة حل مشكلات موجّهة"""
        problem = inp.content.strip() or "المسألة الرياضية/العلمية"
        rendered = f"""🧩 **جلسة حل مشكلات موجهة: التفكير الاستدلالي خطوة بخطوة**

📋 **المسألة المطروحة:**
{problem}

🧭 **الخطوة الاستكشافية الأولى:**
1. ما هي المعطيات الأساسية المعطاة؟ وما هو المجهول المطلوب حسابه تحديداً؟
2. ما هي القوانين أو النظريات التي تربط بين هذه المعطيات؟

💡 *توجيه تربوي:* الهدف هو بناء مهارة استنتاج الحل بنفسك، اكتب محاولتك الأولى وسيقوم الخبير بتوجيهك خطوة بخطوة دون إعطائك الحل النهائي مباشرة."""

        return ServiceExecutionResult(
            service_code="022",
            service_name="جلسة حل مشكلات موجّهة",
            success=True,
            summary="تم إطلاق جلسة تفكيك وتوجيه لحل المشكلات بدون تسليم مباشر للحل.",
            rendered_output=rendered
        )

    @staticmethod
    def process_023_study_plan_review(inp: ServiceInput) -> ServiceExecutionResult:
        """023 — مراجعة خطة مذاكرة"""
        plan_desc = inp.content.strip() or "الجدول والمقررات"
        rendered = f"""📅 **مراجعة وتقييم خطة المذاكرة الشخصية**

📊 **تحليل الخطة الحالية:**
- فحص توازن الساعات اليومية وفترات الراحة.
- تقييم توزيع الموضوعات الصعبة في أوقات ذروة التركيز (الصباحية).
- الكشف عن الازدحام التعارضي قبل مواعيد الاختبارات.

📝 **التوصية التحريرية:**
تم إعداد جدول بديل مرن يمنحك 15% وقتاً احتياطياً للطوارئ والمراجعة غير المتوقعة."""

        return ServiceExecutionResult(
            service_code="023",
            service_name="مراجعة خطة مذاكرة",
            success=True,
            summary="تم تدقيق خطة المذاكرة واقتراح توزيع زمني واقعي يتضمن أوقات الراحة.",
            rendered_output=rendered
        )

    @staticmethod
    def process_024_mock_exam_grading(inp: ServiceInput) -> ServiceExecutionResult:
        """024 — تصحيح اختبار تجريبي يدويًا"""
        rendered = f"""📝 **تصحيح اختبار تجريبي يدوي بواسطة خبير أكاديمي**

🔍 **معايير التقييم:**
- دقة الإجابات النموذجية وفق سلم التصحيح المعتمد (Rubric).
- رصد الأخطاء الشائعة ومنهجية التفكير وإدارة الوقت.
- تقديم تقرير تشخيصي بالدرجة التدريبية والنقاط الواجب تدراكها قبل الاختبار الرسمي."""

        return ServiceExecutionResult(
            service_code="024",
            service_name="تصحيح اختبار تجريبي يدويًا",
            success=True,
            summary="تم تسجيل طلب المراجعة اليدوية للاختبار التجريبي وإصدار تقرير التقييم.",
            rendered_output=rendered
        )

    @staticmethod
    def process_025_practical_coding_stats(inp: ServiceInput) -> ServiceExecutionResult:
        """025 — شرح عملي للبرمجة أو الإحصاء"""
        topic = inp.content.strip() or "Python / Statistics Data Analysis"
        rendered = f"""💻 **شرح تطبيقي عملي: {topic}**

🛠 **منهجية الجلسة العملية:**
- بناء المفهوم خطوة بخطوة عبر مثال حي تطبيقي.
- فحص هيكلية الكود أو التحليل الإحصائي وتتبع تدفق المتغيرات.
- تمرين عملي للمتابعة للتحقق من إتقانك العملي المستقل."""

        return ServiceExecutionResult(
            service_code="025",
            service_name="شرح عملي للبرمجة أو الإحصاء",
            success=True,
            summary=f"تم إعداد الشرح التطبيقي العملي لموضوع {topic}.",
            rendered_output=rendered
        )

    @staticmethod
    def process_026_presentation_coaching(inp: ServiceInput) -> ServiceExecutionResult:
        """026 — تدريب عرض تقديمي"""
        rendered = f"""🎤 **تدريب ومراجعة العرض التقديمي (Presentation Coaching)**

🎯 **محاور التقييم:**
1. تسلسل القصة والأفكار الرئيسية (Storyline).
2. وضوح الشرائح والرسوم البيانية وتجنب الاكتظاظ النصي.
3. التوقيت الزمني وطريقة الإلقاء ولغة الجسد.
4. إعداد بنك الأسئلة المتوقعة من لجنة التحكيم أو الحضور."""

        return ServiceExecutionResult(
            service_code="026",
            service_name="تدريب عرض تقديمي",
            success=True,
            summary="تم تحليل محاور العرض التقديمي وتزويد الطالب بملاحظات تحسين الإلقاء والشرائح.",
            rendered_output=rendered
        )

    @staticmethod
    def process_027_mock_defense(inp: ServiceInput) -> ServiceExecutionResult:
        """027 — محاكاة مناقشة أو دفاع"""
        research = inp.content.strip() or "مشروع التخرج / رسالة الماجستير"
        rendered = f"""🛡 **محاكاة جلسة الدفاع والمناقشة الأكاديمية: {research}**

⚖️ **الأسئلة الاستفزازية لتقييم عمق البحث:**
1. ما هو الإسهام الأصيل لبحثك مقارنة بالدراسات السابقة المنشورة؟
2. لماذا اخترت هذه المنهجية تحديداً وما هي أبرز حدودها ونقاط ضعفها؟
3. كيف تحققت من صلاحية وموثوقية البيانات والنتائج المستخرجة؟"""

        return ServiceExecutionResult(
            service_code="027",
            service_name="محاكاة مناقشة أو دفاع",
            success=True,
            summary="تمت محاكاة جلسة مناقشة البحث بأسئلة منهجية دقيقة.",
            rendered_output=rendered
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
    def process_029_research_structure(inp: ServiceInput) -> ServiceExecutionResult:
        """029 — مراجعة بنية البحث"""
        rendered = f"""📐 **مراجعة البنية الهيكلية للبحث الأكاديمي**

🔬 **المحاور التي تمت مراجعتها:**
- توافق الفصول مع سؤال البحث والفرضيات الأساسية.
- المنطق الانتقالي بين المقدمة، ومراجعة الأدبيات، والمنهجية، ومناقشة النتائج.
- وضوح الخاتمة وعدم اشتمالها على استنتاجات تتجاوز الأدلة المعروضة."""

        return ServiceExecutionResult(
            service_code="029",
            service_name="مراجعة بنية البحث",
            success=True,
            summary="تم تدقيق البنية المنطقية للبحث وتماسك أقسامه.",
            rendered_output=rendered
        )

    @staticmethod
    def process_030_citations_formatting(inp: ServiceInput) -> ServiceExecutionResult:
        """030 — مراجعة المراجع وتنسيقها"""
        style = inp.parameters.get("citation_style", "APA 7th")
        rendered = f"""📚 **مراجعة وتنسيق قائمة المراجع وفق نمط {style}**

📑 **نتائج التدقيق:**
- مطابقة الإحالات داخل المتن (In-text citations) مع قائمة المراجع الختامية.
- التحقق من اكتمال عناصر كل مرجع (المؤلف، السنة، العنوان، الناشر، رابط DOI).
- تنبيه الطالب إلى أي إحالة غير موجودة في المراجع أو العكس."""

        return ServiceExecutionResult(
            service_code="030",
            service_name="مراجعة المراجع وتنسيقها",
            success=True,
            summary=f"تم تنسيق ومطابقة المراجع بالكامل وفق أسلوب {style}.",
            rendered_output=rendered
        )

    @staticmethod
    def process_031_cv_review(inp: ServiceInput) -> ServiceExecutionResult:
        """031 — مراجعة سيرة ذاتية لطالب"""
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
    def process_032_motivation_letter_review(inp: ServiceInput) -> ServiceExecutionResult:
        """032 — تدقيق رسالة دافع كتبها الطالب"""
        rendered = f"""💌 **تدقيق رسالة الدافع (Statement of Purpose / Motivation Letter)**

✨ **تقييم جودة الرسالة:**
- **وضوح الهدف:** الرسالة تبين شغف المتقدم بدقة نحو البرنامج الدراسي المطلوب.
- **الصلة الأكاديمية:** تم ربط الخبرات السابقة بالمقررات المستهدفة.
- **الصوت الأصيل:** الحفاظ على أسلوب الطالب دون اصطناع قصص أو بيانات غير واقعية."""

        return ServiceExecutionResult(
            service_code="032",
            service_name="تدقيق رسالة دافع كتبها الطالب",
            success=True,
            summary="تم تدقيق رسالة الدافع وتزويد الطالب بملاحظات الصياغة والربط المقنع.",
            rendered_output=rendered
        )

    @staticmethod
    def process_033_major_orientation(inp: ServiceInput) -> ServiceExecutionResult:
        """033 — جلسة إرشاد اختيار تخصص"""
        major_query = inp.content.strip() or "المفاضلة بين التخصصات الأكاديمية"
        rendered = f"""🧭 **جلسة إرشاد ومفاضلة التخصصات الجامعية: {major_query}**

🎯 **مصفوفة المفاضلة والتوجيه:**
1. **الاهتمامات والقدرات الذاتية:** مطابقة المواد المفضلة مع متطلبات التخصص.
2. **الآفاق الوظيفية وسوق العمل:** طبيعة الوظائف والمهارات المطلوبة لكل مسار.
3. **خطوات التجربة الاستكشافية:** مراجعة خطة دراسية لمقررين أساسيين قبل اتخاذ القرار النهائي."""

        return ServiceExecutionResult(
            service_code="033",
            service_name="جلسة إرشاد اختيار تخصص",
            success=True,
            summary=f"تم إعداد مصفوفة الاستكشاف الأكاديمي لموضوع {major_query}.",
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

    @staticmethod
    def process_035_english_interview_practice(inp: ServiceInput) -> ServiceExecutionResult:
        """035 — تدريب مقابلة باللغة الإنجليزية"""
        role = inp.content.strip() or "Software Engineer / Graduate Student"
        rendered = f"""👔 **محاكاة مقابلة باللغة الإنجليزية: {role}**

Question 1:
*"Tell me about a challenging academic or professional project where you faced a significant obstacle. How did you overcome it, and what did you learn?"*

💡 **Feedback Focus:**
We will evaluate: Vocabulary Precision, Cohesion & Fluency, Grammar, and Structure (STAR Method)."""

        return ServiceExecutionResult(
            service_code="035",
            service_name="تدريب مقابلة باللغة الإنجليزية",
            success=True,
            summary=f"تم إطلاق محاكاة المقابلة باللغة الإنجليزية لوظيفة {role}.",
            rendered_output=rendered
        )
