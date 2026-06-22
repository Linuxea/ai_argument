// tests-js/utils.test.js — utility module tests
import test from 'node:test';
import assert from 'node:assert/strict';
import { setupDom } from './helpers/jsdom-env.js';

setupDom();

const utils = await import('../static/modules/utils.js');

test('escapeHtml escapes basic HTML', () => {
    assert.equal(utils.escapeHtml('<script>'), '&lt;script&gt;');
    assert.equal(utils.escapeHtml('a & b'), 'a &amp; b');
});

test('escapeHtml handles null / undefined safely', () => {
    assert.equal(utils.escapeHtml(null), '');
    assert.equal(utils.escapeHtml(undefined), '');
});

test('sanitizeColor accepts 6-digit hex', () => {
    assert.equal(utils.sanitizeColor('#abcdef'), '#abcdef');
    assert.equal(utils.sanitizeColor('#ABCDEF'), '#ABCDEF');
});

test('sanitizeColor rejects malformed and falls back', () => {
    assert.equal(utils.sanitizeColor('red'), '#2b2620');
    assert.equal(utils.sanitizeColor('#xyz'), '#2b2620');
    assert.equal(utils.sanitizeColor('#abc'), '#2b2620');  // 3-digit not allowed
    assert.equal(utils.sanitizeColor(''), '#2b2620');
    assert.equal(utils.sanitizeColor(null), '#2b2620');
});

test('escapeRegex escapes regex metacharacters', () => {
    const escaped = utils.escapeRegex('.*+?^${}()|[]\\');
    // Construct a regex with it — must not throw and must match the literal.
    const re = new RegExp(escaped);
    assert.ok(re.test('.*+?^${}()|[]\\'));
});

test('debounce coalesces rapid calls', async () => {
    let count = 0;
    const fn = utils.debounce(() => { count++; }, 20);
    fn();
    fn();
    fn();
    await new Promise((r) => setTimeout(r, 50));
    assert.equal(count, 1);
});

test('debounce.cancel prevents pending call', async () => {
    let count = 0;
    const fn = utils.debounce(() => { count++; }, 20);
    fn();
    fn.cancel();
    await new Promise((r) => setTimeout(r, 50));
    assert.equal(count, 0);
});

test('formatTime returns HH:MM:SS-ish string', () => {
    const out = utils.formatTime(new Date('2024-01-01T13:45:07'));
    // jsdom locale defaults usually produce "13:45:07" or similar; just verify shape.
    assert.match(out, /\d{1,2}:\d{2}/);
});

test('icon() returns a span placeholder with data-lucide', () => {
    const el = utils.icon('moon', { title: 'tip', 'aria-label': 'a' });
    assert.equal(el.tagName, 'SPAN');
    assert.equal(el.dataset.lucide, 'moon');
    assert.equal(el.title, 'tip');
    assert.equal(el.getAttribute('aria-label'), 'a');
});
