/**
 * Fast, standalone Markdown parser with GitHub Flavored Markdown (GFM),
 * GitHub Alerts, Code Blocks with syntax highlight & copy button,
 * Tables, and Mermaid diagram support.
 */

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function slugify(text) {
  return text
    .toLowerCase()
    .trim()
    .replace(/[^\w\s-]/g, '')
    .replace(/[\s_-]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

function parseMarkdown(md) {
  if (!md) return { html: '', toc: [] };

  const toc = [];
  const lines = md.split(/\r?\n/);
  const out = [];
  let inCodeBlock = false;
  let codeLang = '';
  let codeBuffer = [];
  let inTable = false;
  let tableBuffer = [];

  function flushTable() {
    if (tableBuffer.length === 0) return;
    let html = '<div class="table-container"><table>';
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
    html += '</tbody></table></div>';
    out.push(html);
    tableBuffer = [];
    inTable = false;
  }

  function flushCodeBlock() {
    const rawCode = codeBuffer.join('\n');
    const escaped = escapeHtml(rawCode);

    if (codeLang === 'mermaid') {
      out.push(`<div class="mermaid-block"><pre class="mermaid">${escaped}</pre></div>`);
    } else {
      const langLabel = codeLang ? `<span class="code-lang">${escapeHtml(codeLang)}</span>` : '';
      out.push(`
        <div class="code-block-wrapper">
          <div class="code-header">
            ${langLabel}
            <button type="button" class="btn-copy-code" onclick="copyCode(this)" title="Copiar código">
              <span data-icon="copy"></span> Copiar
            </button>
          </div>
          <pre><code class="language-${escapeHtml(codeLang)}">${highlightSyntax(escaped, codeLang)}</code></pre>
        </div>
      `);
    }
    codeBuffer = [];
    inCodeBlock = false;
    codeLang = '';
  }

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    // Fenced code block check
    const codeMatch = line.match(/^```(\w*)/);
    if (codeMatch) {
      if (inTable) flushTable();
      if (inCodeBlock) {
        flushCodeBlock();
      } else {
        inCodeBlock = true;
        codeLang = codeMatch[1].toLowerCase().trim();
      }
      continue;
    }

    if (inCodeBlock) {
      codeBuffer.push(line);
      continue;
    }

    // Table check (lines with pipe '|')
    if (/^\|(.+)\|$/.test(line.trim()) || (/^.+\|.+$/.test(line.trim()) && !line.startsWith('>'))) {
      inTable = true;
      tableBuffer.push(line);
      continue;
    } else if (inTable) {
      flushTable();
    }

    // Empty line
    if (!line.trim()) {
      out.push('');
      continue;
    }

    // Headings
    const headingMatch = line.match(/^(#{1,6})\s+(.+)$/);
    if (headingMatch) {
      const level = headingMatch[1].length;
      const text = headingMatch[2].trim();
      const id = slugify(text) || `heading-${toc.length + 1}`;
      toc.push({ level, text, id });
      out.push(`<h${level} id="${id}"><a href="#${id}" class="heading-anchor">#</a> ${inlineMarkdown(text)}</h${level}>`);
      continue;
    }

    // Horizontal Rule
    if (/^(\*{3,}|-{3,}|_{3,})$/.test(line.trim())) {
      out.push('<hr>');
      continue;
    }

    // GitHub Alerts (> [!NOTE], > [!TIP], > [!IMPORTANT], > [!WARNING], > [!CAUTION])
    const alertMatch = line.match(/^>\s*\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]/i);
    if (alertMatch) {
      const type = alertMatch[1].toUpperCase();
      let alertContent = [];
      while (i + 1 < lines.length && lines[i + 1].startsWith('>')) {
        i++;
        alertContent.push(lines[i].replace(/^>\s?/, ''));
      }
      const body = alertContent.map(inlineMarkdown).join('<br>');
      out.push(`
        <div class="alert alert-${type.toLowerCase()}">
          <div class="alert-title">
            <span class="alert-icon"></span>
            ${type}
          </div>
          <div class="alert-body">${body}</div>
        </div>
      `);
      continue;
    }

    // Standard Blockquote
    if (line.startsWith('>')) {
      const bqText = line.replace(/^>\s?/, '');
      out.push(`<blockquote><p>${inlineMarkdown(bqText)}</p></blockquote>`);
      continue;
    }

    // Task list check
    const taskMatch = line.match(/^(\s*)-\s+\[([ xX])\]\s+(.+)$/);
    if (taskMatch) {
      const checked = taskMatch[2].toLowerCase() === 'x' ? 'checked' : '';
      out.push(`<div class="task-list-item"><input type="checkbox" ${checked} disabled> <span>${inlineMarkdown(taskMatch[3])}</span></div>`);
      continue;
    }

    // Unordered List
    if (/^\s*[-*+]\s+(.+)$/.test(line)) {
      const item = line.replace(/^\s*[-*+]\s+/, '');
      out.push(`<ul><li>${inlineMarkdown(item)}</li></ul>`);
      continue;
    }

    // Ordered List
    const numMatch = line.match(/^\s*(\d+)\.\s+(.+)$/);
    if (numMatch) {
      out.push(`<ol start="${numMatch[1]}"><li>${inlineMarkdown(numMatch[2])}</li></ol>`);
      continue;
    }

    // Regular Paragraph
    out.push(`<p>${inlineMarkdown(line)}</p>`);
  }

  if (inTable) flushTable();
  if (inCodeBlock) flushCodeBlock();

  // Combine adjacent <ul> and <ol>
  let finalHtml = out.join('\n')
    .replace(/<\/ul>\s*<ul>/g, '')
    .replace(/<\/ol>\s*<ol[^>]*>/g, '');

  return { html: finalHtml, toc };
}

function inlineMarkdown(text) {
  let res = escapeHtml(text);

  // Inline Code
  res = res.replace(/`([^`]+)`/g, '<code>$1</code>');

  // Bold & Italic
  res = res.replace(/\*\*\*([^*]+)\*\*\*/g, '<strong><em>$1</em></strong>');
  res = res.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  res = res.replace(/\*([^*]+)\*/g, '<em>$1</em>');
  res = res.replace(/___([^_]+)___/g, '<strong><em>$1</em></strong>');
  res = res.replace(/__([^_]+)__/g, '<strong>$1</strong>');
  res = res.replace(/_([^_]+)_/g, '<em>$1</em>');

  // Strikethrough
  res = res.replace(/~~([^~]+)~~/g, '<del>$1</del>');

  // Images ![alt](url)
  res = res.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, '<img src="$2" alt="$1" class="md-image">');

  // Links [text](url)
  res = res.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');

  return res;
}

function highlightSyntax(code, lang) {
  if (!code) return '';

  if (lang === 'json') {
    return code
      .replace(/(&quot;[\w-]+&quot;)\s*:/g, '<span class="tok-key">$1</span>:')
      .replace(/:\s*(&quot;[^&]*&quot;)/g, ': <span class="tok-string">$1</span>')
      .replace(/:\s*(\b\d+\.?\d*\b)/g, ': <span class="tok-number">$1</span>')
      .replace(/:\s*(true|false|null)\b/g, ': <span class="tok-keyword">$1</span>');
  }

  if (lang === 'python' || lang === 'py') {
    const kws = ['def', 'class', 'import', 'from', 'return', 'if', 'elif', 'else', 'for', 'while', 'in', 'try', 'except', 'finally', 'with', 'as', 'lambda', 'yield', 'async', 'await', 'None', 'True', 'False', 'self'];
    const kwRegex = new RegExp(`\\b(${kws.join('|')})\\b`, 'g');
    return code
      .replace(/(#.*)$/gm, '<span class="tok-comment">$1</span>')
      .replace(/(&quot;.*?&quot;|&#039;.*?&#039;)/g, '<span class="tok-string">$1</span>')
      .replace(kwRegex, '<span class="tok-keyword">$1</span>')
      .replace(/\b(\d+)\b/g, '<span class="tok-number">$1</span>');
  }

  if (lang === 'sql') {
    const sqlKws = ['SELECT', 'FROM', 'WHERE', 'JOIN', 'LEFT', 'RIGHT', 'INNER', 'GROUP', 'BY', 'ORDER', 'LIMIT', 'INSERT', 'INTO', 'UPDATE', 'DELETE', 'CREATE', 'TABLE', 'DROP', 'ALTER', 'AND', 'OR', 'NOT', 'AS', 'ON', 'HAVING', 'COUNT', 'SUM', 'AVG', 'MIN', 'MAX'];
    const sqlRegex = new RegExp(`\\b(${sqlKws.join('|')})\\b`, 'gi');
    return code
      .replace(/(--.*)$/gm, '<span class="tok-comment">$1</span>')
      .replace(/(&quot;.*?&quot;|&#039;.*?&#039;)/g, '<span class="tok-string">$1</span>')
      .replace(sqlRegex, '<span class="tok-keyword">$1</span>');
  }

  if (lang === 'js' || lang === 'javascript' || lang === 'ts') {
    const jsKws = ['const', 'let', 'var', 'function', 'return', 'if', 'else', 'for', 'while', 'import', 'export', 'default', 'from', 'class', 'extends', 'new', 'this', 'async', 'await', 'try', 'catch', 'throw'];
    const jsRegex = new RegExp(`\\b(${jsKws.join('|')})\\b`, 'g');
    return code
      .replace(/(\/\/.*)$/gm, '<span class="tok-comment">$1</span>')
      .replace(/(&quot;.*?&quot;|&#039;.*?&#039;)/g, '<span class="tok-string">$1</span>')
      .replace(jsRegex, '<span class="tok-keyword">$1</span>');
  }

  return code;
}

window.parseMarkdown = parseMarkdown;
