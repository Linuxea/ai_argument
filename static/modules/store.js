// store.js — in-memory record of completed messages.
//
// The canonical source of truth for finished messages, so consumers (search,
// export) don't re-read DOM dataset.raw. The renderer appends a record as each
// message finalises. Streaming state still lives on the DOM during the build
// (the renderer needs dataset.raw for incremental markdown); the store
// captures the finalised snapshot once the message is complete.
export class MessageStore {
    constructor() {
        this._records = [];
    }

    /** Append a finalised message record. Shape:
     *  { el, role, speaker, color, avatar, time, text }
     *  role ∈ 'debater' | 'judge' | 'user' | 'system' | 'tool'. */
    add(rec) {
        this._records.push(rec);
    }

    /** All finalised records, in insertion order. */
    all() {
        return this._records;
    }

    /** Drop everything (new debate / reset). */
    clear() {
        this._records = [];
    }
}
