"""诊断规则字典 v2（内部版，自助开发优先级 §0.5-4）。

把高中议题式样板的三个工程诊断维度从 handler 内联逻辑抽离为可配置、可扩展的
规则字典。每条规则声明依赖的样板小节、达标判定、可观察证据与改进建议，新增维度
只需注册规则，无需改动诊断编排逻辑。

本模块严守开发计划 §16.1 非评分约束：诊断只产出对齐状态（aligned / needs_attention）
与改进建议，绝不生成分数、排名或绩效指标。规则注册入口 `register_diagnostic_rule`
对评分/排名类标识符做防护拦截，口径与 tests/test_no_scoring_paths.py 一致，
防止评分能力借规则字典悄然回流。
"""

from __future__ import annotations

import re
from collections import OrderedDict
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from src.apps.api.schemas.workbench import DiagnosisItem

# 非评分防护：规则标识与依赖小节键中禁止出现的评分/排名类词元。
# 与 tests/test_no_scoring_paths.py 的 FORBIDDEN_TOKENS 保持同一口径。
FORBIDDEN_RULE_TOKENS = {
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

RULE_STATUS_ALIGNED = "aligned"
RULE_STATUS_ATTENTION = "needs_attention"

SectionData = Mapping[str, object]
SectionMap = Mapping[str, SectionData]


@dataclass(frozen=True)
class DiagnosticRule:
    """单条工程诊断规则。

    predicate 返回 True 记为 aligned；evidence 无论达标与否都给出可观察证据，
    不承载任何数值评分。blocking 为 True 时，needs_attention 会进入 blocking_issues。
    """

    rule_id: str
    dimension: str
    section: str
    predicate: Callable[[SectionData], bool]
    evidence: Callable[[SectionData], str]
    aligned_suggestion: str
    attention_suggestion: str
    blocking: bool = True

    def evaluate(self, sections: SectionMap) -> DiagnosisItem:
        section_data: SectionData = sections.get(self.section) or {}
        ok = bool(self.predicate(section_data))
        return DiagnosisItem(
            dimension=self.dimension,
            status=RULE_STATUS_ALIGNED if ok else RULE_STATUS_ATTENTION,
            evidence=self.evidence(section_data),
            suggestion=self.aligned_suggestion if ok else self.attention_suggestion,
        )


def _forbidden_hits(*values: str) -> set[str]:
    tokens: set[str] = set()
    for value in values:
        tokens |= set(re.findall(r"[a-z]+", value.lower()))
    return tokens & FORBIDDEN_RULE_TOKENS


_RULES: OrderedDict[str, DiagnosticRule] = OrderedDict()


def register_diagnostic_rule(rule: DiagnosticRule) -> DiagnosticRule:
    """注册一条诊断规则；对评分/排名标识符和重复注册做防护拦截。"""
    hits = _forbidden_hits(rule.rule_id, rule.section)
    if hits:
        raise ValueError(f"诊断规则禁止评分/排名类标识符: {sorted(hits)}")
    if rule.rule_id in _RULES:
        raise ValueError(f"诊断规则重复注册: {rule.rule_id}")
    _RULES[rule.rule_id] = rule
    return rule


def diagnostic_rules() -> tuple[DiagnosticRule, ...]:
    """按注册顺序返回当前规则字典。"""
    return tuple(_RULES.values())


def evaluate_diagnostic_rules(sections: SectionMap) -> tuple[list[DiagnosisItem], list[str]]:
    """按规则字典顺序评估样板小节，返回诊断项与阻断维度列表。"""
    items: list[DiagnosisItem] = []
    blocking: list[str] = []
    for rule in _RULES.values():
        item = rule.evaluate(sections)
        items.append(item)
        if item.status == RULE_STATUS_ATTENTION and rule.blocking:
            blocking.append(rule.dimension)
    return items, blocking


def _as_list(section: SectionData, key: str) -> list:
    value = section.get(key)
    return list(value) if isinstance(value, list) else []


# 默认工程诊断维度（阶段 1 纵向样板 v0 的三维，迁移自 diagnose_artifact_handler 内联逻辑）。
register_diagnostic_rule(
    DiagnosticRule(
        rule_id="basis_traceability",
        dimension="依据可追溯",
        section="alignment_card",
        predicate=lambda section: bool(_as_list(section, "citations")),
        evidence=lambda section: f"引用片段 {len(_as_list(section, 'citations'))} 条",
        aligned_suggestion="保留引用卡并在导出前复核有效期",
        attention_suggestion="补充并审核权威资料后重新运行对齐卡",
    )
)
register_diagnostic_rule(
    DiagnosticRule(
        rule_id="objective_evidence_alignment",
        dimension="目标—证据一致",
        section="design_blueprint",
        predicate=lambda section: bool(_as_list(section, "objectives"))
        and bool(_as_list(section, "evidence")),
        evidence=lambda section: (
            f"目标 {len(_as_list(section, 'objectives'))} 项 / "
            f"证据 {len(_as_list(section, 'evidence'))} 项"
        ),
        aligned_suggestion="保持目标与证据一一对应",
        attention_suggestion="逐项目标补充对应的可观察证据",
    )
)
register_diagnostic_rule(
    DiagnosticRule(
        rule_id="task_feasibility",
        dimension="任务可实施",
        section="lesson_design",
        predicate=lambda section: bool(_as_list(section, "activities")),
        evidence=lambda section: f"课时活动 {len(_as_list(section, 'activities'))} 个",
        aligned_suggestion="试教后记录调整原因",
        attention_suggestion="补充分工、时长和教师支架",
    )
)
