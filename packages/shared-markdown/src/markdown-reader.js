/**
 * @toolbox-plugins/shared-markdown - MarkdownReader
 * Submodule responsible for rendering static, formatted, sanitized Markdown
 * with optional toggle edit action and code copy support.
 */

import { parseMarkdown } from './parser.js';

export class MarkdownReader {
  /**
   * @param {Object} options
   * @param {string} [options.value='']
   * @param {boolean} [options.allowToggleEdit=false]
   * @param {boolean} [options.readOnly=false]
   * @param {string} [options.placeholder='']
   * @param {() => void} [options.onEditRequested]
   */
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

    // Header with Edit action if allowed
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

    // Content container
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
