// theme.js — light/dark with View Transitions
const STORAGE_KEY = 'theme';

function prefersDark() {
    return window.matchMedia('(prefers-color-scheme: dark)').matches;
}

function resolveInitialTheme() {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === 'dark' || stored === 'light') return stored;
    return prefersDark() ? 'dark' : 'light';
}

function applyTheme(theme) {
    document.documentElement.classList.toggle('dark', theme === 'dark');
}

let onChange = null;

export function initTheme(callback) {
    onChange = callback;
    const theme = resolveInitialTheme();
    applyTheme(theme);
    callback?.(theme === 'dark');

    // Follow system changes if user has never explicitly chosen
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
        if (!localStorage.getItem(STORAGE_KEY)) {
            applyTheme(e.matches ? 'dark' : 'light');
            callback?.(e.matches);
        }
    });
}

export function toggleTheme(originEvent) {
    const isDark = document.documentElement.classList.contains('dark');
    const next = isDark ? 'light' : 'dark';

    const doSwap = () => {
        applyTheme(next);
        localStorage.setItem(STORAGE_KEY, next);
        onChange?.(next === 'dark');
    };

    // View Transitions API (Chrome/Edge); fall back to CSS transition
    if (typeof document.startViewTransition === 'function' &&
        !window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
        // Set reveal origin for the circular wipe
        if (originEvent?.target) {
            const rect = originEvent.target.getBoundingClientRect();
            const x = ((rect.left + rect.width / 2) / window.innerWidth) * 100;
            const y = ((rect.top + rect.height / 2) / window.innerHeight) * 100;
            document.documentElement.style.setProperty('--reveal-x', `${x}%`);
            document.documentElement.style.setProperty('--reveal-y', `${y}%`);
        }
        document.startViewTransition(doSwap);
    } else {
        doSwap();
    }
}

export function isDark() {
    return document.documentElement.classList.contains('dark');
}
