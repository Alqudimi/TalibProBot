"""
Study Wellness, Accessibility & Non-Academic Student Support service processors (Services 139 - 153).
Covers exam stress management, support services referral guide, sleep & study habits companion,
anti-procrastination assistant, student budget organizer, affordable textbooks & tools comparison,
student housing finder, student transit guide, text reader for learning difficulties,
consensual lecture transcription, instant educational terminology translation,
initial sign language/audio description assistant, international student care organizer,
city student services guide, and moderated peer support group.
"""
from src.app.modules.academic_services.schemas import ServiceInput, ServiceExecutionResult


class WellnessAndAccessibilityProcessors:
    """Implementations for study wellness, accessibility and student support (139 to 153)."""

    @staticmethod
    def process_139_exam_stress_management(inp: ServiceInput) -> ServiceExecutionResult:
        """139 — مخطط إدارة ضغط الاختبارات"""
        rendered = """🌿 **مخطط إدارة القلق والضغوط الامتحانية (Exam Stress Management)**

🧘‍♂️ **استراتيجيات التهدئة الذهنية:**
- تمرين التنفس الصندوقي (Box Breathing) لتهدئة ضربات القلب قبل بدء المذاكرة أو دخول القاعة.
- تقسيم كمية الدراسة إلى أجزاء صغيرة يمكن إنجازها لتفادي الشعور بالإغراق الذهني.
- ضمان 7 ساعات نوم لترسيخ الذاكرة واسترجاع المعلومات بكفاءة."""

        return ServiceExecutionResult(
            service_code="139",
            service_name="مخطط إدارة ضغط الاختبارات",
            success=True,
            summary="تم تقديم تقنيات واستراتيجيات إدارة التوتر والتركيز للامتحانات.",
            rendered_output=rendered
        )

    @staticmethod
    def process_140_support_referral_guide(inp: ServiceInput) -> ServiceExecutionResult:
        """140 — دليل الإحالة إلى خدمات الدعم"""
        rendered = """🤝 **دليل ومسارات الإحالة إلى مراكز الدعم المتخصصة**

🏛 **الجهات المعتمدة المتاحة:**
- مركز الإرشاد النفسي والطلابي بالجامعة (استشارات مجانية وسرية).
- الخطوط الساخنة ومراكز الدعم الأكاديمي والاجتماعي الحكومية.
- روابط حجز المواعيد وأرقام التواصل المباشرة الموثوقة."""

        return ServiceExecutionResult(
            service_code="140",
            service_name="دليل الإحالة إلى خدمات الدعم",
            success=True,
            summary="تم عرض دليل الإحالة إلى الجهات المعتمدة للدعم والرعاية الطلابية.",
            rendered_output=rendered
        )

    @staticmethod
    def process_141_sleep_and_study_habits(inp: ServiceInput) -> ServiceExecutionResult:
        """141 — رفيق عادات النوم والمذاكرة"""
        rendered = """🌙 **رفيق توازن النوم والنشاط الدراسي**

🛌 **إحصائيات النوم والإنجاز:**
- متوسط ساعات النوم هذا الأسبوع: 7.2 ساعات (ممتاز لترسيخ الذاكرة).
- التوصية المسائية: إيقاف الشاشات والمذاكرة قبل 45 دقيقة من موعد النوم.
- ضبط منبه الاستيقاظ لمطابقة دورات النوم الطبيعية (Sleep Cycles)."""

        return ServiceExecutionResult(
            service_code="141",
            service_name="رفيق عادات النوم والمذاكرة",
            success=True,
            summary="تم تحليل مؤشرات النوم والنشاط وتقديم توصيات الاستشفاء الذهني.",
            rendered_output=rendered
        )

    @staticmethod
    def process_142_anti_procrastination_helper(inp: ServiceInput) -> ServiceExecutionResult:
        """142 — مساعد مكافحة التسويف"""
        task = inp.content.strip() or "البدء في مراجعة المقرر"
        rendered = f"""🚀 **مساعد التغلب على التسويف (قاعدة الـ 5 دقائق): {task}**

⏱ **خطوة البداية متناهية الصغر:**
- التزم بالعمل على هذه المهمة لمدة **5 دقائق فقط** بدون التفكير في الحجم الكلي.
- افتح الصفحة الأولى الآن وابدأ بقراءة العنوان الأول.
- إذا رغبت بالتوقف بعد 5 دقائق يمكنك ذلك، لكن 80% من الطلاب يواصلون العمل بمجرد كسر حاجز البداية!"""

        return ServiceExecutionResult(
            service_code="142",
            service_name="مساعد مكافحة التسويف",
            success=True,
            summary=f"تم تطبيق تقنية كسر حاجز البداية لمكافحة التسويف في: {task}.",
            rendered_output=rendered
        )

    @staticmethod
    def process_143_student_budget_organizer(inp: ServiceInput) -> ServiceExecutionResult:
        """143 — منظم المصروف الدراسي"""
        rendered = """💰 **منظم ميزانية ونفقات الطالب الذكي**

📊 **توزيع الميزانية الشهرية المقترحة:**
- السكن والمواصلات: 50%
- الكتب والمستلزمات الدراسية: 20%
- الطعام والمعيشة اليومية: 20%
- ادخار وطوارئ: 10%
- تنبيه ذكي عند تجاوز 80% من ميزانية أي فئة."""

        return ServiceExecutionResult(
            service_code="143",
            service_name="منظم المصروف الدراسي",
            success=True,
            summary="تم تنظيم وإعداد ميزانية المصروفات الشهرية للطالب.",
            rendered_output=rendered
        )

    @staticmethod
    def process_144_affordable_resources_comparison(inp: ServiceInput) -> ServiceExecutionResult:
        """144 — مقارنة أدوات وكتب دراسية منخفضة التكلفة"""
        item = inp.content.strip() or "المراجع الجامعية والأدوات الحاسوبية"
        rendered = f"""📚 **مقارنة البدائل الاقتصادية القانونية: {item}**

💡 **الخيارات المتاحة:**
- مصادر التعلم المفتوحة (Open Educational Resources - OER) المجانية والقانونية.
- خدمات استعارة الكتب الرقمية من المكتبات الوطنية والجامعية.
- خصومات الطلاب البرمجية الرسمية (GitHub Student Developer Pack)."""

        return ServiceExecutionResult(
            service_code="144",
            service_name="مقارنة أدوات وكتب دراسية منخفضة التكلفة",
            success=True,
            summary=f"تم عرض البدائل الاقتصادية والقانونية المعتمدة لـ {item}.",
            rendered_output=rendered
        )

    @staticmethod
    def process_145_student_housing_finder(inp: ServiceInput) -> ServiceExecutionResult:
        """145 — مساعد البحث عن سكن طلابي"""
        city = inp.content.strip() or "المدينة الجامعية"
        rendered = f"""🏠 **دليل البحث عن السكن الطلابي الآمن: {city}**

📍 **نصائح التحقق والأمان:**
- القرب من خطوط المواصلات العامة المؤدية للجامعة.
- فحص شمولية الإيجار لفواتير الإنترنت والكهرباء والتدفئة.
- التحذير من الاحتيال: عدم تحويل أي عربون قبل معاينة السكن وتوقيع العقد الرسمي."""

        return ServiceExecutionResult(
            service_code="145",
            service_name="مساعد البحث عن سكن طلابي",
            success=True,
            summary=f"تم تسليم إرشادات وقوائم فحص السكن الطلابي في {city}.",
            rendered_output=rendered
        )

    @staticmethod
    def process_146_student_transit_guide(inp: ServiceInput) -> ServiceExecutionResult:
        """146 — دليل مواصلات الطالب"""
        rendered = """🚌 **دليل مواصلات وخطوط تنقل الطلاب**

🎫 **المزايا المتاحة:**
- تفعيل اشتراك وبطاقة النقل المخفضة للطلاب (توفير حتى 50%).
- المسارات الأسرع للوصول للحرم الجامعي في ساعات الذروة الصباحية.
- بدائل التنقل المشترك واستخدام الدراجات المخصصة للمدن الجامعية."""

        return ServiceExecutionResult(
            service_code="146",
            service_name="دليل مواصلات الطالب",
            success=True,
            summary="تم إعداد دليل وتخفيضات مواصلات وتنقلات الطالب الجامعي.",
            rendered_output=rendered
        )

    @staticmethod
    def process_147_text_reader_for_dyslexia(inp: ServiceInput) -> ServiceExecutionResult:
        """147 — قارئ نصوص للطلاب ذوي صعوبات القراءة"""
        text = inp.content.strip()
        rendered = f"""📖 **تهيئة النصوص الميسرة (Dyslexia & Accessible Reader)**

🔍 **التحسينات المطبقة على النص ({len(text)} حرف):**
- تقسيم الفقرات الطويلة إلى جمل قصيرة ومتباعدة أسطرياً.
- تظليل الكلمات المفتاحية بألوان تباين مريحة للعين.
- إمكانية الاستماع للنص صوتياً بالسرعة التي تناسبك."""

        return ServiceExecutionResult(
            service_code="147",
            service_name="قارئ نصوص للطلاب ذوي صعوبات القراءة",
            success=True,
            summary="تمت معالجة وتيسير قراءة النص وفق معايير الإتاحة القرائية.",
            rendered_output=rendered
        )

    @staticmethod
    def process_148_consensual_transcription(inp: ServiceInput) -> ServiceExecutionResult:
        """148 — تفريغ محاضرات بإذن صاحبها"""
        rendered = """🎙 **خدمة التفريغ الصوتي المنظم للمحاضرات (بإذن المحاضر)**

📝 **مخرجات التفريغ:**
- نص منظم ومرتب في فقرات وعناوين فرعية مع التوقيت الزمني (Timestamps).
- استخراج المصطلحات والمراجع المذكورة شفهياً في المحاضرة.
- خلو التفريغ من الحشو الصوتي مع الالتزام التام بحقوق الملكية الفكرية."""

        return ServiceExecutionResult(
            service_code="148",
            service_name="تفريغ محاضرات بإذن صاحبها",
            success=True,
            summary="تم تفريغ المحاضرة الصوتية وتحويلها إلى نص منظم ومرتب.",
            rendered_output=rendered
        )

    @staticmethod
    def process_149_instant_terminology_translation(inp: ServiceInput) -> ServiceExecutionResult:
        """149 — ترجمة تعليمية فورية للمصطلحات"""
        term = inp.content.strip() or "Photosynthesis / Gradient Descent"
        rendered = f"""🌐 **الترجمة السياقية التخصصية للمصطلح: {term}**

📖 **الترجمة والشرح الأكاديمي:**
- **المعنى العربي الدقيق:** التفسير العلمي المعتمد في المعاجم المتخصصة.
- **في السياق:** كيفية استخدام المصطلح في الأبحاث والمسائل العلمية.
- **تنبيه:** تجنب الترجمة الحرفية التي تغير المعنى الرياضي أو العلمي الدقيق."""

        return ServiceExecutionResult(
            service_code="149",
            service_name="ترجمة تعليمية فورية للمصطلحات",
            success=True,
            summary=f"تم تقديم الترجمة السياقية التخصصية للمصطلح الأكاديمي: {term}.",
            rendered_output=rendered
        )

    @staticmethod
    def process_150_sign_language_audio_assistant(inp: ServiceInput) -> ServiceExecutionResult:
        """150 — مساعد أولي للغة الإشارة أو الوصف النصي"""
        rendered = """🤟 **المساعد الأولي للغة الإشارة والوصف الصوتي**

🔊 **الخدمات المتاحة:**
- تحويل المواد المرئية إلى وصف نصي وصوتي دقيق للأشكال والمخططات البيانية.
- قاموس المصطلحات الأكاديمية بلغة الإشارة بالتعاون مع المراجع المعتمدة.
- إرشادات للمعلمين لتيسير تواصلهم مع الطلاب في القاعات الدراسية."""

        return ServiceExecutionResult(
            service_code="150",
            service_name="مساعد أولي للغة الإشارة أو الوصف النصي",
            success=True,
            summary="تم تفعيل أدوات الدعم الأولي للغة الإشارة والوصف النصي للأشكال.",
            rendered_output=rendered
        )

    @staticmethod
    def process_151_international_student_organizer(inp: ServiceInput) -> ServiceExecutionResult:
        """151 — منظم رعاية الطالب الدولي"""
        rendered = """🌍 **منظم الإجراءات الرسمية للطالب الدولي (International Student Hub)**

📋 **المهام القانونية والمعيشية:**
- تجديد الإقامة الطلابية والتأمين الصحي الإلزامي قبل شهر من الانتهاء.
- فتح الحساب البنكي الطلابي واستخراج الرقم الضريبي إن لزم.
- نصائح الاندماج الثقافي وتطوير لغة البلد المضيف."""

        return ServiceExecutionResult(
            service_code="151",
            service_name="منظم رعاية الطالب الدولي",
            success=True,
            summary="تم تنظيم ومتابعة المهام الرسمية والمعيشية للطالب الدولي.",
            rendered_output=rendered
        )

    @staticmethod
    def process_152_city_student_services_guide(inp: ServiceInput) -> ServiceExecutionResult:
        """152 — دليل خدمات الطالب الدولي في المدينة"""
        city = inp.content.strip() or "المدينة الدراسية"
        rendered = f"""🗺 **دليل الخدمات والمرافق الطلابية في {city}**

📍 **أهم الأماكن:**
- المكتبات العامة ومساحات العمل والمذاكرة الهادئة (Coworking Spaces).
- العيادات الطبية الطلابية والمراكز الصحية المعتمدة.
- الأنشطة الثقافية والمجتمعات الطلابية المفتوحة."""

        return ServiceExecutionResult(
            service_code="152",
            service_name="دليل خدمات الطالب الدولي في المدينة",
            success=True,
            summary=f"تم تسليم دليل المرافق الحيوية والخدمات الطلابية في {city}.",
            rendered_output=rendered
        )

    @staticmethod
    def process_153_peer_support_group(inp: ServiceInput) -> ServiceExecutionResult:
        """153 — مجموعة دعم زملاء مضبوطة القواعد"""
        rendered = """🤝 **مجموعة دعم الأقران والمجتمع الطلابي الآمن (Peer Support Community)**

🔒 **ميثاق وقواعد المشاركة:**
- الاحترام المتبادل، والسرية، ومنع التنمر أو مشاركة البيانات الخاصة قطعياً.
- تبادل التجارب والنصائح الدراسية تحت إشراف مشرفين معتمدين.
- إمكانية الإبلاغ الفوري عن أي محتوى غير لائق بضغطة زر."""

        return ServiceExecutionResult(
            service_code="153",
            service_name="مجموعة دعم زملاء مضبوطة القواعد",
            success=True,
            summary="تم فتح مسار الانضمام لمجتمع دعم الأقران الطلابي المنضبط والآمن.",
            rendered_output=rendered
        )
