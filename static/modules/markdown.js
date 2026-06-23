// markdown.js — configure marked, render with mentions/concession decoration
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
 * Render markdown with custom mention/concession decoration.
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
        // Protect [[Name]] mentions from marked's link-ref handling, and
        // detect [退让]...[/退让] blocks before markdown processing so we can
        // decide whether to wrap them inline (single-line) or as a block
        // (multi-paragraph) — span/p nesting violates HTML.
        const mentions = [];
        const concessions = [];
        let sanitized = String(raw).replace(/\[\[([^\]]+)\]\]/g, (_, name) => {
            mentions.push(name);
            return `\u0000MENTION_${mentions.length - 1}\u0000`;
        });
        sanitized = sanitized.replace(/\[退让\]([\s\S]*?)\[\/退让\]/g, (_, text) => {
            concessions.push(text);
            return `\u0000CONCESSION_${concessions.length - 1}\u0000`;
        });

        let html = window.marked.parse(sanitized);

        // Expand concessions BEFORE mentions. The concession text still holds
        // mention placeholders (\u0000MENTION_N\u0000), which marked treats as
        // opaque text — so they pass through the sub-parse untouched instead
        // of being escaped by the renderer.html override (which is what
        // happened when we pre-expanded them into <span>s here: the second
        // marked.parse escaped those spans and leaked literal tag text).
        html = html.replace(/\u0000CONCESSION_(\d+)\u0000/g, (_, i) => {
            const text = concessions[parseInt(i, 10)] ?? '';
            const inner = window.marked.parse(text);
            // If marked produced a single <p>…</p> with no nested block tags,
            // render inline as <span>; otherwise wrap as a block <div> so
            // the resulting HTML stays valid (spans cannot contain blocks).
            const blockTagRe = /<(p|div|ul|ol|li|h\d|blockquote|pre|table|hr)\b/i;
            const trimmed = inner.trim();
            const single = trimmed.match(/^<p>([\s\S]*)<\/p>$/);
            if (single && !blockTagRe.test(single[1])) {
                return `<span class="concession">${single[1]}</span>`;
            }
            return `<div class="concession concession-block">${inner}</div>`;
        });

        // Expand mention placeholders only after every marked.parse is done,
        // so nothing downstream re-escapes the resulting <span>s.
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
