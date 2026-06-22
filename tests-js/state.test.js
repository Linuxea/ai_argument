// tests-js/state.test.js — UI state machine
import test from 'node:test';
import assert from 'node:assert/strict';
import { setupDom } from './helpers/jsdom-env.js';

setupDom();

const { UIState } = await import('../static/modules/state.js');

test('UIState fires onChange with (next, prev) on valid transition', () => {
    const calls = [];
    const s = new UIState('idle', (next, prev) => calls.push([next, prev]));
    s.set('debating');
    assert.deepEqual(calls, [['debating', 'idle']]);
});

test('UIState ignores same-state set', () => {
    const calls = [];
    const s = new UIState('idle', (n, p) => calls.push([n, p]));
    s.set('idle');
    assert.deepEqual(calls, []);
});

test('UIState.is returns boolean', () => {
    const s = new UIState('paused');
    assert.equal(s.is('paused'), true);
    assert.equal(s.is('idle'), false);
});

test('UIState transitions through full lifecycle', () => {
    const s = new UIState('idle');
    s.set('debating');
    assert.equal(s.current, 'debating');
    s.set('paused');
    assert.equal(s.current, 'paused');
    s.set('stopped');
    assert.equal(s.current, 'stopped');
    s.set('judging');
    assert.equal(s.current, 'judging');
    s.set('stopped');
    assert.equal(s.current, 'stopped');
});

test('UIState defaults to no-op callback if not provided', () => {
    const s = new UIState('idle');
    // Must not throw.
    s.set('debating');
    assert.equal(s.current, 'debating');
});
