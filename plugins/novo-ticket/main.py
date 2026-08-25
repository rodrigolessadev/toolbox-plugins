"""
Plugin Novo Ticket — Toolbox (Versão pywebview)
Interface moderna para criação de tickets e extração temporal de logs.
"""

from __future__ import annotations

import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

# Adiciona diretório plugins ao path para importar shared
PLUGIN_DIR = Path(__file__).resolve().parent
if str(PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGIN_DIR))
PLUGINS_ROOT = PLUGIN_DIR.parent
if str(PLUGINS_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGINS_ROOT))

from shared.web_utils import BasePluginApi, create_plugin_window, open_in_explorer, copy_to_clipboard
import domain
import webview

if sys.platform == "win32":
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("toolbox.plugin.novoticket")
    except Exception:
        pass


class NovoTicketApi(BasePluginApi):
    def __init__(self):
        super().__init__()
        self.active_ticket_dir: Optional[Path] = None

    def select_base_folder(self, initial_dir: Optional[str] = None) -> str:
        return self.select_folder(initial_dir)

    def list_tickets(self, base_dir: Optional[str] = None) -> Dict[str, Any]:
        """Lista os tickets existentes no diretório base informado."""
        target_dir = base_dir or (str(self.active_ticket_dir.parent) if self.active_ticket_dir else "")
        return domain.list_existing_tickets(target_dir)

    def select_existing_ticket_by_path(self, ticket_path: str) -> Dict[str, Any]:
        """Carrega e ativa um ticket a partir do caminho selecionado."""
        return self.get_ticket_details(ticket_path)

    def select_ticket_folder(self, initial_dir: Optional[str] = None) -> Dict[str, Any]:
        chosen = self.select_folder(initial_dir)
        if not chosen:
            return {"success": False, "message": "Nenhum diretório selecionado."}
        p = Path(chosen).resolve()
        if not p.exists() or not p.is_dir():
            return {"success": False, "message": "Diretório inválido."}
        self.active_ticket_dir = p
        return self.get_ticket_details(str(p))

    def preview_ticket(self, base_dir: str, client: str, ticket: str) -> Dict[str, Any]:
        is_dir_valid, msg, base_path = domain.validate_base_dir(base_dir)
        if not is_dir_valid or base_path is None:
            return {"valid": False, "message": msg, "folder_name": "", "full_path": "", "exists": False}
        is_in_valid, msg_in, c_clean, t_clean = domain.validate_inputs(client, ticket)
        if not is_in_valid:
            return {"valid": False, "message": msg_in, "folder_name": "", "full_path": "", "exists": False}
        folder_name = f"{c_clean}_{t_clean}"
        full_path = base_path / folder_name
        return {
            "valid": True,
            "message": "Caminho válido",
            "folder_name": folder_name,
            "full_path": str(full_path),
            "exists": full_path.exists(),
        }

    def create_ticket(self, base_dir: str, client: str, ticket: str) -> Dict[str, Any]:
        success, msg, target = domain.create_ticket_directory(base_dir, client, ticket)
        if not success or target is None:
            return {"success": False, "message": msg}
        self.active_ticket_dir = target
        details = self.get_ticket_details(str(target))
        return {
            "success": True,
            "message": f"Ticket criado com sucesso em: {target.name}",
            "ticket": details.get("ticket"),
        }

    def get_ticket_details(self, ticket_path: str) -> Dict[str, Any]:
        p = Path(ticket_path).resolve()
        if not p.exists() or not p.is_dir():
            return {"success": False, "message": "Diretório do ticket não encontrado."}
        self.active_ticket_dir = p
        subfolders = domain.get_ticket_subdirectories_info(p)
        logs_filtrados = p / "logs_filtrados"
        return {
            "success": True,
            "ticket": {
                "name": p.name,
                "path": str(p),
                "subfolders": subfolders,
                "has_logs_filtrados": logs_filtrados.exists(),
            }
        }

    def get_quick_dates(self) -> Dict[str, str]:
        today = date.today()
        yesterday = today - timedelta(days=1)
        week_ago = today - timedelta(days=7)
        return {
            "today": today.strftime("%Y-%m-%d"),
            "yesterday": yesterday.strftime("%Y-%m-%d"),
            "week_ago": week_ago.strftime("%Y-%m-%d"),
            "default_start_time": "00:00:00",
            "default_end_time": "23:59:59",
        }

    def execute_filter(
        self,
        ticket_path: str,
        selected_subfolders: List[str],
        start_date: str,
        start_time: str,
        end_date: str,
        end_time: str,
        overwrite: bool = True,
    ) -> Dict[str, Any]:
        p = Path(ticket_path).resolve()
        if not p.exists() or not p.is_dir():
            return {"success": False, "message": "Diretório do ticket inválido."}
        if not selected_subfolders:
            return {"success": False, "message": "Selecione ao menos uma subpasta para filtrar."}

        try:
            start_dt, end_dt = domain.parse_datetime_range(start_date, start_time, end_date, end_time)
        except Exception as e:
            return {"success": False, "message": f"Intervalo de data/hora inválido: {e}"}

        try:
            stats = domain.process_ticket_logs(
                ticket_dir=p,
                selected_subfolders=selected_subfolders,
                start_dt=start_dt,
                end_dt=end_dt,
                overwrite=overwrite,
            )
            output_dir = p / "logs_filtrados"
            return {
                "success": True,
                "message": (
                    f"Filtragem concluída! {stats['processed_files']} arquivos processados, "
                    f"{stats['total_lines_written']} blocos de log extraídos."
                ),
                "stats": stats,
                "output_dir": str(output_dir),
            }
        except Exception as e:
            return {"success": False, "message": f"Erro durante a filtragem: {e}"}


def main():
    api = NovoTicketApi()
    ui_index = PLUGIN_DIR / "ui" / "index.html"
    window = create_plugin_window(
        title="Novo Ticket",
        entry_html=ui_index,
        js_api=api,
        width=740,
        height=760,
        min_size=(660, 620),
    )
    if webview and window:
        def on_shown():
            domain.set_window_taskbar_icon()
            import threading
            threading.Timer(0.6, domain.set_window_taskbar_icon).start()

        window.events.shown += on_shown
    if webview:
        webview.start(debug=False)


if __name__ == "__main__":
    main()
