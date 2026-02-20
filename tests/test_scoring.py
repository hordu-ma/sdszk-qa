from src.apps.api.models import (
    Case,
    Message,
    Session,
    TestRequest as SessionTestRequest,
)
from src.apps.api.services.scoring import ScoringService


def _build_case() -> Case:
    return Case(
        title="高血压伴头晕",
        difficulty="medium",
        department="心内科",
        patient_info={"age": 56, "gender": "male", "occupation": "司机"},
        chief_complaint="头晕 1 周",
        present_illness="近一周反复头晕，无恶心呕吐",
        past_history={"diseases": ["高血压"], "allergies": [], "medications": []},
        physical_exam={"visible": {}, "on_request": {}},
        available_tests=[{"type": "blood_routine", "name": "血常规"}],
        standard_diagnosis={"primary": "高血压病 2 级（很高危）", "differential": []},
        key_points=["头晕、头痛症状及特点", "血压测量值（165/105 mmHg）"],
        recommended_tests=["blood_routine", "blood_lipid"],
        is_active=True,
        source="fixed",
        generation_meta=None,
    )


def test_calculate_score_with_keywords_and_tests() -> None:
    case = _build_case()
    session = Session(user_id=1, case_id=1)
    messages = [
        Message(session_id=1, role="user", content="头晕大概一周，血压有点高。"),
        Message(session_id=1, role="assistant", content="好的。"),
    ]
    test_requests = [
        SessionTestRequest(
            session_id=1,
            test_type="blood_routine",
            test_name="血常规",
            result={"wbc": "7.2"},
        )
    ]

    result = ScoringService.calculate_score(
        session=session,
        case=case,
        messages=messages,
        test_requests=test_requests,
        submitted_diagnosis="高血压病 2 级",
    )

    assert result.total_score >= 0
    assert result.dimensions["interview_completeness"] > 0
    assert result.dimensions["test_appropriateness"] > 0
    assert result.dimensions["diagnosis_accuracy"] > 0
    assert "头晕、头痛症状及特点" in result.details["key_points_covered"]
