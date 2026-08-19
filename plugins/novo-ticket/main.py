#!/usr/bin/env python3
"""
Plugin: Novo Ticket
Criação de diretório padronizado no formato CLIENTE_TICKET (em caixa alta)
dentro do diretório inicial especificado.
"""

import json
import os
import subprocess
import sys
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Optional, Any, Callable

# Garante import do módulo compartilhado theme_utils ou fornece fallback autônomo
try:
    try:
        from shared.theme_utils import (
            THEME,
            setup_app_theme,
            create_card_frame,
            create_styled_entry,
            create_primary_button,
            create_secondary_button,
            enable_high_dpi,
        )
    except ImportError:
        shared_dir = str(Path(__file__).resolve().parent.parent)
        if shared_dir not in sys.path:
            sys.path.insert(0, shared_dir)
        from shared.theme_utils import (
            THEME,
            setup_app_theme,
            create_card_frame,
            create_styled_entry,
            create_primary_button,
            create_secondary_button,
            enable_high_dpi,
        )
except Exception:
    # Fallback autossuficiente para execução standalone em ambientes de produção/Marketplace
    THEME = {
        "bg_base": "#0e1014",
        "bg_surface": "#161a21",
        "bg_input": "#161a21",
        "bg_hover": "#1e232d",
        "fg_primary": "#e8eaed",
        "fg_secondary": "#8b94a3",
        "fg_muted": "#555d6e",
        "border": "#2b3240",
        "border_card": "#232834",
        "border_focus": "#6aa3ff",
        "accent": "#3b82f6",
        "accent_hover": "#60a5fa",
        "accent_fg": "#ffffff",
        "success": "#10b981",
        "danger": "#ef4444",
    }

    def enable_high_dpi():
        if sys.platform == "win32":
            try:
                import ctypes
                try:
                    ctypes.windll.shcore.SetProcessDpiAwareness(1)
                except Exception:
                    ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass

    def setup_app_theme(root: Any) -> Any:
        enable_high_dpi()
        try:
            root.configure(bg=THEME["bg_base"])
            style = ttk.Style(root)
            try:
                style.theme_use("clam")
            except Exception:
                pass
            style.configure(".", background=THEME["bg_base"], foreground=THEME["fg_primary"])
            style.configure("TFrame", background=THEME["bg_base"])
            style.configure("TLabel", background=THEME["bg_base"], foreground=THEME["fg_primary"])
            style.configure("TEntry", fieldbackground=THEME["bg_input"], foreground=THEME["fg_primary"])
            return style
        except Exception:
            return None

    def create_card_frame(parent: Any, **kwargs) -> Any:
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
        opts = {
            "font": ("Segoe UI", 9),
            "bg": THEME["bg_input"],
            "fg": THEME["fg_primary"],
            "insertbackground": THEME["fg_primary"],
            "relief": "solid",
            "bd": 1,
            "highlightthickness": 1,
            "highlightbackground": THEME["border"],
            "highlightcolor": THEME["border_focus"],
        }
        if textvariable is not None:
            opts["textvariable"] = textvariable
        opts.update(kwargs)
        return tk.Entry(parent, **opts)

    def create_primary_button(parent: Any, text: str, command: Optional[Callable] = None, **kwargs) -> Any:
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
            "cursor": "hand2",
        }
        opts.update(kwargs)
        return tk.Button(parent, **opts)

    def create_secondary_button(parent: Any, text: str, command: Optional[Callable] = None, **kwargs) -> Any:
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
            "cursor": "hand2",
        }
        opts.update(kwargs)
        return tk.Button(parent, **opts)

from domain import (
    sanitize_component,
    format_ticket_folder_name,
    validate_base_dir,
    create_ticket_directory,
)


CONFIG_DIR = Path.home() / ".toolbox" / "novo-ticket"
CONFIG_FILE = CONFIG_DIR / "config.json"


def load_last_base_dir() -> str:
    """Carrega o último diretório base utilizado."""
    try:
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                last_dir = data.get("last_base_dir", "")
                if last_dir and Path(last_dir).exists():
                    return last_dir
    except Exception:
        pass
    return str(Path.home())


def save_last_base_dir(base_dir: str) -> None:
    """Salva o último diretório base utilizado."""
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump({"last_base_dir": base_dir}, f, indent=2)
    except Exception:
        pass


def open_in_explorer(path: Path) -> None:
    """Abre o diretório no explorador de arquivos do sistema operacional."""
    try:
        if sys.platform == "win32":
            os.startfile(str(path))
        elif sys.platform == "darwin":
            subprocess.run(["open", str(path)], check=False)
        else:
            subprocess.run(["xdg-open", str(path)], check=False)
    except Exception as ex:
        messagebox.showerror("Erro", f"Não foi possível abrir o diretório: {ex}")


class NovoTicketApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Novo Ticket — Toolbox")
        self.root.geometry("560x540")
        self.root.minsize(520, 500)

        enable_high_dpi()
        setup_app_theme(self.root)

        self.last_created_path: Optional[Path] = None

        self._build_ui()
        self._bind_events()
        self._update_preview()

    def _build_ui(self):
        # Container Principal com padding
        main_frame = tk.Frame(self.root, bg=THEME["bg_base"])
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        # Cabeçalho
        header_frame = tk.Frame(main_frame, bg=THEME["bg_base"])
        header_frame.pack(fill="x", pady=(0, 16))

        title_lbl = tk.Label(
            header_frame,
            text="Iniciar Novo Ticket",
            font=("Segoe UI", 14, "bold"),
            bg=THEME["bg_base"],
            fg=THEME["fg_primary"],
        )
        title_lbl.pack(anchor="w")

        subtitle_lbl = tk.Label(
            header_frame,
            text="Cria um diretório padronizado no formato CLIENTE_TICKET em caixa alta.",
            font=("Segoe UI", 9),
            bg=THEME["bg_base"],
            fg=THEME["fg_secondary"],
        )
        subtitle_lbl.pack(anchor="w", pady=(2, 0))

        # Card de Formulário
        card = create_card_frame(main_frame)
        card.pack(fill="x", pady=(0, 16), padx=1)

        form_inner = tk.Frame(card, bg=THEME["bg_surface"], padx=16, pady=16)
        form_inner.pack(fill="both", expand=True)

        # Campo 1: Diretório Inicial
        lbl_dir = tk.Label(
            form_inner,
            text="Diretório Inicial *",
            font=("Segoe UI", 9, "bold"),
            bg=THEME["bg_surface"],
            fg=THEME["fg_primary"],
        )
        lbl_dir.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 4))

        self.base_dir_var = tk.StringVar(value=load_last_base_dir())
        self.entry_dir = create_styled_entry(form_inner, textvariable=self.base_dir_var)
        self.entry_dir.grid(row=1, column=0, sticky="ew", padx=(0, 8), pady=(0, 12))

        btn_browse = create_secondary_button(
            form_inner,
            text="Procurar...",
            command=self._on_browse_dir,
        )
        btn_browse.grid(row=1, column=1, sticky="ew", pady=(0, 12))

        # Campo 2: Cliente
        lbl_cliente = tk.Label(
            form_inner,
            text="Cliente *",
            font=("Segoe UI", 9, "bold"),
            bg=THEME["bg_surface"],
            fg=THEME["fg_primary"],
        )
        lbl_cliente.grid(row=2, column=0, columnspan=2, sticky="w", pady=(0, 4))

        self.cliente_var = tk.StringVar()
        self.entry_cliente = create_styled_entry(form_inner, textvariable=self.cliente_var)
        self.entry_cliente.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(0, 12))

        # Campo 3: Ticket
        lbl_ticket = tk.Label(
            form_inner,
            text="Ticket / Identificador *",
            font=("Segoe UI", 9, "bold"),
            bg=THEME["bg_surface"],
            fg=THEME["fg_primary"],
        )
        lbl_ticket.grid(row=4, column=0, columnspan=2, sticky="w", pady=(0, 4))

        self.ticket_var = tk.StringVar()
        self.entry_ticket = create_styled_entry(form_inner, textvariable=self.ticket_var)
        self.entry_ticket.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(0, 4))

        form_inner.columnconfigure(0, weight=1)

        # Card de Pré-visualização
        preview_card = create_card_frame(main_frame)
        preview_card.pack(fill="x", pady=(0, 16), padx=1)

        preview_inner = tk.Frame(preview_card, bg=THEME["bg_surface"], padx=16, pady=12)
        preview_inner.pack(fill="both", expand=True)

        preview_title = tk.Label(
            preview_inner,
            text="Pré-visualização do destino:",
            font=("Segoe UI", 8, "bold"),
            bg=THEME["bg_surface"],
            fg=THEME["fg_secondary"],
        )
        preview_title.pack(anchor="w")

        self.preview_lbl = tk.Label(
            preview_inner,
            text="...",
            font=("Consolas", 9),
            bg=THEME["bg_surface"],
            fg=THEME["accent_hover"],
            wraplength=480,
            justify="left",
        )
        self.preview_lbl.pack(anchor="w", pady=(4, 0))

        # Barra de Ações (Botões)
        actions_frame = tk.Frame(main_frame, bg=THEME["bg_base"])
        actions_frame.pack(fill="x", pady=(0, 12))

        self.btn_create = create_primary_button(
            actions_frame,
            text="Criar Diretório",
            command=self._on_create,
        )
        self.btn_create.pack(side="left", padx=(0, 8))

        btn_clear = create_secondary_button(
            actions_frame,
            text="Limpar",
            command=self._on_clear,
        )
        btn_clear.pack(side="left")

        # Card de Feedback / Status
        self.status_card = tk.Frame(
            main_frame,
            bg=THEME["bg_surface"],
            bd=1,
            relief="solid",
            highlightthickness=1,
            highlightbackground=THEME["border"],
        )

        self.status_inner = tk.Frame(self.status_card, bg=THEME["bg_surface"], padx=14, pady=10)
        self.status_inner.pack(fill="both", expand=True)

        self.status_msg_lbl = tk.Label(
            self.status_inner,
            text="",
            font=("Segoe UI", 9),
            bg=THEME["bg_surface"],
            fg=THEME["fg_primary"],
            wraplength=480,
            justify="left",
        )
        self.status_msg_lbl.pack(anchor="w")

        self.status_btns_frame = tk.Frame(self.status_inner, bg=THEME["bg_surface"])
        # Botões de ação pós-criação
        self.btn_open_explorer = create_secondary_button(
            self.status_btns_frame,
            text="📁 Abrir no Explorer",
            command=self._on_open_explorer,
        )
        self.btn_open_explorer.pack(side="left", padx=(0, 8))

        self.btn_copy_path = create_secondary_button(
            self.status_btns_frame,
            text="📋 Copiar Caminho",
            command=self._on_copy_path,
        )
        self.btn_copy_path.pack(side="left")

    def _bind_events(self):
        # Atualização dinâmica de preview
        self.base_dir_var.trace_add("write", lambda *args: self._update_preview())
        self.cliente_var.trace_add("write", lambda *args: self._update_preview())
        self.ticket_var.trace_add("write", lambda *args: self._update_preview())

        # Teclas de atalho
        self.entry_cliente.bind("<Return>", lambda e: self.entry_ticket.focus())
        self.entry_ticket.bind("<Return>", lambda e: self._on_create())
        self.root.bind("<Control-Return>", lambda e: self._on_create())

        # Foco inicial no cliente se o diretório base estiver preenchido
        if self.base_dir_var.get():
            self.entry_cliente.focus()
        else:
            self.entry_dir.focus()

    def _update_preview(self):
        base_dir = self.base_dir_var.get().strip()
        cliente = self.cliente_var.get().strip()
        ticket = self.ticket_var.get().strip()

        if not base_dir:
            self.preview_lbl.config(
                text="Aguardando seleção do diretório inicial...",
                fg=THEME["fg_secondary"],
            )
            return

        if not cliente and not ticket:
            self.preview_lbl.config(
                text=f"{base_dir}\\<CLIENTE>_<TICKET>",
                fg=THEME["fg_secondary"],
            )
            return

        clean_cli = sanitize_component(cliente) or "<CLIENTE>"
        clean_tkt = sanitize_component(ticket) or "<TICKET>"
        target_name = f"{clean_cli}_{clean_tkt}"
        full_path = Path(base_dir) / target_name

        self.preview_lbl.config(
            text=str(full_path),
            fg=THEME["accent_hover"] if (cliente and ticket) else THEME["fg_secondary"],
        )

    def _on_browse_dir(self):
        initial = self.base_dir_var.get().strip()
        if not initial or not Path(initial).exists():
            initial = str(Path.home())

        selected = filedialog.askdirectory(
            parent=self.root,
            title="Selecione o Diretório Inicial",
            initialdir=initial,
        )
        if selected:
            norm_path = str(Path(selected).resolve())
            self.base_dir_var.set(norm_path)
            save_last_base_dir(norm_path)

    def _show_status(self, is_success: bool, message: str, target_path: Optional[Path] = None):
        self.last_created_path = target_path if is_success else None

        fg_color = THEME["success"] if is_success else THEME["danger"]
        border_color = THEME["success"] if is_success else THEME["danger"]

        self.status_card.config(highlightbackground=border_color)
        self.status_msg_lbl.config(
            text=f"{'✓ ' if is_success else '✗ '}{message}",
            fg=fg_color,
        )

        if is_success and target_path:
            self.status_btns_frame.pack(anchor="w", pady=(8, 0))
        else:
            self.status_btns_frame.pack_forget()

        self.status_card.pack(fill="x", pady=(4, 0), padx=1)

    def _on_create(self):
        base_dir = self.base_dir_var.get().strip()
        cliente = self.cliente_var.get().strip()
        ticket = self.ticket_var.get().strip()

        success, msg, target_path = create_ticket_directory(base_dir, cliente, ticket)
        self._show_status(success, msg, target_path)

        if success:
            save_last_base_dir(base_dir)
            self.ticket_var.set("")
            self.entry_cliente.focus()

    def _on_clear(self):
        self.cliente_var.set("")
        self.ticket_var.set("")
        self.status_card.pack_forget()
        self.entry_cliente.focus()

    def _on_open_explorer(self):
        if self.last_created_path and self.last_created_path.exists():
            open_in_explorer(self.last_created_path)

    def _on_copy_path(self):
        if self.last_created_path:
            self.root.clipboard_clear()
            self.root.clipboard_append(str(self.last_created_path))
            self.status_msg_lbl.config(
                text=f"✓ Caminho copiado para a área de transferência: {self.last_created_path}",
                fg=THEME["success"],
            )


def main():
    root = tk.Tk()
    app = NovoTicketApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()