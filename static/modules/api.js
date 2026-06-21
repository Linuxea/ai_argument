// api.js — all backend HTTP calls in one place
async function call(method, path, body = null) {
    const opts = { method, headers: {} };
    if (body !== null) {
        opts.headers['Content-Type'] = 'application/json';
        opts.body = JSON.stringify(body);
    }
    const res = await fetch(path, opts);
    if (!res.ok) {
        let detail = `${res.status} ${res.statusText}`;
        try {
            const data = await res.json();
            if (data?.detail) detail = data.detail;
        } catch { /* ignore */ }
        const err = new Error(detail);
        err.status = res.status;
        throw err;
    }
    const ct = res.headers.get('content-type') || '';
    if (ct.includes('application/json')) return res.json();
    return null;
}

export const api = {
    loadDebaters: () => call('GET', '/api/debaters'),
    startDebate: (payload) => call('POST', '/api/debate/start', payload),
    stopDebate: () => call('POST', '/api/debate/stop'),
    resumeDebate: () => call('POST', '/api/debate/resume'),
    sendMessage: (message) => call('POST', '/api/debate/message', { message }),
    requestJudge: () => call('POST', '/api/debate/judge'),
    createDebater: (payload) => call('POST', '/api/debaters', payload),
    refineTopic: (topic) => call('POST', '/api/topic/refine', { topic }),
};
