// toast.js — non-blocking notification system
import { icon, refreshIcons } from './utils.js';

const ICONS = {
    success: 'check-circle-2',
    error:   'alert-circle',
    info:    'info',
    warn:    'alert-triangle',
};

const DEFAULT_DURATION = 3500;
const MAX_TOASTS = 4;

let container = null;

function ensureContainer() {
    if (container && document.body.contains(container)) return container;
    container = document.createElement('div');
    container.className = 'toast-container';
    container.setAttribute('role', 'region');
    container.setAttribute('aria-live', 'polite');
    container.setAttribute('aria-label', '通知');
    document.body.appendChild(container);
    return container;
}

function dismiss(el) {
    if (!el || el.dataset.removing === '1') return;
    el.dataset.removing = '1';
    el.classList.add('removing');
    el.addEventListener('animationend', () => el.remove(), { once: true });
}

function show(message, type = 'info', { duration = DEFAULT_DURATION } = {}) {
    const root = ensureContainer();

    // Cap stack size. Let `dismiss` run its animation; the slot frees as
    // soon as the animationend handler removes the node.
    while (root.children.length >= MAX_TOASTS) {
        dismiss(root.firstElementChild);
    }

    const t = document.createElement('div');
    t.className = `toast ${type}`;
    t.setAttribute('role', type === 'error' ? 'alert' : 'status');

    const iconEl = document.createElement('span');
    iconEl.className = 'toast-icon';
    iconEl.appendChild(icon(ICONS[type] || 'info'));

    const msgEl = document.createElement('span');
    msgEl.className = 'toast-message';
    msgEl.textContent = String(message ?? '');

    const closeBtn = document.createElement('button');
    closeBtn.className = 'toast-close';
    closeBtn.type = 'button';
    closeBtn.setAttribute('aria-label', '关闭');
    closeBtn.appendChild(icon('x'));
    closeBtn.addEventListener('click', () => dismiss(t));

    t.append(iconEl, msgEl, closeBtn);
    root.appendChild(t);
    refreshIcons();

    let timer = null;
    const startTimer = () => {
        if (duration > 0) timer = setTimeout(() => dismiss(t), duration);
    };
    const stopTimer = () => {
        if (timer) {
            clearTimeout(timer);
            timer = null;
        }
    };

    t.addEventListener('mouseenter', stopTimer);
    t.addEventListener('mouseleave', startTimer);
    startTimer();

    return t;
}

export const toast = {
    success: (msg, opts) => show(msg, 'success', opts),
    error:   (msg, opts) => show(msg, 'error', opts),
    info:    (msg, opts) => show(msg, 'info', opts),
    warn:    (msg, opts) => show(msg, 'warn', opts),
    /** Dismiss a specific toast element returned by show/info/warn/etc. */
    dismiss: (el) => dismiss(el),
};
