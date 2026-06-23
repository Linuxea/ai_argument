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

test('B20: single-line concession is inline-wrapped', () => {
    const html = renderMarkdown('I agree: [退让]on this point you are correct[/退让], but...');
    assert.match(html, /<span class="concession">on this point you are correct<\/span>/);
});

test('B20: multi-paragraph concession must NOT produce inline-wrapping a <p> tag', () => {
    // The model returns a multi-paragraph concession. The output must be valid
    // HTML: a span (inline) cannot contain block-level <p> tags.
    const raw = 'rebuttal start\n\n[退让]Yes, on the cost issue you are right.\n\nBut that strengthens my point.[/退让]\n\nContinuing...';
    const html = renderMarkdown(raw);

    // The concession content should be rendered. We don't dictate the wrapping
    // element, but it must not be an inline <span> directly containing <p>.
    // Allow whitespace between the opening span and the first <p>.
    const invalid = /<span[^>]*class="[^"]*\bconcession\b[^"]*"[^>]*>[\s\S]*?<p\b/i;
    assert.ok(!invalid.test(html),
        `concession produced inline <span> wrapping a block <p>:\n${html}`);
});

test('B20: concession tag at start of message handled', () => {
    const html = renderMarkdown('[退让]Fair point[/退让]');
    assert.match(html, /concession/);
    assert.match(html, /Fair point/);
});

test('mentions inside concession render as real spans (not escaped tag text)', () => {
    const html = renderMarkdown('[退让]as [[Alice]] said[/退让]');
    assert.match(html, /concession/);
    // Must render a real mention span, not escaped tag text. The naive
    // /mention/ check passes even on `&lt;span class="mention"&gt;`, which is
    // the regression: a concession sub-parse used to run the mention <span>
    // back through marked, which escaped it.
    assert.match(html, /<span class="mention">Alice<\/span>/,
        `mention inside concession was not rendered as a real span:\n${html}`);
    assert.ok(!html.includes('&lt;span class="mention"'),
        `mention tag leaked as literal escaped text:\n${html}`);
});

test('falsy input returns empty string', () => {
    assert.equal(renderMarkdown(''), '');
    assert.equal(renderMarkdown(null), '');
    assert.equal(renderMarkdown(undefined), '');
});
