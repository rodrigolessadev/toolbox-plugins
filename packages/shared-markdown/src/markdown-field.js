/**
 * @toolbox-plugins/shared-markdown - MarkdownField
 * Unified hybrid component that seamlessly switches between static formatted reader
 * and interactive raw editor.
 */

import { MarkdownReader } from './markdown-reader.js';
import { MarkdownEditor } from './markdown-editor.js';

export class MarkdownField {
  /**
   * @param {Object} options
   * @param {string} [options.value='']
   * @param {'view' | 'edit'} [options.mode='view']
   * @param {boolean} [options.allowToggleEdit=false]
   * @param {boolean} [options.readOnly=false]
   * @param {string} [options.placeholder='']
   * @param {(newContent: string) => void} [options.onSave]
   * @param {() => void} [options.onCancel]
   * @param {(content: string) => void} [options.onChange]
   */
  constructor(options = {}) {
    this.value = String(options.value ?? '');
    this.initialValue = this.value; // Store for rollback on cancel
    this.mode = options.mode === 'edit' ? 'edit' : 'view';
    this.allowToggleEdit = Boolean(options.allowToggleEdit);
    this.readOnly = Boolean(options.readOnly);
    this.placeholder = options.placeholder ?? '';
    this.onSave = options.onSave ?? null;
    this.onCancel = options.onCancel ?? null;
    this.onChange = options.onChange ?? null;

    this.element = document.createElement('div');
    this.element.className = `tb-markdown-field tb-mode-${this.mode}`;

    this.activeInstance = null;
    this.render();
  }

  render() {
    this.element.className = `tb-markdown-field tb-mode-${this.mode}`;
    this.element.innerHTML = '';

    if (this.mode === 'view' || this.readOnly) {
      this.activeInstance = new MarkdownReader({
        value: this.value,
        allowToggleEdit: this.allowToggleEdit && !this.readOnly,
        readOnly: this.readOnly,
        placeholder: this.placeholder,
        onEditRequested: () => {
          this.setMode('edit');
        },
      });
    } else {
      this.activeInstance = new MarkdownEditor({
        value: this.value,
        placeholder: this.placeholder,
        onChange: (content) => {
          this.value = content;
          if (typeof this.onChange === 'function') {
            this.onChange(content);
          }
        },
        onSave: (newContent) => {
          this.value = newContent;
          this.initialValue = newContent;
          if (typeof this.onSave === 'function') {
            this.onSave(newContent);
          }
          this.setMode('view');
        },
        onCancel: () => {
          // Restore prior value
          this.value = this.initialValue;
          if (typeof this.onCancel === 'function') {
            this.onCancel();
          }
          this.setMode('view', true);
        },
      });
    }

    this.element.appendChild(this.activeInstance.element);

    if (this.mode === 'edit' && this.activeInstance && typeof this.activeInstance.focus === 'function') {
      const inst = this.activeInstance;
      setTimeout(() => {
        if (this.mode === 'edit' && inst && typeof inst.focus === 'function') {
          inst.focus();
        }
      }, 10);
    }
  }

  mount(target) {
    if (!target) return;
    if (typeof target === 'string') {
      const el = document.querySelector(target);
      if (el) el.appendChild(this.element);
    } else if (target.appendChild) {
      target.appendChild(this.element);
    }
  }

  getValue() {
    return this.value;
  }

  setValue(newVal) {
    this.value = String(newVal ?? '');
    this.initialValue = this.value;
    if (this.activeInstance && typeof this.activeInstance.setValue === 'function') {
      this.activeInstance.setValue(this.value);
    } else {
      this.render();
    }
  }

  getMode() {
    return this.mode;
  }

  setMode(newMode, keepCurrentValue = false) {
    if (this.readOnly && newMode === 'edit') {
      return;
    }
    const targetMode = newMode === 'edit' ? 'edit' : 'view';
    if (this.mode === targetMode) return;

    if (this.mode === 'edit' && targetMode === 'view' && !keepCurrentValue) {
      // If manually switching to view without save, sync value
      if (this.activeInstance && typeof this.activeInstance.getValue === 'function') {
        this.value = this.activeInstance.getValue();
      }
    } else if (targetMode === 'edit') {
      // Remember initial value when entering edit mode
      this.initialValue = this.value;
    }

    this.mode = targetMode;
    this.render();
  }

  save() {
    if (this.mode === 'edit' && this.activeInstance && typeof this.activeInstance.save === 'function') {
      this.activeInstance.save();
    }
  }

  cancel() {
    if (this.mode === 'edit' && this.activeInstance && typeof this.activeInstance.cancel === 'function') {
      this.activeInstance.cancel();
    }
  }

  destroy() {
    if (this.activeInstance && typeof this.activeInstance.destroy === 'function') {
      this.activeInstance.destroy();
    }
    if (this.element.parentNode) {
      this.element.parentNode.removeChild(this.element);
    }
  }
}

/**
 * Register Web Component if customElements is available
 */
if (typeof customElements !== 'undefined' && !customElements.get('markdown-field')) {
  class MarkdownFieldElement extends HTMLElement {
    connectedCallback() {
      if (this._field) return;

      const value = this.getAttribute('value') || this.textContent || '';
      const mode = this.getAttribute('mode') || 'view';
      const allowToggleEdit = this.hasAttribute('allow-toggle-edit');
      const readOnly = this.hasAttribute('readonly');
      const placeholder = this.getAttribute('placeholder') || '';

      this.innerHTML = '';
      this._field = new MarkdownField({
        value,
        mode,
        allowToggleEdit,
        readOnly,
        placeholder,
        onSave: (newContent) => {
          this.setAttribute('value', newContent);
          this.dispatchEvent(new CustomEvent('save', { detail: { value: newContent } }));
        },
        onCancel: () => {
          this.dispatchEvent(new CustomEvent('cancel'));
        },
        onChange: (content) => {
          this.dispatchEvent(new CustomEvent('change', { detail: { value: content } }));
        },
      });

      this.appendChild(this._field.element);
    }

    static get observedAttributes() {
      return ['value', 'mode'];
    }

    attributeChangedCallback(name, oldVal, newVal) {
      if (!this._field || oldVal === newVal) return;
      if (name === 'value') {
        this._field.setValue(newVal);
      } else if (name === 'mode') {
        this._field.setMode(newVal);
      }
    }

    get value() {
      return this._field ? this._field.getValue() : this.getAttribute('value');
    }

    set value(val) {
      if (this._field) {
        this._field.setValue(val);
      } else {
        this.setAttribute('value', val);
      }
    }
  }

  customElements.define('markdown-field', MarkdownFieldElement);
}
