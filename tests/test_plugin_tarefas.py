import importlib.util
import json
import os
import sys
from pathlib import Path
import pytest

pytestmark = pytest.mark.plugin("tarefas")

REPO_ROOT = Path(__file__).parent.parent
PLUGINS_DIR = REPO_ROOT / "plugins"
TAREFAS_DIR = PLUGINS_DIR / "tarefas"
DOMAIN_PATH = TAREFAS_DIR / "domain.py"
MAIN_PATH = TAREFAS_DIR / "main.py"

# Carrega módulos de tarefas com nomes únicos para evitar colisão no sys.modules
spec_domain = importlib.util.spec_from_file_location("tarefas_domain", DOMAIN_PATH)
tarefas_domain = importlib.util.module_from_spec(spec_domain)
spec_domain.loader.exec_module(tarefas_domain)

spec_main = importlib.util.spec_from_file_location("tarefas_main", MAIN_PATH)
tarefas_main = importlib.util.module_from_spec(spec_main)
spec_main.loader.exec_module(tarefas_main)

TarefasApi = tarefas_main.TarefasApi


@pytest.fixture(autouse=True)
def isolated_tarefas_env(tmp_path, monkeypatch):
    """Garante ambiente isolado e limpo para cada teste."""
    data_dir = tmp_path / "tarefas_data"
    data_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("TOOLBOX_TAREFAS_DATA_DIR", str(data_dir))
    return data_dir


def test_tarefas_manifests():
    """Valida o manifesto oficial plugin.json e package.json."""
    pj = TAREFAS_DIR / "plugin.json"
    assert pj.exists(), "plugin.json do plugin tarefas deve existir"
    data = json.loads(pj.read_text(encoding="utf-8"))

    assert data.get("name") == "Tarefas"
    assert data.get("version") == "1.0.0"
    assert data.get("entry") == "main.py"
    assert data.get("icon") == "check-square"
    assert data.get("theme_version") == "material-3"

    pkg = TAREFAS_DIR / "package.json"
    assert pkg.exists(), "package.json do plugin tarefas deve existir"
    pkg_data = json.loads(pkg.read_text(encoding="utf-8"))
    assert "@toolbox-plugins/shared-markdown" in pkg_data.get("dependencies", {})


def test_tarefas_ui_files_exist():
    """Valida a presença de todos os arquivos de UI necessários."""
    ui_dir = TAREFAS_DIR / "ui"
    assert (ui_dir / "index.html").exists()
    assert (ui_dir / "style.css").exists()
    assert (ui_dir / "icons.js").exists()
    assert (ui_dir / "app.js").exists()
    assert (ui_dir / "toolbox-theme.css").exists()

    # Valida menções no HTML aos elementos exigidos na issue
    html_content = (ui_dir / "index.html").read_text(encoding="utf-8")
    assert "chatInput" in html_content
    assert "chatSubmitBtn" in html_content
    assert "markdown-field" in html_content
    assert "tabsContainer" in html_content


def test_domain_crud_and_status():
    """Testa criação, leitura, atualização e alternância de status de tarefas."""
    assert tarefas_domain.load_tasks() == []

    # Criação
    task1 = tarefas_domain.create_task("Desenvolver nova feature", "# Detalhes\n\nImplementar componentes.")
    assert task1["id"].startswith("task_")
    assert task1["title"] == "Desenvolver nova feature"
    assert task1["completed"] is False
    assert len(task1["attachments"]) == 0
    assert "Implementar componentes" in task1["description"]

    # Criação de segunda tarefa
    task2 = tarefas_domain.create_task("Testar no ambiente de QA")
    tasks = tarefas_domain.load_tasks()
    assert len(tasks) == 2
    assert tasks[0]["id"] == task2["id"]  # Ordem cronológica decrescente

    # Busca
    found = tarefas_domain.get_task(task1["id"])
    assert found is not None
    assert found["title"] == task1["title"]

    # Atualização
    updated = tarefas_domain.update_task(task1["id"], {"title": "Desenvolver nova feature v2", "description": "Novo texto"})
    assert updated["title"] == "Desenvolver nova feature v2"
    assert updated["description"] == "Novo texto"

    # Toggle status
    toggled = tarefas_domain.toggle_task_status(task1["id"])
    assert toggled["completed"] is True

    toggled_again = tarefas_domain.toggle_task_status(task1["id"])
    assert toggled_again["completed"] is False

    # Erro com título vazio
    with pytest.raises(ValueError):
        tarefas_domain.create_task("   ")


def test_domain_attachments_lifecycle(tmp_path):
    """Testa anexo de arquivos, cálculo de tamanho e remoção segura."""
    task = tarefas_domain.create_task("Tarefa com Documentos")
    task_id = task["id"]

    # Cria arquivo temporário para anexar
    sample_file = tmp_path / "especificacao.pdf"
    sample_file.write_text("Conteúdo do PDF de teste com alguns bytes a mais.", encoding="utf-8")

    # Adiciona anexo
    att_meta = tarefas_domain.add_attachment(task_id, sample_file)
    assert att_meta["id"].startswith("att_")
    assert att_meta["name"] == "especificacao.pdf"
    assert att_meta["size"] > 0
    assert "B" in att_meta["size_formatted"]

    # Verifica persistência do anexo na tarefa
    reloaded_task = tarefas_domain.get_task(task_id)
    assert len(reloaded_task["attachments"]) == 1
    assert reloaded_task["attachments"][0]["id"] == att_meta["id"]

    # Verifica existência física do arquivo salvo
    saved_path = tarefas_domain.get_attachment_path(task_id, att_meta["id"])
    assert saved_path is not None
    assert saved_path.exists()

    # Remove anexo
    removed = tarefas_domain.remove_attachment(task_id, att_meta["id"])
    assert removed is True
    assert not saved_path.exists()

    reloaded_after_rm = tarefas_domain.get_task(task_id)
    assert len(reloaded_after_rm["attachments"]) == 0


def test_domain_delete_task_cleanup(tmp_path):
    """Testa exclusão de tarefa e limpeza de diretório de anexos."""
    task = tarefas_domain.create_task("Tarefa para exclusão")
    task_id = task["id"]

    # Anexa arquivo
    dummy_file = tmp_path / "planilha.xlsx"
    dummy_file.write_text("dummy binary content", encoding="utf-8")
    tarefas_domain.add_attachment(task_id, dummy_file)

    task_att_dir = tarefas_domain.get_attachments_dir(task_id)
    assert task_att_dir.exists()

    # Exclui tarefa
    assert tarefas_domain.delete_task(task_id) is True
    assert tarefas_domain.get_task(task_id) is None
    # Verifica que o diretório de anexos da tarefa foi limpo
    assert not task_att_dir.exists()


def test_tarefas_api():
    """Valida as chamadas da API exposta ao pywebview."""
    api = TarefasApi()

    # Versão
    ver_res = api.get_plugin_version()
    assert ver_res["success"] is True
    assert ver_res["version"] == "1.0.0"

    # Criar tarefa
    c_res = api.create_task("Tarefa via API")
    assert c_res["success"] is True
    task_id = c_res["task"]["id"]

    # Listar tarefas
    list_res = api.get_tasks()
    assert list_res["success"] is True
    assert len(list_res["tasks"]) == 1

    # Atualizar tarefa
    up_res = api.update_task(task_id, {"title": "Tarefa via API Renomeada"})
    assert up_res["success"] is True
    assert up_res["task"]["title"] == "Tarefa via API Renomeada"

    # Alternar status
    tog_res = api.toggle_task(task_id)
    assert tog_res["success"] is True
    assert tog_res["task"]["completed"] is True

    # Excluir tarefa
    del_res = api.delete_task(task_id)
    assert del_res["success"] is True
    assert len(del_res["tasks"]) == 0
