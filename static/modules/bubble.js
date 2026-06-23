// bubble.js — pure DOM factories for message bubbles.
//
// No streaming state, no rAF, no incremental re-rendering: these build a DOM
// tree and return it. The streaming lifecycle (append/finalize, rAF batching)
// lives in renderer.js. Kept separate so bubble structure is unit-testable in
// isolation, and so renderer.js can shrink to just the state machine.
import { icon, sanitizeColor, formatTime } from './utils.js';
import { renderMarkdown } from './markdown.js';

/** Build the `.message.ai` shell (header + `--bubble-color`), no content yet.
 *  Caller appends skeleton/content. */
export function createDebaterBubble(debater, isConsecutive) {
    const message = document.createElement('div');
    message.className = isConsecutive ? 'message ai continuation' : 'message ai';
    message.dataset.speaker = debater.name;
    message.style.setProperty('--bubble-color', sanitizeColor(debater.color));

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
    return message;
}

/** Skeleton "正在斟酌……" placeholder, replaced on first real chunk. */
export function createSkeleton() {
    const skel = document.createElement('div');
    skel.className = 'message-skeleton';
    skel.dataset.skeleton = '1';
    skel.innerHTML = `<span class="skeleton-dots"><span></span><span></span><span></span></span><span>正在斟酌……</span>`;
    return skel;
}

/** Build a thinking section (expanded, label "思考中…"), header toggle wired.
 *  Returns the section element; the renderer updates `.thinking-text-inner`. */
export function createThinkingSection() {
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

    const toggleFn = () => {
        const collapsed = text.classList.toggle('thinking-collapsed');
        toggle.textContent = collapsed ? '▶' : '▼';
        header.setAttribute('aria-expanded', String(!collapsed));
    };
    header.addEventListener('click', toggleFn);
    header.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            toggleFn();
        }
    });

    return section;
}

/** Build a complete tool-card (检索) message: shell + content + results,
 *  label toggle wired, results expanded by default. */
export function createToolCard({ name, color, avatar, query, resultSummary, isConsecutive }) {
    const message = document.createElement('div');
    message.className = isConsecutive ? 'message ai tool-card continuation' : 'message ai tool-card';
    message.dataset.speaker = name;
    message.style.setProperty('--bubble-color', sanitizeColor(color || '#333333'));

    const header = document.createElement('div');
    header.className = 'message-header';

    if (!isConsecutive) {
        const av = document.createElement('span');
        av.className = 'message-avatar';
        av.textContent = avatar || '🔍';
        header.appendChild(av);

        const sender = document.createElement('span');
        sender.className = 'message-sender';
        sender.style.color = sanitizeColor(color || '#333');
        sender.textContent = name;
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
    label.setAttribute('aria-expanded', 'true');

    const toggle = document.createElement('span');
    toggle.className = 'tool-card-toggle';
    toggle.textContent = '▼';

    const labelText = document.createElement('span');
    labelText.textContent = '检索: ';

    const querySpan = document.createElement('span');
    querySpan.className = 'tool-card-query';
    querySpan.textContent = query || '(空)';

    const searchIcon = icon('search');
    label.append(toggle, searchIcon, labelText, querySpan);

    const results = document.createElement('div');
    results.className = 'tool-card-results';

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
    return message;
}

/** Build a system notice line (renders text-only, no markdown). */
export function createSystemMessage(text) {
    const m = document.createElement('div');
    m.className = 'message system';
    const c = document.createElement('div');
    c.className = 'message-content';
    c.textContent = text;
    m.appendChild(c);
    return m;
}

/** Build the user's own message bubble. */
export function createUserMessage(text) {
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
    return m;
}
