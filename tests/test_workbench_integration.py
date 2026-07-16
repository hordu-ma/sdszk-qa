from __future__ import annotations

from uuid import uuid4

import bcrypt
import httpx
import pytest
from sqlalchemy import delete

from src.apps.api.dependencies import AsyncSessionLocal, engine
from src.apps.api.main import app
from src.apps.api.models import TeachingProject, User


@pytest.mark.integration
@pytest.mark.asyncio(loop_scope="session")
async def test_project_upload_retrieve_and_task_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(User.metadata.create_all)

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

            review = await client.post(
                f"/api/workbench/documents/{documents.json()[0]['id']}/review",
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
            assert retrieval.json()["citations"][0]["filename"] == "basis.md"

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
    async with engine.begin() as conn:
        await conn.run_sync(User.metadata.create_all)

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
