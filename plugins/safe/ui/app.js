/**
 * Toolbox Safe Plugin — Frontend Logic (app.js)
 */

let currentAuthMode = 'hybrid';
let activeCategory = 'all';
let cachedSecrets = [];
let autoLockInterval = null;
let currentSecretBeingViewed = null;

let appInitialized = false;

// ============================================================================
// Inicialização
// ============================================================================

window.addEventListener('DOMContentLoaded', () => {
  if (window.lucide) {
    window.lucide.createIcons();
  }
  
  // Aguarda pywebview ficar pronto
  if (window.pywebview && window.pywebview.api) {
    initApp();
  } else {
    window.addEventListener('pywebviewready', initApp);
    // Fallback após 500ms para ambientes de desenvolvimento / preview
    setTimeout(initApp, 500);
  }
});

async function callApi(method, ...args) {
  if (window.pywebview && window.pywebview.api && window.pywebview.api[method]) {
    try {
      return await window.pywebview.api[method](...args);
    } catch (e) {
      console.error(`Erro ao chamar ${method}:`, e);
      return { success: false, message: e.toString() };
    }
  }
  console.warn(`pywebview.api.${method} indisponível (modo mock/preview).`);
  return { success: false, message: 'API indisponível' };
}

async function initApp() {
  if (appInitialized) return;

  const statusRes = await callApi('get_vault_status');
  if (statusRes && statusRes.success) {
    appInitialized = true;
    const data = statusRes.data;
    if (!data.configured) {
      showScreen('screen-setup');
    } else if (data.status === 'LOCKED') {
      showScreen('screen-unlock');
      setupUnlockScreen(data);
    } else {
      showScreen('screen-vault');
      loadVaultData();
      startAutoLockTimer(data.auto_lock_remaining);
    }
  } else {
    if (window.pywebview && window.pywebview.api) {
      appInitialized = true;
      showScreen('screen-setup');
    }
  }
}

function showScreen(screenId) {
  document.querySelectorAll('.app-screen').forEach(s => {
    s.classList.remove('active');
    s.style.display = 'none';
  });
  const target = document.getElementById(screenId);
  if (target) {
    target.classList.add('active');
    target.style.display = (screenId === 'screen-loading') ? 'flex' : 'block';
  }
  if (window.lucide) window.lucide.createIcons();
}

// ============================================================================
// Tela de Setup
// ============================================================================

function selectAuthMode(mode, element) {
  currentAuthMode = mode;
  document.querySelectorAll('.mode-card').forEach(c => c.classList.remove('selected'));
  element.classList.add('selected');
  const radio = element.querySelector('input[type="radio"]');
  if (radio) radio.checked = true;

  const pwdGroup = document.getElementById('setup-password-group');
  if (mode === 'windows_hello') {
    pwdGroup.style.opacity = '0.5';
  } else {
    pwdGroup.style.opacity = '1';
  }
}

async function handleSetupSubmit() {
  const password = document.getElementById('setup-password').value;
  const timeout = parseInt(document.getElementById('setup-timeout').value, 10);
  const btn = document.getElementById('btn-save-setup');

  if (currentAuthMode !== 'windows_hello' && (!password || password.length < 4)) {
    alert('Por favor, defina uma Senha Mestre de no mínimo 4 caracteres.');
    return;
  }

  btn.disabled = true;
  btn.innerText = 'Inicializando Cofre...';

  const res = await callApi('setup_vault', currentAuthMode, password, currentAuthMode !== 'master_password', timeout);
  btn.disabled = false;
  btn.innerText = 'Criar e Inicializar Cofre';

  if (res && res.success) {
    showScreen('screen-vault');
    loadVaultData();
    startAutoLockTimer(timeout);
  } else {
    alert(res.message || 'Falha ao inicializar o cofre.');
  }
}

// ============================================================================
// Tela de Desbloqueio
// ============================================================================

function setupUnlockScreen(data) {
  const btnHello = document.getElementById('btn-unlock-hello');
  if (data.auth_mode === 'master_password' || !data.windows_hello_available) {
    btnHello.style.display = 'none';
  } else {
    btnHello.style.display = 'flex';
  }
  document.getElementById('unlock-password').value = '';
  document.getElementById('unlock-error').classList.add('hidden');
}

async function handleUnlockHello() {
  const btnHello = document.getElementById('btn-unlock-hello');
  const errBanner = document.getElementById('unlock-error');
  errBanner.classList.add('hidden');

  btnHello.disabled = true;
  const originalHtml = btnHello.innerHTML;
  btnHello.innerHTML = '<i data-lucide="loader" class="spin"></i> Aguardando Windows Hello...';
  if (window.lucide) window.lucide.createIcons();

  try {
    const res = await callApi('unlock_vault', null, true, 'Desbloquear Cofre Seguro Toolbox');
    if (res && res.success) {
      showScreen('screen-vault');
      loadVaultData();
      const statusRes = await callApi('get_vault_status');
      if (statusRes && statusRes.success) {
        startAutoLockTimer(statusRes.data.auto_lock_remaining);
      }
    } else {
      errBanner.innerText = res.message || 'Falha ao autenticar com Windows Hello.';
      errBanner.classList.remove('hidden');
      showScreen('screen-unlock');
    }
  } catch (err) {
    errBanner.innerText = String(err);
    errBanner.classList.remove('hidden');
    showScreen('screen-unlock');
  } finally {
    btnHello.disabled = false;
    btnHello.innerHTML = originalHtml;
    if (window.lucide) window.lucide.createIcons();
  }
}

async function handleUnlockPassword() {
  const pwdInput = document.getElementById('unlock-password');
  const password = pwdInput.value;
  const errBanner = document.getElementById('unlock-error');
  errBanner.classList.add('hidden');

  if (!password) {
    errBanner.innerText = 'Digite sua Senha Mestre.';
    errBanner.classList.remove('hidden');
    return;
  }

  const res = await callApi('unlock_vault', password, false);
  if (res && res.success) {
    showScreen('screen-vault');
    loadVaultData();
    const statusRes = await callApi('get_vault_status');
    if (statusRes.success) {
      startAutoLockTimer(statusRes.data.auto_lock_remaining);
    }
  } else {
    errBanner.innerText = res.message || 'Senha incorreta.';
    errBanner.classList.remove('hidden');
  }
}

async function handleLockVault() {
  await callApi('lock_vault');
  if (autoLockInterval) clearInterval(autoLockInterval);
  const statusRes = await callApi('get_vault_status');
  showScreen('screen-unlock');
  if (statusRes.success) setupUnlockScreen(statusRes.data);
}

// ============================================================================
// Temporizador de Auto-Lock
// ============================================================================

function startAutoLockTimer(remainingSeconds) {
  if (autoLockInterval) clearInterval(autoLockInterval);
  let timeLeft = remainingSeconds;

  const updateDisplay = () => {
    if (timeLeft <= 0) {
      document.getElementById('autolock-countdown').innerText = '00:00';
      handleLockVault();
      return;
    }
    const mins = Math.floor(timeLeft / 60);
    const secs = timeLeft % 60;
    document.getElementById('autolock-countdown').innerText = 
      `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    timeLeft--;
  };

  updateDisplay();
  autoLockInterval = setInterval(updateDisplay, 1000);
}

// ============================================================================
// Workspace & Gerenciador de Segredos
// ============================================================================

async function loadVaultData() {
  const res = await callApi('list_secrets', 'all');
  if (res && res.success) {
    cachedSecrets = res.data || [];
    updateCategoryCounts();
    renderSecretsGrid();
  }
}

function updateCategoryCounts() {
  const counts = { all: cachedSecrets.length, password: 0, api_key: 0, token: 0, certificate: 0, note: 0 };
  cachedSecrets.forEach(s => {
    if (counts[s.category] !== undefined) {
      counts[s.category]++;
    }
  });

  for (const cat in counts) {
    const el = document.getElementById(`count-${cat}`);
    if (el) el.innerText = counts[cat];
  }
}

function selectCategory(cat, element) {
  activeCategory = cat;
  document.querySelectorAll('.category-item').forEach(c => c.classList.remove('active'));
  element.classList.add('active');
  renderSecretsGrid();
}

function handleSearch(query) {
  renderSecretsGrid(query);
}

function renderSecretsGrid(searchQuery = '') {
  const grid = document.getElementById('secrets-grid');
  const emptyState = document.getElementById('empty-state');
  grid.innerHTML = '';

  const q = searchQuery.toLowerCase().trim();
  const filtered = cachedSecrets.filter(s => {
    const matchesCat = activeCategory === 'all' || s.category === activeCategory;
    const matchesSearch = !q || 
      (s.title && s.title.toLowerCase().includes(q)) || 
      (s.username_or_key && s.username_or_key.toLowerCase().includes(q)) ||
      (s.tags && s.tags.some(t => t.toLowerCase().includes(q)));
    return matchesCat && matchesSearch;
  });

  if (filtered.length === 0) {
    grid.classList.add('hidden');
    emptyState.classList.remove('hidden');
    if (window.lucide) window.lucide.createIcons();
    return;
  }

  grid.classList.remove('hidden');
  emptyState.classList.add('hidden');

  filtered.forEach(secret => {
    const card = document.createElement('div');
    card.className = 'secret-card';

    const catLabels = {
      password: 'Senha',
      api_key: 'API Key',
      token: 'Token',
      certificate: 'Certificado',
      note: 'Nota Segura',
      general: 'Geral'
    };

    const catLabel = catLabels[secret.category] || 'Geral';
    const userDisplay = secret.username_or_key ? escapeHtml(secret.username_or_key) : '<span style="color:var(--fg-muted)">Sem login</span>';

    card.innerHTML = `
      <div class="card-top">
        <div class="card-title-group">
          <h4>${escapeHtml(secret.title)}</h4>
          <div class="card-user">${userDisplay}</div>
        </div>
        <span class="category-badge ${secret.category}">${catLabel}</span>
      </div>

      <div class="card-footer">
        <button class="btn btn-secondary btn-sm" onclick="viewSecretDetails('${secret.id}')">
          <i data-lucide="eye"></i> Ver Segredo
        </button>
        <div class="actions">
          <button class="btn-icon-sm" onclick="editSecret('${secret.id}')" title="Editar"><i data-lucide="edit-2"></i></button>
          <button class="btn-icon-sm" onclick="deleteSecretConfirm('${secret.id}')" title="Excluir"><i data-lucide="trash-2"></i></button>
        </div>
      </div>
    `;

    grid.appendChild(card);
  });

  if (window.lucide) window.lucide.createIcons();
}

// ============================================================================
// Modal Adicionar / Editar Segredo
// ============================================================================

function openAddSecretModal() {
  document.getElementById('modal-secret-title').innerText = 'Novo Registro Seguro';
  document.getElementById('secret-id').value = '';
  document.getElementById('secret-title-input').value = '';
  document.getElementById('secret-category-select').value = activeCategory !== 'all' ? activeCategory : 'password';
  document.getElementById('secret-username-input').value = '';
  document.getElementById('secret-payload-input').value = '';
  document.getElementById('secret-tags-input').value = '';
  document.getElementById('generator-panel').classList.add('hidden');
  openModal('modal-secret');
}

async function editSecret(entryId) {
  const res = await callApi('get_secret', entryId);
  if (!res || !res.success) {
    alert(res.message || 'Falha ao obter credencial para edição.');
    return;
  }
  const data = res.data;
  document.getElementById('modal-secret-title').innerText = 'Editar Registro Seguro';
  document.getElementById('secret-id').value = data.id;
  document.getElementById('secret-title-input').value = data.title;
  document.getElementById('secret-category-select').value = data.category;
  document.getElementById('secret-username-input').value = data.username_or_key || '';
  document.getElementById('secret-payload-input').value = typeof data.payload === 'object' ? JSON.stringify(data.payload, null, 2) : data.payload;
  document.getElementById('secret-tags-input').value = (data.tags || []).join(', ');
  document.getElementById('generator-panel').classList.add('hidden');

  closeModal('modal-view');
  openModal('modal-secret');
}

async function handleSaveSecret(event) {
  event.preventDefault();
  const entryId = document.getElementById('secret-id').value || null;
  const title = document.getElementById('secret-title-input').value;
  const category = document.getElementById('secret-category-select').value;
  const username = document.getElementById('secret-username-input').value;
  const payload = document.getElementById('secret-payload-input').value;
  const tagsRaw = document.getElementById('secret-tags-input').value;
  const tags = tagsRaw ? tagsRaw.split(',').map(t => t.trim()).filter(Boolean) : [];

  const res = await callApi('save_secret', title, payload, category, username, entryId, tags);
  if (res && res.success) {
    closeModal('modal-secret');
    loadVaultData();
  } else {
    alert(res.message || 'Falha ao salvar segredo criptografado.');
  }
}

async function deleteSecretConfirm(entryId) {
  if (confirm('Tem certeza que deseja excluir esta credencial permanentemente?')) {
    const res = await callApi('delete_secret', entryId);
    if (res && res.success) {
      loadVaultData();
    } else {
      alert(res.message || 'Erro ao excluir.');
    }
  }
}

// ============================================================================
// Modal Visualizar Segredo
// ============================================================================

async function viewSecretDetails(entryId) {
  const res = await callApi('get_secret', entryId);
  if (!res || !res.success) {
    alert(res.message || 'Falha ao decriptografar dados.');
    return;
  }
  const secret = res.data;
  currentSecretBeingViewed = secret;

  document.getElementById('view-title').innerText = secret.title;
  const badge = document.getElementById('view-category-badge');
  badge.className = `category-badge ${secret.category}`;
  badge.innerText = secret.category.toUpperCase();

  document.getElementById('view-created-at').innerText = `Atualizado em: ${secret.updated_at}`;
  document.getElementById('view-username').innerText = secret.username_or_key || '(Nenhum)';
  
  const payloadStr = typeof secret.payload === 'object' ? JSON.stringify(secret.payload, null, 2) : String(secret.payload);
  document.getElementById('view-payload-raw').value = payloadStr;
  
  // Reseta estado mascarado
  const payloadEl = document.getElementById('view-payload');
  payloadEl.classList.add('masked');
  payloadEl.innerText = '••••••••••••••••';
  document.getElementById('btn-toggle-secret-view').innerHTML = '<i data-lucide="eye"></i>';

  const tagsContainer = document.getElementById('view-tags-container');
  tagsContainer.innerHTML = '';
  (secret.tags || []).forEach(t => {
    const span = document.createElement('span');
    span.className = 'tag-badge';
    span.innerText = t;
    tagsContainer.appendChild(span);
  });

  document.getElementById('btn-edit-current-secret').onclick = () => editSecret(secret.id);

  openModal('modal-view');
  if (window.lucide) window.lucide.createIcons();
}

function toggleSecretMask() {
  const payloadEl = document.getElementById('view-payload');
  const raw = document.getElementById('view-payload-raw').value;
  const btn = document.getElementById('btn-toggle-secret-view');

  if (payloadEl.classList.contains('masked')) {
    payloadEl.classList.remove('masked');
    payloadEl.innerText = raw;
    btn.innerHTML = '<i data-lucide="eye-off"></i>';
  } else {
    payloadEl.classList.add('masked');
    payloadEl.innerText = '••••••••••••••••';
    btn.innerHTML = '<i data-lucide="eye"></i>';
  }
  if (window.lucide) window.lucide.createIcons();
}

async function copyField(elementId, btn) {
  let text = '';
  if (elementId === 'view-payload-raw') {
    text = document.getElementById('view-payload-raw').value;
  } else {
    text = document.getElementById(elementId).innerText;
  }

  await callApi('copy_secret_to_clipboard', text);
  
  // Feedback visual no botão
  const origHtml = btn.innerHTML;
  btn.innerHTML = '<i data-lucide="check" style="color:var(--success)"></i>';
  if (window.lucide) window.lucide.createIcons();
  setTimeout(() => {
    btn.innerHTML = origHtml;
    if (window.lucide) window.lucide.createIcons();
  }, 1500);
}

// ============================================================================
// Gerador de Senhas
// ============================================================================

function togglePasswordGenerator() {
  const p = document.getElementById('generator-panel');
  p.classList.toggle('hidden');
  if (!p.classList.contains('hidden')) {
    generateNewPassword();
  }
}

async function generateNewPassword() {
  const length = parseInt(document.getElementById('gen-length').value, 10);
  const upper = document.getElementById('gen-upper').checked;
  const lower = document.getElementById('gen-lower').checked;
  const digits = document.getElementById('gen-digits').checked;
  const symbols = document.getElementById('gen-symbols').checked;

  const res = await callApi('generate_password', length, upper, lower, digits, symbols);
  if (res && res.success) {
    document.getElementById('secret-payload-input').value = res.password;
  }
}

// ============================================================================
// Configurações e Modais Utilitários
// ============================================================================

function openModal(modalId) {
  document.getElementById(modalId).classList.remove('hidden');
  if (modalId === 'modal-grants') {
    loadGrantsList();
  }
  if (window.lucide) window.lucide.createIcons();
}

function closeModal(modalId) {
  document.getElementById(modalId).classList.add('hidden');
}

async function loadGrantsList() {
  const res = await callApi('list_plugin_grants');
  const container = document.getElementById('grants-list');
  container.innerHTML = '';
  if (res && res.success && res.data && res.data.length > 0) {
    res.data.forEach(g => {
      const item = document.createElement('div');
      item.className = 'grant-item';
      item.innerHTML = `
        <div class="grant-info">
          <strong>Plugin: ${escapeHtml(g.plugin_id)}</strong>
          <span>Segredo: ${escapeHtml(g.entry_title || g.entry_id)} (${g.access_level})</span>
        </div>
        <button class="btn btn-danger btn-sm" onclick="handleRevokeGrant('${g.id}')">Revogar</button>
      `;
      container.appendChild(item);
    });
  } else {
    container.innerHTML = '<p class="subtitle" style="text-align:center;padding:20px;">Nenhum plugin externo com permissões concedidas.</p>';
  }
}

async function handleRevokeGrant(grantId) {
  await callApi('revoke_plugin_access', grantId);
  loadGrantsList();
}

async function handleSaveSettings() {
  const timeout = parseInt(document.getElementById('settings-timeout').value, 10);
  await callApi('update_settings', timeout);
  closeModal('modal-settings');
  startAutoLockTimer(timeout);
}

function togglePasswordVisibility(inputId, btn) {
  const input = document.getElementById(inputId);
  if (input.type === 'password') {
    input.type = 'text';
    btn.innerHTML = '<i data-lucide="eye-off"></i>';
  } else {
    input.type = 'password';
    btn.innerHTML = '<i data-lucide="eye"></i>';
  }
  if (window.lucide) window.lucide.createIcons();
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
