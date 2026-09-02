/**
 * Markdown Viewer Application Logic — Suporte a Múltiplas Abas (M3)
 */

let tabs = [];
let activeTabId = null;
let tabIdSeq = 1;
let contextMenuTabId = null;
let pendingCloseTabId = null;

let globalState = {
  viewMode: 'split', // 'reader' | 'split' | 'editor'
  isTocCollapsed: false,
  theme: 'dark',
};

const SAMPLE_MARKDOWN = `# 🚀 Visualizador de Markdown — Toolbox

Bem-vindo ao **Visualizador & Editor de Markdown** no padrão oficial **Material Design 3 (M3)**.

> [!NOTE]
> Você pode abrir múltiplos arquivos locais, arrastar e soltar arquivos \`.md\` nesta janela ou alternar entre abas simultaneamente!

---

## 📌 Principais Recursos

- **Múltiplas Abas (Tabs):** Trabalhe com vários documentos abertos em abas concorrentes.
- **Visualização Rica:** Suporte a GitHub Flavored Markdown (GFM), tabelas, alertas e listas.
  - Sub-níveis e recuo de listas aninhadas
  - Caixas de seleção e *task lists*
- **Destaque de Sintaxe:** Blocos de código coloridos com botão de cópia rápida em 1 clique.
- **Table of Contents (TOC) Retrátil:** Sumário lateral navegável nos modos Leitor, Dividido e Editor.
- **Live Hot-Reload:** Qualquer alteração feita externamente no arquivo aberto reflete em tempo real nesta janela.
- **Temas Claro & Escuro:** Alterne entre os temas Claro e Escuro clicando no ícone do sol/lua na barra superior.
- **Modos de Exibição:** Modo Leitor (*Zen View*), Modo Dividido (*Split-View*) e Modo Editor Puro.

---

### 💻 Exemplo de Código Python

\`\`\`python
def calcular_metricas(dados: list) -> dict:
    """Calcula média e total de dados analíticos."""
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

- [x] Suporte a Múltiplas Abas com isolamento de estado
- [x] Detecção inteligente de alterações não salvas (*dirty state*)
- [x] Menu de contexto completo e atalhos de teclado produtivos
- [x] Arrastar e soltar múltiplos arquivos \`.md\`
- [x] Sincronização e Hot-reload de arquivos em tempo real
- [x] Alternador de tema Claro / Escuro com persistência

> [!TIP]
> Use os atalhos de teclado **Ctrl+T** / **Ctrl+N** (Nova Aba), **Ctrl+W** (Fechar Aba), **Ctrl+Tab** (Alternar Aba) e **Ctrl+S** (Salvar).
`;

let isRestoringSession = false;

function waitForApi(timeoutMs = 4000) {
  return new Promise((resolve) => {
    if (window.pywebview && window.pywebview.api && window.pywebview.api.load_session) {
      return resolve(window.pywebview.api);
    }
    const start = Date.now();
    const interval = setInterval(() => {
      if (window.pywebview && window.pywebview.api && window.pywebview.api.load_session) {
        clearInterval(interval);
        resolve(window.pywebview.api);
      } else if (Date.now() - start > timeoutMs) {
        clearInterval(interval);
        resolve(null);
      }
    }, 50);
    window.addEventListener('pywebviewready', () => {
      if (window.pywebview && window.pywebview.api) {
        clearInterval(interval);
        resolve(window.pywebview.api);
      }
    }, { once: true });
  });
}

async function init() {
  initTheme();
  setupEventListeners();

  isRestoringSession = true;
  try {
    const api = await waitForApi();
    if (api) {
      await loadPluginVersion();
    }

    let hasInitialFile = false;
    if (api && api.get_initial_file) {
      try {
        const initFileRes = await api.get_initial_file();
        if (initFileRes && initFileRes.success && initFileRes.content !== undefined) {
          hasInitialFile = true;
          createTab(initFileRes.filename, initFileRes.path, initFileRes.content, initFileRes.content, false, initFileRes.mtime || 0, true);
        }
      } catch (e) {
        console.error('Erro ao ler arquivo inicial:', e);
      }
    }

    if (!hasInitialFile) {
      const restored = await restoreSession();
      if (!restored && tabs.length === 0) {
        createTab('sem-titulo-1.md', '', SAMPLE_MARKDOWN, SAMPLE_MARKDOWN, false, 0, true);
      }
    }
  } finally {
    isRestoringSession = false;
  }

  updateViewMode(globalState.viewMode || 'split');
  startFileWatcher();
}

function initTheme() {
  const savedTheme = localStorage.getItem('toolbox_theme') || 'dark';
  applyTheme(savedTheme);
}

function applyTheme(theme) {
  globalState.theme = theme;
  document.documentElement.setAttribute('data-theme', theme);
  localStorage.setItem('toolbox_theme', theme);

  const iconEl = document.getElementById('themeIcon');
  if (iconEl) {
    iconEl.setAttribute('data-icon', theme === 'dark' ? 'sun' : 'moon');
  }
  if (window.renderIcons) window.renderIcons();
}

function toggleTheme() {
  const newTheme = globalState.theme === 'dark' ? 'light' : 'dark';
  applyTheme(newTheme);
}

let appVersion = '';

async function loadPluginVersion() {
  try {
    if (window.pywebview && window.pywebview.api && window.pywebview.api.get_plugin_version) {
      const res = await window.pywebview.api.get_plugin_version();
      if (res.success && res.version) {
        appVersion = `v${res.version}`;
        const badge = document.getElementById('pluginVersionBadge');
        if (badge) badge.textContent = appVersion;
        updateTitle();
      }
    }
  } catch (e) {
    console.error(e);
  }
}

// ─────────────────────── Persistência de Sessão & Hot Exit ───────────────────────

let sessionSaveDebounceTimer = null;

function scheduleSessionSave(delay = 750) {
  if (isRestoringSession) {
    return;
  }
  if (sessionSaveDebounceTimer) {
    clearTimeout(sessionSaveDebounceTimer);
  }
  sessionSaveDebounceTimer = setTimeout(() => {
    persistCurrentSession();
  }, delay);
}

async function persistCurrentSession() {
  if (isRestoringSession) {
    return;
  }
  try {
    if (!window.pywebview || !window.pywebview.api || !window.pywebview.api.save_session) {
      return;
    }

    const currentTab = getActiveTab();
    const textarea = document.getElementById('editorTextarea');
    if (currentTab && textarea) {
      currentTab.content = textarea.value;
      currentTab.scrollTop = textarea.scrollTop;
      currentTab.cursorPos = { start: textarea.selectionStart, end: textarea.selectionEnd };
    }

    const sessionData = {
      activeTabId: activeTabId,
      viewMode: globalState.viewMode,
      theme: globalState.theme,
      isTocCollapsed: globalState.isTocCollapsed,
      tabs: tabs.map(t => ({
        id: t.id,
        title: t.title,
        filePath: t.filePath,
        savedContent: t.savedContent,
        isDirty: t.isDirty,
        lastMtime: t.lastMtime,
        scrollTop: t.scrollTop || 0,
        cursorPos: t.cursorPos || { start: 0, end: 0 }
      }))
    };

    const snapshots = {};
    tabs.forEach(t => {
      snapshots[t.id] = t.content || '';
    });

    await window.pywebview.api.save_session(sessionData, snapshots);
  } catch (err) {
    console.error('[MarkdownViewer] Falha ao persistir sessão:', err);
  }
}

async function restoreSession() {
  try {
    if (!window.pywebview || !window.pywebview.api || !window.pywebview.api.load_session) {
      return false;
    }

    const res = await window.pywebview.api.load_session();
    if (res && res.success && res.hasSession && res.data && Array.isArray(res.data.tabs) && res.data.tabs.length > 0) {
      const data = res.data;
      tabs = [];

      data.tabs.forEach(t => {
        const tab = {
          id: t.id || `tab-${tabIdSeq++}`,
          title: t.title || 'sem-titulo.md',
          filePath: t.filePath || '',
          content: t.content || '',
          savedContent: t.savedContent || '',
          isDirty: Boolean(t.isDirty),
          lastMtime: t.lastMtime || 0,
          pendingExternalContent: null,
          pendingExternalMtime: 0,
          scrollTop: t.scrollTop || 0,
          cursorPos: t.cursorPos || { start: 0, end: 0 },
          lastToc: []
        };
        const num = parseInt((tab.id || '').replace('tab-', ''), 10);
        if (!isNaN(num) && num >= tabIdSeq) {
          tabIdSeq = num + 1;
        }
        tabs.push(tab);
      });

      if (data.viewMode) {
        globalState.viewMode = data.viewMode;
      }
      if (data.isTocCollapsed) {
        globalState.isTocCollapsed = data.isTocCollapsed;
      }

      renderTabs();

      const targetActiveId = data.activeTabId && tabs.some(t => t.id === data.activeTabId)
        ? data.activeTabId
        : tabs[0].id;

      activateTab(targetActiveId);
      return true;
    }
  } catch (err) {
    console.error('[MarkdownViewer] Falha ao restaurar sessão:', err);
  }
  return false;
}

// ─────────────────────── Resolução Dinâmica de Títulos de Abas ───────────────────────

function extractFirstMarkdownTitle(content) {
  if (!content || !content.trim()) return null;

  // 1. Títulos ATX (# Título, ## Título, etc.)
  const atxMatch = content.match(/^(?:#{1,6})\s+(.+)$/m);
  if (atxMatch && atxMatch[1]) {
    const cleaned = sanitizeHeadingText(atxMatch[1]);
    if (cleaned) return cleaned;
  }

  // 2. Títulos Setext (Linha seguida por === ou ---)
  const setextMatch = content.match(/^([^\r\n]+)\r?\n(?:={2,}|-{2,})$/m);
  if (setextMatch && setextMatch[1]) {
    const cleaned = sanitizeHeadingText(setextMatch[1]);
    if (cleaned) return cleaned;
  }

  return null;
}

function sanitizeHeadingText(raw) {
  if (!raw) return '';
  return raw
    .replace(/[*_~`\[\]]/g, '')    // Remove marcadores de formatação inline (bold, italic, code, brackets)
    .replace(/<[^>]*>/g, '')        // Remove tags HTML
    .replace(/\s+/g, ' ')           // Normaliza múltiplos espaços
    .trim();
}

function getTabDisplayName(tab) {
  if (!tab) return 'Sem título';
  if (tab.filePath) {
    return tab.title;
  }
  const extracted = extractFirstMarkdownTitle(tab.content);
  if (extracted) {
    return extracted;
  }
  return tab.title || 'Sem título';
}

function getSuggestedFilename(tab) {
  const name = getTabDisplayName(tab);
  let sanitized = name.replace(/[<>:"/\\|?*]/g, '').trim();
  if (!sanitized) sanitized = 'documento';
  if (!sanitized.toLowerCase().endsWith('.md')) {
    sanitized += '.md';
  }
  return sanitized;
}

// ─────────────────────── Gerenciamento de Abas ───────────────────────

function getActiveTab() {
  return tabs.find(t => t.id === activeTabId) || null;
}

function createTab(title, filePath = '', content = '', savedContent = '', isDirty = false, lastMtime = 0, activate = true, forcedId = null) {
  const tabId = forcedId || `tab-${tabIdSeq++}`;
  if (forcedId) {
    const num = parseInt(forcedId.replace('tab-', ''), 10);
    if (!isNaN(num) && num >= tabIdSeq) {
      tabIdSeq = num + 1;
    }
  }

  const newTab = {
    id: tabId,
    title: title || `sem-titulo-${tabIdSeq - 1}.md`,
    filePath: filePath || '',
    content: content,
    savedContent: savedContent,
    isDirty: isDirty,
    lastMtime: lastMtime || 0,
    pendingExternalContent: null,
    pendingExternalMtime: 0,
    scrollTop: 0,
    cursorPos: { start: 0, end: 0 },
    lastToc: [],
  };

  tabs.push(newTab);
  renderTabs();

  if (activate) {
    activateTab(tabId);
  }

  scheduleSessionSave(300);
  return newTab;
}

function renderTabs() {
  const tabsList = document.getElementById('tabsList');
  if (!tabsList) return;

  tabsList.innerHTML = tabs.map(tab => {
    const isActive = tab.id === activeTabId;
    const isDirty = tab.isDirty;
    const displayName = getTabDisplayName(tab);
    const tooltip = tab.filePath ? tab.filePath : `${displayName} (Não salvo no disco)`;

    return `
      <div class="tab-item ${isActive ? 'active' : ''} ${isDirty ? 'dirty' : ''}"
           id="tabElement_${tab.id}"
           data-tab-id="${tab.id}"
           title="${escapeHtml(tooltip)}"
           onclick="handleTabClick('${tab.id}', event)"
           oncontextmenu="handleTabContextMenu('${tab.id}', event)">
        <span class="tab-icon" data-icon="file-text"></span>
        <span class="tab-title">${escapeHtml(displayName)}</span>
        <span class="tab-dirty-indicator" title="Alterações não salvas"></span>
        <button type="button" class="tab-close-btn"
                title="Fechar (Ctrl+W)"
                aria-label="Fechar aba ${escapeHtml(displayName)}"
                onclick="handleTabCloseClick('${tab.id}', event)">✕</button>
      </div>
    `;
  }).join('');

  if (window.renderIcons) window.renderIcons();
}


function activateTab(tabId) {
  const currentTab = getActiveTab();
  const textarea = document.getElementById('editorTextarea');

  // Salva o estado atual da aba ativa anterior
  if (currentTab && textarea) {
    currentTab.content = textarea.value;
    currentTab.scrollTop = textarea.scrollTop;
    currentTab.cursorPos = { start: textarea.selectionStart, end: textarea.selectionEnd };
  }

  const targetTab = tabs.find(t => t.id === tabId);
  if (!targetTab) return;

  activeTabId = tabId;

  // Carrega os dados da nova aba
  if (textarea) {
    textarea.value = targetTab.content;
    textarea.scrollTop = targetTab.scrollTop || 0;
    if (targetTab.cursorPos) {
      textarea.setSelectionRange(targetTab.cursorPos.start || 0, targetTab.cursorPos.end || 0);
    }
  }

  updateTitle();
  renderDocument();
  renderTabs();

  // Scroll suave da barra de abas até a aba ativada
  const tabEl = document.getElementById(`tabElement_${tabId}`);
  if (tabEl) {
    tabEl.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'nearest' });
  }

  // Verifica banner externo para a aba ativada
  if (targetTab.pendingExternalContent !== null) {
    showExternalModifiedBanner();
  } else {
    dismissExternalBanner();
  }

  scheduleSessionSave(200);
}

function handleTabClick(tabId, e) {
  if (e.target.closest('.tab-close-btn')) return;
  activateTab(tabId);
}

function handleTabCloseClick(tabId, e) {
  if (e) e.stopPropagation();
  handleCloseTab(tabId);
}

function handleCloseTab(tabId) {
  const tab = tabs.find(t => t.id === tabId);
  if (!tab) return;

  // Sincroniza o conteúdo antes de checar se está sujo
  if (tab.id === activeTabId) {
    const textarea = document.getElementById('editorTextarea');
    if (textarea) {
      tab.content = textarea.value;
      tab.isDirty = tab.content !== tab.savedContent;
    }
  }

  if (tab.isDirty) {
    openCloseConfirmModal(tabId);
  } else {
    closeTabImmediately(tabId);
  }
}

function closeTabImmediately(tabId) {
  const tabIndex = tabs.findIndex(t => t.id === tabId);
  if (tabIndex === -1) return;

  const wasActive = tabId === activeTabId;
  tabs.splice(tabIndex, 1);

  if (window.pywebview && window.pywebview.api && window.pywebview.api.delete_tab_snapshot) {
    window.pywebview.api.delete_tab_snapshot(tabId);
  }

  if (tabs.length === 0) {
    // Se fechou todas as abas, cria uma aba limpa imediatamente
    createTab('sem-titulo-1.md', '', '', '', false, 0, true);
    scheduleSessionSave(50);
    return;
  }

  if (wasActive) {
    // Ativa a aba anterior ou a próxima
    const nextIndex = Math.min(tabIndex, tabs.length - 1);
    activateTab(tabs[nextIndex].id);
  } else {
    renderTabs();
  }

  scheduleSessionSave(50);
}


function openCloseConfirmModal(tabId) {
  pendingCloseTabId = tabId;
  const tab = tabs.find(t => t.id === tabId);
  const msgEl = document.getElementById('closeConfirmMessage');
  if (msgEl && tab) {
    msgEl.textContent = `O arquivo '${tab.title}' possui alterações não salvas. Deseja salvar as alterações antes de fechar?`;
  }
  const modal = document.getElementById('modalCloseConfirm');
  if (modal) modal.style.display = 'flex';
}

function dismissCloseConfirmModal() {
  pendingCloseTabId = null;
  const modal = document.getElementById('modalCloseConfirm');
  if (modal) modal.style.display = 'none';
}

async function confirmCloseWithSave() {
  const tabId = pendingCloseTabId;
  dismissCloseConfirmModal();

  if (!tabId) return;
  const tab = tabs.find(t => t.id === tabId);
  if (!tab) return;

  activateTab(tabId);
  const saved = await handleSaveFile();
  if (saved) {
    closeTabImmediately(tabId);
  }
}

function confirmCloseWithoutSave() {
  const tabId = pendingCloseTabId;
  dismissCloseConfirmModal();

  if (tabId) {
    closeTabImmediately(tabId);
  }
}

function handleTabContextMenu(tabId, e) {
  if (e) {
    e.preventDefault();
    e.stopPropagation();
  }
  contextMenuTabId = tabId;
  openTabContextMenu(e.clientX, e.clientY);
}

function openTabContextMenu(x, y) {
  const menu = document.getElementById('tabContextMenu');
  if (!menu) return;

  menu.style.display = 'flex';

  // Garante posicionamento dentro dos limites da tela
  const maxX = window.innerWidth - 200;
  const maxY = window.innerHeight - 220;
  menu.style.left = `${Math.min(x, maxX)}px`;
  menu.style.top = `${Math.min(y, maxY)}px`;

  if (window.renderIcons) window.renderIcons();
}

function dismissTabContextMenu() {
  const menu = document.getElementById('tabContextMenu');
  if (menu) menu.style.display = 'none';
  contextMenuTabId = null;
}

function handleContextMenuAction(action) {
  const targetId = contextMenuTabId || activeTabId;
  dismissTabContextMenu();

  if (!targetId) return;

  switch (action) {
    case 'close':
      handleCloseTab(targetId);
      break;
    case 'close-others':
      closeOtherTabs(targetId);
      break;
    case 'close-right':
      closeTabsToRight(targetId);
      break;
    case 'close-all':
      closeAllTabs();
      break;
    case 'save':
      activateTab(targetId);
      handleSaveFile();
      break;
    case 'save-as':
      activateTab(targetId);
      handleSaveFileAs();
      break;
  }
}

function closeOtherTabs(targetTabId) {
  const dirtyOthers = tabs.filter(t => t.id !== targetTabId && t.isDirty);
  if (dirtyOthers.length > 0) {
    if (!confirm(`Existem ${dirtyOthers.length} aba(s) com alterações não salvas. Deseja fechar mesmo assim?`)) {
      return;
    }
  }
  tabs = tabs.filter(t => t.id === targetTabId);
  activateTab(targetTabId);
}

function closeTabsToRight(targetTabId) {
  const targetIdx = tabs.findIndex(t => t.id === targetTabId);
  if (targetIdx === -1) return;

  const rightTabs = tabs.slice(targetIdx + 1);
  const dirtyRight = rightTabs.filter(t => t.isDirty);
  if (dirtyRight.length > 0) {
    if (!confirm(`Existem ${dirtyRight.length} aba(s) à direita com alterações não salvas. Deseja fechar mesmo assim?`)) {
      return;
    }
  }

  tabs = tabs.slice(0, targetIdx + 1);
  const activeStillExists = tabs.some(t => t.id === activeTabId);
  if (!activeStillExists) {
    activateTab(targetTabId);
  } else {
    renderTabs();
  }
}

function closeAllTabs() {
  const dirtyTabs = tabs.filter(t => t.isDirty);
  if (dirtyTabs.length > 0) {
    if (!confirm(`Existem ${dirtyTabs.length} aba(s) com alterações não salvas. Deseja fechar todas?`)) {
      return;
    }
  }
  tabs = [];
  createTab('sem-titulo-1.md', '', '', '', false, 0, true);
}

function handleCycleTab(direction) {
  if (tabs.length <= 1) return;
  const currentIdx = tabs.findIndex(t => t.id === activeTabId);
  let nextIdx = (currentIdx + direction) % tabs.length;
  if (nextIdx < 0) nextIdx = tabs.length - 1;
  activateTab(tabs[nextIdx].id);
}

function handleSelectTabByIndex(idx) {
  if (idx >= 0 && idx < tabs.length) {
    activateTab(tabs[idx].id);
  }
}

// ─────────────────────── Event Listeners & Editor ───────────────────────

function setupEventListeners() {
  const textarea = document.getElementById('editorTextarea');
  if (textarea) {
    textarea.addEventListener('input', () => {
      const activeTab = getActiveTab();
      if (!activeTab) return;

      activeTab.content = textarea.value;
      activeTab.isDirty = activeTab.content !== activeTab.savedContent;

      renderDocument();
      updateStats();
      updateTitle();

      const tabEl = document.getElementById(`tabElement_${activeTab.id}`);
      if (tabEl) {
        if (activeTab.isDirty) tabEl.classList.add('dirty');
        else tabEl.classList.remove('dirty');
        const tabTitleEl = tabEl.querySelector('.tab-title');
        if (tabTitleEl) {
          tabTitleEl.textContent = getTabDisplayName(activeTab);
        }
      }

      scheduleSessionSave();
    });

    textarea.addEventListener('scroll', syncScroll);

    // Suporte a indentação com Tab e Shift+Tab
    textarea.addEventListener('keydown', (e) => {
      if (e.key === 'Tab') {
        e.preventDefault();
        const start = textarea.selectionStart;
        const end = textarea.selectionEnd;
        const val = textarea.value;

        if (e.shiftKey) {
          // Shift + Tab (recuar 2 espaços)
          const lineStart = val.lastIndexOf('\n', start - 1) + 1;
          if (val.substring(lineStart, lineStart + 2) === '  ') {
            textarea.value = val.substring(0, lineStart) + val.substring(lineStart + 2);
            textarea.selectionStart = Math.max(lineStart, start - 2);
            textarea.selectionEnd = Math.max(lineStart, end - 2);
          } else if (val.charAt(lineStart) === ' ' || val.charAt(lineStart) === '\t') {
            textarea.value = val.substring(0, lineStart) + val.substring(lineStart + 1);
            textarea.selectionStart = Math.max(lineStart, start - 1);
            textarea.selectionEnd = Math.max(lineStart, end - 1);
          }
        } else {
          // Tab (inserir 2 espaços)
          textarea.value = val.substring(0, start) + '  ' + val.substring(end);
          textarea.selectionStart = textarea.selectionEnd = start + 2;
        }

        const activeTab = getActiveTab();
        if (activeTab) {
          activeTab.content = textarea.value;
          activeTab.isDirty = activeTab.content !== activeTab.savedContent;
          renderDocument();
          updateStats();
          updateTitle();
          const tabEl = document.getElementById(`tabElement_${activeTab.id}`);
          if (tabEl) {
            if (activeTab.isDirty) tabEl.classList.add('dirty');
            else tabEl.classList.remove('dirty');
            const tabTitleEl = tabEl.querySelector('.tab-title');
            if (tabTitleEl) {
              tabTitleEl.textContent = getTabDisplayName(activeTab);
            }
          }
          scheduleSessionSave();
        }
      }
    });
  }

  // Duplo clique na barra de abas cria uma nova aba (estilo VS Code / navegadores)
  const tabBarContainer = document.getElementById('tabBarContainer');
  if (tabBarContainer) {
    tabBarContainer.addEventListener('dblclick', (e) => {
      // Não cria aba se clicou sobre uma aba existente ou sobre um botão de controle
      if (!e.target.closest('.tab-item') && !e.target.closest('button')) {
        handleNewTab();
      }
    });
  }

  // Persistir sessão ao fechar a janela (Hot Exit)
  window.addEventListener('beforeunload', () => {
    persistCurrentSession();
  });

  // Fechar menu de contexto ao clicar fora
  window.addEventListener('click', (e) => {
    if (!e.target.closest('#tabContextMenu')) {
      dismissTabContextMenu();
    }
  });

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
      for (let i = 0; i < files.length; i++) {
        const file = files[i];
        const text = await file.text();
        openOrFocusFile(file.name, file.path || '', text, Date.now());
      }
    }
  });

  // Atalhos de teclado
  window.addEventListener('keydown', (e) => {
    if (e.ctrlKey || e.metaKey) {
      const key = e.key.toLowerCase();

      if (key === 't' || key === 'n') {
        e.preventDefault();
        handleNewTab();
      } else if (key === 'w') {
        e.preventDefault();
        if (activeTabId) handleCloseTab(activeTabId);
      } else if (e.key === 'Tab') {
        e.preventDefault();
        handleCycleTab(e.shiftKey ? -1 : 1);
      } else if (key === 'o') {
        e.preventDefault();
        handleOpenFile();
      } else if (key === 's') {
        e.preventDefault();
        if (e.shiftKey) {
          handleSaveAllFiles();
        } else {
          handleSaveFile();
        }
      } else if (/^[1-9]$/.test(e.key)) {
        e.preventDefault();
        const tabIdx = parseInt(e.key, 10) - 1;
        handleSelectTabByIndex(tabIdx);
      }
    }
  });
}

function syncScroll() {
  if (globalState.viewMode !== 'split') return;
  const textarea = document.getElementById('editorTextarea');
  const preview = document.getElementById('previewPane');
  if (!textarea || !preview) return;

  const pct = textarea.scrollTop / (textarea.scrollHeight - textarea.clientHeight || 1);
  preview.scrollTop = pct * (preview.scrollHeight - preview.clientHeight);
}

function renderDocument() {
  const preview = document.getElementById('previewContent');
  if (!preview) return;

  const activeTab = getActiveTab();
  const content = activeTab ? activeTab.content : '';

  const { html, toc } = window.parseMarkdown(content);
  if (activeTab) activeTab.lastToc = toc || [];
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
      ${escapeHtml(item.text)}
    </a>
  `).join('');
}

function scrollToHeading(e, id) {
  if (e) e.preventDefault();

  const activeTab = getActiveTab();

  if (globalState.viewMode === 'reader' || globalState.viewMode === 'split') {
    const el = document.getElementById(id);
    const pane = document.getElementById('previewPane');
    if (el && pane) {
      pane.scrollTo({
        top: el.offsetTop - 20,
        behavior: 'smooth'
      });
    }
  }

  if (globalState.viewMode === 'editor' || globalState.viewMode === 'split') {
    const textarea = document.getElementById('editorTextarea');
    if (textarea && activeTab) {
      const headingItem = (activeTab.lastToc || []).find(h => h.id === id);
      const targetText = headingItem ? headingItem.text.trim().toLowerCase() : '';

      const content = textarea.value;
      const lines = content.split(/\r?\n/);
      let targetLineIndex = -1;
      let charPos = 0;

      for (let i = 0; i < lines.length; i++) {
        const line = lines[i];
        const headingMatch = line.match(/^(#{1,6})\s+(.+)$/);
        if (headingMatch) {
          const matchText = headingMatch[2].trim();
          if (headingItem && matchText === headingItem.text) {
            targetLineIndex = i;
            break;
          }
          if (targetText && matchText.toLowerCase() === targetText) {
            targetLineIndex = i;
            break;
          }
        }
        charPos += line.length + 1;
      }

      if (targetLineIndex !== -1) {
        textarea.focus();
        const lineLen = lines[targetLineIndex] ? lines[targetLineIndex].length : 0;
        textarea.setSelectionRange(charPos, charPos + lineLen);

        const totalLines = lines.length || 1;
        const lineRatio = targetLineIndex / totalLines;
        const targetScrollTop = lineRatio * (textarea.scrollHeight - textarea.clientHeight);
        textarea.scrollTo({
          top: targetScrollTop,
          behavior: 'smooth'
        });
      }
    }
  }
}

function updateStats() {
  const activeTab = getActiveTab();
  const text = activeTab ? activeTab.content : '';
  const lines = text.split(/\r?\n/).length;
  const words = (text.match(/\b\w+\b/g) || []).length;
  const chars = text.length;

  document.getElementById('statLines').textContent = `${lines} linhas`;
  document.getElementById('statWords').textContent = `${words} palavras`;
  document.getElementById('statChars').textContent = `${chars} caracteres`;
}

function updateTitle() {
  const el = document.getElementById('docTitle');
  const activeTab = getActiveTab();
  const displayName = activeTab ? getTabDisplayName(activeTab) : 'sem-titulo.md';
  const mod = (activeTab && activeTab.isDirty) ? ' •' : '';
  
  if (el) {
    el.textContent = `${displayName}${mod}`;
    el.title = (activeTab && activeTab.filePath) ? activeTab.filePath : displayName;
  }

  const versionSuffix = appVersion ? ` ${appVersion}` : '';
  const fullTitle = `${displayName}${mod} — Visualizador de Markdown${versionSuffix}`;
  document.title = fullTitle;

  if (window.pywebview && window.pywebview.api && window.pywebview.api.set_window_title) {
    try {
      window.pywebview.api.set_window_title(fullTitle);
    } catch (e) {
      // Ignora falhas se a janela já estiver fechando
    }
  }
}

function updateViewMode(mode) {
  globalState.viewMode = mode;
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

function toggleTocCollapse() {
  globalState.isTocCollapsed = !globalState.isTocCollapsed;
  const layout = document.getElementById('mainLayout');
  const iconToggle = document.getElementById('tocIconToggle');

  if (globalState.isTocCollapsed) {
    layout.classList.add('toc-collapsed');
    if (iconToggle) iconToggle.setAttribute('data-icon', 'chevron-right');
  } else {
    layout.classList.remove('toc-collapsed');
    if (iconToggle) iconToggle.setAttribute('data-icon', 'chevron-left');
  }
  if (window.renderIcons) window.renderIcons();
}

// ─────────────────────── Operações de Arquivo ───────────────────────

function handleNewTab() {
  createTab(`sem-titulo-${tabIdSeq}.md`, '', '# Novo Documento\n\nComece a digitar seu markdown aqui...', '', false, 0, true);
}

function handleNewFile() {
  handleNewTab();
}

async function handleOpenFile() {
  try {
    if (!window.pywebview || !window.pywebview.api || !window.pywebview.api.open_file_dialog) {
      return;
    }
    const res = await window.pywebview.api.open_file_dialog();
    if (res.success) {
      if (res.files && Array.isArray(res.files)) {
        for (const file of res.files) {
          openOrFocusFile(file.filename, file.path, file.content, file.mtime || 0);
        }
      } else if (res.path) {
        openOrFocusFile(res.filename, res.path, res.content, res.mtime || 0);
      }
    }
  } catch (err) {
    console.error('Erro ao abrir arquivo:', err);
  }
}

function openOrFocusFile(filename, filePath, content, mtime = 0) {
  // Se o arquivo com este caminho já estiver aberto, foca na aba existente
  if (filePath) {
    const existingTab = tabs.find(t => t.filePath && t.filePath.toLowerCase() === filePath.toLowerCase());
    if (existingTab) {
      activateTab(existingTab.id);
      showToast(`Aba focada: ${filename}`);
      return existingTab;
    }
  }

  // Se a aba ativa for virgem (sem caminho, não modificada e vazia ou sample), reaproveita-a
  const activeTab = getActiveTab();
  if (activeTab && !activeTab.filePath && !activeTab.isDirty && (activeTab.content === SAMPLE_MARKDOWN || activeTab.content === '')) {
    activeTab.title = filename;
    activeTab.filePath = filePath;
    activeTab.content = content;
    activeTab.savedContent = content;
    activeTab.isDirty = false;
    activeTab.lastMtime = mtime;
    activeTab.pendingExternalContent = null;

    const textarea = document.getElementById('editorTextarea');
    if (textarea) textarea.value = content;

    renderTabs();
    activateTab(activeTab.id);
    return activeTab;
  }

  // Caso contrário, cria uma nova aba
  return createTab(filename, filePath, content, content, false, mtime, true);
}

async function handleSaveFile() {
  const activeTab = getActiveTab();
  if (!activeTab) return false;

  const textarea = document.getElementById('editorTextarea');
  if (textarea) activeTab.content = textarea.value;

  try {
    if (!window.pywebview || !window.pywebview.api || !window.pywebview.api.save_file_dialog) {
      return false;
    }

    if (activeTab.filePath) {
      const res = await window.pywebview.api.save_file(activeTab.filePath, activeTab.content);
      if (res && res.success) {
        activeTab.savedContent = activeTab.content;
        activeTab.isDirty = false;
        const info = await window.pywebview.api.get_file_info(activeTab.filePath);
        if (info && info.mtime) activeTab.lastMtime = info.mtime;

        renderTabs();
        updateTitle();
        showToast('Arquivo salvo com sucesso!');
        scheduleSessionSave(50);
        return true;
      }
    } else {
      const suggestedName = getSuggestedFilename(activeTab);
      const res = await window.pywebview.api.save_file_dialog(activeTab.content, activeTab.filePath, suggestedName);
      if (res && res.success) {
        activeTab.filePath = res.path;
        activeTab.title = res.filename;
        activeTab.savedContent = activeTab.content;
        activeTab.isDirty = false;

        const info = await window.pywebview.api.get_file_info(res.path);
        if (info && info.mtime) activeTab.lastMtime = info.mtime;

        renderTabs();
        updateTitle();
        showToast('Arquivo salvo com sucesso!');
        scheduleSessionSave(50);
        return true;
      }
    }
  } catch (err) {
    console.error('Erro ao salvar:', err);
  }
  return false;
}

async function handleSaveFileAs() {
  const activeTab = getActiveTab();
  if (!activeTab) return;

  const textarea = document.getElementById('editorTextarea');
  if (textarea) activeTab.content = textarea.value;

  try {
    if (!window.pywebview || !window.pywebview.api || !window.pywebview.api.save_file_dialog) return;

    const suggestedName = getSuggestedFilename(activeTab);
    const res = await window.pywebview.api.save_file_dialog(activeTab.content, '', suggestedName);
    if (res && res.success) {
      activeTab.filePath = res.path;
      activeTab.title = res.filename;
      activeTab.savedContent = activeTab.content;
      activeTab.isDirty = false;

      const info = await window.pywebview.api.get_file_info(res.path);
      if (info && info.mtime) activeTab.lastMtime = info.mtime;

      renderTabs();
      updateTitle();
      showToast(`Salvo como: ${res.filename}`);
      scheduleSessionSave(50);
    }
  } catch (err) {
    console.error('Erro ao salvar como:', err);
  }
}

async function handleSaveAllFiles() {
  const dirtyTabs = tabs.filter(t => t.isDirty);
  if (dirtyTabs.length === 0) {
    showToast('Nenhum documento com alterações pendentes.');
    return;
  }

  let savedCount = 0;
  for (const tab of dirtyTabs) {
    if (tab.filePath) {
      const res = await window.pywebview.api.save_file(tab.filePath, tab.content);
      if (res && res.success) {
        tab.savedContent = tab.content;
        tab.isDirty = false;
        savedCount++;
      }
    }
  }

  renderTabs();
  updateTitle();
  showToast(`${savedCount} arquivo(s) salvo(s) com sucesso!`);
  scheduleSessionSave(50);
}

async function handleExportHtml() {
  const activeTab = getActiveTab();
  if (!activeTab) return;

  try {
    if (!window.pywebview || !window.pywebview.api || !window.pywebview.api.export_html_dialog) return;
    const preview = document.getElementById('previewContent');
    const res = await window.pywebview.api.export_html_dialog(activeTab.title, preview.innerHTML);
    if (res.success) {
      showToast('HTML exportado com sucesso!');
    }
  } catch (err) {
    console.error('Erro ao exportar HTML:', err);
  }
}

async function copyTextToClipboard(text) {
  if (text === undefined || text === null) return false;

  try {
    if (window.pywebview && window.pywebview.api && window.pywebview.api.copy_text) {
      const res = await window.pywebview.api.copy_text(text);
      if (res && res.success) return true;
    }
  } catch (e) {
    console.warn('Falha em copy_text:', e);
  }

  try {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch (e) {
    console.warn('Falha em navigator.clipboard:', e);
  }

  try {
    const tempTextArea = document.createElement('textarea');
    tempTextArea.value = text;
    tempTextArea.style.position = 'fixed';
    tempTextArea.style.left = '-9999px';
    tempTextArea.style.top = '0';
    tempTextArea.style.opacity = '0';
    tempTextArea.setAttribute('readonly', '');
    document.body.appendChild(tempTextArea);
    tempTextArea.focus();
    tempTextArea.select();
    const successful = document.execCommand('copy');
    document.body.removeChild(tempTextArea);
    if (successful) return true;
  } catch (e) {
    console.error('Falha no fallback:', e);
  }

  return false;
}

async function copyRawMarkdown() {
  const activeTab = getActiveTab();
  const text = activeTab ? activeTab.content : '';
  const success = await copyTextToClipboard(text);
  if (success) {
    showToast('Markdown bruto copiado!');
  } else {
    showToast('Não foi possível copiar o Markdown.');
  }
}

async function copyCode(btn) {
  const wrapper = btn.closest('.code-block-wrapper');
  if (!wrapper) return;
  const code = wrapper.querySelector('code');
  if (!code) return;

  const txt = code.innerText || code.textContent;
  const success = await copyTextToClipboard(txt);

  if (success) {
    const orig = btn.innerHTML;
    btn.innerHTML = `<span data-icon="check" style="color:var(--success);"></span> Copiado!`;
    btn.classList.add('copied');
    if (window.renderIcons) window.renderIcons();
    setTimeout(() => {
      btn.innerHTML = orig;
      btn.classList.remove('copied');
      if (window.renderIcons) window.renderIcons();
    }, 1500);
  } else {
    showToast('Não foi possível copiar o código.');
  }
}

// ─────────────────────── Live Watcher / Hot-Reload ───────────────────────

function startFileWatcher() {
  setInterval(async () => {
    const activeTab = getActiveTab();
    if (!activeTab || !activeTab.filePath) return;

    try {
      if (!window.pywebview || !window.pywebview.api || !window.pywebview.api.get_file_info) return;

      const info = await window.pywebview.api.get_file_info(activeTab.filePath);
      if (info && info.success && info.exists && info.mtime) {
        if (activeTab.lastMtime === 0) {
          activeTab.lastMtime = info.mtime;
          return;
        }

        if (info.mtime > activeTab.lastMtime) {
          const res = await window.pywebview.api.read_file(activeTab.filePath);
          if (res && res.success) {
            if (!activeTab.isDirty) {
              activeTab.content = res.content;
              activeTab.savedContent = res.content;
              activeTab.lastMtime = info.mtime;
              const textarea = document.getElementById('editorTextarea');
              if (textarea) textarea.value = res.content;
              renderDocument();
              showToast('⚡ Documento atualizado em tempo real!');
            } else {
              activeTab.pendingExternalContent = res.content;
              activeTab.pendingExternalMtime = info.mtime;
              showExternalModifiedBanner();
            }
          }
        }
      }
    } catch (e) {
      console.warn('Erro no file watcher:', e);
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
  const activeTab = getActiveTab();
  if (activeTab) activeTab.pendingExternalContent = null;
}

function applyExternalReload() {
  const activeTab = getActiveTab();
  if (activeTab && activeTab.pendingExternalContent !== null) {
    activeTab.content = activeTab.pendingExternalContent;
    activeTab.savedContent = activeTab.pendingExternalContent;
    activeTab.lastMtime = activeTab.pendingExternalMtime;
    activeTab.isDirty = false;
    activeTab.pendingExternalContent = null;

    const textarea = document.getElementById('editorTextarea');
    if (textarea) textarea.value = activeTab.content;

    dismissExternalBanner();
    renderDocument();
    renderTabs();
    updateTitle();
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

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

document.addEventListener('DOMContentLoaded', init);

// Exports globais para chamadas inline no HTML
window.copyCode = copyCode;
window.toggleTheme = toggleTheme;
window.toggleTocCollapse = toggleTocCollapse;
window.applyExternalReload = applyExternalReload;
window.dismissExternalBanner = dismissExternalBanner;
window.handleNewTab = handleNewTab;
window.handleNewFile = handleNewFile;
window.handleOpenFile = handleOpenFile;
window.handleSaveFile = handleSaveFile;
window.handleExportHtml = handleExportHtml;
window.copyRawMarkdown = copyRawMarkdown;
window.updateViewMode = updateViewMode;
window.handleTabClick = handleTabClick;
window.handleTabCloseClick = handleTabCloseClick;
window.handleTabContextMenu = handleTabContextMenu;
window.handleContextMenuAction = handleContextMenuAction;
window.confirmCloseWithSave = confirmCloseWithSave;
window.confirmCloseWithoutSave = confirmCloseWithoutSave;
window.dismissCloseConfirmModal = dismissCloseConfirmModal;
