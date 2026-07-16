"""种子案例数据卫生回归（开发计划 §6.1）。"""

from src.scripts.validate_cases import CASES_DIR, validate_all


def test_seed_cases_exist() -> None:
    assert sorted(CASES_DIR.glob("*.json")), "种子案例目录为空"


def test_seed_cases_consistency() -> None:
    problems = validate_all()
    details = "\n".join(
        f"{filename}: {error}" for filename, errors in problems.items() for error in errors
    )
    assert not problems, f"种子案例存在文件名/内容不一致：\n{details}"
