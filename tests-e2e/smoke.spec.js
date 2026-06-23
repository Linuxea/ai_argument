// tests-e2e/smoke.spec.js — frontend integration smoke tests.
//
// These exercise the REAL vendored marked + the real markdown.js / app shell /
// CSS against a served page — the layer the jsdom unit tests (stubbed marked,
// isolated modules) cannot reach. This is the regression net that caught the
// tool-card fold leak and the concession mention-escape bug during manual
// profiling; keep it growing as new rendering bugs are fixed.
import { test, expect } from '@playwright/test';

const PAGE = '/static/index.html';

// Wait until the vendored deps have loaded (deferred classic scripts run before
// the module that uses them, but be explicit).
async function ready(page) {
    await page.waitForFunction(
        () => typeof window.marked !== 'undefined' && typeof window.lucide !== 'undefined',
    );
}

// Drive renderMarkdown through the real module + real marked.
async function render(page, input) {
    return page.evaluate(async (raw) => {
        const { renderMarkdown } = await import('/static/modules/markdown.js');
        const el = document.createElement('div');
        el.innerHTML = renderMarkdown(raw);
        return {
            mention: el.querySelectorAll('.mention').length,
            concession: el.querySelectorAll('.concession, .concession-block').length,
            leakedLiteralSpan: el.textContent.includes('<span'),
        };
    }, input);
}

test('static shell loads with no JS errors and vendored deps present', async ({ page }) => {
    const errors = [];
    page.on('pageerror', (e) => errors.push(e.message));
    await page.goto(PAGE);
    await ready(page);
    expect(errors, errors.join('\n')).toEqual([]);
    expect(await page.evaluate(() => typeof window.marked)).toBe('object');
    expect(await page.evaluate(() => typeof window.lucide)).toBe('object');
});

test('global search toggle is present and on by default', async ({ page }) => {
    await page.goto(PAGE);
    const checked = await page.locator('#search-enabled').evaluate((el) => el.checked);
    expect(checked).toBe(true);
});

test('[[Name]] renders as a mention badge via real marked', async ({ page }) => {
    await page.goto(PAGE);
    await ready(page);
    const r = await render(page, '我同意[[正方]]的判断。');
    expect(r.mention).toBe(1);
    expect(r.leakedLiteralSpan).toBe(false);
});

test('residual [退让] markup degrades to plain text (concession feature removed)', async ({ page }) => {
    // Guards against re-introducing the removed concession markup: a literal
    // [退让]...[/退让] must NOT get special styling, and a mention inside it
    // must still render (the old bug escaped it into literal tag text).
    await page.goto(PAGE);
    await ready(page);
    const r = await render(page, '[退让]我同意[[反方]]某点[/退让]但保留。');
    expect(r.concession).toBe(0);
    expect(r.mention).toBe(1);
    expect(r.leakedLiteralSpan).toBe(false);
});
