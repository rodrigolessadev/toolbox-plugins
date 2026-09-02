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
    codeIndentLen = 0;
    codeFenceChar = '';
  }

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    // Fenced code block check (suporte a espaços/tabs antes de ``` ou ~~~)
    if (inCodeBlock) {
      const closeFencePattern = codeFenceChar === '~' ? /^\s*~{3,}\s*$/ : /^\s*`{3,}\s*$/;
      if (closeFencePattern.test(line)) {
        flushCodeBlock();
        continue;
      }
      // Remove recuo base correspondente à abertura da cerca
      if (codeIndentLen > 0) {
        const indentRegex = new RegExp(`^[ ]{0,${codeIndentLen}}`);
        codeBuffer.push(line.replace(indentRegex, ''));
      } else {
        codeBuffer.push(line);
      }
      continue;
    }

    const openCodeMatch = line.match(/^(\s*)(`{3,}|~{3,})([^\n\r]*)/);
    if (openCodeMatch) {
      if (inTable) flushTable();
      inCodeBlock = true;
      codeFenceChar = openCodeMatch[2][0];
      codeIndentLen = openCodeMatch[1].replace(/\t/g, '  ').length;
      const rawInfo = openCodeMatch[3] ? openCodeMatch[3].trim() : '';
      codeLang = rawInfo ? rawInfo.split(/\s+/)[0].toLowerCase() : '';
      continue;
    }

    // Indented Code Block check (4 espaços ou 1 tab após linha em branco / início de documento)
    const isIndentedCodeStart = (out.length === 0 || out[out.length - 1] === '') && /^( {4}|\t)/.test(line) && line.trim() !== '';
    if (isIndentedCodeStart) {
      if (inTable) flushTable();
      const rawCodeLines = [];
      while (i < lines.length) {
        const curLine = lines[i];
        if (/^( {4}|\t)/.test(curLine)) {
          rawCodeLines.push(curLine.replace(/^( {4}|\t)/, ''));
          i++;
        } else if (curLine.trim() === '') {
          let nextIndented = false;
          for (let j = i + 1; j < lines.length; j++) {
            if (lines[j].trim() === '') continue;
            if (/^( {4}|\t)/.test(lines[j])) {
              nextIndented = true;
            }
            break;
          }
          if (nextIndented) {
            rawCodeLines.push('');
            i++;
          } else {
            break;
          }
        } else {
          break;
        }
      }
      i--; // adjust loop pointer
      const rawText = rawCodeLines.join('\n');
      const escaped = escapeHtml(rawText);
      out.push(`
        <div class="code-block-wrapper">
          <div class="code-header">
            <span class="code-lang">code</span>
            <button type="button" class="btn-copy-code" onclick="copyCode(this)" title="Copiar código">
              <span data-icon="copy"></span> Copiar
            </button>
          </div>
          <pre><code>${escaped}</code></pre>
        </div>
      `);
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

    // Check if start of a list (unordered, ordered, or task list)
    if (/^\s*[-*+]\s+/.test(line) || /^\s*\d+\.\s+/.test(line)) {
      const listLines = [];
      while (i < lines.length) {
        const curLine = lines[i];
        if (/^\s*(?:`{3,}|~{3,})/.test(curLine)) {
          break;
        }
        if (/^\s*[-*+]\s+/.test(curLine) || /^\s*\d+\.\s+/.test(curLine)) {
          listLines.push(curLine);
          i++;
        } else if (curLine.startsWith('  ') && curLine.trim() !== '') {
          listLines.push(curLine);
          i++;
        } else {
          break;
        }
      }
      i--; // adjust loop pointer
      if (listLines.length > 0) {
        out.push(renderNestedList(listLines));
      }
      continue;
    }

    // Regular Paragraph
    out.push(`<p>${inlineMarkdown(line)}</p>`);
  }

  if (inTable) flushTable();
  if (inCodeBlock) flushCodeBlock();

  return { html: out.join('\n'), toc };
}

function renderNestedList(lines) {
  let html = '';
  const stack = []; // { type: 'ul' | 'ol', level: number }

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const indentMatch = line.match(/^(\s*)/);
    const rawIndent = indentMatch ? indentMatch[1].replace(/\t/g, '  ').length : 0;
    const level = Math.floor(rawIndent / 2);

    const taskMatch = line.match(/^\s*[-*+]\s+\[([ xX])\]\s+(.*)$/);
    const olMatch = line.match(/^\s*\d+\.\s+(.*)$/);
    const ulMatch = line.match(/^\s*[-*+]\s+(.*)$/);

    const type = olMatch ? 'ol' : 'ul';
    let content = '';

    if (taskMatch) {
      const checked = taskMatch[1].toLowerCase() === 'x' ? 'checked' : '';
      content = `<div class="task-list-item"><input type="checkbox" ${checked} disabled> <span>${inlineMarkdown(taskMatch[2])}</span></div>`;
    } else if (olMatch) {
      content = inlineMarkdown(olMatch[1]);
    } else if (ulMatch) {
      content = inlineMarkdown(ulMatch[1]);
    } else {
      // Continuation line of previous list item
      content = inlineMarkdown(line.trim());
      html += ` ${content}`;
      continue;
    }

    if (stack.length === 0) {
      stack.push({ type, level });
      html += `<${type}><li>${content}`;
    } else if (level > stack[stack.length - 1].level) {
      stack.push({ type, level });
      html += `<${type}><li>${content}`;
    } else if (level === stack[stack.length - 1].level) {
      if (type !== stack[stack.length - 1].type) {
        html += `</li></${stack.pop().type}><${type}><li>${content}`;
        stack.push({ type, level });
      } else {
        html += `</li><li>${content}`;
      }
    } else {
      while (stack.length > 0 && level < stack[stack.length - 1].level) {
        html += `</li></${stack.pop().type}>`;
      }
      if (stack.length > 0 && stack[stack.length - 1].level === level) {
        if (type !== stack[stack.length - 1].type) {
          html += `</li></${stack.pop().type}><${type}><li>${content}`;
          stack.push({ type, level });
        } else {
          html += `</li><li>${content}`;
        }
      } else {
        stack.push({ type, level });
        html += `<${type}><li>${content}`;
      }
    }
  }

  while (stack.length > 0) {
    html += `</li></${stack.pop().type}>`;
  }

  return html;
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
