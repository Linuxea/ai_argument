// sse.js — SSE client wrapper with status reporting
//
// Two correctness invariants (frontend audit C2 + C4):
//   1. Per-source closed flag: a `connect()` always calls `close()` first,
//      but the just-killed EventSource may emit one final async `error`
//      event that races with the reset of `_intentionalClose`. The closure
//      variable `closedSrc` captured in each listener filters those out so
//      the UI doesn't see a phantom "disconnected" toast on quick reconnect.
//   2. lastEventId tracking: native EventSource sends `Last-Event-ID` on
//      auto-reconnect, and the server replays buffered events. We expose
//      `lastEventId` and dispatch it with each event so callers can dedupe
//      on the application side if needed (e.g. for chunks the caller has
//      already rendered into a streaming bubble).
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
        // Highest event id observed on this connection. 0 means none yet.
        this.lastEventId = 0;
    }

    connect() {
        this.close();
        this._intentionalClose = false;
        // Capture the source we're about to create in a closure so the
        // error handler can tell whether *this particular* source was
        // closed by us (e.g. by a subsequent connect() or close()) —
        // avoiding the race where a stale source fires one last error
        // event after we've already moved on.
        const src = new EventSource(this.url);
        const closedSrc = { value: false };
        this.source = src;
        const markClosed = () => { closedSrc.value = true; };

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
                // Track highest id for replay dedup. EventSource exposes
                // lastEventId on the event itself.
                const id = parseInt(e.lastEventId, 10);
                if (Number.isFinite(id) && id > this.lastEventId) {
                    this.lastEventId = id;
                }
                this.dispatchEvent(new CustomEvent('event', {
                    detail: { type: name, data, id: e.lastEventId || '' },
                }));
                if (TERMINAL.has(name)) {
                    // Server will end stream too; close client side proactively
                    this._intentionalClose = true;
                    markClosed();
                    this.close();
                }
            });
        }

        src.addEventListener('error', () => {
            // EventSource auto-reconnects unless we close it. If readyState is CLOSED, surface to UI.
            if (this._intentionalClose || closedSrc.value) {
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
