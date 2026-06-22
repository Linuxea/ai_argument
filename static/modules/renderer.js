// renderer.js — streaming message renderer with rAF-batched markdown
import { icon, refreshIcons, sanitizeColor, formatTime } from './utils.js';
import { renderMarkdown } from './markdown.js';

export class MessageRenderer {
    /**
     * @param {HTMLElement} container - messages list
     * @param {AutoScroller} scroller
     */
    constructor(container, scroller) {
        this.container = container;
        this.scroller = scroller;
        this._lastSpeakerName = null;
        this._lastSpeakerType = null;

        // Active streaming state
        this.currentMessageContainer = null;
        this.currentMessageEl = null;        // .message-content div
        this.currentThinkingEl = null;
        this.currentDebater = null;          // { name, color, avatar }

        this._rafPending = false;
        this._pendingTextRender = false;
        this._pendingThinkingRender = false;
    }

    /** Clear everything (new debate). */
    reset() {
        this.container.querySelectorAll('.message, .message-skeleton, .empty-state').forEach((n) => n.remove());
        this._lastSpeakerName = null;
        this._lastSpeakerType = null;
        this.currentMessageContainer = null;
        this.currentMessageEl = null;
        this.currentThinkingEl = null;
        this.currentDebater = null;
        // sentinel may have been removed; re-attach
        this.scroller.pinSentinel();
    }

    /** Show an empty-state hint. */
    showEmptyState({ onSuggest } = {}) {
        const existing = this.container.querySelector('.empty-state');
        if (existing) existing.remove();

        const wrap = document.createElement('div');
        wrap.className = 'empty-state';

        wrap.innerHTML = `
            <svg class="empty-state-illustration" viewBox="0 0 120 120" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <path d="M60 12 V22" stroke-width="1.5"/>
                <rect x="22" y="22" width="76" height="7" rx="3.5" fill="currentColor" stroke="none" opacity="0.9"/>
                <path d="M34 29 H86 V92 H34 Z" stroke-width="2.5"/>
                <rect x="22" y="92" width="76" height="7" rx="3.5" fill="currentColor" stroke="none" opacity="0.9"/>
                <path d="M50 42 H70" stroke-width="3"/>
                <path d="M60 38 V66" stroke-width="3"/>
                <path d="M50 54 H70" stroke-width="2.5"/>
                <path d="M50 74 Q60 70 70 74" stroke-width="2.5"/>
            </svg>
            <h3>开启一场辩论</h3>
            <p>输入辩题、勾选两位以上的辩手，然后点击「开始辩论」。<br>需要灵感？试试下面的话题：</p>
            <div class="empty-state-suggestions"></div>
        `;

        const suggestions = ['人工智能是否会取代程序员？', '远程办公是更好的工作方式吗？', '应该全面禁用一次性塑料吗？'];
        const sug = wrap.querySelector('.empty-state-suggestions');
        for (const s of suggestions) {
            const b = document.createElement('button');
            b.className = 'empty-state-suggestion';
            b.type = 'button';
            b.textContent = s;
            b.addEventListener('click', () => onSuggest?.(s));
            sug.appendChild(b);
        }

        // Insert before sentinel
        this.container.insertBefore(wrap, this.scroller.sentinel);
    }

    hideEmptyState() {
        this.container.querySelector('.empty-state')?.remove();
    }

    /** Create a skeleton placeholder while waiting for first chunk. */
    startDebaterTurn(debater) {
        this.hideEmptyState();
        this.currentDebater = debater;

        const message = document.createElement('div');
        const isConsecutive = (this._lastSpeakerName === debater.name && this._lastSpeakerType === 'debater');
        message.className = isConsecutive ? 'message ai continuation' : 'message ai';
        message.dataset.speaker = debater.name;

        const header = document.createElement('div');
        header.className = 'message-header';

        if (!isConsecutive) {
            const av = document.createElement('span');
            av.className = 'message-avatar';
            av.textContent = debater.avatar || '💬';
            header.appendChild(av);

            const sender = document.createElement('span');
            sender.className = 'message-sender';
            sender.style.color = sanitizeColor(debater.color);
            sender.textContent = debater.name;
            header.appendChild(sender);
        }

        const timeEl = document.createElement('span');
        timeEl.className = 'message-time';
        timeEl.textContent = formatTime();
        header.appendChild(timeEl);

        message.appendChild(header);

        // Skeleton placeholder — replaced on first chunk
        const skel = document.createElement('div');
        skel.className = 'message-skeleton';
        skel.dataset.skeleton = '1';
        skel.innerHTML = `<span class="skeleton-dots"><span></span><span></span><span></span></span><span>正在斟酌……</span>`;
        message.appendChild(skel);

        this.container.insertBefore(message, this.scroller.sentinel);
        this.currentMessageContainer = message;
        this.currentMessageEl = null;
        this.currentThinkingEl = null;
        this._lastSpeakerName = debater.name;
        this._lastSpeakerType = 'debater';

        // Counted: a new bubble counts as "1 new message" for the unseen
        // badge. Subsequent chunks within this bubble are NOT counted so the
        // badge doesn't inflate to 99+ during a single debater's streaming.
        this.scroller.schedule({ counted: true });
    }

    _removeSkeleton() {
        if (!this.currentMessageContainer) return;
        const skel = this.currentMessageContainer.querySelector('[data-skeleton]');
        if (skel) skel.remove();
    }

    /** Ensure we have a container (in case start event was missed). */
    _ensureContainer() {
        if (!this.currentMessageContainer) {
            if (!this.currentDebater) {
                // No prior startDebaterTurn — refuse to silently attribute the
                // chunk to a stale debater. Caller will see appendChunk()
                // become a no-op until a proper debater_start event arrives.
                return false;
            }
            this.startDebaterTurn(this.currentDebater);
        }
        return true;
    }

    _ensureContentEl() {
        if (!this.currentMessageEl) {
            this._removeSkeleton();
            const el = document.createElement('div');
            el.className = 'message-content';
            this.currentMessageContainer.appendChild(el);
            this.currentMessageEl = el;
        }
    }

    /** Append a streamed text chunk. Renders in next rAF. */
    appendChunk(text) {
        if (!text) return;
        if (!this._ensureContainer()) return;
        this._ensureContentEl();
        const prev = this.currentMessageEl.dataset.raw || '';
        this.currentMessageEl.dataset.raw = prev + text;
        this._pendingTextRender = true;
        this._scheduleRender();
    }

    /** Append a streamed thinking chunk. */
    appendThinking(text) {
        if (!text) return;
        if (!this._ensureContainer()) return;
        this._removeSkeleton();

        if (!this.currentThinkingEl) {
            const section = document.createElement('div');
            section.className = 'thinking-section';

            const header = document.createElement('div');
            header.className = 'thinking-header';
            header.setAttribute('role', 'button');
            header.setAttribute('tabindex', '0');
            header.setAttribute('aria-expanded', 'true');

            const toggle = document.createElement('span');
            toggle.className = 'thinking-toggle';
            toggle.textContent = '▼';

            const label = document.createElement('span');
            label.className = 'thinking-label';
            label.textContent = '思考中…';

            header.append(toggle, label);

            const text = document.createElement('div');
            text.className = 'thinking-text';

            const inner = document.createElement('div');
            inner.className = 'thinking-text-inner';
            text.appendChild(inner);

            section.append(header, text);

            // Click & keyboard toggle
            const toggleFn = () => {
                const collapsed = text.classList.toggle('thinking-collapsed');
                toggle.style.transform = collapsed ? '' : 'rotate(0deg)';
                header.setAttribute('aria-expanded', String(!collapsed));
            };
            header.addEventListener('click', toggleFn);
            header.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    toggleFn();
                }
            });

            // Insert before any message-content
            this.currentMessageContainer.appendChild(section);
            this.currentThinkingEl = section;
        }

        const inner = this.currentThinkingEl.querySelector('.thinking-text-inner');
        inner.dataset.raw = (inner.dataset.raw || '') + text;
        this._pendingThinkingRender = true;
        this._scheduleRender();
    }

    _scheduleRender() {
        if (this._rafPending) return;
        this._rafPending = true;
        requestAnimationFrame(() => {
            this._rafPending = false;
            if (this._pendingTextRender && this.currentMessageEl) {
                const raw = this.currentMessageEl.dataset.raw || '';
                // Render markdown + streaming cursor sentinel
                this.currentMessageEl.innerHTML = renderMarkdown(raw) + '<span class="cursor" aria-hidden="true"></span>';
                this._pendingTextRender = false;
            }
            if (this._pendingThinkingRender && this.currentThinkingEl) {
                const inner = this.currentThinkingEl.querySelector('.thinking-text-inner');
                inner.textContent = inner.dataset.raw || '';
                this._pendingThinkingRender = false;
            }
            // Not counted: the new-message bump for this bubble happened in
            // ``startDebaterTurn``; subsequent chunks update content within
            // the same bubble and shouldn't bump the unseen-message badge.
            this.scroller.schedule();
        });
    }

    /** Finalize the active message (called at debater_finalize / debater_end). */
    finalize() {
        // Collapse thinking section
        let thinkingHasContent = false;
        if (this.currentThinkingEl) {
            const inner = this.currentThinkingEl.querySelector('.thinking-text-inner');
            thinkingHasContent = !!(inner?.dataset.raw || '').trim();
            if (thinkingHasContent) {
                const text = this.currentThinkingEl.querySelector('.thinking-text');
                const toggle = this.currentThinkingEl.querySelector('.thinking-toggle');
                const label = this.currentThinkingEl.querySelector('.thinking-label');
                const header = this.currentThinkingEl.querySelector('.thinking-header');
                text.classList.add('thinking-collapsed');
                toggle.textContent = '▶';
                label.textContent = '思考过程';
                header?.setAttribute('aria-expanded', 'false');
            } else {
                this.currentThinkingEl.remove();
                this.currentThinkingEl = null;
            }
        }

        // Final markdown render (drop cursor)
        if (this.currentMessageEl) {
            const raw = this.currentMessageEl.dataset.raw || '';
            if (!raw.trim() && !thinkingHasContent) {
                this.currentMessageContainer?.remove();
            } else {
                this.currentMessageEl.innerHTML = renderMarkdown(raw);
            }
        } else if (this.currentMessageContainer) {
            const onlySkeleton = !!this.currentMessageContainer.querySelector('[data-skeleton]');
            if (onlySkeleton || !thinkingHasContent) {
                this.currentMessageContainer.remove();
            }
        }

        this.currentMessageContainer = null;
        this.currentMessageEl = null;
        this.currentThinkingEl = null;
        this._pendingTextRender = false;
        this._pendingThinkingRender = false;
        // Note: `currentDebater` is intentionally preserved so the speaker
        // identity survives across the finalize→tool_call→appendChunk sequence
        // inside a single turn. ``endTurn()`` (called on debater_end) clears
        // it explicitly to prevent stale-attribution bugs across turns.
    }

    /** Hard end-of-turn: like finalize() but also forgets the debater identity
     * so subsequent stray chunks don't get attributed to them. */
    endTurn() {
        this.finalize();
        this.currentDebater = null;
    }

    /** Add a system notice line. */
    addSystem(text) {
        const m = document.createElement('div');
        m.className = 'message system';
        const c = document.createElement('div');
        c.className = 'message-content';
        c.textContent = text;
        m.appendChild(c);
        this.container.insertBefore(m, this.scroller.sentinel);
        // Reset speaker grouping after a system divider
        this._lastSpeakerName = null;
        this._lastSpeakerType = null;
        this.scroller.schedule({ counted: true });
    }

    /** Append a user message. */
    addUser(text) {
        const m = document.createElement('div');
        m.className = 'message user';

        const header = document.createElement('div');
        header.className = 'message-header';

        const avatar = document.createElement('span');
        avatar.className = 'message-avatar';
        avatar.textContent = '👤';

        const sender = document.createElement('span');
        sender.className = 'message-sender';
        sender.textContent = '你';

        const time = document.createElement('span');
        time.className = 'message-time';
        time.textContent = formatTime();

        header.append(avatar, sender, time);

        const content = document.createElement('div');
        content.className = 'message-content';
        content.textContent = text;

        m.append(header, content);
        this.container.insertBefore(m, this.scroller.sentinel);

        this._lastSpeakerName = '__user';
        this._lastSpeakerType = 'user';
        this.scroller.scrollToBottom();
    }

    /** Add a tool-call card (web search result). */
    addToolCard({ debaterName, query, resultSummary }) {
        const message = document.createElement('div');
        const isConsecutive = (this._lastSpeakerName === debaterName && this._lastSpeakerType === 'debater');
        message.className = isConsecutive ? 'message ai tool-card continuation' : 'message ai tool-card';
        message.dataset.speaker = debaterName;

        const header = document.createElement('div');
        header.className = 'message-header';

        if (!isConsecutive) {
            const av = document.createElement('span');
            av.className = 'message-avatar';
            av.textContent = this.currentDebater?.avatar || '🔍';
            header.appendChild(av);

            const sender = document.createElement('span');
            sender.className = 'message-sender';
            sender.style.color = sanitizeColor(this.currentDebater?.color || '#333');
            sender.textContent = debaterName;
            header.appendChild(sender);
        }

        const time = document.createElement('span');
        time.className = 'message-time';
        time.textContent = formatTime();
        header.appendChild(time);

        const content = document.createElement('div');
        content.className = 'tool-card-content';

        const label = document.createElement('div');
        label.className = 'tool-card-label';
        label.setAttribute('role', 'button');
        label.setAttribute('tabindex', '0');
        label.setAttribute('aria-expanded', 'false');

        const toggle = document.createElement('span');
        toggle.className = 'tool-card-toggle';
        toggle.textContent = '▶';

        const labelText = document.createElement('span');
        labelText.textContent = '检索: ';

        const querySpan = document.createElement('span');
        querySpan.className = 'tool-card-query';
        querySpan.textContent = query || '(空)';

        const searchIcon = icon('search');
        label.append(toggle, searchIcon, labelText, querySpan);

        const results = document.createElement('div');
        results.className = 'tool-card-results tool-card-collapsed';

        const inner = document.createElement('div');
        inner.className = 'tool-card-results-inner';
        inner.innerHTML = renderMarkdown(resultSummary || '');
        results.appendChild(inner);

        const toggleFn = () => {
            const collapsed = results.classList.toggle('tool-card-collapsed');
            toggle.textContent = collapsed ? '▶' : '▼';
            label.setAttribute('aria-expanded', String(!collapsed));
        };
        label.addEventListener('click', toggleFn);
        label.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                toggleFn();
            }
        });

        content.append(label, results);
        message.append(header, content);
        this.container.insertBefore(message, this.scroller.sentinel);
        this._lastSpeakerName = debaterName;
        this._lastSpeakerType = 'debater';
        this.scroller.schedule({ counted: true });
        refreshIcons();
    }

    /** Begin / append to a judge message. */
    appendJudgeChunk(text) {
        if (!this.currentMessageContainer || !this.currentMessageContainer.dataset.judge) {
            // Reset speaker tracking so judge gets its own header even if last debater was named "裁判"
            this._lastSpeakerName = null;
            this._lastSpeakerType = null;
            this.startDebaterTurn({ name: '裁判', color: '#55704c', avatar: '⚖️' });
            this.currentMessageContainer.classList.add('judge');
            this.currentMessageContainer.dataset.judge = 'true';
            this._lastSpeakerType = 'judge';
        }
        this.appendChunk(text);
    }
}
