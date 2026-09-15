"""
Módulo de domínio e persistência de dados do Plugin de Tarefas.
Gerencia tarefas, status, descrições em Markdown e anexos vinculados.
"""

from __future__ import annotations

import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional


def get_data_dir() -> Path:
    """Retorna o diretório base de persistência do plugin de Tarefas."""
    env_dir = os.environ.get("TOOLBOX_TAREFAS_DATA_DIR")
    if env_dir:
        base_dir = Path(env_dir)
    elif sys.platform == "win32" and "APPDATA" in os.environ:
        base_dir = Path(os.environ["APPDATA"]) / "com.toolbox.desktop" / "tarefas"
    else:
        base_dir = Path.home() / ".toolbox" / "tarefas"

    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir


def get_tasks_file() -> Path:
    """Retorna o arquivo JSON principal de armazenamento de tarefas."""
    return get_data_dir() / "tasks.json"


def get_attachments_dir(task_id: Optional[str] = None) -> Path:
    """Retorna o diretório de anexos de uma tarefa ou a raiz de anexos."""
    base = get_data_dir() / "attachments"
    if task_id:
        clean_id = re.sub(r"[^a-zA-Z0-9_\-]", "_", str(task_id))
        target = base / clean_id
        target.mkdir(parents=True, exist_ok=True)
        return target
    base.mkdir(parents=True, exist_ok=True)
    return base


def format_file_size(size_bytes: int) -> str:
    """Formata tamanho de bytes em formato amigável (B, KB, MB, GB)."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"


def _now_iso() -> str:
    """Retorna o timestamp ISO 8601 atual formatado."""
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def load_tasks() -> List[Dict[str, Any]]:
    """Carrega todas as tarefas salvas do arquivo JSON."""
    tasks_file = get_tasks_file()
    if not tasks_file.exists():
        return []
    try:
        content = tasks_file.read_text(encoding="utf-8")
        if not content.strip():
            return []
        data = json.loads(content)
        if isinstance(data, list):
            return data
        elif isinstance(data, dict) and "tasks" in data and isinstance(data["tasks"], list):
            return data["tasks"]
        return []
    except Exception:
        return []


def save_tasks(tasks: List[Dict[str, Any]]) -> bool:
    """Salva a lista completa de tarefas no arquivo JSON de persistência."""
    try:
        tasks_file = get_tasks_file()
        tasks_file.write_text(json.dumps(tasks, indent=2, ensure_ascii=False), encoding="utf-8")
        return True
    except Exception:
        return False


def get_task(task_id: str) -> Optional[Dict[str, Any]]:
    """Busca uma tarefa pelo seu identificador."""
    tasks = load_tasks()
    for t in tasks:
        if t.get("id") == task_id:
            return t
    return None


def create_task(title: str, description: str = "") -> Dict[str, Any]:
    """Cria e persiste uma nova tarefa."""
    clean_title = (title or "").strip()
    if not clean_title:
        raise ValueError("O título da tarefa não pode ser vazio.")

    now = _now_iso()
    task_id = f"task_{uuid.uuid4().hex[:8]}"

    desc = description.strip() if description else f"# {clean_title}\n\nDescreva os detalhes e etapas desta tarefa aqui."

    new_task: Dict[str, Any] = {
        "id": task_id,
        "title": clean_title,
        "description": desc,
        "completed": False,
        "created_at": now,
        "updated_at": now,
        "attachments": []
    }

    tasks = load_tasks()
    tasks.insert(0, new_task)
    save_tasks(tasks)
    return new_task


def update_task(task_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    """Atualiza campos de uma tarefa existente."""
    tasks = load_tasks()
    found = False
    updated_task = {}

    for i, t in enumerate(tasks):
        if t.get("id") == task_id:
            found = True
            for key in ["title", "description", "completed"]:
                if key in updates:
                    t[key] = updates[key]
            t["updated_at"] = _now_iso()
            tasks[i] = t
            updated_task = t
            break

    if not found:
        raise ValueError(f"Tarefa com ID {task_id} não encontrada.")

    save_tasks(tasks)
    return updated_task


def toggle_task_status(task_id: str) -> Dict[str, Any]:
    """Inverte o status de conclusão de uma tarefa."""
    tasks = load_tasks()
    for t in tasks:
        if t.get("id") == task_id:
            t["completed"] = not bool(t.get("completed", False))
            t["updated_at"] = _now_iso()
            save_tasks(tasks)
            return t

    raise ValueError(f"Tarefa com ID {task_id} não encontrada.")


def delete_task(task_id: str) -> bool:
    """Exclui uma tarefa e seu diretório correspondente de anexos."""
    tasks = load_tasks()
    initial_len = len(tasks)
    tasks = [t for t in tasks if t.get("id") != task_id]

    if len(tasks) == initial_len:
        return False

    save_tasks(tasks)

    # Exclui pasta de anexos correspondente se existir
    task_att_dir = get_attachments_dir(task_id)
    if task_att_dir.exists():
        try:
            shutil.rmtree(task_att_dir, ignore_errors=True)
        except Exception:
            pass

    return True


def add_attachment(task_id: str, file_path: str | Path) -> Dict[str, Any]:
    """
    Copia um arquivo externo para o diretório de anexos da tarefa e
    vincula seus metadados à tarefa.
    """
    source_p = Path(file_path).resolve()
    if not source_p.exists() or not source_p.is_file():
        raise FileNotFoundError(f"Arquivo de anexo não encontrado: {file_path}")

    task = get_task(task_id)
    if not task:
        raise ValueError(f"Tarefa com ID {task_id} não encontrada.")

    att_dir = get_attachments_dir(task_id)
    att_id = f"att_{uuid.uuid4().hex[:8]}"

    # Garante nome de arquivo seguro sem conflito
    original_name = source_p.name
    destination_p = att_dir / original_name

    if destination_p.exists():
        stem = source_p.stem
        suffix = source_p.suffix
        counter = 1
        while destination_p.exists():
            destination_p = att_dir / f"{stem}_{counter}{suffix}"
            counter += 1

    shutil.copy2(source_p, destination_p)
    file_size = destination_p.stat().st_size

    attachment_meta: Dict[str, Any] = {
        "id": att_id,
        "name": destination_p.name,
        "size": file_size,
        "size_formatted": format_file_size(file_size),
        "extension": destination_p.suffix.lower(),
        "file_path": str(destination_p.resolve()),
        "original_path": str(source_p),
        "added_at": _now_iso(),
    }

    tasks = load_tasks()
    for t in tasks:
        if t.get("id") == task_id:
            if "attachments" not in t or not isinstance(t["attachments"], list):
                t["attachments"] = []
            t["attachments"].append(attachment_meta)
            t["updated_at"] = _now_iso()
            break

    save_tasks(tasks)
    return attachment_meta


def remove_attachment(task_id: str, attachment_id: str) -> bool:
    """Remove um anexo vinculado e exclui o arquivo do disco."""
    tasks = load_tasks()
    found = False

    for t in tasks:
        if t.get("id") == task_id:
            atts = t.get("attachments", [])
            new_atts = []
            for att in atts:
                if att.get("id") == attachment_id:
                    found = True
                    # Remove o arquivo físico se existir
                    p = Path(att.get("file_path", ""))
                    if p.exists() and p.is_file():
                        try:
                            p.unlink(missing_ok=True)
                        except Exception:
                            pass
                else:
                    new_atts.append(att)
            t["attachments"] = new_atts
            t["updated_at"] = _now_iso()
            break

    if found:
        save_tasks(tasks)
        return True
    return False


def get_attachment_path(task_id: str, attachment_id: str) -> Optional[Path]:
    """Retorna o Path do arquivo anexo se existente no disco."""
    task = get_task(task_id)
    if not task:
        return None
    for att in task.get("attachments", []):
        if att.get("id") == attachment_id:
            p = Path(att.get("file_path", ""))
            if p.exists():
                return p
    return None


def open_attachment_externally(task_id: str, attachment_id: str) -> bool:
    """Abre o arquivo do anexo com a aplicação padrão do sistema."""
    p = get_attachment_path(task_id, attachment_id)
    if not p or not p.exists():
        return False

    try:
        if sys.platform == "win32":
            os.startfile(str(p))
            return True
        elif sys.platform == "darwin":
            subprocess.run(["open", str(p)], check=False)
            return True
        else:
            subprocess.run(["xdg-open", str(p)], check=False)
            return True
    except Exception:
        return False


def open_attachment_folder(task_id: str, attachment_id: str) -> bool:
    """Abre a pasta contendo o anexo no explorador de arquivos nativo."""
    p = get_attachment_path(task_id, attachment_id)
    if not p or not p.exists():
        return False

    try:
        if sys.platform == "win32":
            subprocess.run(["explorer", f"/select,{str(p)}"], check=False)
            return True
        elif sys.platform == "darwin":
            subprocess.run(["open", "-R", str(p)], check=False)
            return True
        else:
            subprocess.run(["xdg-open", str(p.parent)], check=False)
            return True
    except Exception:
        return False
