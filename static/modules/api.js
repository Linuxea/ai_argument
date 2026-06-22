// api.js — all backend HTTP calls in one place

/**
 * Convert a FastAPI/Pydantic error `detail` value into a readable string.
 *
 * `detail` may be:
 *   - a string (custom HTTPException) — pass through
 *   - an array of validation errors (Pydantic):
 *       [{ type, loc: [...], msg, ... }, ...]
 *   - a non-array object — JSON-stringify rather than .toString()ing it
 *
 * Without this, `new Error([{...}, {...}])` collapses to the infamous
 * "[object Object],[object Object]" message.
 */
function formatErrorDetail(detail) {
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail)) {
        const parts = detail.map((item) => {
            if (typeof item === 'string') return item;
            if (item && typeof item === 'object') {
                const msg = item.msg || item.message || '';
                const loc = Array.isArray(item.loc) ? item.loc.filter(
                    (s) => s !== 'body' && s !== 'query' && s !== 'path',
                ).join('.') : '';
                if (msg && loc) return `${loc}: ${msg}`;
                if (msg) return msg;
                try { return JSON.stringify(item); } catch { return String(item); }
            }
            return String(item);
        });
        return parts.join('; ');
    }
    if (detail && typeof detail === 'object') {
        try { return JSON.stringify(detail); } catch { return String(detail); }
    }
    return String(detail ?? '');
}

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
            if (data?.detail !== undefined && data?.detail !== null) {
                detail = formatErrorDetail(data.detail);
            }
        } catch { /* non-JSON or empty body — keep status fallback */ }
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

// Exported for testing only. Not part of the public API.
export { formatErrorDetail };
