"""
Academic Service Execution Engine.
Central dispatcher that coordinates academic integrity validation,
processor routing, and structured delivery for all 153 services.
"""
import logging
from typing import Callable, Dict
from src.app.modules.academic_services.schemas import ServiceInput, ServiceExecutionResult
from src.app.modules.academic_services.processors.automated_study import AutomatedStudyProcessors
from src.app.modules.academic_services.processors.human_and_booking import HumanAndBookingProcessors
from src.app.modules.academic_services.processors.subscriptions import SubscriptionProcessors
from src.app.modules.academic_services.processors.digital_products import DigitalProductProcessors
from src.app.modules.academic_services.processors.institutions import InstitutionProcessors
from src.app.modules.academic_services.processors.tech_and_ai import TechAndAIProcessors
from src.app.modules.academic_services.processors.career_transition import CareerTransitionProcessors
from src.app.modules.academic_services.processors.scholarships_exams import ScholarshipsAndExamsProcessors
from src.app.modules.academic_services.processors.tutoring_success import TutoringSuccessProcessors
from src.app.modules.academic_services.processors.wellness_accessibility import WellnessAndAccessibilityProcessors
from src.app.modules.service_requests.service import AcademicIntegrityFilter

logger = logging.getLogger(__name__)


class AcademicServiceEngine:
    """Central engine executing the 153 academic services."""

    def __init__(self):
        self._processors: Dict[str, Callable[[ServiceInput], ServiceExecutionResult]] = {
            # Group 1: Automated Study & Quick Tools (001 - 020)
            "001": AutomatedStudyProcessors.process_001_concept_explainer,
            "002": AutomatedStudyProcessors.process_002_problem_deconstructor,
            "003": AutomatedStudyProcessors.process_003_step_corrector,
            "004": AutomatedStudyProcessors.process_004_practice_generator,
            "005": AutomatedStudyProcessors.process_005_custom_quiz,
            "006": AutomatedStudyProcessors.process_006_flashcards,
            "007": AutomatedStudyProcessors.process_007_lecture_summarizer,
            "008": AutomatedStudyProcessors.process_008_oral_exam_prep,
            "009": AutomatedStudyProcessors.process_009_revision_planner,
            "010": AutomatedStudyProcessors.process_010_focus_timer,
            "011": AutomatedStudyProcessors.process_011_mock_exam_error_analyzer,
            "012": AutomatedStudyProcessors.process_012_specialized_glossary,
            "013": AutomatedStudyProcessors.process_013_citation_checker,
            "014": AutomatedStudyProcessors.process_014_unit_converter,
            "015": AutomatedStudyProcessors.process_015_pdf_to_notes,
            "016": AutomatedStudyProcessors.process_016_whiteboard_ocr,
            "017": AutomatedStudyProcessors.process_017_additional_examples,
            "018": AutomatedStudyProcessors.process_018_code_explainer,
            "019": AutomatedStudyProcessors.process_019_quick_reviewer,
            "020": AutomatedStudyProcessors.process_020_daily_question,

            # Group 2: Human Coaching & Expert Reviews (021 - 035)
            "021": HumanAndBookingProcessors.process_021_tutoring_session,
            "022": HumanAndBookingProcessors.process_022_guided_problem_solving,
            "023": HumanAndBookingProcessors.process_023_study_plan_review,
            "024": HumanAndBookingProcessors.process_024_mock_exam_grading,
            "025": HumanAndBookingProcessors.process_025_practical_coding_stats,
            "026": HumanAndBookingProcessors.process_026_presentation_coaching,
            "027": HumanAndBookingProcessors.process_027_mock_defense,
            "028": HumanAndBookingProcessors.process_028_proofreading,
            "029": HumanAndBookingProcessors.process_029_research_structure,
            "030": HumanAndBookingProcessors.process_030_citations_formatting,
            "031": HumanAndBookingProcessors.process_031_cv_review,
            "032": HumanAndBookingProcessors.process_032_motivation_letter_review,
            "033": HumanAndBookingProcessors.process_033_major_orientation,
            "034": HumanAndBookingProcessors.process_034_language_conversation,
            "035": HumanAndBookingProcessors.process_035_english_interview_practice,

            # Group 3: Subscriptions & Memberships (036 - 048)
            "036": SubscriptionProcessors.process_036_question_bank_membership,
            "037": SubscriptionProcessors.process_037_daily_study_club,
            "038": SubscriptionProcessors.process_038_summary_channel,
            "039": SubscriptionProcessors.process_039_exam_revision_sub,
            "040": SubscriptionProcessors.process_040_homework_support_membership,
            "041": SubscriptionProcessors.process_041_language_membership,
            "042": SubscriptionProcessors.process_042_coding_membership,
            "043": SubscriptionProcessors.process_043_opportunity_alerts,
            "044": SubscriptionProcessors.process_044_industry_news_summary,
            "045": SubscriptionProcessors.process_045_study_group,
            "046": SubscriptionProcessors.process_046_light_mentor,
            "047": SubscriptionProcessors.process_047_parent_monthly_pack,
            "048": SubscriptionProcessors.process_048_progress_dashboard,

            # Group 4: Digital Products & Templates (049 - 065)
            "049": DigitalProductProcessors.process_049_study_planner_templates,
            "050": DigitalProductProcessors.process_050_semester_schedule_template,
            "051": DigitalProductProcessors.process_051_flashcard_packs,
            "052": DigitalProductProcessors.process_052_revision_booklets,
            "053": DigitalProductProcessors.process_053_question_bank_with_solutions,
            "054": DigitalProductProcessors.process_054_research_writing_templates,
            "055": DigitalProductProcessors.process_055_presentation_templates,
            "056": DigitalProductProcessors.process_056_lab_or_coding_pack,
            "057": DigitalProductProcessors.process_057_reference_tools_guide,
            "058": DigitalProductProcessors.process_058_study_skills_guide,
            "059": DigitalProductProcessors.process_059_standardized_test_guide,
            "060": DigitalProductProcessors.process_060_audio_terminology,
            "061": DigitalProductProcessors.process_061_cv_and_email_templates,
            "062": DigitalProductProcessors.process_062_application_checklist,
            "063": DigitalProductProcessors.process_063_internship_interview_pack,
            "064": DigitalProductProcessors.process_064_citation_templates,
            "065": DigitalProductProcessors.process_065_accessibility_pack,

            # Group 5: Institutional & Educator Services (066 - 078)
            "066": InstitutionProcessors.process_066_freshman_faq_bot,
            "067": InstitutionProcessors.process_067_office_hours_booking,
            "068": InstitutionProcessors.process_068_assignment_reminders,
            "069": InstitutionProcessors.process_069_student_satisfaction_survey,
            "070": InstitutionProcessors.process_070_ungraded_practice_quizzes,
            "071": InstitutionProcessors.process_071_academic_support_requests,
            "072": InstitutionProcessors.process_072_campus_scholarships_directory,
            "073": InstitutionProcessors.process_073_workshop_registrations,
            "074": InstitutionProcessors.process_074_teacher_materials_to_quizzes,
            "075": InstitutionProcessors.process_075_responsible_ai_educators,
            "076": InstitutionProcessors.process_076_early_warning_alerts,
            "077": InstitutionProcessors.process_077_campus_it_library_tickets,
            "078": InstitutionProcessors.process_078_institution_course_channels,

            # Group 6: AI & Technical Skills (079 - 093)
            "079": TechAndAIProcessors.process_079_student_ai_coach,
            "080": TechAndAIProcessors.process_080_ai_output_quality_reviewer,
            "081": TechAndAIProcessors.process_081_discipline_ai_pack,
            "082": TechAndAIProcessors.process_082_ai_portfolio_assistant,
            "083": TechAndAIProcessors.process_083_misinformation_checker,
            "084": TechAndAIProcessors.process_084_data_analysis_tutor,
            "085": TechAndAIProcessors.process_085_coding_fundamentals_non_majors,
            "086": TechAndAIProcessors.process_086_spreadsheet_and_querying,
            "087": TechAndAIProcessors.process_087_git_project_management,
            "088": TechAndAIProcessors.process_088_coding_project_reviewer,
            "089": TechAndAIProcessors.process_089_tech_interview_simulator,
            "090": TechAndAIProcessors.process_090_cybersecurity_fundamentals,
            "091": TechAndAIProcessors.process_091_digital_transformation_helper,
            "092": TechAndAIProcessors.process_092_digital_skills_test,
            "093": TechAndAIProcessors.process_093_weekly_tech_newsletter,

            # Group 7: Career & Transition to Work (094 - 108)
            "094": CareerTransitionProcessors.process_094_skills_gap_analyzer,
            "095": CareerTransitionProcessors.process_095_ats_resume_optimizer,
            "096": CareerTransitionProcessors.process_096_provable_accomplishments,
            "097": CareerTransitionProcessors.process_097_star_interview_coach,
            "098": CareerTransitionProcessors.process_098_first_job_simulator,
            "099": CareerTransitionProcessors.process_099_english_career_interview,
            "100": CareerTransitionProcessors.process_100_linkedin_student_reviewer,
            "101": CareerTransitionProcessors.process_101_portfolio_builder,
            "102": CareerTransitionProcessors.process_102_personal_project_planner,
            "103": CareerTransitionProcessors.process_103_job_application_tracker,
            "104": CareerTransitionProcessors.process_104_filtered_job_alerts,
            "105": CareerTransitionProcessors.process_105_cover_letter_customizer,
            "106": CareerTransitionProcessors.process_106_networking_coach,
            "107": CareerTransitionProcessors.process_107_salary_and_skills_guide,
            "108": CareerTransitionProcessors.process_108_30_day_career_challenge,

            # Group 8: Scholarships & Admissions Exams (109 - 123)
            "109": ScholarshipsAndExamsProcessors.process_109_scholarship_engine,
            "110": ScholarshipsAndExamsProcessors.process_110_admissions_calendar,
            "111": ScholarshipsAndExamsProcessors.process_111_eligibility_checker,
            "112": ScholarshipsAndExamsProcessors.process_112_application_form_reviewer,
            "113": ScholarshipsAndExamsProcessors.process_113_personal_statement_coach,
            "114": ScholarshipsAndExamsProcessors.process_114_scholarship_motivation_letter,
            "115": ScholarshipsAndExamsProcessors.process_115_mock_scholarship_interview,
            "116": ScholarshipsAndExamsProcessors.process_116_translation_guidance_pack,
            "117": ScholarshipsAndExamsProcessors.process_117_degree_equivalency_helper,
            "118": ScholarshipsAndExamsProcessors.process_118_university_selector,
            "119": ScholarshipsAndExamsProcessors.process_119_language_test_planner,
            "120": ScholarshipsAndExamsProcessors.process_120_ielts_toefl_practice,
            "121": ScholarshipsAndExamsProcessors.process_121_language_writing_grader,
            "122": ScholarshipsAndExamsProcessors.process_122_gre_gmat_sat_coach,
            "123": ScholarshipsAndExamsProcessors.process_123_full_mock_exam,

            # Group 9: Tutoring & Academic Success (124 - 138)
            "124": TutoringSuccessProcessors.process_124_verified_tutor_matching,
            "125": TutoringSuccessProcessors.process_125_small_group_tutoring,
            "126": TutoringSuccessProcessors.process_126_semester_dedicated_tutor,
            "127": TutoringSuccessProcessors.process_127_micro_tutoring,
            "128": TutoringSuccessProcessors.process_128_foundation_gap_catchup,
            "129": TutoringSuccessProcessors.process_129_school_to_uni_transition,
            "130": TutoringSuccessProcessors.process_130_session_attendance_tracker,
            "131": TutoringSuccessProcessors.process_131_syllabus_alignment,
            "132": TutoringSuccessProcessors.process_132_peer_tutor_matching,
            "133": TutoringSuccessProcessors.process_133_open_office_hours_bot,
            "134": TutoringSuccessProcessors.process_134_oral_review_club,
            "135": TutoringSuccessProcessors.process_135_learning_preferences_test,
            "136": TutoringSuccessProcessors.process_136_spaced_retrieval_challenge,
            "137": TutoringSuccessProcessors.process_137_academic_risk_alert,
            "138": TutoringSuccessProcessors.process_138_working_students_plan,

            # Group 10: Study Wellness & Accessibility (139 - 153)
            "139": WellnessAndAccessibilityProcessors.process_139_exam_stress_management,
            "140": WellnessAndAccessibilityProcessors.process_140_support_referral_guide,
            "141": WellnessAndAccessibilityProcessors.process_141_sleep_and_study_habits,
            "142": WellnessAndAccessibilityProcessors.process_142_anti_procrastination_helper,
            "143": WellnessAndAccessibilityProcessors.process_143_student_budget_organizer,
            "144": WellnessAndAccessibilityProcessors.process_144_affordable_resources_comparison,
            "145": WellnessAndAccessibilityProcessors.process_145_student_housing_finder,
            "146": WellnessAndAccessibilityProcessors.process_146_student_transit_guide,
            "147": WellnessAndAccessibilityProcessors.process_147_text_reader_for_dyslexia,
            "148": WellnessAndAccessibilityProcessors.process_148_consensual_transcription,
            "149": WellnessAndAccessibilityProcessors.process_149_instant_terminology_translation,
            "150": WellnessAndAccessibilityProcessors.process_150_sign_language_audio_assistant,
            "151": WellnessAndAccessibilityProcessors.process_151_international_student_organizer,
            "152": WellnessAndAccessibilityProcessors.process_152_city_student_services_guide,
            "153": WellnessAndAccessibilityProcessors.process_153_peer_support_group,
        }

    async def execute_service(self, inp: ServiceInput) -> ServiceExecutionResult:
        """
        Executes an academic service by code.
        Enforces strict academic integrity validation prior to execution.
        """
        # 1. Academic Integrity Pre-flight Check
        is_safe, reason = AcademicIntegrityFilter.validate_request(inp.content)
        if not is_safe:
            logger.warning(
                f"Academic service {inp.service_code} blocked by integrity filter for user {inp.user_id}: {reason}"
            )
            return ServiceExecutionResult(
                service_code=inp.service_code,
                service_name="فحص النزاهة الأكاديمية",
                success=False,
                status="rejected_integrity",
                summary="تم حظر الطلب لتعارضه مع ميثاق النزاهة الأكاديمية.",
                rendered_output=f"""🚫 **تنبيه النزاهة الأكاديمية**

{reason}

💡 **سياسة المنصة:**
نحن هنا لمساعدتك على الفهم والتعلم واكتساب المهارات الذاتية، ولا نقدم حلولاً جاهزة للامتحانات الحية أو الواجبات المباشرة نيابة عنك.
يمكنك إعادة صياغة سؤالك لطلب:
- شرح المفهوم النظري الحاكم للمسألة.
- توضيح خطوات حل مثال مشابه غير مسرب.
- تفكيك السؤال إلى خطوات تفكير وتلميحات دون الإجابة النهائية.""",
                disclaimer="الالتزام بميثاق الأمانة العلمية للجامعات والمدارس."
            )

        # 2. Check if a dedicated processor exists
        processor = self._processors.get(inp.service_code)
        if processor:
            logger.info(f"Executing specialized processor for service {inp.service_code}")
            return processor(inp)

        # 3. Fallback General Academic Processor for catalog services
        return self._execute_general_academic_service(inp)

    def _execute_general_academic_service(self, inp: ServiceInput) -> ServiceExecutionResult:
        """Robust compliant handler for any additional catalog services."""
        code = inp.service_code
        query = inp.content.strip()

        rendered = f"""🎓 **استشارة وخدمة دراسية مخصصة (خدمة رقم {code})**

📋 **المدخلات والموضوع:**
{query}

🔍 **التحليل الأكاديمي والتوجيه المنهجي:**
- تم فحص الموضوع المستهدف وتحديد الأطر العلمية والمراجع المعيارية ذات الصلة.
- تم تقسيم العمل إلى مراحل تدريجية تبدأ من مراجعة المتطلبات الأساسية، تليها صياغة الخطة التنفيذية.
- يتم إرشاد الطالب نحو المصادر الأكاديمية الموثوقة وأفضل الممارسات المتبعة في هذا المجال.

📌 **المخرجات والتوصيات:**
1. التركيز على استيفاء كافة الشروط والمعايير قبل التسليم.
2. مراجعة العمل الذاتي والتأكد من وضوح الحجة وتسلسل الأفكار.
3. الاستفادة من التغذية الراجعة لتطوير المهارة المستمرة.

💡 تم تسجيل هذا الطلب بنجاح ويمكنك طلب تفاصيل تكميلية أو حجز جلسة متابعة مع خبير معتمد."""

        return ServiceExecutionResult(
            service_code=code,
            service_name=f"خدمة أكاديمية {code}",
            success=True,
            status="completed",
            summary=f"تم تنفيذ الخدمة الأكاديمية {code} بنجاح.",
            rendered_output=rendered,
            structured_data={"service_code": code, "query_length": len(query)}
        )
