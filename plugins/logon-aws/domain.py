"""Módulo de domínio do plugin Logon AWS & Port Forwarding.
Gerencia processos de autenticação AWS SSO, túneis SSM e monitoramento de portas via TCP sockets.
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
from typing import Any, Dict, List, Optional, Tuple

CONFIG_FILE = Path(__file__).parent / "config.json"

DEFAULT_CONFIG: Dict[str, Any] = {
    "profile": "default",
    "local_port": 5432,
    "remote_port": 5432,
    "target": "",
    "auto_open_browser": True,
}

# Flag para evitar abrir prompt no Windows
CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


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


class AwsTunnelManager:
    """Gerenciador singleton para túneis AWS e sessões de logon."""

    def __init__(self) -> None:
        self.process: Optional[subprocess.Popen[str]] = None
        self.logs: List[str] = []
        self.active_profile: str = ""
        self.active_port: int = 5432
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

    def run_sso_login(self, profile: str, auto_open_browser: bool = True) -> Dict[str, Any]:
        """Executa login AWS SSO em background sem abrir janela de prompt."""
        profile = profile.strip() or "default"
        self.append_log(f"Iniciando AWS SSO Login para o profile '{profile}'...")

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

                opened_url = False
                if proc.stdout:
                    for line in iter(proc.stdout.readline, ""):
                        if not line:
                            break
                        line_str = line.strip()
                        self.append_log(line_str)

                        # Detecta URLs de autenticação SSO
                        urls = re.findall(r"https?://[^\s]+", line_str)
                        if urls and auto_open_browser and not opened_url:
                            for url in urls:
                                if "awsapps.com" in url or "signin.aws" in url or "start.aws" in url or "device" in url:
                                    self.append_log(f"Abrindo URL de autenticação no navegador: {url}")
                                    webbrowser.open(url)
                                    opened_url = True

                proc.wait()
                if proc.returncode == 0:
                    self.append_log(f"✔ AWS SSO Login concluído com sucesso para '{profile}'!")
                else:
                    self.append_log(f"✖ AWS SSO Login finalizou com código {proc.returncode}.")
            except Exception as e:
                self.append_log(f"Erro ao executar login AWS: {e}")

        threading.Thread(target=_login_worker, daemon=True).start()
        return {"success": True, "message": f"Login SSO iniciado para profile '{profile}'."}

    def start_tunnel(
        self,
        profile: str,
        local_port: int,
        remote_port: int = 5432,
        target: str = "",
    ) -> Dict[str, Any]:
        """Inicia túnel SSM Port Forwarding em background."""
        with self._lock:
            if self.process and self.process.poll() is None:
                return {
                    "success": False,
                    "error": "Já existe um túnel ativo. Desconecte antes de iniciar outro.",
                }

        profile = profile.strip() or "default"
        local_port = int(local_port) if local_port else 5432
        remote_port = int(remote_port) if remote_port else local_port

        self.active_profile = profile
        self.active_port = local_port

        # Salva as configurações utilizadas
        save_config({
            "profile": profile,
            "local_port": local_port,
            "remote_port": remote_port,
            "target": target,
        })

        params_json = json.dumps({
            "portNumber": [str(remote_port)],
            "localPortNumber": [str(local_port)],
        })

        cmd = [
            "aws", "ssm", "start-session",
            "--document-name", "AWS-StartPortForwardingSession",
            "--parameters", params_json,
            "--profile", profile,
        ]

        if target.strip():
            cmd.extend(["--target", target.strip()])

        self.append_log(f"Iniciando túnel SSM (porta local: {local_port} ➔ remota: {remote_port})...")
        self.append_log(f"Comando: {' '.join(cmd)}")

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
        except Exception as e:
            self.append_log(f"Erro ao iniciar processo do túnel: {e}")
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

        threading.Thread(target=_reader_worker, args=(proc,), daemon=True).start()
        return {"success": True, "message": f"Túnel iniciado na porta {local_port}."}

    def stop_tunnel(self) -> Dict[str, Any]:
        """Interrompe o processo do túnel SSM ativo."""
        with self._lock:
            if not self.process or self.process.poll() is not None:
                self.append_log("Nenhum processo de túnel em execução.")
                return {"success": True, "message": "Nenhum túnel ativo."}

            try:
                self.append_log("Encerrando processo do túnel SSM...")
                self.process.terminate()
                try:
                    self.process.wait(timeout=2.0)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                self.process = None
                self.append_log("✔ Túnel desconectado com sucesso.")
                return {"success": True, "message": "Túnel desconectado."}
            except Exception as e:
                self.append_log(f"Erro ao interromper túnel: {e}")
                return {"success": False, "error": str(e)}

    def get_status(self, custom_port: Optional[int] = None) -> Dict[str, Any]:
        """Retorna o estado da conexão e da porta local."""
        port = custom_port or self.active_port or 5432
        port_active = is_port_open(port)
        has_process = self.process is not None and self.process.poll() is None

        return {
            "connected": port_active,
            "process_running": has_process,
            "port": port,
            "profile": self.active_profile,
        }


# Instância global gerenciadora
tunnel_manager = AwsTunnelManager()
