/**
 * Markdown Viewer Application Logic
 */

let state = {
  currentPath: '',
  filename: 'sem-titulo.md',
  content: '',
  lastMtime: 0,
  pendingExternalContent: null,
  pendingExternalMtime: 0,
  viewMode: 'split', // 'reader' | 'split' | 'editor'
  isModified: false,
  isTocCollapsed: false,
  theme: 'dark'
};

const SAMPLE_MARKDOWN = `# 🚀 Visualizador de Markdown — Toolbox

Bem-vindo ao **Visualizador & Editor de Markdown** no padrão oficial **Material Design 3 (M3)**.

> [!NOTE]
> Você pode abrir arquivos locais, arrastar e soltar arquivos \`.md\` nesta janela ou editar o conteúdo em tempo real!

---

## 📌 Principais Recursos

- **Visualização Rica:** Suporte a GitHub Flavored Markdown (GFM), tabelas, alertas e listas de tarefas.
- **Destaque de Sintaxe:** Blocos de código coloridos com botão de cópia rápida em 1 clique.
- **Table of Contents (TOC) Retrátil:** Sumário lateral navegável que pode ser recolhido para leitura em tela cheia.
- **Live Hot-Reload:** Qualquer alteração feita externamente no arquivo aberto reflete em tempo real nesta janela.
- **Temas Claro & Escuro:** Alterne entre os temas Claro e Escuro clicando no ícone do sol/lua na barra superior.
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
| **Theme System** | \`M3\` | 🎨 Dark & Light M3 | Full CSS Tokens |

---

### ✅ Lista de Tarefas (Task List)

- [x] Implementar parser standalone GFM
- [x] Suporte a alertas e notas GitHub (\`[!NOTE]\`, \`[!WARNING]\`, etc.)
- [x] Sumário lateral retrátil com 1 clique
- [x] Sincronização e Hot-reload de arquivos em tempo real
- [x] Alternador de tema Claro / Escuro com persistência
- [x] Scroll completo irrestrito para documentos longos

> [!TIP]
> Use os atalhos de teclado **Ctrl+O** (Abrir), **Ctrl+S** (Salvar) e **Ctrl+N** (Novo) para navegar com máxima produtividade.
`;

function init() {
  initTheme();
  loadPluginVersion();

  const textarea = document.getElementById('editorTextarea');
  if (textarea) {
    textarea.value = SAMPLE_MARKDOWN;
    state.content = SAMPLE_MARKDOWN;
  }

  setupEventListeners();
  renderDocument();
  updateViewMode('split');
  startFileWatcher();
}

function initTheme() {
  const savedTheme = localStorage.getItem('toolbox_theme') || 'dark';
  applyTheme(savedTheme);
}

function applyTheme(theme) {
  state.theme = theme;
  document.documentElement.setAttribute('data-theme', theme);
  localStorage.setItem('toolbox_theme', theme);

  const iconEl = document.getElementById('themeIcon');
  if (iconEl) {
    iconEl.setAttribute('data-icon', theme === 'dark' ? 'sun' : 'moon');
  }
  if (window.renderIcons) window.renderIcons();
}

function toggleTheme() {
  const newTheme = state.theme === 'dark' ? 'light' : 'dark';
  applyTheme(newTheme);
}

async function loadPluginVersion() {
  try {
    if (window.pywebview && window.pywebview.api && window.pywebview.api.get_plugin_version) {
      const res = await window.pywebview.api.get_plugin_version();
      if (res.success && res.version) {
        const badge = document.getElementById('pluginVersionBadge');
        if (badge) badge.textContent = `v${res.version}`;
      }
    }
  } catch (e) {
    console.error(e);
  }
}

function toggleTocCollapse() {
  state.isTocCollapsed = !state.isTocCollapsed;
  const layout = document.getElementById('mainLayout');
  const iconToggle = document.getElementById('tocIconToggle');

  if (state.isTocCollapsed) {
    layout.classList.add('toc-collapsed');
    if (iconToggle) iconToggle.setAttribute('data-icon', 'chevron-right');
  } else {
    layout.classList.remove('toc-collapsed');
    if (iconToggle) iconToggle.setAttribute('data-icon', 'chevron-left');
  }
  if (window.renderIcons) window.renderIcons();
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
      loadFileContent(file.name, file.path || '', text, Date.now());
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

  main.classList.remove('layout-reader', 'layout-split', 'layout-editor');

  if (mode === 'reader') {
    main.classList.add('layout-reader');
    if (btnReader) btnReader.classList.add('active');
  } else if (mode === 'editor') {
    main.classList.add('layout-editor');
    if (btnEditor) btnEditor.classList.add('active');
  } else {
    main.classList.add('layout-split');
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
      loadFileContent(res.filename, res.path, res.content, res.mtime || 0);
    }
  } catch (err) {
    console.error('Erro ao abrir arquivo:', err);
  }
}

function loadFileContent(filename, path, content, mtime = 0) {
  state.filename = filename;
  state.currentPath = path;
  state.content = content;
  state.lastMtime = mtime;
  state.isModified = false;
  state.pendingExternalContent = null;
  dismissExternalBanner();

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
      
      // Atualiza o timestamp após salvar para não disparar falso reload
      const info = await window.pywebview.api.get_file_info(res.path);
      if (info && info.mtime) state.lastMtime = info.mtime;

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
  loadFileContent('sem-titulo.md', '', '# Novo Documento\n\nComece a digitar seu markdown aqui...', 0);
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

// ─────────────────────── Live Watcher / Hot-Reload ───────────────────────

function startFileWatcher() {
  setInterval(async () => {
    if (!state.currentPath) return;
    try {
      if (!window.pywebview || !window.pywebview.api || !window.pywebview.api.get_file_info) return;

      const info = await window.pywebview.api.get_file_info(state.currentPath);
      if (info && info.success && info.exists && info.mtime) {
        if (state.lastMtime === 0) {
          state.lastMtime = info.mtime;
          return;
        }

        if (info.mtime > state.lastMtime) {
          const res = await window.pywebview.api.read_file(state.currentPath);
          if (res && res.success) {
            if (!state.isModified) {
              // Recarrega silenciosamente e atualiza a visualização
              state.content = res.content;
              state.lastMtime = info.mtime;
              const textarea = document.getElementById('editorTextarea');
              if (textarea) textarea.value = res.content;
              renderDocument();
              showToast('⚡ Documento atualizado em tempo real!');
            } else {
              // Há alterações locais não salvas, exibe o banner de aviso
              state.pendingExternalContent = res.content;
              state.pendingExternalMtime = info.mtime;
              showExternalModifiedBanner();
            }
          }
        }
      }
    } catch (e) {
      console.warn('Erro na verificação do arquivo:', e);
    }
  }, 1200);
}

function showExternalModifiedBanner() {
  const banner = document.getElementById('externalBanner');
  if (banner) banner.classList.add('show');
}

function dismissExternalBanner() {
  const banner = document.getElementById('externalBanner');
  if (banner) banner.classList.remove('show');
}

function applyExternalReload() {
  if (state.pendingExternalContent !== null) {
    loadFileContent(state.filename, state.currentPath, state.pendingExternalContent, state.pendingExternalMtime);
    showToast('Arquivo recarregado com o conteúdo do disco!');
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
  }, 2200);
}

document.addEventListener('DOMContentLoaded', init);
window.copyCode = copyCode;
window.toggleTheme = toggleTheme;
window.toggleTocCollapse = toggleTocCollapse;
window.applyExternalReload = applyExternalReload;
window.dismissExternalBanner = dismissExternalBanner;
