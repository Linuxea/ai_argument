class DebateApp {
    constructor() {
        this.eventSource = null;
        this.currentMessageEl = null;
        this.debateActive = false;
        this.debatePaused = false;
        this.init();
    }

    async init() {
        this.bindElements();
        this.bindEventListeners();
        this.loadSettings();
        await this.loadDebaters();
    }

    bindElements() {
        // Topic input
        this.topicInput = document.getElementById('topic-input');

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

        debaters.forEach(debater => {
            const item = document.createElement('div');
            item.className = 'debater-item';
            item.innerHTML = `
                <input type="checkbox" id="debater-${debater.name}" value="${debater.name}">
                <span class="debater-avatar">${debater.avatar}</span>
                <span class="debater-name">${debater.name}</span>
                <span class="debater-stance" style="color: ${debater.color}">${debater.stance}</span>
            `;
            this.debaterList.appendChild(item);
        });
    }

    async startDebate() {
        const topic = this.topicInput.value.trim();
        if (!topic) {
            alert('Please enter a debate topic');
            return;
        }

        const selectedDebaters = this.getSelectedDebaters();
        if (selectedDebaters.length < 2) {
            alert('Please select at least 2 debaters');
            return;
        }

        try {
            // Clear messages
            this.messages.innerHTML = '';
            this.chatTitle.textContent = topic;

            // Start debate
            const response = await fetch('/api/debate/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    topic: topic,
                    debater_names: selectedDebaters
                })
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to start debate');
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
            this.addSystemMessage(`Round ${data.round_number} complete`);
        });

        this.eventSource.addEventListener('debate_end', (e) => {
            const data = JSON.parse(e.data);
            this.debateActive = false;
            this.debatePaused = false;
            this.updateUI('stopped');
            this.eventSource.close();
            this.eventSource = null;
            this.addSystemMessage(`Debate ended: ${data.reason}`);
        });

        this.eventSource.addEventListener('judge_chunk', (e) => {
            const data = JSON.parse(e.data);

            // Create judge message if not exists
            if (!this.currentMessageEl || !this.currentMessageEl.dataset.judge) {
                this.createMessage('Judge', '#10b981', '⚖️', 'judge');
                this.currentMessageEl.dataset.judge = 'true';
            }

            this.appendToMessage(data.text_chunk);
        });

        this.eventSource.addEventListener('judge_result', (e) => {
            const data = JSON.parse(e.data);
            this.finalizeMessage();
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

        message.innerHTML = `
            <div class="message-header">
                <span class="message-avatar">${avatar}</span>
                <span class="message-sender" style="color: ${color}">${name}</span>
                <span class="message-time">${time}</span>
            </div>
            <div class="message-content"></div>
        `;

        this.messages.appendChild(message);
        this.currentMessageEl = message.querySelector('.message-content');
        this.scrollToBottom();
    }

    appendToMessage(text) {
        if (this.currentMessageEl) {
            this.currentMessageEl.textContent += text;
            this.scrollToBottom();
        }
    }

    finalizeMessage() {
        if (this.currentMessageEl) {
            const raw = this.currentMessageEl.textContent;
            this.currentMessageEl.innerHTML = marked.parse(raw);
        }
        this.currentMessageEl = null;
    }

    addSystemMessage(text) {
        const message = document.createElement('div');
        message.className = 'message system';

        message.innerHTML = `
            <div class="message-content">${text}</div>
        `;

        this.messages.appendChild(message);
        this.scrollToBottom();
    }

    addUserMessage(text) {
        const message = document.createElement('div');
        message.className = 'message user';

        const time = new Date().toLocaleTimeString();

        message.innerHTML = `
            <div class="message-header">
                <span class="message-avatar">👤</span>
                <span class="message-sender">You</span>
                <span class="message-time">${time}</span>
            </div>
            <div class="message-content">${this.escapeHtml(text)}</div>
        `;

        this.messages.appendChild(message);
        this.scrollToBottom();
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    scrollToBottom() {
        this.messages.scrollTop = this.messages.scrollHeight;
    }

    async stopDebate() {
        try {
            const response = await fetch('/api/debate/stop', { method: 'POST' });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to stop debate');
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
                throw new Error(error.detail || 'Failed to resume debate');
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
                throw new Error(error.detail || 'Failed to send message');
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
                throw new Error(error.detail || 'Failed to request judge');
            }

            // Judge response will come through SSE

        } catch (error) {
            console.error('Failed to request judge:', error);
            alert(error.message);
        }
    }

    async addCustomDebater() {
        const name = this.customName.value.trim();
        const color = this.customColor.value;
        const avatar = this.customAvatar.value.trim() || '💬';
        const stance = this.customStance.value;
        const personality = this.customPersonality.value.trim();

        if (!name) {
            alert('Please enter a debater name');
            return;
        }

        if (!personality) {
            alert('Please enter a personality description');
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
                throw new Error(error.detail || 'Failed to create debater');
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
                this.judgeBtn.disabled = false;
                break;

            case 'paused':
                this.startBtn.disabled = true;
                this.stopBtn.disabled = true;
                this.resumeBtn.disabled = false;
                this.userInput.disabled = true;
                this.sendBtn.disabled = true;
                this.judgeBtn.disabled = true;
                break;

            case 'stopped':
                this.startBtn.disabled = false;
                this.stopBtn.disabled = true;
                this.resumeBtn.disabled = true;
                this.userInput.disabled = true;
                this.sendBtn.disabled = true;
                this.judgeBtn.disabled = true;
                break;
        }
    }

    loadSettings() {
        const apiUrl = localStorage.getItem('api_url');
        const apiKey = localStorage.getItem('api_key');
        const modelName = localStorage.getItem('model_name');

        if (apiUrl) this.apiUrl.value = apiUrl;
        if (apiKey) this.apiKey.value = apiKey;
        if (modelName) this.modelName.value = modelName;

        // Sync cached settings to backend on page load
        if (apiUrl || apiKey || modelName) {
            fetch('/api/settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    api_url: this.apiUrl.value,
                    api_key: this.apiKey.value,
                    model_name: this.modelName.value
                })
            }).catch(err => console.error('Failed to sync settings:', err));
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
                throw new Error(error.detail || 'Failed to save settings');
            }

            // Also cache to localStorage for page reloads
            localStorage.setItem('api_url', this.apiUrl.value);
            localStorage.setItem('api_key', this.apiKey.value);
            localStorage.setItem('model_name', this.modelName.value);

            alert('Settings saved and applied.');
        } catch (error) {
            console.error('Failed to save settings:', error);
            alert(error.message);
        }
    }
}

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.app = new DebateApp();
});
