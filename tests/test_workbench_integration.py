from __future__ import annotations

from uuid import uuid4

import bcrypt
import httpx
import pytest
from sqlalchemy import delete, select, text

from src.apps.api.dependencies import AsyncSessionLocal, engine
from src.apps.api.main import app
from src.apps.api.models import (
    MemoryInjectionAudit,
    SkillRun,
    TeachingProject,
    User,
)
from src.apps.api.services.model_asset_service import sync_model_assets


async def _ensure_schema() -> None:
    """建表并启用库内检索所需扩展（CI 全新数据库场景）。"""
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(User.metadata.create_all)
    async with AsyncSessionLocal() as db:
        await sync_model_assets(db)


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
    async with AsyncSessionLocal() as db:
        db.add(user)
        await db.commit()
        await db.refresh(user)
        user_id = user.id

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
            assert retrieval.json()["skill_version"] == "1.1.0"
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
                "skill.alignment_card",
                "skill.design_blueprint",
                "skill.generate_section",
                "skill.diagnose_artifact",
                "skill.export_artifact",
            ]
            assert skills.json()[0]["status"] == "enabled"

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
            assert len(export.json()["pinned_items"]) == 1

            cleared = await client.post("/api/workbench/memory/clear", headers=headers)
            assert cleared.json() == {
                "cleared_preference": True,
                "cleared_class_profiles": 1,
                "cleared_pinned_items": 1,
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
