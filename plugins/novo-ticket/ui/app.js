let currentTicket = null;
let currentSubfolders = [];
let quickDatesData = null;

// Inicialização
document.addEventListener('DOMContentLoaded', async () => {
  setupInputListeners();
  loadSavedBaseDir();
  await loadQuickDates();
});

window.addEventListener('pywebviewready', () => {
  refreshExistingTicketsList();
});

function switchTab(tabId) {
  document.querySelectorAll('.tab-pane').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
  
  document.getElementById(tabId).classList.add('active');
  if (tabId === 'tabTicket') {
    document.getElementById('tabBtn1').classList.add('active');
  } else {
    document.getElementById('tabBtn2').classList.add('active');
    renderSubfoldersTree();
  }
}

function setupInputListeners() {
  const updatePreviewAndList = () => {
    handlePreviewUpdate();
    const baseDir = document.getElementById('inputBaseDir').value.trim();
    if (baseDir) {
      localStorage.setItem('toolbox_novo_ticket_base_dir', baseDir);
      refreshExistingTicketsList();
    } else {
      const select = document.getElementById('selectExistingTicket');
      if (select) {
        select.innerHTML = '<option value="">Informe o diretório base acima para listar os tickets...</option>';
      }
    }
  };

  document.getElementById('inputBaseDir').addEventListener('input', updatePreviewAndList);
  document.getElementById('inputBaseDir').addEventListener('change', updatePreviewAndList);
  document.getElementById('inputClient').addEventListener('input', () => handlePreviewUpdate());
  document.getElementById('inputTicket').addEventListener('input', () => handlePreviewUpdate());
}

function loadSavedBaseDir() {
  const saved = localStorage.getItem('toolbox_novo_ticket_base_dir');
  if (saved && saved.trim()) {
    document.getElementById('inputBaseDir').value = saved.trim();
    handlePreviewUpdate();
    refreshExistingTicketsList();
  } else {
    document.getElementById('inputBaseDir').value = '';
    const select = document.getElementById('selectExistingTicket');
    if (select) {
      select.innerHTML = '<option value="">Informe o diretório base acima para listar os tickets...</option>';
    }
  }
}

async function refreshExistingTicketsList() {
  const select = document.getElementById('selectExistingTicket');
  if (!select) return;
  const baseDir = document.getElementById('inputBaseDir').value.trim();
  if (!baseDir) {
    select.innerHTML = '<option value="">Informe o diretório base acima para listar os tickets...</option>';
    return;
  }

  if (!window.pywebview || !window.pywebview.api || !window.pywebview.api.list_tickets) {
    return;
  }

  try {
    const res = await window.pywebview.api.list_tickets(baseDir);
    if (res.success && Array.isArray(res.tickets) && res.tickets.length > 0) {
      select.innerHTML = res.tickets.map(t => {
        const mod = t.modified_at ? ` (${t.modified_at})` : '';
        return `<option value="${t.path}">${t.name}${mod}</option>`;
      }).join('');
    } else if (res.success) {
      select.innerHTML = '<option value="">Nenhuma pasta de ticket encontrada no diretório base</option>';
    } else {
      select.innerHTML = `<option value="">${res.message || 'Diretório não encontrado'}</option>`;
    }
  } catch (err) {
    console.error('Erro ao listar tickets:', err);
    select.innerHTML = '<option value="">Erro ao carregar lista de tickets</option>';
  }
}

async function loadQuickDates() {
  try {
    if (window.pywebview && window.pywebview.api) {
      quickDatesData = await window.pywebview.api.get_quick_dates();
      if (quickDatesData) {
        document.getElementById('startDate').value = quickDatesData.today;
        document.getElementById('endDate').value = quickDatesData.today;
      }
    }
  } catch (err) {
    console.error('Erro ao carregar datas:', err);
  }
}

function applyQuickDate(type) {
  if (!quickDatesData) return;
  if (type === 'today') {
    document.getElementById('startDate').value = quickDatesData.today;
    document.getElementById('endDate').value = quickDatesData.today;
  } else if (type === 'yesterday') {
    document.getElementById('startDate').value = quickDatesData.yesterday;
    document.getElementById('endDate').value = quickDatesData.yesterday;
  } else if (type === 'week') {
    document.getElementById('startDate').value = quickDatesData.week_ago;
    document.getElementById('endDate').value = quickDatesData.today;
  }
}

async function handleSelectBaseDir() {
  try {
    const cur = document.getElementById('inputBaseDir').value;
    const res = await window.pywebview.api.select_base_folder(cur);
    if (res) {
      document.getElementById('inputBaseDir').value = res;
      localStorage.setItem('toolbox_novo_ticket_base_dir', res);
      handlePreviewUpdate();
      refreshExistingTicketsList();
    }
  } catch (err) {
    console.error('select_base_folder erro:', err);
  }
}

async function handlePreviewUpdate() {
  const baseDir = document.getElementById('inputBaseDir').value;
  const client = document.getElementById('inputClient').value;
  const ticket = document.getElementById('inputTicket').value;

  const previewEl = document.getElementById('previewPath');
  if (!baseDir || (!client && !ticket)) {
    previewEl.textContent = 'Informe o diretório, cliente e ticket...';
    previewEl.style.color = 'var(--fg-muted)';
    return;
  }

  try {
    const res = await window.pywebview.api.preview_ticket(baseDir, client, ticket);
    if (res.valid) {
      previewEl.textContent = res.full_path + (res.exists ? ' (⚠️ já existe no disco)' : '');
      previewEl.style.color = res.exists ? 'var(--warning)' : 'var(--accent-hover)';
    } else {
      previewEl.textContent = res.message;
      previewEl.style.color = 'var(--danger)';
    }
  } catch (err) {
    console.error(err);
  }
}

async function handleCreateTicket() {
  const baseDir = document.getElementById('inputBaseDir').value;
  const client = document.getElementById('inputClient').value;
  const ticket = document.getElementById('inputTicket').value;

  try {
    const res = await window.pywebview.api.create_ticket(baseDir, client, ticket);
    if (res.success && res.ticket) {
      setActiveTicket(res.ticket);
      localStorage.setItem('toolbox_novo_ticket_base_dir', baseDir);
      refreshExistingTicketsList();
      switchTab('tabLogs');
    } else {
      alert(res.message || 'Erro ao criar ticket.');
    }
  } catch (err) {
    alert('Erro: ' + err);
  }
}

async function handleOpenSelectedTicket() {
  const select = document.getElementById('selectExistingTicket');
  if (!select || !select.value) {
    alert('Selecione uma pasta de ticket válida na lista.');
    return;
  }

  try {
    const res = await window.pywebview.api.select_existing_ticket_by_path(select.value);
    if (res.success && res.ticket) {
      setActiveTicket(res.ticket);
      switchTab('tabLogs');
    } else {
      alert(res.message || 'Erro ao carregar detalhes do ticket.');
    }
  } catch (err) {
    alert('Erro ao abrir ticket: ' + err);
  }
}

async function handleSelectExistingTicket() {
  try {
    const res = await window.pywebview.api.select_ticket_folder();
    if (res.success && res.ticket) {
      setActiveTicket(res.ticket);
      switchTab('tabLogs');
    } else if (res.message) {
      alert(res.message);
    }
  } catch (err) {
    alert('Erro ao abrir pasta: ' + err);
  }
}

function setActiveTicket(ticket) {
  currentTicket = ticket;
  currentSubfolders = ticket.subfolders || [];
  
  // Atualiza Badge do Header
  const badge = document.getElementById('activeTicketBadge');
  badge.textContent = `Ticket Ativo: ${ticket.name}`;
  badge.className = 'badge badge-accent';

  // Atualiza Card de Ticket Ativo
  document.getElementById('cardActiveTicket').style.display = 'flex';
  document.getElementById('activeTicketName').textContent = ticket.name;
  document.getElementById('activeTicketPath').textContent = ticket.path;

  renderSubfoldersTree();
}

function renderSubfoldersTree() {
  const container = document.getElementById('subfoldersTree');
  if (!currentTicket) {
    container.innerHTML = `<div style="padding: 16px; text-align: center; color: var(--fg-muted);">Nenhum ticket ativo selecionado.</div>`;
    return;
  }

  const query = (document.getElementById('inputSearchSubfolders')?.value || '').toLowerCase().trim();
  const filtered = currentSubfolders.filter(s => s.name.toLowerCase().includes(query) || s.path.toLowerCase().includes(query));

  if (filtered.length === 0) {
    container.innerHTML = `<div style="padding: 16px; text-align: center; color: var(--fg-muted);">Nenhuma subpasta encontrada com o termo pesquisado.</div>`;
    return;
  }

  container.innerHTML = filtered.map(item => {
    const indent = (item.depth || 0) * 20;
    const badgeClass = item.log_count > 0 ? 'badge-success' : 'badge-muted';
    const badgeText = item.log_count > 0 ? `${item.log_count} logs` : 'sem logs';
    const isChecked = item.selected !== false ? 'checked' : '';

    return `
      <div class="tree-row" style="padding-left: ${10 + indent}px;">
        <div class="tree-row-left">
          <input type="checkbox" class="tree-checkbox subfolder-chk" data-path="${item.path}" ${isChecked} onchange="handleSubfolderToggle('${item.path}', this.checked)">
          <span style="font-size: 13px; font-weight: 500;">${item.name}</span>
          ${item.depth > 0 ? `<span style="font-size: 10px; color: var(--fg-muted);">(${item.parent})</span>` : ''}
        </div>
        <div class="badge ${badgeClass}">${badgeText}</div>
      </div>
    `;
  }).join('');
}

function handleSubfolderToggle(path, checked) {
  const target = currentSubfolders.find(s => s.path === path);
  if (target) {
    target.selected = checked;
  }
}

function toggleSelectAllSubfolders(selectAll) {
  currentSubfolders.forEach(s => s.selected = selectAll);
  renderSubfoldersTree();
}

function handleSearchSubfolders() {
  renderSubfoldersTree();
}

async function reloadSubfolders() {
  if (!currentTicket) return;
  try {
    const res = await window.pywebview.api.get_ticket_details(currentTicket.path);
    if (res.success && res.ticket) {
      setActiveTicket(res.ticket);
    }
  } catch (err) {
    console.error(err);
  }
}

async function handleCopyActivePath() {
  if (!currentTicket) return;
  try {
    await window.pywebview.api.copy_text(currentTicket.path);
    alert('Caminho copiado para a área de transferência!');
  } catch (err) {
    console.error(err);
  }
}

async function handleOpenActiveInExplorer() {
  if (!currentTicket) return;
  try {
    await window.pywebview.api.open_path(currentTicket.path);
  } catch (err) {
    console.error(err);
  }
}

async function handleExecuteFilter() {
  if (!currentTicket) {
    alert('Selecione ou crie um ticket primeiro!');
    return;
  }

  const selectedPaths = currentSubfolders.filter(s => s.selected !== false).map(s => s.path);
  if (selectedPaths.length === 0) {
    alert('Selecione ao menos uma subpasta com logs para filtrar.');
    return;
  }

  const startDate = document.getElementById('startDate').value;
  const startTime = document.getElementById('startTime').value;
  const endDate = document.getElementById('endDate').value;
  const endTime = document.getElementById('endTime').value;
  const overwrite = document.getElementById('checkOverwrite').checked;

  const btn = document.getElementById('btnExecuteFilter');
  btn.disabled = true;
  btn.textContent = 'Processando...';

  const feedbackCard = document.getElementById('cardFilterFeedback');
  const feedbackMsg = document.getElementById('feedbackMessage');
  const feedbackActions = document.getElementById('feedbackActions');

  try {
    const res = await window.pywebview.api.execute_filter(
      currentTicket.path,
      selectedPaths,
      startDate,
      startTime,
      endDate,
      endTime,
      overwrite
    );

    feedbackCard.style.display = 'flex';
    if (res.success) {
      feedbackCard.className = 'feedback-box feedback-success';
      feedbackMsg.textContent = res.message;
      feedbackActions.style.display = 'flex';
    } else {
      feedbackCard.className = 'feedback-box feedback-danger';
      feedbackMsg.textContent = res.message;
      feedbackActions.style.display = 'none';
    }
  } catch (err) {
    feedbackCard.style.display = 'flex';
    feedbackCard.className = 'feedback-box feedback-danger';
    feedbackMsg.textContent = 'Erro inesperado: ' + err;
  } finally {
    btn.disabled = false;
    btn.innerHTML = `<span data-icon="zap"></span> Extrair e Filtrar Logs`;
    if (window.renderIcons) window.renderIcons();
  }
}

async function handleOpenFilteredFolder() {
  if (!currentTicket) return;
  const filteredPath = currentTicket.path + '/logs_filtrados';
  try {
    await window.pywebview.api.open_path(filteredPath);
  } catch (err) {
    console.error(err);
  }
}
