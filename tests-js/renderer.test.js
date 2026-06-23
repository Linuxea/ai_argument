// tests-js/renderer.test.js — renderer behavior tests
import test from 'node:test';
import assert from 'node:assert/strict';
import { setupDom } from './helpers/jsdom-env.js';

setupDom();

// Stub marked since it's loaded via CDN; the markdown module falls back to
// plain-text rendering if window.marked is undefined.
globalThis.window.marked = {
    setOptions: () => {},
    use: () => {},
    parse: (s) => `<p>${s.replace(/\n\n/g, '</p><p>')}</p>`,
};

const { MessageRenderer } = await import('../static/modules/renderer.js');

function makeRenderer() {
    document.body.innerHTML = '<div class="chat-area"><div id="messages"></div></div>';
    const messages = document.getElementById('messages');
    // Minimal fake scroller — renderer only calls schedule / pinSentinel / sentinel.
    const sentinel = document.createElement('div');
    messages.appendChild(sentinel);
    const scroller = {
        sentinel,
        schedule: () => {},
        pinSentinel: () => {},
        scrollToBottom: () => {},
    };
    return { messages, renderer: new MessageRenderer(messages, scroller) };
}

test('B19: finalize with only thinking (no content) removes the empty bubble', () => {
    const { renderer, messages } = makeRenderer();
    renderer.startDebaterTurn({ name: 'Thinker', color: '#000000', avatar: '🤔' });
    renderer.appendThinking('  ');  // whitespace only — empty thinking
    renderer.finalize();
    // No content + empty thinking → no message bubble should remain.
    const bubbles = messages.querySelectorAll('.message');
    assert.equal(bubbles.length, 0,
        'finalize() with empty thinking + empty content should remove the bubble');
});

test('B19: finalize with thinking but no body keeps the bubble (thinking has content)', () => {
    const { renderer, messages } = makeRenderer();
    renderer.startDebaterTurn({ name: 'Thinker', color: '#000000', avatar: '🤔' });
    renderer.appendThinking('reasoning about X');
    renderer.finalize();
    const bubbles = messages.querySelectorAll('.message');
    assert.equal(bubbles.length, 1,
        'finalize() with non-empty thinking must keep the bubble visible');
    const thinkingSection = bubbles[0].querySelector('.thinking-section');
    assert.ok(thinkingSection, 'thinking section should still be present');
    const text = thinkingSection.querySelector('.thinking-text');
    // Thinking now stays expanded by default (user can still collapse manually).
    assert.ok(!text.classList.contains('thinking-collapsed'),
        'finalize() should leave the thinking section expanded by default');
    const header = thinkingSection.querySelector('.thinking-header');
    assert.equal(header.getAttribute('aria-expanded'), 'true',
        'thinking header should report expanded after finalize');
});

test('B19: finalize with normal content keeps the bubble', () => {
    const { renderer, messages } = makeRenderer();
    renderer.startDebaterTurn({ name: 'Speaker', color: '#000000', avatar: '💬' });
    renderer.appendChunk('hello world');
    renderer.finalize();
    const bubbles = messages.querySelectorAll('.message');
    assert.equal(bubbles.length, 1);
    const content = bubbles[0].querySelector('.message-content');
    assert.ok(content && content.textContent.includes('hello world'));
});

test('B18: appendChunk after endTurn() (no new debater_start) drops chunk safely', () => {
    // If the SSE stream is buggy / out of order and a chunk arrives after a
    // debater_end (which clears the speaker identity) with no preceding
    // debater_start, we must NOT silently attribute it to a stale debater.
    // The safe behavior is to drop it.
    const { renderer, messages } = makeRenderer();
    renderer.startDebaterTurn({ name: 'Alice', color: '#000000', avatar: '🧑' });
    renderer.appendChunk('first turn');
    renderer.endTurn();

    // No new startDebaterTurn → orphan chunk
    renderer.appendChunk('orphan chunk');

    // The orphan must NOT have been merged into Alice's previous bubble.
    const aliceContent = messages.querySelector('.message-content');
    assert.ok(!/orphan chunk/.test(aliceContent.textContent),
        'orphan chunk must not be appended to finalized Alice');

    // The orphan must NOT have created a new bubble attributing Alice as speaker.
    const bubbles = messages.querySelectorAll('.message');
    if (bubbles.length > 1) {
        const second = bubbles[1];
        const sender = second.querySelector('.message-sender');
        assert.ok(
            !sender || sender.textContent !== 'Alice',
            'orphan chunk created a bubble falsely attributed to Alice'
        );
    }
});

test('B18: appendChunk after a (soft) finalize within a turn DOES attribute to speaker', () => {
    // The tool_call flow does: finalize() → addToolCard() → more debater_chunk
    // events for the SAME speaker. These chunks SHOULD continue going to that
    // speaker (just in a fresh bubble). This regression guards against the
    // overly-aggressive B18 fix that broke this flow.
    const { renderer, messages } = makeRenderer();
    renderer.startDebaterTurn({ name: 'Alice', color: '#aabbcc', avatar: '🧑' });
    renderer.appendChunk('before tool');
    renderer.finalize();                          // soft finalize for tool_call
    renderer.appendChunk('after tool');           // chunks continue
    renderer.finalize();

    // We should see at least one Alice bubble containing "after tool"
    const senders = Array.from(messages.querySelectorAll('.message-sender'))
        .map((el) => el.textContent);
    assert.ok(senders.includes('Alice'),
        'post-tool chunks should still be attributed to Alice');
    const allText = messages.textContent;
    assert.ok(allText.includes('after tool'),
        'post-tool chunks should be rendered, not dropped');
});

test('B21: a new debater turn counts as 1 new message (not 1 per chunk)', () => {
    // The unseen-message badge should bump by exactly 1 for a debater turn,
    // not by N (where N is the chunk count). Otherwise badges instantly read
    // "99+" during a single 80-200 word response.
    document.body.innerHTML = '<div class="chat-area"><div id="messages"></div></div>';
    const messages = document.getElementById('messages');
    const sentinel = document.createElement('div');
    messages.appendChild(sentinel);

    let countedCalls = 0;
    const scroller = {
        sentinel,
        schedule: ({ counted = false } = {}) => { if (counted) countedCalls++; },
        pinSentinel: () => {},
        scrollToBottom: () => {},
    };
    const renderer = new MessageRenderer(messages, scroller);
    renderer.startDebaterTurn({ name: 'A', color: '#000', avatar: '💬' });
    renderer.appendChunk('chunk 1');
    renderer.appendChunk('chunk 2');
    renderer.appendChunk('chunk 3');

    return new Promise((resolve) => setTimeout(() => {
        assert.equal(countedCalls, 1,
            `startDebaterTurn should produce exactly 1 counted schedule (got ${countedCalls})`);
        resolve();
    }, 20));
});

test('F2: each debater bubble carries its own --bubble-color for tinting', () => {
    const { renderer, messages } = makeRenderer();
    renderer.startDebaterTurn({ name: '正方', color: '#2ecc71', avatar: '🟢' });
    renderer.appendChunk('hi');
    renderer.finalize();
    renderer.startDebaterTurn({ name: '反方', color: '#e74c3c', avatar: '🔴' });
    renderer.appendChunk('hey');
    renderer.finalize();

    const bubbles = messages.querySelectorAll('.message.ai');
    assert.equal(bubbles.length, 2);
    assert.equal(bubbles[0].style.getPropertyValue('--bubble-color'), '#2ecc71');
    assert.equal(bubbles[1].style.getPropertyValue('--bubble-color'), '#e74c3c');
});

test('F2: tool-card bubbles also carry the current debater --bubble-color', () => {
    const { renderer, messages } = makeRenderer();
    renderer.startDebaterTurn({ name: '正方', color: '#2ecc71', avatar: '🟢' });
    renderer.addToolCard({ debaterName: '正方', query: 'q', resultSummary: 's' });
    const card = messages.querySelector('.message.ai.tool-card');
    assert.ok(card, 'tool card should be rendered');
    assert.equal(card.style.getPropertyValue('--bubble-color'), '#2ecc71');
});

test('F3: tool-card results are expanded by default (not collapsed)', () => {
    const { renderer, messages } = makeRenderer();
    renderer.startDebaterTurn({ name: 'A', color: '#000', avatar: '💬' });
    renderer.addToolCard({ debaterName: 'A', query: 'q', resultSummary: 's' });
    const results = messages.querySelector('.tool-card-results');
    assert.ok(results, 'tool-card results element should exist');
    assert.ok(!results.classList.contains('tool-card-collapsed'),
        'tool-card results should start expanded');
    const label = messages.querySelector('.tool-card-label');
    assert.equal(label.getAttribute('aria-expanded'), 'true',
        'tool-card label should report expanded initially');
    const toggle = messages.querySelector('.tool-card-toggle');
    assert.equal(toggle.textContent, '▼');
});

test('F: renderer populates MessageStore on finalize / addSystem / addUser / addToolCard', async () => {
    const { MessageStore } = await import('../static/modules/store.js');
    document.body.innerHTML = '<div class="chat-area"><div id="messages"></div></div>';
    const messages = document.getElementById('messages');
    const sentinel = document.createElement('div');
    messages.appendChild(sentinel);
    const scroller = { sentinel, schedule: () => {}, pinSentinel: () => {}, scrollToBottom: () => {} };
    const store = new MessageStore();
    const renderer = new MessageRenderer(messages, scroller, store);

    renderer.startDebaterTurn({ name: '正方', color: '#2ecc71', avatar: '🟢' });
    renderer.appendChunk('first speech');
    renderer.endTurn();
    renderer.addSystem('round 1 done');
    renderer.addUser('user comment');
    renderer.startDebaterTurn({ name: '反方', color: '#e74c3c', avatar: '🔴' });
    renderer.addToolCard({ debaterName: '反方', query: 'q', resultSummary: 'summary' });
    renderer.appendChunk('rebuttal');
    renderer.endTurn();

    const recs = store.all();
    const roles = recs.map((r) => r.role);
    assert.deepEqual(roles, ['debater', 'system', 'user', 'tool', 'debater']);
    assert.equal(recs[0].speaker, '正方');
    assert.ok(recs[0].text.includes('first speech'));
    assert.equal(recs[3].speaker, '反方');
    assert.ok(recs[3].text.includes('summary'));

    // reset() clears the store
    renderer.reset();
    assert.equal(store.all().length, 0);
});
