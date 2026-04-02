# AI 辩论室 UI 轻量重构 定现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 优化现有 UI 的视觉一致性，采用智性/学术风格、大量留白、克制的视觉密度,更换字体为 Merriweather + Source Sans Pro,并添加搜索工具卡片功能。

**Architecture:** 保持现有侧边栏结构，通过 CSS 变量统一视觉语言。在消息底部添加可搜索工具卡片抽屉,采用底部抽屉式交互。

**Tech Stack:** HTML, CSS, JavaScript(原生)

**Files:**
- Create: `static/favicon.svg` (如果不存在)
- Modify: `static/index.html` - 更新字体引入
- Modify: `static/style.css` - 完全重写样式
- Modify: `static/app.js` - 添加搜索工具卡片逻辑
- Create: `tests/test_ui.py` - UI 相关测试(可选)

---

## Task 1: 更新 HTML 字体引入
**Files:**
- Modify: `static/index.html`

- [ ] **Step 1: 更新 Google Fonts 引入**

将 Playfair Display + Outfit 替为 Merriweather + Source Sans Pro + Source Code Pro:

```html
<!-- 更换为 -->
<link href="https://fonts.googleapis.com/css2?family=Merriweather:wght@400;700;900&family=Source+Sans+Pro:wght@300;400;600&family=Source+Code+Pro:wght@400;500&display=swap" rel="stylesheet">
```

- [ ] **Step 2: 添加 favicon(如果不存在)**

检查 `/static/favicon.svg` 是否存在,如果不存在,创建一个简单的 SVG favicon.

- [ ] **Step 3: 添加字体预加载**

添加 `<link rel="preconnect">` 以加快字体加载。

- [ ] **Step 4: 提交**

```bash
git add static/index.html
git commit -m "feat: update fonts to Merriweather + Source Sans Pro"
```

---

## Task 2: 完全重写 CSS 样式
**Files:**
- Modify: `static/style.css`

- [ ] **Step 1: 定义新的 CSS 变量系统**

```css
:root {
    /* Surfaces - 更温暖的羊皮纸色 */
    --bg-base:       #f5f1ea;
    --bg-surface:    #faf8f4;
    --bg-elevated:   #ffffff;
    --bg-card:       #ffffff;
    --bg-input:      #f0ece4;

    /* Borders & shadows - 更柔和 */
    --border:        #d4c8b1;
    --border-hover:  #c0a0a8;
    --shadow-sm:     0 1px 2px rgba(166, 115, 50, 0.04);
    --shadow-md:     0 2px 8px rgba(166, 115, 50, 0.06);
    --shadow-lg:     0 4px 16px rgba(166, 115, 50, 0.08);

    /* Accent palette - 统一的金棕色调 */
    --ink:           #1a1714;
    --ink-soft:      #5c5548;
    --ink-muted:     #8b7355;
    --gold:           #a67b32;
    --gold-dim:       #8b5a14;
    --gold-glow:       rgba(166, 115, 50, 0.12);
    --sage:           #5a6e50;
    --sage-dim:       #3d4d40;
    --sage-glow:       rgba(90, 110, 80, 0.08);
    --navy:           #4a5a60;

    /* Typography - 新字体 */
    --font-display:  'Merriweather', Georgia, serif;
    --font-body:     'Source Sans Pro', system-ui, sans-serif;
    --font-mono:    'Source Code Pro', monospace;

    /* Sizing */
    --sidebar-w:     320px;
    --radius-sm:     8px;
    --radius-md:     12px;
    --radius-lg:     16px;
}
```

- [ ] **Step 2: 定义 Dark 主题变量**

在 `:root` 中添加 `html.dark` 选择器下的变量覆盖。

- [ ] **Step 3: 重写基础样式**

- body, .app, .sidebar, .chat-area 等基础布局

- [ ] **Step 4: 重写侧边栏区块样式**

- .sidebar-section 统一间距、边框、背景
- 辩手列表项优化
- 按钮样式统一化

- [ ] **Step 5: 重写消息卡片样式**

- .message 系列样式更柔和
- 移除消息卡片外边框
- 使用渐变背景
- 时间戳改为圆角胶囊
- stance 标签改为圆角胶囊
- 系统消息使用居中、斜体
- 用户消息保持边框，使用渐变背景区分

- [ ] **Step 6: 重写工具卡片样式**

- .tool-card 样式优化

- [ ] **Step 7: 重写输入栏样式**

- [ ] **Step 8: 重写设置面板样式**

- [ ] **Step 9: 重写按钮样式**

- 主按钮、辅助按钮、下载/裁判按钮统一化

- [ ] **Step 10: 添加动画**

- 消息入场动画
- 按钮悬停/点击效果

- [ ] **Step 11: 添加响应式调整**

- 移动端适配优化

- [ ] **Step 12: 提交**

```bash
git add static/style.css
git commit -m "feat: redesign UI with warm academic aesthetic"
```

---

## Task 3: 添加搜索工具卡片功能
**Files:**
- Modify: `static/index.html` - 添加搜索工具 HTML 结构
- Modify: `static/style.css` - 添加搜索工具样式
- Modify: `static/app.js` - 添加搜索工具交互逻辑
- Create: `tests/test_ui.py` - UI 相关测试(可选)

---

### 搜索功能设计
- **搜索范围**: 所有已渲染的消息内容(`.message-content` 的 innerText)
- **搜索触发**: 它内实时搜索(输入即搜索，无需按回车)
- **结果展示**: 显示匹配的消息(最多 10 条)
- **点击行为**: 点击结果 → 滚动到对应消息并高亮
- **关闭方式**: 点击抽屉外部或按 ESC 键关闭

---

- [ ] **Step 1: 添加搜索工具 HTML 结构**

在 `index.html` 的 `.input-bar` 之前添加:

```html
<!-- Search Drawer -->
<div id="search-drawer" class="search-drawer">
    <div class="search-drawer-header">
        <input type="text" id="search-input" placeholder="搜索消息内容...">
        <button id="search-close-btn" class="icon-btn">✕</button>
    </div>
    <div id="search-results" class="search-results"></div>
</div>
<!-- Search Toggle Button (显示在消息区域右下角) -->
<button id="search-toggle-btn" class="search-toggle-btn" title="搜索">🔍</button>
```

- [ ] **Step 2: 添加搜索工具 CSS 样式**

```css
/* ─── Search Drawer ─────────────────────────────────── */

.search-drawer {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    background: var(--bg-surface);
    border-top: 1px solid var(--border);
    transform: translateY(100%);
    transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1);
    max-height: 50vh;
    overflow-y: auto;
    z-index: 50;
    padding: 20px 24px;
}

.search-drawer.open {
    transform: translateY(0);
}

.search-drawer-header {
    display: flex;
    gap: 10px;
    margin-bottom: 16px;
}

.search-drawer-header input {
    flex: 1;
    padding: 12px 16px;
    background: var(--bg-input);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    font-size: 0.95rem;
    color: var(--text);
}

.search-drawer-header input:focus {
    outline: none;
    border-color: var(--gold-dim);
    box-shadow: 0 0 0 3px var(--gold-glow);
}

.search-results {
    display: flex;
    flex-direction: column;
    gap: 8px;
}

.search-result-item {
    padding: 12px 16px;
    background: var(--bg-card);
    border-radius: var(--radius-sm);
    cursor: pointer;
    border: 1px solid transparent;
    transition: all 0.15s;
}

.search-result-item:hover {
    background: var(--bg-input);
    border-color: var(--border);
}

.search-result-item .result-speaker {
    font-family: var(--font-display);
    font-weight: 700;
    font-size: 0.85rem;
    margin-bottom: 4px;
}

.search-result-item .result-preview {
    font-size: 0.8rem;
    color: var(--text-muted);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.search-result-item .result-time {
    font-size: 0.7rem;
    color: var(--text-muted);
    margin-left: auto;
}

.search-empty {
    text-align: center;
    padding: 24px;
    color: var(--text-muted);
    font-size: 0.9rem;
}

/* Search Toggle Button */
.search-toggle-btn {
    position: fixed;
    bottom: 80px;
    right: 20px;
    width: 44px;
    height: 44px;
    background: var(--bg-elevated);
    border: 1px solid var(--border);
    border-radius: 50%;
    font-size: 1.1rem;
    cursor: pointer;
    z-index: 40;
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: var(--shadow-md);
    transition: all 0.2s;
}

.search-toggle-btn:hover {
    background: var(--bg-input);
    border-color: var(--border-hover);
    box-shadow: var(--shadow-lg);
}

.search-toggle-btn.hidden {
    opacity: 0;
    pointer-events: none;
}
```

- [ ] **Step 3: 在 app.js 中添加搜索工具交互逻辑**

在 `bindElements()` 方法中添加:

```javascript
// Search
this.searchDrawer = document.getElementById('search-drawer');
this.searchInput = document.getElementById('search-input');
this.searchResults = document.getElementById('search-results');
this.searchToggleBtn = document.getElementById('search-toggle-btn');
this.searchCloseBtn = document.getElementById('search-close-btn');
```

在 `bindEventListeners()` 方法中添加

```javascript
// Search toggle button
this.searchToggleBtn.addEventListener('click', () => this.openSearchDrawer());

// Close button
this.searchCloseBtn.addEventListener('click', () => this.closeSearchDrawer());

// Search input
this.searchInput.addEventListener('input', (e) => this.handleSearch(e.target.value));

// Close on click outside
this.searchDrawer.addEventListener('click', (e) => {
    if (e.target === this.searchDrawer) {
        this.closeSearchDrawer();
    }
});

// Close on Escape key
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && this.searchDrawer.classList.contains('open')) {
        this.closeSearchDrawer();
    }
});
```

添加新方法

```javascript
openSearchDrawer() {
    this.searchDrawer.classList.add('open');
    this.searchToggleBtn.classList.add('hidden');
    this.searchInput.focus();
    // Index all messages for search
    this._indexMessages();
}

closeSearchDrawer() {
    this.searchDrawer.classList.remove('open');
    this.searchToggleBtn.classList.remove('hidden');
    this.searchInput.value = '';
    this.searchResults.innerHTML = '';
}

_indexMessages() {
    const messages = this.messages.querySelectorAll('.message');
    this._searchIndex = [];
    messages.forEach((msg, idx) => {
        const contentEl = msg.querySelector('.message-content');
        const speakerEl = msg.querySelector('.message-sender');
        const timeEl = msg.querySelector('.message-time');
        if (contentEl && speakerEl) {
            this._searchIndex.push({
                index: idx,
                element: msg,
                speaker: speakerEl.textContent,
                content: contentEl.textContent || contentEl.innerText,
                time: timeEl ? timeEl.textContent : ''
            });
        }
    });
}
handleSearch(query) {
    if (!query.trim()) {
        this.searchResults.innerHTML = '<div class="search-empty">输入搜索词</div>';
        return;
    }
    const q = query.toLowerCase().trim();
    const results = this._searchIndex.filter(item =>
        item.content.toLowerCase().includes(q)
    ).slice(0, 10);

    if (results.length === 0) {
        this.searchResults.innerHTML = '<div class="search-empty">未找到匹配的消息</div>';
        return;
    }

    this.searchResults.innerHTML = results.map(item => `
        <div class="search-result-item" data-index="${item.index}">
            <div class="result-speaker" style="color: ${this.getSpeakerColor(item.speaker)}">${item.speaker}</div>
            <div class="result-preview">${this.escapeHtml(item.content.substring(0, 60))}...</div>
            <div class="result-time">${item.time}</div>
        </div>
    `).join('');

    // Bind click events
    this.searchResults.querySelectorAll('.search-result-item').forEach(el => {
        el.addEventListener('click', () => {
            const idx = parseInt(el.dataset.index);
            this.scrollToMessage(idx);
            this.closeSearchDrawer();
        });
    });
}
getSpeakerColor(speakerName) {
    // Try to find color from the debater data or message element
    const messages = this.messages.querySelectorAll('.message');
    for (const msg of messages) {
        const senderEl = msg.querySelector('.message-sender');
        if (senderEl && senderEl.textContent === speakerName) {
            return senderEl.style.color || 'var(--gold)';
        }
    }
    return 'var(--gold)';
}
scrollToMessage(index) {
    const messages = this.messages.querySelectorAll('.message');
    if (index >= 0 && index < messages.length) {
        const targetMsg = messages[index];
        targetMsg.scrollIntoView({ behavior: 'smooth', block: 'center' });
        // Highlight effect
        targetMsg.style.transition = 'background 0.3s';
        targetMsg.style.background = 'var(--gold-glow)';
        setTimeout(() => {
            targetMsg.style.background = '';
        }, 1000);
    }
}
```

- [ ] **Step 4: 提交**

```bash
git add static/index.html static/style.css static/app.js
git commit -m "feat: add search tool card drawer"
```
