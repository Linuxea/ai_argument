// tests-js/api.test.js
// Regression tests for B4 — api.js must produce a readable error message even
// when FastAPI returns a Pydantic ValidationError (where `detail` is an array
// of {msg, loc, ...} objects instead of a string).
import test from 'node:test';
import assert from 'node:assert/strict';
import { setupDom } from './helpers/jsdom-env.js';

setupDom();

// Stub fetch on globalThis BEFORE importing api.js so the module captures it.
function stubFetch(status, body) {
    globalThis.fetch = async () => ({
        ok: status >= 200 && status < 300,
        status,
        statusText: status === 422 ? 'Unprocessable Entity' : 'Bad Request',
        headers: { get: () => 'application/json' },
        json: async () => body,
    });
}

const { api } = await import('../static/modules/api.js');

test('B4: array `detail` is flattened to a readable string', async () => {
    stubFetch(422, {
        detail: [
            { type: 'string_too_long', loc: ['body', 'topic'], msg: 'String should have at most 500 characters' },
            { type: 'value_error', loc: ['body', 'color'], msg: 'color must be a 6-digit hex color' },
        ],
    });

    try {
        await api.startDebate({ topic: 'x', debater_names: ['a', 'b'] });
        assert.fail('expected api.startDebate to throw');
    } catch (err) {
        // The message MUST contain the human-readable parts, not be the literal
        // "[object Object],[object Object]".
        assert.ok(!/object Object/.test(err.message),
            `error message contained '[object Object]': ${err.message}`);
        assert.match(err.message, /500 characters/);
        assert.match(err.message, /6-digit hex/);
        // Field hints help the user too.
        assert.match(err.message, /topic|color/);
        assert.equal(err.status, 422);
    }
});

test('B4: string `detail` passes through unchanged', async () => {
    stubFetch(400, { detail: 'At least 2 debaters required' });
    try {
        await api.startDebate({ topic: 'x', debater_names: ['a'] });
        assert.fail('expected throw');
    } catch (err) {
        assert.equal(err.message, 'At least 2 debaters required');
        assert.equal(err.status, 400);
    }
});

test('B4: missing detail falls back to status text', async () => {
    stubFetch(500, {});
    try {
        await api.refineTopic('t');
        assert.fail('expected throw');
    } catch (err) {
        assert.match(err.message, /500/);
    }
});

test('B4: non-JSON error body does not crash', async () => {
    globalThis.fetch = async () => ({
        ok: false,
        status: 502,
        statusText: 'Bad Gateway',
        headers: { get: () => 'text/html' },
        json: async () => { throw new SyntaxError('Unexpected token <'); },
    });
    try {
        await api.refineTopic('t');
        assert.fail('expected throw');
    } catch (err) {
        assert.match(err.message, /502/);
        assert.equal(err.status, 502);
    }
});

test('B4: detail object (not array, not string) is stringified safely', async () => {
    stubFetch(400, { detail: { code: 'X', hint: 'try again' } });
    try {
        await api.refineTopic('t');
        assert.fail('expected throw');
    } catch (err) {
        assert.ok(!/object Object/.test(err.message), err.message);
        assert.match(err.message, /code|hint|X|try again/);
    }
});
