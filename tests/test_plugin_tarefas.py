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
    assert bool(data.get("version")), "version deve estar preenchida no plugin.json"
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

    # Garante que markdown-field.js é carregado como script clássico (sem type="module") para evitar bloqueio CORS em file://
    import re
    assert not re.search(r'<script\s+type=["\']module["\']\s+src=["\'][^"\']*markdown-field\.js', html_content), \
        "markdown-field.js não deve ter type='module' no index.html para compatibilidade pywebview file://"

    # Valida suporte a alternância e edição no app.js e style.css
    app_js = (ui_dir / "app.js").read_text(encoding="utf-8")
    assert "handleToggleDescriptionEdit" in app_js
    assert "renderNativeDescriptionFallback" in app_js
    assert "handleNativeSaveDesc" in app_js
    assert "btnEditDesc_" in app_js

    style_css = (ui_dir / "style.css").read_text(encoding="utf-8")
    assert ".description-header-row" in style_css


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
    assert ver_res["version"] == json.loads((TAREFAS_DIR / "plugin.json").read_text(encoding="utf-8"))["version"]

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


def test_subtasks_lifecycle_and_cascade_delete(tmp_path):
    """Testa criação de subtarefas, cálculo de estatísticas e exclusão em cascata."""
    # Cria tarefa pai
    parent = tarefas_domain.create_task("Tarefa Pai Principal")
    pid = parent["id"]
    assert parent.get("parent_id") is None

    # Cria duas subtarefas vinculadas
    sub1 = tarefas_domain.create_task("Subtarefa Etapa 1", parent_id=pid)
    sub2 = tarefas_domain.create_task("Subtarefa Etapa 2", parent_id=pid)

    assert sub1["parent_id"] == pid
    assert sub2["parent_id"] == pid

    # Recupera subtarefas
    subtasks = tarefas_domain.get_subtasks(pid)
    assert len(subtasks) == 2
    assert {s["id"] for s in subtasks} == {sub1["id"], sub2["id"]}

    # Progresso inicial: 0/2
    stats = tarefas_domain.get_task_subtask_stats(pid)
    assert stats == {"total": 2, "completed": 0}

    # Marca sub1 como concluída
    tarefas_domain.toggle_task_status(sub1["id"])
    stats = tarefas_domain.get_task_subtask_stats(pid)
    assert stats == {"total": 2, "completed": 1}

    # Adiciona um anexo na subtarefa 2
    dummy_file = tmp_path / "anexo_subtarefa.txt"
    dummy_file.write_text("conteudo da subtarefa", encoding="utf-8")
    att = tarefas_domain.add_attachment(sub2["id"], dummy_file)
    att_path = Path(att["file_path"])
    assert att_path.exists()

    # Exclui a tarefa pai
    deleted = tarefas_domain.delete_task(pid)
    assert deleted is True

    # Verifica que tanto o pai quanto as subtarefas foram removidas do banco de dados JSON
    all_remaining = tarefas_domain.load_tasks()
    assert len(all_remaining) == 0
    assert tarefas_domain.get_task(pid) is None
    assert tarefas_domain.get_task(sub1["id"]) is None
    assert tarefas_domain.get_task(sub2["id"]) is None
    assert not att_path.exists(), "Diretório de anexo da subtarefa deve ser excluído em cascata"


def test_subtask_validation_invalid_parent():
    """Valida que tentar criar subtarefa com parent_id inexistente dispara ValueError."""
    with pytest.raises(ValueError, match="não encontrada"):
        tarefas_domain.create_task("Subtarefa Órfã", parent_id="task_inexistente_999")


def test_tarefas_api_subtasks():
    """Testa criação de subtarefas através da classe TarefasApi."""
    api = TarefasApi()
    p_res = api.create_task("Pai via API")
    assert p_res["success"] is True
    pid = p_res["task"]["id"]

    sub_res = api.create_subtask(parent_id=pid, title="Filha via API")
    assert sub_res["success"] is True
    assert sub_res["task"]["parent_id"] == pid
    assert len(sub_res["tasks"]) == 2

    # UI files check for subtask components
    ui_dir = TAREFAS_DIR / "ui"
    app_js = (ui_dir / "app.js").read_text(encoding="utf-8")
    assert "promptCreateSubtask" in app_js
    assert "renderDetailSubtasksList" in app_js
    assert "toggleCollapseParent" in app_js
    assert "subtasks-container" in app_js

    style_css = (ui_dir / "style.css").read_text(encoding="utf-8")
    assert ".subtasks-container" in style_css
    assert ".btn-chevron" in style_css
    assert ".subtask-badge" in style_css
    assert ".detail-subtasks-section" in style_css


def test_domain_reorder_tasks():
    """Valida a persistência da reordenação manual de tarefas raiz."""
    t1 = tarefas_domain.create_task("Tarefa 1")
    t2 = tarefas_domain.create_task("Tarefa 2")
    t3 = tarefas_domain.create_task("Tarefa 3")

    initial = [t["id"] for t in tarefas_domain.load_tasks()]
    assert initial == [t3["id"], t2["id"], t1["id"]]

    # Reordena para [T1, T3, T2]
    new_order = [t1["id"], t3["id"], t2["id"]]
    success = tarefas_domain.reorder_tasks(new_order)
    assert success is True

    reordered = [t["id"] for t in tarefas_domain.load_tasks()]
    assert reordered == new_order


def test_domain_reorder_with_subtasks():
    """Valida reordenação entre subtarefas do mesmo pai sem corromper hierarquia."""
    parent = tarefas_domain.create_task("Tarefa Principal")
    pid = parent["id"]

    sub1 = tarefas_domain.create_task("Subtarefa Alpha", parent_id=pid)
    sub2 = tarefas_domain.create_task("Subtarefa Beta", parent_id=pid)
    sub3 = tarefas_domain.create_task("Subtarefa Gamma", parent_id=pid)

    # Inverte a ordem das subtarefas para [sub3, sub1, sub2]
    success = tarefas_domain.reorder_tasks([sub3["id"], sub1["id"], sub2["id"]])
    assert success is True

    subtasks = tarefas_domain.get_subtasks(pid)
    assert [s["id"] for s in subtasks] == [sub3["id"], sub1["id"], sub2["id"]]
    # Garante que parent_id permanece intacto
    for s in subtasks:
        assert s["parent_id"] == pid


def test_domain_reorder_partial_and_invalid():
    """Valida que reordenação com IDs inválidos ou parciais não apaga tarefas existentes."""
    t1 = tarefas_domain.create_task("Item A")
    t2 = tarefas_domain.create_task("Item B")

    # Passa IDs inválidos ou vazios
    assert tarefas_domain.reorder_tasks(["id_fantasma_1", "id_fantasma_2"]) is True
    # Tarefas reais permanecem intactas (ordem de inserção prepend: B, A)
    assert [t["id"] for t in tarefas_domain.load_tasks()] == [t2["id"], t1["id"]]


def test_tarefas_api_reorder_tasks():
    """Valida o método reorder_tasks exposto na TarefasApi para a WebView."""
    api = TarefasApi()
    res1 = api.create_task("Alpha")
    res2 = api.create_task("Beta")

    id1 = res1["task"]["id"]
    id2 = res2["task"]["id"]

    res_reorder = api.reorder_tasks([id2, id1])
    assert res_reorder["success"] is True
    assert [t["id"] for t in res_reorder["tasks"]] == [id2, id1]


def test_tarefas_ui_drag_and_drop_assets():
    """Valida que os componentes de UI para drag and drop estão presentes."""
    ui_dir = TAREFAS_DIR / "ui"

    app_js = (ui_dir / "app.js").read_text(encoding="utf-8")
    assert "handleDragStart" in app_js
    assert "handleDragOver" in app_js
    assert "handleDragLeave" in app_js
    assert "handleDrop" in app_js
    assert "handleDragEnd" in app_js
    assert "reorder_tasks" in app_js
    assert "drag-handle" in app_js

    style_css = (ui_dir / "style.css").read_text(encoding="utf-8")
    assert ".drag-handle" in style_css
    assert ".task-card.dragging" in style_css
    assert ".task-card.drag-over-top" in style_css
    assert ".task-card.drag-over-bottom" in style_css

    icons_js = (ui_dir / "icons.js").read_text(encoding="utf-8")
    assert "grip-vertical" in icons_js

