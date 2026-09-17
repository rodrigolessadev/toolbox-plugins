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
    assert (ui_dir / "markdown-field.js").exists()
    assert (ui_dir / "markdown-field.css").exists()

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


def test_domain_sort_tasks_by_status_and_date():
    """Valida a ordenação determinística: pendentes no topo, concluídas ao final, mais recentes primeiro."""
    tasks = [
        {"id": "t1", "completed": True, "created_at": "2026-09-17 10:00:00"},
        {"id": "t2", "completed": False, "created_at": "2026-09-17 08:00:00"},
        {"id": "t3", "completed": False, "created_at": "2026-09-17 12:00:00"},
        {"id": "t4", "completed": True, "created_at": "2026-09-17 14:00:00"},
    ]

    sorted_tasks = tarefas_domain.sort_tasks_by_status_and_date(tasks, descending=True)
    sorted_ids = [t["id"] for t in sorted_tasks]

    # Pendentes primeiro por data decrescente (t3 depois t2), seguidas de concluídas por data decrescente (t4 depois t1)
    assert sorted_ids == ["t3", "t2", "t4", "t1"]

    # Testa ordem ascendente
    sorted_asc = tarefas_domain.sort_tasks_by_status_and_date(tasks, descending=False)
    assert [t["id"] for t in sorted_asc] == ["t2", "t3", "t1", "t4"]


def test_domain_sort_tasks_with_hierarchy():
    """Valida ordenação com estrutura hierárquica preservando subtarefas sob seus pais."""
    tasks = [
        {"id": "p1", "parent_id": None, "completed": False, "created_at": "2026-09-17 10:00:00"},
        {"id": "s1_1", "parent_id": "p1", "completed": True, "created_at": "2026-09-17 09:00:00"},
        {"id": "s1_2", "parent_id": "p1", "completed": False, "created_at": "2026-09-17 09:30:00"},
        {"id": "p2", "parent_id": None, "completed": True, "created_at": "2026-09-17 12:00:00"},
        {"id": "p3", "parent_id": None, "completed": False, "created_at": "2026-09-17 11:00:00"},
    ]

    sorted_tasks = tarefas_domain.sort_tasks_by_status_and_date(tasks, descending=True)
    sorted_ids = [t["id"] for t in sorted_tasks]

    # Raízes ordenadas: p3 (pendente, 11h), p1 (pendente, 10h), p2 (concluída, 12h)
    # Sob p1, subtarefas ordenadas: s1_2 (pendente, 09:30), s1_1 (concluída, 09:00)
    assert sorted_ids == ["p3", "p1", "s1_2", "s1_1", "p2"]


def test_domain_load_tasks_with_sort_flag():
    """Valida que load_tasks aceita o parâmetro sort_by_status_and_date."""
    tarefas_domain.create_task("Antiga", "")
    tarefas_domain.create_task("Nova", "")

    # Inverte status da mais recente para concluída
    all_t = tarefas_domain.load_tasks()
    tarefas_domain.toggle_task_status(all_t[0]["id"])

    # Sem flag: ordem natural salva em disco
    raw = tarefas_domain.load_tasks(sort_by_status_and_date=False)
    # Com flag: pendentes sempre no topo
    sorted_list = tarefas_domain.load_tasks(sort_by_status_and_date=True)

    assert sorted_list[0]["completed"] is False
    assert sorted_list[-1]["completed"] is True


def test_tarefas_api_sort_tasks():
    """Valida o método sort_tasks exposto na TarefasApi."""
    api = TarefasApi()
    res1 = api.create_task("Tarefa A")
    res2 = api.create_task("Tarefa B")

    api.toggle_task(res2["task"]["id"])  # Marca B como concluída

    res_sort = api.sort_tasks(descending=True)
    assert res_sort["success"] is True
    assert res_sort["tasks"][0]["id"] == res1["task"]["id"]
    assert res_sort["tasks"][1]["id"] == res2["task"]["id"]


def test_tarefas_ui_sorting_and_divider_assets():
    """Valida que o frontend possui o divisor de concluídas e as rotinas de ordenação."""
    ui_dir = TAREFAS_DIR / "ui"

    app_js = (ui_dir / "app.js").read_text(encoding="utf-8")
    assert "sortTasksByStatusAndDate" in app_js
    assert "completed-divider" in app_js
    assert "calculateAdjustedTimestamp" in app_js

    style_css = (ui_dir / "style.css").read_text(encoding="utf-8")
    assert ".completed-divider" in style_css
    assert ".completed-divider-line" in style_css
    assert ".completed-divider-text" in style_css


def test_domain_filter_tasks_default_one_month():
    """Valida que por padrão (sem datas fornecidas), apenas tarefas do último mês (30 dias) são mantidas."""
    from datetime import datetime, timedelta

    now = datetime.now()
    recent_date = (now - timedelta(days=5)).strftime("%Y-%m-%d %H:%M:%S")
    old_date = (now - timedelta(days=45)).strftime("%Y-%m-%d %H:%M:%S")

    tasks = [
        {"id": "t_recent", "title": "Tarefa Recente", "created_at": recent_date},
        {"id": "t_old", "title": "Tarefa Antiga", "created_at": old_date},
    ]

    filtered = tarefas_domain.filter_tasks_by_date_range(tasks, default_one_month=True)
    assert len(filtered) == 1
    assert filtered[0]["id"] == "t_recent"

    # Se default_one_month=False e sem datas, retorna todas
    unfiltered = tarefas_domain.filter_tasks_by_date_range(tasks, default_one_month=False)
    assert len(unfiltered) == 2


def test_domain_filter_tasks_custom_range():
    """Valida o filtro por intervalo customizado de datas."""
    tasks = [
        {"id": "t1", "title": "Maio", "created_at": "2026-05-15 10:00:00"},
        {"id": "t2", "title": "Junho", "created_at": "2026-06-15 10:00:00"},
        {"id": "t3", "title": "Julho", "created_at": "2026-07-15 10:00:00"},
    ]

    filtered = tarefas_domain.filter_tasks_by_date_range(
        tasks,
        date_from="2026-06-01",
        date_to="2026-06-30"
    )
    assert len(filtered) == 1
    assert filtered[0]["id"] == "t2"

    # Apenas date_from
    filtered_from = tarefas_domain.filter_tasks_by_date_range(
        tasks,
        date_from="2026-06-01"
    )
    assert [t["id"] for t in filtered_from] == ["t2", "t3"]

    # Apenas date_to
    filtered_to = tarefas_domain.filter_tasks_by_date_range(
        tasks,
        date_to="2026-06-30"
    )
    assert [t["id"] for t in filtered_to] == ["t1", "t2"]


def test_domain_filter_tasks_parent_with_subtask_in_range():
    """Valida que uma tarefa-pai antiga é preservada se tiver uma subtarefa no intervalo filtrado."""
    from datetime import datetime, timedelta

    now = datetime.now()
    recent_date = (now - timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S")
    old_date = (now - timedelta(days=60)).strftime("%Y-%m-%d %H:%M:%S")

    tasks = [
        {"id": "parent_old", "parent_id": None, "title": "Pai Antigo", "created_at": old_date},
        {"id": "sub_recent", "parent_id": "parent_old", "title": "Filho Recente", "created_at": recent_date},
        {"id": "other_old", "parent_id": None, "title": "Outro Antigo", "created_at": old_date},
    ]

    filtered = tarefas_domain.filter_tasks_by_date_range(tasks, default_one_month=True)
    filtered_ids = [t["id"] for t in filtered]

    assert "parent_old" in filtered_ids
    assert "sub_recent" in filtered_ids
    assert "other_old" not in filtered_ids


def test_tarefas_api_date_filtering():
    """Valida os métodos get_tasks e filter_tasks_by_date expostos na TarefasApi."""
    api = TarefasApi()
    res1 = api.create_task("Task 1")
    assert res1["success"] is True

    # Chamada de filter_tasks_by_date
    res_filter = api.filter_tasks_by_date(default_one_month=True)
    assert res_filter["success"] is True
    assert len(res_filter["tasks"]) >= 1

    # Chamada com intervalo futuro que não deve conter a tarefa
    res_empty = api.filter_tasks_by_date(date_from="2099-01-01", date_to="2099-01-31")
    assert res_empty["success"] is True
    assert len(res_empty["tasks"]) == 0


def test_tarefas_ui_date_filter_components():
    """Valida que os componentes de filtro por data estão presentes na UI (HTML, CSS e JS)."""
    ui_dir = TAREFAS_DIR / "ui"

    html = (ui_dir / "index.html").read_text(encoding="utf-8")
    assert "dateFilterFrom" in html
    assert "dateFilterTo" in html
    assert "btnResetDateFilter" in html
    assert "btnAllDates" in html

    css = (ui_dir / "style.css").read_text(encoding="utf-8")
    assert ".date-filter-group" in css
    assert ".date-input" in css
    assert ".date-all-btn" in css

    app_js = (ui_dir / "app.js").read_text(encoding="utf-8")
    assert "getDateRangeBoundaries" in app_js
    assert "isTaskInDateRange" in app_js
    assert "toggleAllDatesFilter" in app_js
    assert "filter_tasks_by_date" in app_js


def test_tarefas_ui_quick_edit_icons_and_version_badge_compliance():
    """Valida a correção do ícone de edição rápida, conformidade da exclusividade de versão e layout flexbox."""
    ui_dir = TAREFAS_DIR / "ui"

    # 1. Validação de ausência de versão duplicada na UI (deve ficar apenas na barra de títulos)
    html = (ui_dir / "index.html").read_text(encoding="utf-8")
    assert "versionBadge" not in html, "Badge de versão não deve estar presente no HTML interno da UI"

    # 2. Validação dos ícones de edição rápida (deve usar 'edit', nunca 'edit-3')
    app_js = (ui_dir / "app.js").read_text(encoding="utf-8")
    assert 'data-icon="edit-3"' not in app_js, "Nenhum botão deve usar o ícone inválido 'edit-3'"
    assert 'data-icon="edit"' in app_js, "Os botões de edição rápida devem usar o ícone 'edit'"
    assert "versionBadge" not in app_js, "app.js não deve manipular elementos de badge de versão na UI"

    # 3. Validação de regras de layout para espaçamento e flex-shrink em abas detalhadas
    style_css = (ui_dir / "style.css").read_text(encoding="utf-8")
    assert ".detail-header-card" in style_css
    assert ".detail-markdown-section" in style_css
    assert ".detail-subtasks-section" in style_css
    assert ".native-desc-actions" in style_css
    assert "flex-shrink: 0;" in style_css


def test_tarefas_subtask_creation_via_chat_and_card_selection():
    """
    Valida os requisitos da issue #251:
    - Criação de subtarefa via chat sem window.prompt().
    - Funções prepareSubtaskCreation, cancelSubtaskCreation, clearSelection, selectTask, handleCardClick e handleChatCancel.
    - Estilos de destaque para card selecionado (.task-card.selected) e botões de subtarefa.
    - Criação de subtarefa via TarefasApi mantendo integridade dos dados e parent_id.
    """
    ui_dir = TAREFAS_DIR / "ui"
    app_js = (ui_dir / "app.js").read_text(encoding="utf-8")
    style_css = (ui_dir / "style.css").read_text(encoding="utf-8")
    index_html = (ui_dir / "index.html").read_text(encoding="utf-8")

    # 1. Sem prompt() modal intrusivo no app.js
    import re
    assert not re.search(r'\bprompt\(', app_js), "window.prompt() não deve ser chamado em app.js"

    # 2. Funções obrigatórias presentes e exportadas
    required_fns = [
        "prepareSubtaskCreation",
        "cancelSubtaskCreation",
        "clearSelection",
        "selectTask",
        "handleCardClick",
        "handleChatCancel",
    ]
    for fn in required_fns:
        assert fn in app_js, f"Função {fn} deve estar definida em app.js"
        assert f"window.{fn} = {fn};" in app_js, f"Função {fn} deve ser exportada para window em app.js"

    # 3. Estado reativo no app.js
    assert "selectedTaskId" in app_js
    assert "subtaskTargetId" in app_js

    # 4. Estilos CSS para card selecionado e elementos de subtarefa
    assert ".task-card.selected" in style_css
    assert "border-left:" in style_css or "border-color:" in style_css
    assert ".chat-btn-subtask" in style_css
    assert ".chat-edit-banner.subtask-mode" in style_css

    # 5. HTML contém botão de cancelamento configurado
    assert "handleChatCancel()" in index_html

    # 6. Teste de API: criação de tarefa raiz e posterior subtarefa via API
    api = TarefasApi()
    res_parent = api.create_task("Tarefa Principal Pai", "Descrição da tarefa pai")
    assert res_parent["success"] is True
    parent_id = res_parent["task"]["id"]

    res_sub = api.create_task("Subtarefa Criada via Chat", "Detalhes da subtarefa", parent_id=parent_id)
    assert res_sub["success"] is True
    assert res_sub["task"]["parent_id"] == parent_id
    assert res_sub["task"]["title"] == "Subtarefa Criada via Chat"

    # Valida presença na lista completa
    tasks = res_sub["tasks"]
    sub_found = next((t for t in tasks if t["id"] == res_sub["task"]["id"]), None)
    assert sub_found is not None
    assert sub_found["parent_id"] == parent_id


def test_tarefas_drag_and_drop_reorder_and_nesting():
    """
    Valida os requisitos da issue #252:
    - Suporte a 3 zonas de drag no frontend (top, center, bottom).
    - Presença do estilo .drag-over-center no CSS.
    - Prevenção de ciclos no frontend e no domínio.
    - Conversão de tarefa em subtarefa (aninhamento) via update_task.
    - Promoção de subtarefa para raiz via update_task(parent_id=None).
    """
    ui_dir = TAREFAS_DIR / "ui"
    app_js = (ui_dir / "app.js").read_text(encoding="utf-8")
    style_css = (ui_dir / "style.css").read_text(encoding="utf-8")

    # 1. Valida classes e lógica de 3 zonas no app.js
    assert "drag-over-top" in app_js
    assert "drag-over-center" in app_js
    assert "drag-over-bottom" in app_js
    assert "isDescendant" in app_js
    assert "window.isDescendant = isDescendant;" in app_js

    # 2. Valida estilos no CSS
    assert ".task-card.drag-over-center" in style_css
    assert ".task-card.drag-over-top" in style_css
    assert ".task-card.drag-over-bottom" in style_css

    # 3. Teste de domínio: conversão de tarefa raiz em subtarefa (aninhamento)
    api = TarefasApi()
    res1 = api.create_task("Tarefa Raiz A")
    res2 = api.create_task("Tarefa Raiz B")
    task_a_id = res1["task"]["id"]
    task_b_id = res2["task"]["id"]

    # Aninha Tarefa B sob Tarefa A
    res_nest = api.update_task(task_b_id, {"parent_id": task_a_id})
    assert res_nest["success"] is True
    assert res_nest["task"]["parent_id"] == task_a_id

    # 4. Desaninhamento: promove subtarefa B de volta para raiz
    res_unnest = api.update_task(task_b_id, {"parent_id": None})
    assert res_unnest["success"] is True
    assert res_unnest["task"]["parent_id"] is None

    # 5. Prevenção defensiva de ciclos
    # A não pode ser pai de si mesma
    with pytest.raises(ValueError, match="não pode ser pai de si mesma"):
        tarefas_domain.update_task(task_a_id, {"parent_id": task_a_id})

    # Cria hierarquia A -> B -> C
    api.update_task(task_b_id, {"parent_id": task_a_id})
    res3 = api.create_task("Subtarefa C", parent_id=task_b_id)
    task_c_id = res3["task"]["id"]

    # Tenta fazer A virar filha de C (ciclo!)
    with pytest.raises(ValueError, match="ciclos de dependência"):
        tarefas_domain.update_task(task_a_id, {"parent_id": task_c_id})


def test_tarefas_markdown_rendering_and_local_assets():
    """
    Valida a resolução da Issue #253:
    1. Presença dos bundles locais de markdown (markdown-field.js e markdown-field.css) em plugins/tarefas/ui/.
    2. Referência direta aos assets locais em plugins/tarefas/ui/index.html.
    3. Inicialização e ciclo de vida do MarkdownField em plugins/tarefas/ui/app.js.
    4. Estilização de integração no plugins/tarefas/ui/style.css.
    5. Execução do bundle com Node.js para garantir exportação de window.ToolboxMarkdown e parsing GFM sem erros.
    """
    import subprocess

    ui_dir = TAREFAS_DIR / "ui"
    js_file = ui_dir / "markdown-field.js"
    css_file = ui_dir / "markdown-field.css"

    # 1. Existência e integridade dos arquivos
    assert js_file.exists(), "markdown-field.js deve existir na pasta ui do plugin tarefas"
    assert css_file.exists(), "markdown-field.css deve existir na pasta ui do plugin tarefas"
    assert js_file.stat().st_size > 10000, "markdown-field.js deve ser o bundle autossuficiente completo"
    assert css_file.stat().st_size > 2000, "markdown-field.css deve conter as regras de estilo"

    # 2. index.html carrega localmente os assets
    html_content = (ui_dir / "index.html").read_text(encoding="utf-8")
    assert 'href="markdown-field.css"' in html_content, "index.html deve referenciar markdown-field.css localmente"
    assert 'src="markdown-field.js"' in html_content, "index.html deve referenciar markdown-field.js localmente"

    # 3. app.js instancia window.ToolboxMarkdown.MarkdownField em modo view
    app_js = (ui_dir / "app.js").read_text(encoding="utf-8")
    assert "window.ToolboxMarkdown.MarkdownField" in app_js
    assert "mode: 'view'" in app_js
    assert "updateDescHeaderButton(task.id, 'view')" in app_js
    assert "handleToggleDescriptionEdit" in app_js

    # 4. style.css possui regras de integração
    style_css = (ui_dir / "style.css").read_text(encoding="utf-8")
    assert ".detail-markdown-section .tb-reader-header" in style_css
    assert ".detail-markdown-section .tb-reader-body" in style_css

    # 5. Execução do bundle via Node para validar parsing GFM (títulos, listas, checklists, blocos de código)
    node_test_script = f"""
    const fs = require('fs');
    const vm = require('vm');
    const code = fs.readFileSync('{js_file}', 'utf8');
    const window = {{}};
    const sandbox = {{ window, console, setTimeout, clearTimeout }};
    vm.createContext(sandbox);
    vm.runInContext(code, sandbox);

    if (!sandbox.window.ToolboxMarkdown || !sandbox.window.ToolboxMarkdown.parseMarkdown) {{
      throw new Error('ToolboxMarkdown não exportado corretamente no window');
    }}

    const {{ parseMarkdown }} = sandbox.window.ToolboxMarkdown;
    const testMd = '# Titulo Principal\\n\\n- [x] Item 1 concluido\\n- [ ] Item 2 pendente\\n\\n```python\\nprint("hello")\\n```';
    const {{ html }} = parseMarkdown(testMd);

    if (!html.includes('tb-h1') || !html.includes('tb-task-checkbox') || !html.includes('tb-code-block')) {{
      throw new Error('Falha na renderização de elementos GFM: ' + html);
    }}
    console.log('OK');
    """
    result = subprocess.run(["node", "-e", node_test_script], capture_output=True, text=True)
    assert result.returncode == 0, f"Erro ao executar parseMarkdown no bundle: {result.stderr}"
    assert "OK" in result.stdout






