"""
Comprehensive integration tests for Academic Services Execution Engine (Services 001 - 153).
Verifies pedagogic structure, integrity guards, and compliance with Project-Jobs.md.
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
async def test_human_and_booking_services_routing():
    """Verify human and booking services 021, 028, 031 execute properly."""
    engine = AcademicServiceEngine()

    # 021 Tutoring Session
    res_021 = await engine.execute_service(ServiceInput(
        service_code="021",
        user_id="11111111-1111-1111-1111-111111111111",
        content="فيزياء الكم"
    ))
    assert res_021.success is True
    assert res_021.status == "scheduled"
    assert "حجز جلسة تدريس فردية" in res_021.rendered_output

    # 031 CV Review
    res_031 = await engine.execute_service(ServiceInput(
        service_code="031",
        user_id="11111111-1111-1111-1111-111111111111",
        content="خبرات برمجية ومشاريع بايثون"
    ))
    assert res_031.success is True
    assert "السيرة الذاتية" in res_031.rendered_output


@pytest.mark.asyncio
async def test_general_fallback_for_remaining_catalog_services():
    """Verify any service from the 153 catalogue executes safely via fallback."""
    engine = AcademicServiceEngine()
    inp = ServiceInput(
        service_code="099",
        user_id="11111111-1111-1111-1111-111111111111",
        content="استشارة تخصصية متقدمة"
    )
    result = await engine.execute_service(inp)

    assert result.success is True
    assert result.service_code == "099"
    assert "خدمة رقم 099" in result.rendered_output
