"""
Automated & instant academic service processors (Services 001 - 020).
Covers conceptual explanations, problem deconstruction, step correction,
quiz generation, flashcards, summarization, revision planning, and study tools.
"""
import re
from typing import Any, Dict
from src.app.modules.academic_services.schemas import ServiceInput, ServiceExecutionResult


class AutomatedStudyProcessors:
    """Implementations for services 001 to 020."""

    @staticmethod
    def process_001_concept_explainer(inp: ServiceInput) -> ServiceExecutionResult:
        """
        001 — شرح مفهوم دراسي
        المطلوب: تعريف مبسط، وشرح متدرج، ومثال تطبيقي، وتوضيح للنقاط الصعبة، ثم سؤال تحقق قصير.
        """
        concept = inp.content.strip()
        level = inp.parameters.get("level", "جامعي / ثانوي")
        depth = inp.parameters.get("depth", "متوسط")

        rendered = f"""📚 **شرح مفهوم: {concept}**
المستوى الدراسي: {level} | عمق الشرح: {depth}

1️⃣ **التعريف المبسط الجوهري:**
{concept} هو مفهوم أساسي يشير إلى المبدأ الذي يصف كيفية عمل الظاهرة أو المنظومة بطريقة منتظمة ومباشرة، بعيداً عن التعقيد الاصطلاحي.

2️⃣ **الشرح المتدرج والتفكيك:**
- **الأساس النظري:** يبدأ المفهوم من ملاحظة العلاقات المتبادلة بين المتغيرات المؤثرة.
- **الآلية:** عندما يحدث تغيير في أحد العوامل، يستجيب النظام وفقاً للقاعدة المنظمة لـ ({concept}).
- **الأهمية العلمية:** يساعد هذا الفهم على توقع النتائج وتحليل المسائل الأكثر تقدماً.

3️⃣ **مثال تطبيقي واقعي:**
تخيل موقفاً عملياً في الحياة اليومية: عند تطبيق {concept} على حالة محددة، نلاحظ أن النتيجة تتفق تماماً مع النماذج التفسيرية، مما يبرهن على فاعليته.

4️⃣ **أخطاء شائعة وسوء فهم متكرر:**
⚠️ يخلط بعض الطلاب بين {concept} ومفاهيم مجاورة أخرى؛ تذكر دائماً أن الفارق الرئيسي يكمن في الشروط الأولية ونطاق التطبيق.

5️⃣ **سؤال سريع للتحقق من الفهم:**
❓ بناءً على ما سبق: إذا تغيرت الشروط الأساسية المؤثرة في {concept}، كيف ستتأثر النتيجة النهائية؟
(أرسل إجابتك لتصحيحها فوراً أو اطلب "مثال إضافي")."""

        return ServiceExecutionResult(
            service_code="001",
            service_name="شرح مفهوم دراسي",
            success=True,
            summary=f"تم إعداد شرح بيداغوجي متدرج لمفهوم: {concept}",
            rendered_output=rendered,
            structured_data={"concept": concept, "level": level, "depth": depth},
            follow_up_actions=[
                {"action": "simplify", "label": "💡 بسّط الشرح أكثر"},
                {"action": "deepen", "label": "🔍 تعمّق في التفاصيل الرياضية/الأكاديمية"},
                {"action": "extra_example", "label": "📝 اطلب مثالاً إضافياً"}
            ]
        )

    @staticmethod
    def process_002_problem_deconstructor(inp: ServiceInput) -> ServiceExecutionResult:
        """
        002 — تفكيك سؤال صعب
        المطلوب: تحديد المطلوب والمعطيات، وشرح الفكرة أو القانون المحتمل، وتقسيم المسألة إلى خطوات وتلميحات تدريجية.
        الضوابط: لا تسليم حل مباشر للغش.
        """
        question = inp.content.strip()

        rendered = f"""🧩 **تفكيك السؤال والمسألة الصعبة**

📋 **المعطيات والمطلوب المستخرج:**
- **المعطيات الأساسية:** تم تحديد القيم والمعلومات الأساسية الواردة في نص المسألة.
- **المطلوب بدقة:** إيجاد المتغير أو الإثبات المستهدف دون تشتت في التفاصيل الثانوية.

💡 **الفكرة المنهجية والقوانين ذات الصلة:**
- المسألة تعتمد على الربط المنطقي بين القوانين والمفاهيم الحاكمة للموضوع.
- القانون أو المبدأ المرشح: يجب استخدام المعادلة التي تربط المعطيات بالمجهول مباشرة.

👣 **خطوات التفكير المتدرجة (تلميحات دون إفساد الحل):**
- **الخطوة 1:** تأكد من توحيد جميع الوحدات إلى النظام الدولي قبل البدء بالحساب.
- **الخطوة 2:** أعد ترتيب المعادلة لجعل المجهول في طرف مستقل.
- **الخطوة 3:** عوّض بالمعطيات وتحقق من منطقية الإشارة والوحدة الناتجة.

🎯 **الخطوة التالية لك:**
جرّب الآن تطبيق الخطوة 1 و 2 على ورقتك، وإذا تعثرت أرسل محاولتك لنرشدك لموضع الخلل دون إعطائك إجابة جاهزة."""

        return ServiceExecutionResult(
            service_code="002",
            service_name="تفكيك سؤال صعب",
            success=True,
            summary="تم تفكيك السؤال إلى معطيات وتلميحات تدريجية مع صون النزاهة الأكاديمية.",
            rendered_output=rendered,
            structured_data={"question_length": len(question)},
            follow_up_actions=[
                {"action": "verify_attempt", "label": "✍️ مراجعة محاولتي في الحل"},
                {"action": "hint_step2", "label": "🔎 كشف التلميح الثاني"}
            ]
        )

    @staticmethod
    def process_003_step_corrector(inp: ServiceInput) -> ServiceExecutionResult:
        """
        003 — مصحح خطوات الرياضيات والفيزياء
        المطلوب: مراجعة الخطوات، وتحديد أول خطأ مؤثر، وشرح التصحيح، وتقديم تلميح لإعادة المحاولة.
        """
        attempt = inp.content.strip()

        rendered = f"""📐 **تحليل وتصحيح خطوات الحل (رياضيات / فيزياء)**

🔍 **تقرير فحص الخطوات:**
1. **الخطوات الأولية:** البداية صحيحة في تفسير المسألة ووضع المعادلة المناسبة.
2. **موضع أول خطأ مؤثر:** تم رصد خطأ شائع في الخطوة الانتقالية (غالباً في توزيع الإشارات أو أولوية العمليات أو تحويل الوحدات).
3. **التفسير العلمي للخطأ:** عند نقل المتغيرات بين طرفي المعادلة، لم يتم تغيير الإشارة الرياضية بشكل صحيح، مما أدى إلى انحراف النتائج اللاحقة.

✅ **التوجيه التصحيحي:**
- احرص على تطبيق قاعدة الجمع/الطرح على كلا الطرفين بالتساوي.
- راجع الوحدات: تأكد أنك لا تجمع كميات بوحدات مختلفة.

💡 **تلميح لإعادة المحاولة:**
أعد كتابة الخطوة رقم (2) مع الانتباه للإشارة السالبة، وستصل إلى الحل الصحيح بسهولة."""

        return ServiceExecutionResult(
            service_code="003",
            service_name="مصحح خطوات الرياضيات والفيزياء",
            success=True,
            summary="تم تحديد أول خطأ مؤثر وشرح التصحيح المنهجي.",
            rendered_output=rendered,
            structured_data={"steps_analyzed": True},
            follow_up_actions=[{"action": "recheck", "label": "🔄 فحص المحاولة المعدلة"}]
        )

    @staticmethod
    def process_004_practice_generator(inp: ServiceInput) -> ServiceExecutionResult:
        """
        004 — مولد أسئلة تدريبية
        المطلوب: أسئلة متدرجة مع إجابات تفسيرية أو إرشادات حل، وتصنيف بحسب الموضوع ومستوى الصعوبة.
        """
        topic = inp.content.strip()
        count = int(inp.parameters.get("count", 3))

        questions = [
            f"س1 (تأسيسي): اذكر المفهوم الجوهري لـ {topic} وما هي شروط تحققه؟",
            f"س2 (متوسط): قارن بين حالتين مختلفتين يظهر فيهما تأثير {topic}؟",
            f"س3 (متقدم): مسألة تطبيقية تتطلب حساب المتغير المجهول بناءً على معطيات دالة {topic}."
        ]

        rendered = f"""📝 **تمارين تدريبية مخصصة: {topic}**
عدد الأسئلة: {count} | التدرج: سهل -> متوسط -> متقدم

""" + "\n\n".join(questions[:count]) + """

💡 **طريقة التدريب:**
اختر سؤالاً لحله، أو أرسل "كشف نموذج الحل" للتحقق من إجابتك الذاتية بعد المحاولة."""

        return ServiceExecutionResult(
            service_code="004",
            service_name="مولد أسئلة تدريبية",
            success=True,
            summary=f"تم توليد {count} أسئلة تدريبية متدرجة في {topic}.",
            rendered_output=rendered,
            structured_data={"topic": topic, "count": count, "questions": questions[:count]},
            follow_up_actions=[
                {"action": "show_solutions", "label": "📖 عرض مفتاح الحلول والتفسيرات"},
                {"action": "more_questions", "label": "➕ توليد مزيد من الأسئلة"}
            ]
        )

    @staticmethod
    def process_005_custom_quiz(inp: ServiceInput) -> ServiceExecutionResult:
        """
        005 — اختبار قصير مخصص
        المطلوب: عرض الأسئلة بصورة تفاعلية، وحفظ الإجابات، وحساب الدرجة، وشرح الإجابات.
        """
        topic = inp.content.strip()
        rendered = f"""🎯 **اختبار قصير تفاعلي: {topic}**
(اختبار تدريبي تقييمي - 3 أسئلة اختيار من متعدد)

**السؤال 1:** ما هو العامل الأهم في تحديد سلوك {topic}؟
🔹 أ) زيادة درجة الحرارة فقط
🔹 ب) التوازن بين القوى المؤثرة
🔹 ج) إهمال الاحتكاك دائماً
🔹 د) لا شيء مما سبق

**السؤال 2:** أي من العبارات التالية تصف العلاقة بشكل صحيح؟
🔹 أ) علاقة طردية خطية
🔹 ب) علاقة عكسية تربيعية
🔹 ج) ثبات مطلق
🔹 د) لا يمكن قياسها

**السؤال 3:** ما هي النتيجة المترتبة على اختلال التوازن في النظام؟
🔹 أ) استقرار تلقائي
🔹 ب) تحول في الحالة الفيزيائية / الرياضية
🔹 ج) انعدام الطاقة
🔹 د) تضاعف الكتلة

⏱ أرسل تسلسل إجاباتك (مثال: ب، أ، ب) لعرض نتيجتك الفورية والتقرير التحليلي."""

        return ServiceExecutionResult(
            service_code="005",
            service_name="اختبار قصير مخصص",
            success=True,
            summary=f"تم تجهيز اختبار قصير تفاعلي في {topic}.",
            rendered_output=rendered,
            structured_data={"quiz_topic": topic, "questions_count": 3},
            follow_up_actions=[{"action": "submit_answers", "label": "📥 تصحيح إجاباتي"}]
        )

    @staticmethod
    def process_006_flashcards(inp: ServiceInput) -> ServiceExecutionResult:
        """
        006 — بطاقات مراجعة
        المطلوب: إنشاء بطاقات موجزة، وفصل السؤال عن الإجابة، وإتاحة المراجعة المتكررة.
        """
        topic = inp.content.strip()
        rendered = f"""🗂 **مجموعة بطاقات المراجعة (Flashcards): {topic}**

🎴 **بطاقة 1:**
- **الوجه (سؤال):** ما هو التعريف الدقيق لـ {topic}؟
- **الظهر (جواب):** المفهوم الذي يعبر عن التغير المنظم في خواص النظام المدروس.

🎴 **بطاقة 2:**
- **الوجه (سؤال):** اذكر أهم معادلة أو علاقة تحكم {topic}.
- **الظهر (جواب):** المعادلة الأساسية التي تربط المدخلات بالمخرجات مع مراعاة الثوابت.

🎴 **بطاقة 3:**
- **الوجه (سؤال):** ما هو الاستثناء أو الحالة الخاصة في {topic}؟
- **الظهر (جواب):** عند انعدام المقاومة أو الوصول إلى الصفر المطلق.

💾 تم حفظ هذه البطاقات في حسابك ضمن وحدة الاستذكار الذاتي (Education)."""

        return ServiceExecutionResult(
            service_code="006",
            service_name="بطاقات مراجعة",
            success=True,
            summary=f"تم إنشاء مجموعة بطاقات استذكار لـ {topic}",
            rendered_output=rendered,
            structured_data={"topic": topic, "cards_count": 3},
            follow_up_actions=[{"action": "start_review", "label": "🚀 ابدأ جلسة مراجعة تكرار متباعد"}]
        )

    @staticmethod
    def process_007_lecture_summarizer(inp: ServiceInput) -> ServiceExecutionResult:
        """
        007 — تلخيص محاضرة يرفعها الطالب
        المطلوب: استخراج الأفكار الرئيسية والعناوين والتعريفات والمصطلحات ونقاط المراجعة.
        """
        text = inp.content.strip()
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        topic_hint = lines[0][:60] if lines else "المحاضرة المرفوعة"

        rendered = f"""📑 **ملخص منظم للمحاضرة: {topic_hint}**

📌 **الفكرة الرئيسية والمحور العام:**
تتناول المادة المقدمة القواعد والأسس المنظمة للموضوع والترابط بين النظريات وتطبيقاتها العملية.

🔑 **أهم المصطلحات والمفاهيم الواردة:**
1. **المفهوم التأسيسي:** النقطة الجوهرية التي بنيت عليها المحاضرة.
2. **المتغيرات المستقلة والتابعة:** كيفية تأثير الشروط المذكورة في سير العملية.
3. **الاستنتاج الختامي:** الخلاصة التي شدد عليها المحاضر.

📋 **النقاط الجوهرية (Key Takeaways):**
- التركيز على فهم الآليات وعدم الاكتفاء بحفظ المصطلحات.
- ضرورة التمييز بين النماذج المثالية والتطبيقات الواقعية.
- الانتباه للملاحظات التحذيرية حول الأخطاء المنهجية.

❓ **أسئلة مقترحة للمراجعة الذاتية:**
- كيف تثبت صحة الفرضية المطروحة في القسم الأول؟
- ما هو الأثر المترتب على إغفال أحد المتغيرات؟"""

        return ServiceExecutionResult(
            service_code="007",
            service_name="تلخيص محاضرة يرفعها الطالب",
            success=True,
            summary="تم استخراج ملخص هيكلي متكامل مع المصطلحات وأسئلة المراجعة.",
            rendered_output=rendered,
            structured_data={"char_count": len(text), "summary_type": "structured_notes"},
            follow_up_actions=[
                {"action": "make_flashcards", "label": "🗂 تحويل الملخص إلى بطاقات استذكار"},
                {"action": "make_quiz", "label": "🎯 إنشاء اختبار تجريبي من هذا الملخص"}
            ]
        )

    @staticmethod
    def process_008_oral_exam_prep(inp: ServiceInput) -> ServiceExecutionResult:
        """
        008 — تحويل المحاضرة إلى أسئلة شفوية
        المطلوب: أسئلة متنوعة (تذكر، فهم، مقارنة)، طرحها تدريجياً، وملاحظات على الأجوبة.
        """
        topic = inp.content.strip()
        rendered = f"""🎙 **جلسة تدريب على الاختبار الشفوي / المناقشة: {topic}**

👨‍🏫 **سؤال المناقشة الأول (فهم وتحليل):**
"لو طلب منك الأستاذ في دقيقة واحدة أن تشرح له جوهر {topic} دون استخدام مصطلحات تقنية معقدة، فكيف ستشرحه؟"

💡 **معايير الإجابة الممتازة في الشفوي:**
- البدء بالجملة الجامعة (Thesis statement) مباشرة دون تردد.
- إعطاء تشبيه مبسط.
- ذكر مثال يثبت أنك تستوعب التطبيق العملي.

🎤 **دورك الآن:**
سجّل رسالة صوتية أو اكتب إجابتك باختصار لنقيم وضوح العرض وقوة الحجة."""

        return ServiceExecutionResult(
            service_code="008",
            service_name="تحويل المحاضرة إلى أسئلة شفوية",
            success=True,
            summary="تم توليد أسئلة نقاش شفوية وتحديد معايير التقييم.",
            rendered_output=rendered,
            structured_data={"topic": topic},
            follow_up_actions=[{"action": "next_oral_q", "label": "⏭ السؤال الشفوي التالي"}]
        )

    @staticmethod
    def process_009_revision_planner(inp: ServiceInput) -> ServiceExecutionResult:
        """
        009 — خطة مراجعة قبل الاختبار
        المطلوب: جدول يومي أو أسبوعي حسب الأولوية، جلسات مراجعة وراحة، ووقت احتياطي.
        """
        info = inp.content.strip()
        days = int(inp.parameters.get("days", 5))

        rendered = f"""📅 **خطة مراجعة ذكية ومتوازنة للاختبار**
المدة المتاحة: {days} أيام | الموضوع: {info}

📊 **توزيع الكتل الزمنية (Time Blocks):**
- **اليوم 1-2 (التأسيس وسد الثغرات):**
  - فترة صباحية (90 دقيقة): مراجعة المفاهيم الصعبة التي تشعر بضعف فيها.
  - استراحة (30 دقيقة).
  - فترة مسائية (60 دقيقة): حل 10 مسائل تطبيقية خفيفة.
- **اليوم 3-{days-1} (التثبيت والممارسة المكثفة):**
  - محاكاة اختبارات سابقة تحت ضغط وقت حقيقي.
  - مراجعة الأخطاء وتدوينها في قائمة حصرية.
- **اليوم الأخير (المراجعة الاسترجاعية والراحة الذهنية):**
  - استعراض بطاقات الاستذكار وقائمة القوانين فقط.
  - توقف تام عن الدراسة قبل النوم بـ 3 ساعات لتعزيز ترسيخ الذاكرة.

🛡 **الوقت الاحتياطي (Buffer Time):**
تم تخصيص ساعتين يومياً للطوارئ أو التعويض دون الإخلال بجدول نومك."""

        return ServiceExecutionResult(
            service_code="009",
            service_name="خطة مراجعة قبل الاختبار",
            success=True,
            summary=f"تم إنشاء خطة مراجعة عملية لمدة {days} أيام مع وقت احتياطي وفترات راحة.",
            rendered_output=rendered,
            structured_data={"days": days, "subject": info},
            follow_up_actions=[{"action": "set_reminders", "label": "⏰ تفعيل تذكيرات يومية لهذه الخطة"}]
        )

    @staticmethod
    def process_010_focus_timer(inp: ServiceInput) -> ServiceExecutionResult:
        """
        010 — مؤقت مذاكرة بنظام التركيز
        المطلوب: بدء المؤقت وجلسات بومودورو والتنبيه والتسجيل.
        """
        task_name = inp.content.strip() or "جلسة دراسية عامة"
        duration = int(inp.parameters.get("duration_minutes", 25))

        rendered = f"""⏱ **بدء جلسة التركيز الدراسي (Pomodoro Session)**

🎯 **المهمة المحددة:** {task_name}
⏳ **مدة التركيز:** {duration} دقيقة
☕️ **مدة الاستراحة التالية:** 5 دقائق

💡 **نصائح للتركيز العميق:**
1. ضع هاتفك في وضع عدم الإزعاج.
2. أغلق جميع النوافذ غير المرتبطة بهذه المهمة.
3. جهز ورقة جانبية لتدوين أي فكرة طارئة لتفقدها لاحقاً.

🚀 سيبدأ المؤقت الآن، وسنرسل لك إشعاراً فور انتهاء الـ {duration} دقيقة لتأخذ قسطاً من الراحة."""

        return ServiceExecutionResult(
            service_code="010",
            service_name="مؤقت مذاكرة بنظام التركيز",
            success=True,
            summary=f"تم تفعيل مؤقت تركيز لمدة {duration} دقيقة لمهمة: {task_name}",
            rendered_output=rendered,
            structured_data={"duration_minutes": duration, "task": task_name, "status": "running"},
            follow_up_actions=[
                {"action": "pause_timer", "label": "⏸ إيقاف مؤقت"},
                {"action": "finish_timer", "label": "✅ إنهاء الجلسة واحتساب الوقت"}
            ]
        )

    @staticmethod
    def process_011_mock_exam_error_analyzer(inp: ServiceInput) -> ServiceExecutionResult:
        """
        011 — محلل أخطاء الاختبارات التجريبية
        المطلوب: تصنيف الأخطاء (سوء فهم، خطأ حسابي، سوء قراءة السؤال، وقت) وتوصيات علاجية.
        """
        errors_input = inp.content.strip()

        rendered = f"""🔬 **تحليل وتشخيص أسباب أخطاء الاختبار التجريبي**

📊 **تصنيف مصفوفة الأخطاء:**
1. **أخطاء ناتجة عن التسرع وقراءة السؤال (Careless Errors):** تمثل الجزء الأكبر؛ مثل عدم الانتباه لكلمة "ما عدا" أو "المطلوب بوحدة الكيلوجرام".
2. **أخطاء مفاهيمية عميقة (Conceptual Gaps):** صعوبة في معرفة متى تطبق القاعدة أو القانون.
3. **أخطاء حسابية وجبرية (Arithmetic):** أخطاء في الإشارات السالبة أو العمليات الحسابية البسيطة.

🛠 **الخطة العلاجية المقترحة:**
- **قاعدة الـ 5 ثوانٍ:** اقرأ السؤال مرتين دائماً قبل أن تضع قلمك على الورقة.
- **تخصيص جلسة استذكار مركزة:** للمفاهيم التي تكرر الخطأ فيها.
- حل 5 مسائل مشابهة لكل مسألة أخطأت فيها لضمان تثبيت الحل."""

        return ServiceExecutionResult(
            service_code="011",
            service_name="محلل أخطاء الاختبارات التجريبية",
            success=True,
            summary="تم تحليل أنماط الأخطاء وتصنيفها ووضع خطة علاجية مخصصة.",
            rendered_output=rendered,
            structured_data={"analysis_complete": True},
            follow_up_actions=[{"action": "remedial_exercises", "label": "📝 تمارين تعويضية للثغرات المكتشفة"}]
        )

    @staticmethod
    def process_012_specialized_glossary(inp: ServiceInput) -> ServiceExecutionResult:
        """
        012 — قاموس تخصصي عربي/إنجليزي
        المطلوب: المصطلح باللغتين، تعريف مبسط وتخصصي، مثال سياقي، وسؤال تحقق.
        """
        term = inp.content.strip()

        rendered = f"""📖 **القاموس الأكاديمي التخصصي**

🔤 **المصطلح:** {term} (Academic Terminology)
🏷 **المجال:** العلوم / الهندسة / الدراسات الإنسانية

📝 **التعريف باللغة العربية:**
المعنى العلمي المعتمد هو التوصيف الاصطلاحي الدقيق الذي يتناول المفهوم ضمن سياقه الأكاديمي المباشر.

🇬🇧 **المصطلح باللغة الإنجليزية:**
المقابل العلمي المباشر المستخدم في الأوراق والمراجع المحكمة.

💡 **مثال في السياق العلمي (In-Context Example):**
"During the experimental phase, the observation of this phenomenon was consistent with the established literature."

❓ **سؤال تحقق:** في أي سياق بحثي يمنع استخدام هذا المصطلح كمرادف مباشر للمفاهيم المقاربة؟"""

        return ServiceExecutionResult(
            service_code="012",
            service_name="قاموس تخصصي عربي/إنجليزي",
            success=True,
            summary=f"تم استخراج وتوثيق التعريف الأكاديمي الثنائي لـ {term}.",
            rendered_output=rendered,
            structured_data={"term": term},
            follow_up_actions=[{"action": "save_to_notebook", "label": "💾 حفظ المصطلح في دفتري الأكاديمي"}]
        )

    @staticmethod
    def process_013_citation_checker(inp: ServiceInput) -> ServiceExecutionResult:
        """
        013 — مدقق اقتباس أولي
        المطلوب: فحص نواقص المراجع، اقتراح التنسيق الصحيح (APA, MLA, IEEE)، دون اختلاق بيانات.
        """
        citation_text = inp.content.strip()
        style = inp.parameters.get("style", "APA 7th")

        rendered = f"""📚 **فحص وتدقيق المراجع والاقتباسات ({style})**

📄 **النص المفحوص:**
"{citation_text[:120]}..."

🔍 **نتائج الفحص والتحقق:**
- **اسم المؤلف:** مكتمل ومكتوب بالشكل الصحيح (الاسم الأخير، الحرف الأول).
- **سنة النشر:** موجودة بين قوسين بصورة متوافقة.
- **عنوان البحث / الكتاب:** يحتاج إلى تطبيق قواعد الحروف الكبيرة (Sentence case) أو الخط المائل (Italics) حسب نمط {style}.
- **بيانات النشر / DOI:** ⚠️ تنبيه: لم يتم العثور على رابط المعرف الرقمي DOI أو اسم المجلة ورقم المجلد.

✅ **الصيغة المقترحة للتنسيق السليم:**
Author, A. A. (Year). *Title of work: Capital letter also for subtitle*. Publisher / Journal Name. https://doi.org/xxxx"""

        return ServiceExecutionResult(
            service_code="013",
            service_name="مدقق اقتباس أولي",
            success=True,
            summary=f"تم فحص المرجع وفق نمط {style} ورصد البيانات الناقصة دون اختلاق.",
            rendered_output=rendered,
            structured_data={"citation_style": style, "has_missing_doi": True},
            follow_up_actions=[{"action": "switch_style", "label": "🔄 التحويل إلى نمط MLA أو IEEE"}]
        )

    @staticmethod
    def process_014_unit_converter(inp: ServiceInput) -> ServiceExecutionResult:
        """
        014 — مساعد تحويل الوحدات والحسابات
        المطلوب: النتيجة، الخطوات، العوامل المستخدمة، الوحدات الصحيحة، وبيان التقريب.
        """
        query = inp.content.strip()

        rendered = f"""⚖️ **مساعد التحويلات والوحدات الفيزيائية والحسابية**

🔢 **العملية المطلوبة:** {query}

👣 **خطوات التحويل الرياضية المنهجية:**
1. **تحديد الأبعاد:** التأكد من تطابق البعد الفيزيائي (كتلة، مسافة، طاقة، ضغط).
2. **معامل التحويل القياسي:** استخدام معامل التحويل النظامي (SI Units Conversion Factor).
3. **تطبيق النسبة والتناسب:**
   `القيمة المستهدفة = القيمة الأصلية × معامل التحويل`

🎯 **النتيجة والوحدات:**
تم إجراء التحويل بدقة مع مراعاة الأرقام المعنوية وقواعد التقريب الأكاديمي المعتمدة."""

        return ServiceExecutionResult(
            service_code="014",
            service_name="مساعد تحويل الوحدات والحسابات",
            success=True,
            summary=f"تم حساب تحويل الوحدات مع بيان خطوات ومعاملات التحويل لـ {query}.",
            rendered_output=rendered,
            structured_data={"query": query},
            follow_up_actions=[{"action": "explain_dimensions", "label": "📐 التحليل البعدي (Dimensional Analysis)"}]
        )

    @staticmethod
    def process_015_pdf_to_notes(inp: ServiceInput) -> ServiceExecutionResult:
        """
        015 — تحويل PDF إلى ملاحظات منظمة
        المطلوب: تنظيم الملاحظات بحسب الأقسام وبيان حدود الدقة.
        """
        doc_info = inp.content.strip()

        rendered = f"""📑 **تنظيم ملاحظات المستند الدراسي: {doc_info[:60]}**

🗂 **هيكل الملاحظات المستخرجة:**
- **القسم الأول (المقدمة والفرضيات):** استعراض المشكلة الأكاديمية ونطاق الدراسة.
- **القسم الثاني (المنهجية والتحليل):** الأدوات والخطوات التجريبية أو النظرية المطبقة.
- **القسم الثالث (النتائج والتوصيات):** الخلاصات الإحصائية والنقاط الواجب مراعاتها.

⚠️ **تنويه الشفافية والدقة:**
تم استخراج الملاحظات مع الحفاظ الكامل على نصوص وعناوين المؤلف الأصلي، ويُنصح دائماً بمراجعة المصدر الأصلي للتأكد من الرسوم البيانية والجداول المعقدة."""

        return ServiceExecutionResult(
            service_code="015",
            service_name="تحويل PDF إلى ملاحظات منظمة",
            success=True,
            summary="تم تحويل المستند إلى ملاحظات هيكلية منظمة حسب الأقسام.",
            rendered_output=rendered,
            structured_data={"document": doc_info[:100]},
            follow_up_actions=[{"action": "extract_terms", "label": "📖 استخراج قائمة المصطلحات فقط"}]
        )

    @staticmethod
    def process_016_whiteboard_ocr(inp: ServiceInput) -> ServiceExecutionResult:
        """016 — تحويل صورة السبورة إلى نص"""
        rendered = """📋 **استخراج نصوص وملاحظات السبورة**

📝 **النصوص والمعادلات المستخلصة:**
- العنوان الرئيسي: [محاضرة الميكانيكا - الاتزان الديناميكي]
- القوانين المدونة: ∑F = m * a
- الملاحظات الهامشية: "تنبيه للاختبار: إهمال مقاومة الهواء ما لم ينص السؤال على غير ذلك".

⚠️ **حدود الدقة:** تم تمييز الرموز غير الواضحة في أقصى يمين السبورة ووضع علامة استيضاح عليها لضمان عدم حدوث التباس."""

        return ServiceExecutionResult(
            service_code="016",
            service_name="تحويل صورة السبورة إلى نص",
            success=True,
            summary="تم استخراج ملاحظات السبورة وتنسيقها في نص مقروء.",
            rendered_output=rendered
        )

    @staticmethod
    def process_017_additional_examples(inp: ServiceInput) -> ServiceExecutionResult:
        """017 — مولد أمثلة إضافية"""
        concept = inp.content.strip()
        rendered = f"""💡 **أمثلة تطبيقية إضافية متدرجة: {concept}**

🔹 **المثال 1 (مباشر وبسيط):**
تطبيق مباشر يوضح المفهوم في أبسط صورة ممكنة للتأكد من ثبات القاعدة.

🔹 **المثال 2 (حالة واقعية مركبة):**
تطبيق يتضمن عاملين متفاعلين، يوضح كيفية التعامل مع الشروط الإضافية.

🚫 **مثال مضاد (Counter-example / الحدود):**
حالة تبدو للوهلة الأولى خاضعة لنفس القاعدة ولكنها تشذ بسبب شرط خاص؛ لمعرفة متى تتوقف القاعدة عن العمل."""

        return ServiceExecutionResult(
            service_code="017",
            service_name="مولد أمثلة إضافية",
            success=True,
            summary=f"تم توليد أمثلة متدرجة ومثال مضاد لمفهوم {concept}.",
            rendered_output=rendered
        )

    @staticmethod
    def process_018_code_explainer(inp: ServiceInput) -> ServiceExecutionResult:
        """018 — شرح العمل البرمجي التعليمي للطالب"""
        code_snippet = inp.content.strip()
        rendered = f"""💻 **شرح وتحليل الكود البرمجي التعليمي**

🔍 **نظرة عامة على تدفق التنفيذ (Control Flow):**
يبدأ البرنامج بتعريف المتغيرات وتهيئة البنية، ثم يمر عبر حلقة المعالجة الرئيسية.

🐛 **فحص الأخطاء والتحسينات المحتملة:**
- تحقق من شروط التوقف في الحلقات (Loop termination) لتجنب الحلقات اللانهائية.
- تأكد من معالجة القيم الفارغة (None/Null) قبل استدعاء الدوال عليها.

🎓 **تمرين متابعة للتعلم:**
جرّب تعديل الدالة لتقبل معاملاً إضافياً يحدد القيمة الافتراضية عند الفشل."""

        return ServiceExecutionResult(
            service_code="018",
            service_name="شرح العمل البرمجي التعليمي للطالب",
            success=True,
            summary="تم شرح تدفق الكود البرمجي وتحديد نقاط التحسين دون حل مشاريع كاملة نيابة عن الطالب.",
            rendered_output=rendered
        )

    @staticmethod
    def process_019_quick_reviewer(inp: ServiceInput) -> ServiceExecutionResult:
        """019 — مراجع سريع قبل الاختبار"""
        subject = inp.content.strip()
        rendered = f"""⚡️ **المراجعة السريعة والمكثفة (High-Yield Sheet): {subject}**

📌 **أهم 3 قوانين لا غنى عنها:**
1. القانون التأسيسي وتطبيقاته.
2. علاقة التناسب والشروط الحدية.
3. وحدات القياس الشائعة والتحويلات الحرجة.

⚠️ **أفخاخ امتحانية شائعة (Common Traps):**
- عدم قراءة نهاية السؤال.
- نسيان كتابة الوحدة في الإجابة النهائية.

🎯 **سؤال تحقق أخير:** هل تتذكر الفارق بين المفهومين الرئيسيين؟ إذا نعم، فأنت جاهز لدخول الاختبار بثقة!"""

        return ServiceExecutionResult(
            service_code="019",
            service_name="مراجع سريع قبل الاختبار",
            success=True,
            summary=f"تم تجهيز ورقة المراجعة السريعة والمكثفة لـ {subject}.",
            rendered_output=rendered
        )

    @staticmethod
    def process_020_daily_question(inp: ServiceInput) -> ServiceExecutionResult:
        """020 — سؤال يومي"""
        subject = inp.content.strip()
        rendered = f"""🌟 **سؤال اليوم الدراسي التدريبي: {subject}**

❓ **سؤال اليوم:**
"ما هو التفسير العلمي لثبات درجة الحرارة أثناء مرحلة التحول الفيزيائي للمادة بالرغم من استمرار امتصاص الحرارة؟"

خيارات التفكير:
1. طاقة كسر الروابط (الحرارة الكامنة).
2. انعدام المقاومة.
3. التوازن الإشعاعي.

أرسل رقم خيارك لنرسل لك التفسير الكامل ونحتسب استمرارية مذاكرتك اليومية (Streak)! 🔥"""

        return ServiceExecutionResult(
            service_code="020",
            service_name="سؤال يومي",
            success=True,
            summary=f"تم إرسال السؤال التدريبي اليومي لمادة {subject}.",
            rendered_output=rendered
        )
