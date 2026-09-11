/**
 * @toolbox-plugins/shared-markdown - Bundle Autossuficiente para Plugins
 * Inclui Parser GFM com sanitização XSS, MarkdownReader, MarkdownEditor e MarkdownField.
 */

// --- 1. Parser & Sanitizer ---

export function escapeHtml(str) {
  return String(str ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

export function sanitizeHtml(html) {
  if (!html) return '';
  let sanitized = String(html);
  sanitized = sanitized.replace(/<(script|iframe|object|embed|applet|meta|link|style|base|form)[\s\S]*?<\/\1>/gi, '');
  sanitized = sanitized.replace(/<(script|iframe|object|embed|applet|meta|link|style|base|form)[^>]*\/?>/gi, '');
  sanitized = sanitized.replace(/\s+on[a-z]+(\s*=\s*(?:'[^']*'|"[^"]*"|[^\s>]+))?/gi, '');
  sanitized = sanitized.replace(/\b(href|src)\s*=\s*(['"])\s*(javascript|vbscript|data\s*:\s*text\/html):/gi, '$1=$2about:blank#blocked-');
  return sanitized;
}

export function slugify(text) {
  return String(text ?? '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .trim()
    .replace(/[^\w\s-]/g, '')
    .replace(/[\s_-]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

function inlineMarkdown(text) {
  if (!text) return '';
  let s = escapeHtml(text);
  s = s.replace(/`([^`]+)`/g, '<code class="tb-inline-code">$1</code>');
  s = s.replace(/([*_]{3})((?:\\.|(?!\1).)+?)\1/g, '<strong><em>$2</em></strong>');
  s = s.replace(/([*_]{2})((?:\\.|(?!\1).)+?)\1/g, '<strong>$2</strong>');
  s = s.replace(/([*_])((?:\\.|(?!\1).)+?)\1/g, '<em>$2</em>');
  s = s.replace(/~~((?:\\.|(?!~~).)+?)~~/g, '<del>$1</del>');
  s = s.replace(/^\[x\]\s*/i, '<input type="checkbox" checked disabled class="tb-checkbox" /> ');
  s = s.replace(/^\[ \]\s*/, '<input type="checkbox" disabled class="tb-checkbox" /> ');
  s = s.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (match, txt, url) => {
    const trimmedUrl = url.trim();
    if (/^(javascript|vbscript|data\s*:)/i.test(trimmedUrl)) return txt;
    return `<a href="${trimmedUrl}" target="_blank" rel="noopener noreferrer" class="tb-link">${txt}</a>`;
  });
  s = s.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, (match, alt, url) => {
    const trimmedUrl = url.trim();
    if (/^(javascript|vbscript|data\s*:)/i.test(trimmedUrl)) return '';
    return `<img src="${trimmedUrl}" alt="${alt}" class="tb-img" loading="lazy" />`;
  });
  return s;
}

export function parseMarkdown(md) {
  if (!md) return { html: '', toc: [] };

  const toc = [];
  const lines = md.split(/\r?\n/);
  const out = [];

  let inCodeBlock = false;
  let codeLang = '';
  let codeBuffer = [];

  let inTable = false;
  let tableBuffer = [];

  let inList = false;
  let listType = null;

  function flushList() {
    if (inList) {
      out.push(`</${listType}>`);
      inList = false;
      listType = null;
    }
  }

  function flushTable() {
    if (tableBuffer.length === 0) return;
    let html = '<div class="tb-table-wrapper"><table class="tb-table">';
    let isHeader = true;

    for (let r = 0; r < tableBuffer.length; r++) {
      const row = tableBuffer[r].trim();
      if (/^\|?[\s-:]+\|[\s-:]+\|?$/.test(row) || /^\|?[-:\s|]+$/.test(row)) continue;
      const cols = row.split('|').map(c => c.trim()).filter((c, idx, arr) => {
        if (idx === 0 && c === '' && row.startsWith('|')) return false;
        if (idx === arr.length - 1 && c === '' && row.endsWith('|')) return false;
        return true;
      });

      if (isHeader) {
        html += '<thead><tr>';
        cols.forEach(c => { html += `<th>${inlineMarkdown(c)}</th>`; });
        html += '</tr></thead><tbody>';
        isHeader = false;
      } else {
        html += '<tr>';
        cols.forEach(c => { html += `<td>${inlineMarkdown(c)}</td>`; });
        html += '</tr>';
      }
    }
    if (!isHeader) html += '</tbody>';
    html += '</table></div>';
    out.push(html);
    tableBuffer = [];
    inTable = false;
  }

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    if (/^```/.test(line)) {
      if (inCodeBlock) {
        const rawCode = codeBuffer.join('\n');
        const escaped = escapeHtml(rawCode);
        out.push(
          `<div class="tb-code-block">` +
            `<div class="tb-code-header">` +
              `<span class="tb-code-lang">${escapeHtml(codeLang || 'plaintext')}</span>` +
              `<button type="button" class="tb-btn-copy-code" title="Copiar código">` +
                `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/></svg>` +
                `<span class="tb-copy-label">Copiar</span>` +
              `</button>` +
            `</div>` +
            `<pre class="tb-pre"><code class="language-${escapeHtml(codeLang)}">${escaped}</code></pre>` +
          `</div>`
        );
        inCodeBlock = false;
        codeLang = '';
        codeBuffer = [];
      } else {
        flushList();
        if (inTable) flushTable();
        inCodeBlock = true;
        codeLang = line.replace(/^```/, '').trim();
        codeBuffer = [];
      }
      continue;
    }

    if (inCodeBlock) {
      codeBuffer.push(line);
      continue;
    }

    if (/^\s*\|/.test(line)) {
      flushList();
      inTable = true;
      tableBuffer.push(line);
      continue;
    } else if (inTable) {
      flushTable();
    }

    if (line.trim() === '') {
      flushList();
      continue;
    }

    if (/^(\*{3,}|-{3,}|_{3,})$/.test(line.trim())) {
      flushList();
      out.push('<hr class="tb-hr" />');
      continue;
    }

    const alertMatch = line.match(/^>\s*\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]/i);
    if (alertMatch) {
      flushList();
      const alertType = alertMatch[1].toLowerCase();
      let alertContent = [];
      while (i + 1 < lines.length && lines[i + 1].startsWith('>')) {
        i++;
        alertContent.push(lines[i].replace(/^>\s?/, ''));
      }
      const renderedAlert = alertContent.map(inlineMarkdown).join('<br />');
      out.push(
        `<div class="tb-alert tb-alert-${alertType}">` +
          `<div class="tb-alert-title">${alertType.toUpperCase()}</div>` +
          `<div class="tb-alert-body">${renderedAlert}</div>` +
        `</div>`
      );
      continue;
    }

    if (/^>\s?/.test(line)) {
      flushList();
      let bqContent = [line.replace(/^>\s?/, '')];
      while (i + 1 < lines.length && /^>\s?/.test(lines[i + 1])) {
        i++;
        bqContent.push(lines[i].replace(/^>\s?/, ''));
      }
      const renderedBq = bqContent.map(inlineMarkdown).join('<br />');
      out.push(`<blockquote class="tb-blockquote">${renderedBq}</blockquote>`);
      continue;
    }

    const headingMatch = line.match(/^(#{1,6})\s+(.+)$/);
    if (headingMatch) {
      flushList();
      const level = headingMatch[1].length;
      const title = headingMatch[2].trim();
      const id = slugify(title);
      toc.push({ level, title, id });
      out.push(`<h${level} id="${id}" class="tb-heading tb-h${level}">${inlineMarkdown(title)}</h${level}>`);
      continue;
    }

    const checkMatch = line.match(/^(\s*)([-*+])\s+\[([ xX])\]\s+(.+)$/);
    if (checkMatch) {
      if (!inList || listType !== 'ul') {
        flushList();
        inList = true;
        listType = 'ul';
        out.push('<ul class="tb-list tb-task-list">');
      }
      const isChecked = checkMatch[3].toLowerCase() === 'x';
      const itemText = checkMatch[4];
      out.push(
        `<li class="tb-task-item">` +
          `<input type="checkbox" ${isChecked ? 'checked' : ''} disabled class="tb-task-checkbox" /> ` +
          `<span>${inlineMarkdown(itemText)}</span>` +
        `</li>`
      );
      continue;
    }

    const ulMatch = line.match(/^(\s*)([-*+])\s+(.+)$/);
    if (ulMatch) {
      if (!inList || listType !== 'ul') {
        flushList();
        inList = true;
        listType = 'ul';
        out.push('<ul class="tb-list">');
      }
      out.push(`<li>${inlineMarkdown(ulMatch[3])}</li>`);
      continue;
    }

    const olMatch = line.match(/^(\s*)(\d+)\.\s+(.+)$/);
    if (olMatch) {
      if (!inList || listType !== 'ol') {
        flushList();
        inList = true;
        listType = 'ol';
        out.push('<ol class="tb-list tb-ordered-list">');
      }
      out.push(`<li>${inlineMarkdown(olMatch[3])}</li>`);
      continue;
    }

    flushList();
    out.push(`<p class="tb-p">${inlineMarkdown(line)}</p>`);
  }

  if (inCodeBlock) {
    const rawCode = codeBuffer.join('\n');
    out.push(`<pre class="tb-pre"><code class="language-${escapeHtml(codeLang)}">${escapeHtml(rawCode)}</code></pre>`);
  }
  if (inTable) flushTable();
  flushList();

  return { html: sanitizeHtml(out.join('\n')), toc };
}

// --- 2. MarkdownReader ---

export class MarkdownReader {
  constructor(options = {}) {
    this.value = options.value ?? '';
    this.allowToggleEdit = Boolean(options.allowToggleEdit);
    this.readOnly = Boolean(options.readOnly);
    this.placeholder = options.placeholder ?? '';
    this.onEditRequested = options.onEditRequested ?? null;

    this.element = document.createElement('div');
    this.element.className = 'tb-markdown-reader';
    this.render();
  }

  render() {
    this.element.innerHTML = '';

    if (this.allowToggleEdit && !this.readOnly) {
      const header = document.createElement('div');
      header.className = 'tb-reader-header';

      const editBtn = document.createElement('button');
      editBtn.type = 'button';
      editBtn.className = 'tb-btn-edit-action';
      editBtn.title = 'Editar conteúdo';
      editBtn.innerHTML = `
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z"/>
          <path d="m15 5 4 4"/>
        </svg>
        <span class="tb-edit-label">Editar</span>
      `;
      editBtn.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        if (typeof this.onEditRequested === 'function') {
          this.onEditRequested();
        }
      });
      header.appendChild(editBtn);
      this.element.appendChild(header);
    }

    const body = document.createElement('div');
    body.className = 'tb-reader-body';

    if (!this.value || this.value.trim() === '') {
      const placeholderText = this.placeholder || 'Nenhum conteúdo informado.';
      body.innerHTML = `<div class="tb-reader-placeholder">${placeholderText}</div>`;
    } else {
      const { html } = parseMarkdown(this.value);
      body.innerHTML = html;
      this.bindCopyButtons(body);
    }

    this.element.appendChild(body);
  }

  bindCopyButtons(container) {
    const copyBtns = container.querySelectorAll('.tb-btn-copy-code');
    copyBtns.forEach((btn) => {
      btn.addEventListener('click', async (e) => {
        e.preventDefault();
        const codeBlock = btn.closest('.tb-code-block');
        if (!codeBlock) return;
        const codeElem = codeBlock.querySelector('pre code');
        if (!codeElem) return;

        const textToCopy = codeElem.innerText;
        try {
          if (navigator.clipboard && navigator.clipboard.writeText) {
            await navigator.clipboard.writeText(textToCopy);
          } else {
            const textarea = document.createElement('textarea');
            textarea.value = textToCopy;
            textarea.style.position = 'fixed';
            textarea.style.opacity = '0';
            document.body.appendChild(textarea);
            textarea.select();
            document.execCommand('copy');
            document.body.removeChild(textarea);
          }

          const label = btn.querySelector('.tb-copy-label');
          if (label) {
            const original = label.textContent;
            label.textContent = 'Copiado!';
            btn.classList.add('tb-copied');
            setTimeout(() => {
              label.textContent = original;
              btn.classList.remove('tb-copied');
            }, 2000);
          }
        } catch (err) {
          console.error('Falha ao copiar código:', err);
        }
      });
    });
  }

  setValue(newValue) {
    this.value = String(newValue ?? '');
    this.render();
  }

  getValue() {
    return this.value;
  }

  destroy() {
    this.element.innerHTML = '';
  }
}

// --- 3. MarkdownEditor ---

export class MarkdownEditor {
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
      if ((e.ctrlKey || e.metaKey) && (e.key === 'Enter' || e.key === 's' || e.key === 'S')) {
        e.preventDefault();
        this.save();
      }
      if (e.key === 'Escape') {
        e.preventDefault();
        this.cancel();
      }
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
    if (typeof this.onChange === 'function') this.onChange(this.value);
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
    if (typeof this.onChange === 'function') this.onChange(this.value);
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
    if (typeof this.onChange === 'function') this.onChange(this.value);
  }

  save() {
    if (this.textarea) this.value = this.textarea.value;
    if (typeof this.onSave === 'function') this.onSave(this.value);
  }

  cancel() {
    if (typeof this.onCancel === 'function') this.onCancel();
  }

  focus() {
    if (this.textarea) this.textarea.focus();
  }

  setValue(val) {
    this.value = String(val ?? '');
    if (this.textarea) this.textarea.value = this.value;
  }

  getValue() {
    return this.textarea ? this.textarea.value : this.value;
  }

  destroy() {
    this.element.innerHTML = '';
  }
}

// --- 4. MarkdownField (Componente Híbrido Unificado) ---

export class MarkdownField {
  constructor(options = {}) {
    this.value = String(options.value ?? '');
    this.initialValue = this.value;
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
    if (this.readOnly && newMode === 'edit') return;
    const targetMode = newMode === 'edit' ? 'edit' : 'view';
    if (this.mode === targetMode) return;

    if (this.mode === 'edit' && targetMode === 'view' && !keepCurrentValue) {
      if (this.activeInstance && typeof this.activeInstance.getValue === 'function') {
        this.value = this.activeInstance.getValue();
      }
    } else if (targetMode === 'edit') {
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

// Global Browser Registration
if (typeof window !== 'undefined') {
  window.ToolboxMarkdown = {
    MarkdownField,
    MarkdownReader,
    MarkdownEditor,
    parseMarkdown,
    sanitizeHtml,
    escapeHtml,
    slugify,
  };
}

// Web Component
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
      if (name === 'value') this._field.setValue(newVal);
      if (name === 'mode') this._field.setMode(newVal);
    }

    get value() {
      return this._field ? this._field.getValue() : this.getAttribute('value');
    }

    set value(val) {
      if (this._field) this._field.setValue(val);
      else this.setAttribute('value', val);
    }
  }

  customElements.define('markdown-field', MarkdownFieldElement);
}
