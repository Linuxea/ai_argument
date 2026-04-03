// Configure marked.js for safe rendering — disable raw HTML in markdown
marked.setOptions({
    breaks: true,
    gfm: true,
    headerIds: false,
    mangle: false,
});

// Escape all raw HTML that appears in markdown input.
// In marked.js the renderer method for raw HTML tokens is called "html"
// (it handles both block-level and inline HTML). By overriding it to
// escape the text we neutralise any XSS payload the LLM might emit.
marked.use({
    renderer: {
        html({ text }) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        },
    },
});

class DebateApp {
    constructor() {
        this.eventSource = null;
        this.currentMessageEl = null;
        this.debateActive = false;
        this.debatePaused = false;
        this._currentDebaterName = null;
        this._currentDebaterColor = null;
        this._currentDebaterAvatar = null;
        this._lastSpeakerName = null;  // Track last speaker for merging headers
        this.init();
    }

    async init() {
        this.initTheme();
        this.bindElements();
        this.bindEventListeners();
        const maxRounds = localStorage.getItem('max_rounds');
        if (maxRounds) this.maxRoundsInput.value = maxRounds;
        await this.loadDebaters();
    }

    bindElements() {
        // Topic input
        this.topicInput = document.getElementById('topic-input');
        this.maxRoundsInput = document.getElementById('max-rounds');
        this.refineTopicBtn = document.getElementById('refine-topic-btn');

        // Debater list
        this.debaterList = document.getElementById('debater-list');

        // Control buttons
        this.startBtn = document.getElementById('start-btn');
        this.stopBtn = document.getElementById('stop-btn');
        this.resumeBtn = document.getElementById('resume-btn');

        // Custom debater
        this.customName = document.getElementById('custom-name');
        this.customColor = document.getElementById('custom-color');
        this.customAvatar = document.getElementById('custom-avatar');
        this.customStance = document.getElementById('custom-stance');
        this.customPersonality = document.getElementById('custom-personality');
        this.addDebaterBtn = document.getElementById('add-debater-btn');

        // Chat area
        this.chatTitle = document.getElementById('chat-title');
        this.messages = document.getElementById('messages');
        this.userInput = document.getElementById('user-input');
        this.sendBtn = document.getElementById('send-btn');
        this.judgeBtn = document.getElementById('judge-btn');
        this.downloadBtn = document.getElementById('download-btn');

        // Unhide judge button (starts hidden in HTML)
        if (this.judgeBtn) this.judgeBtn.removeAttribute('hidden');

        // Theme
        this.themeToggle = document.getElementById('theme-toggle');

        // Search tool
        this.searchToggleBtn = document.getElementById('search-toggle-btn');
        this.searchDrawer = document.getElementById('search-drawer');
        this.searchBackdrop = document.getElementById('search-backdrop');
        this.searchClose = document.getElementById('search-close');
        this.searchInput = document.getElementById('search-input');
        this.searchResults = document.getElementById('search-results');
        this._searchDebounceTimer = null;
        this._messageIndex = [];
    }

    bindEventListeners() {
        // Control buttons
        this.startBtn.addEventListener('click', () => this.startDebate());
        this.stopBtn.addEventListener('click', () => this.stopDebate());
        this.resumeBtn.addEventListener('click', () => this.resumeDebate());

        // Topic refinement
        this.refineTopicBtn.addEventListener('click', () => this.refineTopic());

        // Custom debater
        this.addDebaterBtn.addEventListener('click', () => this.addCustomDebater());

        // User message
        this.sendBtn.addEventListener('click', () => this.sendUserMessage());
        this.userInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.sendUserMessage();
        });

        // Judge
        this.judgeBtn.addEventListener('click', () => this.requestJudge());

        // Download
        this.downloadBtn.addEventListener('click', () => this.downloadChat());

        // Theme
        this.themeToggle.addEventListener('click', () => this.toggleTheme());

        // Search tool
        this.searchToggleBtn.addEventListener('click', () => this.openSearchDrawer());
        this.searchClose.addEventListener('click', () => this.closeSearchDrawer());
        this.searchBackdrop.addEventListener('click', () => this.closeSearchDrawer());
        this.searchInput.addEventListener('input', () => this.handleSearch());

        // Global ESC handler for search
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                if (this.searchDrawer.classList.contains('open')) {
                    this.closeSearchDrawer();
                }
            }
        });
    }

    async loadDebaters() {
        try {
            const response = await fetch('/api/debaters');
            const debaters = await response.json();
            this.renderDebaters(debaters);
        } catch (error) {
            console.error('Failed to load debaters:', error);
        }
    }

    renderDebaters(debaters) {
        this.debaterList.innerHTML = '';
        this._draggedItem = null;

        debaters.forEach(debater => {
            const item = document.createElement('div');
            item.className = 'debater-item';
            item.draggable = true;

            const handle = document.createElement('span');
            handle.className = 'drag-handle';
            handle.textContent = '⠿';

            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.id = `debater-${CSS.escape(debater.name)}`;
            checkbox.value = debater.name;
            checkbox.checked = true;

            const avatar = document.createElement('span');
            avatar.className = 'debater-avatar';
            avatar.textContent = debater.avatar;

            const name = document.createElement('span');
            name.className = 'debater-name';
            name.textContent = debater.name;

            const stance = document.createElement('span');
            stance.className = 'debater-stance';
            stance.style.color = this.sanitizeColor(debater.color);
            stance.textContent = debater.stance;

            item.appendChild(handle);
            item.appendChild(checkbox);
            item.appendChild(avatar);
            item.appendChild(name);
            item.appendChild(stance);
            this.debaterList.appendChild(item);

            // Drag-and-drop: reorder debaters to control turn order
            item.addEventListener('dragstart', () => {
                this._draggedItem = item;
                item.classList.add('dragging');
            });
            item.addEventListener('dragend', () => {
                item.classList.remove('dragging');
                this._clearDragOver();
                this._draggedItem = null;
            });
            item.addEventListener('dragover', (e) => {
                e.preventDefault();
                if (!this._draggedItem || this._draggedItem === item) return;
                this._clearDragOver();
                const rect = item.getBoundingClientRect();
                const mid = rect.top + rect.height / 2;
                if (e.clientY < mid) {
                    item.classList.add('drag-over-top');
                } else {
                    item.classList.add('drag-over-bottom');
                }
            });
            item.addEventListener('drop', (e) => {
                e.preventDefault();
                if (!this._draggedItem || this._draggedItem === item) return;
                const rect = item.getBoundingClientRect();
                const mid = rect.top + rect.height / 2;
                if (e.clientY < mid) {
                    this.debaterList.insertBefore(this._draggedItem, item);
                } else {
                    this.debaterList.insertBefore(this._draggedItem, item.nextSibling);
                }
                this._clearDragOver();
            });
        });
    }

    async refineTopic() {
        const topic = this.topicInput.value.trim();
        if (!topic) {
            alert('请先输入辩论主题');
            return;
        }

        // Show loading state
        const originalText = this.refineTopicBtn.textContent;
        this.refineTopicBtn.disabled = true;
        this.refineTopicBtn.textContent = '优化中...';

        try {
            const response = await fetch('/api/topic/refine', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ topic })
            });

            if (!response.ok) {
                const error = await response.json().catch(() => ({}));
                throw new Error(error.detail || '话题优化失败');
            }

            const data = await response.json();
            this.topicInput.value = data.refined_topic;

        } catch (error) {
            console.error('Failed to refine topic:', error);
            alert(error.message);
        } finally {
            this.refineTopicBtn.disabled = false;
            this.refineTopicBtn.textContent = originalText;
        }
    }

    async startDebate() {
        const topic = this.topicInput.value.trim();
        if (!topic) {
            alert('请输入辩论主题');
            return;
        }

        const selectedDebaters = this.getSelectedDebaters();
        if (selectedDebaters.length < 2) {
            alert('请至少选择2位辩手');
            return;
        }

        try {
            // Clear messages
            this.messages.innerHTML = '';
            this._lastSpeakerName = null;  // Reset for new debate
            this.chatTitle.textContent = topic;

            // Start debate
            const response = await fetch('/api/debate/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    topic: topic,
                    debater_names: selectedDebaters,
                    max_rounds: parseInt(this.maxRoundsInput.value) || 10
                })
            });

            if (!response.ok) {
                const error = await response.json().catch(() => ({}));
                throw new Error(error.detail || '启动辩论失败');
            }

            this.debateActive = true;
            this.debatePaused = false;
            this.updateUI('debating');
            this.connectSSE();

        } catch (error) {
            console.error('Failed to start debate:', error);
            alert(error.message);
        }
    }

    getSelectedDebaters() {
        const checkboxes = this.debaterList.querySelectorAll('input[type="checkbox"]:checked');
        return Array.from(checkboxes).map(cb => cb.value);
    }

    _clearDragOver() {
        this.debaterList.querySelectorAll('.drag-over-top, .drag-over-bottom').forEach(el => {
            el.classList.remove('drag-over-top', 'drag-over-bottom');
        });
    }

    _parseSSEData(e, eventName) {
        try {
            return JSON.parse(e.data);
        } catch (err) {
            console.error(`Failed to parse SSE data for ${eventName}:`, err, e.data);
            return null;
        }
    }

    connectSSE() {
        this.eventSource = new EventSource('/api/debate/stream');

        this.eventSource.addEventListener('debater_start', (e) => {
            const data = this._parseSSEData(e, 'debater_start');
            if (!data) return;
            this._currentDebaterName = data.debater_name;
            this._currentDebaterColor = data.color;
            this._currentDebaterAvatar = data.avatar;
            this.createMessage(data.debater_name, data.color, data.avatar, 'debater');
        });

        this.eventSource.addEventListener('thinking_chunk', (e) => {
            const data = this._parseSSEData(e, 'thinking_chunk');
            if (!data) return;
            this.appendToThinking(data.text_chunk);
        });

        this.eventSource.addEventListener('debater_chunk', (e) => {
            const data = this._parseSSEData(e, 'debater_chunk');
            if (!data) return;
            this.appendToMessage(data.text_chunk);
        });

        this.eventSource.addEventListener('debater_finalize', () => {
            this.finalizeMessage();
        });

        this.eventSource.addEventListener('debater_end', (e) => {
            this._parseSSEData(e, 'debater_end');
            this.finalizeMessage();
        });

        this.eventSource.addEventListener('tool_call', (e) => {
            const data = this._parseSSEData(e, 'tool_call');
            if (!data) return;
            // Finalize current text bubble (if any)
            this.finalizeMessage();
            // Render search card
            this.addToolCard(data.debater_name, data.query, data.result_summary);
        });

        this.eventSource.addEventListener('round_end', (e) => {
            const data = this._parseSSEData(e, 'round_end');
            if (!data) return;
            this.addSystemMessage(`第 ${data.round_number} 轮结束`);
        });

        this.eventSource.addEventListener('debate_paused', (e) => {
            this._parseSSEData(e, 'debate_paused');
            this.debatePaused = true;
            this.debateActive = true;
            this.updateUI('paused');
            // Close SSE — resume will open a new one
            if (this.eventSource) {
                this.eventSource.close();
                this.eventSource = null;
            }
            this.addSystemMessage('辩论已暂停');
        });

        this.eventSource.addEventListener('debate_end', (e) => {
            const data = this._parseSSEData(e, 'debate_end');
            if (!data) return;
            this.debateActive = false;
            this.debatePaused = false;
            this.updateUI('stopped');
            this.eventSource.close();
            this.eventSource = null;
            const reasonMap = { 'Max rounds reached': '已达到最大轮次' };
            this.addSystemMessage(`辩论结束：${reasonMap[data.reason] || data.reason}`);

            // Auto-trigger judge when debate ends naturally (max rounds reached)
            if (data.reason === 'Max rounds reached') {
                this.requestJudge();
            }
        });

        this.eventSource.addEventListener('judge_chunk', (e) => {
            const data = this._parseSSEData(e, 'judge_chunk');
            if (!data) return;

            // Create judge message if not exists
            if (!this.currentMessageEl || !this.currentMessageEl.dataset.judge) {
                this.createMessage('裁判', '#10b981', '⚖️', 'judge');
                this.currentMessageEl.dataset.judge = 'true';
            }

            this.appendToMessage(data.text_chunk);
        });

        this.eventSource.addEventListener('judge_result', (e) => {
            this._parseSSEData(e, 'judge_result');
            this.finalizeMessage();
            // Judge is done — close SSE connection
            if (this.eventSource) {
                this.eventSource.close();
                this.eventSource = null;
            }
        });

        this.eventSource.onerror = (e) => {
            console.error('SSE error:', e);
            if (this.eventSource) {
                this.eventSource.close();
                this.eventSource = null;
            }
        };
    }

    createMessage(name, color, avatar, type = 'debater') {
        const message = document.createElement('div');
        const isConsecutive = (this._lastSpeakerName === name);
        message.className = isConsecutive ? 'message ai continuation' : 'message ai';
        message.dataset.speaker = name;

        const time = new Date().toLocaleTimeString();

        const header = document.createElement('div');
        header.className = 'message-header';

        if (!isConsecutive) {
            const avatarEl = document.createElement('span');
            avatarEl.className = 'message-avatar';
            avatarEl.textContent = avatar;
            header.appendChild(avatarEl);

            const senderEl = document.createElement('span');
            senderEl.className = 'message-sender';
            senderEl.style.color = this.sanitizeColor(color);
            senderEl.textContent = name;
            header.appendChild(senderEl);
        }

        const timeEl = document.createElement('span');
        timeEl.className = 'message-time';
        timeEl.textContent = time;
        header.appendChild(timeEl);

        message.appendChild(header);
        // Don't create message-content yet - wait for actual content

        this.messages.appendChild(message);
        this.currentMessageContainer = message; // Store the container, not content
        this.currentMessageEl = null; // Will be created when content arrives
        this._lastSpeakerName = name;
    }

    appendToMessage(text) {
        if (!this.currentMessageContainer) {
            // No active message container — create one
            this.createMessage(
                this._currentDebaterName || 'Unknown',
                this._currentDebaterColor || '#333333',
                this._currentDebaterAvatar || '💬',
                'debater'
            );
        }

        // Create message-content if it doesn't exist yet
        if (!this.currentMessageEl) {
            const content = document.createElement('div');
            content.className = 'message-content';
            this.currentMessageContainer.appendChild(content);
            this.currentMessageEl = content;
        }

        const raw = (this.currentMessageEl.dataset.raw || '') + text;
        this.currentMessageEl.dataset.raw = raw;
        this.currentMessageEl.innerHTML = this.renderContent(raw);
        this.scrollToBottom();
    }

    appendToThinking(text) {
        // Ensure message container exists
        if (!this.currentMessageContainer) {
            this.createMessage(
                this._currentDebaterName || 'Unknown',
                this._currentDebaterColor || '#333333',
                this._currentDebaterAvatar || '💬',
                'debater'
            );
        }

        // Create thinking section if it doesn't exist
        if (!this.currentThinkingEl) {
            const thinkingSection = document.createElement('div');
            thinkingSection.className = 'thinking-section';

            const header = document.createElement('div');
            header.className = 'thinking-header';
            header.style.cursor = 'pointer';

            const toggle = document.createElement('span');
            toggle.className = 'thinking-toggle';
            toggle.textContent = '▼';

            const label = document.createElement('span');
            label.className = 'thinking-label';
            label.textContent = ' 💭 thinking...';

            header.appendChild(toggle);
            header.appendChild(label);

            const thinkingSpan = document.createElement('div');
            thinkingSpan.className = 'thinking-text';

            thinkingSection.appendChild(header);
            thinkingSection.appendChild(thinkingSpan);

            // Append to message container (thinking is independent of message-content)
            this.currentMessageContainer.appendChild(thinkingSection);

            this.currentThinkingEl = thinkingSection;
        }

        // Append text to thinking span
        const thinkingText = this.currentThinkingEl.querySelector('.thinking-text');
        thinkingText.textContent += text;
        this.scrollToBottom();
    }

    finalizeMessage() {
        // Handle thinking section collapse
        if (this.currentThinkingEl) {
            const thinkingHeader = this.currentThinkingEl.querySelector('.thinking-header');
            const thinkingText = this.currentThinkingEl.querySelector('.thinking-text');
            const hasThinking = thinkingText && thinkingText.textContent.trim();

            if (hasThinking) {
                thinkingText.classList.add('thinking-collapsed');
                thinkingHeader.querySelector('.thinking-toggle').textContent = '▶';
                thinkingHeader.querySelector('.thinking-label').textContent = ' 💭 thinking';

                // Add click handler for toggle
                thinkingHeader.onclick = () => {
                    const collapsed = thinkingText.classList.toggle('thinking-collapsed');
                    thinkingHeader.querySelector('.thinking-toggle').textContent = collapsed ? '▶' : '▼';
                };
            }
        }

        // Handle message-content rendering (if it exists)
        if (this.currentMessageEl) {
            const raw = this.currentMessageEl.dataset.raw || '';
            this.currentMessageEl.innerHTML = this.renderContent(raw);
        }

        // Clear state
        this.currentThinkingEl = null;
        this.currentMessageEl = null;
        this.currentMessageContainer = null;
    }

    addSystemMessage(text) {
        const message = document.createElement('div');
        message.className = 'message system';

        const content = document.createElement('div');
        content.className = 'message-content';
        content.textContent = text;

        message.appendChild(content);
        this.messages.appendChild(message);
    }

    addUserMessage(text) {
        const message = document.createElement('div');
        message.className = 'message user';

        const time = new Date().toLocaleTimeString();

        const header = document.createElement('div');
        header.className = 'message-header';

        const avatarEl = document.createElement('span');
        avatarEl.className = 'message-avatar';
        avatarEl.textContent = '👤';

        const senderEl = document.createElement('span');
        senderEl.className = 'message-sender';
        senderEl.textContent = '你';

        const timeEl = document.createElement('span');
        timeEl.className = 'message-time';
        timeEl.textContent = time;

        header.appendChild(avatarEl);
        header.appendChild(senderEl);
        header.appendChild(timeEl);

        const content = document.createElement('div');
        content.className = 'message-content';
        content.textContent = text;

        message.appendChild(header);
        message.appendChild(content);
        this.messages.appendChild(message);
    }

    addToolCard(debaterName, query, resultSummary) {
        const message = document.createElement('div');
        const isConsecutive = (this._lastSpeakerName === debaterName);
        message.className = isConsecutive ? 'message ai tool-card continuation' : 'message ai tool-card';
        message.dataset.speaker = debaterName;

        const header = document.createElement('div');
        header.className = 'message-header';

        if (!isConsecutive) {
            const avatarEl = document.createElement('span');
            avatarEl.className = 'message-avatar';
            avatarEl.textContent = this._currentDebaterAvatar || '🔍';
            header.appendChild(avatarEl);

            const senderEl = document.createElement('span');
            senderEl.className = 'message-sender';
            senderEl.style.color = this.sanitizeColor(this._currentDebaterColor || '#333333');
            senderEl.textContent = debaterName;
            header.appendChild(senderEl);
        }

        const timeEl = document.createElement('span');
        timeEl.className = 'message-time';
        timeEl.textContent = new Date().toLocaleTimeString();
        header.appendChild(timeEl);

        const content = document.createElement('div');
        content.className = 'tool-card-content';

        const label = document.createElement('div');
        label.className = 'tool-card-label';
        label.title = 'Click to expand/collapse results';
        label.style.cursor = 'pointer';

        const toggle = document.createElement('span');
        toggle.className = 'tool-card-toggle';
        toggle.textContent = '▶';

        const labelText = document.createTextNode(' 🔍 Searched: ');

        const querySpan = document.createElement('span');
        querySpan.textContent = query;

        label.appendChild(toggle);
        label.appendChild(labelText);
        label.appendChild(querySpan);

        const results = document.createElement('div');
        results.className = 'tool-card-results tool-card-collapsed';
        results.innerHTML = this.renderContent(resultSummary || '');

        label.addEventListener('click', () => {
            const collapsed = results.classList.toggle('tool-card-collapsed');
            label.querySelector('.tool-card-toggle').textContent = collapsed ? '▶' : '▼';
        });

        content.appendChild(label);
        content.appendChild(results);

        message.appendChild(header);
        message.appendChild(content);
        this.messages.appendChild(message);
        this._lastSpeakerName = debaterName;
        this.scrollToBottom();
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    sanitizeColor(color) {
        return /^#[0-9a-fA-F]{6}$/.test(color) ? color : '#333333';
    }

    renderContent(raw) {
        try {
            // Protect [[Name]] patterns from marked.js before parsing.
            // marked treats [[ as link reference syntax and mangles them.
            const mentions = [];
            const sanitized = raw.replace(/\[\[([^\]]+)\]\]/g, (match, name) => {
                mentions.push(name);
                return `%%MENTION_${mentions.length - 1}%%`;
            });
            // marked.parse() renders markdown to HTML.
            // Raw HTML in the input is escaped by our custom renderer (see top of file).
            const html = marked.parse(sanitized);
            // Restore mentions as highlighted badges
            return html.replace(/%%MENTION_(\d+)%%/g, (_, i) => {
                return `<span class="mention">${this.escapeHtml(mentions[parseInt(i)])}</span>`;
            });
        } catch (err) {
            console.error('marked.parse failed, falling back to escaped text:', err);
            return this.escapeHtml(raw);
        }
    }

    scrollToBottom() {
        // Only auto-scroll if user is near the bottom (within 150px).
        // If they scrolled up to read, don't force them back down.
        const threshold = 150;
        const distFromBottom = this.messages.scrollHeight - this.messages.scrollTop - this.messages.clientHeight;
        if (distFromBottom < threshold) {
            this.messages.scrollTop = this.messages.scrollHeight;
        }
    }

    async stopDebate() {
        try {
            const response = await fetch('/api/debate/stop', { method: 'POST' });

            if (!response.ok) {
                const error = await response.json().catch(() => ({}));
                throw new Error(error.detail || '暂停辩论失败');
            }

            // State update is handled by the 'debate_paused' SSE event

        } catch (error) {
            console.error('Failed to stop debate:', error);
            alert(error.message);
        }
    }

    async resumeDebate() {
        try {
            const response = await fetch('/api/debate/resume', { method: 'POST' });

            if (!response.ok) {
                const error = await response.json().catch(() => ({}));
                throw new Error(error.detail || '继续辩论失败');
            }

            this.debatePaused = false;
            this.updateUI('debating');
            this.connectSSE();

        } catch (error) {
            console.error('Failed to resume debate:', error);
            alert(error.message);
        }
    }

    async sendUserMessage() {
        const text = this.userInput.value.trim();
        if (!text) return;

        try {
            const response = await fetch('/api/debate/message', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: text })
            });

            if (!response.ok) {
                const error = await response.json().catch(() => ({}));
                throw new Error(error.detail || '发送消息失败');
            }

            this.addUserMessage(text);
            this.userInput.value = '';

        } catch (error) {
            console.error('Failed to send message:', error);
            alert(error.message);
        }
    }

    async requestJudge() {
        try {
            const response = await fetch('/api/debate/judge', { method: 'POST' });

            if (!response.ok) {
                const error = await response.json().catch(() => ({}));
                throw new Error(error.detail || '请求裁判失败');
            }

            // Reconnect SSE to receive judge events
            // (previous SSE was closed when debate ended)
            this.connectSSE();

        } catch (error) {
            console.error('Failed to request judge:', error);
            alert(error.message);
        }
    }

    downloadChat() {
        const topic = this.chatTitle.textContent;
        const msgEls = this.messages.querySelectorAll('.message');
        if (msgEls.length === 0) {
            alert('没有可下载的消息。');
            return;
        }

        const isDark = document.documentElement.classList.contains('dark');

        const bg = isDark ? '#121217' : '#f5f1ea';
        const fg = isDark ? '#e4e0d8' : '#1a1714';
        const msgBg = isDark ? '#24242f' : '#fff';
        const userBg = isDark ? 'linear-gradient(135deg,rgba(122,148,174,.12),#24242f)' : 'linear-gradient(135deg,rgba(45,62,80,.07),#fff)';
        const border = isDark ? '#2e2e3e' : '#ddd7cc';
        const muted = isDark ? '#706a60' : '#9a9183';

        let body = '';
        msgEls.forEach(el => {
            if (el.classList.contains('system')) {
                const text = el.querySelector('.message-content')?.textContent || '';
                body += `<div class="sys-msg">${this.escapeHtml(text)}</div>\n`;
            } else {
                const avatar = el.querySelector('.message-avatar')?.textContent || '';
                const sender = el.querySelector('.message-sender')?.textContent || '';
                const color = el.querySelector('.message-sender')?.style.color || '#333';
                const time = el.querySelector('.message-time')?.textContent || '';
                // Tool cards use .tool-card-content, regular messages use .message-content
                // Use raw dataset for debater messages (pre-markdown) when available,
                // otherwise fall back to textContent for safety
                const contentEl = el.querySelector('.message-content') ||
                                  el.querySelector('.tool-card-content');
                // Extract thinking text if present
                const thinkingEl = el.querySelector('.thinking-text');
                let thinkingContent = '';
                if (thinkingEl) {
                    thinkingContent = `<div style="color:${muted};font-size:.82rem;font-style:italic;margin-bottom:8px;padding:6px 10px;background:${bg};border-radius:6px">💭 ${this.escapeHtml(thinkingEl.textContent)}</div>`;
                }
                let content;
                if (el.classList.contains('user') || el.classList.contains('system')) {
                    content = this.escapeHtml(contentEl?.textContent || '');
                } else if (contentEl?.dataset?.raw) {
                    content = this.renderContent(contentEl.dataset.raw);
                } else {
                    content = this.escapeHtml(contentEl?.textContent || '');
                }
                const isUser = el.classList.contains('user');
                const isToolCard = el.classList.contains('tool-card');
                const cls = isUser ? 'user-msg' : (isToolCard ? 'tool-msg' : 'debater-msg');
                body += `<div class="${cls}">
  <div class="msg-header"><span class="avatar">${this.escapeHtml(avatar)}</span> <span class="sender" style="color:${color}">${this.escapeHtml(sender)}</span> <span class="time">${this.escapeHtml(time)}</span></div>
  <div class="msg-body">${thinkingContent}${content}</div>
</div>\n`;
            }
        });

        const html = `<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8"><title>${this.escapeHtml(topic)}</title>
<style>
  body{font-family:'Outfit',system-ui,sans-serif;max-width:800px;margin:40px auto;padding:0 20px;background:${bg};color:${fg};line-height:1.7}
  h1{font-family:'Playfair Display',Georgia,serif;font-size:1.4rem;text-align:center;padding-bottom:16px;border-bottom:2px solid #c0503a;margin-bottom:28px}
  .debater-msg,.user-msg,.tool-msg{margin-bottom:22px}
  .msg-header{font-size:.82rem;margin-bottom:4px}
  .msg-header .avatar{font-size:1rem}
  .msg-header .sender{font-family:'Playfair Display',Georgia,serif;font-weight:700;font-size:.78rem;letter-spacing:.04em}
  .msg-header .time{color:${muted};font-size:.72rem;margin-left:6px}
  .msg-body{background:${msgBg};padding:14px 18px;border-radius:12px;border-left:3px solid #c0503a;box-shadow:0 1px 3px rgba(80,65,40,.06);font-size:.93rem}
  .user-msg .msg-body{border-left-color:#2d3e50;background:${userBg}}
  .sys-msg{text-align:center;color:${muted};font-style:italic;font-size:.84rem;margin:12px 0}
  .sys-msg::before,.sys-msg::after{content:' — ';color:${border}}
  .tool-msg .msg-body{border-left:1px dashed ${border};background:${bg};font-size:.85rem;color:${muted};padding:10px 14px}
  .tool-card-label{font-weight:500;color:${fg};margin-bottom:8px}
  .tool-card-results{margin-top:8px;padding:8px 12px;background:${msgBg};border-radius:6px;font-size:.82rem}
</style></head><body>
<h1>${this.escapeHtml(topic)}</h1>
${body}
</body></html>`;

        const blob = new Blob([html], { type: 'text/html' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `debate-${Date.now()}.html`;
        a.click();
        URL.revokeObjectURL(url);
    }

    async addCustomDebater() {
        const name = this.customName.value.trim();
        const color = this.customColor.value;
        const avatar = this.customAvatar.value.trim() || '💬';
        const stance = this.customStance.value;
        const personality = this.customPersonality.value.trim();

        if (!name) {
            alert('请输入辩手名称');
            return;
        }

        if (!personality) {
            alert('请输入性格描述');
            return;
        }

        try {
            const response = await fetch('/api/debaters', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    name,
                    color,
                    avatar,
                    stance,
                    personality
                })
            });

            if (!response.ok) {
                const error = await response.json().catch(() => ({}));
                throw new Error(error.detail || '创建辩手失败');
            }

            // Clear form
            this.customName.value = '';
            this.customAvatar.value = '';
            this.customPersonality.value = '';

            // Reload debater list
            await this.loadDebaters();

        } catch (error) {
            console.error('Failed to create debater:', error);
            alert(error.message);
        }
    }

    updateUI(state) {
        // state: 'idle', 'debating', 'paused', 'stopped'

        switch (state) {
            case 'idle':
                this.startBtn.disabled = false;
                this.stopBtn.disabled = true;
                this.resumeBtn.disabled = true;
                this.userInput.disabled = true;
                this.sendBtn.disabled = true;
                this.judgeBtn.disabled = true;
                this.judgeBtn.hidden = true;
                break;

            case 'debating':
                this.startBtn.disabled = true;
                this.stopBtn.disabled = false;
                this.resumeBtn.disabled = true;
                this.userInput.disabled = false;
                this.sendBtn.disabled = false;
                this.judgeBtn.disabled = true;
                this.judgeBtn.hidden = true;
                this.downloadBtn.disabled = false;
                break;

            case 'paused':
                this.startBtn.disabled = true;
                this.stopBtn.disabled = true;
                this.resumeBtn.disabled = false;
                this.userInput.disabled = true;
                this.sendBtn.disabled = true;
                this.judgeBtn.disabled = true;
                this.judgeBtn.hidden = true;
                this.downloadBtn.disabled = false;
                break;

            case 'stopped':
                this.startBtn.disabled = false;
                this.stopBtn.disabled = true;
                this.resumeBtn.disabled = true;
                this.userInput.disabled = true;
                this.sendBtn.disabled = true;
                this.judgeBtn.disabled = false;
                this.judgeBtn.hidden = false;
                this.downloadBtn.disabled = false;
                break;
        }
    }

    initTheme() {
        const stored = localStorage.getItem('theme');
        const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
        const dark = stored === 'dark' || (!stored && prefersDark);
        if (dark) document.documentElement.classList.add('dark');
        this._updateThemeIcon(dark);
    }

    toggleTheme() {
        const isDark = document.documentElement.classList.toggle('dark');
        localStorage.setItem('theme', isDark ? 'dark' : 'light');
        this._updateThemeIcon(isDark);
    }

    _updateThemeIcon(isDark) {
        if (this.themeToggle) this.themeToggle.textContent = isDark ? '☀️' : '🌙';
    }

    // ═══════════════════════════════════════════════════════
    // Search Tool Methods
    // ═══════════════════════════════════════════════════════

    openSearchDrawer() {
        this._indexMessages();
        this.searchDrawer.classList.add('open');
        this.searchBackdrop.classList.add('open');
        setTimeout(() => this.searchInput.focus(), 100);
    }

    closeSearchDrawer() {
        this.searchDrawer.classList.remove('open');
        this.searchBackdrop.classList.remove('open');
        this.searchInput.value = '';
        this.searchResults.innerHTML = '';
        this.searchToggleBtn.focus();
    }

    _indexMessages() {
        // Build searchable index from all rendered messages (including tool cards)
        this._messageIndex = [];
        const msgEls = this.messages.querySelectorAll('.message');
        msgEls.forEach((el, idx) => {
            // Regular messages use .message-content, tool cards use .tool-card-content
            const contentEl = el.querySelector('.message-content') ||
                              el.querySelector('.tool-card-content');
            if (!contentEl) return;

            // Prefer raw markdown text (dataset.raw) when available for better
            // matching of [[Name]] mentions and original markdown formatting.
            // Fall back to innerText for user/system messages without raw data.
            const text = contentEl.dataset.raw || contentEl.innerText || '';
            const sender = el.querySelector('.message-sender')?.textContent || '';
            const avatar = el.querySelector('.message-avatar')?.textContent || '';
            const time = el.querySelector('.message-time')?.textContent || '';
            const color = el.querySelector('.message-sender')?.style.color || '#333333';

            this._messageIndex.push({
                id: idx,
                element: el,
                text,
                sender,
                avatar,
                time,
                color
            });
        });
    }

    handleSearch() {
        const query = this.searchInput.value.trim().toLowerCase();

        if (!query) {
            this.searchResults.innerHTML = '';
            return;
        }

        // Search through indexed messages
        const matches = this._messageIndex
            .filter(msg => msg.text.toLowerCase().includes(query))
            .slice(0, 10); // Limit to 10 results

        this._renderSearchResults(matches, query);
    }

    _renderSearchResults(matches, query) {
        this.searchResults.innerHTML = '';

        if (matches.length === 0) {
            this.searchResults.innerHTML = '<div class="search-empty">没有找到匹配的消息</div>';
            return;
        }

        matches.forEach(msg => {
            const item = document.createElement('div');
            item.className = 'search-result-item';

            // Create header
            const header = document.createElement('div');
            header.className = 'search-result-header';

            const avatarEl = document.createElement('span');
            avatarEl.className = 'search-result-avatar';
            avatarEl.textContent = msg.avatar;

            const senderEl = document.createElement('span');
            senderEl.className = 'search-result-sender';
            senderEl.style.color = this.sanitizeColor(msg.color);
            senderEl.textContent = msg.sender;

            const timeEl = document.createElement('span');
            timeEl.className = 'search-result-time';
            timeEl.textContent = msg.time;

            header.appendChild(avatarEl);
            header.appendChild(senderEl);
            header.appendChild(timeEl);

            // Create preview with highlight
            const preview = document.createElement('div');
            preview.className = 'search-result-preview';
            preview.innerHTML = this._highlightText(msg.text, query);

            item.appendChild(header);
            item.appendChild(preview);

            // Click to scroll and highlight
            item.addEventListener('click', () => {
                this.closeSearchDrawer();
                this.scrollToMessage(msg.element);
            });

            this.searchResults.appendChild(item);
        });
    }

    _highlightText(text, query) {
        // Escape HTML first
        const escaped = this.escapeHtml(text);

        // Create case-insensitive regex for highlighting
        const regex = new RegExp(`(${this.escapeRegex(query)})`, 'gi');
        return escaped.replace(regex, '<span class="search-highlight">$1</span>');
    }

    escapeRegex(string) {
        return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    }

    scrollToMessage(element) {
        // Remove previous highlight
        this.messages.querySelectorAll('.message.highlight').forEach(el => {
            el.classList.remove('highlight');
        });

        // Scroll into view
        element.scrollIntoView({ behavior: 'smooth', block: 'center' });

        // Add highlight animation
        element.classList.add('highlight');

        // Remove highlight after animation completes
        setTimeout(() => {
            element.classList.remove('highlight');
        }, 2000);
    }
}

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.app = new DebateApp();
});
