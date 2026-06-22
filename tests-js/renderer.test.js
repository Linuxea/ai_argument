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
    // Thinking section should be collapsed.
    const thinkingSection = bubbles[0].querySelector('.thinking-section');
    assert.ok(thinkingSection, 'thinking section should still be present');
    const text = thinkingSection.querySelector('.thinking-text');
    assert.ok(text.classList.contains('thinking-collapsed'),
        'finalize() should collapse the thinking section');
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
