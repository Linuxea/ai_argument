// tests-js/store.test.js — MessageStore is the canonical record of finalised messages.
import test from 'node:test';
import assert from 'node:assert/strict';
import { setupDom } from './helpers/jsdom-env.js';

setupDom();

const { MessageStore } = await import('../static/modules/store.js');

test('add / all preserves insertion order', () => {
    const s = new MessageStore();
    s.add({ role: 'debater', text: 'first' });
    s.add({ role: 'user', text: 'second' });
    s.add({ role: 'system', text: 'third' });
    const all = s.all();
    assert.equal(all.length, 3);
    assert.deepEqual(all.map((r) => r.text), ['first', 'second', 'third']);
});

test('clear drops every record', () => {
    const s = new MessageStore();
    s.add({ role: 'debater', text: 'x' });
    s.add({ role: 'debater', text: 'y' });
    s.clear();
    assert.equal(s.all().length, 0);
});
