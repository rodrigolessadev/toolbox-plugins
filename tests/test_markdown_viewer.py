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
