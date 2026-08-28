let currentTicket = null;
let currentSubfolders = [];
let currentTicketFiles = [];
let quickDatesData = null;

// Inicialização
document.addEventListener('DOMContentLoaded', async () => {
  setupInputListeners();
  await loadSavedBaseDir();
  await loadQuickDates();
});

window.addEventListener('pywebviewready', async () => {
  await loadSavedBaseDir();
  refreshExistingTicketsList();
});

function switchTab(tabId) {
  document.querySelectorAll('.tab-pane').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
  
  const pane = document.getElementById(tabId);
  if (pane) pane.classList.add('active');

  if (tabId === 'tabTicket') {
    document.getElementById('tabBtn1')?.classList.add('active');
  } else if (tabId === 'tabLogs') {
    document.getElementById('tabBtn2')?.classList.add('active');
    renderSubfoldersTree();
  } else if (tabId === 'tabFiles') {
    document.getElementById('tabBtn3')?.classList.add('active');
    renderTicketFiles();
  }

  if (window.renderIcons) window.renderIcons();
}

function setupInputListeners() {
  const updatePreviewAndList = async () => {
    handlePreviewUpdate();
    const baseDir = document.getElementById('inputBaseDir').value.trim();
    if (baseDir) {
      localStorage.setItem('toolbox_novo_ticket_base_dir', baseDir);
      if (window.pywebview && window.pywebview.api && window.pywebview.api.set_base_dir) {
        try {
          await window.pywebview.api.set_base_dir(baseDir);
        } catch (e) {
          console.warn('Erro ao persistir base_dir:', e);
        }
      }
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

async function loadSavedBaseDir() {
  let saved = '';
  if (window.pywebview && window.pywebview.api && window.pywebview.api.get_config) {
    try {
      const res = await window.pywebview.api.get_config();
      if (res && res.success && res.config && res.config.base_dir) {
        saved = res.config.base_dir;
      }
    } catch (e) {
      console.warn('Erro ao carregar config do backend:', e);
    }
  }

  if (!saved) {
    saved = localStorage.getItem('toolbox_novo_ticket_base_dir') || '';
  }

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
    if (window.pywebview && window.pywebview.api && window.pywebview.api.get_quick_dates) {
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
      if (window.pywebview && window.pywebview.api && window.pywebview.api.set_base_dir) {
        await window.pywebview.api.set_base_dir(res);
      }
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
      if (window.pywebview && window.pywebview.api && window.pywebview.api.set_base_dir) {
        await window.pywebview.api.set_base_dir(baseDir);
      }
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

let isCopyingBadge = false;

function showToast(message, type = 'success') {
  const container = document.getElementById('toastContainer');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `<span data-icon="${type === 'success' ? 'check' : 'alert-circle'}"></span> <span>${message}</span>`;
  container.appendChild(toast);
  if (window.renderIcons) window.renderIcons();

  setTimeout(() => {
    toast.classList.add('toast-fadeout');
    setTimeout(() => {
      if (toast.parentNode) toast.parentNode.removeChild(toast);
    }, 250);
  }, 2500);
}

async function copyToClipboard(text, successLabel = 'Texto copiado!') {
  if (!text) return false;
  try {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(text);
    } else if (window.pywebview && window.pywebview.api && window.pywebview.api.copy_text) {
      await window.pywebview.api.copy_text(text);
    } else {
      const textarea = document.createElement('textarea');
      textarea.value = text;
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand('copy');
      document.body.removeChild(textarea);
    }
    showToast(successLabel, 'success');
    return true;
  } catch (err) {
    console.error('Erro ao copiar para clipboard:', err);
    showToast('Erro ao copiar para a área de transferência', 'danger');
    return false;
  }
}

async function handleCopyActiveTicketId() {
  if (!currentTicket || !currentTicket.name) return;
  const ticketId = currentTicket.name.trim();
  const badge = document.getElementById('activeTicketBadge');

  const copied = await copyToClipboard(ticketId, `Ticket copiado: ${ticketId}`);
  if (copied && badge && !isCopyingBadge) {
    isCopyingBadge = true;
    const originalText = `Ticket Ativo: ${ticketId}`;
    badge.className = 'badge badge-success badge-interactive';
    badge.innerHTML = `<span data-icon="check"></span> Copiado!`;
    if (window.renderIcons) window.renderIcons();

    setTimeout(() => {
      if (currentTicket && currentTicket.name === ticketId) {
        badge.className = 'badge badge-accent badge-interactive';
        badge.textContent = originalText;
      }
      isCopyingBadge = false;
    }, 1500);
  }
}

async function handleCopyActivePath() {
  if (!currentTicket || !currentTicket.path) return;
  await copyToClipboard(currentTicket.path, 'Caminho do ticket copiado!');
}

function setActiveTicket(ticket) {
  currentTicket = ticket;
  currentSubfolders = ticket.subfolders || [];
  currentTicketFiles = ticket.files || [];
  
  // Atualiza Badge do Header com Acessibilidade e Interatividade
  const badge = document.getElementById('activeTicketBadge');
  if (badge) {
    badge.textContent = `Ticket Ativo: ${ticket.name}`;
    badge.className = 'badge badge-accent badge-interactive';
    badge.setAttribute('role', 'button');
    badge.setAttribute('tabindex', '0');
    badge.setAttribute('title', `Clique para copiar o código do ticket (${ticket.name})`);
    badge.setAttribute('aria-label', `Copiar identificador do ticket ativo: ${ticket.name}`);
    badge.onclick = handleCopyActiveTicketId;
    badge.onkeydown = (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        handleCopyActiveTicketId();
      }
    };
  }

  // Atualiza Card de Ticket Ativo
  const cardActive = document.getElementById('cardActiveTicket');
  if (cardActive) cardActive.style.display = 'flex';
  
  const nameEl = document.getElementById('activeTicketName');
  if (nameEl) {
    nameEl.textContent = ticket.name;
    nameEl.style.cursor = 'pointer';
    nameEl.setAttribute('title', 'Clique para copiar o código do ticket');
    nameEl.onclick = handleCopyActiveTicketId;
  }
  
  const pathEl = document.getElementById('activeTicketPath');
  if (pathEl) {
    pathEl.textContent = ticket.path;
    pathEl.style.cursor = 'pointer';
    pathEl.setAttribute('title', 'Clique para copiar o caminho do ticket');
    pathEl.onclick = handleCopyActivePath;
  }

  // Atualiza contadores de arquivos
  updateFilesBadges(currentTicketFiles.length);

  renderSubfoldersTree();
  renderTicketFiles();
}

function updateFilesBadges(count) {
  const countEl = document.getElementById('activeFilesCount');
  if (countEl) countEl.textContent = count;

  const tabBadge = document.getElementById('tabFilesBadge');
  if (tabBadge) {
    tabBadge.textContent = count;
    tabBadge.style.display = count > 0 ? 'inline-block' : 'none';
  }
}

// ─────────────────────── Aba 2: Subpastas e Filtro de Logs ───────────────────────

function renderSubfoldersTree() {
  const container = document.getElementById('subfoldersTree');
  if (!container) return;
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

// ─────────────────────── Aba 3: Arquivos do Ticket ───────────────────────

function renderTicketFiles() {
  const container = document.getElementById('ticketFilesContainer');
  if (!container) return;
  if (!currentTicket) {
    container.innerHTML = `<div style="padding: 24px; text-align: center; color: var(--fg-muted);">Nenhum ticket ativo selecionado.</div>`;
    return;
  }

  const query = (document.getElementById('inputSearchFiles')?.value || '').toLowerCase().trim();
  const filtered = currentTicketFiles.filter(f => 
    f.name.toLowerCase().includes(query) || 
    f.relative_path.toLowerCase().includes(query) ||
    f.extension.toLowerCase().includes(query)
  );

  if (filtered.length === 0) {
    container.innerHTML = `<div style="padding: 24px; text-align: center; color: var(--fg-muted);">Nenhum arquivo encontrado ${query ? 'com o filtro aplicado' : 'na pasta do ticket'}.</div>`;
    return;
  }

  container.innerHTML = filtered.map(file => {
    let iconName = 'file';
    let iconClass = '';
    const ext = file.extension.toLowerCase();

    if (file.is_markdown) {
      iconName = 'file-text';
      iconClass = 'is-markdown';
    } else if (['.log', '.txt', '.out'].includes(ext)) {
      iconName = 'terminal';
      iconClass = 'is-log';
    } else if (['.json', '.sql', '.py', '.xml', '.csv', '.yaml', '.yml'].includes(ext)) {
      iconName = 'code';
      iconClass = 'is-code';
    }

    const isMd = file.is_markdown;
    const safeFullPath = file.full_path.replace(/\\/g, '\\\\').replace(/'/g, "\\'");

    return `
      <div class="file-row">
        <div class="file-row-left">
          <div class="file-icon-box ${iconClass}">
            <span data-icon="${iconName}"></span>
          </div>
          <div class="file-info">
            <div class="file-name" onclick="handleOpenTicketFile('${safeFullPath}')" title="Clique para abrir">
              ${file.name}
            </div>
            <div class="file-path" title="${file.full_path}">
              ${file.relative_path}
            </div>
          </div>
        </div>
        <div class="file-meta">
          <span class="badge badge-muted" style="font-family: monospace;">${file.size_formatted}</span>
          <span style="font-size: 11px; color: var(--fg-muted);">${file.modified_at}</span>
        </div>
        <div class="file-actions">
          ${isMd ? `
            <button class="btn-icon btn-icon-accent" onclick="handleOpenTicketFile('${safeFullPath}')" title="Abrir no Visualizador de Markdown">
              <span data-icon="file-text"></span> Visualizar
            </button>
          ` : `
            <button class="btn-icon" onclick="handleOpenTicketFile('${safeFullPath}')" title="Abrir arquivo">
              <span data-icon="eye"></span> Abrir
            </button>
          `}
          <button class="btn-icon" onclick="handleCopyFilePath('${safeFullPath}', this)" title="Copiar caminho completo">
            <span data-icon="copy"></span>
          </button>
          <button class="btn-icon" onclick="handleOpenTicketFileLocation('${safeFullPath}')" title="Abrir pasta no Explorer">
            <span data-icon="external"></span>
          </button>
        </div>
      </div>
    `;
  }).join('');

  if (window.renderIcons) window.renderIcons();
}

function handleSearchFiles() {
  renderTicketFiles();
}

async function reloadTicketFiles() {
  if (!currentTicket) return;
  try {
    if (window.pywebview && window.pywebview.api && window.pywebview.api.list_ticket_files) {
      const res = await window.pywebview.api.list_ticket_files(currentTicket.path);
      if (res && res.success) {
        currentTicketFiles = res.files || [];
        updateFilesBadges(currentTicketFiles.length);
        renderTicketFiles();
      }
    }
  } catch (err) {
    console.error('Erro ao recarregar arquivos:', err);
  }
}

async function handleOpenTicketFile(filePath) {
  try {
    if (window.pywebview && window.pywebview.api && window.pywebview.api.open_ticket_file) {
      const res = await window.pywebview.api.open_ticket_file(filePath);
      if (res && !res.success && res.message) {
        alert(res.message);
      }
    }
  } catch (err) {
    console.error('Erro ao abrir arquivo:', err);
  }
}

async function handleCopyFilePath(filePath, btn) {
  try {
    if (window.pywebview && window.pywebview.api && window.pywebview.api.copy_text) {
      await window.pywebview.api.copy_text(filePath);
    } else if (navigator.clipboard) {
      await navigator.clipboard.writeText(filePath);
    }
    if (btn) {
      const orig = btn.innerHTML;
      btn.innerHTML = `<span data-icon="check" style="color:var(--success);"></span>`;
      if (window.renderIcons) window.renderIcons();
      setTimeout(() => {
        btn.innerHTML = orig;
        if (window.renderIcons) window.renderIcons();
      }, 1200);
    }
  } catch (err) {
    console.error('Erro ao copiar caminho:', err);
  }
}

async function handleOpenTicketFileLocation(filePath) {
  try {
    if (window.pywebview && window.pywebview.api && window.pywebview.api.open_path) {
      await window.pywebview.api.open_path(filePath);
    }
  } catch (err) {
    console.error('Erro ao abrir localização no explorer:', err);
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
      await reloadTicketFiles();
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

