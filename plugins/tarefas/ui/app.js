/**
 * Tarefas Plugin - Frontend Application Logic
 * Gerenciamento de tarefas, chat inline rápido, abas dinâmicas e anexos.
 */

// Estado Global
let state = {
  tasks: [],
  activeFilter: 'all', // 'all' | 'pending' | 'completed'
  editingTaskId: null,
  openTabs: [], // Lista de IDs de tarefas com abas abertas
  activeTabId: 'main', // 'main' ou ID da tarefa
  markdownFields: {}, // Instâncias ativas de MarkdownField por taskId
};

// Fallback Mock para desenvolvimento web fora do pywebview
const mockApi = {
  get_tasks: async () => ({
    success: true,
    tasks: [
      {
        id: 'task_demo1',
        title: 'Criar documentação de arquitetura do sistema',
        description: '# Arquitetura do Sistema\n\n- [x] Levantamento de requisitos\n- [ ] Diagrama C4\n- [ ] Validação com a equipe\n\n```python\nprint("Planejamento concluído")\n```',
        completed: false,
        created_at: '2026-09-15 10:00:00',
        updated_at: '2026-09-15 10:00:00',
        attachments: [
          {
            id: 'att_demo1',
            name: 'diagrama_c4.png',
            size_formatted: '245 KB',
            added_at: '2026-09-15 10:05:00'
          }
        ]
      },
      {
        id: 'task_demo2',
        title: 'Revisar PR de autenticação biométrica',
        description: 'Verificar testes unitários e cobertura do Windows Hello.',
        completed: true,
        created_at: '2026-09-15 11:30:00',
        updated_at: '2026-09-15 12:00:00',
        attachments: []
      }
    ]
  }),
  create_task: async (title, desc = '') => {
    const newTask = {
      id: 'task_' + Math.random().toString(36).substr(2, 6),
      title,
      description: desc || `# ${title}\n\nDetalhes da tarefa aqui.`,
      completed: false,
      created_at: new Date().toISOString().replace('T', ' ').substr(0, 19),
      updated_at: new Date().toISOString().replace('T', ' ').substr(0, 19),
      attachments: []
    };
    state.tasks.unshift(newTask);
    return { success: true, task: newTask, tasks: state.tasks };
  },
  update_task: async (id, updates) => {
    const t = state.tasks.find(item => item.id === id);
    if (t) {
      Object.assign(t, updates);
      t.updated_at = new Date().toISOString().replace('T', ' ').substr(0, 19);
    }
    return { success: true, task: t, tasks: state.tasks };
  },
  toggle_task: async (id) => {
    const t = state.tasks.find(item => item.id === id);
    if (t) {
      t.completed = !t.completed;
      t.updated_at = new Date().toISOString().replace('T', ' ').substr(0, 19);
    }
    return { success: true, task: t, tasks: state.tasks };
  },
  delete_task: async (id) => {
    state.tasks = state.tasks.filter(t => t.id !== id);
    return { success: true, tasks: state.tasks };
  },
  add_attachment_dialog: async (taskId) => {
    const t = state.tasks.find(item => item.id === taskId);
    if (!t) return { success: false, error: 'Tarefa não encontrada' };
    const att = {
      id: 'att_' + Math.random().toString(36).substr(2, 6),
      name: 'novo_anexo_exemplo.pdf',
      size_formatted: '1.2 MB',
      added_at: new Date().toISOString().replace('T', ' ').substr(0, 19)
    };
    t.attachments.push(att);
    return { success: true, added: [att], task: t, tasks: state.tasks };
  },
  remove_attachment: async (taskId, attId) => {
    const t = state.tasks.find(item => item.id === taskId);
    if (t) {
      t.attachments = t.attachments.filter(a => a.id !== attId);
    }
    return { success: true, task: t, tasks: state.tasks };
  },
  open_attachment: async () => ({ success: true }),
  open_attachment_folder: async () => ({ success: true }),
  get_plugin_version: async () => ({ success: true, version: '1.0.0' }),
};

function getApi() {
  if (window.pywebview && window.pywebview.api) {
    return window.pywebview.api;
  }
  return mockApi;
}

// Inicialização
document.addEventListener('DOMContentLoaded', async () => {
  initTheme();
  setupChatListeners();

  // Se pywebview estiver rodando, aguarda evento pywebviewready
  if (window.pywebview) {
    window.addEventListener('pywebviewready', async () => {
      await loadInitialData();
    });
  } else {
    // Timeout para esperar injeção pywebview ou cair no mock
    setTimeout(async () => {
      await loadInitialData();
    }, 150);
  }
});

async function loadInitialData() {
  const api = getApi();
  try {
    const verRes = await api.get_plugin_version();
    if (verRes && verRes.version) {
      const badge = document.getElementById('versionBadge');
      if (badge) badge.textContent = `v${verRes.version}`;
    }

    const res = await api.get_tasks();
    if (res && res.success) {
      state.tasks = res.tasks || [];
    }
  } catch (err) {
    console.error('Erro ao carregar dados iniciais:', err);
  }
  renderTasksList();
  if (window.renderIcons) window.renderIcons();
}

// --- Tema Escuro / Claro ---
function initTheme() {
  const saved = localStorage.getItem('toolbox-theme') || 'dark';
  document.documentElement.setAttribute('data-theme', saved);
  updateThemeIcon(saved);
}

function toggleTheme() {
  const current = document.documentElement.getAttribute('data-theme') || 'dark';
  const next = current === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', next);
  localStorage.setItem('toolbox-theme', next);
  updateThemeIcon(next);
}

function updateThemeIcon(theme) {
  const icon = document.getElementById('themeIcon');
  if (!icon) return;
  icon.setAttribute('data-icon', theme === 'dark' ? 'sun' : 'moon');
  if (window.renderIcons) window.renderIcons();
}

// --- Filtros ---
function setFilter(filter) {
  state.activeFilter = filter;
  document.querySelectorAll('.filter-btn').forEach(btn => btn.classList.remove('active'));
  const activeBtn = document.getElementById(`filter${filter.charAt(0).toUpperCase() + filter.slice(1)}Btn`);
  if (activeBtn) activeBtn.classList.add('active');
  renderTasksList();
}

// --- Renderização da Lista de Tarefas ---
function renderTasksList() {
  const container = document.getElementById('tasksListContainer');
  const statsText = document.getElementById('tasksStatsText');
  if (!container) return;

  const total = state.tasks.length;
  const completedCount = state.tasks.filter(t => t.completed).length;
  const pendingCount = total - completedCount;

  if (statsText) {
    statsText.textContent = `${completedCount} de ${total} concluída${total === 1 ? '' : 's'}`;
  }

  let filtered = state.tasks;
  if (state.activeFilter === 'pending') {
    filtered = state.tasks.filter(t => !t.completed);
  } else if (state.activeFilter === 'completed') {
    filtered = state.tasks.filter(t => t.completed);
  }

  if (filtered.length === 0) {
    container.innerHTML = `
      <div class="empty-state">
        <div data-icon="check-square" class="empty-icon"></div>
        <div style="font-size: 14px; font-weight: 600; color: var(--fg);">Nenhuma tarefa encontrada</div>
        <div style="font-size: 12px;">Use o campo abaixo para adicionar tarefas com rapidez.</div>
      </div>
    `;
    if (window.renderIcons) window.renderIcons();
    return;
  }

  container.innerHTML = filtered.map(task => {
    const isCompleted = Boolean(task.completed);
    const attCount = (task.attachments || []).length;
    const attBadge = attCount > 0
      ? `<span class="task-meta-badge" title="${attCount} anexo(s)"><span data-icon="paperclip"></span> ${attCount}</span>`
      : '';

    return `
      <div class="task-card ${isCompleted ? 'completed' : ''}" id="card_${task.id}">
        <div class="task-left">
          <input
            type="checkbox"
            class="task-checkbox-custom"
            ${isCompleted ? 'checked' : ''}
            onchange="handleToggleTask('${task.id}')"
            title="${isCompleted ? 'Marcar como pendente' : 'Marcar como concluída'}"
          />
          <span class="task-title" title="${escapeHtml(task.title)}">${escapeHtml(task.title)}</span>
          ${attBadge}
        </div>
        <div class="task-actions">
          <button
            type="button"
            class="action-btn action-btn-edit"
            onclick="startQuickEdit('${task.id}')"
            title="Editar rapidamente no chat"
          >
            <span data-icon="edit-3"></span>
          </button>
          <button
            type="button"
            class="action-btn action-btn-view"
            onclick="openTaskTab('${task.id}')"
            title="Visualizar detalhes em aba dedicada"
          >
            <span data-icon="eye"></span>
          </button>
          <button
            type="button"
            class="action-btn action-btn-delete"
            onclick="handleDeleteTask('${task.id}')"
            title="Excluir tarefa"
          >
            <span data-icon="trash-2"></span>
          </button>
        </div>
      </div>
    `;
  }).join('');

  if (window.renderIcons) window.renderIcons();
}

// --- Toggle de Conclusão de Tarefa ---
async function handleToggleTask(taskId) {
  const api = getApi();
  try {
    const res = await api.toggle_task(taskId);
    if (res && res.success) {
      state.tasks = res.tasks;
      renderTasksList();
      updateDetailPaneIfOpen(taskId);
    }
  } catch (err) {
    console.error('Erro ao alternar status da tarefa:', err);
  }
}

// --- Exclusão de Tarefa ---
async function handleDeleteTask(taskId) {
  const task = state.tasks.find(t => t.id === taskId);
  const taskTitle = task ? task.title : 'esta tarefa';
  if (!confirm(`Deseja realmente excluir "${taskTitle}"?`)) return;

  const api = getApi();
  try {
    const res = await api.delete_task(taskId);
    if (res && res.success) {
      state.tasks = res.tasks;
      if (state.editingTaskId === taskId) {
        cancelQuickEdit();
      }
      closeTaskTab(taskId);
      renderTasksList();
    }
  } catch (err) {
    console.error('Erro ao excluir tarefa:', err);
  }
}

// --- Edição Rápida no Chat (Requisito #2) ---
function setupChatListeners() {
  const chatInput = document.getElementById('chatInput');
  if (!chatInput) return;

  chatInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleChatSubmit();
    } else if (e.key === 'Escape') {
      e.preventDefault();
      cancelQuickEdit();
    }
  });
}

function startQuickEdit(taskId) {
  const task = state.tasks.find(t => t.id === taskId);
  if (!task) return;

  // Garante que a aba principal está visível
  switchToTab('main');

  state.editingTaskId = taskId;

  const input = document.getElementById('chatInput');
  const banner = document.getElementById('chatEditBanner');
  const bannerMsg = document.getElementById('chatEditMessage');
  const btn = document.getElementById('chatSubmitBtn');
  const btnText = document.getElementById('chatSubmitText');
  const btnIcon = document.getElementById('chatSubmitIcon');

  if (input) {
    input.value = task.title;
    input.placeholder = 'Editando tarefa... Pressione Enter para salvar ou Esc para cancelar';
    input.focus();
    input.select();
  }

  if (banner) {
    banner.classList.add('active');
  }
  if (bannerMsg) {
    bannerMsg.textContent = `Editando: "${task.title}"`;
  }

  if (btn) {
    btn.className = 'chat-btn chat-btn-alterar';
  }
  if (btnText) {
    btnText.textContent = 'Alterar';
  }
  if (btnIcon) {
    btnIcon.setAttribute('data-icon', 'check');
  }

  if (window.renderIcons) window.renderIcons();
}

function cancelQuickEdit() {
  state.editingTaskId = null;

  const input = document.getElementById('chatInput');
  const banner = document.getElementById('chatEditBanner');
  const btn = document.getElementById('chatSubmitBtn');
  const btnText = document.getElementById('chatSubmitText');
  const btnIcon = document.getElementById('chatSubmitIcon');

  if (input) {
    input.value = '';
    input.placeholder = 'Adicionar uma nova tarefa... (Pressione Enter)';
  }

  if (banner) {
    banner.classList.remove('active');
  }

  if (btn) {
    btn.className = 'chat-btn chat-btn-submit';
  }
  if (btnText) {
    btnText.textContent = 'Enviar';
  }
  if (btnIcon) {
    btnIcon.setAttribute('data-icon', 'send');
  }

  if (window.renderIcons) window.renderIcons();
}

async function handleChatSubmit() {
  const input = document.getElementById('chatInput');
  if (!input) return;

  const text = (input.value || '').trim();
  if (!text) return;

  const api = getApi();

  if (state.editingTaskId) {
    // MODO ALTERAÇÃO RÁPIDA
    const targetId = state.editingTaskId;
    try {
      const res = await api.update_task(targetId, { title: text });
      if (res && res.success) {
        state.tasks = res.tasks;
        cancelQuickEdit();
        renderTasksList();
        updateDetailPaneIfOpen(targetId);
      }
    } catch (err) {
      console.error('Erro ao atualizar tarefa:', err);
    }
  } else {
    // MODO CRIAÇÃO DE NOVA TAREFA
    try {
      const res = await api.create_task(text);
      if (res && res.success) {
        state.tasks = res.tasks;
        input.value = '';
        renderTasksList();
      }
    } catch (err) {
      console.error('Erro ao criar tarefa:', err);
    }
  }
}

// --- Gestão de Abas (Tabs) e Detalhes da Tarefa (Requisito #3) ---
function switchToTab(tabId) {
  state.activeTabId = tabId;

  // Atualiza botões de abas no header
  document.querySelectorAll('.tab-item').forEach(el => {
    el.classList.remove('active');
  });

  if (tabId === 'main') {
    const mainTabBtn = document.getElementById('tabMainBtn');
    if (mainTabBtn) mainTabBtn.classList.add('active');
  } else {
    const tabBtn = document.getElementById(`tabBtn_${tabId}`);
    if (tabBtn) tabBtn.classList.add('active');
  }

  // Atualiza visibilidade dos painéis
  document.querySelectorAll('.view-pane').forEach(el => {
    el.classList.remove('active');
  });

  if (tabId === 'main') {
    const mainPane = document.getElementById('paneMain');
    if (mainPane) mainPane.classList.add('active');
  } else {
    const detailPane = document.getElementById(`pane_${tabId}`);
    if (detailPane) detailPane.classList.add('active');
  }

  if (window.renderIcons) window.renderIcons();
}

function openTaskTab(taskId) {
  const task = state.tasks.find(t => t.id === taskId);
  if (!task) return;

  if (!state.openTabs.includes(taskId)) {
    state.openTabs.push(taskId);
    createTabHeader(task);
    createDetailPane(task);
  }

  switchToTab(taskId);
}

function closeTaskTab(taskId, event) {
  if (event) event.stopPropagation();

  state.openTabs = state.openTabs.filter(id => id !== taskId);

  const tabBtn = document.getElementById(`tabBtn_${taskId}`);
  if (tabBtn) tabBtn.remove();

  const pane = document.getElementById(`pane_${taskId}`);
  if (pane) pane.remove();

  if (state.markdownFields && state.markdownFields[taskId]) {
    delete state.markdownFields[taskId];
  }

  if (state.activeTabId === taskId) {
    switchToTab('main');
  }
}

function createTabHeader(task) {
  const tabsContainer = document.getElementById('tabsContainer');
  if (!tabsContainer) return;

  const tabEl = document.createElement('div');
  tabEl.className = 'tab-item';
  tabEl.id = `tabBtn_${task.id}`;
  tabEl.onclick = () => switchToTab(task.id);
  tabEl.innerHTML = `
    <span data-icon="file"></span>
    <span class="tab-title-text" id="tabText_${task.id}">${escapeHtml(task.title)}</span>
    <button type="button" class="tab-close-btn" onclick="closeTaskTab('${task.id}', event)" title="Fechar aba">
      <span data-icon="x"></span>
    </button>
  `;
  tabsContainer.appendChild(tabEl);
  if (window.renderIcons) window.renderIcons();
}

function createDetailPane(task) {
  const container = document.getElementById('dynamicPanesContainer');
  if (!container) return;

  const pane = document.createElement('section');
  pane.className = 'view-pane';
  pane.id = `pane_${task.id}`;

  const isCompleted = Boolean(task.completed);

  pane.innerHTML = `
    <div class="detail-container">
      <!-- Header da Tarefa -->
      <div class="detail-header-card">
        <div class="detail-header-left">
          <input
            type="checkbox"
            class="task-checkbox-custom"
            id="detailCheck_${task.id}"
            ${isCompleted ? 'checked' : ''}
            onchange="handleDetailToggleTask('${task.id}')"
            title="${isCompleted ? 'Marcar como pendente' : 'Marcar como concluída'}"
          />
          <input
            type="text"
            class="detail-task-title-input"
            id="detailTitleInput_${task.id}"
            value="${escapeHtml(task.title)}"
            onchange="handleDetailTitleChange('${task.id}', this.value)"
            title="Clique para editar o título da tarefa"
          />
        </div>
        <div style="font-size: 11px; color: var(--fg-muted);">
          Criada em ${escapeHtml(task.created_at || '')}
        </div>
      </div>

      <!-- Seção Descrição com Shared-Markdown -->
      <div class="detail-markdown-section">
        <div class="description-header-row">
          <div class="detail-section-title" style="margin-bottom: 0;">
            <span data-icon="file-text"></span> Descrição & Detalhes (Markdown)
          </div>
          <button
            type="button"
            class="btn btn-secondary btn-sm"
            id="btnEditDesc_${task.id}"
            onclick="handleToggleDescriptionEdit('${task.id}')"
            title="Alternar entre modo de visualização e edição"
          >
            <span data-icon="edit-3"></span> <span id="btnEditDescText_${task.id}">Editar Descrição</span>
          </button>
        </div>
        <div id="markdownContainer_${task.id}" style="flex: 1; min-height: 180px;">
          <!-- Componente <markdown-field> montado aqui -->
        </div>
      </div>

      <!-- Seção de Anexos -->
      <div class="detail-attachments-section">
        <div class="attachments-header-row">
          <div class="detail-section-title" style="margin-bottom: 0;">
            <span data-icon="paperclip"></span> Anexos (<span id="attCount_${task.id}">${(task.attachments || []).length}</span>)
          </div>
          <button type="button" class="btn btn-secondary btn-sm" onclick="handleAddAttachment('${task.id}')">
            <span data-icon="plus"></span> Adicionar Anexo
          </button>
        </div>
        <div class="attachments-grid" id="attachmentsGrid_${task.id}">
          ${renderAttachmentsGrid(task)}
        </div>
      </div>
    </div>
  `;

  container.appendChild(pane);

  // Instancia o MarkdownField no modo 'view' (Leitor formatado) com allowToggleEdit
  initMarkdownFieldForTask(task);
  if (window.renderIcons) window.renderIcons();
}

function updateDescHeaderButton(taskId, mode) {
  const btnText = document.getElementById(`btnEditDescText_${taskId}`);
  const btn = document.getElementById(`btnEditDesc_${taskId}`);
  if (btnText) {
    btnText.textContent = mode === 'edit' ? 'Visualizar' : 'Editar Descrição';
  }
  if (btn) {
    const iconSpan = btn.querySelector('[data-icon]');
    if (iconSpan) {
      iconSpan.setAttribute('data-icon', mode === 'edit' ? 'eye' : 'edit-3');
      if (window.renderIcons) window.renderIcons();
    }
  }
}

function handleToggleDescriptionEdit(taskId) {
  const mf = state.markdownFields ? state.markdownFields[taskId] : null;
  if (mf && typeof mf.getMode === 'function') {
    const curMode = mf.getMode();
    const targetMode = curMode === 'view' ? 'edit' : 'view';
    mf.setMode(targetMode);
    updateDescHeaderButton(taskId, targetMode);
    return;
  }

  // Fallback nativo: alterna visibilidade entre viewer e editor
  const nativeViewer = document.getElementById(`nativeDescViewer_${taskId}`);
  const nativeEditor = document.getElementById(`nativeDescEditor_${taskId}`);
  if (nativeViewer && nativeEditor) {
    const isEditing = nativeEditor.style.display !== 'none';
    const targetMode = isEditing ? 'view' : 'edit';
    nativeEditor.style.display = isEditing ? 'none' : 'flex';
    nativeViewer.style.display = isEditing ? 'block' : 'none';
    updateDescHeaderButton(taskId, targetMode);
  }
}

function renderNativeDescriptionFallback(task, container, descVal) {
  container.innerHTML = `
    <div id="nativeDescViewer_${task.id}" class="native-desc-viewer">
      <pre class="native-desc-content">${escapeHtml(descVal)}</pre>
    </div>
    <div id="nativeDescEditor_${task.id}" class="native-desc-editor" style="display: none; flex-direction: column; gap: 8px;">
      <textarea
        id="nativeDescTextarea_${task.id}"
        class="native-desc-textarea"
        placeholder="Descreva a tarefa..."
        rows="8"
      >${escapeHtml(descVal)}</textarea>
      <div class="native-desc-actions" style="display: flex; justify-content: flex-end; gap: 8px;">
        <button type="button" class="btn btn-secondary btn-sm" onclick="handleNativeCancelDesc('${task.id}')">
          Cancelar
        </button>
        <button type="button" class="btn btn-primary btn-sm" onclick="handleNativeSaveDesc('${task.id}')">
          Salvar
        </button>
      </div>
    </div>
  `;
}

async function handleNativeSaveDesc(taskId) {
  const textarea = document.getElementById(`nativeDescTextarea_${taskId}`);
  if (!textarea) return;
  const newContent = textarea.value;

  const api = getApi();
  try {
    const res = await api.update_task(taskId, { description: newContent });
    if (res && res.success) {
      state.tasks = res.tasks;
      const t = state.tasks.find(item => item.id === taskId);
      if (t) t.description = newContent;

      const viewer = document.getElementById(`nativeDescViewer_${taskId}`);
      if (viewer) {
        viewer.innerHTML = `<pre class="native-desc-content">${escapeHtml(newContent)}</pre>`;
      }
    }
  } catch (err) {
    console.error('Erro ao salvar descrição (nativo):', err);
  }
  handleToggleDescriptionEdit(taskId);
}

function handleNativeCancelDesc(taskId) {
  const task = state.tasks.find(t => t.id === taskId);
  const textarea = document.getElementById(`nativeDescTextarea_${taskId}`);
  if (task && textarea) {
    textarea.value = task.description || '';
  }
  handleToggleDescriptionEdit(taskId);
}

function initMarkdownFieldForTask(task) {
  const container = document.getElementById(`markdownContainer_${task.id}`);
  if (!container) return;

  const descVal = task.description || `# ${task.title}\n\nDescreva os detalhes e passos desta tarefa aqui...`;

  if (window.ToolboxMarkdown && window.ToolboxMarkdown.MarkdownField) {
    const mf = new window.ToolboxMarkdown.MarkdownField({
      value: descVal,
      mode: 'view', // Exigência da issue: inicia no modo Leitor formatado
      allowToggleEdit: true, // Botão "Editar" comuta para edição
      placeholder: 'Descreva a tarefa com Markdown...',
      onSave: async (newContent) => {
        const api = getApi();
        try {
          const res = await api.update_task(task.id, { description: newContent });
          if (res && res.success) {
            state.tasks = res.tasks;
            const t = state.tasks.find(item => item.id === task.id);
            if (t) t.description = newContent;
          }
        } catch (err) {
          console.error('Erro ao salvar descrição markdown:', err);
        }
        updateDescHeaderButton(task.id, 'view');
      },
      onCancel: () => {
        updateDescHeaderButton(task.id, 'view');
      }
    });

    // Sobrescreve setMode para sincronizar o botão do cabeçalho
    const origSetMode = mf.setMode.bind(mf);
    mf.setMode = (newMode, keepVal) => {
      origSetMode(newMode, keepVal);
      updateDescHeaderButton(task.id, mf.getMode());
    };

    if (!state.markdownFields) state.markdownFields = {};
    state.markdownFields[task.id] = mf;

    container.innerHTML = '';
    container.appendChild(mf.element);
  } else if (typeof customElements !== 'undefined' && customElements.get('markdown-field')) {
    // Fallback para Web Component se declarado
    const mfEl = document.createElement('markdown-field');
    mfEl.setAttribute('mode', 'view');
    mfEl.setAttribute('allow-toggle-edit', '');
    mfEl.setAttribute('value', descVal);
    mfEl.addEventListener('save', async (e) => {
      const api = getApi();
      try {
        const res = await api.update_task(task.id, { description: e.detail.value });
        if (res && res.success) {
          state.tasks = res.tasks;
          const t = state.tasks.find(item => item.id === task.id);
          if (t) t.description = e.detail.value;
        }
      } catch (err) {
        console.error('Erro ao salvar descrição:', err);
      }
      updateDescHeaderButton(task.id, 'view');
    });
    container.innerHTML = '';
    container.appendChild(mfEl);
  } else {
    // Fallback Nativo Resiliente com textarea e preview
    renderNativeDescriptionFallback(task, container, descVal);
  }
}

function renderAttachmentsGrid(task) {
  const atts = task.attachments || [];
  if (atts.length === 0) {
    return `
      <div style="font-size: 12px; color: var(--fg-muted); padding: 12px; grid-column: 1 / -1; text-align: center;">
        Nenhum anexo adicionado a esta tarefa ainda.
      </div>
    `;
  }

  return atts.map(att => `
    <div class="attachment-card" id="attCard_${att.id}">
      <div class="attachment-info">
        <span data-icon="file" style="color: var(--accent); flex-shrink: 0;"></span>
        <div style="overflow: hidden;">
          <div class="attachment-name" title="${escapeHtml(att.name)}">${escapeHtml(att.name)}</div>
          <div class="attachment-size">${escapeHtml(att.size_formatted || '')} • ${escapeHtml(att.added_at || '')}</div>
        </div>
      </div>
      <div class="attachment-actions">
        <button
          type="button"
          class="action-btn"
          onclick="handleOpenAttachment('${task.id}', '${att.id}')"
          title="Abrir anexo"
        >
          <span data-icon="external-link"></span>
        </button>
        <button
          type="button"
          class="action-btn"
          onclick="handleOpenAttachmentFolder('${task.id}', '${att.id}')"
          title="Abrir pasta do arquivo"
        >
          <span data-icon="folder-open"></span>
        </button>
        <button
          type="button"
          class="action-btn action-btn-delete"
          onclick="handleRemoveAttachment('${task.id}', '${att.id}')"
          title="Remover anexo"
        >
          <span data-icon="trash-2"></span>
        </button>
      </div>
    </div>
  `).join('');
}

async function handleAddAttachment(taskId) {
  const api = getApi();
  try {
    const res = await api.add_attachment_dialog(taskId);
    if (res && res.success) {
      state.tasks = res.tasks;
      const task = state.tasks.find(t => t.id === taskId);
      if (task) {
        const grid = document.getElementById(`attachmentsGrid_${taskId}`);
        const count = document.getElementById(`attCount_${taskId}`);
        if (grid) grid.innerHTML = renderAttachmentsGrid(task);
        if (count) count.textContent = (task.attachments || []).length;
        renderTasksList();
        if (window.renderIcons) window.renderIcons();
      }
    }
  } catch (err) {
    console.error('Erro ao adicionar anexo:', err);
  }
}

async function handleRemoveAttachment(taskId, attId) {
  if (!confirm('Deseja realmente remover este anexo?')) return;
  const api = getApi();
  try {
    const res = await api.remove_attachment(taskId, attId);
    if (res && res.success) {
      state.tasks = res.tasks;
      const task = state.tasks.find(t => t.id === taskId);
      if (task) {
        const grid = document.getElementById(`attachmentsGrid_${taskId}`);
        const count = document.getElementById(`attCount_${taskId}`);
        if (grid) grid.innerHTML = renderAttachmentsGrid(task);
        if (count) count.textContent = (task.attachments || []).length;
        renderTasksList();
        if (window.renderIcons) window.renderIcons();
      }
    }
  } catch (err) {
    console.error('Erro ao remover anexo:', err);
  }
}

async function handleOpenAttachment(taskId, attId) {
  const api = getApi();
  await api.open_attachment(taskId, attId);
}

async function handleOpenAttachmentFolder(taskId, attId) {
  const api = getApi();
  await api.open_attachment_folder(taskId, attId);
}

async function handleDetailTitleChange(taskId, newTitle) {
  const clean = (newTitle || '').trim();
  if (!clean) return;

  const api = getApi();
  try {
    const res = await api.update_task(taskId, { title: clean });
    if (res && res.success) {
      state.tasks = res.tasks;
      const tabText = document.getElementById(`tabText_${taskId}`);
      if (tabText) tabText.textContent = clean;
      renderTasksList();
    }
  } catch (err) {
    console.error('Erro ao alterar título da tarefa:', err);
  }
}

async function handleDetailToggleTask(taskId) {
  await handleToggleTask(taskId);
}

function updateDetailPaneIfOpen(taskId) {
  if (!state.openTabs.includes(taskId)) return;
  const task = state.tasks.find(t => t.id === taskId);
  if (!task) return;

  const check = document.getElementById(`detailCheck_${taskId}`);
  if (check) check.checked = Boolean(task.completed);

  const titleInput = document.getElementById(`detailTitleInput_${taskId}`);
  if (titleInput && titleInput.value !== task.title) {
    titleInput.value = task.title;
  }

  const tabText = document.getElementById(`tabText_${taskId}`);
  if (tabText) tabText.textContent = task.title;
}

// Utilitário de escape de HTML
function escapeHtml(str) {
  return String(str ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

// Exportações globais para chamadas nos inline handlers HTML
window.switchToTab = switchToTab;
window.closeTaskTab = closeTaskTab;
window.openTaskTab = openTaskTab;
window.handleToggleTask = handleToggleTask;
window.handleDeleteTask = handleDeleteTask;
window.startQuickEdit = startQuickEdit;
window.cancelQuickEdit = cancelQuickEdit;
window.handleChatSubmit = handleChatSubmit;
window.handleAddAttachment = handleAddAttachment;
window.handleRemoveAttachment = handleRemoveAttachment;
window.handleOpenAttachment = handleOpenAttachment;
window.handleOpenAttachmentFolder = handleOpenAttachmentFolder;
window.handleDetailTitleChange = handleDetailTitleChange;
window.handleDetailToggleTask = handleDetailToggleTask;
window.handleToggleDescriptionEdit = handleToggleDescriptionEdit;
window.handleNativeSaveDesc = handleNativeSaveDesc;
window.handleNativeCancelDesc = handleNativeCancelDesc;
window.setFilter = setFilter;
window.toggleTheme = toggleTheme;
