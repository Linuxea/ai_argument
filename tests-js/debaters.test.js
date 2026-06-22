// tests-js/debaters.test.js — B5 + drag/keyboard behavior tests
import test from 'node:test';
import assert from 'node:assert/strict';
import { setupDom } from './helpers/jsdom-env.js';

setupDom();

// lucide refreshIcons() walks document.querySelectorAll — needs a body.
const { DebaterList } = await import('../static/modules/debaters.js');

function makeList(debaters) {
    document.body.innerHTML = '<div id="root"></div>';
    const root = document.getElementById('root');
    const list = new DebaterList(root);
    list.setDebaters(debaters);
    return { list, root };
}

const PRESETS = [
    { name: '正方', color: '#11aa11', avatar: '🟢', stance: '正方' },
    { name: '反方', color: '#aa1111', avatar: '🔴', stance: '反方' },
    { name: '分析家', color: '#1111aa', avatar: '🔵', stance: '中立' },
];

test('B5: re-rendering with a new debater preserves user checkbox state', () => {
    const { list, root } = makeList(PRESETS);

    // User unchecks "反方"
    const fanCb = root.querySelector('input[value="反方"]');
    fanCb.checked = false;

    // Add a new debater (server returns presets + new entry)
    list.setDebaters([...PRESETS, { name: '新人', color: '#a67b32', avatar: '🟣', stance: '中立' }]);

    // "反方" must remain unchecked.
    const fanCbAfter = root.querySelector('input[value="反方"]');
    assert.equal(fanCbAfter.checked, false, '反方 should remain unchecked after re-render');

    // Other previously-checked items remain checked.
    assert.equal(root.querySelector('input[value="正方"]').checked, true);
    assert.equal(root.querySelector('input[value="分析家"]').checked, true);

    // The new entry defaults to checked (because the user hasn't said otherwise).
    assert.equal(root.querySelector('input[value="新人"]').checked, true);
});

test('B5: re-render preserves user-arranged DOM order', () => {
    const { list, root } = makeList(PRESETS);

    // Simulate user dragging 反方 to the front.
    const items = root.querySelectorAll('.debater-item');
    const fan = Array.from(items).find((el) => el.dataset.name === '反方');
    root.insertBefore(fan, root.firstChild);
    assert.deepEqual(list.getOrder(), ['反方', '正方', '分析家']);

    // Now add a new debater.
    list.setDebaters([...PRESETS, { name: '新人', color: '#a67b32', avatar: '🟣', stance: '中立' }]);

    const orderAfter = list.getOrder();
    assert.equal(orderAfter[0], '反方', 'user-arranged 反方 must still be first');
    // 新人 should appear (anywhere — it's new).
    assert.ok(orderAfter.includes('新人'));
});

test('B5: removed debaters drop out cleanly', () => {
    const { list, root } = makeList(PRESETS);
    list.setDebaters([PRESETS[0], PRESETS[2]]); // drop 反方
    const names = Array.from(root.querySelectorAll('.debater-item'))
        .map((el) => el.dataset.name);
    assert.deepEqual(names.sort(), ['分析家', '正方'].sort());
});

test('getSelected returns only checked debaters', () => {
    const { root, list } = makeList(PRESETS);
    root.querySelector('input[value="反方"]').checked = false;
    assert.deepEqual(list.getSelected().sort(), ['分析家', '正方']);
});

test('getOrder follows DOM, not initial input list', () => {
    const { root, list } = makeList(PRESETS);
    const last = root.querySelector('.debater-item:last-child');
    root.insertBefore(last, root.firstChild);
    const order = list.getOrder();
    assert.equal(order[0], '分析家');
});
