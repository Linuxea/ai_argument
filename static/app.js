class DebateApp {
    constructor() {
        this.eventSource = null;
        this.currentMessageEl = null;
        this.debateActive = false;
        this.debatePaused = false;
        this.init();
    }

    async init() {
        this.initTheme();
        this.bindElements();
        this.bindEventListeners();
        this.loadSettings();
        await this.loadDebaters();
    }

    bindElements() {
        // Topic input
        this.topicInput = document.getElementById('topic-input');
        this.maxRoundsInput = document.getElementById('max-rounds');

        // Debater list
        this.debaterList = document.getElementById('debater-list');

        // API settings
        this.apiUrl = document.getElementById('api-url');
        this.apiKey = document.getElementById('api-key');
        this.modelName = document.getElementById('model-name');
        this.saveSettingsBtn = document.getElementById('save-settings-btn');

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

        // Theme
        this.themeToggle = document.getElementById('theme-toggle');

        // Settings panel
        this.settingsBtn = document.getElementById('settings-btn');
        this.settingsClose = document.getElementById('settings-close');
        this.settingsPanel = document.getElementById('settings-panel');
        this.settingsBackdrop = document.getElementById('settings-backdrop');
    }

    bindEventListeners() {
        // Control buttons
        this.startBtn.addEventListener('click', () => this.startDebate());
        this.stopBtn.addEventListener('click', () => this.stopDebate());
        this.resumeBtn.addEventListener('click', () => this.resumeDebate());

        // Settings
        this.saveSettingsBtn.addEventListener('click', () => this.saveSettings());

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

        // Settings panel
        this.settingsBtn.addEventListener('click', () => this.openSettings());
        this.settingsClose.addEventListener('click', () => this.closeSettings());
        this.settingsBackdrop.addEventListener('click', () => this.closeSettings());
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.settingsPanel.classList.contains('open')) {
                this.closeSettings();
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
            // Sync current settings to backend before starting
            await fetch('/api/settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    api_url: this.apiUrl.value,
                    api_key: this.apiKey.value,
                    model_name: this.modelName.value
                })
            });

            // Clear messages
            this.messages.innerHTML = '';
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
                const error = await response.json();
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

    connectSSE() {
        this.eventSource = new EventSource('/api/debate/stream');

        this.eventSource.addEventListener('debater_start', (e) => {
            const data = JSON.parse(e.data);
            this.createMessage(data.debater_name, data.color, data.avatar, 'debater');
        });

        this.eventSource.addEventListener('debater_chunk', (e) => {
            const data = JSON.parse(e.data);
            this.appendToMessage(data.text_chunk);
        });

        this.eventSource.addEventListener('debater_end', (e) => {
            const data = JSON.parse(e.data);
            this.finalizeMessage();
        });

        this.eventSource.addEventListener('round_end', (e) => {
            const data = JSON.parse(e.data);
            this.addSystemMessage(`第 ${data.round_number} 轮结束`);
        });

        this.eventSource.addEventListener('debate_end', (e) => {
            const data = JSON.parse(e.data);
            this.debateActive = false;
            this.debatePaused = false;
            this.updateUI('stopped');
            this.eventSource.close();
            this.eventSource = null;
            const reasonMap = { 'Max rounds reached': '已达到最大轮次', 'Stopped by user': '用户手动停止' };
            this.addSystemMessage(`辩论结束：${reasonMap[data.reason] || data.reason}`);

            // Auto-trigger judge when debate ends naturally (max rounds reached)
            if (data.reason === 'Max rounds reached') {
                this.requestJudge();
            }
        });

        this.eventSource.addEventListener('judge_chunk', (e) => {
            const data = JSON.parse(e.data);

            // Create judge message if not exists
            if (!this.currentMessageEl || !this.currentMessageEl.dataset.judge) {
                this.createMessage('裁判', '#10b981', '⚖️', 'judge');
                this.currentMessageEl.dataset.judge = 'true';
            }

            this.appendToMessage(data.text_chunk);
        });

        this.eventSource.addEventListener('judge_result', (e) => {
            const data = JSON.parse(e.data);
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
        message.className = 'message ai';

        const time = new Date().toLocaleTimeString();

        const header = document.createElement('div');
        header.className = 'message-header';

        const avatarEl = document.createElement('span');
        avatarEl.className = 'message-avatar';
        avatarEl.textContent = avatar;

        const senderEl = document.createElement('span');
        senderEl.className = 'message-sender';
        senderEl.style.color = this.sanitizeColor(color);
        senderEl.textContent = name;

        const timeEl = document.createElement('span');
        timeEl.className = 'message-time';
        timeEl.textContent = time;

        header.appendChild(avatarEl);
        header.appendChild(senderEl);
        header.appendChild(timeEl);

        const content = document.createElement('div');
        content.className = 'message-content';

        message.appendChild(header);
        message.appendChild(content);

        this.messages.appendChild(message);
        this.currentMessageEl = content;
    }

    appendToMessage(text) {
        if (this.currentMessageEl) {
            const raw = (this.currentMessageEl.dataset.raw || '') + text;
            this.currentMessageEl.dataset.raw = raw;
            this.currentMessageEl.innerHTML = this.renderContent(raw);
        }
    }

    finalizeMessage() {
        if (this.currentMessageEl) {
            const raw = this.currentMessageEl.dataset.raw || '';
            this.currentMessageEl.innerHTML = this.renderContent(raw);
        }
        this.currentMessageEl = null;
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

        message.innerHTML = `
            <div class="message-header">
                <span class="message-avatar">👤</span>
                <span class="message-sender">你</span>
                <span class="message-time">${time}</span>
            </div>
            <div class="message-content">${this.escapeHtml(text)}</div>
        `;

        this.messages.appendChild(message);
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
        const html = marked.parse(raw);
        // Replace [[Name]] with highlighted mention badges
        return html.replace(/\[\[([^\]]+)\]\]/g, '<span class="mention">$1</span>');
    }

    scrollToBottom() {
        this.messages.scrollTop = this.messages.scrollHeight;
    }

    async stopDebate() {
        try {
            const response = await fetch('/api/debate/stop', { method: 'POST' });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || '暂停辩论失败');
            }

            this.debatePaused = true;
            this.updateUI('paused');

        } catch (error) {
            console.error('Failed to stop debate:', error);
            alert(error.message);
        }
    }

    async resumeDebate() {
        try {
            const response = await fetch('/api/debate/resume', { method: 'POST' });

            if (!response.ok) {
                const error = await response.json();
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
                const error = await response.json();
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
                const error = await response.json();
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
                const content = el.querySelector('.message-content')?.innerHTML || '';
                const isUser = el.classList.contains('user');
                const cls = isUser ? 'user-msg' : 'debater-msg';
                body += `<div class="${cls}">
  <div class="msg-header"><span class="avatar">${avatar}</span> <span class="sender" style="color:${color}">${this.escapeHtml(sender)}</span> <span class="time">${time}</span></div>
  <div class="msg-body">${content}</div>
</div>\n`;
            }
        });

        const bg = isDark ? '#121217' : '#f5f1ea';
        const fg = isDark ? '#e4e0d8' : '#1a1714';
        const msgBg = isDark ? '#24242f' : '#fff';
        const userBg = isDark ? 'linear-gradient(135deg,rgba(122,148,174,.12),#24242f)' : 'linear-gradient(135deg,rgba(45,62,80,.07),#fff)';
        const border = isDark ? '#2e2e3e' : '#ddd7cc';
        const muted = isDark ? '#706a60' : '#9a9183';

        const html = `<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8"><title>${this.escapeHtml(topic)}</title>
<style>
  body{font-family:'Outfit',system-ui,sans-serif;max-width:800px;margin:40px auto;padding:0 20px;background:${bg};color:${fg};line-height:1.7}
  h1{font-family:'Playfair Display',Georgia,serif;font-size:1.4rem;text-align:center;padding-bottom:16px;border-bottom:2px solid #c0503a;margin-bottom:28px}
  .debater-msg,.user-msg{margin-bottom:22px}
  .msg-header{font-size:.82rem;margin-bottom:4px}
  .msg-header .avatar{font-size:1rem}
  .msg-header .sender{font-family:'Playfair Display',Georgia,serif;font-weight:700;font-size:.78rem;letter-spacing:.04em}
  .msg-header .time{color:${muted};font-size:.72rem;margin-left:6px}
  .msg-body{background:${msgBg};padding:14px 18px;border-radius:12px;border-left:3px solid #c0503a;box-shadow:0 1px 3px rgba(80,65,40,.06);font-size:.93rem}
  .user-msg .msg-body{border-left-color:#2d3e50;background:${userBg}}
  .sys-msg{text-align:center;color:${muted};font-style:italic;font-size:.84rem;margin:12px 0}
  .sys-msg::before,.sys-msg::after{content:' — ';color:${border}}
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
                const error = await response.json();
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
                break;

            case 'debating':
                this.startBtn.disabled = true;
                this.stopBtn.disabled = false;
                this.resumeBtn.disabled = true;
                this.userInput.disabled = false;
                this.sendBtn.disabled = false;
                this.judgeBtn.disabled = true;
                this.downloadBtn.disabled = false;
                break;

            case 'paused':
                this.startBtn.disabled = true;
                this.stopBtn.disabled = true;
                this.resumeBtn.disabled = false;
                this.userInput.disabled = true;
                this.sendBtn.disabled = true;
                this.judgeBtn.disabled = true;
                this.downloadBtn.disabled = false;
                break;

            case 'stopped':
                this.startBtn.disabled = false;
                this.stopBtn.disabled = true;
                this.resumeBtn.disabled = true;
                this.userInput.disabled = true;
                this.sendBtn.disabled = true;
                this.judgeBtn.disabled = false;
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

    openSettings() {
        this.settingsPanel.classList.add('open');
        this.settingsBackdrop.classList.add('open');
        this.settingsBackdrop.setAttribute('aria-hidden', 'false');
        setTimeout(() => this.apiUrl.focus(), 50);
    }

    closeSettings() {
        this.settingsPanel.classList.remove('open');
        this.settingsBackdrop.classList.remove('open');
        this.settingsBackdrop.setAttribute('aria-hidden', 'true');
        this.settingsBtn.focus();
    }

    async loadSettings() {
        // Clear stale defaults from previous versions
        const staleDefaults = ['http://localhost:11434/v1', 'ollama', 'llama3'];
        ['api_url', 'api_key', 'model_name'].forEach((key, i) => {
            if (localStorage.getItem(key) === staleDefaults[i]) {
                localStorage.removeItem(key);
            }
        });

        const apiUrl = localStorage.getItem('api_url');
        const apiKey = localStorage.getItem('api_key');
        const modelName = localStorage.getItem('model_name');
        const maxRounds = localStorage.getItem('max_rounds');

        if (apiUrl) this.apiUrl.value = apiUrl;
        if (apiKey) this.apiKey.value = apiKey;
        if (modelName) this.modelName.value = modelName;
        if (maxRounds) this.maxRoundsInput.value = maxRounds;

        // Sync cached settings to backend on reload
        if (apiUrl || apiKey || modelName) {
            fetch('/api/settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    api_url: apiUrl,
                    api_key: apiKey,
                    model_name: modelName
                })
            }).then(() => this.fetchModels())
              .catch(err => console.error('Failed to sync settings:', err));
        }
    }

    async saveSettings() {
        try {
            const response = await fetch('/api/settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    api_url: this.apiUrl.value,
                    api_key: this.apiKey.value,
                    model_name: this.modelName.value
                })
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || '保存设置失败');
            }

            // Also cache to localStorage for page reloads
            localStorage.setItem('api_url', this.apiUrl.value);
            localStorage.setItem('api_key', this.apiKey.value);
            localStorage.setItem('model_name', this.modelName.value);
            localStorage.setItem('max_rounds', this.maxRoundsInput.value);

            // Fetch available models and populate dropdown
            await this.fetchModels();

            alert('设置已保存并生效。');
        } catch (error) {
            console.error('Failed to save settings:', error);
            alert(error.message);
        }
    }

    async fetchModels() {
        try {
            const resp = await fetch('/api/models');
            if (!resp.ok) {
                const err = await resp.json();
                console.error('Failed to fetch models:', err.detail);
                return;
            }
            const data = await resp.json();
            const current = this.modelName.value;
            this.modelName.innerHTML = '';
            data.models.forEach(id => {
                const opt = document.createElement('option');
                opt.value = id;
                opt.textContent = id;
                if (id === current) opt.selected = true;
                this.modelName.appendChild(opt);
            });
            if (!current && data.models.length > 0) {
                this.modelName.value = data.models[0];
            }
        } catch (err) {
            console.error('Failed to fetch models:', err);
        }
    }
}

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.app = new DebateApp();
});
