import { test, describe, before } from 'node:test';
import assert from 'node:assert/strict';

// Simple DOM Mock for Node.js testing environment
function setupMockDom() {
  class MockElement {
    constructor(tagName = 'div') {
      this.tagName = tagName.toUpperCase();
      this.className = '';
      this.innerHTML = '';
      this.innerText = '';
      this.value = '';
      this.children = [];
      this.parentNode = null;
      this.attributes = {};
      this.eventListeners = {};
    }

    appendChild(child) {
      child.parentNode = this;
      this.children.push(child);
      return child;
    }

    removeChild(child) {
      const idx = this.children.indexOf(child);
      if (idx !== -1) {
        this.children.splice(idx, 1);
        child.parentNode = null;
      }
      return child;
    }

    querySelectorAll(selector) {
      return [];
    }

    querySelector(selector) {
      return null;
    }

    closest(selector) {
      return null;
    }

    addEventListener(event, callback) {
      if (!this.eventListeners[event]) {
        this.eventListeners[event] = [];
      }
      this.eventListeners[event].push(callback);
    }

    dispatchEvent(event) {
      const callbacks = this.eventListeners[event.type || event] || [];
      callbacks.forEach(cb => cb(event));
    }

    setAttribute(name, val) {
      this.attributes[name] = String(val);
    }

    getAttribute(name) {
      return this.attributes[name] ?? null;
    }

    hasAttribute(name) {
      return name in this.attributes;
    }

    focus() {}
  }

  globalThis.document = {
    createElement(tagName) {
      return new MockElement(tagName);
    },
    querySelector(selector) {
      return null;
    },
  };
}

describe('MarkdownField Component Lifecycle Tests', async () => {
  before(() => {
    setupMockDom();
  });

  const { MarkdownField } = await import('../src/markdown-field.js');

  test('initializes in view mode by default', () => {
    const field = new MarkdownField({
      value: '# Hello World',
    });

    assert.equal(field.getMode(), 'view');
    assert.equal(field.getValue(), '# Hello World');
    assert.ok(field.element.className.includes('tb-mode-view'));
  });

  test('switches from view mode to edit mode and updates class', () => {
    const field = new MarkdownField({
      value: 'Texto inicial',
      mode: 'view',
      allowToggleEdit: true,
    });

    assert.equal(field.getMode(), 'view');
    field.setMode('edit');
    assert.equal(field.getMode(), 'edit');
    assert.ok(field.element.className.includes('tb-mode-edit'));
  });

  test('save updates value, calls onSave, and switches back to view mode', () => {
    let savedContent = null;
    const field = new MarkdownField({
      value: 'Valor original',
      mode: 'edit',
      onSave: (newVal) => {
        savedContent = newVal;
      },
    });

    // Simulate user editing content
    field.activeInstance.setValue('Valor alterado pelo usuário');
    field.save();

    assert.equal(savedContent, 'Valor alterado pelo usuário');
    assert.equal(field.getValue(), 'Valor alterado pelo usuário');
    assert.equal(field.getMode(), 'view');
  });

  test('cancel restores initial value, calls onCancel, and does NOT call onSave', () => {
    let saved = false;
    let cancelled = false;

    const field = new MarkdownField({
      value: 'Valor inicial intocado',
      mode: 'edit',
      onSave: () => {
        saved = true;
      },
      onCancel: () => {
        cancelled = true;
      },
    });

    // Simulate dirty edit
    field.activeInstance.setValue('Rascunho que será descartado');
    field.cancel();

    assert.equal(cancelled, true, 'onCancel deve ser chamado');
    assert.equal(saved, false, 'onSave NÃO deve ser chamado ao cancelar');
    assert.equal(field.getValue(), 'Valor inicial intocado', 'Valor original deve ser restaurado');
    assert.equal(field.getMode(), 'view');
  });

  test('readOnly mode prevents entering edit mode', () => {
    const field = new MarkdownField({
      value: 'Conteúdo somente leitura',
      mode: 'view',
      readOnly: true,
    });

    field.setMode('edit');
    assert.equal(field.getMode(), 'view', 'Não deve permitir transição para edit quando readOnly');
  });
});
