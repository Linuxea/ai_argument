# Settings Slide-out Panel

## Goal

Extract the API settings section from the sidebar into a dedicated slide-out panel, keeping a small settings entry button on the main page. This prepares for future settings options (theme preference, language, etc.) without crowding the sidebar.

## What Moves

The entire "API 设置" sidebar section:
- API URL input
- API key input
- Model dropdown
- Save settings button

## What Stays in Sidebar

- Header (title + 🌙 theme toggle + ⚙️ settings button)
- 辩论主题 (topic input + max rounds)
- 辩手列表 (debater list with drag-and-drop)
- 控制按钮 (start / stop / resume)
- 自定义辩手 (add custom debater form)

## Settings Panel UI

- **Trigger:** ⚙️ icon button in the sidebar header (next to 🌙)
- **Animation:** slides in from the right edge, 320px wide, overlaying the chat area
- **Backdrop:** semi-transparent overlay behind the panel; click to dismiss
- **Close:** ✕ button at top-right of panel
- **Layout:** single-column form, matching the existing sidebar section style
- **Future-proofing:** panel is a vertical stack of sections; new setting groups can be appended below API settings

## Scope

- Frontend only — no backend changes
- Same `localStorage` + `/api/settings` endpoints
- Same `loadSettings()`, `saveSettings()`, `fetchModels()` logic, just moved to operate on panel elements instead of sidebar elements

## Files Changed

| File | Change |
|------|--------|
| `static/index.html` | Remove API settings section from sidebar; add ⚙️ button; add settings panel HTML + backdrop |
| `static/style.css` | Add `.settings-panel`, `.settings-backdrop`, slide animation styles |
| `static/app.js` | Bind new panel elements; add `openSettings()` / `closeSettings()`; update element IDs in `loadSettings()` / `saveSettings()` |
