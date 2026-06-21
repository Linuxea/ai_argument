// debaters.js — debater list with drag-and-drop + keyboard reordering
import { icon, refreshIcons, sanitizeColor } from './utils.js';

export class DebaterList {
    constructor(container) {
        this.container = container;
        this.debaters = [];
        this._draggedItem = null;
        this._kbdGrabbed = null;
    }

    setDebaters(debaters) {
        this.debaters = debaters;
        this.render();
    }

    getSelected() {
        const checked = this.container.querySelectorAll('input[type="checkbox"]:checked');
        return Array.from(checked).map((cb) => cb.value);
    }

    // Return the on-screen order of names (regardless of selection)
    getOrder() {
        return Array.from(this.container.querySelectorAll('.debater-item'))
            .map((el) => el.dataset.name);
    }

    render() {
        // Don't repaint while user is dragging — would invalidate references
        if (this._draggedItem || this._kbdGrabbed) return;

        this.container.innerHTML = '';

        for (const d of this.debaters) {
            const item = this._renderItem(d);
            this.container.appendChild(item);
        }
        refreshIcons();
    }

    _renderItem(d) {
        const item = document.createElement('div');
        item.className = 'debater-item';
        item.draggable = true;
        item.dataset.name = d.name;
        item.setAttribute('role', 'listitem');

        const handle = document.createElement('span');
        handle.className = 'drag-handle';
        handle.setAttribute('aria-label', '拖拽以重新排序');
        handle.setAttribute('tabindex', '0');
        handle.appendChild(icon('grip-vertical'));

        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.id = `debater-${CSS.escape(d.name)}`;
        checkbox.value = d.name;
        checkbox.checked = true;
        checkbox.setAttribute('aria-label', `选择辩手 ${d.name}`);

        const avatar = document.createElement('span');
        avatar.className = 'debater-avatar';
        avatar.textContent = d.avatar;

        const name = document.createElement('label');
        name.className = 'debater-name';
        name.htmlFor = checkbox.id;
        name.textContent = d.name;

        const stance = document.createElement('span');
        stance.className = 'debater-stance';
        stance.style.color = sanitizeColor(d.color);
        stance.textContent = d.stance;

        item.append(handle, checkbox, avatar, name, stance);
        this._bindDrag(item);
        this._bindKeyboard(item, handle);
        return item;
    }

    _bindDrag(item) {
        item.addEventListener('dragstart', () => {
            this._draggedItem = item;
            item.classList.add('dragging');
        });
        item.addEventListener('dragend', () => {
            item.classList.remove('dragging');
            this._clearDragOver();
            this._draggedItem = null;
        });
        item.addEventListener('dragover', (e) => {
            e.preventDefault();
            if (!this._draggedItem || this._draggedItem === item) return;
            this._clearDragOver();
            const rect = item.getBoundingClientRect();
            const mid = rect.top + rect.height / 2;
            item.classList.add(e.clientY < mid ? 'drag-over-top' : 'drag-over-bottom');
        });
        item.addEventListener('drop', (e) => {
            e.preventDefault();
            if (!this._draggedItem || this._draggedItem === item) return;
            const rect = item.getBoundingClientRect();
            const mid = rect.top + rect.height / 2;
            if (e.clientY < mid) {
                this.container.insertBefore(this._draggedItem, item);
            } else {
                this.container.insertBefore(this._draggedItem, item.nextSibling);
            }
            this._clearDragOver();
        });
    }

    _bindKeyboard(item, handle) {
        handle.addEventListener('keydown', (e) => {
            if (e.key === ' ' || e.key === 'Enter') {
                e.preventDefault();
                this._toggleGrab(item);
            } else if (this._kbdGrabbed === item) {
                if (e.key === 'ArrowUp') {
                    e.preventDefault();
                    const prev = item.previousElementSibling;
                    if (prev?.classList.contains('debater-item')) {
                        this.container.insertBefore(item, prev);
                        handle.focus();
                    }
                } else if (e.key === 'ArrowDown') {
                    e.preventDefault();
                    const next = item.nextElementSibling;
                    if (next?.classList.contains('debater-item')) {
                        this.container.insertBefore(next, item);
                        handle.focus();
                    }
                } else if (e.key === 'Escape') {
                    e.preventDefault();
                    this._toggleGrab(item);
                }
            }
        });
    }

    _toggleGrab(item) {
        if (this._kbdGrabbed === item) {
            item.classList.remove('kbd-grabbed');
            this._kbdGrabbed = null;
        } else {
            // Release previous if any
            if (this._kbdGrabbed) this._kbdGrabbed.classList.remove('kbd-grabbed');
            this._kbdGrabbed = item;
            item.classList.add('kbd-grabbed');
        }
    }

    _clearDragOver() {
        this.container.querySelectorAll('.drag-over-top, .drag-over-bottom').forEach((el) => {
            el.classList.remove('drag-over-top', 'drag-over-bottom');
        });
    }
}
