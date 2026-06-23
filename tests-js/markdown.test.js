// tests-js/markdown.test.js
import test from 'node:test';
import assert from 'node:assert/strict';
import { setupDom } from './helpers/jsdom-env.js';

setupDom();

// marked stub that respects the renderer.html() override the way real marked
// does — escape raw HTML through it.
const _renderers = [];
globalThis.window.marked = {
    setOptions: () => {},
    use: (config) => {
        if (config && config.renderer) _renderers.push(config.renderer);
    },
    parse: (s) => {
        // Run any HTML occurrences through registered renderer.html overrides
        // before treating the rest as paragraphs. The regex avoids matching
        // null bytes (placeholder sentinels) so we don't corrupt them.
        const escaped = String(s).replace(/<[^>\u0000]+>/g, (tag) => {
            for (const r of _renderers) {
                if (typeof r.html === 'function') return r.html(tag);
            }
            return tag;
        });
        const paras = escaped.split(/\n\n+/).map((p) => `<p>${p.replace(/\n/g, '<br>')}</p>`);
        return paras.join('');
    },
};

const { renderMarkdown } = await import('../static/modules/markdown.js');

test('renders plain markdown', () => {
    const html = renderMarkdown('hello');
    assert.match(html, /hello/);
});

test('escapes raw HTML in input (xss guard)', () => {
    const html = renderMarkdown('<script>alert(1)</script>');
    assert.ok(!html.includes('<script>'), `xss leaked: ${html}`);
});

test('[[Name]] mentions are wrapped in <span class="mention">', () => {
    const html = renderMarkdown('Hi [[Alice]]!');
    assert.match(html, /<span class="mention">Alice<\/span>/);
});

test('falsy input returns empty string', () => {
    assert.equal(renderMarkdown(''), '');
    assert.equal(renderMarkdown(null), '');
    assert.equal(renderMarkdown(undefined), '');
});
