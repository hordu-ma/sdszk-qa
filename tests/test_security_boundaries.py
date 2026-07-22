"""WP2.5 增量 1 集成安全回归：越权、权限隔离、敏感数据与恶意文件 API 面。

跨用户与跨角色访问必须被 403/404 阻断；任何 API 响应不得泄露口令散列；
恶意内容通过上传接口必须被 415 拒绝。
"""

from __future__ import annotations

import io
import zipfile
from uuid import uuid4

import bcrypt
import httpx
import pytest
from sqlalchemy import delete, text

from src.apps.api.dependencies import AsyncSessionLocal, engine
from src.apps.api.main import app
from src.apps.api.models import TeachingProject, User
from src.apps.api.services.model_asset_service import sync_model_assets


async def _ensure_schema() -> None:
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(User.metadata.create_all)
    async with AsyncSessionLocal() as db:
        await sync_model_assets(db)


def _macro_docx() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", "<w:document/>")
        archive.writestr("word/vbaProject.bin", b"macro-payload")
    return buffer.getvalue()


@pytest.mark.integration
@pytest.mark.asyncio(loop_scope="session")
async def test_cross_user_and_role_boundaries(monkeypatch: pytest.MonkeyPatch) -> None:
    await _ensure_schema()
    password = "password123"
    suffix = uuid4().hex[:8]

    def _user(name: str, role: str) -> User:
        return User(
            username=f"{name}_{suffix}",
            hashed_password=bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode(),
            full_name=f"WP2.5 {name}",
            role=role,
            is_active=True,
        )

    teacher_a = _user("sec_teacher_a", "teacher")
    teacher_b = _user("sec_teacher_b", "teacher")
    async with AsyncSessionLocal() as db:
        db.add_all([teacher_a, teacher_b])
        await db.commit()
        await db.refresh(teacher_a)
        await db.refresh(teacher_b)
        user_ids = [teacher_a.id, teacher_b.id]
        teacher_a_id = teacher_a.id

    objects: dict[str, bytes] = {}

    async def _put_object(object_key: str, data: bytes, content_type: str) -> None:
        del content_type
        objects[object_key] = data

    monkeypatch.setattr("src.apps.api.routes.workbench.put_object", _put_object)

    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:

            async def _login(username: str) -> dict[str, str]:
                response = await client.post(
                    "/api/auth/login", json={"username": username, "password": password}
                )
                assert "hashed_password" not in response.text
                return {"Authorization": f"Bearer {response.json()['access_token']}"}

            headers_a = await _login(teacher_a.username)
            headers_b = await _login(teacher_b.username)

            me = await client.get("/api/auth/me", headers=headers_a)
            assert me.status_code == 200
            assert "hashed_password" not in me.text

            project = await client.post(
                "/api/workbench/projects",
                json={"title": "越权边界样板", "stage": "高中", "course_type": "议题式"},
                headers=headers_a,
            )
            project_id = project.json()["id"]
            upload = await client.post(
                f"/api/workbench/projects/{project_id}/documents",
                files={"file": ("basis.md", "# 依据\n正文".encode(), "text/markdown")},
                headers=headers_a,
            )
            assert upload.status_code == 202
            document_id = upload.json()["document"]["id"]
            dataset = await client.post(
                "/api/workbench/evaluation/datasets",
                json={
                    "project_id": project_id,
                    "dataset_key": "sec-boundary",
                    "name": "越权样例集",
                },
                headers=headers_a,
            )
            dataset_id = dataset.json()["id"]

            # 跨用户资源访问一律 403/404
            cross_user_denied = [
                ("GET", f"/api/workbench/projects/{project_id}", None),
                ("GET", f"/api/workbench/projects/{project_id}/versions", None),
                ("GET", f"/api/workbench/projects/{project_id}/documents", None),
                ("GET", f"/api/workbench/projects/{project_id}/diagnosis/structure", None),
                (
                    "POST",
                    f"/api/workbench/projects/{project_id}/versions",
                    {"source_version": 1, "content": {}},
                ),
                (
                    "POST",
                    "/api/workbench/skills/diagnose-artifact",
                    {"project_id": project_id},
                ),
                (
                    "POST",
                    "/api/workbench/evaluation/datasets",
                    {
                        "project_id": project_id,
                        "dataset_key": "sec-hijack",
                        "name": "跨用户创建",
                    },
                ),
                ("POST", f"/api/workbench/evaluation/datasets/{dataset_id}/freeze", None),
                ("POST", f"/api/workbench/evaluation/datasets/{dataset_id}/runs", None),
                ("GET", f"/api/workbench/evaluation/datasets/{dataset_id}/report", None),
                (
                    "GET",
                    f"/api/workbench/signals/l4-summary?project_id={project_id}",
                    None,
                ),
            ]
            for method, url, payload in cross_user_denied:
                response = await client.request(
                    method, url, json=payload, headers=headers_b
                )
                assert response.status_code in {403, 404}, (
                    f"{method} {url} 应拒绝跨用户访问，实际 {response.status_code}"
                )

            # 教师角色不得触达审核/复核/全局信号能力
            teacher_role_denied = [
                (
                    "POST",
                    f"/api/workbench/documents/{document_id}/review",
                    {"review_status": "approved"},
                ),
                (
                    "POST",
                    f"/api/workbench/evaluation/datasets/{dataset_id}/review",
                    {"review_status": "approved", "review_note": "教师不可审核"},
                ),
                ("GET", "/api/workbench/evaluation/review-queue", None),
                ("GET", "/api/workbench/spot-checks", None),
                (
                    "POST",
                    "/api/workbench/spot-checks/sample",
                    {"sample_size": 5},
                ),
                ("GET", "/api/workbench/signals/l4-summary", None),
            ]
            for method, url, payload in teacher_role_denied:
                response = await client.request(
                    method, url, json=payload, headers=headers_a
                )
                assert response.status_code == 403, (
                    f"{method} {url} 应拒绝教师角色，实际 {response.status_code}"
                )

            # 未认证访问被拒绝
            anonymous = await client.get(f"/api/workbench/projects/{project_id}")
            assert anonymous.status_code in {401, 403}

            # 恶意文件通过 API 上传被 415 拒绝
            malicious_uploads = [
                ("evil.docx", b"MZ\x90\x00\x03fakepe", "application/vnd.openxmlformats"),
                ("evil.pdf", b"#!/bin/sh\nrm -rf /", "application/pdf"),
                ("evil.txt", b"text\x00binary", "text/plain"),
                ("macro.docx", _macro_docx(), "application/vnd.openxmlformats"),
            ]
            for name, payload_bytes, content_type in malicious_uploads:
                response = await client.post(
                    f"/api/workbench/projects/{project_id}/documents",
                    files={"file": (name, payload_bytes, content_type)},
                    headers=headers_a,
                )
                assert response.status_code == 415, (
                    f"{name} 应被内容校验拒绝，实际 {response.status_code}"
                )
    finally:
        async with AsyncSessionLocal() as db:
            await db.execute(
                delete(TeachingProject).where(TeachingProject.owner_id == teacher_a_id)
            )
            await db.execute(delete(User).where(User.id.in_(user_ids)))
            await db.commit()
