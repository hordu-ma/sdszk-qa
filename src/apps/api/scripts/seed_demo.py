"""创建 base-spark 演示账号和首个思政主题。"""

import asyncio
import os

import bcrypt
from sqlalchemy import select

from src.apps.api.dependencies import AsyncSessionLocal
from src.apps.api.models import Case, User


async def seed() -> None:
    username = os.environ["DEMO_USERNAME"]
    password = os.environ["DEMO_PASSWORD"]
    full_name = os.getenv("DEMO_FULL_NAME", "鲁韵验证教师")
    async with AsyncSessionLocal() as db:
        user_result = await db.execute(select(User).where(User.username == username))
        user = user_result.scalar_one_or_none()
        if user is None:
            user = User(
                username=username,
                hashed_password=bcrypt.hashpw(password.encode()[:72], bcrypt.gensalt()).decode(),
                full_name=full_name,
                role="admin",
                is_active=True,
            )
            db.add(user)
        else:
            user.role = "admin"
        case_result = await db.execute(
            select(Case).where(Case.title == "高中家国情怀议题式教学")
        )
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
    print(f"demo user ready: {username}")


if __name__ == "__main__":
    asyncio.run(seed())
