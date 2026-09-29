# drilldown-diagram

把**机器可读的源**（YAML / DSL / JSON / AST）变成**读者能自己导航的模型**——
宏观一张图、分组页、单节点详情页，hash 深链可贴进工单或评审。

## 什么时候用

- 真源里有几十到上百个节点（Dify DSL / CI 流水线 / K8s manifest / 调用图 / 状态机 / 消息流）
- 需要让读者能点进节点看细节，再退出来回到原位置
- 数字必须可信（节点数 / 边数 / 行号区间不能手写）
- 凭证必须脱敏（API key / token / 内部 URL 不能出现在产物里）

## 什么时候不要用

| 场景 | 用什么 |
|------|--------|
| ≤ 15 个元素，一屏能说清 | [effective-html/skills/html-diagram](https://github.com/plannotator/effective-html/tree/main/skills/html-diagram) 静态图，或直接写散文 |
| 一次性海报 / 配图 | [effective-html/skills/design-artifact](https://github.com/plannotator/effective-html/tree/main/skills/design-artifact) 或 [html-wireframe](https://github.com/plannotator/effective-html/tree/main/skills/html-wireframe) |
| 解释一个概念 / 思维导图 | [effective-html/skills/design-artifact](https://github.com/plannotator/effective-html/tree/main/skills/design-artifact) 或 [html](https://github.com/plannotator/effective-html/tree/main/skills/html) |

命中以下任一条才继续：节点数 ≥ 30、有 ≥ 2 层展开需求、结论要靠计数撑住、需要深链贴进工单。

## 产物

- **单文件 HTML**：内联 CSS/JS，浏览器直接打开，无构建、无服务器、无外部依赖
- **三层视图**：宏观 → 分组 → 单节点，Esc 与面包屑 zoom out
- **hash 深链**：`<file>.html#node=<id>` 直接定位，可分享
- **计数可信**：节点数、边数、行号区间全部由脚本从真源算出并注入

## IRON LAW

> 图里不允许出现手写的数字。

本 skill 的起点事故就是文档里写"53 节点 / 62 边"，真源实际是 52 / 63。手写数字一定会漂移。

## 仓库结构

```
.
├── SKILL.md                    # Agent 入口：能力描述 + 工作流
├── references/
│   ├── data-discipline.md      # 数据纪律：口径、脱敏、复算性
│   ├── interaction-spec.md     # 交互契约：DOM、键盘、hash 路由（脚本按此自检）
│   └── pitfalls.md             # 18 个真实坑 + 4 个安全坑（症状→根因→修法）
└── scripts/
    ├── dag_layout.py           # 分层 DAG 布局
    ├── leak_scan.py            # 脱敏扫描（密钥、token、内部 URL）
    └── validate_diagram.py     # 交付前自检（按 interaction-spec 跑）
```

## 使用

在 Claude Code / Codex / OpenCode 里：

> "用 drilldown-diagram 把 `<path/to/source.yaml>` 可视化"

Agent 自动加载 `SKILL.md` 并按 8 步工作流执行：锁真源 → 解析 → 脱敏 → 布局 → 渲染 → 三宽度自检 → 复现性检查 → 登记。

## 相关

- [plannotator/effective-html](https://github.com/plannotator/effective-html) — 上游通用 HTML artifacts 约定来源（`html` / `html-diagram` / `design-artifact` / `html-wireframe` / `html-prototype` / `html-plan`）。本 skill 沿用其「单文件、内联、无构建、无外部服务」约定
- [VastFuture Skill Hub](https://github.com/VastFuture/vast-skill-hub) — 组织索引

## 依赖

**零组织内私有依赖**。运行时只需要 Python 3（执行 `scripts/`）和现代浏览器（打开产物 HTML）。
不依赖任何 vast-* / 私有 skill——所有引用都指向公开上游 `plannotator/effective-html`。

---

License: MIT
