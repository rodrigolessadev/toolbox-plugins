"""Módulo de domínio do plugin Logon AWS & Port Forwarding.
Gerencia processos de autenticação AWS SSO, túneis SSM, verificação de sessão STS e monitoramento de portas via TCP sockets.
"""
from __future__ import annotations

import json
import os
import re
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

CONFIG_FILE = Path(__file__).parent / "config.json"
PLUGIN_DIR = Path(__file__).parent
ASSETS_DIR = PLUGIN_DIR / "ui" / "assets"
ICON_CONNECTED_PATH = ASSETS_DIR / "icon-connected.ico"
ICON_DISCONNECTED_PATH = ASSETS_DIR / "icon-disconnected.ico"

DEFAULT_CONFIG: Dict[str, Any] = {
    "profile": "",
    "local_port": "",
}

# Flag para evitar abrir prompt no Windows
CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


def set_window_taskbar_icon(is_connected: bool, hwnd: Optional[int] = None) -> bool:
    """Atualiza o ícone da janela e da barra de tarefas no Windows (Verde se conectado, Vermelho se desconectado)."""
    if sys.platform != "win32":
        return False

    icon_path = ICON_CONNECTED_PATH if is_connected else ICON_DISCONNECTED_PATH
    if not icon_path.exists():
        return False

    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        IMAGE_ICON = 1
        LR_LOADFROMFILE = 0x00000010
        WM_SETICON = 0x0080
        ICON_SMALL = 0
        ICON_BIG = 1

        h_icon_big = user32.LoadImageW(
            None,
            str(icon_path),
            IMAGE_ICON,
            32,
            32,
            LR_LOADFROMFILE,
        )
        h_icon_small = user32.LoadImageW(
            None,
            str(icon_path),
            IMAGE_ICON,
            16,
            16,
            LR_LOADFROMFILE,
        )

        if not h_icon_big and not h_icon_small:
            return False

        if hwnd:
            target_hwnds = [hwnd]
        else:
            current_pid = os.getpid()
            target_hwnds = []

            def _enum_windows_cb(handle: int, _: Any) -> bool:
                lpdw_pid = wintypes.DWORD()
                user32.GetWindowThreadProcessId(handle, ctypes.byref(lpdw_pid))
                if lpdw_pid.value == current_pid:
                    if user32.IsWindowVisible(handle):
                        target_hwnds.append(handle)
                return True

            WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
            user32.EnumWindows(WNDENUMPROC(_enum_windows_cb), 0)

        success = False
        for target in target_hwnds:
            if h_icon_big:
                user32.SendMessageW(target, WM_SETICON, ICON_BIG, h_icon_big)
            if h_icon_small:
                user32.SendMessageW(target, WM_SETICON, ICON_SMALL, h_icon_small)
            success = True
        return success
    except Exception:
        pass
    return False


def load_config() -> Dict[str, Any]:
    """Carrega as preferências salvas do plugin."""
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            return {**DEFAULT_CONFIG, **data}
        except Exception:
            return DEFAULT_CONFIG.copy()
    return DEFAULT_CONFIG.copy()


def save_config(config: Dict[str, Any]) -> bool:
    """Salva preferências do usuário no config.json."""
    try:
        data = {**load_config(), **config}
        CONFIG_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        return True
    except Exception:
        return False


def is_port_open(port: int, host: str = "127.0.0.1", timeout: float = 0.6) -> bool:
    """Verifica se uma porta TCP local está aberta e respondendo."""
    if port <= 0 or port > 65535:
        return False
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception:
        return False


def check_sts_session(profile: str, timeout: float = 8.0) -> Tuple[bool, str]:
    """Executa 'aws sts get-caller-identity' para verificar se a sessão AWS está ativa."""
    profile = profile.strip()
    if not profile:
        return False, "Profile AWS não informado."
    cmd = ["aws", "sts", "get-caller-identity", "--profile", profile]
    try:
        res = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=CREATE_NO_WINDOW,
            timeout=timeout,
        )
        if res.returncode == 0:
            return True, res.stdout.strip()
        err = res.stderr.strip() or f"Código de saída {res.returncode}"
        return False, err
    except Exception as e:
        return False, str(e)


def discover_ec2_target(profile: str, region: str = "sa-east-1") -> Tuple[bool, str]:
    """Busca a instância EC2 com a tag Name='SSH Tunneling Instance' em estado running."""
    profile = profile.strip()
    if not profile:
        return False, "Profile AWS não informado."
    cmd = [
        "aws", "ec2", "describe-instances",
        "--filters", "Name=tag:Name,Values=SSH Tunneling Instance", "Name=instance-state-name,Values=running",
        "--output", "text",
        "--query", "Reservations[*].Instances[*].InstanceId",
        "--region", region,
        "--profile", profile,
    ]
    try:
        res = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=CREATE_NO_WINDOW,
            timeout=15.0,
        )
        if res.returncode != 0:
            err_msg = res.stderr.strip() or f"Código de saída {res.returncode}"
            return False, f"Falha ao consultar instâncias EC2: {err_msg}"

        instance_id = res.stdout.strip()
        if not instance_id or instance_id == "None":
            return False, f"Nenhuma instância EC2 'SSH Tunneling Instance' em execução encontrada na região {region}"

        # Se vier mais de uma instância, pega a primeira
        first_instance = instance_id.split()[0]
        return True, first_instance
    except Exception as e:
        return False, f"Erro ao executar consulta EC2: {e}"


def terminate_process_tree(proc: Optional[subprocess.Popen[str]]) -> None:
    """Encerra um processo e toda a sua árvore de subprocessos filhos recursivamente."""
    if proc is None:
        return
    try:
        if proc.poll() is not None:
            return
    except Exception:
        pass

    pid = proc.pid
    if sys.platform == "win32":
        try:
            # /F força o término, /T mata a árvore inteira de processos filhos (como session-manager-plugin.exe)
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=CREATE_NO_WINDOW,
                timeout=3.0,
            )
        except Exception:
            pass

    # Fallback / garantia de encerramento via interface Python
    try:
        proc.terminate()
        try:
            proc.wait(timeout=1.0)
        except Exception:
            proc.kill()
    except Exception:
        pass


class AwsTunnelManager:
    """Gerenciador singleton para túneis AWS, sessões SSO no navegador e fluxo One-Click."""

    def __init__(self) -> None:
        self.process: Optional[subprocess.Popen[str]] = None
        self.sso_process: Optional[subprocess.Popen[str]] = None
        self.logs: List[str] = []
        self.active_profile: str = ""
        self.active_port: int = 42586
        self.current_state: str = "idle"  # idle, checking_sts, authenticating_sso, starting_tunnel, connected
        self._lock = threading.RLock()

    def append_log(self, text: str) -> None:
        """Adiciona linha ao histórico de logs com timestamp."""
        ts = time.strftime("%H:%M:%S")
        entry = f"[{ts}] {text.strip()}"
        with self._lock:
            self.logs.append(entry)
            if len(self.logs) > 300:
                self.logs.pop(0)

    def get_logs(self) -> List[str]:
        """Retorna cópia dos logs recentes."""
        with self._lock:
            return list(self.logs)

    def clear_logs(self) -> None:
        """Limpa o histórico de logs."""
        with self._lock:
            self.logs.clear()

    def cancel_sso_login(self) -> Dict[str, Any]:
        """Cancela o processo de login SSO em andamento e seus processos filhos."""
        with self._lock:
            if self.sso_process:
                self.append_log("Cancelando processo de login AWS SSO...")
                terminate_process_tree(self.sso_process)
                self.sso_process = None

            self.current_state = "idle"
            self.append_log("Autenticação SSO cancelada pelo usuário.")
            return {"success": True, "message": "Login SSO cancelado."}

    def run_sso_login(
        self,
        profile: str,
        on_success_callback: Optional[Callable[[], None]] = None,
    ) -> Dict[str, Any]:
        """Executa login AWS SSO em background delegando a autorização ao navegador padrão."""
        profile = profile.strip()
        if not profile:
            return {"success": False, "error": "Por favor, informe seu usuário/profile AWS."}

        with self._lock:
            if self.sso_process and self.sso_process.poll() is None:
                return {"success": False, "error": "Já existe uma autenticação SSO em andamento."}

            self.active_profile = profile
            self.current_state = "authenticating_sso"

        self.append_log(f"Iniciando AWS SSO Login para o profile '{profile}' no navegador padrão...")

        cmd = ["aws", "sso", "login", "--profile", profile]

        def _login_worker() -> None:
            try:
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    creationflags=CREATE_NO_WINDOW,
                )
                with self._lock:
                    self.sso_process = proc

                if proc.stdout:
                    for line in iter(proc.stdout.readline, ""):
                        if not line:
                            break
                        line_str = line.strip()
                        self.append_log(line_str)

                proc.wait()

                if proc.returncode == 0:
                    self.append_log(f"✔ AWS SSO Login concluído com sucesso para '{profile}'!")
                    if on_success_callback:
                        on_success_callback()
                    else:
                        with self._lock:
                            self.current_state = "idle"
                else:
                    self.append_log(f"✖ AWS SSO Login finalizou com código {proc.returncode}.")
                    with self._lock:
                        self.current_state = "idle"

            except Exception as e:
                self.append_log(f"Erro ao executar login AWS: {e}")
                with self._lock:
                    self.current_state = "idle"
            finally:
                with self._lock:
                    if self.sso_process == proc:
                        self.sso_process = None

        threading.Thread(target=_login_worker, daemon=True).start()
        return {"success": True, "message": f"Login SSO iniciado para profile '{profile}'."}

    def start_tunnel(
        self,
        profile: str,
        local_port: Any = "",
        region: str = "sa-east-1",
        target_instance_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Inicia túnel SSM Port Forwarding com porta 22 fixa e target EC2 automático."""
        profile = profile.strip()
        if not profile:
            return {"success": False, "error": "Por favor, informe seu usuário/profile AWS."}

        try:
            port_num = int(local_port) if local_port else 0
        except (ValueError, TypeError):
            port_num = 0

        if port_num <= 0:
            return {"success": False, "error": "Por favor, informe uma porta local válida para abrir o túnel."}

        local_port = port_num

        with self._lock:
            if self.process and self.process.poll() is None:
                return {
                    "success": False,
                    "error": "Já existe um túnel ativo. Desconecte antes de iniciar outro.",
                }
            self.current_state = "starting_tunnel"

        self.active_profile = profile
        self.active_port = local_port

        save_config({
            "profile": profile,
            "local_port": local_port,
        })

        if target_instance_id:
            instance_id = target_instance_id
        else:
            self.append_log(f"Descobrindo instância EC2 'SSH Tunneling Instance' em {region}...")
            ok, inst = discover_ec2_target(profile, region)
            if not ok:
                self.append_log(f"Erro na busca de EC2: {inst}")
                with self._lock:
                    self.current_state = "idle"
                return {"success": False, "error": inst}
            instance_id = inst
            self.append_log(f"Instância encontrada: {instance_id}")

        params = json.dumps({"portNumber": ["22"], "localPortNumber": [str(local_port)]})
        cmd = [
            "aws", "ssm", "start-session",
            "--target", instance_id,
            "--document-name", "AWS-StartPortForwardingSession",
            "--parameters", params,
            "--region", region,
            "--profile", profile,
        ]

        self.append_log(f"Iniciando túnel SSM: 127.0.0.1:{local_port} -> {instance_id}:22")

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=CREATE_NO_WINDOW,
            )
            with self._lock:
                self.process = proc
                self.current_state = "starting_tunnel"
        except Exception as e:
            self.append_log(f"Falha ao executar comando SSM: {e}")
            with self._lock:
                self.current_state = "idle"
            return {"success": False, "error": str(e)}

        def _reader_worker(p: subprocess.Popen[str]) -> None:
            try:
                if p.stdout:
                    for line in iter(p.stdout.readline, ""):
                        if not line:
                            break
                        self.append_log(line.strip())
                p.wait()
                self.append_log(f"Túnel SSM encerrado (código: {p.returncode}).")
            except Exception as e:
                self.append_log(f"Erro no monitoramento do túnel: {e}")
            finally:
                with self._lock:
                    if self.process == p:
                        self.process = None
                        self.current_state = "idle"
                set_window_taskbar_icon(False)

        threading.Thread(target=_reader_worker, args=(proc,), daemon=True).start()
        return {"success": True, "message": f"Túnel iniciado na porta {local_port}.", "instance_id": instance_id}

    def one_click_connect(
        self,
        profile: str,
        local_port: Any = "",
        region: str = "sa-east-1",
    ) -> Dict[str, Any]:
        """Fluxo unificado One-Click Connect:

        1. Verifica sessão STS prévia.
        2. Se ativa, conecta o túnel SSM diretamente.
        3. Se expirada, abre navegador padrão para autenticação SSO e conecta automaticamente ao finalizar.
        """
        profile = profile.strip()
        if not profile:
            return {"success": False, "error": "Por favor, informe seu usuário/profile AWS."}

        try:
            port_num = int(local_port) if local_port else 0
        except (ValueError, TypeError):
            port_num = 0

        if port_num <= 0:
            return {"success": False, "error": "Por favor, informe uma porta local válida para abrir o túnel."}

        local_port = port_num

        with self._lock:
            if self.process and self.process.poll() is None:
                return {
                    "success": False,
                    "error": "Já existe um túnel ativo. Desconecte antes de iniciar outro.",
                }
            if self.sso_process and self.sso_process.poll() is None:
                return {
                    "success": False,
                    "error": "Já existe uma autenticação SSO em andamento.",
                }

        save_config({
            "profile": profile,
            "local_port": local_port,
        })

        def _one_click_worker() -> None:
            with self._lock:
                self.current_state = "checking_sts"
            self.append_log(f"Verificando sessão ativa para '{profile}' via AWS STS...")

            is_active, sts_msg = check_sts_session(profile)

            if is_active:
                self.append_log(f"✔ Sessão AWS ativa para '{profile}'! Pulando autenticação SSO...")
                self.start_tunnel(profile, local_port, region)
            else:
                self.append_log(f"⚠️ Sessão AWS não autenticada ou expirada para '{profile}'.")
                self.append_log("Abrindo navegador padrão para autorização AWS SSO...")

                def _on_sso_success() -> None:
                    self.append_log(f"🚀 Autenticação concluída! Conectando túnel SSM automaticamente na porta {local_port}...")
                    self.start_tunnel(profile, local_port, region)

                self.run_sso_login(
                    profile=profile,
                    on_success_callback=_on_sso_success,
                )

        threading.Thread(target=_one_click_worker, daemon=True).start()
        return {"success": True, "message": "Fluxo One-Click Connect iniciado."}

    def stop_tunnel(self) -> Dict[str, Any]:
        """Interrompe o processo do túnel SSM ativo e toda a sua árvore de subprocessos."""
        with self._lock:
            if not self.process:
                self.append_log("Nenhum processo de túnel em execução.")
                set_window_taskbar_icon(False)
                return {"success": True, "message": "Nenhum túnel ativo."}

            try:
                self.append_log("Encerrando processo do túnel SSM e processos filhos...")
                terminate_process_tree(self.process)
                self.process = None
                self.current_state = "idle"
                self.append_log("✔ Túnel desconectado com sucesso.")
                set_window_taskbar_icon(False)
                return {"success": True, "message": "Túnel desconectado."}
            except Exception as e:
                self.append_log(f"Erro ao interromper túnel: {e}")
                self.process = None
                self.current_state = "idle"
                set_window_taskbar_icon(False)
                return {"success": False, "error": str(e)}

    def stop_all(self) -> None:
        """Encerra imediatamente todos os subprocessos ativos (túnel SSM e login SSO) e libera recursos."""
        with self._lock:
            if self.process:
                terminate_process_tree(self.process)
                self.process = None
            if self.sso_process:
                terminate_process_tree(self.sso_process)
                self.sso_process = None
            self.current_state = "idle"
        set_window_taskbar_icon(False)

    def get_status(self, custom_port: Any = None) -> Dict[str, Any]:
        """Retorna o estado detalhado da conexão e dos subprocessos, sincronizando o ícone da barra de tarefas."""
        try:
            port = int(custom_port) if custom_port else (int(self.active_port) if self.active_port else 0)
        except (ValueError, TypeError):
            port = 0

        has_tunnel = self.process is not None and self.process.poll() is None
        port_active = is_port_open(port) if (has_tunnel and port > 0) else False
        has_sso = self.sso_process is not None and self.sso_process.poll() is None

        state = self.current_state
        if has_tunnel and port_active:
            state = "connected"
        elif has_tunnel and not port_active:
            state = "starting_tunnel"
        elif has_sso:
            state = "authenticating_sso"
        elif not has_tunnel and not has_sso and state not in ("checking_sts", "starting_tunnel"):
            state = "disconnected"

        is_connected = has_tunnel and port_active
        set_window_taskbar_icon(is_connected)

        return {
            "connected": is_connected,
            "process_running": has_tunnel,
            "sso_running": has_sso,
            "state": state,
            "port": port,
            "profile": self.active_profile,
        }


# Instância global gerenciadora
tunnel_manager = AwsTunnelManager()
