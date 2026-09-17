import json
import subprocess
from pathlib import Path
import pytest

ROOT = Path(__file__).parent.parent
PACKAGES_DIR = ROOT / "packages"
SHARED_MD_DIR = PACKAGES_DIR / "shared-markdown"
SHARED_UI_MD_DIR = ROOT / "plugins" / "shared" / "ui" / "markdown"


def test_package_structure_and_manifest():
    """Valida que o pacote @toolbox-plugins/shared-markdown existe com estrutura correta."""
    assert SHARED_MD_DIR.exists(), "Diretório packages/shared-markdown deve existir"
    
    pkg_json_file = SHARED_MD_DIR / "package.json"
    assert pkg_json_file.exists(), "package.json deve existir em packages/shared-markdown"
    
    pkg_data = json.loads(pkg_json_file.read_text(encoding="utf-8"))
    assert pkg_data.get("name") == "@toolbox-plugins/shared-markdown"
    assert pkg_data.get("version") == "1.0.0"
    assert pkg_data.get("main") == "src/index.js"
    assert "exports" in pkg_data
    assert "." in pkg_data["exports"]
    assert "./style.css" in pkg_data["exports"]

    # Valida arquivos fontes
    src_dir = SHARED_MD_DIR / "src"
    assert (src_dir / "index.js").exists(), "src/index.js deve existir"
    assert (src_dir / "markdown-field.js").exists(), "src/markdown-field.js deve existir"
    assert (src_dir / "markdown-reader.js").exists(), "src/markdown-reader.js deve existir"
    assert (src_dir / "markdown-editor.js").exists(), "src/markdown-editor.js deve existir"
    assert (src_dir / "parser.js").exists(), "src/parser.js deve existir"
    assert (src_dir / "style.css").exists(), "src/style.css deve existir"
    assert (src_dir / "index.d.ts").exists(), "src/index.d.ts deve existir"
    assert (SHARED_MD_DIR / "README.md").exists(), "README.md deve existir"


def test_distribution_bundle_structure():
    """Valida que a distribuição em plugins/shared/ui/markdown existe para consumo autossuficiente."""
    assert SHARED_UI_MD_DIR.exists(), "Diretório plugins/shared/ui/markdown deve existir"
    assert (SHARED_UI_MD_DIR / "markdown-field.js").exists(), "markdown-field.js deve existir"
    assert (SHARED_UI_MD_DIR / "markdown-field.css").exists(), "markdown-field.css deve existir"
    assert (SHARED_UI_MD_DIR / "index.js").exists(), "index.js deve existir"

    bundle_content = (SHARED_UI_MD_DIR / "markdown-field.js").read_text(encoding="utf-8")
    assert "class MarkdownField" in bundle_content
    assert "class MarkdownReader" in bundle_content
    assert "class MarkdownEditor" in bundle_content
    assert "function parseMarkdown" in bundle_content
    assert "function sanitizeHtml" in bundle_content
    assert "ToolboxMarkdown" in bundle_content
    assert "customElements.define('markdown-field'" in bundle_content

    # Garante que o bundle não possui palavras-chave 'export ' soltas que quebram scripts clássicos em pywebview
    import re
    assert not re.search(r"^\s*export\s+(function|class|const|let|var|default)\b", bundle_content, re.MULTILINE), \
        "markdown-field.js não deve conter declarações 'export' no escopo global para compatibilidade com script clássico"


def test_shared_markdown_node_tests():
    """Executa a suíte de testes unitários do Node.js para o componente de Markdown."""
    test_files = [
        str(SHARED_MD_DIR / "test" / "parser.test.js"),
        str(SHARED_MD_DIR / "test" / "markdown-field.test.js"),
    ]
    cmd = ["node", "--test"] + test_files
    result = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
    assert result.returncode == 0, f"Testes Node falharam:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    assert ("pass 16" in result.stdout or "pass 15" in result.stdout)
    assert "fail 0" in result.stdout

