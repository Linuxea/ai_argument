// tests-js/sse.test.js — SSEClient wrapper tests
import test from 'node:test';
import assert from 'node:assert/strict';
import { setupDom } from './helpers/jsdom-env.js';

setupDom();

// EventSource shim — captures listeners and lets tests trigger events.
class FakeEventSource {
    static instances = [];
    static CLOSED = 2;
    constructor(url) {
        this.url = url;
        this.readyState = 0;
        this.listeners = new Map();
        FakeEventSource.instances.push(this);
    }
    addEventListener(name, cb) {
        if (!this.listeners.has(name)) this.listeners.set(name, []);
        this.listeners.get(name).push(cb);
    }
    close() {
        this.readyState = FakeEventSource.CLOSED;
    }
    dispatch(name, evt) {
        for (const cb of this.listeners.get(name) || []) cb(evt);
    }
}
globalThis.EventSource = FakeEventSource;

const { SSEClient } = await import('../static/modules/sse.js');

test('SSEClient connect() opens an EventSource', () => {
    FakeEventSource.instances = [];
    const c = new SSEClient('/stream');
    c.connect();
    assert.equal(FakeEventSource.instances.length, 1);
    assert.equal(FakeEventSource.instances[0].url, '/stream');
});

test('SSEClient parses JSON event payloads and dispatches "event" with type+data', () => {
    FakeEventSource.instances = [];
    const c = new SSEClient('/stream');
    c.connect();
    const src = FakeEventSource.instances[0];

    const seen = [];
    c.addEventListener('event', (e) => seen.push(e.detail));
    src.dispatch('debater_chunk', { data: JSON.stringify({ text_chunk: 'hi' }) });
    assert.deepEqual(seen, [{ type: 'debater_chunk', data: { text_chunk: 'hi' } }]);
});

test('SSEClient silently drops events with malformed JSON', () => {
    FakeEventSource.instances = [];
    const c = new SSEClient('/stream');
    c.connect();
    const src = FakeEventSource.instances[0];
    const seen = [];
    c.addEventListener('event', (e) => seen.push(e.detail));
    src.dispatch('debater_chunk', { data: '{not json' });
    assert.equal(seen.length, 0);
});

test('SSEClient closes itself on a terminal event', () => {
    FakeEventSource.instances = [];
    const c = new SSEClient('/stream');
    c.connect();
    const src = FakeEventSource.instances[0];
    src.dispatch('debate_end', { data: '{"reason":"done"}' });
    assert.equal(src.readyState, FakeEventSource.CLOSED);
});

test('SSEClient dispatches "status disconnected" when error + state CLOSED + not intentional', () => {
    FakeEventSource.instances = [];
    const c = new SSEClient('/stream');
    c.connect();
    const src = FakeEventSource.instances[0];

    const statuses = [];
    c.addEventListener('status', (e) => statuses.push(e.detail.state));

    src.readyState = FakeEventSource.CLOSED;
    src.dispatch('error', {});

    assert.ok(statuses.includes('disconnected'),
        `expected 'disconnected', got: ${JSON.stringify(statuses)}`);
});

test('SSEClient dispatches "status reconnecting" when error + not CLOSED', () => {
    FakeEventSource.instances = [];
    const c = new SSEClient('/stream');
    c.connect();
    const src = FakeEventSource.instances[0];

    const statuses = [];
    c.addEventListener('status', (e) => statuses.push(e.detail.state));

    src.readyState = 0;  // CONNECTING
    src.dispatch('error', {});

    assert.ok(statuses.includes('reconnecting'),
        `expected 'reconnecting', got: ${JSON.stringify(statuses)}`);
});

test('SSEClient.close() prevents disconnected status from firing on subsequent errors', () => {
    FakeEventSource.instances = [];
    const c = new SSEClient('/stream');
    c.connect();
    const src = FakeEventSource.instances[0];

    const statuses = [];
    c.addEventListener('status', (e) => statuses.push(e.detail.state));
    c.close();
    src.dispatch('error', {});

    // Intentional close → should emit 'closed', not 'disconnected'.
    assert.ok(!statuses.includes('disconnected'),
        `unexpected 'disconnected' after intentional close: ${JSON.stringify(statuses)}`);
});

test('SSEClient open event fires status:open', () => {
    FakeEventSource.instances = [];
    const c = new SSEClient('/stream');
    c.connect();
    const src = FakeEventSource.instances[0];
    const statuses = [];
    c.addEventListener('status', (e) => statuses.push(e.detail.state));
    src.dispatch('open', {});
    assert.ok(statuses.includes('open'));
});

test('Calling connect() twice closes the previous source', () => {
    FakeEventSource.instances = [];
    const c = new SSEClient('/stream');
    c.connect();
    const first = FakeEventSource.instances[0];
    c.connect();
    assert.equal(first.readyState, FakeEventSource.CLOSED,
        'first source should be closed when connect() is called again');
    assert.equal(FakeEventSource.instances.length, 2);
});
