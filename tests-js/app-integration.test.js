// tests-js/app-integration.test.js — exercises DebateApp wiring lightly.
// We don't load app.js (it auto-instantiates on DOMContentLoaded); instead we
// verify isolated event-handling math.
import test from 'node:test';
import assert from 'node:assert/strict';
import { setupDom } from './helpers/jsdom-env.js';

setupDom();

// Minimal DOM matching the live index.html
document.body.innerHTML = `
    <input id="topic-input" type="text">
    <input id="max-rounds" type="number" min="1" max="50" value="10">
    <input type="checkbox" id="search-enabled" checked>
    <button id="refine-topic-btn"></button>
    <div id="debater-list"></div>
    <button id="start-btn"></button>
    <button id="stop-btn"></button>
    <button id="resume-btn"></button>
    <input id="custom-name"><input id="custom-color"><input id="custom-avatar">
    <select id="custom-stance"><option>中立</option></select>
    <textarea id="custom-personality"></textarea>
    <button id="add-debater-btn"></button>
    <h2 id="chat-title"></h2>
    <div class="chat-area"><div id="messages"></div></div>
    <textarea id="user-input"></textarea>
    <button id="send-btn"></button>
    <button id="judge-btn" hidden></button>
    <button id="download-btn"></button>
    <button id="theme-toggle"></button>
    <div id="round-progress"><div id="round-progress-fill"></div></div>
    <div id="round-info">
        <span></span><span></span>
        <span id="current-speaker"></span>
        <span id="round-badge"></span>
    </div>
    <button id="search-toggle-btn"></button>
    <dialog id="search-dialog"><input id="search-input"><div id="search-results"></div></dialog>
    <button id="search-close"></button>
    <div id="connection-indicator"></div>
`;

// marked stub used by renderer
globalThis.window.marked = {
    setOptions: () => {}, use: () => {},
    parse: (s) => `<p>${s.replace(/\n\n+/g, '</p><p>')}</p>`,
};

// Mock fetch — we don't want DebateApp.init() to hit the network.
globalThis.fetch = async () => ({
    ok: true,
    status: 200,
    headers: { get: () => 'application/json' },
    json: async () => ([]),  // empty debater list — init survives
});

// Override window.localStorage with a working in-memory store (jsdom provides
// one but the prototype implementation can be lossy across imports).
const _store = {};
globalThis.localStorage = {
    getItem: (k) => (k in _store ? _store[k] : null),
    setItem: (k, v) => { _store[k] = String(v); },
    removeItem: (k) => { delete _store[k]; },
    clear: () => { for (const k of Object.keys(_store)) delete _store[k]; },
};

// dialog polyfill (jsdom lacks showModal)
const Dialog = globalThis.window.HTMLDialogElement;
if (Dialog) {
    Dialog.prototype.showModal = function () { this.open = true; };
    Dialog.prototype.show = function () { this.open = true; };
    Dialog.prototype.close = function () { this.open = false; };
}

// Now import. app.js wires to DOMContentLoaded; we can also instantiate
// manually since DebateApp is on window after the module loads.
await import('../static/app.js');

// Trigger the DOMContentLoaded handler
document.dispatchEvent(new Event('DOMContentLoaded'));
// Let the init() promise settle.
await new Promise((r) => setTimeout(r, 50));

const app = globalThis.window.app;
assert.ok(app, 'DebateApp should be on window');

test('_readMaxRounds reads a valid integer', () => {
    app.maxRoundsInput.value = '15';
    assert.equal(app._readMaxRounds(), 15);
});

test('_readMaxRounds returns 10 for invalid input', () => {
    app.maxRoundsInput.value = 'abc';
    assert.equal(app._readMaxRounds(), 10);
    app.maxRoundsInput.value = '-5';
    assert.equal(app._readMaxRounds(), 10);
    app.maxRoundsInput.value = '0';
    assert.equal(app._readMaxRounds(), 10);
});

test('B25: _cancelAutoJudge clears a pending auto-judge timer', () => {
    let fired = false;
    app._autoJudgeTimer = setTimeout(() => { fired = true; }, 50);
    app._cancelAutoJudge();
    assert.equal(app._autoJudgeTimer, null);
    return new Promise((r) => setTimeout(() => {
        assert.equal(fired, false, 'auto-judge fired despite being cancelled');
        r();
    }, 80));
});

test('B8: _setRoundProgress shows 1-based current round with active speaker', () => {
    app._setRoundProgress(0, 5, 'Alice');
    assert.match(app.roundBadgeEl.textContent, /1 \/ 5/);
    app._setRoundProgress(2, 5, 'Bob');
    assert.match(app.roundBadgeEl.textContent, /2 \/ 5/);
});

test('B8: _setRoundProgress shows completed-count when no speaker', () => {
    app._setRoundProgress(3, 5, null);
    assert.match(app.roundBadgeEl.textContent, /3 \/ 5/);
});

test('B8: progress bar fill percent is clamped 0..100', () => {
    app._setRoundProgress(0, 5, null);
    assert.equal(app.roundProgressFill.style.width, '0%');
    app._setRoundProgress(5, 5, null);
    assert.equal(app.roundProgressFill.style.width, '100%');
    // Overflow case (defensive)
    app._setRoundProgress(10, 5, null);
    assert.equal(app.roundProgressFill.style.width, '100%');
});

test('B8: completed shows "已完成" when current >= total', () => {
    app._setRoundProgress(5, 5, null);
    assert.equal(app.currentSpeakerEl.textContent, '已完成');
});
