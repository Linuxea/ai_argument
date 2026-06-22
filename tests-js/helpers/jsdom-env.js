// tests-js/helpers/jsdom-env.js
// Boots a JSDOM environment and installs window/document/localStorage on
// globalThis so the static/ ES modules can run unchanged.
import { JSDOM } from 'jsdom';

export function setupDom(html = '<!doctype html><html><body></body></html>') {
    const dom = new JSDOM(html, {
        url: 'http://localhost/',
        pretendToBeVisual: true,
    });

    const { window } = dom;

    // Mirror the most-used globals onto globalThis so modules using bare
    // names (document, window, requestAnimationFrame, ...) work seamlessly.
    const GLOBAL_KEYS = [
        'window', 'document', 'navigator', 'HTMLElement', 'Node', 'Element',
        'Event', 'CustomEvent', 'EventTarget', 'KeyboardEvent', 'MouseEvent',
        'getComputedStyle', 'matchMedia', 'localStorage', 'sessionStorage',
        'requestAnimationFrame', 'cancelAnimationFrame', 'IntersectionObserver',
        'CSS', 'fetch', 'URL', 'Blob', 'FileReader',
    ];
    for (const key of GLOBAL_KEYS) {
        if (window[key] === undefined) continue;
        try {
            Object.defineProperty(globalThis, key, {
                value: window[key],
                writable: true,
                configurable: true,
            });
        } catch {
            // Some props (e.g. navigator on Node 22) are getter-only; skip.
        }
    }

    // matchMedia stub if jsdom doesn't provide it.
    if (!globalThis.matchMedia) {
        globalThis.matchMedia = () => ({
            matches: false,
            addEventListener: () => {},
            removeEventListener: () => {},
        });
    }
    // jsdom provides matchMedia but without listeners — wrap if needed.
    const origMM = globalThis.matchMedia;
    globalThis.matchMedia = (q) => {
        const m = origMM(q);
        if (typeof m.addEventListener !== 'function') {
            m.addEventListener = () => {};
            m.removeEventListener = () => {};
        }
        return m;
    };
    // Mirror onto window so code calling `window.matchMedia(...)` works.
    try {
        Object.defineProperty(window, 'matchMedia', {
            value: globalThis.matchMedia,
            writable: true,
            configurable: true,
        });
    } catch { /* getter-only on some Node versions */ }

    // IntersectionObserver shim (jsdom doesn't have one).
    globalThis.IntersectionObserver = class {
        constructor(cb) { this._cb = cb; }
        observe() {}
        unobserve() {}
        disconnect() {}
    };

    // CSS.escape stub for environments without it.
    if (!globalThis.CSS || typeof globalThis.CSS.escape !== 'function') {
        globalThis.CSS = {
            ...(globalThis.CSS || {}),
            escape: (s) => String(s).replace(/[^a-zA-Z0-9_-]/g, (c) => `\\${c}`),
        };
    }

    return { dom, window, document: window.document };
}

export function teardownDom() {
    delete globalThis.window;
    delete globalThis.document;
    // Best-effort: most others can stay; tests recreate per-case.
}
