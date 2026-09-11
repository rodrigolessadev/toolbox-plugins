import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { parseMarkdown, sanitizeHtml, escapeHtml, slugify } from '../src/parser.js';

describe('Parser & Sanitizer Tests', () => {
  test('escapeHtml correctly escapes special characters', () => {
    assert.equal(escapeHtml('<div class="test">a & b \'c\'</div>'), '&lt;div class=&quot;test&quot;&gt;a &amp; b &#039;c&#039;&lt;/div&gt;');
  });

  test('slugify generates clean url slugs', () => {
    assert.equal(slugify('Minha Tarefa de 2026!'), 'minha-tarefa-de-2026');
    assert.equal(slugify('  Header -- Com Espaços__  '), 'header-com-espacos');
  });

  test('sanitizeHtml neutralizes script tags and inline handlers', () => {
    const malicious = '<p>Olá</p><script>alert("xss")</script><img src="x" onerror="alert(1)">';
    const clean = sanitizeHtml(malicious);
    assert.ok(!clean.includes('<script>'), 'Não deve conter script tag');
    assert.ok(!clean.includes('onerror'), 'Não deve conter inline onerror');
    assert.ok(clean.includes('<p>Olá</p>'));
  });

  test('sanitizeHtml neutralizes javascript: and data: URLs', () => {
    const malicious = '<a href="javascript:alert(1)">Clique</a><iframe src="data:text/html,<script>alert(1)</script>"></iframe>';
    const clean = sanitizeHtml(malicious);
    assert.ok(!clean.includes('href="javascript:'), 'Não deve conter href com javascript:');
    assert.ok(!clean.includes('<iframe'), 'Não deve conter iframe');
  });

  test('parseMarkdown renders headings and generates TOC', () => {
    const md = '# Título Principal\n## Subtítulo 1\n### Seção A';
    const { html, toc } = parseMarkdown(md);

    assert.equal(toc.length, 3);
    assert.equal(toc[0].title, 'Título Principal');
    assert.equal(toc[0].level, 1);
    assert.equal(toc[0].id, 'titulo-principal');

    assert.ok(html.includes('<h1 id="titulo-principal" class="tb-heading tb-h1">Título Principal</h1>'));
    assert.ok(html.includes('<h2 id="subtitulo-1" class="tb-heading tb-h2">Subtítulo 1</h2>'));
    assert.ok(html.includes('<h3 id="secao-a" class="tb-heading tb-h3">Seção A</h3>'));
  });

  test('parseMarkdown renders bold, italic, code and links', () => {
    const md = 'Este é um **texto em negrito** e este é *itálico* com `código inline` e [Link](https://google.com).';
    const { html } = parseMarkdown(md);

    assert.ok(html.includes('<strong>texto em negrito</strong>'));
    assert.ok(html.includes('<em>itálico</em>'));
    assert.ok(html.includes('<code class="tb-inline-code">código inline</code>'));
    assert.ok(html.includes('<a href="https://google.com" target="_blank" rel="noopener noreferrer" class="tb-link">Link</a>'));
  });

  test('parseMarkdown renders task lists (checklists)', () => {
    const md = '- [ ] Tarefa Pendente\n- [x] Tarefa Concluída';
    const { html } = parseMarkdown(md);

    assert.ok(html.includes('class="tb-list tb-task-list"'));
    assert.ok(html.includes('disabled class="tb-task-checkbox"'));
    assert.ok(html.includes('checked'));
    assert.ok(html.includes('Tarefa Pendente'));
    assert.ok(html.includes('Tarefa Concluída'));
  });

  test('parseMarkdown renders code blocks with copy button', () => {
    const md = '```javascript\nconst a = 10;\nconsole.log(a);\n```';
    const { html } = parseMarkdown(md);

    assert.ok(html.includes('class="tb-code-block"'));
    assert.ok(html.includes('class="tb-btn-copy-code"'));
    assert.ok(html.includes('language-javascript'));
    assert.ok(html.includes('const a = 10;'));
  });

  test('parseMarkdown renders tables', () => {
    const md = '| Item | Preço |\n| --- | --- |\n| Maçã | R$ 2,00 |\n| Banana | R$ 1,50 |';
    const { html } = parseMarkdown(md);

    assert.ok(html.includes('class="tb-table-wrapper"'));
    assert.ok(html.includes('<th>Item</th>'));
    assert.ok(html.includes('<td>R$ 2,00</td>'));
  });

  test('parseMarkdown renders GitHub alerts', () => {
    const md = '> [!NOTE]\n> Esta é uma nota importante.';
    const { html } = parseMarkdown(md);

    assert.ok(html.includes('tb-alert-note'));
    assert.ok(html.includes('NOTE'));
    assert.ok(html.includes('Esta é uma nota importante.'));
  });
});
