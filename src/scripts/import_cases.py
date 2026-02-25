"""主题数据导入脚本。

从 src/cases/*.json 读取主题数据并导入到数据库。
支持去重和更新现有主题。
"""

import asyncio
import json
import sys
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# 添加项目根目录到路径
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from src.apps.api.dependencies import AsyncSessionLocal  # noqa: E402
from src.apps.api.models import Case  # noqa: E402


async def import_case_from_json(db: AsyncSession, json_file: Path) -> None:
    """从 JSON 文件导入单个主题。

    Args:
        db: 数据库会话
        json_file: JSON 文件路径
    """
    with open(json_file, encoding="utf-8") as f:
        data = json.load(f)

    # 查找是否已存在同名主题
    result = await db.execute(select(Case).where(Case.title == data["title"]))
    existing_case = result.scalar_one_or_none()

    if existing_case:
        # 更新现有主题
        existing_case.difficulty = data["difficulty"]
        existing_case.department = data["department"]
        existing_case.context_info = data["context_info"]
        existing_case.core_question = data["core_question"]
        existing_case.scenario_text = data["scenario_text"]
        existing_case.supplementary_info = data["supplementary_info"]
        existing_case.reference_answer = data["reference_answer"]
        existing_case.key_points = data["key_points"]
        existing_case.is_active = True
        existing_case.source = "fixed"
        existing_case.generation_meta = None

        print(f"✓ 更新主题: {data['title']} ({data['difficulty']})")
    else:
        # 创建新主题
        case = Case(
            title=data["title"],
            difficulty=data["difficulty"],
            department=data["department"],
            context_info=data["context_info"],
            core_question=data["core_question"],
            scenario_text=data["scenario_text"],
            supplementary_info=data["supplementary_info"],
            reference_answer=data["reference_answer"],
            key_points=data["key_points"],
            is_active=True,
            source="fixed",
            generation_meta=None,
        )
        db.add(case)
        print(f"✓ 创建主题: {data['title']} ({data['difficulty']})")

    await db.commit()


async def import_all_cases() -> None:
    """导入所有主题。"""
    cases_dir = project_root / "src" / "cases"

    if not cases_dir.exists():
        print(f"✗ 主题目录不存在: {cases_dir}")
        return

    json_files = list(cases_dir.glob("*.json"))

    if not json_files:
        print(f"✗ 未找到主题 JSON 文件: {cases_dir}")
        return

    print("=" * 50)
    print("主题数据导入")
    print("=" * 50)
    print(f"\n找到 {len(json_files)} 个主题文件\n")

    async with AsyncSessionLocal() as db:
        for json_file in sorted(json_files):
            try:
                await import_case_from_json(db, json_file)
            except Exception as e:
                print(f"✗ 导入失败 {json_file.name}: {e}")

    print("\n" + "=" * 50)
    print("导入完成！")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(import_all_cases())
