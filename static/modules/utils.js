// utils.js — shared utilities
export function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = String(text ?? '');
    return div.innerHTML;
}

export function sanitizeColor(color) {
    return /^#[0-9a-fA-F]{6}$/.test(color) ? color : '#a67b32';
}

export function escapeRegex(string) {
    return String(string).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

export function debounce(fn, delay) {
    let timer = null;
    function debounced(...args) {
        if (timer) clearTimeout(timer);
        timer = setTimeout(() => {
            timer = null;
            fn.apply(this, args);
        }, delay);
    }
    debounced.cancel = () => {
        if (timer) {
            clearTimeout(timer);
            timer = null;
        }
    };
    return debounced;
}

export function formatTime(date = new Date()) {
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
}

export function uid() {
    return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 7)}`;
}

// Render a lucide icon by name. Returns an element placeholder that lucide
// upgrades to an <svg>. If lucide never loads, we leave a tiny fallback glyph.
const ICON_FALLBACK = {
    moon: '🌙', sun: '☀️', search: '🔍', x: '✕',
    sparkles: '✨', gavel: '⚖️', download: '⬇',
    'send-horizontal': '➤', 'arrow-down': '↓',
    'grip-vertical': '⠿', user: '👤', info: 'ⓘ',
    'alert-circle': '⚠', 'alert-triangle': '⚠',
    'check-circle-2': '✓',
};

export function icon(name, attrs = {}) {
    const wrapper = document.createElement('span');
    wrapper.dataset.lucide = name;
    wrapper.className = 'icon-slot';
    // Lucide replaces innerHTML on upgrade; until then we show a text fallback
    wrapper.textContent = ICON_FALLBACK[name] || '';
    if (attrs.title) wrapper.title = attrs.title;
    if (attrs['aria-label']) wrapper.setAttribute('aria-label', attrs['aria-label']);
    return wrapper;
}

// Convert all data-lucide placeholders into svg icons.
// Called after dynamic DOM insertions.
let _rafScheduled = false;
export function refreshIcons() {
    if (_rafScheduled) return;
    _rafScheduled = true;
    requestAnimationFrame(() => {
        _rafScheduled = false;

        // Apply text fallback to any data-lucide placeholders that haven't been
        // upgraded yet (will be visible until lucide loads, or permanently if CDN fails).
        document.querySelectorAll('[data-lucide]:not(svg)').forEach((el) => {
            if (!el.textContent && !el.dataset.fallbackApplied) {
                const name = el.dataset.lucide;
                el.textContent = ICON_FALLBACK[name] || '';
                el.dataset.fallbackApplied = '1';
            }
        });

        if (window.lucide && typeof window.lucide.createIcons === 'function') {
            try {
                window.lucide.createIcons();
            } catch (err) {
                console.warn('lucide.createIcons failed:', err);
            }
        }
    });
}

// Schedule periodic retries until lucide either loads or we give up.
// Also runs once after window 'load'.
let _retryCount = 0;
function _retry() {
    if (_retryCount++ > 20) return;
    refreshIcons();
    if (!window.lucide) setTimeout(_retry, 250);
}
if (typeof window !== 'undefined') {
    if (document.readyState === 'complete') _retry();
    else window.addEventListener('load', _retry);
}
