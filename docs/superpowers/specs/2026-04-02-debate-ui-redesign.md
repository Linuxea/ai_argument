# AI 辩论室 UI 重设计方案

## 设计方向
- **风格**: 智性/学术（牛津辩论社风格)
- **配色**: 保持暖色调羊皮纸风格，统一为更温暖的金棕色调
- **字体**: Merriweather(标题) + Source Sans Pro(正文)
- **视觉密度**: 大量留白、克制

## 问题诊断
当前 UI 主要问题:
1. **侧边栏各区块视觉不统一** - 间距、边框、背景样式不一致
2. **消息卡片样式割裂** - 不同类型消息(辩手/用户/系统)区分不够清晰

3. **搜索工具卡片** - 占用空间大，交互方式不够优雅

## 改造方案: 轻量重构
保持现有结构，优化视觉细节，最小化改动风险。

## 具体改动

### 1. 字体更换
- 标题字体: **Merriweather** (衬线，文学感强)
- 正文/标签字体: **Source Sans Pro** (清晰、现代)
- 代码字体= **Source Code Pro** (等宽)

```css
@import url('https://fonts.googleapis.com/css2?family=Merriweather:wght@400;700;900&family=Source+Sans+Pro:wght@300;400;600;family=Source+Code+Pro:wght@400;500&display=swap');
```

### 2. 色统一
**色板调整为更温暖的金棕色调:**
- `--ink`: #1a1714
- `--ink-soft`: #5c5548
- `--ink-muted`: #8b7355
- `--border`: #d4c8b1
- `--border-hover`: #c0a0a8
- `--gold`: #a67b32
- `--gold-dim`: #8b5a14
- `--gold-glow`: rgba(166, 115, 50, 0.12)
- `--sage`: #5a6e50
- `--sage-dim`: #3d4d40
- `--sage-glow`: rgba(90, 110, 80, 0.08)
- `--navy`: #4a5a60

```css
:root {
    /* Surfaces */
    --bg-base:       #f5f1ea;
    --bg-surface:    #faf8f4;
    --bg-elevated:   #ffffff;
    --bg-card:       #ffffff;
    --bg-input:      #f0ece4;

    /* Borders & shadows */
    --border:        #d4c8b1;
    --border-hover:  #c0a0a8;
    --shadow-sm:     0 1px 2px rgba(166, 115, 50, 0.04);
    --shadow-md:     0 2px 8px rgba(166, 115, 50, 0.06);
    --shadow-lg:     0 4px 16px rgba(166, 115, 50, 0.08);

    /* Accent palette */
    --ink:           #1a1714;
    --ink-soft:      #5c5548;
    --ink-muted:     #8b7355
    --gold:           #a67b32
    --gold-dim:       #8b5a14
    --gold-glow:       rgba(166, 115, 50, 0.12)
    --sage:           #5a6e50
    --sage-dim:         #3d4d40
    --sage-glow:       rgba(90, 110, 80, 0.08)
    --navy:           #4a5a60

    /* Text */
    --text:          #1a1714
    --text-soft:     #5c5548
    --text-muted:    #8b7355

    /* Typography */
    --font-display:  'Merriweather', Georgia, serif;
    --font-body:     'Source Sans Pro', system-ui, sans-serif;
    --font-mono:    'Source Code Pro', monospace;
}
```

### 3. 间距优化
**统一侧边栏区块间距为 `16px`， 边框样式:**
- 所有 section 使用相同的 padding、边框
- 减少视觉噪音
- 标签更小、更克制
- 辩手列表项最大高度增加到 `240px`

### 4. 消息卡片重新设计
**更柔和的视觉效果:**
- 卡片阴影更轻 (`0 1px 2px rgba`)
- 左侧彩色条使用渐变背景
- 时间戳改为圆角胶囊样式
- stance 标签改为圆角胶囊
- 移除消息卡片的外边框（用户消息除外）
- 系统消息使用居中、斜体显示
- 优化消息头部布局：头像+姓名+时间更紧凑

- 用户消息保持边框，使用渐变背景区分

### 5. 搜索工具卡片
**底部抽屉式设计:**
- 搜索按钮显示在消息底部
- 点击后展开抽屉，显示搜索结果
- 结果可折叠，点击查看详情
- 包含：搜索词、来源摘要、相关搜索建议

### 6. 按钮样式优化
**更统一的按钮样式:**
- 主按钮使用统一的背景和边框
- 辅助按钮（暂停/继续/裁判）使用幽灵按钮样式
- 下载按钮更优雅

### 7. 设置面板
**保持现有功能，优化视觉效果**

## 文件改动
- `static/index.html` - 更新字体引入
- `static/style.css` - 完全重写
- `static/app.js` - 添加搜索卡片交互逻辑

