from __future__ import annotations

import io
import zipfile

import pytest

from src.apps.api.models import TeachingProject
from src.apps.api.scripts.seed_demo import _demo_users
from src.apps.api.services.knowledge_service import (
    _char_vector_similarity,
    _ilike_pattern,
    chunk_text,
    extract_text,
)
from src.apps.api.services.model_gateway import (
    OllamaAdapter,
    OpenAICompatibleAdapter,
    resolve_provider_adapter,
)
from src.apps.api.services.skill_runtime import (
    SKILL_REGISTRY,
    RegisteredSkill,
    input_hash,
    register_skill,
)
from src.apps.api.services.vertical_sample_service import build_docx


def test_extract_text_supports_markdown() -> None:
    text = extract_text("basis.md", "课程标准\n\n家国情怀教学目标".encode())
    assert "家国情怀" in text


def test_extract_text_supports_docx_without_extra_parser() -> None:
    body = """<?xml version="1.0" encoding="UTF-8"?>
    <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
      <w:body><w:p><w:r><w:t>课程标准依据</w:t></w:r></w:p></w:body>
    </w:document>"""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("word/document.xml", body)
    assert extract_text("basis.docx", buffer.getvalue()) == "课程标准依据"


def test_chunk_text_keeps_content() -> None:
    source = "第一部分课程依据。\n\n第二部分教学目标。"
    chunks = chunk_text(source)
    assert chunks
    assert "课程依据" in "".join(chunks)
    assert "教学目标" in "".join(chunks)


def test_ilike_pattern_escapes_wildcards() -> None:
    assert _ilike_pattern("50%目标_测试") == r"%50\%目标\_测试%"
    assert _ilike_pattern("反斜杠\\") == "%反斜杠\\\\%"


def test_input_hash_is_order_stable() -> None:
    assert input_hash({"a": 1, "b": "文"}) == input_hash({"b": "文", "a": 1})
    assert input_hash({"a": 1}) != input_hash({"a": 2})


def test_registry_registers_retrieve_basis_baseline() -> None:
    skill = SKILL_REGISTRY["skill.retrieve_basis"]
    assert skill.skill_version == "1.1.0"
    assert skill.maturity == "baseline"
    assert skill.required_roles == ()


def test_registry_contains_vertical_sample_chain() -> None:
    assert list(SKILL_REGISTRY) == [
        "skill.retrieve_basis",
        "skill.alignment_card",
        "skill.design_blueprint",
        "skill.generate_section",
        "skill.diagnose_artifact",
        "skill.export_artifact",
    ]
    assert all(item.degradation_policy for item in SKILL_REGISTRY.values())


def test_char_vector_similarity_prefers_related_text() -> None:
    related = _char_vector_similarity("家国情怀教学目标", "家国情怀目标与评价证据一致")
    unrelated = _char_vector_similarity("家国情怀教学目标", "数据库备份与容器运行")
    assert related > unrelated


def test_build_docx_contains_required_ooxml_parts() -> None:
    project = TeachingProject(
        id=1,
        owner_id=1,
        title="高中议题式教学样板",
        stage="高中",
        course_type="议题式",
    )
    data = build_docx(
        project,
        {
            "alignment_card": {
                "core_question": "如何理解家国情怀",
                "objectives": ["目标"],
                "citations": [{"filename": "课程标准.md", "location_label": "分块 1"}],
            },
            "design_blueprint": {
                "evidence": ["观点陈述"],
                "learning_tasks": [{"title": "研读", "minutes": 15, "evidence": "研读记录"}],
            },
            "lesson_design": {
                "section_name": "课时设计",
                "opening": "从真实情境导入",
                "activities": [
                    {
                        "title": "讨论",
                        "minutes": 15,
                        "teacher_action": "提出问题",
                        "student_action": "引用依据",
                        "evidence": "课堂发言",
                    }
                ],
                "teacher_notes": ["保留教师确认点"],
            },
            "diagnosis": {
                "conclusion": "可进入教师确认",
                "items": [
                    {
                        "dimension": "依据可追溯",
                        "status": "aligned",
                        "evidence": "引用 1 条",
                        "suggestion": "复核有效期",
                    }
                ],
            },
        },
    )
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        assert "word/document.xml" in archive.namelist()
        assert "word/styles.xml" in archive.namelist()
        document = archive.read("word/document.xml").decode()
        assert "高中议题式教学样板" in document
        assert "教师活动" in document
        assert "改进建议" in document
        assert "<w:tbl>" in document
        assert "{'title'" not in document


def test_demo_users_split_admin_and_teacher(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEMO_PASSWORD", "shared-test-password")
    monkeypatch.setenv("DEMO_ADMIN_USERNAME", "demo_admin")
    monkeypatch.setenv("DEMO_TEACHER_USERNAME", "demo_teacher")
    monkeypatch.delenv("DEMO_ADMIN_PASSWORD", raising=False)
    monkeypatch.delenv("DEMO_TEACHER_PASSWORD", raising=False)
    users = _demo_users()

    assert [(item["username"], item["role"]) for item in users] == [
        ("demo_admin", "admin"),
        ("demo_teacher", "teacher"),
    ]
    assert {item["password"] for item in users} == {"shared-test-password"}


def test_provider_adapters_parse_stream_contracts() -> None:
    ollama = OllamaAdapter()
    content, done = ollama.parse_line('{"message":{"content":"鲁韵"},"done":false}')
    assert (content, done) == ("鲁韵", False)

    openai = OpenAICompatibleAdapter()
    content, done = openai.parse_line('data: {"choices":[{"delta":{"content":"思政"}}]}')
    assert (content, done) == ("思政", False)
    assert openai.parse_line("data: [DONE]") == ("", True)
    assert isinstance(resolve_provider_adapter("vllm"), OpenAICompatibleAdapter)


def test_registry_rejects_scoring_skills() -> None:
    template = SKILL_REGISTRY["skill.retrieve_basis"]
    with pytest.raises(ValueError, match="评分/排名"):
        register_skill(
            RegisteredSkill(
                skill_id="skill.teacher_score",
                skill_version="0.0.1",
                name="非法评分",
                input_model=template.input_model,
                output_model=template.output_model,
                handler=template.handler,
            )
        )
    assert "skill.teacher_score" not in SKILL_REGISTRY
