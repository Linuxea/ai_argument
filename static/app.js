// app.js — entry module for The Salon AI debate chatroom
import { api } from './modules/api.js';
import { toast } from './modules/toast.js';
import { initTheme, toggleTheme, isDark } from './modules/theme.js';
import { renderMarkdown } from './modules/markdown.js';
import { escapeHtml, debounce, refreshIcons, formatTime } from './modules/utils.js';
import { SSEClient } from './modules/sse.js';
import { UIState } from './modules/state.js';
import { AutoScroller } from './modules/autoscroll.js';
import { MessageRenderer } from './modules/renderer.js';
import { DebaterList } from './modules/debaters.js';
import { SearchPanel } from './modules/search.js';

const STORAGE_MAX_ROUNDS = 'max_rounds';

class DebateApp {
    constructor() {
        this.sse = null;
        this.maxRounds = 10;
        this.totalRounds = 10;
        this.currentRound = 0;
        this.currentSpeaker = null;
        // Auto-judge timer reference so we can cancel it if the user navigates
        // away or starts a new debate before it fires.
        this._autoJudgeTimer = null;
        this.init();
    }

    async init() {
        this._bindElements();
        initTheme((dark) => this._updateThemeIcon(dark));
        this._bindEvents();

        this.scroller = new AutoScroller(this.messages);
        this.renderer = new MessageRenderer(this.messages, this.scroller);
        this.debaterList = new DebaterList(this.debaterListEl);
        this.search = new SearchPanel({
            dialog: this.searchDialog,
            input: this.searchInput,
            results: this.searchResults,
            openBtn: this.searchToggleBtn,
            messagesContainer: this.messages,
        });

        this.state = new UIState('idle', (s) => this._applyUIState(s));

        // Restore preferences
        const stored = localStorage.getItem(STORAGE_MAX_ROUNDS);
        if (stored && parseInt(stored, 10) > 0) {
            this.maxRoundsInput.value = stored;
        }
        this.maxRounds = this._readMaxRounds();

        await this._loadDebaters();
        this._applyUIState('idle');
        this.renderer.showEmptyState({ onSuggest: (s) => this._useSuggestion(s) });
        refreshIcons();
    }

    _bindElements() {
        // Sidebar
        this.topicInput = document.getElementById('topic-input');
        this.maxRoundsInput = document.getElementById('max-rounds');
        this.refineTopicBtn = document.getElementById('refine-topic-btn');
        this.debaterListEl = document.getElementById('debater-list');
        this.startBtn = document.getElementById('start-btn');
        this.stopBtn = document.getElementById('stop-btn');
        this.resumeBtn = document.getElementById('resume-btn');

        // Custom debater form
        this.customName = document.getElementById('custom-name');
        this.customColor = document.getElementById('custom-color');
        this.customAvatar = document.getElementById('custom-avatar');
        this.customStance = document.getElementById('custom-stance');
        this.customPersonality = document.getElementById('custom-personality');
        this.addDebaterBtn = document.getElementById('add-debater-btn');

        // Chat
        this.chatTitle = document.getElementById('chat-title');
        this.messages = document.getElementById('messages');
        this.userInput = document.getElementById('user-input');
        this.sendBtn = document.getElementById('send-btn');
        this.judgeBtn = document.getElementById('judge-btn');
        this.downloadBtn = document.getElementById('download-btn');
        this.themeToggle = document.getElementById('theme-toggle');

        // Round progress
        this.roundProgress = document.getElementById('round-progress');
        this.roundProgressFill = document.getElementById('round-progress-fill');
        this.roundInfo = document.getElementById('round-info');
        this.currentSpeakerEl = document.getElementById('current-speaker');
        this.roundBadgeEl = document.getElementById('round-badge');

        // Search
        this.searchToggleBtn = document.getElementById('search-toggle-btn');
        this.searchDialog = document.getElementById('search-dialog');
        this.searchInput = document.getElementById('search-input');
        this.searchResults = document.getElementById('search-results');
        this.searchCloseBtn = document.getElementById('search-close');

        // Connection indicator
        this.connectionIndicator = document.getElementById('connection-indicator');
    }

    _bindEvents() {
        this.startBtn.addEventListener('click', () => this._startDebate());
        this.stopBtn.addEventListener('click', () => this._stopDebate());
        this.resumeBtn.addEventListener('click', () => this._resumeDebate());
        this.refineTopicBtn.addEventListener('click', () => this._refineTopic());
        this.addDebaterBtn.addEventListener('click', () => this._addCustomDebater());
        this.sendBtn.addEventListener('click', () => this._sendUserMessage());
        this.judgeBtn.addEventListener('click', () => this._requestJudge());
        this.downloadBtn.addEventListener('click', () => this._downloadChat());
        this.themeToggle.addEventListener('click', (e) => toggleTheme(e));
        this.searchCloseBtn?.addEventListener('click', () => this.search.close());

        // Auto-grow textarea + Enter to send
        this.userInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this._sendUserMessage();
            }
        });
        const autoGrow = () => {
            this.userInput.style.height = 'auto';
            this.userInput.style.height = Math.min(this.userInput.scrollHeight, 160) + 'px';
        };
        this.userInput.addEventListener('input', autoGrow);

        // Persist max rounds
        this.maxRoundsInput.addEventListener('change', () => {
            const v = parseInt(this.maxRoundsInput.value, 10);
            if (v > 0 && v <= 50) {
                localStorage.setItem(STORAGE_MAX_ROUNDS, String(v));
                this.maxRounds = v;
            }
        });

        // Global keybinds
        document.addEventListener('keydown', (e) => {
            // Cmd/Ctrl+K → search
            if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
                e.preventDefault();
                this.search.open();
            }
        });

        // Topic Ctrl+Enter to start
        this.topicInput.addEventListener('keydown', (e) => {
            if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
                e.preventDefault();
                if (!this.startBtn.disabled) this._startDebate();
            }
        });
    }

    async _loadDebaters() {
        try {
            const debaters = await api.loadDebaters();
            this.debaterList.setDebaters(debaters);
        } catch (err) {
            console.error('Failed to load debaters:', err);
            toast.error(`加载辩手失败: ${err.message}`);
        }
    }

    _useSuggestion(topic) {
        this.topicInput.value = topic;
        this.topicInput.focus();
    }

    async _refineTopic() {
        const topic = this.topicInput.value.trim();
        if (!topic) {
            toast.warn('请先输入辩论主题');
            return;
        }
        const original = this.refineTopicBtn.innerHTML;
        this.refineTopicBtn.disabled = true;
        this.refineTopicBtn.textContent = '优化中…';
        try {
            const data = await api.refineTopic(topic);
            this.topicInput.value = data.refined_topic;
            toast.success('已优化辩题表述');
        } catch (err) {
            console.error('Failed to refine topic:', err);
            toast.error(`话题优化失败: ${err.message}`);
        } finally {
            this.refineTopicBtn.disabled = false;
            this.refineTopicBtn.innerHTML = original;
            refreshIcons();
        }
    }

    _readMaxRounds() {
        const v = parseInt(this.maxRoundsInput.value, 10);
        return Number.isFinite(v) && v > 0 ? v : 10;
    }

    _cancelAutoJudge() {
        if (this._autoJudgeTimer !== null) {
            clearTimeout(this._autoJudgeTimer);
            this._autoJudgeTimer = null;
        }
    }

    async _startDebate() {
        const topic = this.topicInput.value.trim();
        if (!topic) {
            toast.warn('请输入辩论主题');
            return;
        }
        // Respect user-arranged drag order
        const selectedOrdered = this.debaterList.getOrder().filter((name) =>
            this.debaterList.getSelected().includes(name));
        if (selectedOrdered.length < 2) {
            toast.warn('请至少选择 2 位辩手');
            return;
        }

        // Cancel any pending auto-judge from a previous debate.
        this._cancelAutoJudge();

        const maxRounds = this._readMaxRounds();
        this.maxRounds = maxRounds;
        this.totalRounds = maxRounds;

        try {
            this.renderer.reset();
            this.chatTitle.textContent = topic;
            this._setRoundProgress(0, maxRounds, null);
            this.roundProgress.classList.add('active');
            this.roundInfo.classList.add('active');

            await api.startDebate({
                topic,
                debater_names: selectedOrdered,
                max_rounds: maxRounds,
            });

            this.state.set('debating');
            this._connectSSE();
        } catch (err) {
            console.error('Failed to start debate:', err);
            toast.error(`启动辩论失败: ${err.message}`);
        }
    }

    async _stopDebate() {
        try {
            await api.stopDebate();
        } catch (err) {
            console.error('Failed to stop:', err);
            toast.error(`暂停失败: ${err.message}`);
        }
    }

    async _resumeDebate() {
        try {
            await api.resumeDebate();
            this.state.set('debating');
            this._connectSSE();
        } catch (err) {
            console.error('Failed to resume:', err);
            toast.error(`继续失败: ${err.message}`);
        }
    }

    async _sendUserMessage() {
        const text = this.userInput.value.trim();
        if (!text) return;
        try {
            await api.sendMessage(text);
            this.renderer.addUser(text);
            this.userInput.value = '';
            this.userInput.style.height = 'auto';
        } catch (err) {
            console.error('Send failed:', err);
            toast.error(`发送失败: ${err.message}`);
        }
    }

    async _requestJudge() {
        try {
            this.state.set('judging');
            await api.requestJudge();
            this._connectSSE();
        } catch (err) {
            console.error('Judge failed:', err);
            toast.error(`请求裁判失败: ${err.message}`);
            this.state.set('stopped');
        }
    }

    async _addCustomDebater() {
        const name = this.customName.value.trim();
        const color = this.customColor.value;
        const avatar = this.customAvatar.value.trim() || '💬';
        const stance = this.customStance.value;
        const personality = this.customPersonality.value.trim();

        if (!name) return toast.warn('请输入辩手名称');
        if (!personality) return toast.warn('请填写性格描述');

        try {
            await api.createDebater({ name, color, avatar, stance, personality });
            this.customName.value = '';
            this.customAvatar.value = '';
            this.customPersonality.value = '';
            await this._loadDebaters();
            toast.success(`已添加辩手「${name}」`);
        } catch (err) {
            console.error('Create debater failed:', err);
            toast.error(`创建辩手失败: ${err.message}`);
        }
    }

    // ─── SSE ───────────────────────────────────────

    _connectSSE() {
        if (this.sse) this.sse.close();
        this.sse = new SSEClient('/api/debate/stream');
        this.sse.addEventListener('event', (e) => this._handleSSEEvent(e.detail));
        this.sse.addEventListener('status', (e) => this._handleSSEStatus(e.detail));
        this.sse.connect();
    }

    _handleSSEStatus({ state }) {
        if (state === 'disconnected') {
            this._setConnectionIndicator('连接已断开');
            toast.error('与服务器的连接已断开', { duration: 5000 });
        } else if (state === 'reconnecting') {
            this._setConnectionIndicator('重新连接…');
        } else {
            this._setConnectionIndicator(null);
        }
    }

    _setConnectionIndicator(text) {
        if (!this.connectionIndicator) return;
        if (!text) {
            this.connectionIndicator.classList.remove('visible');
            return;
        }
        this.connectionIndicator.textContent = text;
        this.connectionIndicator.classList.add('visible');
    }

    _handleSSEEvent({ type, data }) {
        switch (type) {
            case 'debater_start':
                this.currentSpeaker = data.debater_name;
                this.renderer.startDebaterTurn({
                    name: data.debater_name,
                    color: data.color,
                    avatar: data.avatar,
                });
                if (typeof data.round_number === 'number') {
                    this.currentRound = data.round_number + 1;
                }
                if (typeof data.total_rounds === 'number' && data.total_rounds > 0) {
                    this.totalRounds = data.total_rounds;
                }
                this._setRoundProgress(this.currentRound, this.totalRounds, data.debater_name);
                break;

            case 'thinking_chunk':
                this.renderer.appendThinking(data.text_chunk);
                break;

            case 'debater_chunk':
                this.renderer.appendChunk(data.text_chunk);
                break;

            case 'debater_finalize':
                this.renderer.finalize();
                break;

            case 'debater_end':
                this.renderer.endTurn();
                break;

            case 'tool_call':
                this.renderer.finalize();
                this.renderer.addToolCard({
                    debaterName: data.debater_name,
                    query: data.query,
                    resultSummary: data.result_summary,
                });
                break;

            case 'round_end':
                this.renderer.addSystem(`第 ${data.round_number} 轮结束`);
                this.currentRound = data.round_number;
                this._setRoundProgress(this.currentRound, this.totalRounds, null);
                break;

            case 'debate_paused':
                this.state.set('paused');
                this.renderer.addSystem('辩论已暂停');
                break;

            case 'debate_end': {
                this.state.set('stopped');
                const reasonMap = { 'Max rounds reached': '已达到最大轮次' };
                this.renderer.addSystem(`辩论结束：${reasonMap[data.reason] || data.reason}`);
                this._setRoundProgress(this.totalRounds, this.totalRounds, null);
                if (data.reason === 'Max rounds reached') {
                    // Auto-judge after a short delay. Track the timer so we
                    // can cancel it if the user starts a new debate or
                    // navigates away before it fires.
                    this._cancelAutoJudge();
                    this._autoJudgeTimer = setTimeout(() => {
                        this._autoJudgeTimer = null;
                        // Sanity check the state in case it changed during the delay.
                        if (this.state.is('stopped')) this._requestJudge();
                    }, 400);
                }
                break;
            }

            case 'judge_chunk':
                this.renderer.appendJudgeChunk(data.text_chunk);
                break;

            case 'judge_result':
                this.renderer.finalize();
                this.state.set('stopped');
                break;

            case 'debate_error':
                this.renderer.finalize();
                this.state.set('stopped');
                toast.error(data?.message || '辩论过程中出错');
                this.renderer.addSystem(data?.message || '辩论过程中出错');
                break;

            case 'judge_error':
                this.renderer.finalize();
                this.state.set('stopped');
                toast.error(data?.message || '评判失败');
                this.renderer.addSystem(data?.message || '评判失败');
                break;
        }
    }

    _setRoundProgress(current, total, speakerName) {
        const pct = total > 0 ? Math.min(100, Math.max(0, (current / total) * 100)) : 0;
        this.roundProgressFill.style.width = pct + '%';
        if (speakerName) {
            this.currentSpeakerEl.textContent = speakerName;
            this.currentSpeakerEl.previousElementSibling?.classList.remove('hidden');
        } else if (current >= total && total > 0) {
            this.currentSpeakerEl.textContent = '已完成';
        } else {
            this.currentSpeakerEl.textContent = '等待开始…';
        }
        // Show 1-based round while a speaker is active (round 1 of N), or the
        // completed-round count when between rounds.
        const displayRound = speakerName ? Math.max(1, current) : current;
        this.roundBadgeEl.textContent = `第 ${displayRound} / ${total} 轮`;
    }

    // ─── UI state machine ──────────────────────────

    _applyUIState(state) {
        const set = (el, key, value) => {
            if (!el) return;
            el[key] = value;
        };

        switch (state) {
            case 'idle':
                set(this.startBtn,  'disabled', false);
                set(this.stopBtn,   'disabled', true);
                set(this.resumeBtn, 'disabled', true);
                set(this.userInput, 'disabled', true);
                set(this.sendBtn,   'disabled', true);
                set(this.judgeBtn,  'disabled', true);
                this.judgeBtn.hidden = true;
                set(this.downloadBtn, 'disabled', true);
                this.roundProgress.classList.remove('active');
                this.roundInfo.classList.remove('active');
                break;

            case 'debating':
                set(this.startBtn,  'disabled', true);
                set(this.stopBtn,   'disabled', false);
                set(this.resumeBtn, 'disabled', true);
                set(this.userInput, 'disabled', false);
                set(this.sendBtn,   'disabled', false);
                set(this.judgeBtn,  'disabled', true);
                this.judgeBtn.hidden = true;
                set(this.downloadBtn, 'disabled', false);
                break;

            case 'paused':
                set(this.startBtn,  'disabled', true);
                set(this.stopBtn,   'disabled', true);
                set(this.resumeBtn, 'disabled', false);
                set(this.userInput, 'disabled', true);
                set(this.sendBtn,   'disabled', true);
                set(this.judgeBtn,  'disabled', false);
                this.judgeBtn.hidden = false;
                set(this.downloadBtn, 'disabled', false);
                break;

            case 'stopped':
                set(this.startBtn,  'disabled', false);
                set(this.stopBtn,   'disabled', true);
                set(this.resumeBtn, 'disabled', true);
                set(this.userInput, 'disabled', true);
                set(this.sendBtn,   'disabled', true);
                set(this.judgeBtn,  'disabled', false);
                this.judgeBtn.hidden = false;
                set(this.downloadBtn, 'disabled', false);
                break;

            case 'judging':
                set(this.startBtn,  'disabled', true);
                set(this.stopBtn,   'disabled', true);
                set(this.resumeBtn, 'disabled', true);
                set(this.userInput, 'disabled', true);
                set(this.sendBtn,   'disabled', true);
                set(this.judgeBtn,  'disabled', true);
                this.judgeBtn.hidden = false;
                break;
        }
    }

    _updateThemeIcon(dark) {
        if (!this.themeToggle) return;
        this.themeToggle.innerHTML = '';
        const span = document.createElement('span');
        span.dataset.lucide = dark ? 'sun' : 'moon';
        span.className = 'icon-slot';
        this.themeToggle.appendChild(span);
        refreshIcons();
    }

    // ─── Download ──────────────────────────────────

    _downloadChat() {
        const topic = this.chatTitle.textContent;
        const msgEls = this.messages.querySelectorAll('.message');
        if (!msgEls.length) {
            toast.warn('没有可下载的消息');
            return;
        }

        const dark = isDark();
        const palette = dark ? {
            bg: '#0f1014', fg: '#ebe6dc', card: '#22232e', input: '#1d1e28',
            muted: '#8e8675', border: '#2e2f3d', user: 'linear-gradient(135deg,rgba(125,160,178,.14),#22232e)',
        } : {
            bg: '#f5f1ea', fg: '#1a1714', card: '#ffffff', input: '#f0ece4',
            muted: '#7a6f5d', border: '#d4c8b1', user: 'linear-gradient(135deg,rgba(62,82,96,.10),#ffffff)',
        };

        let body = '';
        msgEls.forEach((el) => {
            if (el.classList.contains('system')) {
                const text = el.querySelector('.message-content')?.textContent || '';
                body += `<div class="sys-msg">${escapeHtml(text)}</div>\n`;
                return;
            }
            const avatar = el.querySelector('.message-avatar')?.textContent || '';
            const sender = el.querySelector('.message-sender')?.textContent || '';
            const color = el.querySelector('.message-sender')?.style.color || '#333';
            const time = el.querySelector('.message-time')?.textContent || '';
            const contentEl = el.querySelector('.message-content') || el.querySelector('.tool-card-content');
            const thinkingRaw = el.querySelector('.thinking-text-inner')?.dataset.raw || '';
            const thinkingHtml = thinkingRaw
                ? `<div style="color:${palette.muted};font-size:.82rem;font-style:italic;margin-bottom:8px;padding:6px 10px;background:${palette.input};border-radius:6px">💭 ${escapeHtml(thinkingRaw)}</div>`
                : '';
            let content;
            if (el.classList.contains('user')) {
                content = escapeHtml(contentEl?.textContent || '');
            } else if (contentEl?.dataset?.raw) {
                content = renderMarkdown(contentEl.dataset.raw);
            } else {
                content = escapeHtml(contentEl?.textContent || '');
            }
            const isUser = el.classList.contains('user');
            const isTool = el.classList.contains('tool-card');
            const cls = isUser ? 'user-msg' : (isTool ? 'tool-msg' : 'debater-msg');
            body += `<div class="${cls}">
  <div class="msg-header"><span class="avatar">${escapeHtml(avatar)}</span> <span class="sender" style="color:${color}">${escapeHtml(sender)}</span> <span class="time">${escapeHtml(time)}</span></div>
  <div class="msg-body">${thinkingHtml}${content}</div>
</div>\n`;
        });

        const html = `<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8"><title>${escapeHtml(topic)}</title>
<style>
  body{font-family:Georgia,serif;max-width:780px;margin:40px auto;padding:0 20px;background:${palette.bg};color:${palette.fg};line-height:1.75}
  h1{font-size:1.5rem;text-align:center;padding-bottom:16px;border-bottom:2px solid #a67b32;margin-bottom:32px}
  .debater-msg,.user-msg,.tool-msg{margin-bottom:24px}
  .msg-header{font-size:.82rem;margin-bottom:6px}
  .msg-header .avatar{font-size:1rem}
  .msg-header .sender{font-weight:700;font-size:.85rem;letter-spacing:.04em}
  .msg-header .time{color:${palette.muted};font-size:.72rem;margin-left:8px}
  .msg-body{background:${palette.card};padding:14px 18px;border-radius:12px;border-left:3px solid #a67b32;font-size:.95rem}
  .user-msg .msg-body{border-left-color:#3e5260;background:${palette.user}}
  .sys-msg{text-align:center;color:${palette.muted};font-style:italic;font-size:.84rem;margin:14px 0}
  .sys-msg::before,.sys-msg::after{content:' — ';color:${palette.border}}
  .tool-msg .msg-body{border-left:1px dashed ${palette.border};background:${palette.input};font-size:.85rem;color:${palette.muted};padding:10px 14px}
  .mention{background:rgba(166,123,50,.14);color:#8b5a14;border-radius:4px;padding:1px 6px;font-weight:600}
  blockquote{margin:0.6em 0;padding:0.4em 0.9em;border-left:2px solid #a67b32;background:rgba(166,123,50,.10);color:${palette.muted};font-style:italic;border-radius:0 4px 4px 0}
  code{background:${palette.input};padding:1px 5px;border-radius:4px}
  pre{background:${palette.input};border:1px solid ${palette.border};border-radius:8px;padding:12px;overflow-x:auto}
</style></head><body>
<h1>${escapeHtml(topic)}</h1>
${body}
</body></html>`;

        const blob = new Blob([html], { type: 'text/html;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        const safeName = topic.replace(/[\\/:*?"<>|]/g, '_').slice(0, 60) || 'debate';
        a.download = `${safeName}-${Date.now()}.html`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
        toast.success('已下载辩论记录');
    }
}

document.addEventListener('DOMContentLoaded', () => {
    window.app = new DebateApp();
});
