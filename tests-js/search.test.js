// tests-js/search.test.js — SearchPanel behaviors
import test from 'node:test';
import assert from 'node:assert/strict';
import { setupDom } from './helpers/jsdom-env.js';

setupDom();

const { SearchPanel } = await import('../static/modules/search.js');
const { MessageStore } = await import('../static/modules/store.js');

function makePanel() {
    document.body.innerHTML = `
        <div id="messages">
            <div class="message ai" data-speaker="A">
                <div class="message-header">
                    <span class="message-avatar">🟢</span>
                    <span class="message-sender" style="color: #00ff00">Alice</span>
                    <span class="message-time">10:00</span>
                </div>
                <div class="message-content"></div>
            </div>
            <div class="message ai" data-speaker="B">
                <div class="message-header">
                    <span class="message-avatar">🔴</span>
                    <span class="message-sender" style="color: #ff0000">Bob</span>
                    <span class="message-time">10:01</span>
                </div>
                <div class="message-content"></div>
            </div>
        </div>
        <dialog id="search-dialog">
            <input id="search-input" />
            <div id="search-results"></div>
            <button id="search-toggle"></button>
        </dialog>
    `;
    // Build a MessageStore with records pointing at the DOM elements above
    // (mirrors what the renderer would do on finalize).
    const store = new MessageStore();
    const messages = document.getElementById('messages');
    const elA = messages.querySelector('[data-speaker="A"]');
    const elB = messages.querySelector('[data-speaker="B"]');
    store.add({ el: elA, role: 'debater', speaker: 'Alice', color: '#00ff00', avatar: '🟢', time: '10:00', text: 'hello world from Alice' });
    store.add({ el: elB, role: 'debater', speaker: 'Bob',   color: '#ff0000', avatar: '🔴', time: '10:01', text: 'goodbye world' });
    return new SearchPanel({
        dialog: document.getElementById('search-dialog'),
        input: document.getElementById('search-input'),
        results: document.getElementById('search-results'),
        openBtn: document.getElementById('search-toggle'),
        store,
    });
}

test('SearchPanel indexes messages on open()', () => {
    const p = makePanel();
    // dialog.showModal isn't implemented by jsdom; stub on instance
    p.dialog.showModal = () => { p.dialog.open = true; };
    p.open();
    assert.equal(p._messageIndex.length, 2);
});

test('Search filtering by query returns matching message', () => {
    const p = makePanel();
    p.dialog.showModal = () => { p.dialog.open = true; };
    p.open();
    p.input.value = 'goodbye';
    p._runSearch();
    const items = p.results.querySelectorAll('.search-result-item');
    assert.equal(items.length, 1);
    assert.ok(items[0].textContent.includes('Bob') || items[0].textContent.includes('goodbye'));
});

test('Search highlighting wraps the matched substring', () => {
    const p = makePanel();
    p.dialog.showModal = () => { p.dialog.open = true; };
    p.open();
    p.input.value = 'world';
    p._runSearch();
    const marks = p.results.querySelectorAll('mark.search-highlight');
    assert.ok(marks.length >= 1, 'at least one match should be highlighted');
});

test('B30: clicking two results in quick succession does not strip the second highlight', async () => {
    const p = makePanel();
    p.dialog.showModal = () => { p.dialog.open = true; };
    p.dialog.close = () => { p.dialog.open = false; };
    p.open();
    const messages = document.getElementById('messages');
    const elA = messages.querySelector('[data-speaker="A"]');
    const elB = messages.querySelector('[data-speaker="B"]');

    // Stub scrollIntoView (jsdom doesn't implement)
    elA.scrollIntoView = () => {};
    elB.scrollIntoView = () => {};

    // First jump
    p._jumpTo(elA);
    assert.ok(elA.classList.contains('highlight'));

    // Second jump shortly after
    await new Promise((r) => setTimeout(r, 10));
    p._jumpTo(elB);

    // Wait past the first timer's window (which would have fired at ~2000ms)
    // but well before the second timer's expiry. Use a short total wait so
    // the test doesn't take forever — pin the highlight expiry shorter.
    // We assert directly that timers from the first jump don't strip B's
    // highlight by checking B still has the class after first timer would
    // have fired (we can't actually wait 2000ms in tests; instead verify the
    // panel canceled the old timer).
    assert.equal(
        p._highlightTimers.length, 1,
        'after the second jump the panel should track only its own timer (old one cancelled)',
    );
    assert.ok(elB.classList.contains('highlight'),
        'B should still be highlighted after the second jump');
});
