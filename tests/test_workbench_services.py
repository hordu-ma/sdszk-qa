from __future__ import annotations

import io
import zipfile

import pytest

from src.apps.api.services.knowledge_service import _ilike_pattern, chunk_text, extract_text
from src.apps.api.services.skill_runtime import (
    SKILL_REGISTRY,
    RegisteredSkill,
    input_hash,
    register_skill,
)


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
