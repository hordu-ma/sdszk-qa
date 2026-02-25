# SKILLS

可触发的 Codex skills 集合。

## 目录结构

```
SKILLS/
  catalog/          # 主题索引（backend/frontend/infra/testing）
  skills/<name>/    # 独立 skill
    SKILL.md        # 工作流 + guardrails + references 引用
    references/     # 领域参考文档
    agents/         # UI 元数据
  metadata/         # 版本与归属信息
```

## 使用

1. 在 `catalog/*.yaml` 选择 skill。
2. 触发 skill：`$add-api-endpoint`。
3. 按 SKILL.md 工作流执行，按需读取 `references/`。

## 维护

- 新增能力 → 新增独立 skill，不堆叠在通用文档。
- 变更 → 更新对应 SKILL.md 与 references/。
- frontmatter `name` 与目录名保持一致。

## 部署口径

- 生产部署统一手册：`src/infra/README.md`
