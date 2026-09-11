/**
 * @toolbox-plugins/shared-markdown - Parser & XSS Sanitizer
 * Fast, self-contained Markdown parser with GitHub Flavored Markdown (GFM),
 * strict XSS sanitization, code blocks with copy action, checklists, tables and alerts.
 */

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

  // 1. Remove dangerous tags and their content
  sanitized = sanitized.replace(/<(script|iframe|object|embed|applet|meta|link|style|base|form)[\s\S]*?<\/\1>/gi, '');
  sanitized = sanitized.replace(/<(script|iframe|object|embed|applet|meta|link|style|base|form)[^>]*\/?>/gi, '');

  // 2. Remove inline event handlers (onerror, onload, onclick, etc.)
  sanitized = sanitized.replace(/\s+on[a-z]+(\s*=\s*(?:'[^']*'|"[^"]*"|[^\s>]+))?/gi, '');

  // 3. Neutralize dangerous URL schemes in href and src
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

  // Inline code: `code`
  s = s.replace(/`([^`]+)`/g, '<code class="tb-inline-code">$1</code>');

  // Bold & Italic: ***text*** or ___text___
  s = s.replace(/([*_]{3})((?:\\.|(?!\1).)+?)\1/g, '<strong><em>$2</em></strong>');

  // Bold: **text** or __text__
  s = s.replace(/([*_]{2})((?:\\.|(?!\1).)+?)\1/g, '<strong>$2</strong>');

  // Italic: *text* or _text_
  s = s.replace(/([*_])((?:\\.|(?!\1).)+?)\1/g, '<em>$2</em>');

  // Strikethrough: ~~text~~
  s = s.replace(/~~((?:\\.|(?!~~).)+?)~~/g, '<del>$1</del>');

  // Checkbox items inline: [x] or [ ]
  s = s.replace(/^\[x\]\s*/i, '<input type="checkbox" checked disabled class="tb-checkbox" /> ');
  s = s.replace(/^\[ \]\s*/, '<input type="checkbox" disabled class="tb-checkbox" /> ');

  // Links: [text](url)
  s = s.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (match, txt, url) => {
    const trimmedUrl = url.trim();
    if (/^(javascript|vbscript|data\s*:)/i.test(trimmedUrl)) {
      return txt;
    }
    return `<a href="${trimmedUrl}" target="_blank" rel="noopener noreferrer" class="tb-link">${txt}</a>`;
  });

  // Images: ![alt](url)
  s = s.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, (match, alt, url) => {
    const trimmedUrl = url.trim();
    if (/^(javascript|vbscript|data\s*:)/i.test(trimmedUrl)) {
      return '';
    }
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
  let listType = null; // 'ul' | 'ol'

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
      if (/^\|?[\s-:]+\|[\s-:]+\|?$/.test(row) || /^\|?[-:\s|]+$/.test(row)) {
        continue;
      }
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
    if (!isHeader) {
      html += '</tbody>';
    }
    html += '</table></div>';
    out.push(html);
    tableBuffer = [];
    inTable = false;
  }

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    // Fenced Code Block start/end
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

    // Tables (| col1 | col2 |)
    if (/^\s*\|/.test(line)) {
      flushList();
      inTable = true;
      tableBuffer.push(line);
      continue;
    } else if (inTable) {
      flushTable();
    }

    // Blank line
    if (line.trim() === '') {
      flushList();
      continue;
    }

    // Horizontal Rule
    if (/^(\*{3,}|-{3,}|_{3,})$/.test(line.trim())) {
      flushList();
      out.push('<hr class="tb-hr" />');
      continue;
    }

    // GitHub Alerts: > [!NOTE], > [!TIP], > [!IMPORTANT], > [!WARNING], > [!CAUTION]
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

    // Blockquote: > text
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

    // Headings: # H1 ... ###### H6
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

    // Checklist item: - [ ] or - [x]
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

    // Unordered List: * or - or +
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

    // Ordered List: 1. text
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

    // Standard Paragraph
    flushList();
    out.push(`<p class="tb-p">${inlineMarkdown(line)}</p>`);
  }

  if (inCodeBlock) {
    const rawCode = codeBuffer.join('\n');
    out.push(`<pre class="tb-pre"><code class="language-${escapeHtml(codeLang)}">${escapeHtml(rawCode)}</code></pre>`);
  }

  if (inTable) {
    flushTable();
  }

  flushList();

  const finalHtml = sanitizeHtml(out.join('\n'));
  return { html: finalHtml, toc };
}
