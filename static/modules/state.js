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

    set(next) {
        if (this.current === next) return;
        const allowed = TRANSITIONS[this.current] || [];
        // Allow any transition but log unusual ones
        if (!allowed.includes(next)) {
            console.debug(`UIState: unusual transition ${this.current} -> ${next}`);
        }
        const prev = this.current;
        this.current = next;
        this.onChange(next, prev);
    }

    is(state) {
        return this.current === state;
    }
}
