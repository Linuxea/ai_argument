// autoscroll.js — follows bottom unless user scrolls up; floating jump button
import { icon, refreshIcons } from './utils.js';

export class AutoScroller {
    constructor(container, { offsetThreshold = 80 } = {}) {
        this.container = container;
        this.offsetThreshold = offsetThreshold;
        this.following = true;
        this.unseenCount = 0;
        this._rafPending = false;

        // Sentinel sits at the very end inside `container`
        this.sentinel = document.createElement('div');
        this.sentinel.className = 'messages-sentinel';
        container.appendChild(this.sentinel);

        // Floating "scroll to bottom" button (anchored to chat-area)
        this.button = document.createElement('button');
        this.button.className = 'scroll-bottom-btn';
        this.button.type = 'button';
        this.button.setAttribute('aria-label', '滚动到底部');

        const iconEl = icon('arrow-down');
        const label = document.createElement('span');
        label.textContent = '最新';
        this.countBadge = document.createElement('span');
        this.countBadge.className = 'scroll-bottom-btn-count';
        this.countBadge.hidden = true;

        this.button.append(iconEl, label, this.countBadge);
        this.button.addEventListener('click', () => this.scrollToBottom(true));

        // Insert button into chat-area (parent of messages container)
        const chatArea = container.closest('.chat-area') || container.parentElement;
        chatArea.appendChild(this.button);

        // Observe sentinel visibility = following state
        this.observer = new IntersectionObserver((entries) => {
            for (const e of entries) {
                this.following = e.isIntersecting;
                if (this.following) {
                    this.unseenCount = 0;
                    this._updateButton();
                }
                this.button.classList.toggle('visible', !this.following);
            }
        }, {
            root: container,
            threshold: 0,
            rootMargin: `0px 0px ${this.offsetThreshold}px 0px`,
        });
        this.observer.observe(this.sentinel);

        refreshIcons();
    }

    // Ensure sentinel stays as the last child (call after appending a message)
    pinSentinel() {
        if (this.sentinel.nextSibling !== null) {
            this.container.appendChild(this.sentinel);
        }
    }

    // Schedule a scroll if following; otherwise bump unseen counter
    schedule({ counted = false } = {}) {
        this.pinSentinel();
        if (this.following) {
            if (this._rafPending) return;
            this._rafPending = true;
            requestAnimationFrame(() => {
                this._rafPending = false;
                // jump directly (smooth scroll causes jank during streaming)
                this.container.scrollTop = this.container.scrollHeight;
            });
        } else if (counted) {
            this.unseenCount += 1;
            this._updateButton();
        }
    }

    scrollToBottom(smooth = false) {
        this.pinSentinel();
        this.following = true;
        this.unseenCount = 0;
        this._updateButton();
        if (smooth) {
            this.container.scrollTo({ top: this.container.scrollHeight, behavior: 'smooth' });
        } else {
            this.container.scrollTop = this.container.scrollHeight;
        }
    }

    _updateButton() {
        if (this.unseenCount > 0) {
            this.countBadge.hidden = false;
            this.countBadge.textContent = this.unseenCount > 99 ? '99+' : String(this.unseenCount);
        } else {
            this.countBadge.hidden = true;
        }
    }
}
