---
name: extend-scoring
description: Deprecated. Do not implement session scoring or teacher ranking. Product diagnosis is formative and non-scoring per the development plan.
status: deprecated
---

> **已废弃 / 禁止执行。**  
> 产品原则：教学诊断**不输出教师总分或排名**，不建设 session scoring 模块。  
> 权威依据：`src/docs/2026-luyun-curriculum-pedagogy-development-plan.md`（诊断非评分、非范围清单）。  
> 若任务涉及“评价工具 / 量规 / 形成性评价表”，应走教学成果与诊断 Skills（`diagnose_design` 等）设计，而不是本 skill。

# Extend Scoring（Deprecated）

Do **not** apply this workflow.

## Replacement

1. Read the development plan sections on non-scoring diagnosis and product Skills.
2. For rubrics as **classroom materials**, use teaching-design generation/export Skills.
3. For design quality feedback, use evidence-based diagnosis items (`已建立/部分建立/尚未建立/证据不足`), not total scores.

## Guardrails

- Never add `scoring.py`, teacher leaderboards, or student ideological scoring.
- Never treat Memory signals as performance grades.
