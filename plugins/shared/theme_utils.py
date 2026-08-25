"""
Utilitário de temas e design system para plugins Desktop (Tkinter).
Suporta temas Claro e Escuro dinamicamente com tokens alinhados ao Toolbox.
"""

import os
import sys
from typing import Any, Callable, Dict, Optional

# Design Tokens: Modo Escuro (Dark Theme)
THEME_DARK: Dict[str, str] = {
    "bg_base": "#0e1014",         # Fundo principal da janela
    "bg_surface": "#161a21",      # Fundo elevado / container de cards
    "bg_elev": "#1f242d",         # Superfície secundária de elevação
    "bg_input": "#12151c",        # Fundo de campos de texto e inputs
    "bg_hover": "#262c36",        # Hover e estados ativos
    "border": "#2b3240",          # Bordas padrão de componentes
    "border_card": "#232936",     # Bordas de cards e separadores
    "border_focus": "#6aa3ff",    # Borda em foco (accent)
    "fg_primary": "#e8eaed",      # Texto principal de alto contraste
    "fg_secondary": "#8b94a3",    # Texto atenuado / legendas
    "fg_muted": "#606979",        # Texto desabilitado
    "accent": "#6aa3ff",          # Acento primário do Toolbox
    "accent_hover": "#5493f0",    # Acento em hover
    "accent_fg": "#ffffff",       # Texto sobre o acento primário
    "success": "#10b981",         # Indicadores de sucesso (Emerald-500)
    "success_bg": "#064e3b",      # Fundo de badge de sucesso
    "warning": "#f59e0b",         # Alertas e avisos (Amber-500)
    "warning_bg": "#78350f",      # Fundo de badge de alerta
    "danger": "#ef4444",          # Erros e exclusões (Red-500)
    "danger_bg": "#7f1d1d",       # Fundo de badge de erro
}

# Design Tokens: Modo Claro (Light Theme)
THEME_LIGHT: Dict[str, str] = {
    "bg_base": "#f4f5f8",         # Fundo principal claro
    "bg_surface": "#ffffff",      # Fundo elevado / cards brancos
    "bg_elev": "#eaecef",         # Superfície secundária clara
    "bg_input": "#ffffff",        # Fundo de campos de texto
    "bg_hover": "#f0f2f5",        # Hover claro
    "border": "#e2e8f0",          # Bordas sutis claras
    "border_card": "#cbd5e1",     # Bordas de cards
    "border_focus": "#2563eb",    # Borda em foco (azul vivo)
    "fg_primary": "#0e1014",      # Texto principal escuro de alto contraste
    "fg_secondary": "#475569",    # Texto atenuado / legendas
    "fg_muted": "#94a3b8",        # Texto desabilitado
    "accent": "#2563eb",          # Acento primário claro (Blue-600)
    "accent_hover": "#1d4ed8",    # Acento em hover (Blue-700)
    "accent_fg": "#ffffff",       # Texto sobre o acento primário
    "success": "#10b981",         # Indicadores de sucesso
    "success_bg": "#d1fae5",      # Fundo de badge de sucesso
    "warning": "#f59e0b",         # Alertas e avisos
    "warning_bg": "#fef3c7",      # Fundo de badge de alerta
    "danger": "#ef4444",          # Erros e exclusões
    "danger_bg": "#fee2e2",       # Fundo de badge de erro
}

def resolve_theme_mode(theme: Optional[str] = None) -> str:
    """Resolve o modo de tema ('dark' ou 'light') a partir do parâmetro, CLI ou env var."""
    if theme in ("dark", "light"):
        return theme

    # 1. Argumentos CLI (--theme light / --theme dark / --theme=light)
    if sys.argv:
        for i, arg in enumerate(sys.argv):
            if arg == "--theme" and i + 1 < len(sys.argv):
                val = sys.argv[i + 1].strip().lower()
                if val in ("dark", "light"):
                    return val
            elif arg.startswith("--theme="):
                val = arg.split("=", 1)[1].strip().lower()
                if val in ("dark", "light"):
                    return val

    # 2. Variável de ambiente TOOLBOX_THEME
    env_theme = os.environ.get("TOOLBOX_THEME", "").strip().lower()
    if env_theme in ("dark", "light"):
        return env_theme

    return "dark"


def get_theme_tokens(mode: Optional[str] = None) -> Dict[str, str]:
    """Retorna um dicionário com os tokens do tema correspondente."""
    m = resolve_theme_mode(mode)
    return dict(THEME_LIGHT if m == "light" else THEME_DARK)


# Dicionário de compatibilidade global (atualizado por setup_app_theme)
THEME: Dict[str, str] = get_theme_tokens()


def enable_high_dpi():
    """Ativa suporte a High-DPI no Windows para evitar fontes borradas em telas 1080p/4K."""
    if sys.platform == "win32":
        try:
            import ctypes
            try:
                ctypes.windll.shcore.SetProcessDpiAwareness(1)
            except Exception:
                ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def setup_app_theme(root: Any, theme: Optional[str] = None) -> Any:
    """Configura tema visual global, estilos ttk e opções de popup no Tkinter."""
    enable_high_dpi()
    
    tokens = get_theme_tokens(theme)
    THEME.clear()
    THEME.update(tokens)

    try:
        root.configure(bg=THEME["bg_base"])
    except Exception:
        pass

    try:
        from tkinter import ttk
        style = ttk.Style(root)
        try:
            style.theme_use("clam")
        except Exception:
            pass

        style.configure(".", background=THEME["bg_base"], foreground=THEME["fg_primary"])
        style.configure("TFrame", background=THEME["bg_base"])
        style.configure("Card.TFrame", background=THEME["bg_surface"])
        
        # Labels
        style.configure("TLabel", background=THEME["bg_base"], foreground=THEME["fg_primary"], font=("Segoe UI", 9))
        style.configure("Card.TLabel", background=THEME["bg_surface"], foreground=THEME["fg_primary"], font=("Segoe UI", 9))
        style.configure("Title.TLabel", font=("Segoe UI", 13, "bold"), foreground=THEME["accent"], background=THEME["bg_base"])
        style.configure("Section.TLabel", font=("Segoe UI", 10, "bold"), foreground=THEME["fg_primary"], background=THEME["bg_surface"])
        style.configure("Muted.TLabel", foreground=THEME["fg_secondary"], font=("Segoe UI", 8), background=THEME["bg_base"])
        style.configure("CardMuted.TLabel", foreground=THEME["fg_secondary"], font=("Segoe UI", 8), background=THEME["bg_surface"])

        # Inputs
        style.configure("TEntry",
            fieldbackground=THEME["bg_input"],
            foreground=THEME["fg_primary"],
            insertcolor=THEME["fg_primary"],
            bordercolor=THEME["border"],
            lightcolor=THEME["border"],
            darkcolor=THEME["border"]
        )
        style.map("TEntry",
            fieldbackground=[("focus", THEME["bg_hover"]), ("readonly", THEME["bg_input"])],
            foreground=[("disabled", THEME["fg_muted"])],
            bordercolor=[("focus", THEME["border_focus"])]
        )

        # Combobox
        style.configure("TCombobox",
            fieldbackground=THEME["bg_input"],
            background=THEME["bg_surface"],
            foreground=THEME["fg_primary"],
            arrowcolor=THEME["fg_primary"],
            bordercolor=THEME["border"]
        )
        style.map("TCombobox",
            fieldbackground=[("readonly", THEME["bg_input"]), ("focus", THEME["bg_hover"])],
            selectbackground=[("readonly", THEME["accent"])],
            selectforeground=[("readonly", THEME["accent_fg"])]
        )

        # Checkbutton & Radiobutton
        style.configure("TCheckbutton", background=THEME["bg_base"], foreground=THEME["fg_primary"], font=("Segoe UI", 9))
        style.configure("Card.TCheckbutton", background=THEME["bg_surface"], foreground=THEME["fg_primary"], font=("Segoe UI", 9))
        style.configure("TRadiobutton", background=THEME["bg_base"], foreground=THEME["fg_primary"], font=("Segoe UI", 9))

        # Popups de Listbox do Combobox
        try:
            root.option_add("*TCombobox*Listbox.background", THEME["bg_input"])
            root.option_add("*TCombobox*Listbox.foreground", THEME["fg_primary"])
            root.option_add("*TCombobox*Listbox.selectBackground", THEME["accent"])
            root.option_add("*TCombobox*Listbox.selectForeground", THEME["accent_fg"])
        except Exception:
            pass

        return style
    except Exception:
        return None


def create_card_frame(parent: Any, **kwargs) -> Any:
    """Cria um contêiner estilo Card com fundo elevado e borda sutil."""
    import tkinter as tk
    opts = {
        "bg": THEME["bg_surface"],
        "bd": 1,
        "relief": "solid",
        "highlightthickness": 1,
        "highlightbackground": THEME["border_card"],
    }
    opts.update(kwargs)
    return tk.Frame(parent, **opts)


def create_styled_entry(parent: Any, textvariable: Any = None, **kwargs) -> Any:
    """Cria um campo Entry com contraste calibrado, cursor visível e highlight de foco."""
    import tkinter as tk
    opts = {
        "font": ("Segoe UI", 9),
        "bg": THEME["bg_input"],
        "fg": THEME["fg_primary"],
        "insertbackground": THEME["fg_primary"],
        "relief": "solid",
        "bd": 1,
        "highlightthickness": 1,
        "highlightbackground": THEME["border"],
        "highlightcolor": THEME["border_focus"]
    }
    if textvariable is not None:
        opts["textvariable"] = textvariable
    opts.update(kwargs)
    return tk.Entry(parent, **opts)


def create_styled_text(parent: Any, **kwargs) -> Any:
    """Cria uma área ScrolledText integrada ao tema ativo."""
    from tkinter.scrolledtext import ScrolledText
    opts = {
        "font": ("Consolas", 9),
        "bg": THEME["bg_input"],
        "fg": THEME["fg_primary"],
        "insertbackground": THEME["fg_primary"],
        "relief": "solid",
        "bd": 1,
        "highlightthickness": 1,
        "highlightbackground": THEME["border"]
    }
    opts.update(kwargs)
    return ScrolledText(parent, **opts)


def create_primary_button(parent: Any, text: str, command: Optional[Callable] = None, **kwargs) -> Any:
    """Cria um botão primário destacado com hover azul suave."""
    import tkinter as tk
    opts = {
        "text": text,
        "command": command,
        "font": ("Segoe UI", 9, "bold"),
        "bg": THEME["accent"],
        "fg": THEME["accent_fg"],
        "activebackground": THEME["accent_hover"],
        "activeforeground": THEME["accent_fg"],
        "relief": "flat",
        "padx": 16,
        "pady": 6,
        "cursor": "hand2"
    }
    opts.update(kwargs)
    return tk.Button(parent, **opts)


def create_secondary_button(parent: Any, text: str, command: Optional[Callable] = None, **kwargs) -> Any:
    """Cria um botão secundário neutro com contorno sutil e hover suave."""
    import tkinter as tk
    opts = {
        "text": text,
        "command": command,
        "font": ("Segoe UI", 9),
        "bg": THEME["bg_surface"],
        "fg": THEME["fg_primary"],
        "activebackground": THEME["bg_hover"],
        "activeforeground": THEME["fg_primary"],
        "relief": "solid",
        "bd": 1,
        "highlightthickness": 1,
        "highlightbackground": THEME["border"],
        "padx": 12,
        "pady": 4,
        "cursor": "hand2"
    }
    opts.update(kwargs)
    return tk.Button(parent, **opts)


def create_info_banner(parent: Any, text: str, **kwargs) -> Any:
    """Cria um card informativo/banner contextual no topo do layout."""
    import tkinter as tk
    card = create_card_frame(parent, **kwargs)
    label = tk.Label(
        card,
        text=text,
        font=("Segoe UI", 9),
        bg=THEME["bg_surface"],
        fg=THEME["fg_secondary"]
    )
    label.pack(padx=12, pady=6, anchor="w")
    return card


def create_modal_window(parent: Any, title: str, geometry: str = "800x580") -> Any:
    """Cria uma janela modal Toplevel com tema ativo e foco capturado."""
    import tkinter as tk
    win = tk.Toplevel(parent)
    win.title(title)
    win.geometry(geometry)
    win.configure(bg=THEME["bg_base"])
    win.transient(parent)
    win.grab_set()
    return win
