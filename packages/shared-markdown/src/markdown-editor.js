/**
 * @toolbox-plugins/shared-markdown - MarkdownEditor
 * Submodule responsible for interactive editing of raw Markdown with markers (#, *, [], etc.),
 * quick formatting toolbar, keyboard shortcuts and Save / Cancel actions.
 */

export class MarkdownEditor {
  /**
   * @param {Object} options
   * @param {string} [options.value='']
   * @param {string} [options.placeholder='']
   * @param {(newContent: string) => void} [options.onSave]
   * @param {() => void} [options.onCancel]
   * @param {(content: string) => void} [options.onChange]
   */
  constructor(options = {}) {
    this.value = options.value ?? '';
    this.placeholder = options.placeholder ?? 'Digite o conteúdo em Markdown...';
    this.onSave = options.onSave ?? null;
    this.onCancel = options.onCancel ?? null;
    this.onChange = options.onChange ?? null;

    this.element = document.createElement('div');
    this.element.className = 'tb-markdown-editor';

    this.render();
  }

  render() {
    this.element.innerHTML = '';

    // 1. Formatting Toolbar
    const toolbar = document.createElement('div');
    toolbar.className = 'tb-editor-toolbar';

    const tools = [
      { id: 'bold', label: 'B', title: 'Negrito (**texto**)', icon: '<b>B</b>', action: () => this.wrapSelection('**', '**', 'negrito') },
      { id: 'italic', label: 'I', title: 'Itálico (*texto*)', icon: '<i>I</i>', action: () => this.wrapSelection('*', '*', 'itálico') },
      { id: 'heading', label: 'H', title: 'Título (### )', icon: '<b>H</b>', action: () => this.prefixLine('### ') },
      { id: 'ul', label: '•', title: 'Lista com marcadores (- )', icon: '•', action: () => this.prefixLine('- ') },
      { id: 'task', label: '☑', title: 'Lista de tarefas (- [ ] )', icon: '☑', action: () => this.prefixLine('- [ ] ') },
      { id: 'quote', label: '“', title: 'Citação (> )', icon: '“', action: () => this.prefixLine('> ') },
      { id: 'code', label: '</>', title: 'Código inline ou bloco', icon: '&lt;/&gt;', action: () => this.wrapCode() },
      { id: 'link', label: '🔗', title: 'Link ([texto](url))', icon: '🔗', action: () => this.insertLink() },
    ];

    tools.forEach((tool) => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'tb-editor-tool-btn';
      btn.title = tool.title;
      btn.innerHTML = tool.icon;
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        tool.action();
      });
      toolbar.appendChild(btn);
    });

    this.element.appendChild(toolbar);

    // 2. Textarea
    const textarea = document.createElement('textarea');
    textarea.className = 'tb-editor-textarea';
    textarea.placeholder = this.placeholder;
    textarea.value = this.value;
    textarea.rows = 8;

    textarea.addEventListener('input', () => {
      this.value = textarea.value;
      if (typeof this.onChange === 'function') {
        this.onChange(this.value);
      }
    });

    textarea.addEventListener('keydown', (e) => {
      // Ctrl+Enter or Ctrl+S to save
      if ((e.ctrlKey || e.metaKey) && (e.key === 'Enter' || e.key === 's' || e.key === 'S')) {
        e.preventDefault();
        this.save();
      }
      // Escape to cancel
      if (e.key === 'Escape') {
        e.preventDefault();
        this.cancel();
      }
      // Tab indentation support
      if (e.key === 'Tab') {
        e.preventDefault();
        const start = textarea.selectionStart;
        const end = textarea.selectionEnd;
        textarea.value = textarea.value.substring(0, start) + '  ' + textarea.value.substring(end);
        textarea.selectionStart = textarea.selectionEnd = start + 2;
        this.value = textarea.value;
        if (typeof this.onChange === 'function') {
          this.onChange(this.value);
        }
      }
    });

    this.textarea = textarea;
    this.element.appendChild(textarea);

    // 3. Actions Footer (Salvar e Cancelar)
    const footer = document.createElement('div');
    footer.className = 'tb-editor-footer';

    const hints = document.createElement('div');
    hints.className = 'tb-editor-hints';
    hints.innerHTML = '<span class="tb-hint-key">Ctrl+S</span> salvar &bull; <span class="tb-hint-key">Esc</span> cancelar';
    footer.appendChild(hints);

    const btnGroup = document.createElement('div');
    btnGroup.className = 'tb-editor-actions';

    const cancelBtn = document.createElement('button');
    cancelBtn.type = 'button';
    cancelBtn.className = 'tb-btn-cancel';
    cancelBtn.innerHTML = `
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M18 6 6 18"/><path d="m6 6 12 12"/>
      </svg>
      <span>Cancelar</span>
    `;
    cancelBtn.addEventListener('click', (e) => {
      e.preventDefault();
      this.cancel();
    });

    const saveBtn = document.createElement('button');
    saveBtn.type = 'button';
    saveBtn.className = 'tb-btn-save';
    saveBtn.innerHTML = `
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <polyline points="20 6 9 17 4 12"/>
      </svg>
      <span>Salvar</span>
    `;
    saveBtn.addEventListener('click', (e) => {
      e.preventDefault();
      this.save();
    });

    btnGroup.appendChild(cancelBtn);
    btnGroup.appendChild(saveBtn);
    footer.appendChild(btnGroup);

    this.element.appendChild(footer);
  }

  wrapSelection(prefix, suffix, fallback = '') {
    if (!this.textarea) return;
    const start = this.textarea.selectionStart;
    const end = this.textarea.selectionEnd;
    const selected = this.textarea.value.substring(start, end) || fallback;
    const replacement = `${prefix}${selected}${suffix}`;

    this.textarea.value = this.textarea.value.substring(0, start) + replacement + this.textarea.value.substring(end);
    this.textarea.focus();
    this.textarea.selectionStart = start + prefix.length;
    this.textarea.selectionEnd = start + prefix.length + selected.length;

    this.value = this.textarea.value;
    if (typeof this.onChange === 'function') {
      this.onChange(this.value);
    }
  }

  prefixLine(prefix) {
    if (!this.textarea) return;
    const start = this.textarea.selectionStart;
    const val = this.textarea.value;
    const lineStart = val.lastIndexOf('\n', start - 1) + 1;

    this.textarea.value = val.substring(0, lineStart) + prefix + val.substring(lineStart);
    this.textarea.focus();
    this.textarea.selectionStart = this.textarea.selectionEnd = start + prefix.length;

    this.value = this.textarea.value;
    if (typeof this.onChange === 'function') {
      this.onChange(this.value);
    }
  }

  wrapCode() {
    if (!this.textarea) return;
    const start = this.textarea.selectionStart;
    const end = this.textarea.selectionEnd;
    const selected = this.textarea.value.substring(start, end);

    if (selected.includes('\n')) {
      this.wrapSelection('```\n', '\n```', 'código');
    } else {
      this.wrapSelection('`', '`', 'código');
    }
  }

  insertLink() {
    if (!this.textarea) return;
    const start = this.textarea.selectionStart;
    const end = this.textarea.selectionEnd;
    const selected = this.textarea.value.substring(start, end) || 'texto';
    const replacement = `[${selected}](https://)`;

    this.textarea.value = this.textarea.value.substring(0, start) + replacement + this.textarea.value.substring(end);
    this.textarea.focus();
    this.textarea.selectionStart = start + replacement.length - 9;
    this.textarea.selectionEnd = start + replacement.length - 1;

    this.value = this.textarea.value;
    if (typeof this.onChange === 'function') {
      this.onChange(this.value);
    }
  }

  save() {
    if (this.textarea) {
      this.value = this.textarea.value;
    }
    if (typeof this.onSave === 'function') {
      this.onSave(this.value);
    }
  }

  cancel() {
    if (typeof this.onCancel === 'function') {
      this.onCancel();
    }
  }

  focus() {
    if (this.textarea) {
      this.textarea.focus();
    }
  }

  setValue(val) {
    this.value = String(val ?? '');
    if (this.textarea) {
      this.textarea.value = this.value;
    }
  }

  getValue() {
    return this.textarea ? this.textarea.value : this.value;
  }

  destroy() {
    this.element.innerHTML = '';
  }
}
