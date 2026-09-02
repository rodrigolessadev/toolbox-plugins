"""
Testes unitários para persistência de sessão e autosave temporário (Hot Exit) no Visualizador de Markdown.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

import importlib.util

ROOT = Path(__file__).parent.parent
DOMAIN_PATH = ROOT / "plugins" / "markdown-viewer" / "domain.py"
MAIN_PATH = ROOT / "plugins" / "markdown-viewer" / "main.py"

orig_domain = sys.modules.get("domain")
try:
    spec_domain = importlib.util.spec_from_file_location("md_viewer_domain_session", DOMAIN_PATH)
    domain = importlib.util.module_from_spec(spec_domain)
    spec_domain.loader.exec_module(domain)

    spec_main = importlib.util.spec_from_file_location("md_viewer_main_session", MAIN_PATH)
    md_main = importlib.util.module_from_spec(spec_main)
    spec_main.loader.exec_module(md_main)
    MarkdownViewerApi = md_main.MarkdownViewerApi
finally:
    if orig_domain is not None:
        sys.modules["domain"] = orig_domain
    else:
        sys.modules.pop("domain", None)


def test_session_save_and_load(tmp_path: Path, monkeypatch):
    """Valida o salvamento e o carregamento completo do estado da sessão e snapshots."""
    monkeypatch.setattr(domain, "get_session_dir", lambda: tmp_path)

    session_data = {
        "activeTabId": "tab-2",
        "viewMode": "split",
        "theme": "dark",
        "tabs": [
            {
                "id": "tab-1",
                "title": "Documento 1.md",
                "filePath": "C:/temp/doc1.md",
                "isDirty": False,
                "savedContent": "# Doc 1",
                "lastMtime": 123456789,
                "scrollTop": 100,
                "cursorPos": {"start": 5, "end": 5}
            },
            {
                "id": "tab-2",
                "title": "sem-titulo-1.md",
                "filePath": "",
                "isDirty": True,
                "savedContent": "",
                "lastMtime": 0,
                "scrollTop": 0,
                "cursorPos": {"start": 10, "end": 10}
            }
        ]
    }

    snapshots = {
        "tab-1": "# Doc 1",
        "tab-2": "# Conteúdo Novo Não Salvo\nTexto importante digitado pelo usuário."
    }

    # Salva sessão
    res_save = domain.save_session(session_data, snapshots)
    assert res_save["success"] is True
    assert (tmp_path / "session.json").exists()
    assert (tmp_path / "tab-1.tmp").exists()
    assert (tmp_path / "tab-2.tmp").exists()

    # Carrega sessão
    res_load = domain.load_session()
    assert res_load["success"] is True
    assert res_load["hasSession"] is True
    loaded = res_load["data"]

    assert loaded["activeTabId"] == "tab-2"
    assert loaded["viewMode"] == "split"
    assert len(loaded["tabs"]) == 2

    # Verifica se os conteúdos dos snapshots foram restaurados nas abas correspondentes
    tab1 = next(t for t in loaded["tabs"] if t["id"] == "tab-1")
    assert tab1["content"] == "# Doc 1"
    assert tab1["isDirty"] is False

    tab2 = next(t for t in loaded["tabs"] if t["id"] == "tab-2")
    assert tab2["content"] == "# Conteúdo Novo Não Salvo\nTexto importante digitado pelo usuário."
    assert tab2["isDirty"] is True


def test_session_cleanup_orphaned_snapshots(tmp_path: Path, monkeypatch):
    """Valida a remoção de snapshots de abas que não estão mais na lista de abas abertas."""
    monkeypatch.setattr(domain, "get_session_dir", lambda: tmp_path)

    # Cria arquivo órfão
    (tmp_path / "tab-old.tmp").write_text("conteúdo antigo", encoding="utf-8")

    session_data = {
        "activeTabId": "tab-1",
        "tabs": [{"id": "tab-1", "title": "Doc 1", "filePath": ""}]
    }
    snapshots = {"tab-1": "novo conteúdo"}

    domain.save_session(session_data, snapshots)

    assert (tmp_path / "tab-1.tmp").exists()
    assert not (tmp_path / "tab-old.tmp").exists()


def test_delete_tab_snapshot(tmp_path: Path, monkeypatch):
    """Valida a exclusão individual do snapshot de uma aba."""
    monkeypatch.setattr(domain, "get_session_dir", lambda: tmp_path)

    tmp_file = tmp_path / "tab-5.tmp"
    tmp_file.write_text("conteúdo temporário", encoding="utf-8")
    assert tmp_file.exists()

    res = domain.delete_tab_snapshot("tab-5")
    assert res["success"] is True
    assert not tmp_file.exists()


def test_clear_all_session(tmp_path: Path, monkeypatch):
    """Valida a limpeza total de todos os arquivos de sessão."""
    monkeypatch.setattr(domain, "get_session_dir", lambda: tmp_path)

    (tmp_path / "session.json").write_text("{}", encoding="utf-8")
    (tmp_path / "tab-1.tmp").write_text("content", encoding="utf-8")

    res = domain.clear_all_session()
    assert res["success"] is True
    assert not (tmp_path / "session.json").exists()
    assert not (tmp_path / "tab-1.tmp").exists()


def test_markdown_viewer_api_session_bridge(tmp_path: Path, monkeypatch):
    """Valida os métodos expostos na JS API bridge MarkdownViewerApi."""
    monkeypatch.setattr(domain, "get_session_dir", lambda: tmp_path)

    api = MarkdownViewerApi()

    # Salva sessão
    save_res = api.save_session(
        {"activeTabId": "tab-1", "tabs": [{"id": "tab-1", "title": "Nota.md"}]},
        {"tab-1": "Conteúdo salvo via API"}
    )
    assert save_res["success"] is True

    # Carrega sessão
    load_res = api.load_session()
    assert load_res["success"] is True
    assert load_res["hasSession"] is True
    assert load_res["data"]["tabs"][0]["content"] == "Conteúdo salvo via API"

    # Delete snapshot
    del_res = api.delete_tab_snapshot("tab-1")
    assert del_res["success"] is True

    # Clear session
    clear_res = api.clear_session()
    assert clear_res["success"] is True
