/* ============================================================
   Logon AWS Plugin - Client Script (M3 + One-Click Connect)
   ============================================================ */

let statusPollInterval = null;
let currentStatus = { connected: false, process_running: false, sso_running: false, state: "disconnected" };

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
    statusPollInterval = setInterval(pollStatus, 1500);
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
  const btnCancelSso = document.getElementById('btnCancelSso');

  pill.className = 'status-pill';

  if (status.connected) {
    pill.classList.add('status-connected');
    text.textContent = `Conectado (: ${status.port})`;
    if (btnConnect) btnConnect.disabled = true;
    if (btnDisconnect) btnDisconnect.disabled = false;
    if (btnCancelSso) btnCancelSso.style.display = 'none';
  } else if (status.state === 'checking_sts') {
    pill.classList.add('status-working');
    text.textContent = 'Verificando Sessão AWS...';
    if (btnConnect) btnConnect.disabled = true;
    if (btnDisconnect) btnDisconnect.disabled = true;
    if (btnCancelSso) btnCancelSso.style.display = 'none';
  } else if (status.sso_running || status.state === 'authenticating_sso') {
    pill.classList.add('status-working');
    text.textContent = 'Autenticando no Navegador...';
    if (btnConnect) btnConnect.disabled = true;
    if (btnDisconnect) btnDisconnect.disabled = true;
    if (btnCancelSso) btnCancelSso.style.display = 'inline-flex';
  } else if (status.process_running || status.state === 'starting_tunnel') {
    pill.classList.add('status-working');
    text.textContent = 'Iniciando Túnel SSM...';
    if (btnConnect) btnConnect.disabled = true;
    if (btnDisconnect) btnDisconnect.disabled = false;
    if (btnCancelSso) btnCancelSso.style.display = 'none';
  } else {
    pill.classList.add('status-disconnected');
    text.textContent = 'Desconectado';
    if (btnConnect) btnConnect.disabled = false;
    if (btnDisconnect) btnDisconnect.disabled = true;
    if (btnCancelSso) btnCancelSso.style.display = 'none';
  }
}

function renderLogs(logs) {
  const container = document.getElementById('consoleLog');
  if (!container || !logs || !logs.length) return;

  const isAtBottom = container.scrollHeight - container.clientHeight <= container.scrollTop + 30;

  container.innerHTML = logs.map(l => {
    let colorStyle = '';
    if (l.includes('✔') || l.includes('sucesso') || l.includes('concluído')) colorStyle = 'color: var(--md-sys-color-success);';
    else if (l.includes('✖') || l.includes('Erro') || l.includes('error') || l.includes('Falha')) colorStyle = 'color: var(--md-sys-color-error);';
    else if (l.includes('⚠️') || l.includes('Aviso')) colorStyle = 'color: var(--md-sys-color-warning);';
    else if (l.includes('Iniciando') || l.includes('Comando:') || l.includes('🚀') || l.includes('Navegador')) colorStyle = 'color: var(--md-sys-color-primary);';

    return `<div class="console-line" style="${colorStyle}">${escapeHtml(l)}</div>`;
  }).join('');

  if (isAtBottom) {
    container.scrollTop = container.scrollHeight;
  }
}

async function handleConnect() {
  const profile = document.getElementById('profileInput').value.trim() || 'rodrigo.lessa';
  const localPort = document.getElementById('localPortInput').value.trim() || '42586';

  updateStatusUI({ connected: false, process_running: false, sso_running: false, state: 'checking_sts', port: localPort });
  showToast(`Verificando credenciais e conectando (${profile})...`);

  try {
    const res = await window.pywebview.api.one_click_connect({
      profile: profile,
      local_port: localPort,
      region: 'sa-east-1',
    });
    if (!res.success && res.error) {
      alert(`Aviso: ${res.error}`);
    }
    setTimeout(pollStatus, 400);
  } catch (e) {
    alert(`Erro ao iniciar One-Click Connect: ${e}`);
  }
}

async function handleSsoLogin() {
  const profile = document.getElementById('profileInput').value.trim() || 'rodrigo.lessa';

  updateStatusUI({ connected: false, process_running: false, sso_running: true, state: 'authenticating_sso' });
  showToast(`Iniciando Login AWS SSO (${profile})...`);

  try {
    const res = await window.pywebview.api.sso_login({
      profile: profile,
    });
    if (!res.success && res.error) {
      alert(`Aviso: ${res.error}`);
    }
    setTimeout(pollStatus, 400);
  } catch (e) {
    alert(`Erro ao iniciar SSO: ${e}`);
  }
}

async function handleCancelSso() {
  showToast('Cancelando autenticação SSO...');
  try {
    await window.pywebview.api.cancel_sso();
    setTimeout(pollStatus, 400);
  } catch (e) {
    console.error('Erro ao cancelar SSO:', e);
  }
}

async function handleDisconnect() {
  showToast('Encerrando túnel SSM...');
  try {
    await window.pywebview.api.disconnect_tunnel();
    setTimeout(pollStatus, 400);
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

