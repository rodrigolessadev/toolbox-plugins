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


def _sort_flat_group(items: List[Dict[str, Any]], descending: bool = True) -> List[Dict[str, Any]]:
    """Ordena uma lista plana de tarefas colocando pendentes primeiro e ordenando por data."""
    pending = [t for t in items if not bool(t.get("completed", False))]
    completed = [t for t in items if bool(t.get("completed", False))]

    key_fn = lambda t: t.get("created_at") or t.get("updated_at") or ""
    pending.sort(key=key_fn, reverse=descending)
    completed.sort(key=key_fn, reverse=descending)
    return pending + completed


def sort_tasks_by_status_and_date(tasks: List[Dict[str, Any]], descending: bool = True) -> List[Dict[str, Any]]:
    """
    Ordena tarefas garantindo pendentes no topo e concluídas ao final.
    Dentro de cada grupo (pendentes e concluídas), ordena por data (created_at / updated_at).
    Se houver relação hierárquica (subtarefas com parent_id), preserva o agrupamento sob cada pai.
    """
    if not tasks:
        return []

    has_parents = any(not t.get("parent_id") for t in tasks)
    has_children = any(bool(t.get("parent_id")) for t in tasks)

    if has_parents and has_children:
        roots = [t for t in tasks if not t.get("parent_id")]
        sorted_roots = _sort_flat_group(roots, descending=descending)

        children_by_parent: Dict[str, List[Dict[str, Any]]] = {}
        for t in tasks:
            pid = t.get("parent_id")
            if pid:
                children_by_parent.setdefault(pid, []).append(t)

        result: List[Dict[str, Any]] = []
        handled_ids = set()
        for root in sorted_roots:
            result.append(root)
            handled_ids.add(root.get("id"))
            subs = children_by_parent.get(root.get("id"), [])
            if subs:
                sorted_subs = _sort_flat_group(subs, descending=descending)
                result.extend(sorted_subs)
                for s in sorted_subs:
                    handled_ids.add(s.get("id"))

        orphans = [t for t in tasks if t.get("id") not in handled_ids]
        if orphans:
            result.extend(_sort_flat_group(orphans, descending=descending))
        return result
    else:
        return _sort_flat_group(tasks, descending=descending)


def filter_tasks_by_date_range(
    tasks: List[Dict[str, Any]],
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    default_one_month: bool = True
) -> List[Dict[str, Any]]:
    """
    Filtra tarefas por intervalo de datas baseando-se em created_at (ou updated_at).
    Se date_from e date_to forem omitidos e default_one_month for True, aplica janela padrão
    dos últimos 30 dias contados a partir da data atual.
    Preserva tarefas pai caso alguma de suas subtarefas esteja no período.
    """
    if not tasks:
        return []

    clean_from = (date_from or "").strip()
    clean_to = (date_to or "").strip()

    if not clean_from and not clean_to and not default_one_month:
        return tasks

    now = datetime.datetime.now()
    if not clean_from and not clean_to and default_one_month:
        one_month_ago = now - datetime.timedelta(days=30)
        start_str = one_month_ago.strftime("%Y-%m-%d 00:00:00")
        end_str = now.strftime("%Y-%m-%d 23:59:59")
    else:
        start_str = f"{clean_from} 00:00:00" if clean_from and len(clean_from) == 10 else (clean_from or "1970-01-01 00:00:00")
        end_str = f"{clean_to} 23:59:59" if clean_to and len(clean_to) == 10 else (clean_to or now.strftime("%Y-%m-%d 23:59:59"))

    def in_range(item: Dict[str, Any]) -> bool:
        dt = item.get("created_at") or item.get("updated_at") or ""
        if not dt:
            return False
        return start_str <= dt <= end_str

    subtasks_by_parent: Dict[str, List[Dict[str, Any]]] = {}
    for t in tasks:
        pid = t.get("parent_id")
        if pid:
            subtasks_by_parent.setdefault(pid, []).append(t)

    matching_ids = set()
    for t in tasks:
        tid = t.get("id")
        if in_range(t):
            matching_ids.add(tid)
            if t.get("parent_id"):
                matching_ids.add(t.get("parent_id"))

    for pid, subs in subtasks_by_parent.items():
        if any(in_range(s) for s in subs):
            matching_ids.add(pid)

    return [t for t in tasks if t.get("id") in matching_ids]


def load_tasks(
    sort_by_status_and_date: bool = False,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    filter_dates: bool = False,
    default_one_month: bool = True
) -> List[Dict[str, Any]]:
    """Carrega todas as tarefas salvas do arquivo JSON com opções de ordenação e filtro de data."""
    tasks_file = get_tasks_file()
    if not tasks_file.exists():
        return []
    try:
        content = tasks_file.read_text(encoding="utf-8")
        if not content.strip():
            return []
        data = json.loads(content)
        tasks = []
        if isinstance(data, list):
            tasks = data
        elif isinstance(data, dict) and "tasks" in data and isinstance(data["tasks"], list):
            tasks = data["tasks"]

        if filter_dates:
            tasks = filter_tasks_by_date_range(
                tasks,
                date_from=date_from,
                date_to=date_to,
                default_one_month=default_one_month
            )

        if sort_by_status_and_date:
            return sort_tasks_by_status_and_date(tasks)
        return tasks
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


def create_task(title: str, description: str = "", parent_id: Optional[str] = None) -> Dict[str, Any]:
    """Cria e persiste uma nova tarefa ou subtarefa."""
    clean_title = (title or "").strip()
    if not clean_title:
        raise ValueError("O título da tarefa não pode ser vazio.")

    clean_parent_id: Optional[str] = None
    if parent_id is not None and str(parent_id).strip():
        clean_parent_id = str(parent_id).strip()
        parent_task = get_task(clean_parent_id)
        if not parent_task:
            raise ValueError(f"Tarefa pai com ID {clean_parent_id} não encontrada.")

    now = _now_iso()
    task_id = f"task_{uuid.uuid4().hex[:8]}"

    desc = description.strip() if description else f"# {clean_title}\n\nDescreva os detalhes e etapas desta tarefa aqui."

    new_task: Dict[str, Any] = {
        "id": task_id,
        "parent_id": clean_parent_id,
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


def get_subtasks(parent_id: str) -> List[Dict[str, Any]]:
    """Retorna todas as tarefas filhas vinculadas à tarefa com parent_id."""
    clean_pid = str(parent_id).strip() if parent_id else ""
    if not clean_pid:
        return []
    tasks = load_tasks()
    return [t for t in tasks if t.get("parent_id") == clean_pid]


def get_task_subtask_stats(task_id: str) -> Dict[str, int]:
    """Retorna a contagem de subtarefas totais e concluídas para uma tarefa pai."""
    subtasks = get_subtasks(task_id)
    total = len(subtasks)
    completed = sum(1 for st in subtasks if bool(st.get("completed", False)))
    return {"total": total, "completed": completed}


def update_task(task_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    """Atualiza campos de uma tarefa existente com suporte a mudança hierárquica e prevenção de ciclos."""
    tasks = load_tasks()
    found = False
    updated_task = {}

    for i, t in enumerate(tasks):
        if t.get("id") == task_id:
            found = True
            for key in ["title", "description", "completed", "created_at"]:
                if key in updates:
                    t[key] = updates[key]

            if "parent_id" in updates:
                new_pid = updates["parent_id"]
                if new_pid is not None and str(new_pid).strip():
                    clean_pid = str(new_pid).strip()
                    if clean_pid == task_id:
                        raise ValueError("Uma tarefa não pode ser pai de si mesma.")
                    parent_task = next((x for x in tasks if x.get("id") == clean_pid), None)
                    if not parent_task:
                        raise ValueError(f"Tarefa pai com ID {clean_pid} não encontrada.")
                    # Prevenção de ciclos: o novo pai não pode ser descendente da tarefa
                    descendant_ids = set()
                    to_check = [task_id]
                    while to_check:
                        curr = to_check.pop()
                        for x in tasks:
                            if x.get("parent_id") == curr and x.get("id") not in descendant_ids:
                                descendant_ids.add(x.get("id"))
                                to_check.append(x.get("id"))
                    if clean_pid in descendant_ids:
                        raise ValueError("Não é permitido criar ciclos de dependência entre tarefas pai e filhas.")
                    t["parent_id"] = clean_pid
                else:
                    t["parent_id"] = None

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
    """Exclui uma tarefa e recursivamente todas as suas subtarefas e pastas de anexos."""
    tasks = load_tasks()
    initial_len = len(tasks)

    # Identifica recursivamente todos os IDs a serem removidos (a tarefa e suas filhas)
    ids_to_delete = {task_id}
    changed = True
    while changed:
        changed = False
        for t in tasks:
            tid = t.get("id")
            pid = t.get("parent_id")
            if pid in ids_to_delete and tid not in ids_to_delete:
                ids_to_delete.add(tid)
                changed = True

    tasks = [t for t in tasks if t.get("id") not in ids_to_delete]

    if len(tasks) == initial_len:
        return False

    save_tasks(tasks)

    # Exclui pasta de anexos correspondente para cada tarefa removida
    for did in ids_to_delete:
        task_att_dir = get_attachments_dir(did)
        if task_att_dir.exists():
            try:
                shutil.rmtree(task_att_dir, ignore_errors=True)
            except Exception:
                pass

    return True


def reorder_tasks(ordered_task_ids: List[str]) -> bool:
    """
    Reorganiza as tarefas no disco de acordo com a lista ordenada de identificadores recebida.
    Tarefas presentes em ordered_task_ids são ordenadas na sequência especificada.
    Tarefas omitidas preservam suas posições relativas sem perda de dados.
    """
    if not ordered_task_ids:
        return True

    tasks = load_tasks()
    if not tasks:
        return True

    task_map = {t["id"]: t for t in tasks if t.get("id")}
    valid_ordered_ids = [tid for tid in ordered_task_ids if tid in task_map]
    if not valid_ordered_ids:
        return True

    valid_set = set(valid_ordered_ids)
    ordered_tasks_queue = [task_map[tid] for tid in valid_ordered_ids]

    new_tasks: List[Dict[str, Any]] = []
    order_idx = 0
    for t in tasks:
        if t.get("id") in valid_set:
            new_tasks.append(ordered_tasks_queue[order_idx])
            order_idx += 1
        else:
            new_tasks.append(t)

    return save_tasks(new_tasks)



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
