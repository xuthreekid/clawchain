---
name: skill-creator
description: 创建或更新 Agent 技能。当需要设计、结构化或打包技能（含脚本、参考文档、资源）时使用。
---

# Skill Creator

本技能指导你创建有效的 Agent 技能。

## 关于技能

技能是模块化、自包含的能力包，通过提供专业知识、工作流和工具来扩展 Agent 能力。可将其视为特定领域或任务的「入门指南」。

### 技能结构

每个技能由必需的 SKILL.md 和可选资源组成：

```
skills/
└── 技能名/
    ├── SKILL.md (必需)
    │   ├── YAML frontmatter: name, description
    │   └── Markdown 正文
    └── 可选资源: scripts/, references/, assets/
```

### SKILL.md 格式

- **Frontmatter**：必须包含 `name` 和 `description`
- **Body**：技能使用说明，仅在技能被触发后加载

示例：

```markdown
---
name: my-skill
description: 简短描述技能用途及何时使用
---

# 技能名称

## 使用步骤
1. ...
2. ...
```

### 创建新技能

1. 在 `skills/` 下创建新目录，如 `skills/my-skill/`
2. 使用 `write` 工具创建 `skills/my-skill/SKILL.md`
3. 写入 frontmatter 和正文
4. 技能会在下次对话时自动被扫描并加入 SKILLS_SNAPSHOT

### 命名规范

- 使用小写字母、数字和连字符
- 如 "计划模式" → `plan-mode`
- 目录名与技能名一致

### 设计原则

- **简洁**：只添加 Agent 真正需要的信息
- **渐进披露**：核心说明在 SKILL.md，详细内容放 references/
- **可复用**：脚本放 scripts/，模板放 assets/
