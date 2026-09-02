import importlib.util
import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).parent.parent
DOMAIN_PATH = ROOT / "plugins" / "markdown-viewer" / "domain.py"
MAIN_PATH = ROOT / "plugins" / "markdown-viewer" / "main.py"

orig_domain = sys.modules.get("domain")
try:
    spec_domain = importlib.util.spec_from_file_location("md_viewer_domain", DOMAIN_PATH)
    md_domain = importlib.util.module_from_spec(spec_domain)
    spec_domain.loader.exec_module(md_domain)

    spec_main = importlib.util.spec_from_file_location("md_viewer_main", MAIN_PATH)
    md_main = importlib.util.module_from_spec(spec_main)
    spec_main.loader.exec_module(md_main)
finally:
    if orig_domain is not None:
        sys.modules["domain"] = orig_domain
    else:
        sys.modules.pop("domain", None)


def test_analyze_markdown():
    sample = """# Título Principal

Texto com várias palavras para análise.

## Subtítulo

- Item 1
- Item 2

```python
print("hello world")
```
"""
    stats = md_domain.analyze_markdown(sample)
    assert stats["heading_count"] == 2
    assert stats["line_count"] > 5
    assert stats["word_count"] > 10
    assert stats["code_block_count"] == 1
    assert stats["read_time_min"] >= 1


def test_read_and_save_markdown_file(tmp_path: Path):
    test_file = tmp_path / "teste.md"
    content = "# Documento de Teste\n\nConteúdo salvo com sucesso."

    res_save = md_domain.save_markdown_file(str(test_file), content)
    assert res_save["success"] is True
    assert res_save["filename"] == "teste.md"

    res_read = md_domain.read_markdown_file(str(test_file))
    assert res_read["success"] is True
    assert res_read["content"] == content
    assert res_read["stats"]["heading_count"] == 1


def test_read_markdown_file_errors():
    res_none = md_domain.read_markdown_file("")
    assert res_none["success"] is False

    res_not_found = md_domain.read_markdown_file("caminho_inexistente_12345.md")
    assert res_not_found["success"] is False


def test_export_html_document():
    doc = md_domain.export_html_document("Meu Relatório", "<h1>Título</h1><p>Parágrafo</p>")
    assert "<!DOCTYPE html>" in doc
    assert "<title>Meu Relatório</title>" in doc
    assert "<h1>Título</h1>" in doc


def test_file_text_icon_and_taskbar_helper():
    icon_path = md_domain.FILE_TEXT_ICON_PATH
    assert icon_path.exists()
    assert icon_path.suffix == ".ico"
    assert icon_path.stat().st_size > 0

    res = md_domain.set_window_taskbar_icon(icon_path=icon_path, hwnd=None)
    assert isinstance(res, bool)


def test_markdown_viewer_api(tmp_path: Path):
    api = md_main.MarkdownViewerApi()
    test_file = tmp_path / "api_test.md"

    res_save = api.save_file(str(test_file), "Conteúdo API")
    assert res_save["success"] is True

    res_read = api.read_file(str(test_file))
    assert res_read["success"] is True
    assert res_read["content"] == "Conteúdo API"

    res_stats = api.analyze_text("# Teste")
    assert res_stats["success"] is True
    assert res_stats["stats"]["heading_count"] == 1

    res_info = api.get_file_info(str(test_file))
    assert res_info["success"] is True
    assert res_info["exists"] is True
    assert "mtime" in res_info

    res_ver = api.get_plugin_version()
    assert res_ver["success"] is True
    assert "version" in res_ver

    res_title = api.set_window_title("Teste — Visualizador de Markdown v1.6.1")
    assert res_title["success"] is True


def test_markdown_viewer_ui_tab_elements():
    ui_html = ROOT / "plugins" / "markdown-viewer" / "ui" / "index.html"
    ui_js = ROOT / "plugins" / "markdown-viewer" / "ui" / "app.js"
    ui_css = ROOT / "plugins" / "markdown-viewer" / "ui" / "style.css"

    assert ui_html.exists()
    assert ui_js.exists()
    assert ui_css.exists()

    html_content = ui_html.read_text(encoding="utf-8")
    assert 'id="tabBarContainer"' in html_content
    assert 'id="tabsList"' in html_content
    assert 'id="btnNewTab"' in html_content
    assert 'id="tabContextMenu"' in html_content
    assert 'id="modalCloseConfirm"' in html_content
    assert 'id="pluginVersionBadge"' in html_content

    js_content = ui_js.read_text(encoding="utf-8")
    assert "createTab" in js_content
    assert "activateTab" in js_content
    assert "handleCloseTab" in js_content
    assert "openOrFocusFile" in js_content
    assert "handleSaveAllFiles" in js_content
    assert "handleTabContextMenu" in js_content
    assert "tabBarContainer.addEventListener('dblclick'" in js_content
    assert "document.title =" in js_content
    assert "set_window_title" in js_content

    css_content = ui_css.read_text(encoding="utf-8")
    assert ".tab-bar-container" in css_content
    assert ".tab-item" in css_content
    assert ".tab-close-btn" in css_content
    assert ".tab-context-menu" in css_content
    assert ".modal-overlay" in css_content


def test_analyze_markdown_indented_code_blocks():
    sample = """# Teste Indentação

Texto explicativo.

  ```java
  CompanyEntity company = companyRepository.findOneOrFail(employee.getEmployer().getId());
  dto.employeeData.consistBudget = remunerationConfigRepository.getConsistBudgetByCompany(company.getHeadquarter());
  ```

Outro trecho com tis:

    ~~~python
    def calculate():
        return 42
    ~~~
"""
    stats = md_domain.analyze_markdown(sample)
    assert stats["heading_count"] == 1
    assert stats["code_block_count"] == 2
    assert stats["word_count"] > 10


def test_markdown_viewer_ui_text_selection_and_indented_code_parser():
    ui_css = ROOT / "plugins" / "markdown-viewer" / "ui" / "style.css"
    ui_parser = ROOT / "plugins" / "markdown-viewer" / "ui" / "vendor" / "marked_parser.js"
    ui_html = ROOT / "plugins" / "markdown-viewer" / "ui" / "index.html"

    assert ui_css.exists()
    assert ui_parser.exists()
    assert ui_html.exists()

    css_content = ui_css.read_text(encoding="utf-8")
    assert ".preview-pane" in css_content
    assert "user-select: text;" in css_content
    assert "-webkit-user-select: text;" in css_content
    assert ".preview-content *" in css_content

    parser_content = ui_parser.read_text(encoding="utf-8")
    # Confirma suporte a cercas com atributos e blocos indentados
    assert "openCodeMatch" in parser_content
    assert "codeIndentLen" in parser_content
    assert "codeFenceChar" in parser_content
    assert "closeFencePattern" in parser_content
    assert "isIndentedCodeStart" in parser_content

    html_content = ui_html.read_text(encoding="utf-8")
    assert "?v=" in html_content


def test_dynamic_tab_title_helpers():
    ui_js = ROOT / "plugins" / "markdown-viewer" / "ui" / "app.js"
    assert ui_js.exists()
    js_content = ui_js.read_text(encoding="utf-8")

    assert "extractFirstMarkdownTitle" in js_content
    assert "sanitizeHeadingText" in js_content
    assert "getTabDisplayName" in js_content
    assert "getSuggestedFilename" in js_content


def test_analyze_markdown_pure_indented_code_blocks():
    sample = """# Documento com Código Indentado

Parágrafo explicativo.

    def process_data(item):
        return item * 2

Outro texto após código.

- Item de Lista 1
  ```sql -- busca avancada
  SELECT id, nome FROM clientes WHERE status = 'ativo';
  ```
- Item de Lista 2
"""
    stats = md_domain.analyze_markdown(sample)
    assert stats["heading_count"] == 1
    assert stats["code_block_count"] == 2
    assert stats["line_count"] > 10




