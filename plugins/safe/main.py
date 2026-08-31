"""
Ponto de Entrada e JS Bridge do Plugin Safe (Cofre Seguro) - pywebview.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

PLUGIN_DIR = Path(__file__).resolve().parent
if str(PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGIN_DIR))
PLUGINS_ROOT = PLUGIN_DIR.parent
if str(PLUGINS_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGINS_ROOT))

try:
    from shared.web_utils import BasePluginApi, create_plugin_window, copy_to_clipboard
except ImportError:
    # Fallback se importado diretamente
    from plugins.shared.web_utils import BasePluginApi, create_plugin_window, copy_to_clipboard

try:
    from service import SafeService, SafeAccessDeniedError, SafeVaultLockedError
except ImportError:
    try:
        from .service import SafeService, SafeAccessDeniedError, SafeVaultLockedError
    except ImportError:
        from safe.service import SafeService, SafeAccessDeniedError, SafeVaultLockedError

if sys.platform == "win32":
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("toolbox.plugin.safe")
    except Exception:
        pass


class SafePluginApi(BasePluginApi):
    """
    API exposta ao JavaScript (window.pywebview.api) para a interface do Cofre Seguro.
    """

    def __init__(self, service: Optional[SafeService] = None):
        super().__init__()
        self.service = service or SafeService()
        self.window = None
        self.service.add_on_lock_listener(self._on_service_lock)

    def set_window(self, window: Any) -> None:
        """Define a referência da janela pywebview para eventos push."""
        self.window = window

    def _on_service_lock(self, reason: str) -> None:
        """Acionado quando o serviço do cofre é bloqueado (por timeout ou evento do SO)."""
        if self.window:
            try:
                self.window.evaluate_js("if (typeof onVaultLockedBySystem === 'function') onVaultLockedBySystem();")
            except Exception as e:
                logger.debug(f"Aviso ao avaliar onVaultLockedBySystem na janela: {e}")

    def log_frontend_error(self, message: str, stack: Optional[str] = None) -> Dict[str, Any]:
        """Recebe e registra erros e exceções capturados no frontend JavaScript."""
        log_msg = f"[Frontend] {message}"
        if stack:
            log_msg += f"\nStack: {stack}"
        logger.error(log_msg)
        return {"success": True}

    def get_vault_status(self) -> Dict[str, Any]:
        try:
            status = self.service.get_status()
            logger.debug(f"Status do cofre consultado pela UI: configured={status.get('configured')}, status={status.get('status')}")
            return {"success": True, "data": status}
        except Exception as e:
            logger.error(f"Erro ao obter status do cofre: {e}", exc_info=True)
            return {"success": False, "message": str(e)}

    def setup_vault(
        self,
        auth_mode: str = "hybrid",
        password: Optional[str] = None,
        use_hello: bool = False,
        timeout: int = 300,
        lock_on_os_lock: bool = True,
    ) -> Dict[str, Any]:
        try:
            res = self.service.setup_vault(
                auth_mode=auth_mode,
                password=password,
                use_hello=use_hello,
                auto_lock_timeout=timeout,
                lock_on_os_lock=lock_on_os_lock,
            )
            return {"success": True, "data": res}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def unlock_vault(
        self,
        password: Optional[str] = None,
        use_hello: bool = False,
        reason: str = "Acesso ao Cofre Seguro",
    ) -> Dict[str, Any]:
        try:
            self.service.unlock(password=password, use_hello=use_hello, reason=reason)
            return {"success": True, "message": "Cofre desbloqueado com sucesso!"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def lock_vault(self) -> Dict[str, Any]:
        try:
            self.service.lock()
            return {"success": True, "message": "Cofre bloqueado com sucesso."}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def touch_activity(self) -> Dict[str, Any]:
        try:
            self.service.touch_activity()
            return {"success": True}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def list_secrets(
        self,
        category: Optional[str] = "all",
        search_query: Optional[str] = None,
    ) -> Dict[str, Any]:
        try:
            items = self.service.list_secrets(category=category, search_query=search_query)
            return {"success": True, "data": items}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def get_secret(self, entry_id: str) -> Dict[str, Any]:
        try:
            secret = self.service.get_secret(entry_id=entry_id)
            return {"success": True, "data": secret}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def save_secret(
        self,
        title: str,
        secret_payload: Union[Dict[str, Any], str],
        category: str = "general",
        username_or_key: Optional[str] = None,
        entry_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        try:
            res = self.service.save_secret(
                title=title,
                secret_payload=secret_payload,
                category=category,
                username_or_key=username_or_key,
                entry_id=entry_id,
                tags=tags,
                metadata=metadata,
            )
            return {"success": True, "data": res}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def delete_secret(self, entry_id: str) -> Dict[str, Any]:
        try:
            success = self.service.delete_secret(entry_id=entry_id)
            return {"success": success, "message": "Registro excluído com sucesso."}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def grant_plugin_access(
        self,
        target_plugin_id: str,
        entry_id: str,
        access_level: str = "read",
        expires_at: Optional[str] = None,
    ) -> Dict[str, Any]:
        try:
            res = self.service.grant_permission(
                target_plugin_id=target_plugin_id,
                entry_id=entry_id,
                access_level=access_level,
                expires_at=expires_at,
            )
            return {"success": True, "data": res}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def revoke_plugin_access(self, grant_id: str) -> Dict[str, Any]:
        try:
            success = self.service.revoke_permission(grant_id)
            return {"success": success}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def list_plugin_grants(self) -> Dict[str, Any]:
        try:
            grants = self.service.list_grants()
            return {"success": True, "data": grants}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def generate_password(
        self,
        length: int = 16,
        use_upper: bool = True,
        use_lower: bool = True,
        use_digits: bool = True,
        use_symbols: bool = True,
    ) -> Dict[str, Any]:
        try:
            pwd = self.service.generate_secure_password(
                length=length,
                use_upper=use_upper,
                use_lower=use_lower,
                use_digits=use_digits,
                use_symbols=use_symbols,
            )
            return {"success": True, "password": pwd}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def set_master_password(self, password: str) -> Dict[str, Any]:
        try:
            res = self.service.set_master_password(password=password)
            return {"success": True, "message": res.get("message", "Senha mestre definida com sucesso!")}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def update_security_settings(self, auto_lock_timeout: int, lock_on_os_lock: bool = True) -> Dict[str, Any]:
        try:
            res = self.service.update_security_settings(
                auto_lock_timeout=auto_lock_timeout,
                lock_on_os_lock=lock_on_os_lock,
            )
            return {"success": True, "data": res, "message": "Configurações de segurança salvas com sucesso!"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def update_settings(self, auto_lock_timeout: int) -> Dict[str, Any]:
        return self.update_security_settings(auto_lock_timeout=auto_lock_timeout, lock_on_os_lock=True)

    def export_secrets(self) -> Dict[str, Any]:
        try:
            data = self.service.export_secrets()
            return {"success": True, "data": data}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def preview_import_data(
        self,
        raw_text: Optional[str] = None,
        file_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Gera preview da importação a partir de texto bruto ou caminho de arquivo."""
        try:
            if file_path:
                p = Path(file_path)
                if not p.exists() or not p.is_file():
                    return {"success": False, "message": f"Arquivo não encontrado: {file_path}"}
                raw_bytes = p.read_bytes()
                res = self.service.preview_import(raw_bytes, filename=p.name)
                res["file_path"] = str(p.resolve())
                res["file_name"] = p.name
                return res
            elif raw_text:
                return self.service.preview_import(raw_text)
            else:
                return {"success": False, "message": "Nenhum dado fornecido para pré-visualização."}
        except Exception as e:
            logger.error(f"Erro ao gerar preview de importação: {e}", exc_info=True)
            return {"success": False, "message": str(e)}

    def import_secrets(
        self,
        items_or_payload: Any,
        conflict_policy: str = "skip",
        filename: Optional[str] = None,
    ) -> Dict[str, Any]:
        try:
            res = self.service.import_secrets(items_or_payload, conflict_policy=conflict_policy, filename=filename)
            return res
        except Exception as e:
            logger.error(f"Erro ao importar segredos: {e}", exc_info=True)
            return {"success": False, "message": str(e)}

    def import_secrets_from_file_path(
        self,
        file_path: str,
        conflict_policy: str = "skip",
    ) -> Dict[str, Any]:
        try:
            p = Path(file_path)
            if not p.exists() or not p.is_file():
                return {"success": False, "message": f"Arquivo não encontrado: {file_path}"}
            raw_bytes = p.read_bytes()
            return self.service.import_secrets(raw_bytes, conflict_policy=conflict_policy, filename=p.name)
        except Exception as e:
            return {"success": False, "message": f"Erro ao ler/importar arquivo: {e}"}

    def select_file_for_import(self) -> Dict[str, Any]:
        """Abre janela de seleção de arquivo (.xml, .csv, .txt, .json) e retorna os dados para preview."""
        try:
            win = self.window or self._window
            if not win:
                return {"success": False, "message": "Janela não inicializada."}

            import webview
            file_types = (
                "Arquivos Suportados (*.xml;*.csv;*.txt;*.json)",
                "Microsoft Safe XML (*.xml)",
                "Valores Separados por Vírgula (*.csv)",
                "Texto Simples (*.txt)",
                "Arquivos JSON / Backup (*.json)",
                "Todos os arquivos (*.*)",
            )
            res = win.create_file_dialog(
                webview.OPEN_DIALOG,
                allow_multiple=False,
                file_types=file_types,
            )
            if not res or len(res) == 0:
                return {"success": False, "message": "Nenhum arquivo selecionado."}

            chosen_file = res[0] if isinstance(res, (list, tuple)) else str(res)
            return self.preview_import_data(file_path=chosen_file)
        except Exception as e:
            return {"success": False, "message": str(e)}

    def select_and_import_secrets_file(self, conflict_policy: str = "skip") -> Dict[str, Any]:
        """Abre janela para selecionar arquivo (.xml, .csv, .txt, .json) e importa diretamente."""
        try:
            win = self.window or self._window
            if not win:
                return {"success": False, "message": "Janela não inicializada."}
            
            import webview
            file_types = (
                "Arquivos Suportados (*.xml;*.csv;*.txt;*.json)",
                "Microsoft Safe XML (*.xml)",
                "Valores Separados por Vírgula (*.csv)",
                "Texto Simples (*.txt)",
                "Arquivos JSON (*.json)",
                "Todos os arquivos (*.*)",
            )
            res = win.create_file_dialog(
                webview.OPEN_DIALOG,
                allow_multiple=False,
                file_types=file_types,
            )
            if not res or len(res) == 0:
                return {"success": False, "message": "Nenhum arquivo selecionado."}
            
            chosen_file = res[0] if isinstance(res, (list, tuple)) else str(res)
            return self.import_secrets_from_file_path(chosen_file, conflict_policy=conflict_policy)
        except Exception as e:
            return {"success": False, "message": str(e)}

    def copy_secret_to_clipboard(self, text: str) -> Dict[str, Any]:
        try:
            copy_to_clipboard(text)
            return {"success": True, "message": "Copiado para a área de transferência!"}
        except Exception as e:
            return {"success": False, "message": str(e)}


SHIELD_CHECK_ICON_PATH = PLUGIN_DIR / "ui" / "assets" / "shield-check.ico"


def set_window_taskbar_icon(icon_path: Optional[Path] = None, hwnd: Optional[int] = None) -> bool:
    """Atualiza o ícone da janela e da barra de tarefas no Windows para o ícone do cofre seguro."""
    if sys.platform != "win32":
        return False

    target_icon = Path(icon_path) if icon_path else SHIELD_CHECK_ICON_PATH
    if not target_icon.exists():
        return False

    try:
        import ctypes
        from ctypes import wintypes
        import os

        user32 = ctypes.windll.user32
        IMAGE_ICON = 1
        LR_LOADFROMFILE = 0x00000010
        WM_SETICON = 0x0080
        ICON_SMALL = 0
        ICON_BIG = 1

        h_icon_big = user32.LoadImageW(
            None,
            str(target_icon),
            IMAGE_ICON,
            32,
            32,
            LR_LOADFROMFILE,
        )
        h_icon_small = user32.LoadImageW(
            None,
            str(target_icon),
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
                if lpdw_pid.value == current_pid and user32.IsWindowVisible(handle):
                    target_hwnds.append(handle)
                return True

            enum_proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)(_enum_windows_cb)
            user32.EnumWindows(enum_proc, 0)

        for h in target_hwnds:
            if h_icon_big:
                user32.SendMessageW(h, WM_SETICON, ICON_BIG, h_icon_big)
            if h_icon_small:
                user32.SendMessageW(h, WM_SETICON, ICON_SMALL, h_icon_small)

        return len(target_hwnds) > 0
    except Exception:
        return False


try:
    from logger import get_logger
except ImportError:
    try:
        from .logger import get_logger
    except ImportError:
        import logging
        def get_logger(name="safe"):
            return logging.getLogger(name)

logger = get_logger("safe.main")


def _handle_uncaught_exception(exc_type, exc_value, exc_traceback):
    """Gancho global para registrar exceções não tratadas no processo Python."""
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    logger.critical("Exceção não tratada capturada no processo Safe:", exc_info=(exc_type, exc_value, exc_traceback))


sys.excepthook = _handle_uncaught_exception


def main():
    import webview
    import threading

    logger.info("Iniciando aplicação Cofre Seguro (UI)...")
    try:
        api = SafePluginApi()
        ui_path = PLUGIN_DIR / "ui" / "index.html"
        window = create_plugin_window(
            title="Cofre Seguro",
            entry_html=ui_path,
            js_api=api,
            width=920,
            height=760,
            min_size=(800, 600),
        )
        if window:
            api.set_window(window)

        if webview and window:
            def on_shown():
                set_window_taskbar_icon()
                threading.Timer(0.5, set_window_taskbar_icon).start()

            window.events.shown += on_shown

        logger.info("Janela pywebview inicializada. Abrindo loop de eventos.")
        webview.start(debug=False)
        logger.info("Aplicação Cofre Seguro finalizada.")
    except Exception as e:
        logger.critical(f"Falha fatal ao iniciar pywebview para o Cofre: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
