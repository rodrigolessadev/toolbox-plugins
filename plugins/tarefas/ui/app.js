/**
 * Tarefas Plugin - Frontend Application Logic
 * Gerenciamento de tarefas, chat inline rápido, abas dinâmicas e anexos.
 */

// Estado Global
let state = {
  tasks: [],
  activeFilter: 'all', // 'all' | 'pending' | 'completed'
  editingTaskId: null,
  selectedTaskId: null,
  subtaskTargetId: null,
  openTabs: [], // Lista de IDs de tarefas com abas abertas
  activeTabId: 'main', // 'main' ou ID da tarefa
  markdownFields: {}, // Instâncias ativas de MarkdownField por taskId
  collapsedParents: new Set(JSON.parse(localStorage.getItem('tarefas-collapsed-parents') || '[]')),
  dateFilter: {
    from: localStorage.getItem('tarefas-date-from') || '',
    to: localStorage.getItem('tarefas-date-to') || '',
    allDates: localStorage.getItem('tarefas-date-all') === 'true',
  },
};

// Fallback Mock para desenvolvimento web fora do pywebview
const mockApi = {
  get_tasks: async () => ({
    success: true,
    tasks: [
      {
        id: 'task_demo1',
        parent_id: null,
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
        id: 'task_demo1_sub1',
        parent_id: 'task_demo1',
        title: 'Esboçar diagrama C4 de contexto',
        description: 'Mapear integrações entre o frontend e a camada de domínio.',
        completed: true,
        created_at: '2026-09-15 10:30:00',
        updated_at: '2026-09-15 11:00:00',
        attachments: []
      },
      {
        id: 'task_demo2',
        parent_id: null,
        title: 'Revisar PR de autenticação biométrica',
        description: 'Verificar testes unitários e cobertura do Windows Hello.',
        completed: true,
        created_at: '2026-09-15 11:30:00',
        updated_at: '2026-09-15 12:00:00',
        attachments: []
      }
    ]
  }),
  create_task: async (title, desc = '', parentId = null) => {
    const newTask = {
      id: 'task_' + Math.random().toString(36).substr(2, 6),
      parent_id: parentId || null,
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
  create_subtask: async (parentId, title, desc = '') => {
    return mockApi.create_task(title, desc, parentId);
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
    const idsToDelete = new Set([id]);
    let changed = true;
    while (changed) {
      changed = false;
      for (const t of state.tasks) {
        if (idsToDelete.has(t.parent_id) && !idsToDelete.has(t.id)) {
          idsToDelete.add(t.id);
          changed = true;
        }
      }
    }
    state.tasks = state.tasks.filter(t => !idsToDelete.has(t.id));
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
  reorder_tasks: async (taskIds) => {
    const idMap = new Map(state.tasks.map(t => [t.id, t]));
    const reordered = [];
    const used = new Set();
    for (const id of taskIds) {
      if (idMap.has(id)) {
        reordered.push(idMap.get(id));
        used.add(id);
      }
    }
    for (const t of state.tasks) {
      if (!used.has(t.id)) {
        reordered.push(t);
      }
    }
    state.tasks = reordered;
    return { success: true, tasks: state.tasks };
  },
  sort_tasks: async (descending = true) => {
    state.tasks = sortTasksByStatusAndDate(state.tasks, descending);
    return { success: true, tasks: state.tasks };
  },
  filter_tasks_by_date: async (from = null, to = null, allDates = false) => {
    state.dateFilter.from = from || '';
    state.dateFilter.to = to || '';
    state.dateFilter.allDates = allDates;
    renderTasksList();
    return { success: true, tasks: state.tasks };
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
  initDateFilterUI();

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

// --- Filtro por Intervalo de Datas ---
function getDateRangeBoundaries() {
  if (state.dateFilter.allDates) {
    return { from: null, to: null, isDefault: false, isAll: true };
  }

  const cleanFrom = (state.dateFilter.from || '').trim();
  const cleanTo = (state.dateFilter.to || '').trim();

  // Padrão: 1 mês (últimos 30 dias até hoje) quando ambos em branco
  if (!cleanFrom && !cleanTo) {
    const now = new Date();
    const past = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
    const pad = n => String(n).padStart(2, '0');
    const fromStr = `${past.getFullYear()}-${pad(past.getMonth() + 1)}-${pad(past.getDate())} 00:00:00`;
    const toStr = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())} 23:59:59`;
    return { from: fromStr, to: toStr, isDefault: true, isAll: false };
  }

  const fromStr = cleanFrom ? `${cleanFrom} 00:00:00` : '1970-01-01 00:00:00';
  const toStr = cleanTo ? `${cleanTo} 23:59:59` : '9999-12-31 23:59:59';
  return { from: fromStr, to: toStr, isDefault: false, isAll: false };
}

function isTaskInDateRange(task, bounds) {
  if (bounds.isAll) return true;
  const dt = task.created_at || task.updated_at || '';
  if (!dt) return false;
  return dt >= bounds.from && dt <= bounds.to;
}

function initDateFilterUI() {
  const fromEl = document.getElementById('dateFilterFrom');
  const toEl = document.getElementById('dateFilterTo');
  const allBtn = document.getElementById('btnAllDates');

  if (fromEl) fromEl.value = state.dateFilter.from || '';
  if (toEl) toEl.value = state.dateFilter.to || '';

  if (allBtn) {
    if (state.dateFilter.allDates) {
      allBtn.classList.add('active');
    } else {
      allBtn.classList.remove('active');
    }
  }
}

function handleDateFilterChange() {
  const fromEl = document.getElementById('dateFilterFrom');
  const toEl = document.getElementById('dateFilterTo');

  state.dateFilter.from = fromEl ? fromEl.value : '';
  state.dateFilter.to = toEl ? toEl.value : '';
  state.dateFilter.allDates = false;

  localStorage.setItem('tarefas-date-from', state.dateFilter.from);
  localStorage.setItem('tarefas-date-to', state.dateFilter.to);
  localStorage.setItem('tarefas-date-all', 'false');

  const allBtn = document.getElementById('btnAllDates');
  if (allBtn) allBtn.classList.remove('active');

  renderTasksList();
}

function resetDateFilter() {
  state.dateFilter.from = '';
  state.dateFilter.to = '';
  state.dateFilter.allDates = false;

  localStorage.removeItem('tarefas-date-from');
  localStorage.removeItem('tarefas-date-to');
  localStorage.setItem('tarefas-date-all', 'false');

  initDateFilterUI();
  renderTasksList();
}

function toggleAllDatesFilter() {
  state.dateFilter.allDates = !state.dateFilter.allDates;
  localStorage.setItem('tarefas-date-all', String(state.dateFilter.allDates));

  initDateFilterUI();
  renderTasksList();
}

// --- Gerenciamento de Árvore e Subtarefas ---
function saveCollapsedParents() {
  localStorage.setItem('tarefas-collapsed-parents', JSON.stringify(Array.from(state.collapsedParents)));
}

function toggleCollapseParent(parentId, event) {
  if (event) event.stopPropagation();
  if (state.collapsedParents.has(parentId)) {
    state.collapsedParents.delete(parentId);
  } else {
    state.collapsedParents.add(parentId);
  }
  saveCollapsedParents();
  renderTasksList();
}

async function promptCreateSubtask(parentId) {
  prepareSubtaskCreation(parentId);
}

async function handleAddSubtaskFromDetail(parentId) {
  const input = document.getElementById(`inputSubtask_${parentId}`);
  if (!input) return;
  const title = input.value.trim();
  if (!title) return;

  const api = getApi();
  try {
    const res = await api.create_task(title, '', parentId);
    if (res && res.success) {
      state.tasks = res.tasks;
      input.value = '';
      state.collapsedParents.delete(parentId);
      saveCollapsedParents();
      renderTasksList();
      renderDetailSubtasksList(parentId);
      updateDetailPaneIfOpen(parentId);
    } else {
      alert(res?.error || 'Erro ao criar subtarefa.');
    }
  } catch (err) {
    console.error('Erro ao adicionar subtarefa a partir de detalhes:', err);
  }
}

// --- Ordenação Inteligente por Status e Data ---
function sortTasksByStatusAndDate(taskList, descending = true) {
  if (!taskList || !taskList.length) return [];
  return [...taskList].sort((a, b) => {
    // Critério 1: Status (pendentes primeiro, concluídas ao final)
    const aCompleted = Boolean(a.completed);
    const bCompleted = Boolean(b.completed);
    if (aCompleted !== bCompleted) {
      return aCompleted ? 1 : -1;
    }
    // Critério 2: Timestamp (created_at ou updated_at)
    const aDate = a.created_at || a.updated_at || '';
    const bDate = b.created_at || b.updated_at || '';
    const cmp = aDate.localeCompare(bDate);
    return descending ? -cmp : cmp;
  });
}

function calculateAdjustedTimestamp(prevItem, nextItem) {
  const parseDate = (d) => {
    if (!d) return Date.now();
    const t = new Date(d.replace(' ', 'T')).getTime();
    return isNaN(t) ? Date.now() : t;
  };
  const formatDate = (ms) => {
    const d = new Date(ms);
    const pad = (n) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
  };

  if (prevItem && nextItem) {
    const tPrev = parseDate(prevItem.created_at || prevItem.updated_at);
    const tNext = parseDate(nextItem.created_at || nextItem.updated_at);
    const mid = Math.round((tPrev + tNext) / 2);
    return formatDate(mid);
  } else if (prevItem) {
    const tPrev = parseDate(prevItem.created_at || prevItem.updated_at);
    return formatDate(tPrev - 60000);
  } else if (nextItem) {
    const tNext = parseDate(nextItem.created_at || nextItem.updated_at);
    return formatDate(tNext + 60000);
  }
  return formatDate(Date.now());
}

function renderDetailSubtasksList(parentId) {
  const listEl = document.getElementById(`detailSubtasksList_${parentId}`);
  const countEl = document.getElementById(`detailSubtaskCount_${parentId}`);
  if (!listEl) return;

  const rawSubtasks = state.tasks.filter(t => t.parent_id === parentId);
  const subtasks = sortTasksByStatusAndDate(rawSubtasks, true);
  const total = subtasks.length;
  const completed = subtasks.filter(s => s.completed).length;

  if (countEl) {
    countEl.textContent = total > 0 ? `${completed}/${total}` : '0';
  }

  if (total === 0) {
    listEl.innerHTML = '<div style="font-size: 12px; color: var(--fg-muted); padding: 8px 0;">Nenhuma subtarefa vinculada.</div>';
    return;
  }

  listEl.innerHTML = subtasks.map(st => `
    <div class="detail-subtask-item ${st.completed ? 'completed' : ''}" id="detailSubItem_${st.id}">
      <div class="detail-subtask-left">
        <input
          type="checkbox"
          class="task-checkbox-custom"
          ${st.completed ? 'checked' : ''}
          onchange="handleToggleSubtaskFromDetail('${st.id}', '${parentId}')"
        />
        <span class="detail-subtask-title" title="${escapeHtml(st.title)}">${escapeHtml(st.title)}</span>
      </div>
      <div style="display: flex; align-items: center; gap: 4px;">
        <button type="button" class="action-btn action-btn-view" onclick="openTaskTab('${st.id}')" title="Abrir detalhes da subtarefa">
          <span data-icon="eye"></span>
        </button>
        <button type="button" class="action-btn action-btn-delete" onclick="handleDeleteTask('${st.id}')" title="Excluir subtarefa">
          <span data-icon="trash-2"></span>
        </button>
      </div>
    </div>
  `).join('');

  if (window.renderIcons) window.renderIcons();
}

async function handleToggleSubtaskFromDetail(subtaskId, parentId) {
  await handleToggleTask(subtaskId);
  renderDetailSubtasksList(parentId);
}

// --- Renderização da Lista de Tarefas ---
function renderTasksList() {
  const container = document.getElementById('tasksListContainer');
  const statsText = document.getElementById('tasksStatsText');
  if (!container) return;

  const bounds = getDateRangeBoundaries();

  // Identifica tarefas raiz
  const rootTasks = state.tasks.filter(t => !t.parent_id);

  // Aplica filtro temporal: raiz incluída se estiver no período OU se alguma de suas subtarefas estiver no período
  const dateFilteredRoots = rootTasks.filter(task => {
    if (bounds.isAll) return true;
    if (isTaskInDateRange(task, bounds)) return true;
    const subtasks = state.tasks.filter(st => st.parent_id === task.id);
    return subtasks.some(st => isTaskInDateRange(st, bounds));
  });

  let filteredRoots = dateFilteredRoots;
  if (state.activeFilter === 'pending') {
    filteredRoots = dateFilteredRoots.filter(t => !t.completed || state.tasks.some(st => st.parent_id === t.id && !st.completed));
  } else if (state.activeFilter === 'completed') {
    filteredRoots = dateFilteredRoots.filter(t => t.completed);
  }

  // Estatísticas contextuais
  const inPeriodTotal = dateFilteredRoots.length;
  const completedInPeriod = dateFilteredRoots.filter(t => t.completed).length;

  if (statsText) {
    const periodLabel = bounds.isAll
      ? ''
      : (bounds.isDefault ? ' (último mês)' : ' (período)');
    statsText.textContent = `${completedInPeriod} de ${inPeriodTotal} concluída${inPeriodTotal === 1 ? '' : 's'}${periodLabel}`;
  }

  // Aplica ordenação determinística: pendentes no topo, concluídas ao final, mais recentes primeiro
  filteredRoots = sortTasksByStatusAndDate(filteredRoots, true);

  if (filteredRoots.length === 0) {
    const isFilteredByDate = !bounds.isAll;
    container.innerHTML = `
      <div class="empty-state">
        <div data-icon="${isFilteredByDate ? 'calendar' : 'check-square'}" class="empty-icon"></div>
        <div style="font-size: 14px; font-weight: 600; color: var(--fg);">Nenhuma tarefa encontrada${isFilteredByDate ? ' neste período' : ''}</div>
        <div style="font-size: 12px; margin-bottom: 8px;">
          ${isFilteredByDate ? 'Tente ajustar o intervalo de datas ou alternar para o histórico completo.' : 'Use o campo abaixo para adicionar tarefas com rapidez.'}
        </div>
        ${isFilteredByDate ? `
          <button type="button" class="btn btn-secondary btn-sm" onclick="toggleAllDatesFilter()">
            <span data-icon="calendar"></span> Ver todas as datas
          </button>
        ` : ''}
      </div>
    `;
    if (window.renderIcons) window.renderIcons();
    return;
  }

  function renderRootCardHtml(task) {
    const isCompleted = Boolean(task.completed);
    const rawSubtasks = state.tasks.filter(st => st.parent_id === task.id);
    const subCount = rawSubtasks.length;
    const subCompleted = rawSubtasks.filter(st => st.completed).length;
    const isCollapsed = state.collapsedParents.has(task.id);

    const attCount = (task.attachments || []).length;
    const attBadge = attCount > 0
      ? `<span class="task-meta-badge" title="${attCount} anexo(s)"><span data-icon="paperclip"></span> ${attCount}</span>`
      : '';

    const subtaskBadge = subCount > 0
      ? `<span class="subtask-badge" title="${subCompleted} de ${subCount} subtarefas concluídas">
           <span data-icon="corner-down-right"></span> ${subCompleted}/${subCount}
         </span>`
      : '';

    const chevronBtn = subCount > 0
      ? `<button type="button" class="btn-chevron ${isCollapsed ? 'collapsed' : ''}" onclick="toggleCollapseParent('${task.id}', event)" title="${isCollapsed ? 'Expandir subtarefas' : 'Recolher subtarefas'}">
           <span data-icon="${isCollapsed ? 'chevron-right' : 'chevron-down'}"></span>
         </button>`
      : '';

    // Subtarefas visíveis de acordo com o filtro ativo e temporal
    let visibleSubtasks = rawSubtasks;
    if (!bounds.isAll) {
      const parentMatches = isTaskInDateRange(task, bounds);
      if (!parentMatches) {
        visibleSubtasks = rawSubtasks.filter(st => isTaskInDateRange(st, bounds));
      }
    }
    if (state.activeFilter === 'pending') {
      visibleSubtasks = visibleSubtasks.filter(st => !st.completed);
    } else if (state.activeFilter === 'completed') {
      visibleSubtasks = visibleSubtasks.filter(st => st.completed);
    }
    visibleSubtasks = sortTasksByStatusAndDate(visibleSubtasks, true);

    const subtasksHtml = (subCount > 0 && !isCollapsed)
      ? `<div class="subtasks-container" id="subtasks_${task.id}">
          ${visibleSubtasks.map(sub => {
            const isSubCompleted = Boolean(sub.completed);
            const subAttCount = (sub.attachments || []).length;
            const subAttBadge = subAttCount > 0
              ? `<span class="task-meta-badge" title="${subAttCount} anexo(s)"><span data-icon="paperclip"></span> ${subAttCount}</span>`
              : '';
            const isSubSelected = state.selectedTaskId === sub.id;
            return `
              <div
                class="task-card task-card-nested ${isSubCompleted ? 'completed' : ''} ${isSubSelected ? 'selected' : ''}"
                id="card_${sub.id}"
                draggable="true"
                onclick="handleCardClick(event, '${task.id}')"
                ondragstart="handleDragStart(event, '${sub.id}', '${task.id}')"
                ondragend="handleDragEnd(event)"
                ondragover="handleDragOver(event, '${sub.id}', '${task.id}')"
                ondragleave="handleDragLeave(event)"
                ondrop="handleDrop(event, '${sub.id}', '${task.id}')"
              >
                <div class="task-left">
                  <span
                    class="drag-handle"
                    draggable="true"
                    ondragstart="handleDragStart(event, '${sub.id}', '${task.id}')"
                    ondragend="handleDragEnd(event)"
                    title="Arrastar para reordenar subtarefa"
                  >
                    <span data-icon="grip-vertical"></span>
                  </span>
                  <span class="subtask-indicator" data-icon="corner-down-right"></span>
                  <input
                    type="checkbox"
                    class="task-checkbox-custom"
                    ${isSubCompleted ? 'checked' : ''}
                    onchange="handleToggleTask('${sub.id}')"
                    title="${isSubCompleted ? 'Marcar como pendente' : 'Marcar como concluída'}"
                  />
                  <span class="task-title" title="${escapeHtml(sub.title)}">${escapeHtml(sub.title)}</span>
                  ${subAttBadge}
                </div>
                <div class="task-actions">
                  <button
                    type="button"
                    class="action-btn action-btn-edit"
                    onclick="startQuickEdit('${sub.id}')"
                    title="Editar rapidamente no chat"
                  >
                    <span data-icon="edit"></span>
                  </button>
                  <button
                    type="button"
                    class="action-btn action-btn-view"
                    onclick="openTaskTab('${sub.id}')"
                    title="Visualizar detalhes em aba dedicada"
                  >
                    <span data-icon="eye"></span>
                  </button>
                  <button
                    type="button"
                    class="action-btn action-btn-delete"
                    onclick="handleDeleteTask('${sub.id}')"
                    title="Excluir subtarefa"
                  >
                    <span data-icon="trash-2"></span>
                  </button>
                </div>
              </div>
            `;
          }).join('')}
        </div>`
      : '';

    const isSelected = state.selectedTaskId === task.id;
    return `
      <div class="subtasks-wrapper">
        <div
          class="task-card ${isCompleted ? 'completed' : ''} ${isSelected ? 'selected' : ''}"
          id="card_${task.id}"
          draggable="true"
          onclick="handleCardClick(event, '${task.id}')"
          ondragstart="handleDragStart(event, '${task.id}', null)"
          ondragend="handleDragEnd(event)"
          ondragover="handleDragOver(event, '${task.id}', null)"
          ondragleave="handleDragLeave(event)"
          ondrop="handleDrop(event, '${task.id}', null)"
        >
          <div class="task-left">
            <span
              class="drag-handle"
              draggable="true"
              ondragstart="handleDragStart(event, '${task.id}', null)"
              ondragend="handleDragEnd(event)"
              title="Arrastar para reordenar tarefa"
            >
              <span data-icon="grip-vertical"></span>
            </span>
            ${chevronBtn}
            <input
              type="checkbox"
              class="task-checkbox-custom"
              ${isCompleted ? 'checked' : ''}
              onchange="handleToggleTask('${task.id}')"
              title="${isCompleted ? 'Marcar como pendente' : 'Marcar como concluída'}"
            />
            <span class="task-title" title="${escapeHtml(task.title)}">${escapeHtml(task.title)}</span>
            ${attBadge}
            ${subtaskBadge}
          </div>
          <div class="task-actions">
            <button
              type="button"
              class="action-btn action-btn-add-sub"
              onclick="prepareSubtaskCreation('${task.id}')"
              title="Adicionar subtarefa"
            >
              <span data-icon="plus"></span>
            </button>
            <button
              type="button"
              class="action-btn action-btn-edit"
              onclick="startQuickEdit('${task.id}')"
              title="Editar rapidamente no chat"
            >
              <span data-icon="edit"></span>
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
        ${subtasksHtml}
      </div>
    `;
  }

  const pendingRoots = filteredRoots.filter(t => !t.completed);
  const completedRoots = filteredRoots.filter(t => t.completed);
  const showDivider = state.activeFilter === 'all' && pendingRoots.length > 0 && completedRoots.length > 0;

  let renderedHtml = '';
  if (showDivider) {
    const pendingHtml = pendingRoots.map(renderRootCardHtml).join('');
    const dividerHtml = `
      <div class="completed-divider" id="completedDivider">
        <span class="completed-divider-line"></span>
        <span class="completed-divider-text">
          <span data-icon="check"></span> Concluídas (${completedRoots.length})
        </span>
        <span class="completed-divider-line"></span>
      </div>
    `;
    const completedHtml = completedRoots.map(renderRootCardHtml).join('');
    renderedHtml = pendingHtml + dividerHtml + completedHtml;
  } else {
    renderedHtml = filteredRoots.map(renderRootCardHtml).join('');
  }

  container.innerHTML = renderedHtml;
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

// --- Edição Rápida e Criação de Subtarefas no Chat (Requisitos #2 e #4) ---
function setupChatListeners() {
  const chatInput = document.getElementById('chatInput');
  if (!chatInput) return;

  chatInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleChatSubmit();
    } else if (e.key === 'Escape') {
      e.preventDefault();
      handleChatCancel();
    }
  });

  // Tecla Esc global para cancelar edição ou desselecionar tarefa
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      handleChatCancel();
    }
  });

  // Clicar fora de cards desmarca a tarefa selecionada
  document.addEventListener('click', (e) => {
    if (!state.selectedTaskId && !state.subtaskTargetId) return;
    if (
      e.target.closest('.task-card') ||
      e.target.closest('.chat-dock') ||
      e.target.closest('.modal-overlay') ||
      e.target.closest('.tasks-toolbar') ||
      e.target.closest('.tab-item')
    ) {
      return;
    }
    clearSelection();
  });
}

function handleChatCancel() {
  if (state.editingTaskId) {
    cancelQuickEdit();
  }
  if (state.subtaskTargetId || state.selectedTaskId) {
    clearSelection();
  }
}

function startQuickEdit(taskId) {
  const task = state.tasks.find(t => t.id === taskId);
  if (!task) return;

  // Limpa modo de criação de subtarefa se ativo
  if (state.selectedTaskId || state.subtaskTargetId) {
    clearSelection();
  }

  // Garante que a aba principal está visível
  switchToTab('main');

  state.editingTaskId = taskId;

  const input = document.getElementById('chatInput');
  const banner = document.getElementById('chatEditBanner');
  const bannerIcon = document.getElementById('chatEditBannerIcon');
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
    banner.classList.remove('subtask-mode');
    banner.classList.add('active');
  }
  if (bannerIcon) {
    bannerIcon.setAttribute('data-icon', 'edit');
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
  const bannerIcon = document.getElementById('chatEditBannerIcon');
  const bannerMsg = document.getElementById('chatEditMessage');
  const btn = document.getElementById('chatSubmitBtn');
  const btnText = document.getElementById('chatSubmitText');
  const btnIcon = document.getElementById('chatSubmitIcon');

  if (input) {
    input.value = '';
    input.placeholder = 'Adicionar uma nova tarefa... (Pressione Enter)';
  }

  if (banner) {
    banner.classList.remove('active');
    banner.classList.remove('subtask-mode');
  }
  if (bannerIcon) {
    bannerIcon.setAttribute('data-icon', 'edit');
  }
  if (bannerMsg) {
    bannerMsg.textContent = 'Editando tarefa...';
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

function prepareSubtaskCreation(parentId) {
  const parentTask = state.tasks.find(t => t.id === parentId);
  if (!parentTask) return;

  // Se estava em edição rápida, limpa
  if (state.editingTaskId) {
    state.editingTaskId = null;
  }

  // Garante que a aba principal está visível
  switchToTab('main');

  // Se o item clicado for uma subtarefa, o alvo de criação é o pai raiz
  const targetParentId = parentTask.parent_id || parentTask.id;
  const rootParent = state.tasks.find(t => t.id === targetParentId) || parentTask;

  state.subtaskTargetId = targetParentId;
  state.selectedTaskId = targetParentId;

  // Atualiza classes visuais (.selected)
  document.querySelectorAll('.task-card').forEach(card => card.classList.remove('selected'));
  const cardEl = document.getElementById('card_' + targetParentId);
  if (cardEl) {
    cardEl.classList.add('selected');
    cardEl.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  const input = document.getElementById('chatInput');
  const banner = document.getElementById('chatEditBanner');
  const bannerIcon = document.getElementById('chatEditBannerIcon');
  const bannerMsg = document.getElementById('chatEditMessage');
  const btn = document.getElementById('chatSubmitBtn');
  const btnText = document.getElementById('chatSubmitText');
  const btnIcon = document.getElementById('chatSubmitIcon');

  if (input) {
    input.value = '';
    input.placeholder = `Nova subtarefa para "${rootParent.title}"... (Enter para criar, Esc para cancelar)`;
    input.focus();
  }

  if (banner) {
    banner.classList.add('active');
    banner.classList.add('subtask-mode');
  }
  if (bannerIcon) {
    bannerIcon.setAttribute('data-icon', 'corner-down-right');
  }
  if (bannerMsg) {
    bannerMsg.textContent = `Subtarefa para: "${rootParent.title}"`;
  }

  if (btn) {
    btn.className = 'chat-btn chat-btn-subtask';
  }
  if (btnText) {
    btnText.textContent = 'Adicionar Subtarefa';
  }
  if (btnIcon) {
    btnIcon.setAttribute('data-icon', 'corner-down-right');
  }

  if (window.renderIcons) window.renderIcons();
}

function clearSelection() {
  state.selectedTaskId = null;
  state.subtaskTargetId = null;

  document.querySelectorAll('.task-card.selected').forEach(card => card.classList.remove('selected'));

  const input = document.getElementById('chatInput');
  const banner = document.getElementById('chatEditBanner');
  const bannerIcon = document.getElementById('chatEditBannerIcon');
  const bannerMsg = document.getElementById('chatEditMessage');
  const btn = document.getElementById('chatSubmitBtn');
  const btnText = document.getElementById('chatSubmitText');
  const btnIcon = document.getElementById('chatSubmitIcon');

  if (input && !state.editingTaskId) {
    input.value = '';
    input.placeholder = 'Adicionar uma nova tarefa... (Pressione Enter)';
  }

  if (banner && !state.editingTaskId) {
    banner.classList.remove('active');
    banner.classList.remove('subtask-mode');
    if (bannerIcon) bannerIcon.setAttribute('data-icon', 'edit');
    if (bannerMsg) bannerMsg.textContent = 'Editando tarefa...';
  }

  if (btn && !state.editingTaskId) {
    btn.className = 'chat-btn chat-btn-submit';
  }
  if (btnText && !state.editingTaskId) {
    btnText.textContent = 'Enviar';
  }
  if (btnIcon && !state.editingTaskId) {
    btnIcon.setAttribute('data-icon', 'send');
  }

  if (window.renderIcons) window.renderIcons();
}

function cancelSubtaskCreation() {
  clearSelection();
}

function selectTask(taskId) {
  if (state.selectedTaskId === taskId) {
    clearSelection();
    return;
  }
  prepareSubtaskCreation(taskId);
}

function handleCardClick(event, taskId) {
  if (event && event.target) {
    if (event.target.closest('button, input, .drag-handle, .subtask-collapse-btn, a')) {
      return;
    }
  }
  selectTask(taskId);
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
  } else if (state.subtaskTargetId) {
    // MODO CRIAÇÃO DE SUBTAREFA VIA CHAT
    const parentId = state.subtaskTargetId;
    try {
      const res = await api.create_task(text, '', parentId);
      if (res && res.success) {
        state.tasks = res.tasks;
        state.collapsedParents.delete(parentId);
        saveCollapsedParents();
        input.value = '';
        renderTasksList();
        updateDetailPaneIfOpen(parentId);

        // Mantém a tarefa selecionada para criação contínua e foca no input
        const cardEl = document.getElementById('card_' + parentId);
        if (cardEl) {
          cardEl.classList.add('selected');
        }
        input.focus();
      } else {
        alert(res?.error || 'Erro ao criar subtarefa.');
      }
    } catch (err) {
      console.error('Erro ao criar subtarefa:', err);
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
            <span data-icon="edit"></span> <span id="btnEditDescText_${task.id}">Editar Descrição</span>
          </button>
        </div>
        <div id="markdownContainer_${task.id}" style="flex: 1; min-height: 180px;">
          <!-- Componente <markdown-field> montado aqui -->
        </div>
      </div>

      <!-- Seção de Subtarefas -->
      <div class="detail-subtasks-section">
        <div class="subtasks-header-row">
          <div class="detail-section-title" style="margin-bottom: 0;">
            <span data-icon="corner-down-right"></span> Subtarefas (<span id="detailSubtaskCount_${task.id}">0</span>)
          </div>
        </div>
        <div class="subtask-add-row">
          <input
            type="text"
            class="subtask-input"
            id="inputSubtask_${task.id}"
            placeholder="Adicionar subtarefa... (Pressione Enter)"
            onkeydown="if(event.key === 'Enter') handleAddSubtaskFromDetail('${task.id}')"
          />
          <button type="button" class="btn btn-secondary btn-sm" onclick="handleAddSubtaskFromDetail('${task.id}')">
            <span data-icon="plus"></span> Adicionar
          </button>
        </div>
        <div class="detail-subtasks-list" id="detailSubtasksList_${task.id}">
          <!-- Subtarefas renderizadas dinamicamente -->
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
  renderDetailSubtasksList(task.id);
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
      iconSpan.setAttribute('data-icon', mode === 'edit' ? 'eye' : 'edit');
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

  renderDetailSubtasksList(taskId);
}

// --- Drag and Drop (Reordenação Manual e Aninhamento) ---
let draggedTaskId = null;
let draggedParentId = null;

function isDescendant(potentialParentId, targetId) {
  if (!potentialParentId || !targetId) return false;
  let current = state.tasks.find(t => t.id === targetId);
  const visited = new Set();
  while (current && current.parent_id) {
    if (current.parent_id === potentialParentId) return true;
    if (visited.has(current.parent_id)) break;
    visited.add(current.parent_id);
    current = state.tasks.find(t => t.id === current.parent_id);
  }
  return false;
}

function handleDragStart(e, taskId, parentId) {
  if (e.target && e.target.closest('button, input, textarea, a, .subtask-collapse-btn')) {
    e.preventDefault();
    return;
  }
  draggedTaskId = taskId;
  draggedParentId = parentId || null;
  if (e.dataTransfer) {
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', taskId);
  }
  setTimeout(() => {
    const card = document.getElementById(`card_${taskId}`);
    if (card) card.classList.add('dragging');
  }, 0);
}

function handleDragOver(e, targetTaskId, targetParentId) {
  if (!draggedTaskId || draggedTaskId === targetTaskId) return;

  // Prevenção de ciclos: não permitir arrastar pai sobre si mesmo ou qualquer filho/descendente
  if (isDescendant(draggedTaskId, targetTaskId)) {
    return;
  }

  e.preventDefault();
  if (e.dataTransfer) {
    e.dataTransfer.dropEffect = 'move';
  }

  const card = document.getElementById(`card_${targetTaskId}`);
  if (!card) return;

  const rect = card.getBoundingClientRect();
  const relY = e.clientY - rect.top;
  const ratio = rect.height > 0 ? relY / rect.height : 0.5;

  card.classList.remove('drag-over-top', 'drag-over-center', 'drag-over-bottom');

  if (ratio < 0.25) {
    card.classList.add('drag-over-top');
  } else if (ratio <= 0.75) {
    card.classList.add('drag-over-center');
  } else {
    card.classList.add('drag-over-bottom');
  }
}

function handleDragLeave(e) {
  const card = e.currentTarget;
  if (card && (!e.relatedTarget || !card.contains(e.relatedTarget))) {
    card.classList.remove('drag-over-top', 'drag-over-center', 'drag-over-bottom');
  }
}

function handleDragEnd(e) {
  draggedTaskId = null;
  draggedParentId = null;
  document.querySelectorAll('.task-card').forEach(card => {
    card.classList.remove('dragging', 'drag-over-top', 'drag-over-center', 'drag-over-bottom');
  });
}

function rebuildTasksOrder() {
  const roots = state.tasks.filter(t => !t.parent_id);
  const result = [];
  for (const root of roots) {
    result.push(root);
    const subs = state.tasks.filter(t => t.parent_id === root.id);
    result.push(...subs);
  }
  for (const t of state.tasks) {
    if (!result.includes(t)) result.push(t);
  }
  state.tasks = result;
}

async function handleDrop(e, targetTaskId, targetParentId) {
  e.preventDefault();
  if (!draggedTaskId || draggedTaskId === targetTaskId) {
    handleDragEnd(e);
    return;
  }

  // Prevenção de ciclos
  if (isDescendant(draggedTaskId, targetTaskId)) {
    handleDragEnd(e);
    return;
  }

  const card = document.getElementById(`card_${targetTaskId}`);
  const isCenter = card ? card.classList.contains('drag-over-center') : false;
  const isTop = card ? card.classList.contains('drag-over-top') : true;

  const draggedItem = state.tasks.find(t => t.id === draggedTaskId);
  const targetItem = state.tasks.find(t => t.id === targetTaskId);
  if (!draggedItem || !targetItem) {
    handleDragEnd(e);
    return;
  }

  const api = getApi();

  if (isCenter) {
    // --- CENÁRIO A: ANINHAMENTO COMO SUBTAREFA ---
    // Se o alvo for tarefa raiz, vira subtarefa direta dela.
    // Se o alvo já for subtarefa, adota no mesmo pai daquela subtarefa.
    const newParentId = targetItem.parent_id || targetItem.id;
    if (newParentId === draggedTaskId || isDescendant(draggedTaskId, newParentId)) {
      handleDragEnd(e);
      return;
    }

    // Descolapsa o pai para mostrar a nova subtarefa
    state.collapsedParents.delete(newParentId);
    saveCollapsedParents();

    // Calcula timestamp para figurar na ordem das subtarefas daquele pai
    const existingSubs = state.tasks.filter(t => t.parent_id === newParentId && t.id !== draggedTaskId);
    const lastSub = existingSubs.length > 0 ? existingSubs[existingSubs.length - 1] : null;
    const newTs = calculateAdjustedTimestamp(lastSub, null);

    draggedItem.parent_id = newParentId;
    draggedItem.created_at = newTs;
    draggedItem.updated_at = newTs;

    rebuildTasksOrder();
    renderTasksList();
    handleDragEnd(e);

    try {
      const res = await api.update_task(draggedTaskId, {
        parent_id: newParentId,
        created_at: newTs,
        updated_at: newTs
      });
      if (res && res.success && res.tasks) {
        state.tasks = res.tasks;
        renderTasksList();
      }
    } catch (err) {
      console.error('Erro ao aninhar subtarefa via drag-and-drop:', err);
    }
    return;
  }

  // --- CENÁRIO B: REORDENAÇÃO ENTRE TAREFAS (TOP OU BOTTOM) ---
  // O parent_id de destino é o mesmo do alvo onde foi solto (irmãos)
  const newParentId = targetItem.parent_id || null;
  if (newParentId === draggedTaskId || isDescendant(draggedTaskId, newParentId)) {
    handleDragEnd(e);
    return;
  }

  const siblings = state.tasks.filter(t => (t.parent_id || null) === newParentId && t.id !== draggedTaskId);
  const targetIndex = siblings.findIndex(t => t.id === targetTaskId);
  if (targetIndex === -1) {
    handleDragEnd(e);
    return;
  }

  const insertIndex = isTop ? targetIndex : targetIndex + 1;
  const prevItem = insertIndex > 0 ? siblings[insertIndex - 1] : null;
  const nextItem = insertIndex < siblings.length ? siblings[insertIndex] : null;
  const newTs = calculateAdjustedTimestamp(prevItem, nextItem);

  draggedItem.parent_id = newParentId;
  draggedItem.created_at = newTs;
  draggedItem.updated_at = newTs;

  siblings.splice(insertIndex, 0, draggedItem);
  const orderedSiblingIds = siblings.map(t => t.id);

  let finalOrderedIds = [];
  if (!newParentId) {
    // Reordenando no nível raiz
    for (const rootId of orderedSiblingIds) {
      finalOrderedIds.push(rootId);
      const subs = state.tasks.filter(t => t.parent_id === rootId);
      subs.forEach(s => finalOrderedIds.push(s.id));
    }
    for (const t of state.tasks) {
      if (!finalOrderedIds.includes(t.id)) finalOrderedIds.push(t.id);
    }
  } else {
    // Reordenando dentro de um grupo de subtarefas
    for (const t of state.tasks) {
      if (t.parent_id === newParentId) {
        if (!finalOrderedIds.some(id => orderedSiblingIds.includes(id))) {
          finalOrderedIds.push(...orderedSiblingIds);
        }
      } else if (!orderedSiblingIds.includes(t.id)) {
        finalOrderedIds.push(t.id);
      }
    }
  }

  const idMap = new Map(state.tasks.map(t => [t.id, t]));
  state.tasks = finalOrderedIds.map(id => idMap.get(id)).filter(Boolean);

  renderTasksList();
  handleDragEnd(e);

  const apiRef = getApi();
  try {
    await apiRef.update_task(draggedTaskId, {
      parent_id: newParentId,
      created_at: newTs,
      updated_at: newTs
    });
    const res = await apiRef.reorder_tasks(finalOrderedIds);
    if (res && res.success && res.tasks) {
      state.tasks = res.tasks;
    }
  } catch (err) {
    console.error('Erro ao salvar reordenação:', err);
  }
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
window.toggleCollapseParent = toggleCollapseParent;
window.promptCreateSubtask = promptCreateSubtask;
window.handleAddSubtaskFromDetail = handleAddSubtaskFromDetail;
window.handleToggleSubtaskFromDetail = handleToggleSubtaskFromDetail;
window.handleDragStart = handleDragStart;
window.handleDragOver = handleDragOver;
window.handleDragLeave = handleDragLeave;
window.handleDragEnd = handleDragEnd;
window.handleDrop = handleDrop;
window.sortTasksByStatusAndDate = sortTasksByStatusAndDate;
window.handleDateFilterChange = handleDateFilterChange;
window.resetDateFilter = resetDateFilter;
window.toggleAllDatesFilter = toggleAllDatesFilter;
window.prepareSubtaskCreation = prepareSubtaskCreation;
window.cancelSubtaskCreation = cancelSubtaskCreation;
window.clearSelection = clearSelection;
window.selectTask = selectTask;
window.handleCardClick = handleCardClick;
window.handleChatCancel = handleChatCancel;
window.isDescendant = isDescendant;
window.rebuildTasksOrder = rebuildTasksOrder;
