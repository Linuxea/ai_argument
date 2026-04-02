# Settings Slide-out Panel — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract the API settings section from the sidebar into a right-side slide-out panel, leaving a ⚙️ entry button in the sidebar header.

**Architecture:** Purely frontend refactor. The API settings inputs (URL, key, model, save button) move from the sidebar's `<aside>` into a new `.settings-panel` div that slides in from the right. A backdrop overlay provides click-to-dismiss. No backend changes; JS binds to the new element locations.

**Tech Stack:** Vanilla JS, CSS custom properties, no new dependencies.

---

### Task 1: Add settings panel and backdrop HTML

**Files:**
- Modify: `static/index.html`

- [ ] **Step 1: Remove the API settings section from the sidebar**

Delete the entire `<section class="sidebar-section">` block that contains the API URL, API key, model dropdown, and save settings button (currently lines 36–44 of `index.html`):

Remove this block:
```html
            <section class="sidebar-section">
                <label>API 设置</label>
                <input type="text" id="api-url" placeholder="API 地址（默认：https://api.deepseek.com）" value="">
                <input type="password" id="api-key" placeholder="API 密钥（默认：$DEEPSEEK_API_KEY）" value="">
                <select id="model-name">
                    <option value="">-- 保存后获取模型列表 --</option>
                </select>
                <button id="save-settings-btn">保存设置</button>
            </section>
```

- [ ] **Step 2: Add a ⚙️ settings button to the sidebar header**

In the sidebar header flex container (the `<div style="display:flex...">`), add the settings button after the theme toggle button. Change the header from:

```html
            <div style="display:flex;justify-content:space-between;align-items:center;padding-bottom:18px;border-bottom:2px solid var(--terracotta)">
                <h1 style="border:none;padding:0">AI 辩论</h1>
                <button class="theme-toggle" id="theme-toggle" title="切换主题">🌙</button>
            </div>
```

To:

```html
            <div style="display:flex;justify-content:space-between;align-items:center;padding-bottom:18px;border-bottom:2px solid var(--terracotta)">
                <h1 style="border:none;padding:0">AI 辩论</h1>
                <div style="display:flex;gap:4px">
                    <button class="icon-btn" id="settings-btn" title="设置">⚙️</button>
                    <button class="icon-btn" id="theme-toggle" title="切换主题">🌙</button>
                </div>
            </div>
```

Note: the theme toggle's class changes from `theme-toggle` to `icon-btn` (we'll update the CSS class name in Task 2).

- [ ] **Step 3: Add the settings panel and backdrop HTML before the closing `</div>` of `.app`**

Insert the following block just before the closing `</div>` of the `.app` container (i.e., before the line `</div>` that closes `<div class="app">`):

```html
    <div class="settings-backdrop" id="settings-backdrop"></div>
    <div class="settings-panel" id="settings-panel">
        <div class="settings-panel-header">
            <h3>设置</h3>
            <button class="icon-btn" id="settings-close" title="关闭">✕</button>
        </div>
        <section class="sidebar-section">
            <label>API 设置</label>
            <input type="text" id="api-url" placeholder="API 地址（默认：https://api.deepseek.com）" value="">
            <input type="password" id="api-key" placeholder="API 密钥（默认：$DEEPSEEK_API_KEY）" value="">
            <select id="model-name">
                <option value="">-- 保存后获取模型列表 --</option>
            </select>
            <button id="save-settings-btn">保存设置</button>
        </section>
    </div>
```

The element IDs (`api-url`, `api-key`, `model-name`, `save-settings-btn`) stay the same — they just live inside the panel now instead of the sidebar.

- [ ] **Step 4: Bump cache-buster**

Update `style.css` version from `v=8` to `v=9`, and `app.js` from `v=9` to `v=10`:

```html
    <link rel="stylesheet" href="/static/style.css?v=9">
```
```html
    <script src="/static/app.js?v=10"></script>
```

---

### Task 2: Add CSS for settings panel

**Files:**
- Modify: `static/style.css`

- [ ] **Step 1: Rename `.theme-toggle` to `.icon-btn` and add settings panel styles**

Replace the existing `.theme-toggle` block (lines 100–117 of `style.css`):

```css
/* ─── Theme Toggle ─────────────────────────────────── */

.theme-toggle {
    background: none;
    border: none;
    font-size: 1.15rem;
    cursor: pointer;
    padding: 4px 6px;
    border-radius: var(--radius-sm);
    color: var(--text-muted);
    transition: color 0.2s, background 0.2s;
    line-height: 1;
}

.theme-toggle:hover {
    color: var(--text);
    background: var(--bg-input);
}
```

With:

```css
/* ─── Icon Buttons ─────────────────────────────────── */

.icon-btn {
    background: none;
    border: none;
    font-size: 1.15rem;
    cursor: pointer;
    padding: 4px 6px;
    border-radius: var(--radius-sm);
    color: var(--text-muted);
    transition: color 0.2s, background 0.2s;
    line-height: 1;
}

.icon-btn:hover {
    color: var(--text);
    background: var(--bg-input);
}

/* ─── Settings Panel ──────────────────────────────── */

.settings-backdrop {
    display: none;
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.35);
    z-index: 90;
}

.settings-backdrop.open { display: block; }

.settings-panel {
    position: fixed;
    top: 0;
    right: 0;
    width: 340px;
    height: 100vh;
    background: var(--bg-surface);
    border-left: 1px solid var(--border);
    box-shadow: -4px 0 24px rgba(0, 0, 0, 0.12);
    z-index: 100;
    display: flex;
    flex-direction: column;
    gap: 24px;
    padding: 28px 22px;
    overflow-y: auto;
    transform: translateX(100%);
    transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}

.settings-panel.open {
    transform: translateX(0);
}

.settings-panel-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding-bottom: 18px;
    border-bottom: 2px solid var(--terracotta);
}

.settings-panel-header h3 {
    font-family: var(--font-display);
    font-size: 1.2rem;
    font-weight: 700;
    color: var(--ink);
    letter-spacing: 0.04em;
}
```

---

### Task 3: Update JS bindings and add open/close logic

**Files:**
- Modify: `static/app.js`

- [ ] **Step 1: Update `bindElements()` — add panel elements, keep API settings bindings**

In `bindElements()`, after the `// Theme` block, add a `// Settings panel` block. The API settings element bindings (`this.apiUrl`, `this.apiKey`, `this.modelName`, `this.saveSettingsBtn`) stay exactly the same because the element IDs are unchanged. Only add the new panel-specific bindings:

```javascript
        // Theme
        this.themeToggle = document.getElementById('theme-toggle');

        // Settings panel
        this.settingsBtn = document.getElementById('settings-btn');
        this.settingsClose = document.getElementById('settings-close');
        this.settingsPanel = document.getElementById('settings-panel');
        this.settingsBackdrop = document.getElementById('settings-backdrop');
```

- [ ] **Step 2: Update `bindEventListeners()` — add panel listeners**

In `bindEventListeners()`, after the `// Theme` line, add:

```javascript
        // Theme
        this.themeToggle.addEventListener('click', () => this.toggleTheme());

        // Settings panel
        this.settingsBtn.addEventListener('click', () => this.openSettings());
        this.settingsClose.addEventListener('click', () => this.closeSettings());
        this.settingsBackdrop.addEventListener('click', () => this.closeSettings());
```

- [ ] **Step 3: Add `openSettings()` and `closeSettings()` methods**

Add these methods right after `_updateThemeIcon()`:

```javascript
    openSettings() {
        this.settingsPanel.classList.add('open');
        this.settingsBackdrop.classList.add('open');
    }

    closeSettings() {
        this.settingsPanel.classList.remove('open');
        this.settingsBackdrop.classList.remove('open');
    }
```

- [ ] **Step 4: Verify no element ID references broke**

The following element IDs have NOT changed, so all existing JS references (`this.apiUrl`, `this.apiKey`, `this.modelName`, `this.saveSettingsBtn`, `this.themeToggle`) continue to work:
- `api-url` — moved from sidebar to settings panel, same ID
- `api-key` — moved from sidebar to settings panel, same ID
- `model-name` — moved from sidebar to settings panel, same ID
- `save-settings-btn` — moved from sidebar to settings panel, same ID
- `theme-toggle` — stays in sidebar header, same ID

No changes needed in `loadSettings()`, `saveSettings()`, `fetchModels()`, or `startDebate()`.

- [ ] **Step 5: Run existing tests to confirm no regression**

Run: `python -m pytest tests/ -v`
Expected: Same 2 known failures (Chinese preset names), 29 passing.

- [ ] **Step 6: Commit**

```bash
git add static/style.css static/index.html static/app.js
git commit -m "feat: extract API settings into slide-out panel"
```
