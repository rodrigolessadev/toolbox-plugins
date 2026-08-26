/**
 * Markdown Viewer Application Logic
 */

let state = {
  currentPath: '',
  filename: 'sem-titulo.md',
  content: '',
  viewMode: 'split', // 'reader' | 'split' | 'editor'
  isModified: false
};

const SAMPLE_MARKDOWN = `# 🚀 Visualizador de Markdown — Toolbox

Bem-vindo ao **Visualizador & Editor de Markdown** no padrão oficial **Material Design 3 (M3)**.

> [!NOTE]
> Você pode abrir arquivos locais, arrastar e soltar arquivos \`.md\` nesta janela ou editar o conteúdo em tempo real!

---

## 📌 Principais Recursos

- **Visualização Rica:** Suporte a GitHub Flavored Markdown (GFM), tabelas, alertas e listas de tarefas.
- **Destaque de Sintaxe:** Blocos de código coloridos com botão de cópia rápida em 1 clique.
- **Table of Contents (TOC):** Sumário lateral dinâmico navegável automaticamente gerado dos cabeçalhos.
- **Modos de Exibição:** Modo Leitor (*Zen View*), Modo Dividido (*Split-View*) e Modo Editor Puro.

---

### 💻 Exemplo de Código Python

\`\`\`python
def calcular_metricas(dados: list) -> dict:
    \"\"\"Calcula média e total de dados analíticos.\"\"\"
    total = sum(dados)
    media = total / len(dados) if dados else 0.0
    return {"total": total, "media": media, "status": "OK"}

resultado = calcular_metricas([10, 20, 30, 40, 50])
print(f"Média apurada: {resultado['media']}")
\`\`\`

---

### 📊 Exemplo de Tabela

| Módulo | Versão | Status | Compatibilidade |
| :--- | :---: | :---: | ---: |
| **Toolbox Core** | \`v1.22.3\` | 🟢 Ativo | Windows 10/11 |
| **Marketplace** | \`v4.5.0\` | 🟢 Ativo | Multi-plugins |
| **Theme System** | \`M3\` | 🎨 Dark M3 | Full CSS Tokens |

---

### ✅ Lista de Tarefas (Task List)

- [x] Implementar parser standalone GFM
- [x] Suporte a alertas e notas GitHub (\`[!NOTE]\`, \`[!WARNING]\`, etc.)
- [x] Gerar sumário lateral (TOC) dinâmico
- [x] Drag & Drop de arquivos locais
- [ ] Exportação direta para PDF

> [!TIP]
> Use os atalhos de teclado **Ctrl+O** (Abrir), **Ctrl+S** (Salvar) e **Ctrl+N** (Novo) para navegar com máxima produtividade.
`;

function init() {
  const textarea = document.getElementById('editorTextarea');
  if (textarea) {
    textarea.value = SAMPLE_MARKDOWN;
    state.content = SAMPLE_MARKDOWN;
  }

  setupEventListeners();
  renderDocument();
  updateViewMode('split');
}

function setupEventListeners() {
  const textarea = document.getElementById('editorTextarea');
  if (textarea) {
    textarea.addEventListener('input', () => {
      state.content = textarea.value;
      state.isModified = true;
      renderDocument();
      updateStats();
      updateTitle();
    });

    // Sincronização de scroll simples
    textarea.addEventListener('scroll', syncScroll);
  }

  // Drag & Drop
  window.addEventListener('dragover', (e) => {
    e.preventDefault();
    document.body.classList.add('drag-over');
  });

  window.addEventListener('dragleave', (e) => {
    e.preventDefault();
    document.body.classList.remove('drag-over');
  });

  window.addEventListener('drop', async (e) => {
    e.preventDefault();
    document.body.classList.remove('drag-over');

    const files = e.dataTransfer.files;
    if (files && files.length > 0) {
      const file = files[0];
      const text = await file.text();
      loadFileContent(file.name, file.path || '', text);
    }
  });

  // Atalhos de teclado
  window.addEventListener('keydown', (e) => {
    if (e.ctrlKey || e.metaKey) {
      if (e.key.toLowerCase() === 'o') {
        e.preventDefault();
        handleOpenFile();
      } else if (e.key.toLowerCase() === 's') {
        e.preventDefault();
        handleSaveFile();
      } else if (e.key.toLowerCase() === 'n') {
        e.preventDefault();
        handleNewFile();
      }
    }
  });
}

function syncScroll() {
  if (state.viewMode !== 'split') return;
  const textarea = document.getElementById('editorTextarea');
  const preview = document.getElementById('previewPane');
  if (!textarea || !preview) return;

  const pct = textarea.scrollTop / (textarea.scrollHeight - textarea.clientHeight || 1);
  preview.scrollTop = pct * (preview.scrollHeight - preview.clientHeight);
}

function renderDocument() {
  const preview = document.getElementById('previewContent');
  if (!preview) return;

  const { html, toc } = window.parseMarkdown(state.content);
  preview.innerHTML = html;

  renderTOC(toc);
  updateStats();
  if (window.renderIcons) window.renderIcons();
}

function renderTOC(toc) {
  const tocList = document.getElementById('tocList');
  if (!tocList) return;

  if (!toc || toc.length === 0) {
    tocList.innerHTML = '<div class="toc-empty">Nenhum cabeçalho detectado.</div>';
    return;
  }

  tocList.innerHTML = toc.map(item => `
    <a href="#${item.id}" class="toc-item toc-level-${item.level}" onclick="scrollToHeading(event, '${item.id}')">
      ${item.text}
    </a>
  `).join('');
}

function scrollToHeading(e, id) {
  e.preventDefault();
  const el = document.getElementById(id);
  const pane = document.getElementById('previewPane');
  if (el && pane) {
    pane.scrollTo({
      top: el.offsetTop - 20,
      behavior: 'smooth'
    });
  }
}

function updateStats() {
  const text = state.content || '';
  const lines = text.split(/\r?\n/).length;
  const words = (text.match(/\b\w+\b/g) || []).length;
  const chars = text.length;

  document.getElementById('statLines').textContent = `${lines} linhas`;
  document.getElementById('statWords').textContent = `${words} palavras`;
  document.getElementById('statChars').textContent = `${chars} caracteres`;
}

function updateTitle() {
  const el = document.getElementById('docTitle');
  if (el) {
    const mod = state.isModified ? ' •' : '';
    el.textContent = `${state.filename}${mod}`;
  }
}

function updateViewMode(mode) {
  state.viewMode = mode;
  const main = document.getElementById('mainLayout');
  const btnReader = document.getElementById('btnModeReader');
  const btnSplit = document.getElementById('btnModeSplit');
  const btnEditor = document.getElementById('btnModeEditor');

  [btnReader, btnSplit, btnEditor].forEach(b => b && b.classList.remove('active'));

  if (mode === 'reader') {
    main.className = 'layout-reader';
    if (btnReader) btnReader.classList.add('active');
  } else if (mode === 'editor') {
    main.className = 'layout-editor';
    if (btnEditor) btnEditor.classList.add('active');
  } else {
    main.className = 'layout-split';
    if (btnSplit) btnSplit.classList.add('active');
  }
}

async function handleOpenFile() {
  try {
    if (!window.pywebview || !window.pywebview.api || !window.pywebview.api.open_file_dialog) {
      return;
    }
    const res = await window.pywebview.api.open_file_dialog();
    if (res.success) {
      loadFileContent(res.filename, res.path, res.content);
    }
  } catch (err) {
    console.error('Erro ao abrir arquivo:', err);
  }
}

function loadFileContent(filename, path, content) {
  state.filename = filename;
  state.currentPath = path;
  state.content = content;
  state.isModified = false;

  const textarea = document.getElementById('editorTextarea');
  if (textarea) textarea.value = content;

  renderDocument();
  updateTitle();
}

async function handleSaveFile() {
  try {
    if (!window.pywebview || !window.pywebview.api || !window.pywebview.api.save_file_dialog) {
      return;
    }
    const res = await window.pywebview.api.save_file_dialog(state.content, state.currentPath);
    if (res.success) {
      state.currentPath = res.path;
      state.filename = res.filename;
      state.isModified = false;
      updateTitle();
      showToast('Arquivo salvo com sucesso!');
    }
  } catch (err) {
    console.error('Erro ao salvar:', err);
  }
}

function handleNewFile() {
  if (state.isModified) {
    if (!confirm('Deseja criar um novo documento? Alterações não salvas serão perdidas.')) {
      return;
    }
  }
  loadFileContent('sem-titulo.md', '', '# Novo Documento\n\nComece a digitar seu markdown aqui...');
}

async function handleExportHtml() {
  try {
    if (!window.pywebview || !window.pywebview.api || !window.pywebview.api.export_html_dialog) {
      return;
    }
    const preview = document.getElementById('previewContent');
    const res = await window.pywebview.api.export_html_dialog(state.filename, preview.innerHTML);
    if (res.success) {
      showToast('HTML exportado com sucesso!');
    }
  } catch (err) {
    console.error('Erro ao exportar HTML:', err);
  }
}

async function copyRawMarkdown() {
  try {
    if (window.pywebview && window.pywebview.api && window.pywebview.api.copy_text) {
      await window.pywebview.api.copy_text(state.content);
    } else if (navigator.clipboard) {
      await navigator.clipboard.writeText(state.content);
    }
    showToast('Markdown bruto copiado!');
  } catch (e) {
    console.error(e);
  }
}

async function copyCode(btn) {
  const wrapper = btn.closest('.code-block-wrapper');
  if (!wrapper) return;
  const code = wrapper.querySelector('code');
  if (!code) return;

  const txt = code.innerText || code.textContent;
  try {
    if (window.pywebview && window.pywebview.api && window.pywebview.api.copy_text) {
      await window.pywebview.api.copy_text(txt);
    } else if (navigator.clipboard) {
      await navigator.clipboard.writeText(txt);
    }
    const orig = btn.innerHTML;
    btn.innerHTML = `<span data-icon="check" style="color:var(--success);"></span> Copiado!`;
    if (window.renderIcons) window.renderIcons();
    setTimeout(() => {
      btn.innerHTML = orig;
      if (window.renderIcons) window.renderIcons();
    }, 1200);
  } catch (e) {
    console.error(e);
  }
}

function showToast(msg) {
  let toast = document.getElementById('toast');
  if (!toast) {
    toast = document.createElement('div');
    toast.id = 'toast';
    toast.className = 'toast';
    document.body.appendChild(toast);
  }
  toast.textContent = msg;
  toast.classList.add('show');
  setTimeout(() => {
    toast.classList.remove('show');
  }, 2000);
}

document.addEventListener('DOMContentLoaded', init);
window.copyCode = copyCode;
