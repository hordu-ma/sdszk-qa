import pytest

from src.apps.api.models import TeachingProject
from src.apps.api.schemas.workbench import ProfessionalInputInput
from src.apps.api.services.professional_input_service import (
    ProfessionalInputRule,
    evaluate_professional_input,
    professional_input_rules,
    register_professional_input_rule,
)


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
        "basis_query": "青年责任教学目标与评价证据",
        "course_basis": "课程标准要求形成有依据的价值判断。",
        "learning_objectives": "结合材料提出有依据的价值判断。",
        "class_context": "高一3班，45人，可开展小组讨论。",
        "course_type": "议题式",
        "activity_format": "混合",
        "intended_use": "日常教学",
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
        _payload(
            course_basis="",
            learning_objectives="",
            class_context="",
            available_resources="",
        ),
    )

    assert conflicts == []
    assert len(assumptions) == 4
    assert all("暂未填写" in item for item in assumptions)


def test_professional_input_rule_registry_is_ordered_and_non_scoring() -> None:
    assert [rule.rule_id for rule in professional_input_rules()] == [
        "course_type_mismatch",
        "lesson_time_exceeds_available",
        "digital_activity_without_devices",
        "practice_objective_without_activity",
        "restricted_resource_for_public_use",
        "collaboration_condition_conflict",
    ]

    with pytest.raises(ValueError, match="禁止评分/排名"):
        register_professional_input_rule(
            ProfessionalInputRule("teacher_scoring", ("score",), lambda *_: None)
        )
    with pytest.raises(ValueError, match="重复注册"):
        register_professional_input_rule(professional_input_rules()[0])


@pytest.mark.parametrize(
    ("overrides", "expected_conflict"),
    [
        (
            {"learning_objectives": "完成社会调查实践并展示", "activity_format": "讲授"},
            "practice_objective_without_activity",
        ),
        (
            {"intended_use": "公开课", "available_resources": "案例材料仅内部使用"},
            "restricted_resource_for_public_use",
        ),
        (
            {"teacher_intent": "组织小组讨论", "class_context": "场地限制，无法分组"},
            "collaboration_condition_conflict",
        ),
    ],
)
def test_professional_input_detects_extensible_rule_conflicts(
    overrides: dict[str, object], expected_conflict: str
) -> None:
    conflicts, assumptions = evaluate_professional_input(_project(), _payload(**overrides))

    assert [item.conflict_id for item in conflicts] == [expected_conflict]
    assert assumptions == []
