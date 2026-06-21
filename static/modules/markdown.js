// markdown.js — configure marked, render with mentions/concession decoration
import { escapeHtml } from './utils.js';

let _configured = false;

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

// Try configure immediately; will retry inside renderMarkdown if marked loads later.
configureMarked();

/**
 * Render markdown with custom mention/concession decoration.
 * Safe against raw HTML injection via the renderer.html override.
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
        // Protect [[Name]] mentions from marked's link-ref handling.
        const mentions = [];
        const sanitized = String(raw).replace(/\[\[([^\]]+)\]\]/g, (_, name) => {
            mentions.push(name);
            return `\u0000MENTION_${mentions.length - 1}\u0000`;
        });

        let html = window.marked.parse(sanitized);

        html = html.replace(/\u0000MENTION_(\d+)\u0000/g, (_, i) => {
            const name = mentions[parseInt(i, 10)] ?? '';
            return `<span class="mention">${escapeHtml(name)}</span>`;
        });

        html = html.replace(/\[退让\]([\s\S]*?)\[\/退让\]/g, (_, text) =>
            `<span class="concession">${text}</span>`,
        );

        return html;
    } catch (err) {
        console.error('renderMarkdown failed:', err);
        return escapeHtml(raw);
    }
}
