// Playwright e2e config. Runs a static file server (repo root) so the page's
// absolute /static/... asset paths resolve. The browser binary is reused from
// the global playwright cache (chromium-1228) — run `npx playwright install
// chromium` once on a fresh machine if it's missing.
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
    testDir: './tests-e2e',
    fullyParallel: true,
    forbidOnly: !!process.env.CI,
    retries: process.env.CI ? 2 : 0,
    reporter: 'list',
    use: {
        baseURL: 'http://127.0.0.1:8765',
        trace: 'on-first-retry',
    },
    projects: [
        {
            name: 'chromium',
            use: {
                ...devices['Desktop Chrome'],
                // Portable by default: run `npx playwright install chromium` on a
                // fresh machine. CHROMIUM_EXECUTABLE_PATH lets a constrained env
                // (no browser-download access) point at an existing full-Chromium
                // binary instead of the headless shell.
                launchOptions: {
                    executablePath: process.env.CHROMIUM_EXECUTABLE_PATH || undefined,
                },
            },
        },
    ],
    webServer: {
        command: 'python3 -m http.server 8765',
        port: 8765,
        cwd: '.',
        reuseExistingServer: !process.env.CI,
        timeout: 20000,
    },
});
