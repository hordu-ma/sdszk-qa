"""防评分/排名回流的防护测试（开发计划 §16.1、§2.4）。

计划规定本仓全周期不建设教师/学生总分、排名和绩效类产品路径。
本测试断言 API 面（路径、operationId、Schema 字段）与领域模型
（表名、列名）中不出现评分/排名类标识符，防止相关能力悄然回流。
"""

import re
from typing import Any

from src.apps.api.main import app
from src.apps.api.models.base import Base

# 以词元精确匹配，避免误伤 upgrade/grade 学段字段等普通用词
FORBIDDEN_TOKENS = {
    "score",
    "scores",
    "scoring",
    "rank",
    "ranks",
    "ranking",
    "rankings",
    "rating",
    "ratings",
    "leaderboard",
    "kpi",
}


def _tokens(identifier: str) -> set[str]:
    return set(re.findall(r"[a-z]+", identifier.lower()))


def _assert_clean(identifier: str, source: str) -> None:
    hits = _tokens(identifier) & FORBIDDEN_TOKENS
    assert not hits, f"{source} 出现评分/排名类标识符 {hits}: {identifier}"


def _walk_openapi(node: Any, path: str) -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            _assert_clean(str(key), f"OpenAPI {path}")
            if key == "operationId" and isinstance(value, str):
                _assert_clean(value, f"OpenAPI {path}.operationId")
            _walk_openapi(value, f"{path}.{key}")
    elif isinstance(node, list):
        for index, item in enumerate(node):
            _walk_openapi(item, f"{path}[{index}]")


def test_no_scoring_api_paths() -> None:
    for route in app.routes:
        route_path = getattr(route, "path", "")
        _assert_clean(route_path, "API 路由路径")
        _assert_clean(getattr(route, "name", "") or "", f"API 路由函数 {route_path}")


def test_no_scoring_identifiers_in_openapi_schema() -> None:
    _walk_openapi(app.openapi(), "$")


def test_no_scoring_columns_in_domain_models() -> None:
    for table in Base.metadata.tables.values():
        _assert_clean(table.name, "数据表名")
        for column in table.columns:
            _assert_clean(column.name, f"表 {table.name} 列名")
