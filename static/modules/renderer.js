// renderer.js — streaming message renderer with rAF-batched markdown.
//
// Owns the streaming state machine (current bubble, rAF scheduling,
// append/finalize lifecycle). DOM construction is delegated to bubble.js so
// this file is just control flow, not element-by-element DOM building.
import { refreshIcons } from './utils.js';
import { renderMarkdown } from './markdown.js';
import {
    createDebaterBubble,
    createSkeleton,
    createThinkingSection,
    createToolCard,
    createSystemMessage,
    createUserMessage,
} from './bubble.js';

export class MessageRenderer {
    /**
     * @param {HTMLElement} container - messages list
     * @param {AutoScroller} scroller
     * @param {MessageStore|null} store - if given, finalised messages are
     *        recorded here as the canonical source of truth for search/export.
     */
    constructor(container, scroller, store = null) {
        this.container = container;
        this.scroller = scroller;
        this.store = store;
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
        // Drop recorded messages too — the store is the canonical history.
        this.store?.clear();
    }

    /** Show an empty-state hint. The suggestions block is populated async
     *  via setSuggestionsLoading / setSuggestions / hideSuggestions. */
    showEmptyState({ onSuggest, onRefresh } = {}) {
        const existing = this.container.querySelector('.empty-state');
        if (existing) existing.remove();

        this._onSuggest = onSuggest;

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
            <p>输入辩题、勾选两位以上的辩手，然后点击「开始辩论」。</p>
            <p class="empty-state-hint">需要灵感？试试 AI 生成的话题：</p>
            <div class="empty-state-suggestions"></div>
            <button class="empty-state-refresh" type="button" title="换一批" hidden>
                <span data-lucide="refresh-cw" class="icon-slot"></span>
                <span>换一批</span>
            </button>
        `;

        const refreshBtn = wrap.querySelector('.empty-state-refresh');
        refreshBtn.addEventListener('click', () => {
            if (typeof onRefresh === 'function') onRefresh();
        });

        // Insert before sentinel
        this.container.insertBefore(wrap, this.scroller.sentinel);
        refreshIcons();
    }

    /** Render shimmering skeleton pills while suggestions load. */
    setSuggestionsLoading() {
        const wrap = this.container.querySelector('.empty-state');
        if (!wrap) return;
        const sug = wrap.querySelector('.empty-state-suggestions');
        sug.innerHTML = '';
        for (let i = 0; i < 3; i++) {
            const s = document.createElement('span');
            s.className = 'empty-state-suggestion skeleton';
            sug.appendChild(s);
        }
        const refresh = wrap.querySelector('.empty-state-refresh');
        if (refresh) refresh.hidden = false;
        refresh.disabled = true;
        refreshIcons();
    }

    /** Render real topic suggestion buttons. */
    setSuggestions(topics) {
        const wrap = this.container.querySelector('.empty-state');
        if (!wrap) return;
        const sug = wrap.querySelector('.empty-state-suggestions');
        sug.innerHTML = '';
        const list = Array.isArray(topics) ? topics : [];
        for (const t of list) {
            const b = document.createElement('button');
            b.className = 'empty-state-suggestion';
            b.type = 'button';
            b.textContent = t;
            b.addEventListener('click', () => this._onSuggest?.(t));
            sug.appendChild(b);
        }
        const refresh = wrap.querySelector('.empty-state-refresh');
        if (refresh) {
            refresh.hidden = false;
            refresh.disabled = false;
        }
    }

    /** Hide the whole suggestions block (intro + pills + refresh) on failure. */
    hideSuggestions() {
        const wrap = this.container.querySelector('.empty-state');
        if (!wrap) return;
        wrap.querySelector('.empty-state-hint')?.remove();
        wrap.querySelector('.empty-state-suggestions')?.remove();
        wrap.querySelector('.empty-state-refresh')?.remove();
    }

    hideEmptyState() {
        this.container.querySelector('.empty-state')?.remove();
    }

    /** Create a skeleton placeholder while waiting for first chunk. */
    startDebaterTurn(debater) {
        this.hideEmptyState();
        this.currentDebater = debater;

        const isConsecutive = (this._lastSpeakerName === debater.name && this._lastSpeakerType === 'debater');
        const message = createDebaterBubble(debater, isConsecutive);
        message.appendChild(createSkeleton());

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
            const section = createThinkingSection();
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
        // Thinking section
        let thinkingHasContent = false;
        if (this.currentThinkingEl) {
            const inner = this.currentThinkingEl.querySelector('.thinking-text-inner');
            thinkingHasContent = !!(inner?.dataset.raw || '').trim();
            if (thinkingHasContent) {
                const toggle = this.currentThinkingEl.querySelector('.thinking-toggle');
                const label = this.currentThinkingEl.querySelector('.thinking-label');
                const header = this.currentThinkingEl.querySelector('.thinking-header');
                // Keep the thinking section expanded by default; the user can
                // still collapse it via the header toggle in bubble.js.
                toggle.textContent = '▼';
                label.textContent = '思考过程';
                header?.setAttribute('aria-expanded', 'true');
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

        // Record the finalised message in the store (canonical source of truth
        // for search/export). Only if the bubble was kept — finalize() above
        // removes empty ones. Judge turns are tagged via dataset.judge.
        if (this.store && this.currentMessageContainer?.isConnected) {
            const c = this.currentMessageContainer;
            const thinkingRaw = c.querySelector('.thinking-text-inner')?.dataset.raw || '';
            const textRaw = this.currentMessageEl?.dataset.raw || '';
            const searchable = [textRaw, thinkingRaw].filter(Boolean).join('\n');
            this.store.add({
                el: c,
                role: c.dataset.judge === 'true' ? 'judge' : 'debater',
                speaker: this.currentDebater?.name || '',
                color: this.currentDebater?.color || '',
                avatar: this.currentDebater?.avatar || '',
                time: c.querySelector('.message-time')?.textContent || '',
                text: searchable,
            });
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
        const m = createSystemMessage(text);
        this.container.insertBefore(m, this.scroller.sentinel);
        this.store?.add({
            el: m, role: 'system', speaker: '', color: '', avatar: '', time: '', text,
        });
        // Reset speaker grouping after a system divider
        this._lastSpeakerName = null;
        this._lastSpeakerType = null;
        this.scroller.schedule({ counted: true });
    }

    /** Append a user message. */
    addUser(text) {
        const m = createUserMessage(text);
        this.container.insertBefore(m, this.scroller.sentinel);
        this.store?.add({
            el: m,
            role: 'user',
            speaker: '你',
            color: '',
            avatar: '👤',
            time: m.querySelector('.message-time')?.textContent || '',
            text,
        });

        this._lastSpeakerName = '__user';
        this._lastSpeakerType = 'user';
        this.scroller.scrollToBottom();
    }

    /** Add a tool-call card (web search result). */
    addToolCard({ debaterName, query, resultSummary }) {
        const isConsecutive = (this._lastSpeakerName === debaterName && this._lastSpeakerType === 'debater');
        const message = createToolCard({
            name: debaterName,
            color: this.currentDebater?.color,
            avatar: this.currentDebater?.avatar,
            query,
            resultSummary,
            isConsecutive,
        });
        this.container.insertBefore(message, this.scroller.sentinel);
        this.store?.add({
            el: message,
            role: 'tool',
            speaker: debaterName,
            color: this.currentDebater?.color || '',
            avatar: this.currentDebater?.avatar || '',
            time: message.querySelector('.message-time')?.textContent || '',
            text: [query, resultSummary].filter(Boolean).join('\n'),
        });
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
