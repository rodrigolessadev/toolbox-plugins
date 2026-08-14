import sys
from pathlib import Path

try:
    from shared.theme_utils import (
        THEME, setup_app_theme, create_card_frame, create_styled_entry,
        create_styled_text, create_primary_button, create_secondary_button,
        create_info_banner, create_modal_window, enable_high_dpi
    )
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from shared.theme_utils import (
        THEME, setup_app_theme, create_card_frame, create_styled_entry,
        create_styled_text, create_primary_button, create_secondary_button,
        create_info_banner, create_modal_window, enable_high_dpi
    )

DARK = {
    "bg": THEME["bg_base"],
    "bg2": THEME["bg_surface"],
    "input_bg": THEME["bg_input"],
    "fg": THEME["fg_primary"],
    "muted": THEME["fg_secondary"],
    "accent": THEME["accent"],
    "border": THEME["border"],
    "success": THEME["success"],
    "danger": THEME["danger"],
    "editable_bg": THEME["bg_input"],
    "editable_alt": THEME["bg_hover"],
}

#!/usr/bin/env python3
"""
Plugin: Gerador JSON (Em Desenvolvimento)
Esta é uma versão placeholder. Implementação completa em Etapa 6.
"""
import tkinter as tk
from tkinter import messagebox


def main():
    """Mostra mensagem informativa."""
    root = tk.Tk()
    root.withdraw()  # Esconde a janela principal
    
    messagebox.showinfo(
        "Gerador JSON",
        "🚧 Este plugin está em desenvolvimento.\n\n"
        "Versão completa em breve com templates para:\n"
        "• Pessoa (nome, email, idade, cidade, ativo)\n"
        "• Produto (nome, preço, estoque, categoria)\n"
        "• Usuário (id, username, email, role, createdAt)\n"
    )
    root.destroy()


if __name__ == "__main__":
    main()
