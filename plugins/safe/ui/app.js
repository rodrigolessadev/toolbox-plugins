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
// Bridge da API (pywebview / Toolbox Container)
// ============================================================================

let isAuthenticating = false;
let lastUnlockTimestamp = 0;

function isApiReady(api) {
  return Boolean(
    api &&
    typeof api === 'object' &&
    typeof api.get_vault_status === 'function'
  );
}

function getApiObject() {
  if (window.pywebview && window.pywebview.api && isApiReady(window.pywebview.api)) {
    return window.pywebview.api;
  }
  if (window.toolbox && window.toolbox.api && isApiReady(window.toolbox.api)) {
    return window.toolbox.api;
  }
  if (window.toolbox && isApiReady(window.toolbox)) {
    return window.toolbox;
  }
  if (window.api && isApiReady(window.api)) {
    return window.api;
  }
  return null;
}

let apiWaitPromise = null;

function waitForApi(timeoutMs = 10000, pollIntervalMs = 50) {
  const currentApi = getApiObject();
  if (currentApi) {
    return Promise.resolve(currentApi);
  }

  if (apiWaitPromise) {
    return apiWaitPromise;
  }

  apiWaitPromise = new Promise((resolve) => {
    let resolved = false;

    const timeoutTimer = setTimeout(() => {
      if (!resolved) {
        resolved = true;
        cleanup();
        const fallbackApi = getApiObject();
        if (!fallbackApi) {
          console.warn(`[SafeUI] waitForApi: timeout atingido (${timeoutMs}ms) sem injeção completa da API.`);
        }
        resolve(fallbackApi);
      }
    }, timeoutMs);

    function checkReady() {
      const api = getApiObject();
      if (!resolved && api) {
        resolved = true;
        cleanup();
        resolve(api);
      }
    }

    function onPywebviewReady() {
      checkReady();
    }

    function cleanup() {
      clearTimeout(timeoutTimer);
      clearInterval(pollTimer);
      window.removeEventListener('pywebviewready', onPywebviewReady);
      apiWaitPromise = null;
    }

    window.addEventListener('pywebviewready', onPywebviewReady);
    const pollTimer = setInterval(checkReady, pollIntervalMs);
    checkReady();
  });

  return apiWaitPromise;
}

// ============================================================================
// Inicialização
// ============================================================================

window.addEventListener('DOMContentLoaded', () => {
  if (window.lucide) {
    window.lucide.createIcons();
  }
  setupActivityTracker();
  initApp();
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
  // Ignora verificação enquanto a autenticação está ativa ou nos primeiros 3 segundos após desbloquear
  if (isAuthenticating || (Date.now() - lastUnlockTimestamp < 3000)) {
    return;
  }

  const vaultScreen = document.getElementById('screen-vault');
  if (!vaultScreen || !vaultScreen.classList.contains('active')) {
    return;
  }

  const statusRes = await callApi('get_vault_status');
  if (statusRes && statusRes.success) {
    const data = statusRes.data;
    if (data.status === 'LOCKED') {
      if (vaultScreen && vaultScreen.classList.contains('active') && !isAuthenticating && (Date.now() - lastUnlockTimestamp >= 3000)) {
        window.onVaultLockedBySystem();
      }
    }
  }
}

window.onVaultLockedBySystem = function() {
  if (isAuthenticating || (Date.now() - lastUnlockTimestamp < 3000)) {
    return;
  }
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

  let api = getApiObject();
  if (!api || typeof api[method] !== 'function') {
    api = await waitForApi(4000);
  }

  // Polling rápido se o método específico ainda não foi anexado
  if (api && typeof api[method] !== 'function') {
    const startWait = Date.now();
    while (Date.now() - startWait < 2500) {
      await new Promise(r => setTimeout(r, 50));
      api = getApiObject();
      if (api && typeof api[method] === 'function') break;
    }
  }

  if (api && typeof api[method] === 'function') {
    try {
      return await api[method](...args);
    } catch (e) {
      console.error(`[SafeUI] Erro ao chamar ${method}:`, e);
      return { success: false, message: e.toString() };
    }
  }

  console.warn(`[SafeUI] pywebview/toolbox API.${method} indisponível.`);
  return { success: false, message: `Não existe API disponível para '${method}'. Verifique se o Toolbox Desktop está em execução.` };
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

  resetInitState();

  if (initTimeoutTimer) {
    clearTimeout(initTimeoutTimer);
  }

  // Timeout de segurança para feedback visual caso o bridge trave completamente
  initTimeoutTimer = setTimeout(() => {
    if (!appInitialized) {
      console.warn('[SafeUI] Timeout global de inicialização atingido (10s).');
      callApi('log_frontend_error', 'Timeout global de inicialização atingido (10s).');
      showInitError('Tempo limite de inicialização excedido. O serviço do Cofre não respondeu a tempo.');
    }
  }, 10000);

  try {
    const api = await waitForApi(10000);
    if (!api) {
      if (initTimeoutTimer) clearTimeout(initTimeoutTimer);
      console.error('[SafeUI] Falha no bootstrap: Bridge não foi injetado após 10s.');
      showInitError('A API do Toolbox não está disponível ou demorou para inicializar. Verifique se o aplicativo principal está em execução.');
      return;
    }

    let statusRes = null;
    let attempts = 0;
    while (attempts < 3) {
      attempts++;
      statusRes = await callApi('get_vault_status');
      if (statusRes && statusRes.success) break;
      if (attempts < 3) {
        await new Promise(r => setTimeout(r, attempts * 200));
      }
    }
    if (initTimeoutTimer) clearTimeout(initTimeoutTimer);

    if (statusRes && statusRes.success) {
      appInitialized = true;
      const data = statusRes.data;

      // Atualiza o título da janela/documento com a versão dinâmica
      if (data.window_title) {
        document.title = data.window_title;
      } else if (data.plugin_version) {
        document.title = `Cofre - v${data.plugin_version}`;
      }

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
      const err = (statusRes && statusRes.message) || 'Erro desconhecido ao carregar status do cofre.';
      console.error('[SafeUI] Falha ao obter status do cofre:', err);
      callApi('log_frontend_error', `Falha ao obter status: ${err}`);
      showInitError(`Erro ao carregar dados do cofre: ${err}`);
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

  // Consulta assíncrona em background para refinar status sem travar renderização inicial
  if (authMode !== 'master_password') {
    callApi('check_windows_hello_availability').then((res) => {
      if (res && res.success && res.available !== undefined) {
        if (!res.available && authMode === 'windows_hello') {
          btnHello.style.display = 'none';
          errBanner.innerText = 'Este cofre está protegido por Windows Hello, mas a autenticação biométrica/PIN não está acessível.';
          errBanner.classList.remove('hidden');
        } else if (!res.available) {
          btnHello.style.display = 'none';
          if (divider) divider.style.display = 'none';
        }
      }
    });
  }
}

async function handleUnlockHello() {
  const btnHello = document.getElementById('btn-unlock-hello');
  const errBanner = document.getElementById('unlock-error');
  errBanner.classList.add('hidden');

  btnHello.disabled = true;
  const originalHtml = btnHello.innerHTML;
  btnHello.innerHTML = '<i data-lucide="loader" class="spin"></i> Aguardando Windows Hello...';
  if (window.lucide) window.lucide.createIcons();

  isAuthenticating = true;

  try {
    const res = await callApi('unlock_vault', null, true, 'Desbloquear Cofre Seguro Toolbox');
    if (res && res.success) {
      lastUnlockTimestamp = Date.now();
      lastActivityTimestamp = Date.now();
      lastBackendTouchTimestamp = Date.now();

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
    setTimeout(() => {
      isAuthenticating = false;
    }, 1500);
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

  isAuthenticating = true;

  try {
    const res = await callApi('unlock_vault', password, false);
    if (res && res.success) {
      lastUnlockTimestamp = Date.now();
      lastActivityTimestamp = Date.now();
      lastBackendTouchTimestamp = Date.now();

      showScreen('screen-vault');
      loadVaultData();
      const statusRes = await callApi('get_vault_status');
      if (statusRes && statusRes.success) {
        startAutoLockTimer(statusRes.data.auto_lock_timeout, statusRes.data.auto_lock_remaining);
      }
    } else {
      errBanner.innerText = res.message || 'Senha incorreta.';
      errBanner.classList.remove('hidden');
    }
  } catch (err) {
    errBanner.innerText = String(err);
    errBanner.classList.remove('hidden');
  } finally {
    setTimeout(() => {
      isAuthenticating = false;
    }, 1000);
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
// Workspace & Gerenciador de Segredos (Unificado com KeePassXC)
// ============================================================================

let currentSourceFilter = 'all';
let cachedKpxcEntries = [];

async function loadVaultData(searchQuery = '') {
  const res = await callApi('list_secrets', 'all');
  if (res && res.success) {
    cachedSecrets = res.data || [];
    updateCategoryCounts();
  }

  // Se KeePassXC estiver conectado e desbloqueado, carrega entradas para exibição unificada
  await checkKeePassXCStatus();
  if (kpxcStatusCache && kpxcStatusCache.connected && kpxcStatusCache.unlocked) {
    try {
      const kpxcRes = await callApi('search_keepassxc_entries', searchQuery || '');
      if (kpxcRes && kpxcRes.success) {
        cachedKpxcEntries = kpxcRes.data || [];
      } else {
        cachedKpxcEntries = [];
      }
    } catch (e) {
      cachedKpxcEntries = [];
    }
  } else {
    cachedKpxcEntries = [];
  }

  updateUnifiedStatusText();
  renderSecretsGrid(searchQuery);
}

function setSourceFilter(filter) {
  currentSourceFilter = filter;
  document.querySelectorAll('#sourceFilterGroup .pill-btn').forEach(btn => {
    btn.classList.toggle('active', btn.id === `filter-src-${filter}`);
  });
  renderSecretsGrid(document.getElementById('search-input')?.value || '');
}

function updateUnifiedStatusText() {
  const el = document.getElementById('unified-status-text');
  if (!el) return;
  if (kpxcStatusCache && kpxcStatusCache.connected && kpxcStatusCache.unlocked) {
    el.innerHTML = `<span style="color: #10b981; font-weight: 500;">● KeePassXC Conectado</span> (${cachedKpxcEntries.length} entradas)`;
  } else {
    el.innerHTML = `<span style="color: var(--fg-muted);">KeePassXC offline</span>`;
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
  if (element) element.classList.add('active');

  const grid = document.getElementById('secrets-grid');
  const emptyState = document.getElementById('empty-state');
  const kpxcPanel = document.getElementById('keepassxc-hub-panel');
  const kdbxPanel = document.getElementById('kdbx-sources-panel');
  const sourceFilterToolbar = document.getElementById('sourceFilterGroup');

  if (cat === 'keepassxc') {
    if (grid) grid.classList.add('hidden');
    if (emptyState) emptyState.classList.add('hidden');
    if (kdbxPanel) { kdbxPanel.classList.add('hidden'); kdbxPanel.style.display = 'none'; }
    if (sourceFilterToolbar) sourceFilterToolbar.style.display = 'none';
    if (kpxcPanel) {
      kpxcPanel.classList.remove('hidden');
      kpxcPanel.style.display = 'flex';
    }
    checkKeePassXCStatus();
  } else if (cat === 'kdbx') {
    if (grid) grid.classList.add('hidden');
    if (emptyState) emptyState.classList.add('hidden');
    if (kpxcPanel) { kpxcPanel.classList.add('hidden'); kpxcPanel.style.display = 'none'; }
    if (sourceFilterToolbar) sourceFilterToolbar.style.display = 'none';
    if (kdbxPanel) {
      kdbxPanel.classList.remove('hidden');
      kdbxPanel.style.display = 'flex';
    }
    loadKdbxSources();
  } else {
    if (kpxcPanel) {
      kpxcPanel.classList.add('hidden');
      kpxcPanel.style.display = 'none';
    }
    if (kdbxPanel) {
      kdbxPanel.classList.add('hidden');
      kdbxPanel.style.display = 'none';
    }
    if (sourceFilterToolbar) sourceFilterToolbar.style.display = 'flex';
    renderSecretsGrid(document.getElementById('search-input')?.value || '');
  }
}

// ============================================================================
// Hub KeePassXC — Funções Frontend
// ============================================================================

let kpxcStatusCache = null;

async function checkKeePassXCStatus(manual = false) {
  const dot = document.getElementById('kpxc-status-dot');
  const title = document.getElementById('kpxc-status-title');
  const desc = document.getElementById('kpxc-status-desc');
  const badge = document.getElementById('count-keepassxc');
  const btnLock = document.getElementById('btn-lock-kpxc');
  const btnAssociate = document.getElementById('btn-associate-kpxc');
  const helpBanner = document.getElementById('kpxc-help-banner');

  if (manual && title) {
    title.innerText = 'Verificando KeePassXC...';
  }

  try {
    const res = await callApi('get_keepassxc_status');
    if (res && res.success && res.data) {
      kpxcStatusCache = res.data;
      const data = res.data;

      if (data.connected && data.unlocked) {
        if (dot) dot.style.background = 'var(--success, #10b981)';
        if (title) title.innerText = '🟢 Conectado ao KeePassXC (Cofre Aberto)';
        if (desc) desc.innerText = `Sessão ativa e associada. ID: ${data.client_id || 'Toolbox'}`;
        if (badge) { badge.innerText = '🟢'; badge.style.color = '#10b981'; }
        if (btnLock) btnLock.style.display = 'inline-flex';
        if (btnAssociate) btnAssociate.innerText = 'Reassociar com KeePassXC';
        if (helpBanner) helpBanner.style.display = 'none';
      } else if (data.connected && !data.unlocked) {
        if (dot) dot.style.background = 'var(--warning, #f59e0b)';
        if (title) title.innerText = '🟡 KeePassXC Aberto (Cofre Bloqueado)';
        if (desc) desc.innerText = 'Desbloqueie seu cofre no aplicativo KeePassXC para acessar credenciais.';
        if (badge) { badge.innerText = '🟡'; badge.style.color = '#f59e0b'; }
        if (btnLock) btnLock.style.display = 'none';
        if (btnAssociate) btnAssociate.innerText = 'Parear com KeePassXC';
        if (helpBanner) helpBanner.style.display = 'none';
      } else {
        if (dot) dot.style.background = 'var(--danger, #ef4444)';
        if (title) title.innerText = '🔴 KeePassXC Não Detectado';
        if (desc) desc.innerText = 'Abra o KeePassXC com a opção "Integração com o navegador" ativada.';
        if (badge) { badge.innerText = '🔴'; badge.style.color = '#ef4444'; }
        if (btnLock) btnLock.style.display = 'none';
        if (btnAssociate) btnAssociate.innerText = 'Parear com KeePassXC';
        if (helpBanner) helpBanner.style.display = 'block';
      }
    } else {
      if (dot) dot.style.background = '#888';
      if (title) title.innerText = '⚪ KeePassXC Indisponível';
      if (badge) { badge.innerText = '⚪'; badge.style.color = '#888'; }
    }
  } catch (err) {
    console.error('Erro ao verificar KeePassXC:', err);
  }
  updateUnifiedStatusText();
  if (window.lucide) window.lucide.createIcons();
}

async function handleAssociateKeePassXC() {
  showToast('Iniciando pareamento com KeePassXC...', 'info');
  try {
    const res = await callApi('associate_keepassxc', 'Toolbox Safe');
    if (res && res.success) {
      showToast(res.message || 'Associação concluída com sucesso!', 'success');
      await checkKeePassXCStatus();
      await loadVaultData();
    } else {
      showToast(res.message || 'Falha ao parear com KeePassXC. Verifique se autorizou a solicitação na janela do KeePassXC.', 'error');
    }
  } catch (err) {
    showToast(`Erro ao parear: ${err}`, 'error');
  }
}

async function handleLockKeePassXC() {
  try {
    const res = await callApi('lock_keepassxc_database');
    if (res && res.success) {
      showToast('Cofre do KeePassXC bloqueado.', 'info');
      await checkKeePassXCStatus();
      await loadVaultData();
    } else {
      showToast(res.message || 'Não foi possível bloquear o KeePassXC.', 'warning');
    }
  } catch (err) {
    showToast(`Erro ao bloquear cofre: ${err}`, 'error');
  }
}

async function handleGenerateKeePassXCPassword() {
  try {
    const res = await callApi('generate_keepassxc_password');
    if (res && res.success && res.password) {
      await callApi('copy_secret_to_clipboard', res.password, 30);
      showToast('Senha forte gerada pelo KeePassXC e copiada para a área de transferência!', 'success');
    } else {
      showToast('Não foi possível gerar senha no KeePassXC.', 'warning');
    }
  } catch (err) {
    showToast(`Erro ao gerar senha: ${err}`, 'error');
  }
}

async function handleSearchKeePassXC() {
  const input = document.getElementById('kpxc-search-input');
  const resultsContainer = document.getElementById('kpxc-results-container');
  const query = input ? input.value.trim() : '';

  if (resultsContainer) {
    resultsContainer.innerHTML = '<div style="text-align:center; padding: 20px; color: var(--fg-secondary);"><i data-lucide="loader" class="spin"></i> Consultando cofre do KeePassXC...</div>';
    if (window.lucide) window.lucide.createIcons();
  }

  try {
    const res = await callApi('search_keepassxc_entries', query);
    if (res && res.success) {
      const entries = res.data || [];
      if (entries.length === 0) {
        resultsContainer.innerHTML = `
          <div style="text-align:center; padding: 24px; color: var(--fg-muted); font-size: 13px;">
            Nenhuma entrada encontrada no KeePassXC para "<strong>${escapeHtml(query)}</strong>".
          </div>
        `;
      } else {
        resultsContainer.innerHTML = entries.map(e => `
          <div class="kpxc-entry-card" style="background: var(--bg-elev); border: 1px solid var(--border); border-radius: var(--radius-sm); padding: 12px 16px; display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap;">
            <div>
              <strong style="color: var(--fg-primary); font-size: 14px; display: block;">${escapeHtml(e.name || 'Sem Título')}</strong>
              <span style="color: var(--fg-secondary); font-size: 12px;">Login: <code>${escapeHtml(e.login || '(sem login)')}</code></span>
            </div>
            <div style="display: flex; gap: 8px; flex-wrap: wrap;">
              ${e.login ? `<button type="button" class="btn btn-secondary btn-sm" onclick="copyKeePassXCText('${escapeJs(e.login)}', 'Usuário')"><i data-lucide="user"></i> Copiar Login</button>` : ''}
              ${e.password ? `<button type="button" class="btn btn-primary btn-sm" onclick="copyKeePassXCText('${escapeJs(e.password)}', 'Senha')"><i data-lucide="key"></i> Copiar Senha</button>` : ''}
              ${e.uuid ? `<button type="button" class="btn btn-secondary btn-sm" onclick="fetchAndCopyKeePassXCTotp('${escapeJs(e.uuid)}')"><i data-lucide="clock"></i> TOTP</button>` : ''}
              <button type="button" class="btn btn-secondary btn-sm" onclick="handleImportKeePassXCEntryString('${escapeJs(JSON.stringify(e))}')" title="Salvar no Cofre Central do Toolbox">
                <i data-lucide="download"></i> Salvar no Cofre
              </button>
            </div>
          </div>
        `).join('');
      }
    } else {
      resultsContainer.innerHTML = `<div style="text-align:center; padding: 24px; color: var(--danger); font-size: 13px;">${escapeHtml(res.message || 'Erro ao consultar KeePassXC.')}</div>`;
    }
  } catch (err) {
    resultsContainer.innerHTML = `<div style="text-align:center; padding: 24px; color: var(--danger); font-size: 13px;">Erro: ${escapeHtml(String(err))}</div>`;
  }
  if (window.lucide) window.lucide.createIcons();
}

function escapeJs(str) {
  if (!str) return '';
  return String(str).replace(/\\/g, '\\\\').replace(/'/g, "\\'").replace(/"/g, '\\"');
}

async function copyKeePassXCText(text, label) {
  await callApi('copy_secret_to_clipboard', text, 15);
  showToast(`${label} copiado! (Higienização em 15s)`, 'success');
}

async function fetchAndCopyKeePassXCTotp(uuid) {
  try {
    const res = await callApi('get_keepassxc_totp', uuid);
    if (res && res.success && res.totp) {
      await callApi('copy_secret_to_clipboard', res.totp, 30);
      showToast(`Código TOTP (${res.totp}) copiado!`, 'success');
    } else {
      showToast('Entrada não possui token TOTP configurado.', 'warning');
    }
  } catch (err) {
    showToast(`Erro ao obter TOTP: ${err}`, 'error');
  }
}

async function handleImportKeePassXCEntryString(entryJsonStr) {
  try {
    const entry = JSON.parse(entryJsonStr);
    const res = await callApi('import_keepassxc_entry_to_vault', entry);
    if (res && res.success) {
      showToast('Credencial salva no Cofre Central com sucesso!', 'success');
      await loadVaultData(document.getElementById('search-input')?.value || '');
    } else {
      showToast(res.message || 'Erro ao importar credencial.', 'error');
    }
  } catch (err) {
    showToast(`Erro ao importar credencial: ${err}`, 'error');
  }
}

async function handleSearch(query) {
  const q = (query || '').trim();
  if (kpxcStatusCache && kpxcStatusCache.connected && kpxcStatusCache.unlocked && (currentSourceFilter === 'all' || currentSourceFilter === 'keepassxc')) {
    try {
      const kpxcRes = await callApi('search_keepassxc_entries', q);
      if (kpxcRes && kpxcRes.success) {
        cachedKpxcEntries = kpxcRes.data || [];
      }
    } catch (e) {
      // Ignora erro
    }
  }
  updateUnifiedStatusText();
  renderSecretsGrid(q);
}

function renderSecretsGrid(searchQuery = '') {
  const grid = document.getElementById('secrets-grid');
  const emptyState = document.getElementById('empty-state');
  grid.innerHTML = '';

  const q = (searchQuery || '').toLowerCase().trim();

  let filteredLocals = [];
  if (currentSourceFilter === 'all' || currentSourceFilter === 'local') {
    filteredLocals = cachedSecrets.filter(s => {
      const matchesCat = activeCategory === 'all' || s.category === activeCategory;
      const matchesSearch = !q || 
        (s.title && s.title.toLowerCase().includes(q)) || 
        (s.username_or_key && s.username_or_key.toLowerCase().includes(q)) ||
        (s.tags && s.tags.some(t => t.toLowerCase().includes(q)));
      return matchesCat && matchesSearch;
    }).map(s => ({ ...s, _isLocal: true }));
  }

  let filteredKpxc = [];
  if ((currentSourceFilter === 'all' || currentSourceFilter === 'keepassxc') && (activeCategory === 'all' || activeCategory === 'password')) {
    filteredKpxc = cachedKpxcEntries.filter(e => {
      const name = (e.name || '').toLowerCase();
      const login = (e.login || '').toLowerCase();
      const uuid = (e.uuid || '').toLowerCase();
      return !q || name.includes(q) || login.includes(q) || uuid.includes(q);
    }).map(e => ({
      id: `kpxc_${e.uuid || e.name}`,
      title: e.name || 'Sem Título',
      username_or_key: e.login || '',
      category: 'password',
      _isLocal: false,
      rawEntry: e
    }));
  }

  const combined = [...filteredLocals, ...filteredKpxc];

  if (combined.length === 0) {
    grid.classList.add('hidden');
    emptyState.classList.remove('hidden');
    if (window.lucide) window.lucide.createIcons();
    return;
  }

  grid.classList.remove('hidden');
  emptyState.classList.add('hidden');

  combined.forEach(item => {
    const card = document.createElement('div');
    card.className = 'secret-card';

    if (item._isLocal) {
      const catLabels = {
        password: 'Senha',
        api_key: 'API Key',
        token: 'Token',
        certificate: 'Certificado',
        note: 'Nota Segura',
        general: 'Geral'
      };
      const catLabel = catLabels[item.category] || 'Geral';
      const userDisplay = item.username_or_key ? escapeHtml(item.username_or_key) : '<span style="color:var(--fg-muted)">Sem login</span>';

      card.innerHTML = `
        <div class="card-top">
          <div class="card-title-group">
            <h4>${escapeHtml(item.title)}</h4>
            <div class="card-user">${userDisplay}</div>
          </div>
          <div style="display: flex; gap: 4px; align-items: center;">
            <span class="badge-source badge-source-local">🔒 Local</span>
            <span class="category-badge ${item.category}">${catLabel}</span>
          </div>
        </div>

        <div class="card-footer">
          <button class="btn btn-secondary btn-sm" onclick="viewSecretDetails('${item.id}')">
            <i data-lucide="eye"></i> Ver Segredo
          </button>
          <div class="actions">
            <button class="btn-icon-sm" onclick="editSecret('${item.id}')" title="Editar"><i data-lucide="edit-2"></i></button>
            <button class="btn-icon-sm" onclick="deleteSecretConfirm('${item.id}')" title="Excluir"><i data-lucide="trash-2"></i></button>
          </div>
        </div>
      `;
    } else {
      // Card do KeePassXC
      const userDisplay = item.username_or_key ? `<code>${escapeHtml(item.username_or_key)}</code>` : '<span style="color:var(--fg-muted)">Sem login</span>';
      const entryJson = escapeJs(JSON.stringify(item.rawEntry));

      card.innerHTML = `
        <div class="card-top">
          <div class="card-title-group">
            <h4>${escapeHtml(item.title)}</h4>
            <div class="card-user">${userDisplay}</div>
          </div>
          <span class="badge-source badge-source-kpxc"><i data-lucide="shield-check"></i> KeePassXC</span>
        </div>

        <div class="card-footer" style="flex-wrap: wrap; gap: 6px;">
          <div style="display: flex; gap: 6px;">
            ${item.rawEntry.login ? `<button type="button" class="btn btn-secondary btn-sm" onclick="copyKeePassXCText('${escapeJs(item.rawEntry.login)}', 'Usuário')" title="Copiar Usuário"><i data-lucide="user"></i></button>` : ''}
            ${item.rawEntry.password ? `<button type="button" class="btn btn-primary btn-sm" onclick="copyKeePassXCText('${escapeJs(item.rawEntry.password)}', 'Senha')" title="Copiar Senha"><i data-lucide="key"></i></button>` : ''}
            ${item.rawEntry.uuid ? `<button type="button" class="btn btn-secondary btn-sm" onclick="fetchAndCopyKeePassXCTotp('${escapeJs(item.rawEntry.uuid)}')" title="Copiar Código TOTP"><i data-lucide="clock"></i> TOTP</button>` : ''}
          </div>
          <button type="button" class="btn btn-secondary btn-sm" onclick="handleImportKeePassXCEntryString('${entryJson}')" title="Salvar no Cofre Central do Toolbox">
            <i data-lucide="download"></i> Salvar no Cofre
          </button>
        </div>
      `;
    }

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
  const pwdContainer = document.getElementById('import-safepack-pwd-container');

  if (data.format === 'safepack_password_required') {
    if (pwdContainer) pwdContainer.classList.remove('hidden');
    badgesContainer.innerHTML = `<span class="badge" style="background:var(--accent); color:white;">🔒 SafePack Protegido</span>`;
    listContainer.innerHTML = '<div style="padding: 12px; text-align: center; color: var(--fg-muted);">Informe a senha do backup acima e clique em <strong>Descriptografar</strong> para visualizar os itens.</div>';
    previewBox.classList.remove('hidden');
    if (window.lucide) window.lucide.createIcons();
    return;
  }

  if (pwdContainer && data.format !== 'safepack') {
    pwdContainer.classList.add('hidden');
  }

  // Badges de cabeçalho
  let formatBadge = `<span class="badge" style="background:var(--bg-elev-1);">${escapeHtml((data.format || 'unknown').toUpperCase())}</span>`;
  if (data.format === 'safepack') {
    formatBadge = `<span class="badge" style="background:var(--success); color:white;">🔒 SafePack Descriptografado</span>`;
  }
  let totalBadge = `<span class="badge" style="background:rgba(59, 130, 246, 0.2); color:var(--accent);">${data.total_detected} itens</span>`;
  let conflictBadge = data.conflicts_count > 0 ? `<span class="badge" style="background:rgba(245, 158, 11, 0.2); color:var(--warning);">${data.conflicts_count} já existem</span>` : '';

  badgesContainer.innerHTML = `${formatBadge} ${totalBadge} ${conflictBadge}`;

  // Itens da lista
  let listHtml = '';
  if (data.preview_items && data.preview_items.length > 0) {
    data.preview_items.forEach(it => {
      listHtml += `
        <div style="display: flex; justify-content: space-between; align-items: center; padding: 6px 10px; border-bottom: 1px solid var(--border);">
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

async function handlePreviewWithPassword() {
  const statusMsg = document.getElementById('import-status-msg');
  statusMsg.className = 'hidden';
  const pwd = document.getElementById('import-backup-pwd').value;
  if (!pwd) {
    statusMsg.style.background = 'rgba(248, 113, 113, 0.15)';
    statusMsg.style.color = 'var(--danger)';
    statusMsg.innerText = 'Digite a senha do arquivo de backup.';
    statusMsg.classList.remove('hidden');
    return;
  }

  let res = null;
  if (pendingImportFilePath) {
    res = await callApi('preview_import_data', null, pendingImportFilePath, pwd);
  } else if (pendingImportData) {
    res = await callApi('preview_import_data', pendingImportData, null, pwd);
  }

  if (res && res.success) {
    renderImportPreview(res);
  } else {
    statusMsg.style.background = 'rgba(248, 113, 113, 0.15)';
    statusMsg.style.color = 'var(--danger)';
    statusMsg.innerText = res.message || 'Senha incorreta ou arquivo corrompido.';
    statusMsg.classList.remove('hidden');
  }
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
  const backupPwd = document.getElementById('import-backup-pwd').value || null;
  const btn = document.getElementById('btn-confirm-import');

  let res = null;
  btn.disabled = true;
  btn.innerHTML = '<i data-lucide="loader" class="spin"></i> Importando...';

  try {
    if (pendingImportFilePath) {
      res = await callApi('import_secrets_from_file_path', pendingImportFilePath, policy, backupPwd);
    } else {
      const textToUse = pendingImportData || document.getElementById('import-raw-text').value;
      if (!textToUse || !textToUse.trim()) {
        statusMsg.style.background = 'rgba(248, 113, 113, 0.15)';
        statusMsg.style.color = 'var(--danger)';
        statusMsg.innerText = 'Selecione um arquivo ou cole os dados antes de importar.';
        statusMsg.classList.remove('hidden');
        return;
      }
      res = await callApi('import_secrets', textToUse, policy, null, backupPwd);
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

function handleExportSecrets() {
  document.getElementById('export-status-msg').className = 'hidden';
  document.getElementById('export-backup-pwd').value = '';
  document.getElementById('export-backup-pwd-confirm').value = '';
  openModal('modal-export');
}

function toggleExportPasswordFields() {
  const isSafepack = document.querySelector('input[name="export-format"]:checked').value === 'safepack';
  const pwdBox = document.getElementById('export-safepack-pwd-container');
  if (pwdBox) {
    pwdBox.style.display = isSafepack ? 'block' : 'none';
  }
}

async function handleConfirmExport() {
  const format = document.querySelector('input[name="export-format"]:checked').value;
  const statusMsg = document.getElementById('export-status-msg');
  statusMsg.className = 'hidden';

  let pwd = null;
  if (format === 'safepack') {
    const pwd1 = document.getElementById('export-backup-pwd').value;
    const pwd2 = document.getElementById('export-backup-pwd-confirm').value;

    if (!pwd1 || pwd1.length < 4) {
      statusMsg.style.background = 'rgba(248, 113, 113, 0.15)';
      statusMsg.style.color = 'var(--danger)';
      statusMsg.innerText = 'A senha do arquivo de backup deve ter pelo menos 4 caracteres.';
      statusMsg.classList.remove('hidden');
      return;
    }
    if (pwd1 !== pwd2) {
      statusMsg.style.background = 'rgba(248, 113, 113, 0.15)';
      statusMsg.style.color = 'var(--danger)';
      statusMsg.innerText = 'As senhas informadas não coincidem.';
      statusMsg.classList.remove('hidden');
      return;
    }
    pwd = pwd1;
  }

  const res = await callApi('export_secrets_to_file', format, pwd);
  if (res && res.success) {
    statusMsg.style.background = 'rgba(74, 222, 128, 0.15)';
    statusMsg.style.color = 'var(--success)';
    statusMsg.innerText = res.message || 'Backup exportado com sucesso!';
    statusMsg.classList.remove('hidden');
    setTimeout(() => {
      closeModal('modal-export');
    }, 1200);
  } else if (res && res.message && res.message !== 'Exportação cancelada pelo usuário.') {
    statusMsg.style.background = 'rgba(248, 113, 113, 0.15)';
    statusMsg.style.color = 'var(--danger)';
    statusMsg.innerText = res.message || 'Falha ao exportar backup.';
    statusMsg.classList.remove('hidden');
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

// Exports globais para chamadas inline no HTML
window.setSourceFilter = setSourceFilter;
window.handleImportKeePassXCEntryString = handleImportKeePassXCEntryString;

// ============================================================================
// Fontes KeePass (.kdbx) Diretas & Headless (Issue #217)
// ============================================================================

let cachedKdbxSources = [];
let activeKdbxSource = null;
let cachedKdbxEntries = [];

async function loadKdbxSources() {
  const container = document.getElementById('kdbx-sources-list');
  const badgeCount = document.getElementById('count-kdbx');
  if (container) {
    container.innerHTML = '<div style="text-align: center; padding: 20px; color: var(--fg-muted); font-size: 13px;">Carregando fontes KeePass (.kdbx)...</div>';
  }

  try {
    const res = await callApi('list_kdbx_sources');
    if (res && res.success) {
      cachedKdbxSources = res.data || [];
      if (badgeCount) badgeCount.innerText = cachedKdbxSources.length;
      renderKdbxSourcesList();
    } else {
      if (container) container.innerHTML = '<div style="padding: 12px; color: var(--danger); text-align: center;">Erro ao carregar fontes KeePass.</div>';
    }
  } catch (e) {
    if (container) container.innerHTML = `<div style="padding: 12px; color: var(--danger); text-align: center;">Falha: ${escapeHtml(e.message)}</div>`;
  }
}

function renderKdbxSourcesList() {
  const container = document.getElementById('kdbx-sources-list');
  if (!container) return;

  if (cachedKdbxSources.length === 0) {
    container.innerHTML = `
      <div style="text-align: center; padding: 32px 16px; color: var(--fg-muted); background: var(--bg-elev); border-radius: var(--radius-sm); border: 1px dashed var(--border);">
        <i data-lucide="database" style="width: 32px; height: 32px; margin-bottom: 8px; opacity: 0.5;"></i>
        <div style="font-size: 14px; font-weight: 500; color: var(--fg);">Nenhuma base KeePass (.kdbx) cadastrada</div>
        <div style="font-size: 12px; margin-top: 4px;">Cadastre arquivos locais ou remotos via SSH para consultar e importar credenciais sem abrir o KeePassXC.</div>
        <button type="button" class="btn btn-primary btn-sm" onclick="openAddKdbxSourceModal()" style="margin-top: 14px;">
          <i data-lucide="plus"></i> Cadastrar Primeira Base
        </button>
      </div>
    `;
    if (window.lucide) window.lucide.createIcons();
    return;
  }

  let html = '';
  cachedKdbxSources.forEach(src => {
    const isSsh = src.source_type === 'ssh';
    const typeBadge = isSsh
      ? `<span class="badge" style="background: rgba(168, 85, 247, 0.2); color: #c084fc;">🌐 SSH/SFTP</span>`
      : `<span class="badge" style="background: rgba(59, 130, 246, 0.2); color: var(--accent);">📁 Local</span>`;

    const lastSync = src.last_sync_at ? new Date(src.last_sync_at).toLocaleString('pt-BR') : 'Nunca sincronizado';

    html += `
      <div style="display: flex; justify-content: space-between; align-items: center; padding: 14px 16px; background: var(--bg-elev); border: 1px solid var(--border); border-radius: var(--radius-sm); gap: 12px; flex-wrap: wrap;">
        <div style="flex: 1; min-width: 240px;">
          <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px;">
            <strong style="font-size: 14px; color: var(--fg);">${escapeHtml(src.name)}</strong>
            ${typeBadge}
          </div>
          <div style="font-size: 12px; color: var(--fg-secondary); word-break: break-all;">
            <code>${escapeHtml(src.file_path)}</code>
          </div>
          ${src.keyfile_path ? `<div style="font-size: 11px; color: var(--fg-muted); margin-top: 2px;"><i data-lucide="key" style="width: 12px; height: 12px; display: inline-block; vertical-align: middle;"></i> Keyfile: ${escapeHtml(src.keyfile_path)}</div>` : ''}
          <div style="font-size: 11px; color: var(--fg-muted); margin-top: 4px;">
            Último acesso: <span>${lastSync}</span>
          </div>
        </div>

        <div style="display: flex; gap: 6px; align-items: center; flex-wrap: wrap;">
          <button type="button" class="btn btn-primary btn-sm" onclick="handleOpenKdbxUnlockModal('${src.id}')">
            <i data-lucide="unlock"></i> Abrir & Navegar
          </button>
          ${isSsh ? `
            <button type="button" class="btn btn-secondary btn-sm" onclick="handleSyncKdbxSource('${src.id}')" title="Sincronizar via SSH">
              <i data-lucide="refresh-cw"></i> Sincronizar
            </button>
          ` : ''}
          <button type="button" class="btn btn-secondary btn-sm" onclick="openEditKdbxSourceModal('${src.id}')" title="Editar Fonte">
            <i data-lucide="edit-2"></i>
          </button>
          <button type="button" class="btn btn-danger btn-sm" onclick="handleDeleteKdbxSource('${src.id}', '${escapeHtml(src.name)}')" title="Excluir Fonte">
            <i data-lucide="trash-2"></i>
          </button>
        </div>
      </div>
    `;
  });

  container.innerHTML = html;
  if (window.lucide) window.lucide.createIcons();
}

function openAddKdbxSourceModal() {
  document.getElementById('kdbx-source-modal-title').innerHTML = '<i data-lucide="database" style="color: var(--accent);"></i> Cadastrar Fonte KeePass (.kdbx)';
  document.getElementById('kdbx-source-id').value = '';
  document.getElementById('kdbx-source-name').value = '';
  document.querySelector('input[name="kdbx-source-type"][value="local"]').checked = true;
  document.getElementById('kdbx-source-file-path').value = '';
  document.getElementById('kdbx-source-keyfile-path').value = '';
  document.getElementById('kdbx-ssh-host').value = '';
  document.getElementById('kdbx-ssh-port').value = '22';
  document.getElementById('kdbx-ssh-user').value = '';
  document.getElementById('kdbx-source-status-msg').className = 'hidden';
  toggleKdbxSourceTypeFields();
  openModal('modal-kdbx-source');
  if (window.lucide) window.lucide.createIcons();
}

function openEditKdbxSourceModal(sourceId) {
  const src = cachedKdbxSources.find(s => s.id === sourceId);
  if (!src) return;

  document.getElementById('kdbx-source-modal-title').innerHTML = '<i data-lucide="edit-2" style="color: var(--accent);"></i> Editar Fonte KeePass (.kdbx)';
  document.getElementById('kdbx-source-id').value = src.id;
  document.getElementById('kdbx-source-name').value = src.name || '';
  
  const typeRadio = document.querySelector(`input[name="kdbx-source-type"][value="${src.source_type || 'local'}"]`);
  if (typeRadio) typeRadio.checked = true;

  document.getElementById('kdbx-source-file-path').value = src.file_path || '';
  document.getElementById('kdbx-source-keyfile-path').value = src.keyfile_path || '';
  document.getElementById('kdbx-ssh-host').value = src.ssh_host || '';
  document.getElementById('kdbx-ssh-port').value = src.ssh_port || 22;
  document.getElementById('kdbx-ssh-user').value = src.ssh_user || '';
  document.getElementById('kdbx-source-status-msg').className = 'hidden';

  toggleKdbxSourceTypeFields();
  openModal('modal-kdbx-source');
  if (window.lucide) window.lucide.createIcons();
}

function toggleKdbxSourceTypeFields() {
  const isSsh = document.querySelector('input[name="kdbx-source-type"]:checked')?.value === 'ssh';
  const sshBox = document.getElementById('kdbx-ssh-fields');
  const pathLabel = document.getElementById('kdbx-file-path-label');
  const btnBrowse = document.getElementById('btn-browse-kdbx');

  if (isSsh) {
    if (sshBox) sshBox.classList.remove('hidden');
    if (pathLabel) pathLabel.innerText = 'Caminho Remoto do Arquivo .kdbx *';
    if (btnBrowse) btnBrowse.style.display = 'none';
  } else {
    if (sshBox) sshBox.classList.add('hidden');
    if (pathLabel) pathLabel.innerText = 'Caminho do Arquivo .kdbx *';
    if (btnBrowse) btnBrowse.style.display = 'inline-flex';
  }
}

async function handleBrowseKdbxFile() {
  const res = await callApi('select_kdbx_file');
  if (res && res.success && res.file_path) {
    document.getElementById('kdbx-source-file-path').value = res.file_path;
    const nameInput = document.getElementById('kdbx-source-name');
    if (!nameInput.value.trim() && res.file_name) {
      nameInput.value = res.file_name.replace(/\.[^/.]+$/, '');
    }
  }
}

async function handleBrowseKdbxKeyfile() {
  const res = await callApi('select_kdbx_keyfile');
  if (res && res.success && res.file_path) {
    document.getElementById('kdbx-source-keyfile-path').value = res.file_path;
  }
}

async function handleBrowseUnlockKeyfile() {
  const res = await callApi('select_kdbx_keyfile');
  if (res && res.success && res.file_path) {
    document.getElementById('kdbx-unlock-keyfile').value = res.file_path;
  }
}

async function handleSaveKdbxSource() {
  const sid = document.getElementById('kdbx-source-id').value.trim() || null;
  const name = document.getElementById('kdbx-source-name').value.trim();
  const sourceType = document.querySelector('input[name="kdbx-source-type"]:checked')?.value || 'local';
  const filePath = document.getElementById('kdbx-source-file-path').value.trim();
  const keyfilePath = document.getElementById('kdbx-source-keyfile-path').value.trim() || null;
  const sshHost = document.getElementById('kdbx-ssh-host').value.trim() || null;
  const sshPort = parseInt(document.getElementById('kdbx-ssh-port').value, 10) || 22;
  const sshUser = document.getElementById('kdbx-ssh-user').value.trim() || null;
  const statusMsg = document.getElementById('kdbx-source-status-msg');

  if (!name || !filePath) {
    statusMsg.style.background = 'rgba(248, 113, 113, 0.15)';
    statusMsg.style.color = 'var(--danger)';
    statusMsg.innerText = 'Preencha o nome amigável e o caminho do arquivo .kdbx.';
    statusMsg.classList.remove('hidden');
    return;
  }

  if (sourceType === 'ssh' && !sshHost) {
    statusMsg.style.background = 'rgba(248, 113, 113, 0.15)';
    statusMsg.style.color = 'var(--danger)';
    statusMsg.innerText = 'Para conexões SSH, informe o Host / Servidor.';
    statusMsg.classList.remove('hidden');
    return;
  }

  statusMsg.className = 'hidden';
  const res = await callApi('save_kdbx_source', name, filePath, sourceType, keyfilePath, sshHost, sshPort, sshUser, sid);

  if (res && res.success) {
    statusMsg.style.background = 'rgba(74, 222, 128, 0.15)';
    statusMsg.style.color = 'var(--success)';
    statusMsg.innerText = res.message || 'Fonte salva com sucesso!';
    statusMsg.classList.remove('hidden');
    setTimeout(() => {
      closeModal('modal-kdbx-source');
      loadKdbxSources();
    }, 800);
  } else {
    statusMsg.style.background = 'rgba(248, 113, 113, 0.15)';
    statusMsg.style.color = 'var(--danger)';
    statusMsg.innerText = res.message || 'Erro ao salvar fonte.';
    statusMsg.classList.remove('hidden');
  }
}

async function handleDeleteKdbxSource(sourceId, name) {
  if (!confirm(`Deseja realmente excluir a fonte KeePass "${name}"? Os registros já importados permanecerão no cofre.`)) {
    return;
  }
  const res = await callApi('delete_kdbx_source', sourceId);
  if (res && res.success) {
    showToast(`Fonte "${name}" removida.`);
    loadKdbxSources();
    if (activeKdbxSource && activeKdbxSource.id === sourceId) {
      closeKdbxExplorer();
    }
  } else {
    showToast(res.message || 'Erro ao excluir fonte.');
  }
}

function handleOpenKdbxUnlockModal(sourceId) {
  const src = cachedKdbxSources.find(s => s.id === sourceId);
  if (!src) return;

  document.getElementById('kdbx-unlock-source-id').value = src.id;
  document.getElementById('kdbx-unlock-desc').innerText = `Informe a senha mestra para abrir a base "${src.name}":`;
  document.getElementById('kdbx-unlock-password').value = '';
  document.getElementById('kdbx-unlock-keyfile').value = src.keyfile_path || '';
  document.getElementById('kdbx-unlock-status-msg').className = 'hidden';
  openModal('modal-kdbx-unlock');
  setTimeout(() => document.getElementById('kdbx-unlock-password')?.focus(), 150);
}

async function handleConfirmUnlockKdbx() {
  const sid = document.getElementById('kdbx-unlock-source-id').value;
  const pwd = document.getElementById('kdbx-unlock-password').value;
  const keyfile = document.getElementById('kdbx-unlock-keyfile').value.trim() || null;
  const statusMsg = document.getElementById('kdbx-unlock-status-msg');
  const btn = document.getElementById('btn-confirm-unlock-kdbx');

  btn.disabled = true;
  btn.innerHTML = '<i data-lucide="loader-2" class="spin"></i> Validando...';
  if (window.lucide) window.lucide.createIcons();

  try {
    const res = await callApi('read_kdbx_entries', sid, pwd, keyfile);
    if (res && res.success) {
      activeKdbxSource = cachedKdbxSources.find(s => s.id === sid) || { id: sid, name: 'Base Aberta' };
      cachedKdbxEntries = res.data || [];
      closeModal('modal-kdbx-unlock');
      showToast(`${cachedKdbxEntries.length} credenciais carregadas da base!`);
      openKdbxExplorer();
      loadKdbxSources(); // Atualiza data de último acesso
    } else {
      statusMsg.style.background = 'rgba(248, 113, 113, 0.15)';
      statusMsg.style.color = 'var(--danger)';
      statusMsg.innerText = res.message || 'Falha ao autenticar no KDBX.';
      statusMsg.classList.remove('hidden');
    }
  } catch (e) {
    statusMsg.style.background = 'rgba(248, 113, 113, 0.15)';
    statusMsg.style.color = 'var(--danger)';
    statusMsg.innerText = `Erro: ${e.message}`;
    statusMsg.classList.remove('hidden');
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<i data-lucide="unlock"></i> Desbloquear & Abrir';
    if (window.lucide) window.lucide.createIcons();
  }
}

function openKdbxExplorer() {
  const section = document.getElementById('kdbx-explorer-section');
  const title = document.getElementById('kdbx-active-source-title');
  const subtitle = document.getElementById('kdbx-active-source-subtitle');
  if (!section) return;

  if (title) title.innerHTML = `<i data-lucide="unlock" style="color: var(--success); width: 18px; height: 18px;"></i> Base Aberta: ${escapeHtml(activeKdbxSource?.name || 'KDBX')}`;
  if (subtitle) subtitle.innerText = `${cachedKdbxEntries.length} entradas encontradas • ${activeKdbxSource?.file_path || ''}`;

  section.classList.remove('hidden');
  renderKdbxEntriesList();
  section.scrollIntoView({ behavior: 'smooth' });
}

function closeKdbxExplorer() {
  const section = document.getElementById('kdbx-explorer-section');
  if (section) section.classList.add('hidden');
  activeKdbxSource = null;
  cachedKdbxEntries = [];
}

function handleFilterKdbxEntries(query) {
  renderKdbxEntriesList(query);
}

function renderKdbxEntriesList(filterQuery = '') {
  const container = document.getElementById('kdbx-entries-container');
  if (!container) return;

  const cleanQ = (filterQuery || '').trim().toLowerCase();
  const entries = cleanQ
    ? cachedKdbxEntries.filter(e => {
        const text = `${e.title} ${e.username_or_key} ${e.url || ''} ${e.notes || ''}`.toLowerCase();
        return text.includes(cleanQ);
      })
    : cachedKdbxEntries;

  if (entries.length === 0) {
    container.innerHTML = '<div style="padding: 24px; text-align: center; color: var(--fg-muted); font-size: 13px;">Nenhuma entrada corresponde ao filtro.</div>';
    return;
  }

  let html = '';
  entries.forEach((e, idx) => {
    const meta = e.metadata || {};
    const groupName = meta.group ? `<span class="badge" style="background: var(--bg-elev-2); font-size: 10px;">${escapeHtml(meta.group)}</span>` : '';
    const hasTotp = meta.has_totp ? `<span class="badge" style="background: rgba(16, 185, 129, 0.2); color: #34d399; font-size: 10px;">TOTP</span>` : '';

    html += `
      <div style="display: flex; justify-content: space-between; align-items: center; padding: 10px 14px; background: var(--bg-elev); border: 1px solid var(--border); border-radius: var(--radius-sm); gap: 10px; flex-wrap: wrap;">
        <div style="flex: 1; min-width: 220px;">
          <div style="display: flex; align-items: center; gap: 6px; margin-bottom: 2px;">
            <strong style="color: var(--fg); font-size: 13px;">${escapeHtml(e.title)}</strong>
            ${groupName}
            ${hasTotp}
          </div>
          <div style="font-size: 12px; color: var(--fg-muted);">
            ${e.username_or_key ? `<span style="color: var(--fg);">${escapeHtml(e.username_or_key)}</span> • ` : ''}
            <span>${escapeHtml(e.url || 'Sem URL')}</span>
          </div>
        </div>

        <div style="display: flex; gap: 6px; align-items: center;">
          ${e.username_or_key ? `
            <button type="button" class="btn btn-secondary btn-sm" onclick="copyKdbxField('${escapeHtml(e.username_or_key)}', 'Usuário copiado!')" title="Copiar Usuário">
              <i data-lucide="user"></i>
            </button>
          ` : ''}
          ${e.password ? `
            <button type="button" class="btn btn-secondary btn-sm" onclick="copyKdbxField('${escapeHtml(e.password)}', 'Senha copiada com segurança!')" title="Copiar Senha">
              <i data-lucide="key"></i>
            </button>
          ` : ''}
          <button type="button" class="btn btn-primary btn-sm" onclick="handleImportSingleKdbxEntry(${idx})">
            <i data-lucide="download"></i> Importar para o Cofre
          </button>
        </div>
      </div>
    `;
  });

  container.innerHTML = html;
  if (window.lucide) window.lucide.createIcons();
}

async function copyKdbxField(text, msg) {
  if (!text) return;
  await callApi('copy_secret_to_clipboard', text, 30);
  showToast(msg || 'Copiado para a área de transferência!');
}

async function handleImportSingleKdbxEntry(index) {
  const entry = cachedKdbxEntries[index];
  if (!entry) return;

  const res = await callApi('import_kdbx_entries_to_vault', [entry], 'overwrite');
  if (res && res.success) {
    showToast(`Credencial "${entry.title}" importada para o Cofre Central!`);
    loadVaultData();
  } else {
    showToast(res.message || 'Erro ao importar credencial.');
  }
}

async function handleImportAllKdbxEntries() {
  if (!cachedKdbxEntries || cachedKdbxEntries.length === 0) {
    showToast('Nenhuma entrada disponível para importação.');
    return;
  }

  if (!confirm(`Deseja importar todas as ${cachedKdbxEntries.length} credenciais para o Cofre Central (toolbox.db)?`)) {
    return;
  }

  const btn = document.getElementById('btn-import-all-kdbx');
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<i data-lucide="loader-2" class="spin"></i> Importando...';
  }

  try {
    const res = await callApi('import_kdbx_entries_to_vault', cachedKdbxEntries, 'skip');
    if (res && res.success) {
      showToast(res.message || `${res.imported} credenciais importadas com sucesso!`);
      loadVaultData();
    } else {
      showToast(res.message || 'Erro ao importar credenciais.');
    }
  } catch (e) {
    showToast(`Falha: ${e.message}`);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = '<i data-lucide="download"></i> Importar Todos para o Cofre';
      if (window.lucide) window.lucide.createIcons();
    }
  }
}

async function handleSyncKdbxSource(sourceId) {
  const src = cachedKdbxSources.find(s => s.id === sourceId);
  if (!src) return;

  showToast(`Iniciando sincronização SSH para "${src.name}"...`);
  try {
    const res = await callApi('sync_kdbx_source', sourceId);
    if (res && res.success) {
      showToast(`Sincronização concluída com sucesso!`);
      loadKdbxSources();
    } else {
      showToast(`Erro na sincronização: ${res.message}`);
    }
  } catch (e) {
    showToast(`Falha na sincronização: ${e.message}`);
  }
}

// Exports globais adicionais
window.loadKdbxSources = loadKdbxSources;
window.openAddKdbxSourceModal = openAddKdbxSourceModal;
window.openEditKdbxSourceModal = openEditKdbxSourceModal;
window.toggleKdbxSourceTypeFields = toggleKdbxSourceTypeFields;
window.handleBrowseKdbxFile = handleBrowseKdbxFile;
window.handleBrowseKdbxKeyfile = handleBrowseKdbxKeyfile;
window.handleBrowseUnlockKeyfile = handleBrowseUnlockKeyfile;
window.handleSaveKdbxSource = handleSaveKdbxSource;
window.handleDeleteKdbxSource = handleDeleteKdbxSource;
window.handleOpenKdbxUnlockModal = handleOpenKdbxUnlockModal;
window.handleConfirmUnlockKdbx = handleConfirmUnlockKdbx;
window.closeKdbxExplorer = closeKdbxExplorer;
window.handleFilterKdbxEntries = handleFilterKdbxEntries;
window.copyKdbxField = copyKdbxField;
window.handleImportSingleKdbxEntry = handleImportSingleKdbxEntry;
window.handleImportAllKdbxEntries = handleImportAllKdbxEntries;
window.handleSyncKdbxSource = handleSyncKdbxSource;



