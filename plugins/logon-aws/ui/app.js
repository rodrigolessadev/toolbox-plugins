/* ============================================================
   Logon AWS Plugin - Client Script
   ============================================================ */

let statusPollInterval = null;
let currentStatus = { connected: false, process_running: false };

document.addEventListener('DOMContentLoaded', () => {
  window.addEventListener('pywebviewready', () => {
    initApp();
  });
  // Fallback caso não seja chamado o evento
  setTimeout(() => {
    if (window.pywebview && window.pywebview.api) {
      initApp();
    }
  }, 300);
});

async function initApp() {
  try {
    const data = await window.pywebview.api.get_initial_data();
    if (data.config) {
      if (data.config.profile) document.getElementById('profileInput').value = data.config.profile;
      if (data.config.local_port) document.getElementById('localPortInput').value = data.config.local_port;
      if (typeof data.config.auto_open_browser === 'boolean') {
        document.getElementById('autoOpenBrowser').checked = data.config.auto_open_browser;
      }
    }
    if (data.logs) {
      renderLogs(data.logs);
    }
    if (data.status) {
      updateStatusUI(data.status);
    }
  } catch (e) {
    console.error('Erro na inicialização:', e);
  }

  // Inicia checagem contínua de status
  if (!statusPollInterval) {
    statusPollInterval = setInterval(pollStatus, 2000);
  }
}

async function pollStatus() {
  if (!window.pywebview || !window.pywebview.api) return;
  const localPort = document.getElementById('localPortInput').value || '42586';
  try {
    const status = await window.pywebview.api.check_status({ local_port: localPort });
    updateStatusUI(status);

    const logs = await window.pywebview.api.get_logs();
    renderLogs(logs);
  } catch (e) {
    console.error('Erro no poll de status:', e);
  }
}

function updateStatusUI(status) {
  currentStatus = status;
  const pill = document.getElementById('statusPill');
  const text = document.getElementById('statusText');
  const btnConnect = document.getElementById('btnConnect');
  const btnDisconnect = document.getElementById('btnDisconnect');

  pill.className = 'status-pill';

  if (status.connected) {
    pill.classList.add('status-connected');
    text.textContent = `Conectado (: ${status.port})`;
    if (btnConnect) btnConnect.disabled = true;
    if (btnDisconnect) btnDisconnect.disabled = false;
  } else if (status.process_running) {
    pill.classList.add('status-working');
    text.textContent = 'Iniciando Túnel...';
    if (btnConnect) btnConnect.disabled = true;
    if (btnDisconnect) btnDisconnect.disabled = false;
  } else {
    pill.classList.add('status-disconnected');
    text.textContent = 'Desconectado';
    if (btnConnect) btnConnect.disabled = false;
    if (btnDisconnect) btnDisconnect.disabled = true;
  }
}

function renderLogs(logs) {
  const container = document.getElementById('consoleLog');
  if (!container || !logs || !logs.length) return;

  const isAtBottom = container.scrollHeight - container.clientHeight <= container.scrollTop + 30;

  container.innerHTML = logs.map(l => {
    let colorStyle = '';
    if (l.includes('✔') || l.includes('sucesso')) colorStyle = 'color: var(--md-sys-color-success);';
    else if (l.includes('✖') || l.includes('Erro') || l.includes('error')) colorStyle = 'color: var(--md-sys-color-error);';
    else if (l.includes('Iniciando') || l.includes('Comando:')) colorStyle = 'color: var(--md-sys-color-primary);';

    return `<div class="console-line" style="${colorStyle}">${escapeHtml(l)}</div>`;
  }).join('');

  if (isAtBottom) {
    container.scrollTop = container.scrollHeight;
  }
}

async function handleSsoLogin() {
  const profile = document.getElementById('profileInput').value.trim() || 'rodrigo.lessa';
  const autoOpen = document.getElementById('autoOpenBrowser').checked;

  showToast(`Iniciando Login AWS SSO (${profile})...`);
  try {
    await window.pywebview.api.sso_login({
      profile: profile,
      auto_open_browser: autoOpen,
    });
    setTimeout(pollStatus, 500);
  } catch (e) {
    alert(`Erro ao iniciar SSO: ${e}`);
  }
}

async function handleConnect() {
  const profile = document.getElementById('profileInput').value.trim() || 'rodrigo.lessa';
  const localPort = document.getElementById('localPortInput').value.trim() || '42586';

  updateStatusUI({ connected: false, process_running: true, port: localPort });
  showToast(`Buscando instância e iniciando túnel na porta ${localPort}...`);

  try {
    const res = await window.pywebview.api.connect_tunnel({
      profile: profile,
      local_port: localPort,
      region: 'sa-east-1',
    });
    if (!res.success && res.error) {
      alert(`Aviso: ${res.error}`);
    }
    setTimeout(pollStatus, 600);
  } catch (e) {
    alert(`Erro ao conectar: ${e}`);
  }
}

async function handleDisconnect() {
  showToast('Encerrando túnel SSM...');
  try {
    await window.pywebview.api.disconnect_tunnel();
    setTimeout(pollStatus, 500);
  } catch (e) {
    alert(`Erro ao desconectar: ${e}`);
  }
}

async function handleCopyLogs() {
  const logs = await window.pywebview.api.get_logs();
  const text = logs.join('\n');
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text);
  }
  if (window.pywebview && window.pywebview.api && window.pywebview.api.copy_text) {
    window.pywebview.api.copy_text(text);
  }
  showToast('Logs copiados para a área de transferência!');
}

async function handleClearLogs() {
  await window.pywebview.api.clear_logs();
  renderLogs(['[Logs limpos]']);
  showToast('Histórico de logs limpo.');
}

function toggleTheme() {
  const html = document.documentElement;
  const isDark = html.getAttribute('data-theme') === 'dark';
  html.setAttribute('data-theme', isDark ? 'light' : 'dark');
  const btn = document.getElementById('themeBtn');
  if (btn) btn.textContent = isDark ? '🌙 Tema' : '☀️ Tema';
}

function showToast(message) {
  const container = document.getElementById('toastContainer');
  if (!container) return;
  const toast = document.createElement('div');
  toast.className = 'toast';
  toast.textContent = message;
  container.appendChild(toast);
  setTimeout(() => toast.remove(), 2100);
}

function escapeHtml(text) {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}
