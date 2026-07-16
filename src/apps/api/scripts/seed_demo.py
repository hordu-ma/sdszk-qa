"""创建 base-spark 演示账号和首个思政主题。"""

import asyncio
import os

import bcrypt
from sqlalchemy import select

from src.apps.api.dependencies import AsyncSessionLocal
from src.apps.api.models import Case, User


async def seed() -> None:
    users = _demo_users()
    async with AsyncSessionLocal() as db:
        for item in users:
            user_result = await db.execute(select(User).where(User.username == item["username"]))
            user = user_result.scalar_one_or_none()
            if user is None:
                user = User(
                    username=item["username"],
                    hashed_password=bcrypt.hashpw(
                        item["password"].encode()[:72], bcrypt.gensalt()
                    ).decode(),
                    full_name=item["full_name"],
                    role=item["role"],
                    is_active=True,
                )
                db.add(user)
            else:
                user.full_name = item["full_name"]
                user.role = item["role"]
                user.is_active = True
        case_result = await db.execute(select(Case).where(Case.title == "高中家国情怀议题式教学"))
        if case_result.scalar_one_or_none() is None:
            db.add(
                Case(
                    title="高中家国情怀议题式教学",
                    difficulty="medium",
                    department="高中",
                    context_info={"grade": "高一", "class_size": 45},
                    core_question="如何围绕家国情怀设计目标、任务和评价证据",
                    scenario_text="阶段 1A 问答兼容验证主题",
                    supplementary_info={"constraints": ["45 分钟"]},
                    reference_answer={"primary": "目标、任务与评价证据保持一致"},
                    key_points=["家国情怀", "议题式教学", "评价证据"],
                    source="fixed",
                    is_active=True,
                )
            )
        await db.commit()
    print("demo users ready: " + ", ".join(item["username"] for item in users))


def _demo_users() -> list[dict[str, str]]:
    shared_password = os.environ["DEMO_PASSWORD"]
    return [
        {
            "username": os.getenv("DEMO_ADMIN_USERNAME", "demo_admin"),
            "password": os.getenv("DEMO_ADMIN_PASSWORD", shared_password),
            "full_name": os.getenv("DEMO_ADMIN_FULL_NAME", "鲁韵验证管理员"),
            "role": "admin",
        },
        {
            "username": os.getenv(
                "DEMO_TEACHER_USERNAME", os.getenv("DEMO_USERNAME", "demo_teacher")
            ),
            "password": os.getenv("DEMO_TEACHER_PASSWORD", shared_password),
            "full_name": os.getenv(
                "DEMO_TEACHER_FULL_NAME", os.getenv("DEMO_FULL_NAME", "鲁韵验证教师")
            ),
            "role": "teacher",
        },
    ]


if __name__ == "__main__":
    asyncio.run(seed())
