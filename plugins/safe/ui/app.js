/**
 * Toolbox Safe Plugin — Frontend Logic (app.js)
 */

let appInitialized = false;
let initTimeoutTimer = null;
let currentAuthMode = 'hybrid';
let activeCategory = 'all';
let cachedSecrets = [];
let autoLockInterval = null;
let currentSecretBeingViewed = null;

let configuredAutoLockTimeout = 300;
let lastActivityTimestamp = Date.now();
let lastBackendTouchTimestamp = 0;
let activityTrackerInitialized = false;

// ============================================================================
// Tratamento Global de Erros de Frontend (Logs & Diagnóstico)
// ============================================================================

window.addEventListener('error', (event) => {
  const errMsg = event.message || (event.error && event.error.message) || 'Erro não identificado no frontend';
  const stack = event.error && event.error.stack ? event.error.stack : '';
  console.error('[SafeUI] Erro capturado:', errMsg, stack);
  callApi('log_frontend_error', errMsg, stack);
});

window.addEventListener('unhandledrejection', (event) => {
  const reason = event.reason;
  const errMsg = reason instanceof Error ? reason.message : String(reason);
  const stack = reason instanceof Error ? reason.stack : '';
  console.error('[SafeUI] Promise rejeitada não tratada:', errMsg, stack);
  callApi('log_frontend_error', `UnhandledRejection: ${errMsg}`, stack);
});

// ============================================================================
// Inicialização
// ============================================================================

window.addEventListener('DOMContentLoaded', () => {
  if (window.lucide) {
    window.lucide.createIcons();
  }
  setupActivityTracker();

  // Aguarda pywebview ficar pronto
  if (window.pywebview && window.pywebview.api) {
    initApp();
  } else {
    window.addEventListener('pywebviewready', initApp);
    // Fallback após 500ms para ambientes de desenvolvimento / preview
    setTimeout(initApp, 500);
  }
});

function registerUserActivity() {
  lastActivityTimestamp = Date.now();
  if (configuredAutoLockTimeout > 0) {
    const now = Date.now();
    if (now - lastBackendTouchTimestamp > 3000) {
      lastBackendTouchTimestamp = now;
      callApi('touch_activity');
    }
  }
}

async function checkLockStatus() {
  const statusRes = await callApi('get_vault_status');
  if (statusRes && statusRes.success) {
    const data = statusRes.data;
    if (data.status === 'LOCKED') {
      const vaultScreen = document.getElementById('screen-vault');
      if (vaultScreen && vaultScreen.classList.contains('active')) {
        window.onVaultLockedBySystem();
      }
    }
  }
}

window.onVaultLockedBySystem = function() {
  console.log('[SafeUI] Cofre bloqueado pelo sistema/backend.');
  cachedSecrets = [];
  currentSecretBeingViewed = null;
  if (autoLockInterval) {
    clearInterval(autoLockInterval);
    autoLockInterval = null;
  }
  
  // Limpa elementos do DOM
  const container = document.getElementById('secrets-list');
  if (container) container.innerHTML = '';
  const searchInput = document.getElementById('search-input');
  if (searchInput) searchInput.value = '';

  // Transiciona para a tela de desbloqueio
  showScreen('screen-unlock');
  callApi('get_vault_status').then(statusRes => {
    if (statusRes && statusRes.success) {
      setupUnlockScreen(statusRes.data);
    }
  });
};

function setupActivityTracker() {
  if (activityTrackerInitialized) return;
  activityTrackerInitialized = true;

  const events = [
    'mousemove', 'mousedown', 'mouseup', 'click', 'dblclick',
    'keydown', 'keyup', 'keypress',
    'wheel', 'scroll',
    'touchstart', 'touchmove', 'touchend',
    'pointerdown', 'pointermove', 'pointerup',
    'input', 'change', 'focus'
  ];

  events.forEach(evt => {
    window.addEventListener(evt, registerUserActivity, { capture: true, passive: true });
    document.addEventListener(evt, registerUserActivity, { capture: true, passive: true });
  });

  window.addEventListener('focus', () => {
    registerUserActivity();
    checkLockStatus();
  });

  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') {
      registerUserActivity();
      checkLockStatus();
    }
  });
}

async function callApi(method, ...args) {
  if (method !== 'touch_activity') {
    lastActivityTimestamp = Date.now();
  }
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

function showInitError(message) {
  const spinnerContainer = document.getElementById('loading-spinner-container');
  const errorContainer = document.getElementById('loading-error-container');
  const errorMsgEl = document.getElementById('loading-error-message');

  if (spinnerContainer) spinnerContainer.style.display = 'none';
  if (errorContainer) {
    errorContainer.classList.remove('hidden');
    errorContainer.style.display = 'flex';
  }
  if (errorMsgEl) {
    errorMsgEl.innerText = message || 'Falha ao inicializar o serviço do Cofre Seguro.';
  }
  if (window.lucide) window.lucide.createIcons();
}

function resetInitState() {
  const spinnerContainer = document.getElementById('loading-spinner-container');
  const errorContainer = document.getElementById('loading-error-container');

  if (spinnerContainer) spinnerContainer.style.display = 'flex';
  if (errorContainer) {
    errorContainer.classList.add('hidden');
    errorContainer.style.display = 'none';
  }
  if (window.lucide) window.lucide.createIcons();
}

function retryAppInit() {
  appInitialized = false;
  resetInitState();
  initApp();
}

async function initApp() {
  if (appInitialized) return;

  if (initTimeoutTimer) {
    clearTimeout(initTimeoutTimer);
  }

  // Timeout de segurança de 5 segundos para evitar loop de carregamento infinito
  initTimeoutTimer = setTimeout(() => {
    if (!appInitialized) {
      console.warn('[SafeUI] Timeout de inicialização (5s) atingido.');
      callApi('log_frontend_error', 'Timeout de inicialização do frontend atingido (5 segundos).');
      showInitError('Tempo limite de inicialização excedido. O serviço do Cofre não respondeu a tempo.');
    }
  }, 5000);

  try {
    const statusRes = await callApi('get_vault_status');
    if (initTimeoutTimer) clearTimeout(initTimeoutTimer);

    if (statusRes && statusRes.success) {
      appInitialized = true;
      const data = statusRes.data;
      if (!data.configured) {
        showScreen('screen-setup');
        setupSetupScreen(data);
      } else if (data.status === 'LOCKED') {
        showScreen('screen-unlock');
        setupUnlockScreen(data);
      } else {
        showScreen('screen-vault');
        loadVaultData();
        startAutoLockTimer(data.auto_lock_timeout, data.auto_lock_remaining);
        checkPasswordMigrationBanner(data);
      }
    } else {
      if (window.pywebview && window.pywebview.api) {
        const err = (statusRes && statusRes.message) || 'Erro desconhecido ao carregar status do cofre.';
        console.error('[SafeUI] Falha ao obter status do cofre:', err);
        callApi('log_frontend_error', `Falha ao obter status: ${err}`);
        showInitError(`Erro ao carregar dados do cofre: ${err}`);
      } else {
        // Modo preview / mock sem pywebview
        appInitialized = true;
        showScreen('screen-setup');
      }
    }
  } catch (err) {
    if (initTimeoutTimer) clearTimeout(initTimeoutTimer);
    console.error('[SafeUI] Exceção durante initApp:', err);
    callApi('log_frontend_error', `Exceção em initApp: ${err.message || err}`, err.stack);
    showInitError(`Exceção durante a inicialização: ${err.message || err}`);
  }
}

function checkPasswordMigrationBanner(data) {
  const banner = document.getElementById('banner-password-migration');
  if (banner) {
    if (data && data.needs_password_migration) {
      banner.classList.remove('hidden');
    } else {
      banner.classList.add('hidden');
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

function setupSetupScreen(data) {
  const helloAvailable = Boolean(data && data.windows_hello_available);
  const helloOpt = document.getElementById('setup-hello-option');
  const helloCheckbox = document.getElementById('setup-enable-hello');

  if (helloOpt) {
    if (!helloAvailable) {
      helloOpt.style.opacity = '0.5';
      helloOpt.style.pointerEvents = 'none';
      if (helloCheckbox) helloCheckbox.checked = false;
    } else {
      helloOpt.style.opacity = '1';
      helloOpt.style.pointerEvents = 'auto';
      if (helloCheckbox) helloCheckbox.checked = true;
    }
  }
}

async function handleSetupSubmit() {
  const pwd = document.getElementById('setup-password').value;
  const pwdConfirm = document.getElementById('setup-password-confirm').value;
  const timeout = parseInt(document.getElementById('setup-timeout').value, 10);
  const lockOnOs = document.getElementById('setup-lock-on-os').checked;
  const enableHello = document.getElementById('setup-enable-hello') ? document.getElementById('setup-enable-hello').checked : false;
  const errBox = document.getElementById('setup-error');
  const btn = document.getElementById('btn-save-setup');

  errBox.classList.add('hidden');

  if (!pwd || pwd.length < 4) {
    errBox.innerText = 'A Senha Mestre é obrigatória e deve ter no mínimo 4 caracteres.';
    errBox.classList.remove('hidden');
    return;
  }

  if (pwd !== pwdConfirm) {
    errBox.innerText = 'A confirmação de senha não confere com a Senha Mestre digitada.';
    errBox.classList.remove('hidden');
    return;
  }

  btn.disabled = true;
  btn.innerHTML = '<i data-lucide="loader" class="spin"></i> Inicializando Cofre...';
  if (window.lucide) window.lucide.createIcons();

  const authMode = enableHello ? 'hybrid' : 'master_password';
  const res = await callApi('setup_vault', authMode, pwd, enableHello, timeout, lockOnOs);
  btn.disabled = false;
  btn.innerHTML = '<i data-lucide="lock"></i> Criar e Inicializar Cofre';
  if (window.lucide) window.lucide.createIcons();

  if (res && res.success) {
    showScreen('screen-vault');
    loadVaultData();
    startAutoLockTimer(timeout);
  } else {
    errBox.innerText = res.message || 'Falha ao inicializar o cofre.';
    errBox.classList.remove('hidden');
  }
}

// ============================================================================
// Tela de Desbloqueio
// ============================================================================

function setupUnlockScreen(data) {
  const btnHello = document.getElementById('btn-unlock-hello');
  const pwdGroup = document.getElementById('unlock-password-group');
  const divider = document.getElementById('unlock-divider');
  const errBanner = document.getElementById('unlock-error');

  errBanner.classList.add('hidden');
  document.getElementById('unlock-password').value = '';

  const helloAvailable = Boolean(data && data.windows_hello_available);
  const authMode = (data && data.auth_mode) || 'hybrid';

  if (authMode === 'windows_hello') {
    btnHello.style.display = helloAvailable ? 'flex' : 'none';
    if (divider) divider.style.display = 'none';
    if (pwdGroup) pwdGroup.style.display = 'none';
    if (!helloAvailable) {
      errBanner.innerText = 'Este cofre está protegido por Windows Hello, mas a autenticação biométrica/PIN não está acessível.';
      errBanner.classList.remove('hidden');
    }
  } else if (authMode === 'master_password' || !helloAvailable) {
    btnHello.style.display = 'none';
    if (divider) divider.style.display = 'none';
    if (pwdGroup) pwdGroup.style.display = 'block';
  } else {
    btnHello.style.display = 'flex';
    if (divider) divider.style.display = 'flex';
    if (pwdGroup) pwdGroup.style.display = 'block';
  }

  if (window.lucide) window.lucide.createIcons();
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
        startAutoLockTimer(statusRes.data.auto_lock_timeout, statusRes.data.auto_lock_remaining);
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
      startAutoLockTimer(statusRes.data.auto_lock_timeout, statusRes.data.auto_lock_remaining);
    }
  } else {
    errBanner.innerText = res.message || 'Senha incorreta.';
    errBanner.classList.remove('hidden');
  }
}

async function handleLockVault() {
  await callApi('lock_vault');
  if (autoLockInterval) {
    clearInterval(autoLockInterval);
    autoLockInterval = null;
  }
  const statusRes = await callApi('get_vault_status');
  showScreen('screen-unlock');
  if (statusRes.success) setupUnlockScreen(statusRes.data);
}

// ============================================================================
// Temporizador de Auto-Lock
// ============================================================================

function startAutoLockTimer(timeoutSeconds, initialRemaining) {
  if (autoLockInterval) {
    clearInterval(autoLockInterval);
    autoLockInterval = null;
  }

  configuredAutoLockTimeout = (timeoutSeconds !== undefined && timeoutSeconds !== null) ? parseInt(timeoutSeconds, 10) : 300;

  if (configuredAutoLockTimeout <= 0) {
    const el = document.getElementById('autolock-countdown');
    if (el) el.innerText = '∞';
    return;
  }

  if (initialRemaining !== undefined && initialRemaining !== null && initialRemaining > 0 && initialRemaining < configuredAutoLockTimeout) {
    lastActivityTimestamp = Date.now() - (configuredAutoLockTimeout - initialRemaining) * 1000;
  } else {
    lastActivityTimestamp = Date.now();
  }

  const updateDisplay = () => {
    const el = document.getElementById('autolock-countdown');
    if (!el) return;

    if (configuredAutoLockTimeout <= 0) {
      el.innerText = '∞';
      return;
    }

    const elapsedSeconds = Math.floor((Date.now() - lastActivityTimestamp) / 1000);
    const remainingSeconds = configuredAutoLockTimeout - elapsedSeconds;

    if (remainingSeconds <= 0) {
      el.innerText = '00:00';
      if (autoLockInterval) {
        clearInterval(autoLockInterval);
        autoLockInterval = null;
      }
      handleLockVault();
      return;
    }

    const mins = Math.floor(remainingSeconds / 60);
    const secs = remainingSeconds % 60;
    el.innerText = `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
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

async function openSettingsModal() {
  const statusRes = await callApi('get_vault_status');
  if (statusRes && statusRes.success) {
    const data = statusRes.data;
    document.getElementById('settings-timeout').value = String(data.auto_lock_timeout ?? 300);
    document.getElementById('settings-lock-on-os').checked = (data.lock_on_os_lock !== false);
    
    const authStatus = document.getElementById('settings-auth-status');
    const pwdBtnLabel = document.getElementById('settings-btn-pwd-label');
    if (data.needs_password_migration) {
      if (authStatus) authStatus.innerText = 'Autenticação: Windows Hello Apenas (Sem Senha)';
      if (pwdBtnLabel) pwdBtnLabel.innerText = 'Cadastrar Senha Mestre';
    } else {
      if (authStatus) authStatus.innerText = `Autenticação: ${data.auth_mode === 'hybrid' ? 'Híbrida (Windows Hello + Senha)' : 'Senha Mestre'}`;
      if (pwdBtnLabel) pwdBtnLabel.innerText = 'Alterar Senha Mestre';
    }
  }
  openModal('modal-settings');
}

async function handleSaveSettings() {
  const timeout = parseInt(document.getElementById('settings-timeout').value, 10);
  const lockOnOs = document.getElementById('settings-lock-on-os').checked;
  const res = await callApi('update_security_settings', timeout, lockOnOs);
  if (res && res.success) {
    configuredAutoLockTimeout = timeout;
    closeModal('modal-settings');
    startAutoLockTimer(timeout);
  } else {
    alert(res.message || 'Erro ao salvar configurações.');
  }
}

// ============================================================================
// Cadastro / Alteração de Senha Mestre
// ============================================================================

function openSetPasswordModal() {
  closeModal('modal-settings');
  document.getElementById('new-master-pwd').value = '';
  document.getElementById('new-master-pwd-confirm').value = '';
  const errBox = document.getElementById('set-pwd-error');
  if (errBox) errBox.classList.add('hidden');
  openModal('modal-set-password');
}

async function handleSetMasterPasswordSubmit() {
  const pwd = document.getElementById('new-master-pwd').value;
  const pwdConfirm = document.getElementById('new-master-pwd-confirm').value;
  const errBox = document.getElementById('set-pwd-error');

  errBox.classList.add('hidden');

  if (!pwd || pwd.length < 4) {
    errBox.innerText = 'A Senha Mestre deve ter pelo menos 4 caracteres.';
    errBox.classList.remove('hidden');
    return;
  }

  if (pwd !== pwdConfirm) {
    errBox.innerText = 'A confirmação não confere com a Senha Mestre informada.';
    errBox.classList.remove('hidden');
    return;
  }

  const res = await callApi('set_master_password', pwd);
  if (res && res.success) {
    closeModal('modal-set-password');
    const banner = document.getElementById('banner-password-migration');
    if (banner) banner.classList.add('hidden');
    alert('Senha Mestre configurada com sucesso!');
  } else {
    errBox.innerText = res.message || 'Falha ao definir a Senha Mestre.';
    errBox.classList.remove('hidden');
  }
}

// ============================================================================
// Importação & Exportação de Segredos (Save in Cloud / Backup)
// ============================================================================

// ============================================================================
// Importação de Credenciais (Microsoft Safe / Backup)
// ============================================================================

let pendingImportData = null;
let pendingImportFilePath = null;

function openImportModal() {
  const rawInput = document.getElementById('import-raw-text');
  if (rawInput) rawInput.value = '';
  
  const fileLabel = document.getElementById('import-selected-file-label');
  if (fileLabel) fileLabel.innerText = 'Nenhum arquivo selecionado';
  
  const previewBox = document.getElementById('import-preview-box');
  if (previewBox) previewBox.classList.add('hidden');
  
  const statusMsg = document.getElementById('import-status-msg');
  if (statusMsg) {
    statusMsg.className = 'hidden';
    statusMsg.innerText = '';
  }
  
  pendingImportData = null;
  pendingImportFilePath = null;
  openModal('modal-import');
}

function renderImportPreview(data) {
  const previewBox = document.getElementById('import-preview-box');
  const badgesContainer = document.getElementById('import-preview-badges');
  const listContainer = document.getElementById('import-preview-list');

  if (!data || !data.success || data.total_detected === 0) {
    previewBox.classList.add('hidden');
    return;
  }

  const formatLabels = {
    'xml': 'Microsoft Safe XML',
    'csv': 'Planilha CSV',
    'txt': 'Texto Simples TXT',
    'json': 'JSON / Backup'
  };
  const fmtLabel = formatLabels[data.format] || (data.format ? data.format.toUpperCase() : 'Desconhecido');

  badgesContainer.innerHTML = `
    <span class="badge" style="background: var(--accent); color: white;">${fmtLabel}</span>
    <span class="badge" style="background: var(--bg-elev-1); color: var(--fg); border: 1px solid var(--border);">${data.total_detected} itens</span>
    ${data.conflicts_count > 0 ? `<span class="badge" style="background: rgba(245, 158, 11, 0.2); color: var(--warning);">⚠️ ${data.conflicts_count} existentes</span>` : ''}
  `;

  let listHtml = '';
  if (data.preview_items && data.preview_items.length > 0) {
    data.preview_items.forEach(it => {
      listHtml += `
        <div style="padding: 6px 10px; border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center;">
          <div>
            <strong style="color: var(--fg);">${escapeHtml(it.title)}</strong>
            ${it.username ? `<span style="color: var(--fg-muted); margin-left: 6px;">(${escapeHtml(it.username)})</span>` : ''}
          </div>
          <div style="display: flex; gap: 6px; align-items: center;">
            <span style="font-size: 10px; padding: 2px 6px; border-radius: 4px; background: var(--bg-elev-2); color: var(--fg-muted);">${escapeHtml(it.category)}</span>
            ${it.conflict ? '<span style="font-size: 10px; color: var(--warning);" title="Item já existe no cofre">⚠️ Já existe</span>' : ''}
          </div>
        </div>
      `;
    });
    if (data.total_detected > data.preview_items.length) {
      listHtml += `<div style="padding: 6px 10px; text-align: center; color: var(--fg-muted); font-size: 11px;">+ ${data.total_detected - data.preview_items.length} outros itens...</div>`;
    }
  } else {
    listHtml = '<div style="padding: 10px; text-align: center; color: var(--fg-muted);">Nenhum item válido identificado.</div>';
  }

  listContainer.innerHTML = listHtml;
  previewBox.classList.remove('hidden');
  if (window.lucide) window.lucide.createIcons();
}

async function handleSelectImportFile() {
  const statusMsg = document.getElementById('import-status-msg');
  statusMsg.className = 'hidden';
  
  const res = await callApi('select_file_for_import');
  if (res && res.success) {
    pendingImportFilePath = res.file_path;
    pendingImportData = null;
    document.getElementById('import-selected-file-label').innerText = res.file_name || 'Arquivo selecionado';
    renderImportPreview(res);
  } else if (res && res.message && res.message !== 'Nenhum arquivo selecionado.') {
    statusMsg.style.background = 'rgba(248, 113, 113, 0.15)';
    statusMsg.style.color = 'var(--danger)';
    statusMsg.innerText = res.message;
    statusMsg.classList.remove('hidden');
  }
}

async function handlePreviewPastedText() {
  const text = document.getElementById('import-raw-text').value;
  const statusMsg = document.getElementById('import-status-msg');
  statusMsg.className = 'hidden';

  if (!text || !text.trim()) {
    statusMsg.style.background = 'rgba(248, 113, 113, 0.15)';
    statusMsg.style.color = 'var(--danger)';
    statusMsg.innerText = 'Cole o conteúdo em texto (XML, CSV, TXT ou JSON) para analisar.';
    statusMsg.classList.remove('hidden');
    return;
  }

  const res = await callApi('preview_import_data', text);
  if (res && res.success) {
    pendingImportData = text;
    pendingImportFilePath = null;
    document.getElementById('import-selected-file-label').innerText = 'Texto colado';
    renderImportPreview(res);
  } else {
    statusMsg.style.background = 'rgba(248, 113, 113, 0.15)';
    statusMsg.style.color = 'var(--danger)';
    statusMsg.innerText = res.message || 'Não foi possível reconhecer a estrutura do texto.';
    statusMsg.classList.remove('hidden');
  }
}

async function handleConfirmImport() {
  const statusMsg = document.getElementById('import-status-msg');
  const policy = document.getElementById('import-conflict-policy').value;
  const btn = document.getElementById('btn-confirm-import');

  let res = null;
  btn.disabled = true;
  btn.innerHTML = '<i data-lucide="loader" class="spin"></i> Importando...';

  try {
    if (pendingImportFilePath) {
      res = await callApi('import_secrets_from_file_path', pendingImportFilePath, policy);
    } else {
      const textToUse = pendingImportData || document.getElementById('import-raw-text').value;
      if (!textToUse || !textToUse.trim()) {
        statusMsg.style.background = 'rgba(248, 113, 113, 0.15)';
        statusMsg.style.color = 'var(--danger)';
        statusMsg.innerText = 'Selecione um arquivo ou cole os dados antes de importar.';
        statusMsg.classList.remove('hidden');
        return;
      }
      res = await callApi('import_secrets', textToUse, policy);
    }

    if (res && res.success) {
      statusMsg.style.background = 'rgba(74, 222, 128, 0.15)';
      statusMsg.style.color = 'var(--success)';
      statusMsg.innerText = res.message || `${res.imported} registros importados com sucesso!`;
      statusMsg.classList.remove('hidden');
      loadVaultData();
    } else {
      statusMsg.style.background = 'rgba(248, 113, 113, 0.15)';
      statusMsg.style.color = 'var(--danger)';
      statusMsg.innerText = res.message || 'Erro ao importar credenciais.';
      statusMsg.classList.remove('hidden');
    }
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<i data-lucide="upload"></i> Importar Credenciais';
    if (window.lucide) window.lucide.createIcons();
  }
}

async function handleExportSecrets() {
  const res = await callApi('export_secrets');
  if (res && res.success && res.data) {
    const jsonStr = JSON.stringify(res.data, null, 2);
    await callApi('copy_secret_to_clipboard', jsonStr);
    alert(`${res.data.length} credenciais exportadas e copiadas para a área de transferência em formato JSON!`);
  } else {
    alert(res.message || 'Falha ao exportar credenciais.');
  }
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

