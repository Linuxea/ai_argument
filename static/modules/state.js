// state.js — simple finite state machine for UI state
const TRANSITIONS = {
    idle:     ['debating'],
    debating: ['paused', 'stopped'],
    paused:   ['debating', 'stopped'],
    stopped:  ['judging', 'debating'],
    judging:  ['stopped'],
};

export class UIState {
    constructor(initial = 'idle', onChange = () => {}) {
        this.current = initial;
        this.onChange = onChange;
    }

    /**
     * Attempt to transition to ``next``.
     *
     * Returns true on a legal (or no-op) transition, false if the transition
     * is not in the TRANSITIONS table. The state is NOT updated on rejection,
     * so callers must not assume the UI moved. Previously this method always
     * allowed the transition (the table was decorative) — that defeated the
     * purpose of having a FSM.
     */
    set(next) {
        if (this.current === next) return true;
        const allowed = TRANSITIONS[this.current] || [];
        if (!allowed.includes(next)) {
            console.warn(`UIState: rejected transition ${this.current} -> ${next}`);
            return false;
        }
        const prev = this.current;
        this.current = next;
        this.onChange(next, prev);
        return true;
    }

    is(state) {
        return this.current === state;
    }
}
