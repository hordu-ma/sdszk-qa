from __future__ import annotations

import io
import zipfile

from src.apps.api.models import KnowledgeChunk, KnowledgeDocument
from src.apps.api.services.knowledge_service import _rank, chunk_text, extract_text


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


def test_rank_only_returns_supported_basis() -> None:
    document = KnowledgeDocument(
        project_id=1,
        owner_id=1,
        filename="basis.md",
        content_type="text/markdown",
        object_key="test/basis.md",
        checksum_sha256="0" * 64,
    )
    relevant = KnowledgeChunk(
        document_id=1,
        chunk_index=0,
        content="家国情怀教学目标需要对应学习任务和评价证据",
        location_label="分块 1",
    )
    unrelated = KnowledgeChunk(
        document_id=1,
        chunk_index=1,
        content="课堂设备使用说明",
        location_label="分块 2",
    )
    ranked = _rank("家国情怀教学目标", [(relevant, document), (unrelated, document)])
    assert [item[1] for item in ranked] == [relevant]
