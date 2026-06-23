// markdown.js — configure marked, render with mention decoration
//
// Safety contract:
//   1. Raw HTML tokens are escaped (renderer.html override).
//   2. After marked produces HTML, we run a DOM-based sanitiser that strips
//      on* event-handler attributes and neutralises javascript:/vbscript:/
//      data: URLs on href/src. This closes the gap that marked alone leaves
//      on link/image URLs.
//   3. Marked is pinned to a known version (index.html) — historical
//      releases of marked have had breaking XSS regressions.
import { escapeHtml } from './utils.js';

let _configured = false;

const DANGEROUS_URL_RE = /^\s*(javascript|vbscript|file|data):/i;

function configureMarked() {
    if (_configured) return true;
    if (typeof window.marked === 'undefined') return false;

    window.marked.setOptions({
        breaks: true,
        gfm: true,
    });

    // Override raw HTML token rendering so any HTML in user/LLM input is escaped.
    // The renderer.html signature has differed between marked versions; handle both.
    window.marked.use({
        renderer: {
            html(input) {
                const text = typeof input === 'string' ? input : (input?.text ?? input?.raw ?? '');
                return escapeHtml(text);
            },
        },
    });

    _configured = true;
    return true;
}

function _sanitizeHtml(html) {
    if (typeof window === 'undefined' || typeof window.DOMParser === 'undefined') {
        return html;
    }
    const doc = new window.DOMParser().parseFromString(`<div>${html}</div>`, 'text/html');
    const root = doc.body.firstChild;
    if (!root) return html;
    const elems = root.querySelectorAll('*');
    elems.forEach((el) => {
        for (const attr of [...el.attributes]) {
            const name = attr.name.toLowerCase();
            const value = attr.value || '';
            if (name.startsWith('on')) {
                el.removeAttribute(attr.name);
            } else if ((name === 'href' || name === 'src' || name === 'xlink:href') &&
                       DANGEROUS_URL_RE.test(value)) {
                el.setAttribute(attr.name, '#');
            }
        }
    });
    return root.innerHTML;
}

// Try configure immediately; will retry inside renderMarkdown if marked loads later.
configureMarked();

/**
 * Render markdown with custom mention decoration.
 * Safe against raw HTML injection via the renderer.html override plus
 * a DOM-based sanitiser pass that strips on* handlers and dangerous URLs.
 * Falls back to plain-text rendering if marked is unavailable.
 */
export function renderMarkdown(raw) {
    if (!raw) return '';
    const ready = configureMarked();
    if (!ready) {
        // marked not yet loaded — degrade gracefully
        return escapeHtml(raw).replace(/\n/g, '<br>');
    }

    try {
        // Protect [[Name]] mentions from marked's link-ref handling before
        // markdown processing.
        const mentions = [];
        const sanitized = String(raw).replace(/\[\[([^\]]+)\]\]/g, (_, name) => {
            mentions.push(name);
            return `\u0000MENTION_${mentions.length - 1}\u0000`;
        });

        let html = window.marked.parse(sanitized);

        // Expand mention placeholders after marked is done so nothing
        // re-escapes the resulting <span>s.
        html = html.replace(/\u0000MENTION_(\d+)\u0000/g, (_, i) => {
            const name = mentions[parseInt(i, 10)] ?? '';
            return `<span class="mention">${escapeHtml(name)}</span>`;
        });

        return _sanitizeHtml(html);
    } catch (err) {
        console.error('renderMarkdown failed:', err);
        return escapeHtml(raw);
    }
}
