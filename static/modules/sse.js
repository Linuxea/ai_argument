// sse.js — SSE client wrapper with status reporting
const KNOWN_EVENTS = [
    'debater_start',
    'thinking_chunk',
    'debater_chunk',
    'debater_finalize',
    'debater_end',
    'tool_call',
    'round_end',
    'debate_end',
    'debate_paused',
    'judge_chunk',
    'judge_result',
    'debate_error',
    'judge_error',
];

const TERMINAL = new Set([
    'debate_end',
    'judge_result',
    'debate_paused',
    'debate_error',
    'judge_error',
]);

export class SSEClient extends EventTarget {
    constructor(url) {
        super();
        this.url = url;
        this.source = null;
        this._intentionalClose = false;
    }

    connect() {
        this.close();
        this._intentionalClose = false;
        const src = new EventSource(this.url);
        this.source = src;

        src.addEventListener('open', () => {
            this.dispatchEvent(new CustomEvent('status', { detail: { state: 'open' } }));
        });

        for (const name of KNOWN_EVENTS) {
            src.addEventListener(name, (e) => {
                let data = null;
                try {
                    data = e.data ? JSON.parse(e.data) : {};
                } catch (err) {
                    console.error(`Failed to parse SSE data for ${name}:`, err, e.data);
                    return;
                }
                this.dispatchEvent(new CustomEvent('event', { detail: { type: name, data } }));
                if (TERMINAL.has(name)) {
                    // Server will end stream too; close client side proactively
                    this._intentionalClose = true;
                    this.close();
                }
            });
        }

        src.addEventListener('error', () => {
            // EventSource auto-reconnects unless we close it. If readyState is CLOSED, surface to UI.
            if (this._intentionalClose) {
                this.dispatchEvent(new CustomEvent('status', { detail: { state: 'closed' } }));
                return;
            }
            if (src.readyState === EventSource.CLOSED) {
                this.dispatchEvent(new CustomEvent('status', { detail: { state: 'disconnected' } }));
            } else {
                this.dispatchEvent(new CustomEvent('status', { detail: { state: 'reconnecting' } }));
            }
        });
    }

    close() {
        if (this.source) {
            this._intentionalClose = true;
            this.source.close();
            this.source = null;
        }
    }
}
