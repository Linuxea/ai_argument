// search.js — searches messages, jumps to matches; uses <dialog>
import { debounce, escapeHtml, escapeRegex, sanitizeColor, refreshIcons } from './utils.js';

export class SearchPanel {
    constructor({ dialog, input, results, openBtn, store }) {
        this.dialog = dialog;
        this.input = input;
        this.results = results;
        this.openBtn = openBtn;
        this.store = store;

        this._handleSearch = debounce(() => this._runSearch(), 140);
        this.input.addEventListener('input', this._handleSearch);

        openBtn.addEventListener('click', () => this.open());

        // Close on backdrop click
        dialog.addEventListener('click', (e) => {
            if (e.target === dialog) this.close();
        });

        dialog.addEventListener('close', () => {
            this.input.value = '';
            this.results.innerHTML = '';
            this._renderEmptyHint();
        });

        this._renderEmptyHint();
    }

    open() {
        if (this.dialog.open) return;
        this._indexMessages();
        try {
            this.dialog.showModal();
        } catch {
            this.dialog.show();
        }
        setTimeout(() => this.input.focus(), 50);
    }

    close() {
        if (this.dialog.open) this.dialog.close();
    }

    _indexMessages() {
        // Read finalised messages from the central MessageStore (DOM is no
        // longer the source of truth for search — see store.js).
        this._messageIndex = this.store.all()
            .filter((rec) => rec.text && rec.text.trim())
            .map((rec, idx) => ({
                id: idx,
                element: rec.el,
                text: rec.text,
                sender: rec.speaker || '',
                avatar: rec.avatar || '',
                time: rec.time || '',
                color: rec.color || '',
            }));
    }

    _runSearch() {
        const q = this.input.value.trim().toLowerCase();
        if (!q) {
            this._renderEmptyHint();
            return;
        }
        const matches = this._messageIndex
            .filter((m) => m.text.toLowerCase().includes(q))
            .slice(0, 20);
        this._renderResults(matches, q);
    }

    _renderEmptyHint() {
        this.results.innerHTML = '';
        const hint = document.createElement('div');
        hint.className = 'search-empty-state';
        const total = this._messageIndex?.length ?? 0;
        hint.textContent = total
            ? `共 ${total} 条消息可供搜索`
            : '暂无消息可搜索';
        this.results.appendChild(hint);
    }

    _renderResults(matches, query) {
        this.results.innerHTML = '';

        if (!matches.length) {
            const empty = document.createElement('div');
            empty.className = 'search-empty-state';
            empty.textContent = '没有找到匹配的消息';
            this.results.appendChild(empty);
            return;
        }

        const frag = document.createDocumentFragment();
        for (const m of matches) {
            const item = document.createElement('button');
            item.className = 'search-result-item';
            item.type = 'button';

            const header = document.createElement('div');
            header.className = 'search-result-header';

            const av = document.createElement('span');
            av.className = 'search-result-avatar';
            av.textContent = m.avatar;

            const sender = document.createElement('span');
            sender.className = 'search-result-sender';
            sender.style.color = sanitizeColor(m.color);
            sender.textContent = m.sender || '系统';

            const time = document.createElement('span');
            time.className = 'search-result-time';
            time.textContent = m.time;

            header.append(av, sender, time);

            const preview = document.createElement('div');
            preview.className = 'search-result-preview';
            preview.innerHTML = this._highlight(m.text, query);

            item.append(header, preview);
            item.addEventListener('click', () => {
                this.close();
                this._jumpTo(m.element);
            });

            frag.appendChild(item);
        }
        this.results.appendChild(frag);
        refreshIcons();
    }

    _highlight(text, query) {
        const escaped = escapeHtml(text);
        const re = new RegExp(`(${escapeRegex(query)})`, 'gi');
        return escaped.replace(re, '<mark class="search-highlight">$1</mark>');
    }

    _jumpTo(el) {
        // Clear any pending un-highlight timers from previous jumps so a
        // rapid second click doesn't strip the highlight we're about to add.
        if (this._highlightTimers) {
            for (const t of this._highlightTimers) clearTimeout(t);
        }
        this._highlightTimers = [];

        // Clear any prior highlights — iterate store records instead of
        // querying DOM globally.
        for (const rec of this.store.all()) {
            rec.el?.classList?.remove('highlight');
        }
        el.scrollIntoView({ behavior: 'smooth', block: 'center' });
        el.classList.add('highlight');
        const t = setTimeout(() => el.classList.remove('highlight'), 2000);
        this._highlightTimers.push(t);
    }
}
