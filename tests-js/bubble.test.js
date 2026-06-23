// tests-js/bubble.test.js — pure DOM factories (no streaming state).
import test from 'node:test';
import assert from 'node:assert/strict';
import { setupDom } from './helpers/jsdom-env.js';

setupDom();

// Inline marked stub (no shared stub file) — bubble.js only uses marked for
// tool-card result rendering, which we don't assert on here.
globalThis.window.marked = {
    setOptions: () => {},
    use: () => {},
    parse: (s) => `<p>${s}</p>`,
};

const {
    createDebaterBubble,
    createSkeleton,
    createThinkingSection,
    createToolCard,
    createSystemMessage,
    createUserMessage,
} = await import('../static/modules/bubble.js');

test('createDebaterBubble sets --bubble-color and header', () => {
    const el = createDebaterBubble({ name: '正方', color: '#2ecc71', avatar: '🟢' }, false);
    assert.equal(el.className, 'message ai');
    assert.equal(el.dataset.speaker, '正方');
    assert.equal(el.style.getPropertyValue('--bubble-color'), '#2ecc71');
    assert.equal(el.querySelector('.message-avatar').textContent, '🟢');
    assert.equal(el.querySelector('.message-sender').textContent, '正方');
    assert.ok(el.querySelector('.message-time'));
});

test('createDebaterBubble consecutive omits avatar + sender', () => {
    const el = createDebaterBubble({ name: '正方', color: '#2ecc71', avatar: '🟢' }, true);
    assert.equal(el.className, 'message ai continuation');
    assert.ok(!el.querySelector('.message-avatar'));
    assert.ok(!el.querySelector('.message-sender'));
    assert.ok(el.querySelector('.message-time')); // time always present
});

test('createSkeleton is marked for later removal', () => {
    const el = createSkeleton();
    assert.equal(el.className, 'message-skeleton');
    assert.ok(el.dataset.skeleton);
});

test('createThinkingSection starts expanded with working toggle', () => {
    const section = createThinkingSection();
    const text = section.querySelector('.thinking-text');
    const header = section.querySelector('.thinking-header');
    const toggle = section.querySelector('.thinking-toggle');
    assert.equal(header.getAttribute('aria-expanded'), 'true');
    assert.ok(!text.classList.contains('thinking-collapsed'));
    assert.equal(toggle.textContent, '▼');
    // Clicking the header collapses
    section.querySelector('.thinking-header').dispatchEvent(new Event('click'));
    assert.ok(text.classList.contains('thinking-collapsed'));
    assert.equal(toggle.textContent, '▶');
    assert.equal(header.getAttribute('aria-expanded'), 'false');
});

test('createToolCard defaults to expanded and carries --bubble-color', () => {
    const card = createToolCard({
        name: '正方', color: '#2ecc71', avatar: '🟢',
        query: 'q', resultSummary: 's', isConsecutive: false,
    });
    assert.equal(card.className, 'message ai tool-card');
    assert.equal(card.style.getPropertyValue('--bubble-color'), '#2ecc71');
    const results = card.querySelector('.tool-card-results');
    assert.ok(!results.classList.contains('tool-card-collapsed'),
        'tool-card results must start expanded');
    const label = card.querySelector('.tool-card-label');
    assert.equal(label.getAttribute('aria-expanded'), 'true');
    assert.equal(card.querySelector('.tool-card-toggle').textContent, '▼');
    // Label click collapses
    label.dispatchEvent(new Event('click'));
    assert.ok(results.classList.contains('tool-card-collapsed'));
    assert.equal(label.getAttribute('aria-expanded'), 'false');
});

test('createSystemMessage and createUserMessage build the right shells', () => {
    const sys = createSystemMessage('hello');
    assert.equal(sys.className, 'message system');
    assert.equal(sys.querySelector('.message-content').textContent, 'hello');

    const user = createUserMessage('hi');
    assert.equal(user.className, 'message user');
    assert.equal(user.querySelector('.message-content').textContent, 'hi');
    assert.equal(user.querySelector('.message-sender').textContent, '你');
});
