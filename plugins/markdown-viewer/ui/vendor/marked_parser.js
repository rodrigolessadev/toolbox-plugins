/**
 * Marked Parser Bridge for Markdown Viewer
 * Consome o componente compartilhado oficial @toolbox-plugins/shared-markdown
 * eliminando duplicação de regras de parsing e sanitização.
 */

(function (root) {
  function getShared() {
    if (typeof window !== 'undefined' && window.ToolboxMarkdown) {
      return window.ToolboxMarkdown;
    }
    if (typeof require !== 'undefined') {
      try {
        return require('./markdown-field.js');
      } catch (_) {
        try {
          return require('../../../shared/ui/markdown/markdown-field.js');
        } catch (__) {}
      }
    }
    return null;
  }

  function parseMarkdown(md, options = { highlight: true }) {
    const shared = getShared();
    if (shared && typeof shared.parseMarkdown === 'function') {
      const opts = Object.assign({ highlight: true }, options);
      return shared.parseMarkdown(md, opts);
    }
    // Fallback de segurança se o bundle compartilhado ainda não estiver disponível
    const str = String(md || '');
    return {
      html: `<pre class="tb-pre"><code>${escapeHtml(str)}</code></pre>`,
      toc: []
    };
  }

  function escapeHtml(str) {
    const shared = getShared();
    if (shared && typeof shared.escapeHtml === 'function') {
      return shared.escapeHtml(str);
    }
    return String(str ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function slugify(text) {
    const shared = getShared();
    if (shared && typeof shared.slugify === 'function') {
      return shared.slugify(text);
    }
    return String(text ?? '')
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .toLowerCase()
      .trim()
      .replace(/[^\w\s-]/g, '')
      .replace(/[\s_-]+/g, '-')
      .replace(/^-+|-+$/g, '');
  }

  function highlightSyntax(code, lang) {
    const shared = getShared();
    if (shared && typeof shared.highlightSyntax === 'function') {
      return shared.highlightSyntax(code, lang);
    }
    return code;
  }

  root.parseMarkdown = parseMarkdown;
  root.escapeHtml = escapeHtml;
  root.slugify = slugify;
  root.highlightSyntax = highlightSyntax;

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = { parseMarkdown, escapeHtml, slugify, highlightSyntax };
  }
})(typeof window !== 'undefined' ? window : globalThis);
