import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

PLUGIN_DIR = Path(__file__).resolve().parent
if str(PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGIN_DIR))
PLUGINS_ROOT = PLUGIN_DIR.parent
if str(PLUGINS_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGINS_ROOT))

import importlib.util
from shared.web_utils import BasePluginApi, create_plugin_window

try:
    import webview
except ImportError:
    webview = None

domain_path = PLUGIN_DIR / "domain.py"
spec = importlib.util.spec_from_file_location("tarefas_domain", domain_path)
domain = importlib.util.module_from_spec(spec)
spec.loader.exec_module(domain)


class TarefasApi(BasePluginApi):
    """API exposta para a interface WebView do plugin de Tarefas."""

    def get_tasks(self) -> Dict[str, Any]:
        """Retorna todas as tarefas salvas."""
        try:
            return {"success": True, "tasks": domain.load_tasks()}
        except Exception as exc:
            return {"success": False, "error": str(exc), "tasks": []}

    def create_task(self, title: str, description: str = "", parent_id: Optional[str] = None) -> Dict[str, Any]:
        """Cria uma nova tarefa ou subtarefa e retorna a lista atualizada."""
        try:
            task = domain.create_task(title=title, description=description, parent_id=parent_id)
            return {"success": True, "task": task, "tasks": domain.load_tasks()}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def create_subtask(self, parent_id: str, title: str, description: str = "") -> Dict[str, Any]:
        """Cria uma subtarefa vinculada a uma tarefa pai existente."""
        return self.create_task(title=title, description=description, parent_id=parent_id)

    def update_task(self, task_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Atualiza dados (título, descrição, status) de uma tarefa."""
        try:
            task = domain.update_task(task_id=task_id, updates=updates)
            return {"success": True, "task": task, "tasks": domain.load_tasks()}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def toggle_task(self, task_id: str) -> Dict[str, Any]:
        """Alterna o status de concluído de uma tarefa."""
        try:
            task = domain.toggle_task_status(task_id=task_id)
            return {"success": True, "task": task, "tasks": domain.load_tasks()}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def delete_task(self, task_id: str) -> Dict[str, Any]:
        """Exclui uma tarefa e seus anexos."""
        try:
            success = domain.delete_task(task_id=task_id)
            return {"success": success, "tasks": domain.load_tasks()}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def reorder_tasks(self, task_ids: list) -> Dict[str, Any]:
        """Reorganiza tarefas no disco conforme a lista de IDs recebida."""
        try:
            success = domain.reorder_tasks(task_ids)
            return {"success": success, "tasks": domain.load_tasks()}
        except Exception as exc:
            return {"success": False, "error": str(exc), "tasks": domain.load_tasks()}

    def add_attachment_dialog(self, task_id: str) -> Dict[str, Any]:
        """Abre diálogo nativo do SO para seleção e vinculação de anexos."""
        try:
            if not webview or not webview.windows:
                return {"success": False, "error": "Janela principal não encontrada."}

            win = webview.windows[0]
            result = win.create_file_dialog(
                webview.OPEN_DIALOG,
                allow_multiple=True,
                file_types=("Todos os arquivos (*.*)",)
            )

            if not result:
                return {"success": False, "cancelled": True}

            file_paths = result if isinstance(result, (list, tuple)) else [result]
            added = []
            for fp in file_paths:
                if fp and Path(fp).exists():
                    att = domain.add_attachment(task_id, fp)
                    added.append(att)

            task = domain.get_task(task_id)
            return {
                "success": True,
                "added": added,
                "task": task,
                "tasks": domain.load_tasks()
            }
        except Exception as exc:
            return {"success": False, "error": f"Erro ao anexar arquivo: {str(exc)}"}

    def remove_attachment(self, task_id: str, attachment_id: str) -> Dict[str, Any]:
        """Remove um anexo vinculado."""
        try:
            success = domain.remove_attachment(task_id, attachment_id)
            task = domain.get_task(task_id)
            return {
                "success": success,
                "task": task,
                "tasks": domain.load_tasks()
            }
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def open_attachment(self, task_id: str, attachment_id: str) -> Dict[str, Any]:
        """Abre o anexo diretamente na aplicação padrão do SO."""
        success = domain.open_attachment_externally(task_id, attachment_id)
        return {"success": success}

    def open_attachment_folder(self, task_id: str, attachment_id: str) -> Dict[str, Any]:
        """Abre a pasta contendo o anexo no explorador nativo."""
        success = domain.open_attachment_folder(task_id, attachment_id)
        return {"success": success}

    def get_plugin_version(self) -> Dict[str, Any]:
        """Retorna a versão do plugin declarada no plugin.json."""
        try:
            pj = PLUGIN_DIR / "plugin.json"
            if pj.exists():
                data = json.loads(pj.read_text(encoding="utf-8"))
                return {"success": True, "version": data.get("version", "1.0.0")}
        except Exception:
            pass
        return {"success": True, "version": "1.0.0"}


def main():
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("toolbox.plugin.tarefas")
        except Exception:
            pass

    api = TarefasApi()
    ui_index = Path(__file__).parent / "ui" / "index.html"
    window = create_plugin_window(
        title="Tarefas",
        entry_html=ui_index,
        js_api=api,
        plugin_dir=PLUGIN_DIR,
        width=980,
        height=720,
        min_size=(720, 560),
    )

    if webview:
        webview.start(debug=False)


if __name__ == "__main__":
    main()
