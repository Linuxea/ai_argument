# 前端重构设计：中式水墨辩论场（The Salon → 水墨沙龙）

- **日期**: 2026-06-22
- **范围**: `static/` 前端视觉层 + 4 处颜色漂移修复
- **方向**: 中式水墨辩论场（宣纸 / 墨色 / 朱砂印章 / 水墨氤氲）
- **不动**: 后端、PydanticAI 层、SSE 协议、`renderer.js` 的 DOM 类名契约、`markdown.js` 的 XSS 防护

---

## 1. 设计理念

The Salon 的本质是「文人雅集 / 诸子论辩」。当前「暖色羊皮纸 + Merriweather 拉丁衬线 + 金色」是一套**西方沙龙**读法；本设计把它改写成**中式水墨辩论场**：宣纸为底，墨色浓淡为骨，朱砂印章为签名，水墨氤氲为气韵。

四个视觉锚点：

| 锚点 | 含义 | 落点 |
|------|------|------|
| **宣纸** | 温润米黄底，极淡纤维肌理 | `--bg-*` 全系 + `.chat-area` 纹理 |
| **墨色** | 焦/浓/重/淡/清五色墨阶，主 accent = 焦墨 | `--ink-*` + 通用 accent（替代 gold） |
| **朱砂** | 唯一高饱和色，**仅作"印章/签名"语义**，不作通用 accent（避免与反方红撞色） | 品牌印记、辩手头像方印、@提及、blockquote、搜索高亮 |
| **水墨氤氲** | 极淡墨色径向晕染 | `.chat-area::before` 替代现有 gold/sage 光晕 |

**为什么朱砂不作通用 accent**：presets 里反方辩手 color 已是红（`#e74c3c`），若主题主色也用红，反方 sender 名 / 头像会与品牌朱砂混作一团。因此：**通用交互 accent = 焦墨（沉稳近黑）**，朱砂仅用于「印记/落款」类静态签名元素。这也正好对应书法传统——墨为主，朱印为点睛。

---

## 2. 配色系统（`tokens.css` 整体重写）

### 2.1 亮色（宣纸 · 日谈）

| Token | 旧值 (gold/parchment) | 新值 (ink/xuan) | 语义 |
|-------|------|------|------|
| `--bg-base` | `#f5f1ea` | `#f2ecdf` | 生宣米黄（略偏暖黄） |
| `--bg-surface` | `#faf8f4` | `#faf5ea` | 熟宣（侧栏/header 底） |
| `--bg-elevated` | `#ffffff` | `#fffdf6` | 纯白宣（卡片/气泡） |
| `--bg-card` | `#ffffff` | `#fffdf6` | 同上 |
| `--bg-input` | `#f0ece4` | `#ece4d2` | 旧帛（输入框/skeleton 底） |
| `--bg-overlay` | `rgba(26,23,20,.45)` | `rgba(28,24,18,.5)` | 遮罩（略加暖） |
| `--border` | `#d4c8b1` | `#d9ccb2` | 旧帛边 |
| `--border-hover` | `#c0a0a8` | `#b8a17e` | 墨褐 |
| `--border-strong` | `#a89270` | `#9a8a6c` | 浓墨褐 |
| `--ink` | `#1a1714` | `#1d1a16` | 焦墨（近黑暖） |
| `--ink-soft` | `#4a4338` | `#3f3830` | 浓墨 |
| `--ink-muted` | `#7a6f5d` | `#8a7d68` | 淡墨 |

### 2.2 强调色（语义重映射，非 1:1 换值）

| Token | 旧语义 | 新语义 | 新值 |
|-------|--------|--------|------|
| `--gold` | 主 accent（金） | **主 accent = 焦墨** | `#2b2620` |
| `--gold-dim` | 金深 | 焦墨深（hover/active） | `#13100c` |
| `--gold-glow` | 金辉 | 焦墨淡晕（focus ring / soft bg） | `rgba(43,38,32,.12)` |
| `--on-accent`（**新增**） | — | 坐在 `--gold` 填充上的文字色（亮=白） | `#ffffff` |
| `--cinnabar`（**新增**） | — | 朱砂（印章专用） | `#b8413a` |
| `--cinnabar-dim`（新增） | — | 朱砂深 | `#9a3329` |
| `--cinnabar-glow`（新增） | — | 朱砂淡晕 | `rgba(184,65,58,.12)` |
| `--sage` | 鼠尾草（裁判） | 松烟青（裁判，语义不变） | `#5a6e50`（保留，微调 `#55704c`） |
| `--navy` | 海军蓝（用户/下载） | 花青墨蓝（语义不变） | `#3e5260`（保留） |
| `--rose` | 玫红（danger/断连） | 胭脂（语义不变） | `#b85450`（保留） |

> **Token 别名策略**：保留 `--gold*` 变量名（指向焦墨值），避免改动所有引用 `var(--gold)` 的组件文件；新增 `--cinnabar*` 给印章专用位。这样改动集中在 `tokens.css` + 少数需要朱砂的组件规则。

### 2.3 暗色（松烟 · 夜谈）

当前暗色是冷灰蓝。改为「松烟墨」暖调暗：

| Token | 旧暗值 | 新暗值（松烟） |
|-------|------|------|
| `--bg-base` | `#0f1014` | `#15110c`（松烟暖黑） |
| `--bg-surface` | `#181820` | `#1d1813` |
| `--bg-elevated` | `#22232e` | `#26201a` |
| `--bg-card` | `#282935` | `#2a231d` |
| `--bg-input` | `#1d1e28` | `#1f1a14` |
| `--ink` | `#ebe6dc` | `#ece4d4`（米白） |
| `--ink-soft` | `#c4bdae` | `#c8bca4` |
| `--ink-muted` | `#8e8675` | `#968871` |
| `--gold`(焦墨) | `#d4a040`(亮金) | `#d8cdb6`（月白，暗底下"焦墨"反转成浅） |
| `--gold-dim` | — | `#c2b69e`（更深月白，hover 用） |
| `--on-accent`（**新增**） | — | `#1d1a16`（墨字，坐在月白 accent 上） |
| `--cinnabar` | — | `#d65b54`（暗底提亮的朱砂） |
| `--sage` | `#7eb070` | `#82b074` |
| `--navy` | `#7da0b2` | `#82a6b8` |

> 暗色下「焦墨 accent」语义反转：亮色时 accent 是深墨（在浅底上显重），暗色时 accent 反转成月白浅色（在深底上显亮）。这和当前 gold 亮/暗切换逻辑一致。

---

## 3. 字体系统

### 决策：display 改宋体衬线栈，body 保留无衬线，移除 Merriweather 外链

| Token | 旧 | 新 |
|-------|----|----|
| `--font-display` | `'Merriweather', Georgia, 'Songti SC'...` | `Georgia, 'Noto Serif SC', 'Noto Serif CJK SC', 'Songti SC', 'STSong', 'SimSun', serif`（拉丁优先 Georgia，中文回落宋体） |
| `--font-body` | `'Source Sans Pro', system-ui, 'PingFang SC'...` | 保留（无衬线，UI 控件/输入框用，保证功能可读） |
| `--font-mono` | `'Source Code Pro'...` | 保留 |

**关键选择与权衡**：

- **不外链 CJK webfont**（Noto Serif SC 全量 5MB+，Google Fonts 分片机制复杂且国内访问不稳）。改为**优先系统宋体栈**：macOS 有 Songti SC、Windows 有 SimSun/微软雅黑、Linux 桌面常装 Noto CJK。系统没有时降级到 `Georgia, serif`（拉丁衬线），中文回退到系统默认衬线。
- **消息正文用 `--font-body`（无衬线）而非宋体**：辩论正文是长文本，全宋体在低分屏偏累；无衬线保证可读性。**发送者名、标题、品牌、印章字用 `--font-display`（宋体）**，把"文人感"集中在标识层。这是「可读性 vs 沉浸感」的折中，倾向可读性。
- **移除 Merriweather 外链**：它是拉丁衬线，与新 CJK 宋体不协调；直接用系统宋体栈。保留 Source Sans Pro + Source Code Pro 外链（拉丁字符，体积小）。

`index.html` 的 Google Fonts `<link>` 改为只加载 Source Sans Pro + Source Code Pro。

---

## 4. 纹理与质感（纯 CSS，无 JS）

### 4.1 宣纸肌理（`.chat-area` / `body`）

用 `background-image` 叠加两层：
- 极淡纤维纹：内联 SVG `feTurbulence` 生成的噪点 data URI，`opacity` 极低（0.03–0.05），`mix-blend-mode: multiply`。
- 宣纸不均匀色斑：两层径向渐变（米黄深浅斑）。

```css
.chat-area {
    background:
        radial-gradient(ellipse at 30% 20%, rgba(0,0,0,.02), transparent 60%),
        radial-gradient(ellipse at 70% 80%, rgba(0,0,0,.015), transparent 55%),
        var(--bg-base);
}
.chat-area::before { /* 水墨氤氲，替代 gold/sage 光晕 */
    background:
        radial-gradient(ellipse 65% 30% at 50% 0%, rgba(43,38,32,.06), transparent 70%),
        radial-gradient(ellipse 50% 40% at 85% 100%, rgba(184,65,58,.04), transparent 70%);
}
```

> 纹理 data URI 单独放一个常量，便于暗色模式切换（暗色用更弱的噪点）。

### 4.2 朱砂方印（品牌 + 辩手头像）

**品牌印记**（`.brand`）：标题「The Salon」旁加一枚朱砂方印，CSS 伪元素，写「辩」字（或「论」）。

```css
.brand h1::after {
    content: '辩';
    display: inline-block;
    margin-left: .4em;
    width: 1.6em; height: 1.6em;
    line-height: 1.6em; text-align: center;
    font-family: var(--font-display); font-weight: 900;
    font-size: .6em; color: #fff;
    background: var(--cinnabar);
    border: 2px solid var(--cinnabar-dim);
    border-radius: 2px;
    box-shadow: inset 0 0 0 1px rgba(255,255,255,.15);
    transform: rotate(-4deg);
    vertical-align: middle;
}
```

**辩手头像方印**（`.debater-avatar` / `.message-avatar`）：给 emoji 头像套一个朱砂方印边框（`::before` 朱砂描边方框 + 轻微旋转），让辩手像「盖了印」。不改 `renderer.js`，纯 CSS。

### 4.3 卷轴进度条（`.round-progress-fill`）

渐变从 `gold→sage` 改为**墨色渐变**（淡墨→浓墨），保留进度动效。`.round-badge` 加朱砂细边框，像「第 X / N 轮」的批注印。

### 4.4 empty-state 插画

当前是「对话气泡 + 放大镜」SVG。换为**水墨意象**：一支毛笔 + 砚台，或一枚朱砂闲章。纯改 `renderer.js` 里 `showEmptyState` 的 SVG path（这一处是 JS 内联 SVG，属于既有 DOM 结构内的内容替换，不破坏契约）。

---

## 5. 组件改造清单（按文件）

> 原则：类名/选择器**一律不动**，只改属性值。`var(--gold*)` 引用**不改名**（token 已重指向焦墨），仅在新需要朱砂的位加 `var(--cinnabar*)`。

### `tokens.css` — 整体重写（见 §2、§3）

### `base.css`
- `:focus-visible` outline：`--gold` →（已是焦墨，自动生效）
- `::selection`：`--gold-glow` →（已是焦墨晕）+ 文字保持 `--ink`
- `a` 链接色：`--gold-dim` → 朱砂 `--cinnabar-dim`（链接用朱砂更点睛，且链接少不冲突）

### `layout.css`
- `.brand` 下边框 `--gold` →（焦墨，自动）
- `.brand h1` 字体已用 `--font-display`（自动变宋体）+ 加 `::after` 朱砂印（§4.2）
- `.chat-area::before` 光晕 → 水墨氤氲（§4.1）
- `.round-progress-fill` 渐变 → 墨色渐变
- `.round-badge` 加朱砂细边框
- `.messages` 滚动区底纹继承 `.chat-area`

### `components.css`
- `.primary-btn`：`--gold` 背景（焦墨底白字），hover `--gold-dim`；`box-shadow` glow 用 `--gold-glow`（焦墨晕）；**文字色 `#fff` 改为 `var(--on-accent)`**（暗色下 accent 反转成月白，需墨字）
- `.scroll-bottom-btn-count`、`.refine-btn:hover`：同为 `color:#fff` → `var(--on-accent)`（同上理由）
- `.refine-btn`：「优化」按钮改朱砂描边（`--cinnabar` 边 + `--cinnabar-glow` 底），呼应"AI 点睛"语义
- `.debater-avatar` / `.message-avatar`：加朱砂方印边框（§4.2）
- `.debater-stance` badge：底改淡墨，字保留辩手 color
- `.empty-state-illustration`：换水墨意象（配合 §4.4，改 renderer 的 SVG）
- inputs/textarea focus：`--gold` →（焦墨，自动）
- `.toast.warn` 边：`--gold` →（焦墨，自动）；`.toast` 其余自动
- `.scroll-bottom-btn-count`：`--gold` 底 →（焦墨，自动）

### `messages.css`
- `.message-content` `border-left: --gold` →（焦墨，自动）
- `.cursor`（流式光标）`--gold` → **朱砂 `--cinnabar`**（朱砂光标更像"落笔"）
- `.skeleton-dots` `--gold` → 朱砂
- `.mention`（@提及）：`--gold*` → **朱砂**（提及 = 朱砂印泥感）
- `.concession`（退让）：`--gold*` → 淡墨虚线（退让 = 淡去的墨）
- `blockquote` border `--gold` → 朱砂
- `.message-sender` 字体 `--font-display`（自动宋体）
- `.message.user` navy tint、`.message.judge` sage border：保留（语义色不变）

### `search.css`
- `.search-result-item:hover` border `--gold` →（焦墨，自动）
- `.search-highlight` `--gold*` → 朱砂（搜索高亮 = 朱砂批注）

### `main.css`
- view-transition 保留不动

### `index.html`
- Google Fonts `<link>`：移除 Merriweather，保留 Source Sans Pro + Source Code Pro
- `#custom-color` `value="#a67b32"` → 新默认焦墨 `#2b2620`（见 §6.4）
- 缓存版本号 `?v=21` → `?v=22`（强制刷新）

---

## 6. 重构暴露的颜色漂移修复（4 处）

这些是现有代码把主题色**硬编码为 hex**，一旦 token 改值就会与新主题不一致——属于「重构顺带暴露」要修的 bug。

### 6.1 `app.js:_downloadChat()`（约 583–647 行）— 最严重
**问题**：导出的独立 HTML 把整套配色和内联 border 写死成旧 hex（`#f5f1ea`/`#1a1714`/`#a67b32`/`#3e5260`/`#d4c8b1`/`#7a6f5d` 等）。换肤后下载档案会是旧羊皮纸风，与界面割裂。

**修复**：把 `palette` 对象的两个分支（亮/暗）的 hex 值**全部更新为新主题对应值**（宣纸色、焦墨、朱砂、松烟暗色），并把内联 `border-bottom:2px solid #a67b32`、`border-left:3px solid #a67b32`、blockquote `#a67b32` 等替换为新焦墨/朱砂 hex。导出 HTML 是独立文档，无法用 CSS 变量，只能用与 token 一致的硬编码 hex 常量。

> 导出档案的字体也顺带从 `Georgia,serif` 改为宋体栈，保持一致。

### 6.2 `utils.js:sanitizeColor()`（第 9 行）
**问题**：非法颜色兜底写死 `'#a67b32'`（旧金）。换肤后兜底色与主 accent 不一致。

**修复**：兜底改为新主 accent 焦墨 `'#2b2620'`。同步更新 `tests-js/utils.test.js` 第 26–30 行的 5 处断言（`#a67b32` → `#2b2620`）。

### 6.3 `renderer.js:appendJudgeChunk()`（第 447 行）
**问题**：裁判颜色硬编码 `'#5a6e50'`。若 sage token 微调（§2.2 改 `#55704c`），此处会漂移。

**修复**：改为与新 sage 一致的 `'#55704c'`（与 token 同值硬编码，因为这是传给 `sanitizeColor` 的运行时值）。

### 6.4 `index.html:custom-color`（第 62 行）
**问题**：颜色选择器默认 `value="#a67b32"`（旧金）。

**修复**：改为 `#2b2620`（焦墨，与主 accent 一致）。

---

## 7. 不做的事（YAGNI / 边界）

- **不引入阵营语义色系统**：正/反/中立的区分已由各辩手 `color` + emoji 承担；叠一套会与自定义辩手冲突。
- **不改 `renderer.js` 的 DOM 类名契约**：所有视觉改动靠 CSS；唯一动 JS 内联 SVG 的是 empty-state 插画（既有结构内替换）。
- **不改 `markdown.js`**：XSS 防护层不碰。
- **不外链 CJK webfont**：用系统宋体栈，零额外下载。
- **不改后端、SSE 协议、presets.yaml 的 color 值**：那是辩手数据，保持用户预期。
- **不引入构建步骤**：仍是 vanilla ES modules。
- **不做手卷/折页等 DOM 结构级重构**：方案 C 已否决。

---

## 8. 测试策略

### 8.1 不破现有测试
- 已核实：前端测试**不断言主题 token 颜色**，只断言内联 `style.color`（来自辩手数据）和 `style.width`（进度）。纯 CSS 换肤不破任何测试。
- 后端 100% coverage 不受影响（纯前端改动）。

### 8.2 需更新的测试
- `tests-js/utils.test.js`：`sanitizeColor` 兜底断言 5 处（§6.2）。

### 8.3 验证清单（手动）
1. `.venv/` 不需要；纯前端：`npm test` 通过（含更新后的 utils 断言）。
2. `python -m uvicorn main:app --reload`，浏览器打开：
   - 亮色：宣纸底 + 墨色 accent + 朱砂品牌印 + 朱砂方印头像 + 宋体标题
   - 暗色：松烟暖黑底 + 月白 accent + 提亮朱砂
   - 主题切换（View Transition）平滑
3. 跑一场完整辩论：流式朱砂光标、skeleton 朱砂点、@提及朱砂印泥、blockquote 朱砂边、退让淡墨、裁判松烟青边。
4. 「下载」档案在亮/暗两种模式下都与界面配色一致（§6.1 验证点）。
5. 搜索：结果 hover 焦墨边、高亮朱砂批注。
6. empty-state：水墨毛笔/闲章插画显示正常。
7. 移动端（<860px）：响应式不被纹理/印章破坏。

---

## 9. 风险与回滚

- **风险低**：改动 95% 在 CSS，JS 只动 4 处 hex 常量 + 1 处 SVG path + 1 处测试断言。
- **字体回退**：系统无宋体时降级 `Georgia, serif` + 系统默认 CJK 衬线；功能不受影响。
- **纹理性能**：SVG 噪点 data URI 体积小（<1KB），`mix-blend-mode` 仅在 `.chat-area` 一层，性能可忽略。
- **回滚**：所有改动集中在 `static/styles/*.css` + `static/index.html` + `static/app.js`(_downloadChat) + `static/modules/utils.js` + `static/modules/renderer.js`(1 行) + `tests-js/utils.test.js`。`git revert` 单提交即可。

---

## 10. 交付物

- `static/styles/tokens.css`（重写）
- `static/styles/base.css`（微调）
- `static/styles/layout.css`（光晕/进度/品牌印）
- `static/styles/components.css`（accent 对齐 + 头像方印 + empty-state 配合）
- `static/styles/messages.css`（朱砂/淡墨点睛位）
- `static/styles/search.css`（高亮朱砂）
- `static/index.html`（字体 link + custom-color 默认 + v=22）
- `static/app.js`（_downloadChat 调色板对齐）
- `static/modules/utils.js`（sanitizeColor 兜底）
- `static/modules/renderer.js`（judge 色 1 行 + empty-state SVG）
- `tests-js/utils.test.js`（5 处断言）
- （可选）`static/favicon.svg` 已经是朱砂+墨蓝，保持不动
