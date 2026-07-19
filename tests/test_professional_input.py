from src.apps.api.models import TeachingProject
from src.apps.api.schemas.workbench import ProfessionalInputInput
from src.apps.api.services.professional_input_service import evaluate_professional_input


def _project() -> TeachingProject:
    return TeachingProject(
        id=1,
        owner_id=1,
        title="高中议题式样板",
        stage="高中",
        course_type="议题式",
        status="draft",
    )


def _payload(**overrides: object) -> ProfessionalInputInput:
    data: dict[str, object] = {
        "project_id": 1,
        "topic": "青年责任",
        "core_question": "青年如何承担时代责任？",
        "course_basis": "课程标准要求形成有依据的价值判断。",
        "class_context": "高一3班，45人，可开展小组讨论。",
        "course_type": "议题式",
        "lesson_minutes": 45,
        "available_minutes": 45,
        "teacher_intent": "通过材料研读和讨论形成判断。",
        "available_resources": "普通教室，多媒体可用。",
        "assumptions_confirmed": False,
    }
    data.update(overrides)
    return ProfessionalInputInput.model_validate(data)


def test_professional_input_accepts_explicit_compatible_conditions() -> None:
    conflicts, assumptions = evaluate_professional_input(_project(), _payload())

    assert conflicts == []
    assert assumptions == []


def test_professional_input_detects_time_and_course_type_conflicts() -> None:
    conflicts, assumptions = evaluate_professional_input(
        _project(),
        _payload(course_type="案例式", lesson_minutes=60, available_minutes=40),
    )

    assert {item.conflict_id for item in conflicts} == {
        "course_type_mismatch",
        "lesson_time_exceeds_available",
    }
    assert {item.severity for item in conflicts} == {"blocking"}
    assert assumptions == []


def test_professional_input_detects_digital_resource_conflict() -> None:
    conflicts, _ = evaluate_professional_input(
        _project(),
        _payload(
            teacher_intent="使用在线视频组织数字化探究。",
            available_resources="教室无设备且无网络。",
        ),
    )

    assert [item.conflict_id for item in conflicts] == [
        "digital_activity_without_devices"
    ]


def test_professional_input_marks_missing_fields_as_assumptions() -> None:
    conflicts, assumptions = evaluate_professional_input(
        _project(),
        _payload(course_basis="", class_context="", available_resources=""),
    )

    assert conflicts == []
    assert len(assumptions) == 3
    assert all("暂未填写" in item for item in assumptions)
