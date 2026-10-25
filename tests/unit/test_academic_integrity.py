import pytest
from src.app.modules.service_requests.service import ServiceRequestService
from src.app.shared.errors import AcademicIntegrityViolationError


def test_academic_integrity_allows_educational_questions():
    # Valid learning questions should pass without exception
    ServiceRequestService.screen_academic_integrity("اشرح لي قاعدة كيرشوف في الدوائر الكهربائية مع مثال")
    ServiceRequestService.screen_academic_integrity("كيف أكتب مقدمة بحث في القانون الإداري بنمط APA؟")
    ServiceRequestService.screen_academic_integrity("أريد جدول مراجعة لاختبار الكيمياء خلال أسبوعين")


def test_academic_integrity_blocks_direct_cheating():
    # Direct cheating or exam solving attempts should raise AcademicIntegrityViolationError
    with pytest.raises(AcademicIntegrityViolationError):
        ServiceRequestService.screen_academic_integrity("حل لي اختبار كويز الآن مباشر يا بوت")

    with pytest.raises(AcademicIntegrityViolationError):
        ServiceRequestService.screen_academic_integrity("ادخل عني الامتحان وحل لي الأسئلة")

    with pytest.raises(AcademicIntegrityViolationError):
        ServiceRequestService.screen_academic_integrity("تسريب اسئلة امتحان الفيزياء للغد")
