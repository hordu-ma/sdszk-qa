"""用户数据同步脚本。

从 CSV 文件或模拟数据导入用户到数据库。
支持初始化测试用户和从外部系统同步。
"""

import asyncio
import csv
import sys
from pathlib import Path

import bcrypt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# 添加项目根目录到路径
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from src.apps.api.dependencies import AsyncSessionLocal  # noqa: E402
from src.apps.api.models import User  # noqa: E402


def hash_password(password: str) -> str:
    """哈希密码。

    Args:
        password: 明文密码

    Returns:
        密码哈希
    """
    # bcrypt 限制密码最大 72 字节
    password_bytes = password.encode("utf-8")[:72]
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode("utf-8")


async def create_or_update_user(
    db: AsyncSession,
    username: str,
    password: str,
    full_name: str,
    role: str,
    external_user_id: str | None = None,
) -> User:
    """创建或更新用户。

    Args:
        db: 数据库会话
        username: 用户名
        password: 明文密码
        full_name: 姓名
        role: 角色（student/teacher/reviewer/admin）
        external_user_id: 外部系统用户ID

    Returns:
        用户对象
    """
    # 查找现有用户
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()

    hashed_password = hash_password(password)

    if user:
        # 更新现有用户
        user.hashed_password = hashed_password
        user.full_name = full_name
        user.role = role
        user.is_active = True
        if external_user_id:
            user.external_user_id = external_user_id
        print(f"✓ 更新用户: {username} ({full_name}) - {role}")
    else:
        # 创建新用户
        user = User(
            username=username,
            hashed_password=hashed_password,
            full_name=full_name,
            role=role,
            is_active=True,
            external_user_id=external_user_id,
        )
        db.add(user)
        print(f"✓ 创建用户: {username} ({full_name}) - {role}")

    await db.commit()
    await db.refresh(user)
    return user


async def sync_from_csv(csv_file: Path) -> None:
    """从 CSV 文件同步用户。

    CSV 格式：username,password,full_name,role,external_user_id
    """
    async with AsyncSessionLocal() as db:
        with open(csv_file, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                await create_or_update_user(
                    db,
                    username=row["username"],
                    password=row["password"],
                    full_name=row["full_name"],
                    role=row["role"],
                    external_user_id=row.get("external_user_id"),
                )


async def create_demo_users() -> None:
    """创建演示用户。"""
    demo_users = [
        {
            "username": "student1",
            "password": "password123",
            "full_name": "张三",
            "role": "student",
            "external_user_id": "EXT001",
        },
        {
            "username": "student2",
            "password": "password123",
            "full_name": "李四",
            "role": "student",
            "external_user_id": "EXT002",
        },
        {
            "username": "teacher1",
            "password": "password123",
            "full_name": "王老师",
            "role": "teacher",
            "external_user_id": "EXT003",
        },
        {
            "username": "admin",
            "password": "admin123",
            "full_name": "系统管理员",
            "role": "admin",
            "external_user_id": "EXT999",
        },
    ]

    async with AsyncSessionLocal() as db:
        for user_data in demo_users:
            await create_or_update_user(db, **user_data)


async def main() -> None:
    """主函数。"""
    print("=" * 50)
    print("用户数据同步")
    print("=" * 50)

    if len(sys.argv) > 1:
        # 从 CSV 文件导入
        csv_file = Path(sys.argv[1])
        if not csv_file.exists():
            print(f"✗ 文件不存在: {csv_file}")
            sys.exit(1)

        print(f"\n从 CSV 文件导入: {csv_file}")
        await sync_from_csv(csv_file)
    else:
        # 创建演示用户
        print("\n创建演示用户...")
        await create_demo_users()

    print("\n" + "=" * 50)
    print("同步完成！")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
