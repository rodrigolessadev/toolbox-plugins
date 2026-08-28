import os
import sys
from pathlib import Path
import pytest

PLUGINS_DIR = Path(__file__).resolve().parent.parent / "plugins"
if str(PLUGINS_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGINS_DIR))

from shared.db_utils import get_central_db_path


def test_get_central_db_path_resolution():
    path = get_central_db_path()
    assert isinstance(path, Path)
    assert path.name == "toolbox.db"
    assert path.parent.exists()

    if sys.platform == "win32" and "APPDATA" in os.environ:
        assert "com.toolbox.desktop" in str(path)
