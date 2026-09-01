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
// Workspace & Gerenciador de Segredos
// ============================================================================

async function loadVaultData() {
  const res = await callApi('list_secrets', 'all');
  if (res && res.success) {
    cachedSecrets = res.data || [];
    updateCategoryCounts();
    renderSecretsGrid();
  }
  checkKeePassXCStatus();
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

  if (cat === 'keepassxc') {
    if (grid) grid.classList.add('hidden');
    if (emptyState) emptyState.classList.add('hidden');
    if (kpxcPanel) {
      kpxcPanel.classList.remove('hidden');
      kpxcPanel.style.display = 'flex';
    }
    checkKeePassXCStatus();
  } else {
    if (kpxcPanel) {
      kpxcPanel.classList.add('hidden');
      kpxcPanel.style.display = 'none';
    }
    renderSecretsGrid();
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
        if (helpBanner) helpBanner.style.display = 'none';
      } else {
        if (dot) dot.style.background = 'var(--danger, #ef4444)';
        if (title) title.innerText = '🔴 KeePassXC Desconectado';
        if (desc) desc.innerText = data.error || 'KeePassXC não está em execução ou a integração com o navegador está desabilitada.';
        if (badge) { badge.innerText = '🔴'; badge.style.color = '#ef4444'; }
        if (btnLock) btnLock.style.display = 'none';
        if (helpBanner) helpBanner.style.display = 'block';
      }
    } else {
      if (dot) dot.style.background = '#888';
      if (title) title.innerText = 'KeePassXC Indisponível';
      if (desc) desc.innerText = (res && res.message) || 'Módulo indisponível.';
      if (helpBanner) helpBanner.style.display = 'block';
    }
  } catch (err) {
    if (dot) dot.style.background = '#888';
    if (title) title.innerText = 'Erro ao consultar KeePassXC';
    if (desc) desc.innerText = String(err);
    if (helpBanner) helpBanner.style.display = 'block';
  }
  if (window.lucide) window.lucide.createIcons();
}

async function handleAssociateKeePassXC() {
  const btn = document.getElementById('btn-associate-kpxc');
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<i data-lucide="loader" class="spin"></i> Aguardando Autorização...';
    if (window.lucide) window.lucide.createIcons();
  }

  showToast('Por favor, aprove o diálogo de pareamento que apareceu na janela do KeePassXC.', 'info');

  try {
    const res = await callApi('associate_keepassxc', 'Toolbox');
    if (res && res.success) {
      showToast('Associação com KeePassXC realizada com sucesso!', 'success');
      await checkKeePassXCStatus();
    } else {
      showToast(res.message || 'Falha ao associar com KeePassXC.', 'error');
    }
  } catch (err) {
    showToast(`Erro de associação: ${err}`, 'error');
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = '<i data-lucide="link-2"></i> Parear com KeePassXC';
      if (window.lucide) window.lucide.createIcons();
    }
    await checkKeePassXCStatus();
  }
}

async function handleLockKeePassXC() {
  try {
    const res = await callApi('lock_keepassxc_database');
    if (res && res.success) {
      showToast('Cofre do KeePassXC bloqueado.', 'info');
      await checkKeePassXCStatus();
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
            <div style="display: flex; gap: 8px;">
              ${e.login ? `<button type="button" class="btn btn-secondary btn-sm" onclick="copyKeePassXCText('${escapeJs(e.login)}', 'Usuário')"><i data-lucide="user"></i> Copiar Login</button>` : ''}
              ${e.password ? `<button type="button" class="btn btn-primary btn-sm" onclick="copyKeePassXCText('${escapeJs(e.password)}', 'Senha')"><i data-lucide="key"></i> Copiar Senha</button>` : ''}
              ${e.uuid ? `<button type="button" class="btn btn-secondary btn-sm" onclick="fetchAndCopyKeePassXCTotp('${escapeJs(e.uuid)}')"><i data-lucide="clock"></i> TOTP</button>` : ''}
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

