"""种子案例一致性校验脚本。

校验 src/cases/*.json 的文件名主题、标题、学段和必填字段一致性，
防止再次出现文件名与内容错位（开发计划 §6.1 数据卫生要求）。

用法：
    uv run python src/scripts/validate_cases.py
返回码：0 表示全部通过；1 表示存在不一致。
"""

import json
import re
import sys
from pathlib import Path

CASES_DIR = Path(__file__).resolve().parents[2] / "src" / "cases"

FILENAME_PATTERN = re.compile(r"^case_(\d{3})_([a-z_]+)\.json$")

# 文件名主题 slug 必须与标题中的主题关键词一致
SLUG_TITLE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "patriotism": ("家国情怀", "爱国"),
    "rule_of_law": ("法治",),
    "labor_education": ("劳动",),
    "national_security": ("国家安全",),
    "traditional_culture": ("传统文化",),
    "integration": ("一体化",),
    "research": ("教研", "同课异构"),
    "assessment": ("评价",),
}

# 标题学段前缀必须与 department 字段一致
TITLE_PREFIX_DEPARTMENT: dict[str, str] = {
    "小学思政": "小学",
    "初中思政": "初中",
    "高中思政": "高中",
    "大学思政": "大学",
    "大中小学思政一体化": "一体化",
    "思政教研": "教研",
    "思政课堂": "通用",
}

REQUIRED_FIELDS: dict[str, type] = {
    "title": str,
    "difficulty": str,
    "department": str,
    "context_info": dict,
    "core_question": str,
    "scenario_text": str,
    "supplementary_info": dict,
    "reference_answer": dict,
    "key_points": list,
}

ALLOWED_DIFFICULTIES = {"easy", "medium", "hard"}


def validate_case(path: Path) -> list[str]:
    """校验单个案例文件，返回问题列表（空列表表示通过）。"""
    errors: list[str] = []
    match = FILENAME_PATTERN.match(path.name)
    if match is None:
        return [f"文件名不符合 case_NNN_slug.json 规范: {path.name}"]
    slug = match.group(2)

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        return [f"JSON 解析失败: {exc}"]

    for field, expected_type in REQUIRED_FIELDS.items():
        value = data.get(field)
        if not isinstance(value, expected_type) or (
            isinstance(value, str | dict | list) and not value
        ):
            errors.append(f"字段 {field} 缺失、类型错误或为空")
    if errors:
        return errors

    title: str = data["title"]

    keywords = SLUG_TITLE_KEYWORDS.get(slug)
    if keywords is None:
        errors.append(f"未登记的主题 slug: {slug}（新增主题需在校验脚本登记关键词）")
    elif not any(keyword in title for keyword in keywords):
        errors.append(f"文件名主题 {slug}（期望关键词 {'/'.join(keywords)}）与标题不符: {title}")

    if data["difficulty"] not in ALLOWED_DIFFICULTIES:
        errors.append(f"difficulty 取值非法: {data['difficulty']}")

    prefix = title.split("：", 1)[0]
    expected_department = TITLE_PREFIX_DEPARTMENT.get(prefix)
    if expected_department is None:
        errors.append(f"标题前缀未登记: {prefix}（新增前缀需在校验脚本登记学段映射）")
    elif data["department"] != expected_department:
        errors.append(
            f"标题前缀 {prefix} 对应学段 {expected_department}，"
            f"与 department 字段 {data['department']} 不一致"
        )
    return errors


def validate_all(cases_dir: Path = CASES_DIR) -> dict[str, list[str]]:
    """校验目录下全部案例，返回 {文件名: 问题列表}，只含有问题的文件。"""
    problems: dict[str, list[str]] = {}
    files = sorted(cases_dir.glob("*.json"))
    if not files:
        return {str(cases_dir): ["未找到任何案例 JSON 文件"]}
    for path in files:
        errors = validate_case(path)
        if errors:
            problems[path.name] = errors
    return problems


def main() -> int:
    problems = validate_all()
    total = len(sorted(CASES_DIR.glob("*.json")))
    if not problems:
        print(f"✓ {total} 个种子案例全部通过一致性校验")
        return 0
    for filename, errors in problems.items():
        for error in errors:
            print(f"✗ {filename}: {error}")
    print(f"\n共 {len(problems)} 个文件存在问题（总计 {total} 个）")
    return 1


if __name__ == "__main__":
    sys.exit(main())
