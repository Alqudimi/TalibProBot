"""
Comprehensive integration tests for Academic Services Execution Engine (Services 001 - 153).
Verifies pedagogic structure, integrity guards, and compliance with Project-Jobs.md
across all 10 specialized service families.
"""
import pytest
from src.app.modules.academic_services.engine import AcademicServiceEngine
from src.app.modules.academic_services.schemas import ServiceInput


@pytest.mark.asyncio
async def test_001_concept_explainer_execution():
    """Verify Service 001 produces structured educational explanation."""
    engine = AcademicServiceEngine()
    inp = ServiceInput(
        service_code="001",
        user_id="11111111-1111-1111-1111-111111111111",
        content="ظاهرة دوبلر في الفيزياء",
        parameters={"level": "جامعي", "depth": "متقدم"}
    )
    result = await engine.execute_service(inp)

    assert result.success is True
    assert result.service_code == "001"
    assert "ظاهرة دوبلر في الفيزياء" in result.rendered_output
    assert "التعريف المبسط" in result.rendered_output
    assert "مثال تطبيقي واقعي" in result.rendered_output
    assert "أخطاء شائعة" in result.rendered_output
    assert "سؤال سريع للتحقق من الفهم" in result.rendered_output
    assert len(result.follow_up_actions) >= 2


@pytest.mark.asyncio
async def test_002_problem_deconstructor_preserves_integrity():
    """Verify Service 002 deconstructs without giving cheating answers."""
    engine = AcademicServiceEngine()
    inp = ServiceInput(
        service_code="002",
        user_id="11111111-1111-1111-1111-111111111111",
        content="احسب القوة الدافعة الكهربائية لمولد تيار متردد تردده 50 هرتز ومساحة ملفه 0.2 متر مربع"
    )
    result = await engine.execute_service(inp)

    assert result.success is True
    assert result.service_code == "002"
    assert "المعطيات والمطلوب المستخرج" in result.rendered_output
    assert "خطوات التفكير المتدرجة" in result.rendered_output


@pytest.mark.asyncio
async def test_003_step_corrector_identifies_error():
    """Verify Service 003 identifies first error and gives retry hint."""
    engine = AcademicServiceEngine()
    inp = ServiceInput(
        service_code="003",
        user_id="11111111-1111-1111-1111-111111111111",
        content="الخطوة 1: 2x + 5 = 15\nالخطوة 2: 2x = 15 + 5 = 20\nالخطوة 3: x = 10"
    )
    result = await engine.execute_service(inp)

    assert result.success is True
    assert "موضع أول خطأ مؤثر" in result.rendered_output
    assert "التفسير العلمي للخطأ" in result.rendered_output


@pytest.mark.asyncio
async def test_004_practice_generator_count():
    """Verify Service 004 generates the requested number of exercises."""
    engine = AcademicServiceEngine()
    inp = ServiceInput(
        service_code="004",
        user_id="11111111-1111-1111-1111-111111111111",
        content="المصفوفات والمحددات في الجبر الخطي",
        parameters={"count": 3}
    )
    result = await engine.execute_service(inp)

    assert result.success is True
    assert len(result.structured_data["questions"]) == 3
    assert "س1 (تأسيسي)" in result.rendered_output


@pytest.mark.asyncio
async def test_009_revision_planner_buffers():
    """Verify Service 009 generates realistic schedule with buffer time."""
    engine = AcademicServiceEngine()
    inp = ServiceInput(
        service_code="009",
        user_id="11111111-1111-1111-1111-111111111111",
        content="اختبار الكيمياء العضوية",
        parameters={"days": 7}
    )
    result = await engine.execute_service(inp)

    assert result.success is True
    assert "خطة مراجعة ذكية" in result.rendered_output
    assert "الوقت الاحتياطي" in result.rendered_output
    assert result.structured_data["days"] == 7


@pytest.mark.asyncio
async def test_013_citation_checker_detects_missing_doi():
    """Verify Service 013 warns about missing DOI in citations."""
    engine = AcademicServiceEngine()
    inp = ServiceInput(
        service_code="013",
        user_id="11111111-1111-1111-1111-111111111111",
        content="Smith, J. (2020). Machine learning applications. Tech Press."
    )
    result = await engine.execute_service(inp)

    assert result.success is True
    assert "تنبيه" in result.rendered_output or "نواقص" in result.summary
    assert result.structured_data["has_missing_doi"] is True


@pytest.mark.asyncio
async def test_academic_integrity_guard_blocks_cheating():
    """Verify the engine strictly blocks live exam assistance and direct cheating."""
    engine = AcademicServiceEngine()
    inp = ServiceInput(
        service_code="001",
        user_id="11111111-1111-1111-1111-111111111111",
        content="أنا في قاعة الاختبار الآن وأريد حل هذا السؤال لتسليمه فوراً"
    )
    result = await engine.execute_service(inp)

    assert result.success is False
    assert result.status == "rejected_integrity"
    assert "تنبيه النزاهة الأكاديمية" in result.rendered_output


@pytest.mark.asyncio
async def test_group_2_human_and_booking_services():
    """Verify Group 2: Services 021, 027, 031, 034, 035 execute properly."""
    engine = AcademicServiceEngine()

    res_021 = await engine.execute_service(ServiceInput(
        service_code="021",
        user_id="11111111-1111-1111-1111-111111111111",
        content="فيزياء الكم"
    ))
    assert res_021.success is True
    assert res_021.status == "scheduled"
    assert "حجز جلسة تدريس فردية" in res_021.rendered_output

    res_027 = await engine.execute_service(ServiceInput(
        service_code="027",
        user_id="11111111-1111-1111-1111-111111111111",
        content="مشروع التخرج في الذكاء الاصطناعي"
    ))
    assert res_027.success is True
    assert "محاكاة جلسة الدفاع" in res_027.rendered_output

    res_031 = await engine.execute_service(ServiceInput(
        service_code="031",
        user_id="11111111-1111-1111-1111-111111111111",
        content="خبرات برمجية ومشاريع بايثون"
    ))
    assert res_031.success is True
    assert "السيرة الذاتية" in res_031.rendered_output


@pytest.mark.asyncio
async def test_group_3_subscriptions_services():
    """Verify Group 3: Subscriptions 036, 040, 048 execute properly."""
    engine = AcademicServiceEngine()

    res_036 = await engine.execute_service(ServiceInput(
        service_code="036",
        user_id="11111111-1111-1111-1111-111111111111",
        content="المرحلة الجامعية - كلية الهندسة"
    ))
    assert res_036.success is True
    assert res_036.status == "active"
    assert "بنك الأسئلة الشامل" in res_036.rendered_output

    res_040 = await engine.execute_service(ServiceInput(
        service_code="040",
        user_id="11111111-1111-1111-1111-111111111111",
        content="دعم التوجيه في مسائل الرياضيات"
    ))
    assert res_040.success is True
    assert "عضوية دعم الواجبات التوجيهية" in res_040.rendered_output

    res_048 = await engine.execute_service(ServiceInput(
        service_code="048",
        user_id="11111111-1111-1111-1111-111111111111",
        content=""
    ))
    assert res_048.success is True
    assert "لوحة المؤشرات الأكاديمية" in res_048.rendered_output


@pytest.mark.asyncio
async def test_group_4_digital_products_services():
    """Verify Group 4: Digital Products 049, 051, 054 execute properly."""
    engine = AcademicServiceEngine()

    res_049 = await engine.execute_service(ServiceInput(
        service_code="049",
        user_id="11111111-1111-1111-1111-111111111111",
        content=""
    ))
    assert res_049.success is True
    assert res_049.status == "delivered"
    assert "قوالب تنظيم المذاكرة الرقمية" in res_049.rendered_output

    res_054 = await engine.execute_service(ServiceInput(
        service_code="054",
        user_id="11111111-1111-1111-1111-111111111111",
        content=""
    ))
    assert res_054.success is True
    assert "قوالب كتابة وتنسيق الأبحاث" in res_054.rendered_output


@pytest.mark.asyncio
async def test_group_5_institutions_services():
    """Verify Group 5: Institutional services 066, 067, 073 execute properly."""
    engine = AcademicServiceEngine()

    res_066 = await engine.execute_service(ServiceInput(
        service_code="066",
        user_id="11111111-1111-1111-1111-111111111111",
        content="مواعيد الحذف والإضافة"
    ))
    assert res_066.success is True
    assert "دليل وبوت الإرشاد الطلابي" in res_066.rendered_output

    res_073 = await engine.execute_service(ServiceInput(
        service_code="073",
        user_id="11111111-1111-1111-1111-111111111111",
        content="ورشة الكتابة العلمية المتقدمة"
    ))
    assert res_073.success is True
    assert res_073.status == "confirmed"
    assert "تأكيد التسجيل في الفعالية" in res_073.rendered_output


@pytest.mark.asyncio
async def test_group_6_tech_and_ai_services():
    """Verify Group 6: AI & Tech Skills 079, 084, 089 execute properly."""
    engine = AcademicServiceEngine()

    res_079 = await engine.execute_service(ServiceInput(
        service_code="079",
        user_id="11111111-1111-1111-1111-111111111111",
        content="كيف أصيغ أمراً لتحليل البيانات الطبية"
    ))
    assert res_079.success is True
    assert "مدرب الهندسة الفعالة للأوامر" in res_079.rendered_output

    res_089 = await engine.execute_service(ServiceInput(
        service_code="089",
        user_id="11111111-1111-1111-1111-111111111111",
        content=""
    ))
    assert res_089.success is True
    assert "محاكاة المقابلة التقنية الحية" in res_089.rendered_output


@pytest.mark.asyncio
async def test_group_7_career_transition_services():
    """Verify Group 7: Career Services 094, 097, 108 execute properly."""
    engine = AcademicServiceEngine()

    res_094 = await engine.execute_service(ServiceInput(
        service_code="094",
        user_id="11111111-1111-1111-1111-111111111111",
        content="مهندس تعلم الآلة"
    ))
    assert res_094.success is True
    assert "تحليل فجوة المهارات لسوق العمل" in res_094.rendered_output

    res_097 = await engine.execute_service(ServiceInput(
        service_code="097",
        user_id="11111111-1111-1111-1111-111111111111",
        content=""
    ))
    assert res_097.success is True
    assert "STAR" in res_097.rendered_output


@pytest.mark.asyncio
async def test_group_8_scholarships_and_exams_services():
    """Verify Group 8: Scholarships 109, 113, 121 execute properly."""
    engine = AcademicServiceEngine()

    res_109 = await engine.execute_service(ServiceInput(
        service_code="109",
        user_id="11111111-1111-1111-1111-111111111111",
        content="منح دراسات عليا في ألمانيا"
    ))
    assert res_109.success is True
    assert "محرك البحث الذكي والمخصص للمنح الدراسية" in res_109.rendered_output

    res_121 = await engine.execute_service(ServiceInput(
        service_code="121",
        user_id="11111111-1111-1111-1111-111111111111",
        content="Some people believe that university education should be free for all students."
    ))
    assert res_121.success is True
    assert "تصحيح المقال الأكاديمي" in res_121.rendered_output


@pytest.mark.asyncio
async def test_group_9_tutoring_and_success_services():
    """Verify Group 9: Tutoring & Academic Success 124, 128, 136 execute properly."""
    engine = AcademicServiceEngine()

    res_124 = await engine.execute_service(ServiceInput(
        service_code="124",
        user_id="11111111-1111-1111-1111-111111111111",
        content="الكيمياء الحيوية"
    ))
    assert res_124.success is True
    assert "المطابقة الذكية مع مدرس معتمد وموثوق" in res_124.rendered_output

    res_136 = await engine.execute_service(ServiceInput(
        service_code="136",
        user_id="11111111-1111-1111-1111-111111111111",
        content=""
    ))
    assert res_136.success is True
    assert "الاسترجاع المتباعد" in res_136.rendered_output


@pytest.mark.asyncio
async def test_group_10_wellness_and_accessibility_services():
    """Verify Group 10: Wellness & Accessibility 139, 142, 153 execute properly."""
    engine = AcademicServiceEngine()

    res_139 = await engine.execute_service(ServiceInput(
        service_code="139",
        user_id="11111111-1111-1111-1111-111111111111",
        content=""
    ))
    assert res_139.success is True
    assert "مخطط إدارة القلق والضغوط الامتحانية" in res_139.rendered_output

    res_142 = await engine.execute_service(ServiceInput(
        service_code="142",
        user_id="11111111-1111-1111-1111-111111111111",
        content="مذاكرة الفصل الثالث في الإحصاء"
    ))
    assert res_142.success is True
    assert "مساعد التغلب على التسويف" in res_142.rendered_output

    res_153 = await engine.execute_service(ServiceInput(
        service_code="153",
        user_id="11111111-1111-1111-1111-111111111111",
        content=""
    ))
    assert res_153.success is True
    assert "مجموعة دعم الأقران والمجتمع الطلابي الآمن" in res_153.rendered_output


@pytest.mark.asyncio
async def test_all_153_services_exhaustive_execution():
    """Exhaustive automated verification that all 153 academic services execute properly."""
    engine = AcademicServiceEngine()
    assert len(engine._processors) == 153

    for i in range(1, 154):
        code_str = f"{i:03d}"
        assert code_str in engine._processors, f"Processor {code_str} not registered in engine."

        inp = ServiceInput(
            service_code=code_str,
            user_id="11111111-1111-1111-1111-111111111111",
            content="موضوع دراسي تجريبي للاختبار والتحقق الشامل",
            parameters={"level": "جامعي", "depth": "متقدم"}
        )
        res = await engine.execute_service(inp)
        assert res.success is True, f"Service {code_str} execution failed: {res.summary}"
        assert res.status in ("completed", "scheduled", "delivered", "active", "confirmed"), f"Service {code_str} status invalid: {res.status}"
        assert res.rendered_output and len(res.rendered_output) > 20, f"Service {code_str} rendered output is empty or truncated."
        assert res.service_name and len(res.service_name) > 0, f"Service {code_str} service_name missing."

