# 交互契约（DOM Contract）

`scripts/validate_diagram.py` 按这份契约工作。偏离契约就得同步改脚本，否则自检会假绿。

目录：
- [1. 视图与路由](#1-视图与路由)
- [2. 画布与两级缩放](#2-画布与两级缩放)
- [3. 边的画法](#3-边的画法)
- [4. 文字替代与打印](#4-文字替代与打印)
- [5. 可达性](#5-可达性)
- [6. 主题](#6-主题)

## 1. 视图与路由

```html
<section class="view" id="v-all" data-name="整张图" data-back="#/" hidden> … </section>
```

- 视图 id 一律 `v-<slug>`；首屏视图 id 固定 `v-home`，对应 hash `#/`
- hash ↔ id 的映射只有一条规则：`#/a/b` ⇄ `v-a-b`，`#/n/<节点id>` ⇄ `v-n-<节点id>`
  （脚本用 `id[2:].replace('-','/')` 反推 hash，**节点 id 里不要出现 `-`**，否则深链解不回来）
- 任一时刻只有一个 `.view` 不带 `hidden`
- 面包屑 `<nav id="crumbs">`，用 `textContent` 逐段拼，**不要用 `innerHTML`**
- 浏览器后退必须能 zoom out（用 hash 路由天然获得）

自检会报两类错：`missing_href_targets`（链到不存在的视图）、`unreachable_views`（没有任何入口的视图）。

## 2. 画布与两级缩放

```html
<div class="gwrap" data-init="fit|read">
  <div class="gzoo"><button data-z="out">−</button><button data-z="in">+</button>
       <button data-z="fit">适应宽度</button><button data-z="one">100%</button>
       <span data-zout>20%</span></div>
  <div class="gscroll" tabindex="0" role="region" aria-label="流程图画布，可缩放平移">
    <div class="canvas" style="width:Wpx;height:Hpx">
      <div class="cinner" style="width:Wpx;height:Hpx"> <svg/> + <a class="gnode"/> </div>
    </div>
  </div>
  <details class="galt"><summary>按层阅读（文字替代，共 N 层、M 个节点）</summary><table>…</table></details>
</div>
```

三层不能省：`.gscroll` 负责滚动条；`.canvas` 占**缩放后**的尺寸（决定溢出与滚动范围）；
`.cinner` 是 `transform: scale()` 的对象。**只缩 `.cinner` 不改 `.canvas` 宽度 → 右侧留大片空白或裁掉尾部。**

缩放档位用离散阶梯，别连续乘：

```js
const ZS = [0.2, 0.25, 0.3, 0.4, 0.5, 0.62, 0.75, 0.9, 1, 1.15, 1.3, 1.5, 1.75, 2];
```

- 初始档：画布宽 > 2400px 的图**不要 fit**（fit 会落到 20%，读不了），落到 ~0.62 并显示一行提示：
  「这是一张地图，不是一份清单——先看清分区，再点进去」。`data-init="read"` 就是这个开关。
- `+` / `-` / `0`（回 fit）在 `.gscroll` 获得焦点时可用，按钮本身可 Tab 到
- `Ctrl/⌘ + 滚轮` 缩放，普通滚轮平移；`prefers-reduced-motion` 下去掉过渡

## 3. 边的画法

- 一条边一个 `<path>`，水平三次贝塞尔（`dag_layout.edge_path`）
- 边标签用 `paint-order: stroke` + 与背景同色的 `stroke` 描边，否则压在线上读不出
- 分支条件（if-else 的 case）标在**出边**上，并写明判定顺序（多数引擎是「首个命中即停止」）
- 同层交叉数 > 0 就别硬扛，折叠回边或拆层

## 4. 文字替代与打印

图的语义必须在**没有颜色、没有动画、没有 JS** 时仍然可读：

- 每个画布配一个 `<details class="galt">` 按层阅读表：`第 N 层 → 节点链接`
- 节点卡片用 `<a class="gnode">`，文字在 `.gn-t`（标题）/ `.gn-m`（元信息）里，是真实文本
- `@media print`：展开全部视图、打开所有 `details`、隐藏工具条——打印出来是一份可归档的文档

## 5. 可达性

- 视图切换后把焦点交给该视图的 `<h1>`（`tabindex="-1"`），但**首屏不要自动聚焦**（会在第一次绘制时留下焦点环）
- 每次切视图写 `<div id="announce" role="status" aria-live="polite">`，内容如「整张图：已打开」
- 键盘路径完整：Tab 到节点 → Enter 进详情 → Esc 回上级
- 颜色只作强调，状态差异同时有文字（如「无写入方」「无读取方」用徽标 + 文案）
- 深浅两套主题下正文对比度都要过 4.5:1（自检截图看一遍，别只看 CSS 变量名）

## 6. 主题

```html
<html data-theme="light|dark"> <button id="theme" aria-pressed="true">深色</button>
```

选择写 `localStorage`；`data-theme` 挂在根元素上，所有颜色走 CSS 变量；
SVG 里的描边/填充也用 `var(--…)`，否则深色模式下边会消失。
