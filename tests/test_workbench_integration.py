from __future__ import annotations

from uuid import uuid4

import bcrypt
import httpx
import pytest
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.apps.api.dependencies import AsyncSessionLocal, engine
from src.apps.api.main import app
from src.apps.api.models import (
    MemoryInjectionAudit,
    SkillRun,
    SpotCheckItem,
    TeachingProject,
    User,
)
from src.apps.api.services.model_asset_service import sync_model_assets
from src.apps.api.services.organization_service import ensure_default_pilot_org


async def _ensure_schema() -> None:
    """建表并启用库内检索所需扩展（CI 全新数据库场景）。"""
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(User.metadata.create_all)
    async with AsyncSessionLocal() as db:
        await sync_model_assets(db)


async def _attach_pilot_org(db: AsyncSession, *users: User) -> None:
    """把测试用户挂到默认试点组织，满足 WP2.5 白名单门禁。"""
    org = await ensure_default_pilot_org(db)
    await db.flush()
    for user in users:
        user.organization_id = org.id


@pytest.mark.integration
@pytest.mark.asyncio(loop_scope="session")
async def test_project_upload_retrieve_and_task_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    await _ensure_schema()

    username = f"workbench_{uuid4().hex[:8]}"
    password = "password123"
    user = User(
        username=username,
        hashed_password=bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode(),
        full_name="工作台集成测试",
        role="admin",
        is_active=True,
    )
    reviewer_username = f"reviewer_{uuid4().hex[:8]}"
    reviewer = User(
        username=reviewer_username,
        hashed_password=bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode(),
        full_name="专家复核集成测试",
        role="reviewer",
        is_active=True,
    )
    arbitrator_username = f"arbitrator_{uuid4().hex[:8]}"
    arbitrator = User(
        username=arbitrator_username,
        hashed_password=bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode(),
        full_name="专家仲裁集成测试",
        role="reviewer",
        is_active=True,
    )
    async with AsyncSessionLocal() as db:
        db.add_all([user, reviewer, arbitrator])
        await _attach_pilot_org(db, user, reviewer, arbitrator)
        await db.commit()
        await db.refresh(user)
        await db.refresh(reviewer)
        await db.refresh(arbitrator)
        user_id = user.id
        reviewer_id = reviewer.id
        arbitrator_id = arbitrator.id

    source = "课程标准指出家国情怀教学目标应与学习任务和评价证据保持一致。".encode()

    objects: dict[str, bytes] = {}

    async def _put_object(object_key: str, data: bytes, content_type: str) -> None:
        del content_type
        objects[object_key] = data

    async def _get_object(object_key: str) -> bytes:
        return objects.get(object_key, source)

    monkeypatch.setattr("src.apps.api.routes.workbench.put_object", _put_object)
    monkeypatch.setattr("src.apps.api.routes.workbench.get_object", _get_object)
    monkeypatch.setattr("src.apps.api.services.knowledge_service.get_object", _get_object)
    monkeypatch.setattr("src.apps.api.services.vertical_sample_service.put_object", _put_object)

    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            login = await client.post(
                "/api/auth/login", json={"username": username, "password": password}
            )
            headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
            reviewer_login = await client.post(
                "/api/auth/login",
                json={"username": reviewer_username, "password": password},
            )
            reviewer_headers = {
                "Authorization": f"Bearer {reviewer_login.json()['access_token']}"
            }
            arbitrator_login = await client.post(
                "/api/auth/login",
                json={"username": arbitrator_username, "password": password},
            )
            arbitrator_headers = {
                "Authorization": f"Bearer {arbitrator_login.json()['access_token']}"
            }
            project_response = await client.post(
                "/api/workbench/projects",
                json={"title": "家国情怀样板", "stage": "高中", "course_type": "议题式"},
                headers=headers,
            )
            assert project_response.status_code == 201
            project_id = project_response.json()["id"]

            upload = await client.post(
                f"/api/workbench/projects/{project_id}/documents",
                files={"file": ("basis.md", source, "text/markdown")},
                headers=headers,
            )
            assert upload.status_code == 202
            assert upload.json()["task"]["status"] == "queued"

            documents = await client.get(
                f"/api/workbench/projects/{project_id}/documents", headers=headers
            )
            assert documents.json()[0]["status"] == "ready"
            assert documents.json()[0]["review_status"] == "pending"
            document_id = documents.json()[0]["id"]

            review = await client.post(
                f"/api/workbench/documents/{document_id}/review",
                json={"review_status": "approved"},
                headers=headers,
            )
            assert review.status_code == 200
            assert review.json()["review_status"] == "approved"

            retrieval = await client.post(
                "/api/workbench/skills/retrieve-basis",
                json={"project_id": project_id, "query": "家国情怀教学目标"},
                headers=headers,
            )
            assert retrieval.status_code == 200
            assert retrieval.json()["insufficient_basis"] is False
            assert retrieval.json()["retrieval_mode"] == "hybrid_trgm_char_vector"
            assert retrieval.json()["skill_version"] == "1.2.0"
            assert retrieval.json()["citations"][0]["filename"] == "basis.md"

            model_assets = await client.get(
                "/api/workbench/runtime/model-assets", headers=headers
            )
            assert model_assets.status_code == 200
            assert {item["asset_type"] for item in model_assets.json()} == {
                "generation",
                "embedding",
                "reranker",
            }
            assert all(len(item["revision"]) == 40 for item in model_assets.json())
            assert {item["status"] for item in model_assets.json()} == {"candidate"}

            dataset = await client.post(
                "/api/workbench/evaluation/datasets",
                json={
                    "project_id": project_id,
                    "dataset_key": "retrieval-smoke",
                    "name": "检索工程冒烟集",
                },
                headers=headers,
            )
            assert dataset.status_code == 201
            assert dataset.json()["version_number"] == 1
            assert dataset.json()["data_origin"] == "synthetic"
            assert dataset.json()["review_status"] == "not_applicable"
            dataset_id = dataset.json()["id"]
            rejected_review = await client.post(
                f"/api/workbench/evaluation/datasets/{dataset_id}/review",
                json={
                    "review_status": "approved",
                    "review_note": "模拟数据不得冒充专家审核",
                },
                headers=headers,
            )
            assert rejected_review.status_code == 409
            evaluation_case = await client.post(
                f"/api/workbench/evaluation/datasets/{dataset_id}/cases",
                json={
                    "case_key": "family-country-goal",
                    "query": "家国情怀教学目标",
                    "expected_document_ids": [document_id],
                },
                headers=headers,
            )
            assert evaluation_case.status_code == 201
            rejected_gold_review = await client.post(
                f"/api/workbench/evaluation/cases/{evaluation_case.json()['id']}/reviews",
                json={
                    "review_kind": "independent",
                    "expected_document_ids": [document_id],
                    "rationale": "模拟案例不得进入专家金标流程",
                },
                headers=headers,
            )
            assert rejected_gold_review.status_code == 409
            assert rejected_gold_review.json()["error_code"] == "synthetic_case_not_reviewable"
            frozen = await client.post(
                f"/api/workbench/evaluation/datasets/{dataset_id}/freeze",
                headers=headers,
            )
            assert frozen.status_code == 200
            assert frozen.json()["status"] == "frozen"
            assert len(frozen.json()["content_hash"]) == 64
            rejected_case = await client.post(
                f"/api/workbench/evaluation/datasets/{dataset_id}/cases",
                json={"case_key": "late-case", "query": "不得写入"},
                headers=headers,
            )
            assert rejected_case.status_code == 409
            evaluation_run = await client.post(
                f"/api/workbench/evaluation/datasets/{dataset_id}/runs",
                headers=headers,
            )
            assert evaluation_run.status_code == 200
            assert evaluation_run.json()["status"] == "completed"
            assert evaluation_run.json()["matched_cases"] == 1
            assert evaluation_run.json()["release_manifest"]["vllm"][
                "runtime_version"
            ] == "0.18.0"
            assert evaluation_run.json()["release_manifest"]["retrieval"][
                "embedding_max_tokens"
            ] == 512
            run_id = evaluation_run.json()["id"]
            evaluation_results = await client.get(
                f"/api/workbench/evaluation/runs/{run_id}/results", headers=headers
            )
            assert evaluation_results.status_code == 200
            assert evaluation_results.json()[0]["status"] == "matched"

            gate = await client.get(
                f"/api/workbench/evaluation/datasets/{dataset_id}/regression-gate",
                headers=headers,
            )
            assert gate.status_code == 200
            gate_body = gate.json()
            assert gate_body["verdict"] == "promotable"
            assert gate_body["can_promote"] is True
            assert gate_body["latest_run_id"] == run_id
            assert gate_body["pending_manifest_changes"] == []
            assert gate_body["metrics"]["match_rate"] == 1.0
            assert gate_body["metrics"]["top1_hit_rate"] == 1.0
            assert "不代表专家验收" in gate_body["disclaimer"]
            assert {item["check"] for item in gate_body["checks"]} == {
                "match_rate",
                "top1_hit_rate",
                "insufficient_basis_misses",
                "error_cases",
            }
            assert gate_body["baseline"] is None

            second_run = await client.post(
                f"/api/workbench/evaluation/datasets/{dataset_id}/runs",
                headers=headers,
            )
            assert second_run.status_code == 200
            gate_after_second = await client.get(
                f"/api/workbench/evaluation/datasets/{dataset_id}/regression-gate",
                headers=headers,
            )
            assert gate_after_second.status_code == 200
            second_gate_body = gate_after_second.json()
            assert second_gate_body["verdict"] == "promotable"
            assert second_gate_body["baseline"]["baseline_run_id"] == run_id
            assert second_gate_body["baseline"]["regressed_case_keys"] == []
            assert second_gate_body["baseline"]["manifest_changes"] == []

            next_dataset = await client.post(
                "/api/workbench/evaluation/datasets",
                json={
                    "project_id": project_id,
                    "dataset_key": "retrieval-smoke",
                    "name": "检索工程冒烟集第二版",
                },
                headers=headers,
            )
            assert next_dataset.status_code == 201
            assert next_dataset.json()["version_number"] == 2

            customer_dataset = await client.post(
                "/api/workbench/evaluation/datasets",
                json={
                    "project_id": project_id,
                    "dataset_key": "customer-review-draft",
                    "name": "客户资料审核草案",
                    "data_origin": "customer_provided",
                },
                headers=headers,
            )
            assert customer_dataset.status_code == 201
            assert customer_dataset.json()["review_status"] == "pending"
            reviewed_dataset = await client.post(
                f"/api/workbench/evaluation/datasets/{customer_dataset.json()['id']}/review",
                json={
                    "review_status": "approved",
                    "review_note": "集成测试审核记录",
                },
                headers=headers,
            )
            assert reviewed_dataset.status_code == 200
            assert reviewed_dataset.json()["review_status"] == "approved"
            assert reviewed_dataset.json()["reviewed_by"] == user_id

            bulk_import = await client.post(
                f"/api/workbench/evaluation/datasets/{customer_dataset.json()['id']}/cases/import",
                json={
                    "cases": [
                        {
                            "case_key": "expert-consensus",
                            "query": "家国情怀教学目标",
                            "expected_document_ids": [document_id],
                            "case_metadata": {"source_reference": "integration-test"},
                        },
                        {
                            "case_key": "expert-arbitration",
                            "query": "评价证据如何对应目标",
                            "expected_document_ids": [document_id],
                            "case_metadata": {"source_reference": "integration-test"},
                        },
                    ]
                },
                headers=headers,
            )
            assert bulk_import.status_code == 201
            imported_cases = bulk_import.json()
            assert [item["gold_status"] for item in imported_cases] == ["pending", "pending"]
            review_queue = await client.get(
                "/api/workbench/evaluation/review-queue", headers=reviewer_headers
            )
            assert customer_dataset.json()["id"] in {
                item["id"] for item in review_queue.json()
            }
            reviewer_cases = await client.get(
                f"/api/workbench/evaluation/datasets/{customer_dataset.json()['id']}/cases",
                headers=reviewer_headers,
            )
            assert reviewer_cases.status_code == 200
            assert len(reviewer_cases.json()) == 2
            premature_freeze = await client.post(
                f"/api/workbench/evaluation/datasets/{customer_dataset.json()['id']}/freeze",
                headers=headers,
            )
            assert premature_freeze.status_code == 409
            assert premature_freeze.json()["error_code"] == "evaluation_gold_not_ready"

            consensus_case_id = imported_cases[0]["id"]
            for review_headers in (headers, reviewer_headers):
                review = await client.post(
                    f"/api/workbench/evaluation/cases/{consensus_case_id}/reviews",
                    json={
                        "review_kind": "independent",
                        "expected_document_ids": [document_id],
                        "critical_error_tags": ["fabricated_citation"],
                        "rationale": "依据文档与问题匹配",
                    },
                    headers=review_headers,
                )
                assert review.status_code == 201

            arbitration_case_id = imported_cases[1]["id"]
            first_review = await client.post(
                f"/api/workbench/evaluation/cases/{arbitration_case_id}/reviews",
                json={
                    "review_kind": "independent",
                    "expected_document_ids": [document_id],
                    "rationale": "存在直接依据",
                },
                headers=headers,
            )
            assert first_review.status_code == 201
            second_review = await client.post(
                f"/api/workbench/evaluation/cases/{arbitration_case_id}/reviews",
                json={
                    "review_kind": "independent",
                    "expected_insufficient_basis": True,
                    "rationale": "第二位专家认为依据不足",
                },
                headers=reviewer_headers,
            )
            assert second_review.status_code == 201
            disputed_cases = await client.get(
                f"/api/workbench/evaluation/datasets/{customer_dataset.json()['id']}/cases",
                headers=headers,
            )
            disputed_case = next(
                item for item in disputed_cases.json() if item["id"] == arbitration_case_id
            )
            assert disputed_case["gold_status"] == "disputed"
            rejected_arbitration = await client.post(
                f"/api/workbench/evaluation/cases/{arbitration_case_id}/reviews",
                json={
                    "review_kind": "arbitration",
                    "expected_document_ids": [document_id],
                    "rationale": "仲裁确认该资料可直接支持结论",
                },
                headers=headers,
            )
            assert rejected_arbitration.status_code == 409
            assert (
                rejected_arbitration.json()["error_code"]
                == "evaluation_arbitrator_not_independent"
            )
            arbitration = await client.post(
                f"/api/workbench/evaluation/cases/{arbitration_case_id}/reviews",
                json={
                    "review_kind": "arbitration",
                    "expected_document_ids": [document_id],
                    "rationale": "独立仲裁确认该资料可直接支持结论",
                },
                headers=arbitrator_headers,
            )
            assert arbitration.status_code == 201

            formal_report = await client.get(
                f"/api/workbench/evaluation/datasets/{customer_dataset.json()['id']}/report",
                headers=headers,
            )
            assert formal_report.status_code == 200
            assert formal_report.json()["gold_status_counts"] == {
                "arbitrated": 1,
                "consensus": 1,
            }
            assert formal_report.json()["ready_for_freeze"] is True
            formal_frozen = await client.post(
                f"/api/workbench/evaluation/datasets/{customer_dataset.json()['id']}/freeze",
                headers=headers,
            )
            assert formal_frozen.status_code == 200

            alignment = await client.post(
                "/api/workbench/skills/alignment-card",
                json={
                    "project_id": project_id,
                    "topic": "高中家国情怀议题式教学",
                    "core_question": "青年如何把个人理想融入国家发展",
                    "basis_query": "家国情怀教学目标",
                },
                headers=headers,
            )
            assert alignment.status_code == 200
            assert alignment.json()["version_number"] == 2
            assert alignment.json()["citations"]

            blueprint = await client.post(
                "/api/workbench/skills/design-blueprint",
                json={"project_id": project_id, "lesson_minutes": 45},
                headers=headers,
            )
            assert blueprint.status_code == 200
            assert len(blueprint.json()["learning_tasks"]) == 3

            generated = await client.post(
                "/api/workbench/skills/generate-section",
                json={"project_id": project_id, "guidance": "增加同伴互评"},
                headers=headers,
            )
            assert generated.status_code == 200
            assert generated.json()["activities"]

            diagnosis = await client.post(
                "/api/workbench/skills/diagnose-artifact",
                json={"project_id": project_id},
                headers=headers,
            )
            assert diagnosis.status_code == 200
            assert diagnosis.json()["conclusion"] == "可进入教师确认"
            assert all(item["status"] == "aligned" for item in diagnosis.json()["items"])

            exported = await client.post(
                "/api/workbench/skills/export-artifact",
                json={"project_id": project_id, "template_name": "standard-v2"},
                headers=headers,
            )
            assert exported.status_code == 200
            assert exported.json()["template_version"] == "word-standard-v2"
            download = await client.get(exported.json()["download_url"], headers=headers)
            assert download.status_code == 200
            assert download.content.startswith(b"PK")

            versions = await client.get(
                f"/api/workbench/projects/{project_id}/versions", headers=headers
            )
            assert len(versions.json()) == 5
            diff = await client.get(
                f"/api/workbench/projects/{project_id}/versions/diff",
                params={"from_version": 1, "to_version": 5},
                headers=headers,
            )
            assert diff.status_code == 200
            assert {item["section"] for item in diff.json()["changed_sections"]} >= {
                "alignment_card",
                "design_blueprint",
                "lesson_design",
                "diagnosis",
            }

            source_content = versions.json()[0]["content"]
            edited_content = {
                **source_content,
                "lesson_design": {
                    **source_content["lesson_design"],
                    "opening": "教师修改后的课堂导入",
                },
                "_trace": {
                    "action": "teacher_edit",
                    "source_version": 5,
                    "edited_sections": ["lesson_design"],
                    "edit_summary": "调整课堂导入",
                },
            }
            edited_content.pop("diagnosis")
            manual_version = await client.post(
                f"/api/workbench/projects/{project_id}/versions",
                json={"content": edited_content, "status": "draft", "source_version": 5},
                headers=headers,
            )
            assert manual_version.status_code == 201
            assert manual_version.json()["version_number"] == 6
            assert manual_version.json()["content"]["lesson_design"]["opening"] == (
                "教师修改后的课堂导入"
            )
            assert "diagnosis" not in manual_version.json()["content"]
            assert manual_version.json()["content"]["_trace"]["action"] == "teacher_edit"

            manual_diff = await client.get(
                f"/api/workbench/projects/{project_id}/versions/diff",
                params={"from_version": 5, "to_version": 6},
                headers=headers,
            )
            assert manual_diff.status_code == 200
            assert {item["section"] for item in manual_diff.json()["changed_sections"]} >= {
                "lesson_design",
                "diagnosis",
            }

            blocked_input = await client.post(
                "/api/workbench/skills/confirm-professional-input",
                json={
                    "project_id": project_id,
                    "topic": "高中家国情怀议题式教学",
                    "core_question": "青年如何把个人理想融入国家发展",
                    "basis_query": "家国情怀教学目标与评价证据",
                    "course_basis": "课程标准要求形成有依据的价值判断。",
                    "learning_objectives": "结合材料形成有依据的价值判断。",
                    "class_context": "高一3班，45人，可开展小组讨论。",
                    "course_type": "议题式",
                    "activity_format": "混合",
                    "intended_use": "日常教学",
                    "lesson_minutes": 60,
                    "available_minutes": 45,
                    "teacher_intent": "通过材料研读和讨论形成判断。",
                    "available_resources": "普通教室，多媒体可用。",
                },
                headers=headers,
            )
            assert blocked_input.status_code == 200
            assert blocked_input.json()["version_number"] == 7
            assert blocked_input.json()["ready_for_alignment"] is False
            assert {item["conflict_id"] for item in blocked_input.json()["conflicts"]} == {
                "lesson_time_exceeds_available"
            }
            assert set(blocked_input.json()["invalidated_sections"]) == {
                "alignment_card",
                "design_blueprint",
                "lesson_design",
            }
            blocked_alignment = await client.post(
                "/api/workbench/skills/alignment-card",
                json={
                    "project_id": project_id,
                    "topic": "高中家国情怀议题式教学",
                    "core_question": "青年如何把个人理想融入国家发展",
                    "basis_query": "家国情怀教学目标",
                },
                headers=headers,
            )
            assert blocked_alignment.status_code == 409
            assert blocked_alignment.json()["error_code"] == "professional_input_not_ready"

            ready_input = await client.post(
                "/api/workbench/skills/confirm-professional-input",
                json={
                    "project_id": project_id,
                    "topic": "高中家国情怀议题式教学",
                    "core_question": "青年如何把个人理想融入国家发展",
                    "basis_query": "已确认的家国情怀依据检索问题",
                    "course_basis": "",
                    "learning_objectives": "结合材料形成有依据的价值判断。",
                    "class_context": "",
                    "course_type": "议题式",
                    "activity_format": "混合",
                    "intended_use": "日常教学",
                    "lesson_minutes": 45,
                    "available_minutes": 45,
                    "teacher_intent": "通过材料研读和讨论形成判断。",
                    "available_resources": "",
                    "assumptions_confirmed": True,
                },
                headers=headers,
            )
            assert ready_input.status_code == 200
            assert ready_input.json()["version_number"] == 8
            assert ready_input.json()["ready_for_alignment"] is True
            assert len(ready_input.json()["assumptions"]) == 3
            assert ready_input.json()["rule_set_version"] == "stage2-input-conflict-v2"
            assert ready_input.json()["confirmed_input"]["topic"] == (
                "高中家国情怀议题式教学"
            )
            versions_after_input = await client.get(
                f"/api/workbench/projects/{project_id}/versions", headers=headers
            )
            latest_input_content = versions_after_input.json()[0]["content"]
            assert latest_input_content["professional_input"]["ready_for_alignment"] is True
            assert "alignment_card" not in latest_input_content
            assert latest_input_content["_trace"]["skill_id"] == (
                "skill.confirm_professional_input"
            )

            authoritative_alignment = await client.post(
                "/api/workbench/skills/alignment-card",
                json={
                    "project_id": project_id,
                    "topic": "客户端篡改主题",
                    "core_question": "客户端篡改核心议题",
                    "basis_query": "客户端篡改检索问题",
                },
                headers=headers,
            )
            assert authoritative_alignment.status_code == 200
            assert authoritative_alignment.json()["topic"] == (
                "高中家国情怀议题式教学"
            )
            assert authoritative_alignment.json()["core_question"] == (
                "青年如何把个人理想融入国家发展"
            )
            async with AsyncSessionLocal() as db:
                run = await db.get(
                    SkillRun, authoritative_alignment.json()["skill_run_id"]
                )
                assert run is not None
                assert run.input_payload["professional_input_version"] == 8
                assert run.input_payload["effective_input"] == {
                    "topic": "高中家国情怀议题式教学",
                    "core_question": "青年如何把个人理想融入国家发展",
                    "basis_query": "已确认的家国情怀依据检索问题",
                }

            tasks = await client.get(
                "/api/workbench/tasks", params={"project_id": project_id}, headers=headers
            )
            assert tasks.json()[0]["status"] == "completed"
    finally:
        async with AsyncSessionLocal() as db:
            projects = await db.execute(
                delete(TeachingProject).where(TeachingProject.owner_id == user_id)
            )
            del projects
            await db.execute(delete(User).where(User.id == user_id))
            await db.execute(delete(User).where(User.id == reviewer_id))
            await db.execute(delete(User).where(User.id == arbitrator_id))
            await db.commit()


@pytest.mark.integration
@pytest.mark.asyncio(loop_scope="session")
async def test_wp22_structured_generation_lock_restore_and_artifacts() -> None:
    """WP2.2：锁定、局部重生成、多成果、字段差异和恢复形成不可变闭环。"""
    await _ensure_schema()

    username = f"wp22_{uuid4().hex[:8]}"
    password = "password123"
    user = User(
        username=username,
        hashed_password=bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode(),
        full_name="WP2.2 集成验证",
        role="teacher",
        is_active=True,
    )
    async with AsyncSessionLocal() as db:
        db.add(user)
        await _attach_pilot_org(db, user)
        await db.commit()
        await db.refresh(user)
        user_id = user.id

    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            login = await client.post(
                "/api/auth/login", json={"username": username, "password": password}
            )
            headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
            project = await client.post(
                "/api/workbench/projects",
                json={"title": "WP2.2 结构化闭环", "stage": "高中", "course_type": "议题式"},
                headers=headers,
            )
            project_id = project.json()["id"]
            initial_content = {
                "alignment_card": {
                    "topic": "青年责任",
                    "core_question": "青年如何承担时代责任",
                    "objectives": ["形成有依据的价值判断"],
                    "citations": [],
                },
                "design_blueprint": {
                    "core_question": "青年如何承担时代责任",
                    "objectives": ["形成有依据的价值判断"],
                    "evidence": ["观点与依据记录"],
                    "learning_tasks": [
                        {"title": "材料研读", "minutes": 20, "evidence": "研读记录"},
                        {"title": "观点讨论", "minutes": 25, "evidence": "讨论记录"},
                    ],
                },
                "lesson_design": {
                    "section_name": "课时设计",
                    "opening": "从青年榜样故事导入。",
                    "activities": [
                        {
                            "sequence": 1,
                            "title": "材料研读",
                            "minutes": 20,
                            "teacher_action": "提供材料",
                            "student_action": "提取观点",
                            "evidence": "研读记录",
                        }
                    ],
                    "assessment_evidence": ["观点与依据记录"],
                    "teacher_notes": ["追问依据来源"],
                },
                "diagnosis": {"conclusion": "旧诊断", "items": [], "blocking_issues": []},
            }
            seeded = await client.post(
                f"/api/workbench/projects/{project_id}/versions",
                json={"content": initial_content, "source_version": 1},
                headers=headers,
            )
            assert seeded.status_code == 201
            seeded_version = seeded.json()["version_number"]

            locked = await client.post(
                f"/api/workbench/projects/{project_id}/versions/locks",
                json={
                    "source_version": seeded_version,
                    "locked_paths": ["lesson_design.opening"],
                },
                headers=headers,
            )
            assert locked.status_code == 201
            locked_version = locked.json()["version_number"]
            assert locked.json()["content"]["editor_state"]["locked_paths"] == [
                "lesson_design.opening"
            ]

            blocked = await client.post(
                "/api/workbench/skills/generate-section",
                json={
                    "project_id": project_id,
                    "artifact_kind": "lesson_design",
                    "target_path": "lesson_design.opening",
                    "guidance": "改为问题导入",
                    "source_version": locked_version,
                },
                headers=headers,
            )
            assert blocked.status_code == 409
            assert blocked.json()["error_code"] == "target_locked"

            regenerated = await client.post(
                "/api/workbench/skills/generate-section",
                json={
                    "project_id": project_id,
                    "artifact_kind": "lesson_design",
                    "target_path": "lesson_design.activities.0.evidence",
                    "guidance": "补充可定位材料编号",
                    "source_version": locked_version,
                },
                headers=headers,
            )
            assert regenerated.status_code == 200
            regenerated_version = regenerated.json()["version_number"]
            assert regenerated.json()["changed_paths"] == [
                "lesson_design.activities.0.evidence"
            ]
            versions = await client.get(
                f"/api/workbench/projects/{project_id}/versions", headers=headers
            )
            regenerated_content = versions.json()[0]["content"]
            assert regenerated_content["lesson_design"]["opening"] == (
                "从青年榜样故事导入。"
            )
            assert "补充可定位材料编号" in regenerated_content["lesson_design"][
                "activities"
            ][0]["evidence"]
            assert "diagnosis" not in regenerated_content

            diff = await client.get(
                f"/api/workbench/projects/{project_id}/versions/diff",
                params={"from_version": locked_version, "to_version": regenerated_version},
                headers=headers,
            )
            assert diff.status_code == 200
            field_paths = {item["path"] for item in diff.json()["field_changes"]}
            assert "lesson_design.activities.0.evidence" in field_paths
            assert "diagnosis" in field_paths
            assert "lesson_design.opening" not in field_paths

            stale = await client.post(
                "/api/workbench/skills/generate-section",
                json={
                    "project_id": project_id,
                    "target_path": "lesson_design.teacher_notes",
                    "source_version": locked_version,
                },
                headers=headers,
            )
            assert stale.status_code == 409
            assert stale.json()["error_code"] == "source_version_conflict"

            current_version = regenerated_version
            artifact_kinds = [
                "task_sheet",
                "rubric",
                "board_plan",
                "slide_outline",
                "practice_task",
            ]
            for artifact_kind in artifact_kinds:
                artifact = await client.post(
                    "/api/workbench/skills/generate-section",
                    json={
                        "project_id": project_id,
                        "artifact_kind": artifact_kind,
                        "source_version": current_version,
                    },
                    headers=headers,
                )
                assert artifact.status_code == 200
                assert artifact.json()["artifact_kind"] == artifact_kind
                current_version = artifact.json()["version_number"]

            artifact_versions = await client.get(
                f"/api/workbench/projects/{project_id}/versions", headers=headers
            )
            artifact_content = artifact_versions.json()[0]["content"]
            assert set(artifact_content["teaching_artifacts"]) == set(artifact_kinds)
            assert "不计分、不排名" in artifact_content["teaching_artifacts"]["rubric"][
                "title"
            ]
            all_artifacts_version = current_version

            artifact_lock = await client.post(
                f"/api/workbench/projects/{project_id}/versions/locks",
                json={
                    "source_version": current_version,
                    "locked_paths": [
                        "lesson_design.opening",
                        "teaching_artifacts.task_sheet",
                    ],
                },
                headers=headers,
            )
            current_version = artifact_lock.json()["version_number"]
            full_regeneration = await client.post(
                "/api/workbench/skills/generate-section",
                json={
                    "project_id": project_id,
                    "artifact_kind": "lesson_design",
                    "guidance": "优化活动衔接",
                    "source_version": current_version,
                },
                headers=headers,
            )
            assert full_regeneration.status_code == 200
            current_version = full_regeneration.json()["version_number"]
            after_full = await client.get(
                f"/api/workbench/projects/{project_id}/versions", headers=headers
            )
            after_full_content = after_full.json()[0]["content"]
            assert after_full_content["lesson_design"]["opening"] == (
                "从青年榜样故事导入。"
            )
            assert set(after_full_content["teaching_artifacts"]) == {"task_sheet"}

            restored = await client.post(
                f"/api/workbench/projects/{project_id}/versions/restore",
                json={
                    "source_version": current_version,
                    "restore_version": all_artifacts_version,
                },
                headers=headers,
            )
            assert restored.status_code == 201
            assert set(restored.json()["content"]["teaching_artifacts"]) == set(
                artifact_kinds
            )
            assert restored.json()["content"]["_trace"]["action"] == "restore_version"

            tampered = restored.json()["content"]
            tampered["lesson_design"]["opening"] = "试图覆盖锁定导入"
            rejected_edit = await client.post(
                f"/api/workbench/projects/{project_id}/versions",
                json={
                    "content": tampered,
                    "source_version": restored.json()["version_number"],
                },
                headers=headers,
            )
            assert rejected_edit.status_code == 409
            assert rejected_edit.json()["error_code"] == "locked_content_changed"
    finally:
        async with AsyncSessionLocal() as db:
            await db.execute(
                delete(TeachingProject).where(TeachingProject.owner_id == user_id)
            )
            await db.execute(delete(User).where(User.id == user_id))
            await db.commit()


@pytest.mark.integration
@pytest.mark.asyncio(loop_scope="session")
async def test_wp23_evidence_diagnosis_decisions_and_apply_revision() -> None:
    """WP2.3：结构校正、证据诊断、四类决定和仅采纳项修订形成闭环。"""
    await _ensure_schema()
    username = f"wp23_{uuid4().hex[:8]}"
    password = "password123"
    user = User(
        username=username,
        hashed_password=bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode(),
        full_name="WP2.3 集成测试",
        role="teacher",
        is_active=True,
    )
    async with AsyncSessionLocal() as db:
        db.add(user)
        await _attach_pilot_org(db, user)
        await db.commit()
        await db.refresh(user)
        user_id = user.id

    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            login = await client.post(
                "/api/auth/login", json={"username": username, "password": password}
            )
            headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
            project = await client.post(
                "/api/workbench/projects",
                json={"title": "WP2.3 诊断闭环", "stage": "高中", "course_type": "议题式"},
                headers=headers,
            )
            project_id = project.json()["id"]
            seeded = await client.post(
                f"/api/workbench/projects/{project_id}/versions",
                json={
                    "source_version": 1,
                    "content": {
                        "alignment_card": {"citations": []},
                        "design_blueprint": {
                            "objectives": ["形成判断"],
                            "evidence": [],
                            "learning_tasks": [],
                        },
                        "lesson_design": {
                            "section_name": "已有教案",
                            "activities": [],
                            "teacher_notes": [],
                            "assessment_evidence": [],
                        },
                    },
                },
                headers=headers,
            )
            source_version = seeded.json()["version_number"]

            preview = await client.get(
                f"/api/workbench/projects/{project_id}/diagnosis/structure", headers=headers
            )
            assert [item["path"] for item in preview.json()] == [
                "alignment_card",
                "design_blueprint",
                "lesson_design",
            ]
            nodes = preview.json()
            nodes[2]["title"] = "教师校正后的课时设计"
            confirmed = await client.post(
                f"/api/workbench/projects/{project_id}/diagnosis/structure",
                json={"source_version": source_version, "nodes": nodes},
                headers=headers,
            )
            assert confirmed.status_code == 200
            source_version = confirmed.json()["version_number"]
            assert confirmed.json()["content"]["diagnosis_structure"]["nodes"][2]["title"] == (
                "教师校正后的课时设计"
            )

            diagnosis = await client.post(
                "/api/workbench/skills/diagnose-artifact",
                json={"project_id": project_id, "source_version": source_version},
                headers=headers,
            )
            assert diagnosis.status_code == 200
            assert diagnosis.json()["skill_version"] == "1.1.0"
            items = diagnosis.json()["items"]
            assert all(
                item["source_path"]
                and item["rule_basis"]
                and item["impact"]
                and item["example_revision"]
                for item in items
            )
            source_version = diagnosis.json()["version_number"]

            decisions = [
                ("basis_traceability", "accept", None),
                ("objective_evidence_alignment", "edit", "补充教师编辑后的观察证据。"),
                ("task_feasibility", "request_expert", None),
                ("task_feasibility", "ignore", None),
            ]
            for item_id, action, edited_suggestion in decisions:
                response = await client.post(
                    f"/api/workbench/projects/{project_id}/diagnosis/items/{item_id}/decision",
                    json={
                        "source_version": source_version,
                        "action": action,
                        "edited_suggestion": edited_suggestion,
                    },
                    headers=headers,
                )
                assert response.status_code == 200
                source_version = response.json()["version_number"]

            revised = await client.post(
                "/api/workbench/skills/apply-revision",
                json={"project_id": project_id, "source_version": source_version},
                headers=headers,
            )
            assert revised.status_code == 200
            assert revised.json()["applied_item_ids"] == [
                "basis_traceability",
                "objective_evidence_alignment",
            ]
            assert revised.json()["skipped_item_ids"] == ["task_feasibility"]
            versions = await client.get(
                f"/api/workbench/projects/{project_id}/versions", headers=headers
            )
            content = versions.json()[0]["content"]
            assert "diagnosis" not in content
            assert content["diagnosis_history"]
            assert "补充教师编辑后的观察证据。" in content["design_blueprint"]["evidence"]
            assert len(content["diagnosis_signals"]) == 4
            assert all(
                signal["signal_level"] == "L4"
                and signal["authorized_for_training"] is False
                for signal in content["diagnosis_signals"]
            )
            assert not any("分数" in str(value) for value in content.values())
    finally:
        async with AsyncSessionLocal() as db:
            await db.execute(delete(TeachingProject).where(TeachingProject.owner_id == user_id))
            await db.execute(delete(User).where(User.id == user_id))
            await db.commit()


@pytest.mark.integration
@pytest.mark.asyncio(loop_scope="session")
async def test_review_requires_reviewer_role_and_allows_cross_user(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """教师本人不能审核自己资料；审核员可审核他人资料（阶段 1A 全库范围）。"""
    await _ensure_schema()

    password = "password123"
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    teacher = User(
        username=f"teacher_{uuid4().hex[:8]}",
        hashed_password=hashed,
        full_name="资料上传教师",
        role="teacher",
        is_active=True,
    )
    reviewer = User(
        username=f"reviewer_{uuid4().hex[:8]}",
        hashed_password=hashed,
        full_name="资料审核员",
        role="reviewer",
        is_active=True,
    )
    async with AsyncSessionLocal() as db:
        db.add_all([teacher, reviewer])
        await _attach_pilot_org(db, teacher, reviewer)
        await db.commit()
        await db.refresh(teacher)
        await db.refresh(reviewer)
        teacher_id, reviewer_id = teacher.id, reviewer.id

    source = "义务教育课程标准强调法治教育要落实到真实情境中的行为选择。".encode()

    async def _put_object(*args: object, **kwargs: object) -> None:
        del args, kwargs

    async def _get_object(*args: object, **kwargs: object) -> bytes:
        del args, kwargs
        return source

    monkeypatch.setattr("src.apps.api.routes.workbench.put_object", _put_object)
    monkeypatch.setattr("src.apps.api.services.knowledge_service.get_object", _get_object)

    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            async def _login(username: str) -> dict[str, str]:
                response = await client.post(
                    "/api/auth/login", json={"username": username, "password": password}
                )
                return {"Authorization": f"Bearer {response.json()['access_token']}"}

            teacher_headers = await _login(teacher.username)
            reviewer_headers = await _login(reviewer.username)
            denied_queue = await client.get(
                "/api/workbench/evaluation/review-queue", headers=teacher_headers
            )
            assert denied_queue.status_code == 403

            project = await client.post(
                "/api/workbench/projects",
                json={"title": "法治教育样板", "stage": "初中", "course_type": "案例式"},
                headers=teacher_headers,
            )
            project_id = project.json()["id"]

            upload = await client.post(
                f"/api/workbench/projects/{project_id}/documents",
                files={"file": ("basis.md", source, "text/markdown")},
                headers=teacher_headers,
            )
            document_id = upload.json()["document"]["id"]

            denied = await client.post(
                f"/api/workbench/documents/{document_id}/review",
                json={"review_status": "approved"},
                headers=teacher_headers,
            )
            assert denied.status_code == 403

            approved = await client.post(
                f"/api/workbench/documents/{document_id}/review",
                json={"review_status": "approved"},
                headers=reviewer_headers,
            )
            assert approved.status_code == 200
            assert approved.json()["review_status"] == "approved"
    finally:
        async with AsyncSessionLocal() as db:
            await db.execute(
                delete(TeachingProject).where(TeachingProject.owner_id == teacher_id)
            )
            await db.execute(delete(User).where(User.id.in_([teacher_id, reviewer_id])))
            await db.commit()


@pytest.mark.integration
@pytest.mark.asyncio(loop_scope="session")
async def test_memory_lifecycle_injection_and_clear() -> None:
    """Memory 写入 → 显式注入并留审计 → 清除 → 已删引用不可再注入。"""
    await _ensure_schema()

    username = f"memory_{uuid4().hex[:8]}"
    password = "password123"
    user = User(
        username=username,
        hashed_password=bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode(),
        full_name="记忆集成测试",
        role="teacher",
        is_active=True,
    )
    async with AsyncSessionLocal() as db:
        db.add(user)
        await _attach_pilot_org(db, user)
        await db.commit()
        await db.refresh(user)
        user_id = user.id

    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            login = await client.post(
                "/api/auth/login", json={"username": username, "password": password}
            )
            headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

            skills = await client.get("/api/workbench/skills", headers=headers)
            assert skills.status_code == 200
            assert [item["skill_id"] for item in skills.json()] == [
                "skill.retrieve_basis",
                "skill.confirm_professional_input",
                "skill.alignment_card",
                "skill.design_blueprint",
                "skill.generate_section",
                "skill.diagnose_artifact",
                "skill.apply_revision",
                "skill.export_artifact",
            ]
            assert skills.json()[0]["status"] == "enabled"
            assert skills.json()[1]["skill_version"] == "1.1.0"

            preference = await client.put(
                "/api/workbench/memory/preference",
                json={"default_stage": "初中", "default_course_type": "案例式"},
                headers=headers,
            )
            assert preference.status_code == 200

            profile = await client.post(
                "/api/workbench/memory/class-profiles",
                json={"name": "初二3班", "context": {"class_size": 46, "devices": "多媒体"}},
                headers=headers,
            )
            assert profile.status_code == 201
            profile_id = profile.json()["id"]

            project = await client.post(
                "/api/workbench/projects",
                json={"title": "记忆注入样板", "stage": "初中", "course_type": "案例式"},
                headers=headers,
            )
            project_id = project.json()["id"]

            pinned = await client.post(
                "/api/workbench/memory/pinned-items",
                json={
                    "item_type": "project",
                    "project_id": project_id,
                    "name": "记忆注入样板",
                    "payload": {"reason": "常用样板"},
                },
                headers=headers,
            )
            assert pinned.status_code == 201

            template = await client.post(
                "/api/workbench/memory/pinned-items",
                json={
                    "item_type": "template",
                    "project_id": None,
                    "name": "初中案例式常用输入",
                    "payload": {
                        "course_type": "案例式",
                        "activity_format": "讨论",
                    },
                },
                headers=headers,
            )
            assert template.status_code == 201

            memory_refs = [{"memory_type": "class_context_profile", "memory_id": profile_id}]
            retrieval = await client.post(
                "/api/workbench/skills/retrieve-basis",
                json={
                    "project_id": project_id,
                    "query": "法治教育目标",
                    "memory_refs": memory_refs,
                },
                headers=headers,
            )
            assert retrieval.status_code == 200
            assert retrieval.json()["insufficient_basis"] is True
            skill_run_id = retrieval.json()["skill_run_id"]

            async with AsyncSessionLocal() as db:
                run = await db.get(SkillRun, skill_run_id)
                assert run is not None
                assert run.status == "completed"
                assert run.input_hash
                assert run.memory_refs == [
                    {"memory_type": "class_context_profile", "memory_id": profile_id}
                ]
                audits = await db.execute(
                    select(MemoryInjectionAudit).where(
                        MemoryInjectionAudit.skill_run_id == skill_run_id
                    )
                )
                audit_rows = list(audits.scalars())
                assert len(audit_rows) == 1
                assert audit_rows[0].snapshot["name"] == "初二3班"

            export = await client.get("/api/workbench/memory/export", headers=headers)
            assert export.json()["preference"]["default_stage"] == "初中"
            assert len(export.json()["class_profiles"]) == 1
            assert len(export.json()["pinned_items"]) == 2

            cleared = await client.post("/api/workbench/memory/clear", headers=headers)
            assert cleared.json() == {
                "cleared_preference": True,
                "cleared_class_profiles": 1,
                "cleared_pinned_items": 2,
            }

            rejected = await client.post(
                "/api/workbench/skills/retrieve-basis",
                json={
                    "project_id": project_id,
                    "query": "法治教育目标",
                    "memory_refs": memory_refs,
                },
                headers=headers,
            )
            assert rejected.status_code == 422
            assert rejected.json()["error_code"] == "memory_ref_not_found"
    finally:
        async with AsyncSessionLocal() as db:
            await db.execute(
                delete(TeachingProject).where(TeachingProject.owner_id == user_id)
            )
            await db.execute(delete(User).where(User.id == user_id))
            await db.commit()


@pytest.mark.integration
@pytest.mark.asyncio(loop_scope="session")
async def test_expired_document_excluded_from_search() -> None:
    """有效期已过的资料不得进入检索结果（资料有效期策略）。"""
    await _ensure_schema()

    from datetime import datetime, timedelta

    from src.apps.api.models import KnowledgeChunk, KnowledgeDocument
    from src.apps.api.services import knowledge_service

    user = User(
        username=f"validity_{uuid4().hex[:8]}",
        hashed_password=bcrypt.hashpw(b"password123", bcrypt.gensalt()).decode(),
        full_name="资料有效期测试",
        role="teacher",
        is_active=True,
    )
    async with AsyncSessionLocal() as db:
        db.add(user)
        await _attach_pilot_org(db, user)
        await db.commit()
        await db.refresh(user)
        user_id = user.id
        project = TeachingProject(
            owner_id=user_id,
            title="资料有效期过滤",
            stage="高中",
            course_type="议题式",
            status="draft",
        )
        db.add(project)
        await db.flush()
        expired = KnowledgeDocument(
            project_id=project.id,
            owner_id=user_id,
            filename="expired.md",
            content_type="text/markdown",
            object_key=f"test/{uuid4().hex}",
            checksum_sha256="0" * 64,
            status="ready",
            review_status="approved",
            version_number=1,
            valid_until=datetime.utcnow() - timedelta(days=1),
        )
        db.add(expired)
        await db.flush()
        db.add(
            KnowledgeChunk(
                document_id=expired.id,
                chunk_index=0,
                content="家国情怀教学目标应与学习任务保持一致。",
                location_label="段 1",
            )
        )
        await db.commit()
        project_id = project.id

    try:
        async with AsyncSessionLocal() as db:
            result = await knowledge_service.search_chunks(
                db,
                project_id=project_id,
                user_id=user_id,
                query="家国情怀教学目标",
                limit=5,
            )
        assert result.citations == []
        insufficient, reason = knowledge_service.assess_insufficiency(result.citations)
        assert insufficient is True
        assert reason == "no_candidates"
    finally:
        async with AsyncSessionLocal() as db:
            await db.execute(
                delete(TeachingProject).where(TeachingProject.owner_id == user_id)
            )
            await db.execute(delete(User).where(User.id == user_id))
            await db.commit()


@pytest.mark.integration
@pytest.mark.asyncio(loop_scope="session")
async def test_search_degrades_when_semantic_index_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """项目没有语义向量时必须显式降级，不得以语义模式返回结果。"""
    await _ensure_schema()

    from src.apps.api.models import KnowledgeChunk, KnowledgeDocument
    from src.apps.api.services import knowledge_service

    user = User(
        username=f"semidx_{uuid4().hex[:8]}",
        hashed_password=bcrypt.hashpw(b"password123", bcrypt.gensalt()).decode(),
        full_name="语义索引缺失降级测试",
        role="teacher",
        is_active=True,
    )
    async with AsyncSessionLocal() as db:
        db.add(user)
        await _attach_pilot_org(db, user)
        await db.commit()
        await db.refresh(user)
        user_id = user.id
        project = TeachingProject(
            owner_id=user_id,
            title="语义索引缺失降级",
            stage="高中",
            course_type="议题式",
            status="draft",
        )
        db.add(project)
        await db.flush()
        document = KnowledgeDocument(
            project_id=project.id,
            owner_id=user_id,
            filename="basis.md",
            content_type="text/markdown",
            object_key=f"test/{uuid4().hex}",
            checksum_sha256="0" * 64,
            status="ready",
            review_status="approved",
            version_number=1,
        )
        db.add(document)
        await db.flush()
        db.add(
            KnowledgeChunk(
                document_id=document.id,
                chunk_index=0,
                content="家国情怀教学目标应与学习任务和评价证据保持一致。",
                location_label="分块 1",
            )
        )
        await db.commit()
        project_id = project.id

    monkeypatch.setattr(knowledge_service.settings, "SEMANTIC_RAG_ENABLED", True)

    async def _fake_embed(texts: list[str]) -> list[list[float]]:
        vector = [0.0] * knowledge_service.settings.EMBEDDING_DIMENSIONS
        vector[0] = 1.0
        return [vector for _ in texts]

    async def _fail_rerank(query: str, documents: list[str]) -> list:
        del query, documents
        raise AssertionError("语义索引缺失时不应调用 Reranker")

    monkeypatch.setattr(knowledge_service, "embed_texts", _fake_embed)
    monkeypatch.setattr(knowledge_service, "rerank", _fail_rerank)

    try:
        async with AsyncSessionLocal() as db:
            result = await knowledge_service.search_chunks(
                db,
                project_id=project_id,
                user_id=user_id,
                query="家国情怀教学目标",
                limit=5,
            )
        assert result.mode == knowledge_service.DEGRADED_RETRIEVAL_MODE
        assert "semantic_index_missing" in (result.degraded_reason or "")
        assert result.citations
    finally:
        async with AsyncSessionLocal() as db:
            await db.execute(
                delete(TeachingProject).where(TeachingProject.owner_id == user_id)
            )
            await db.execute(delete(User).where(User.id == user_id))
            await db.commit()


@pytest.mark.integration
@pytest.mark.asyncio(loop_scope="session")
async def test_wp24_spot_check_queue_and_l4_signal_summary() -> None:
    """WP2.4 增量 2：诊断运行抽检双评仲裁 + L4 信号按规则维度汇总。"""
    await _ensure_schema()
    password = "password123"
    suffix = uuid4().hex[:8]

    def _user(name: str, role: str) -> User:
        return User(
            username=f"{name}_{suffix}",
            hashed_password=bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode(),
            full_name=f"WP2.4 {name}",
            role=role,
            is_active=True,
        )

    teacher = _user("wp24_teacher", "teacher")
    reviewer_a = _user("wp24_rev_a", "reviewer")
    reviewer_b = _user("wp24_rev_b", "reviewer")
    arbitrator = _user("wp24_arb", "reviewer")
    async with AsyncSessionLocal() as db:
        db.add_all([teacher, reviewer_a, reviewer_b, arbitrator])
        await _attach_pilot_org(db, teacher, reviewer_a, reviewer_b, arbitrator)
        await db.commit()
        for row in (teacher, reviewer_a, reviewer_b, arbitrator):
            await db.refresh(row)
        user_ids = [teacher.id, reviewer_a.id, reviewer_b.id, arbitrator.id]
        teacher_id = teacher.id

    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:

            async def _login(username: str) -> dict[str, str]:
                response = await client.post(
                    "/api/auth/login", json={"username": username, "password": password}
                )
                return {"Authorization": f"Bearer {response.json()['access_token']}"}

            teacher_headers = await _login(teacher.username)
            rev_a_headers = await _login(reviewer_a.username)
            rev_b_headers = await _login(reviewer_b.username)
            arb_headers = await _login(arbitrator.username)

            project = await client.post(
                "/api/workbench/projects",
                json={"title": "WP2.4 抽检闭环", "stage": "高中", "course_type": "议题式"},
                headers=teacher_headers,
            )
            project_id = project.json()["id"]
            seeded = await client.post(
                f"/api/workbench/projects/{project_id}/versions",
                json={
                    "source_version": 1,
                    "content": {
                        "alignment_card": {"citations": []},
                        "design_blueprint": {
                            "objectives": ["形成判断"],
                            "evidence": [],
                            "learning_tasks": [],
                        },
                        "lesson_design": {
                            "section_name": "已有教案",
                            "activities": [],
                            "teacher_notes": [],
                            "assessment_evidence": [],
                        },
                    },
                },
                headers=teacher_headers,
            )
            source_version = seeded.json()["version_number"]
            preview = await client.get(
                f"/api/workbench/projects/{project_id}/diagnosis/structure",
                headers=teacher_headers,
            )
            confirmed = await client.post(
                f"/api/workbench/projects/{project_id}/diagnosis/structure",
                json={"source_version": source_version, "nodes": preview.json()},
                headers=teacher_headers,
            )
            source_version = confirmed.json()["version_number"]
            diagnosis = await client.post(
                "/api/workbench/skills/diagnose-artifact",
                json={"project_id": project_id, "source_version": source_version},
                headers=teacher_headers,
            )
            assert diagnosis.status_code == 200
            diagnose_run_id = diagnosis.json()["skill_run_id"]
            source_version = diagnosis.json()["version_number"]
            for item_id, action, edited in (
                ("basis_traceability", "accept", None),
                ("objective_evidence_alignment", "edit", "补充编辑后的证据。"),
                ("task_feasibility", "request_expert", None),
            ):
                decision = await client.post(
                    f"/api/workbench/projects/{project_id}/diagnosis/items/{item_id}/decision",
                    json={
                        "source_version": source_version,
                        "action": action,
                        "edited_suggestion": edited,
                    },
                    headers=teacher_headers,
                )
                assert decision.status_code == 200
                source_version = decision.json()["version_number"]

            # 教师无权操作抽检队列与全局汇总
            forbidden = await client.get(
                "/api/workbench/spot-checks", headers=teacher_headers
            )
            assert forbidden.status_code == 403
            forbidden_summary = await client.get(
                "/api/workbench/signals/l4-summary", headers=teacher_headers
            )
            assert forbidden_summary.status_code == 403

            sampled = await client.post(
                "/api/workbench/spot-checks/sample",
                json={"skill_id": "skill.diagnose_artifact", "sample_size": 20},
                headers=rev_a_headers,
            )
            assert sampled.status_code == 201
            sampled_items = sampled.json()["items"]
            assert sampled.json()["disclaimer"]
            item = next(
                row for row in sampled_items if row["skill_run_id"] == diagnose_run_id
            )
            assert item["status"] == "pending"
            assert item["context_snapshot"]["authorized_for_training"] is False
            assert item["context_snapshot"]["release_manifest"]
            item_id = item["id"]

            detail = await client.get(
                f"/api/workbench/spot-checks/{item_id}", headers=rev_b_headers
            )
            assert detail.status_code == 200
            assert detail.json()["skill_run"]["id"] == diagnose_run_id
            assert detail.json()["skill_run"]["output_payload"]

            first = await client.post(
                f"/api/workbench/spot-checks/{item_id}/reviews",
                json={
                    "review_kind": "independent",
                    "verdict": "confirmed",
                    "issue_tags": [],
                    "rationale": "三维证据齐全，结论成立。",
                },
                headers=rev_a_headers,
            )
            assert first.status_code == 201
            duplicate = await client.post(
                f"/api/workbench/spot-checks/{item_id}/reviews",
                json={
                    "review_kind": "independent",
                    "verdict": "confirmed",
                    "issue_tags": [],
                    "rationale": "重复提交应被拒绝。",
                },
                headers=rev_a_headers,
            )
            assert duplicate.status_code == 409
            second = await client.post(
                f"/api/workbench/spot-checks/{item_id}/reviews",
                json={
                    "review_kind": "independent",
                    "verdict": "needs_adjustment",
                    "issue_tags": ["evidence_gap"],
                    "rubric_feedback": "证据维度建议补充分学段口径。",
                    "rationale": "证据链不完整。",
                },
                headers=rev_b_headers,
            )
            assert second.status_code == 201
            queue = await client.get(
                "/api/workbench/spot-checks?status_filter=disputed", headers=rev_a_headers
            )
            assert any(row["id"] == item_id for row in queue.json()["items"])
            not_third = await client.post(
                f"/api/workbench/spot-checks/{item_id}/reviews",
                json={
                    "review_kind": "arbitration",
                    "verdict": "needs_adjustment",
                    "issue_tags": ["evidence_gap"],
                    "rationale": "参与过独立复核，不能仲裁。",
                },
                headers=rev_a_headers,
            )
            assert not_third.status_code == 409
            arbitration = await client.post(
                f"/api/workbench/spot-checks/{item_id}/reviews",
                json={
                    "review_kind": "arbitration",
                    "verdict": "needs_adjustment",
                    "issue_tags": ["evidence_gap"],
                    "rubric_feedback": "维持复核 B 意见，规则字典补充证据口径。",
                    "rationale": "仲裁认定证据不足。",
                },
                headers=arb_headers,
            )
            assert arbitration.status_code == 201
            resolved = await client.get(
                f"/api/workbench/spot-checks/{item_id}", headers=arb_headers
            )
            assert resolved.json()["item"]["status"] == "arbitrated"
            assert resolved.json()["item"]["resolved_verdict"] == "needs_adjustment"
            assert resolved.json()["item"]["resolved_issue_tags"] == ["evidence_gap"]
            assert len(resolved.json()["reviews"]) == 3

            # 项目级 L4 汇总：教师本人可见，按规则维度聚合三条决定
            summary = await client.get(
                f"/api/workbench/signals/l4-summary?project_id={project_id}",
                headers=teacher_headers,
            )
            assert summary.status_code == 200
            body = summary.json()
            assert body["scope"] == "project"
            assert body["signal_level"] == "L4"
            assert body["authorized_for_training"] is False
            assert body["total_signals"] == 3
            by_dimension = {row["dimension"]: row for row in body["dimensions"]}
            assert by_dimension["依据可追溯"]["actions"]["accept"] == 1
            assert by_dimension["目标—证据一致"]["actions"]["edit"] == 1
            assert by_dimension["任务可实施"]["actions"]["request_expert"] == 1

            global_summary = await client.get(
                "/api/workbench/signals/l4-summary", headers=rev_a_headers
            )
            assert global_summary.status_code == 200
            assert global_summary.json()["scope"] == "global"
            assert global_summary.json()["total_signals"] >= 3
    finally:
        async with AsyncSessionLocal() as db:
            run_ids = select(SkillRun.id).where(SkillRun.user_id.in_(user_ids))
            await db.execute(
                delete(SpotCheckItem).where(SpotCheckItem.skill_run_id.in_(run_ids))
            )
            await db.execute(
                delete(TeachingProject).where(TeachingProject.owner_id == teacher_id)
            )
            await db.execute(delete(User).where(User.id.in_(user_ids)))
            await db.commit()
