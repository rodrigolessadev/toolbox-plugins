"""
Módulo Centralizado de Design System e Tema Dark Suave (Soft Dark / Slate Navy).
Projetado para interfaces gráficas Tkinter de plugins do ecossistema Toolbox.
"""
import sys
from typing import Any, Callable, Dict, Optional

# Tokens do Design System Soft Dark (Slate/Navy)
THEME: Dict[str, str] = {
    # Superfícies
    "bg_base": "#0f1117",         # Fundo principal da janela
    "bg_surface": "#171b24",      # Fundo de cards, contêineres e abas
    "bg_input": "#1c222e",        # Fundo de campos de texto, combobox e áreas de código
    "bg_hover": "#242c3b",        # Hover de botões secundários e itens
    "bg_card_highlight": "#1e2634",# Card com destaque visual
    
    # Bordas e separadores
    "border": "#232a38",          # Borda sutil de cards e separadores (1px)
    "border_focus": "#4f8df9",    # Borda ativa de campos em foco
    "border_card": "#262f3f",     # Contorno refinado de cards
    
    # Tipografia
    "fg_primary": "#e2e8f0",      # Texto principal (Slate-200, nítido e suave)
    "fg_secondary": "#94a3b8",    # Labels secundárias, dicas e legendas (Slate-400)
    "fg_muted": "#64748b",        # Placeholders e elementos inativos (Slate-500)
    
    # Cores de Ação e Feedback
    "accent": "#3b82f6",          # Botões primários e destaque (Blue-500)
    "accent_hover": "#2563eb",    # Hover do botão primário
    "accent_fg": "#ffffff",       # Texto sobre o accent
    "success": "#10b981",         # Indicadores de sucesso (Emerald-500)
    "success_bg": "#064e3b",      # Fundo de badge de sucesso
    "warning": "#f59e0b",         # Alertas e avisos (Amber-500)
    "warning_bg": "#78350f",      # Fundo de badge de alerta
    "danger": "#ef4444",          # Erros e exclusões (Red-500)
    "danger_bg": "#7f1d1d",       # Fundo de badge de erro
}


def enable_high_dpi():
    """Ativa suporte a High-DPI no Windows para evitar fontes borradas em telas 1080p/4K."""
    if sys.platform == "win32":
        try:
            import ctypes
            # Shcore SetProcessDpiAwareness: 1 = Process_System_DPI_Aware, 2 = Process_Per_Monitor_DPI_Aware
            try:
                ctypes.windll.shcore.SetProcessDpiAwareness(1)
            except Exception:
                ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def setup_app_theme(root: Any) -> Any:
    """Configura tema visual global, estilos ttk e opções de popup no Tkinter."""
    enable_high_dpi()
    
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
    """Cria uma área ScrolledText integrada ao tema escuro suave."""
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
    """Cria uma janela modal Toplevel com tema escuro e foco capturado."""
    import tkinter as tk
    win = tk.Toplevel(parent)
    win.title(title)
    win.geometry(geometry)
    win.configure(bg=THEME["bg_base"])
    win.transient(parent)
    win.grab_set()
    return win
