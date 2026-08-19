#!/usr/bin/env python3
"""
Plugin: Novo Ticket & Extrator de Logs
Criação e abertura de tickets padronizados no formato CLIENTE_TICKET
e filtragem avançada de arquivos .log por subpastas (multinível via checkboxes) e período.
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Any, Callable, Dict, List, Optional

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
        "warning": "#f59e0b",
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
            style.configure("TNotebook", background=THEME["bg_base"], borderwidth=0)
            style.configure("TNotebook.Tab", background=THEME["bg_surface"], foreground=THEME["fg_secondary"], padding=[14, 7])
            style.map("TNotebook.Tab", background=[("selected", THEME["bg_hover"])], foreground=[("selected", THEME["accent_hover"])])
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
    get_ticket_subdirectories,
    get_ticket_subdirectories_info,
    parse_datetime_range,
    process_ticket_logs,
)


CONFIG_DIR = Path.home() / ".toolbox" / "novo-ticket"
CONFIG_FILE = CONFIG_DIR / "config.json"


def load_config() -> dict:
    """Carrega configurações persistidas do plugin."""
    try:
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {"last_base_dir": str(Path.home()), "last_active_ticket": ""}


def save_config(config_data: dict) -> None:
    """Salva configurações persistidas do plugin."""
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=2)
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
        self.root.title("Novo Ticket & Logs — Toolbox")
        self.root.geometry("700x740")
        self.root.minsize(640, 620)

        enable_high_dpi()
        setup_app_theme(self.root)

        self.config = load_config()
        self.active_ticket_path: Optional[Path] = None
        last_ticket = self.config.get("last_active_ticket", "")
        if last_ticket and Path(last_ticket).exists() and Path(last_ticket).is_dir():
            self.active_ticket_path = Path(last_ticket)

        self.last_logs_output_dir: Optional[Path] = None

        # Dados das subpastas: lista de dicts com metadados e BooleanVars
        self.subdirs_data: List[Dict[str, Any]] = []

        self._build_ui()
        self._bind_events()
        self._update_ticket_preview()
        if self.active_ticket_path:
            self._on_ticket_activated(self.active_ticket_path, switch_tab=False)

    def _build_ui(self):
        # Container Principal
        main_frame = tk.Frame(self.root, bg=THEME["bg_base"])
        main_frame.pack(fill="both", expand=True, padx=16, pady=16)

        # Cabeçalho
        header_frame = tk.Frame(main_frame, bg=THEME["bg_base"])
        header_frame.pack(fill="x", pady=(0, 12))

        title_lbl = tk.Label(
            header_frame,
            text="Novo Ticket & Extrator de Logs",
            font=("Segoe UI", 14, "bold"),
            bg=THEME["bg_base"],
            fg=THEME["fg_primary"],
        )
        title_lbl.pack(anchor="w")

        subtitle_lbl = tk.Label(
            header_frame,
            text="Criação padronizada de diretórios de tickets e filtragem de logs multinível por subpastas e período.",
            font=("Segoe UI", 9),
            bg=THEME["bg_base"],
            fg=THEME["fg_secondary"],
        )
        subtitle_lbl.pack(anchor="w", pady=(2, 0))

        # Notebook com Abas
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill="both", expand=True)

        self.tab_ticket = tk.Frame(self.notebook, bg=THEME["bg_base"], padx=10, pady=12)
        self.tab_logs = tk.Frame(self.notebook, bg=THEME["bg_base"], padx=10, pady=12)

        self.notebook.add(self.tab_ticket, text="  📁 Gestão de Ticket  ")
        self.notebook.add(self.tab_logs, text="  📊 Filtragem de Logs  ")

        self._build_ticket_tab()
        self._build_logs_tab()

    # -----------------------------------------------------------------------
    # Aba 1: Gestão de Ticket
    # -----------------------------------------------------------------------
    def _build_ticket_tab(self):
        # Card 1: Criar Novo Ticket
        create_card = create_card_frame(self.tab_ticket)
        create_card.pack(fill="x", pady=(0, 12), padx=1)

        create_inner = tk.Frame(create_card, bg=THEME["bg_surface"], padx=14, pady=14)
        create_inner.pack(fill="both", expand=True)

        sec_title1 = tk.Label(
            create_inner,
            text="Criar Novo Ticket",
            font=("Segoe UI", 10, "bold"),
            bg=THEME["bg_surface"],
            fg=THEME["accent_hover"],
        )
        sec_title1.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))

        # Campo: Diretório Inicial
        lbl_dir = tk.Label(
            create_inner,
            text="Diretório Inicial *",
            font=("Segoe UI", 8, "bold"),
            bg=THEME["bg_surface"],
            fg=THEME["fg_primary"],
        )
        lbl_dir.grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 2))

        self.base_dir_var = tk.StringVar(value=self.config.get("last_base_dir", str(Path.home())))
        self.entry_dir = create_styled_entry(create_inner, textvariable=self.base_dir_var)
        self.entry_dir.grid(row=2, column=0, sticky="ew", padx=(0, 8), pady=(0, 8))

        btn_browse = create_secondary_button(
            create_inner,
            text="Procurar...",
            command=self._on_browse_base_dir,
        )
        btn_browse.grid(row=2, column=1, sticky="ew", pady=(0, 8))

        # Campos: Cliente e Ticket
        row_fields = tk.Frame(create_inner, bg=THEME["bg_surface"])
        row_fields.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        row_fields.columnconfigure(0, weight=1)
        row_fields.columnconfigure(1, weight=1)

        lbl_cli = tk.Label(
            row_fields, text="Cliente *", font=("Segoe UI", 8, "bold"),
            bg=THEME["bg_surface"], fg=THEME["fg_primary"]
        )
        lbl_cli.grid(row=0, column=0, sticky="w", pady=(0, 2), padx=(0, 6))

        lbl_tkt = tk.Label(
            row_fields, text="Ticket / ID *", font=("Segoe UI", 8, "bold"),
            bg=THEME["bg_surface"], fg=THEME["fg_primary"]
        )
        lbl_tkt.grid(row=0, column=1, sticky="w", pady=(0, 2), padx=(6, 0))

        self.cliente_var = tk.StringVar()
        self.entry_cliente = create_styled_entry(row_fields, textvariable=self.cliente_var)
        self.entry_cliente.grid(row=1, column=0, sticky="ew", padx=(0, 6))

        self.ticket_var = tk.StringVar()
        self.entry_ticket = create_styled_entry(row_fields, textvariable=self.ticket_var)
        self.entry_ticket.grid(row=1, column=1, sticky="ew", padx=(6, 0))

        # Preview
        self.ticket_preview_lbl = tk.Label(
            create_inner,
            text="Destino: ...",
            font=("Consolas", 8),
            bg=THEME["bg_surface"],
            fg=THEME["fg_secondary"],
            wraplength=600,
            justify="left",
        )
        self.ticket_preview_lbl.grid(row=4, column=0, columnspan=2, sticky="w", pady=(0, 8))

        btn_create = create_primary_button(
            create_inner,
            text="Criar Diretório do Ticket",
            command=self._on_create_ticket,
        )
        btn_create.grid(row=5, column=0, sticky="w")

        create_inner.columnconfigure(0, weight=1)

        # Card 2: Abrir Ticket Existente
        open_card = create_card_frame(self.tab_ticket)
        open_card.pack(fill="x", pady=(0, 12), padx=1)

        open_inner = tk.Frame(open_card, bg=THEME["bg_surface"], padx=14, pady=12)
        open_inner.pack(fill="both", expand=True)

        sec_title2 = tk.Label(
            open_inner,
            text="Abrir Ticket Existente",
            font=("Segoe UI", 10, "bold"),
            bg=THEME["bg_surface"],
            fg=THEME["accent_hover"],
        )
        sec_title2.pack(anchor="w", pady=(0, 4))

        lbl_open_desc = tk.Label(
            open_inner,
            text="Selecione a pasta de um ticket já existente para analisar e filtrar seus logs.",
            font=("Segoe UI", 8),
            bg=THEME["bg_surface"],
            fg=THEME["fg_secondary"],
        )
        lbl_open_desc.pack(anchor="w", pady=(0, 8))

        btn_open_exist = create_secondary_button(
            open_inner,
            text="📁 Selecionar Pasta de Ticket Existente...",
            command=self._on_open_existing_ticket,
        )
        btn_open_exist.pack(anchor="w")

        # Card 3: Ticket Ativo Atual
        self.active_card = create_card_frame(self.tab_ticket)
        self.active_card.pack(fill="x", pady=(0, 8), padx=1)

        active_inner = tk.Frame(self.active_card, bg=THEME["bg_surface"], padx=14, pady=12)
        active_inner.pack(fill="both", expand=True)

        lbl_active_title = tk.Label(
            active_inner,
            text="Ticket Ativo Selecionado:",
            font=("Segoe UI", 9, "bold"),
            bg=THEME["bg_surface"],
            fg=THEME["success"],
        )
        lbl_active_title.pack(anchor="w")

        self.active_ticket_lbl = tk.Label(
            active_inner,
            text="Nenhum ticket selecionado",
            font=("Consolas", 9, "bold"),
            bg=THEME["bg_surface"],
            fg=THEME["fg_primary"],
            wraplength=600,
            justify="left",
        )
        self.active_ticket_lbl.pack(anchor="w", pady=(2, 8))

        active_btns = tk.Frame(active_inner, bg=THEME["bg_surface"])
        active_btns.pack(anchor="w")

        self.btn_active_explorer = create_secondary_button(
            active_btns,
            text="📁 Abrir no Explorer",
            command=lambda: self.active_ticket_path and open_in_explorer(self.active_ticket_path),
        )
        self.btn_active_explorer.pack(side="left", padx=(0, 8))

        self.btn_active_copy = create_secondary_button(
            active_btns,
            text="📋 Copiar Caminho",
            command=self._on_copy_active_ticket_path,
        )
        self.btn_active_copy.pack(side="left", padx=(0, 8))

        self.btn_go_logs = create_primary_button(
            active_btns,
            text="Filtrar Logs deste Ticket ➔",
            command=lambda: self.notebook.select(self.tab_logs),
        )
        self.btn_go_logs.pack(side="left")

        # Status Message Card na aba 1
        self.ticket_status_lbl = tk.Label(
            self.tab_ticket,
            text="",
            font=("Segoe UI", 9),
            bg=THEME["bg_base"],
            fg=THEME["success"],
        )
        self.ticket_status_lbl.pack(anchor="w", pady=(4, 0))

    # -----------------------------------------------------------------------
    # Aba 2: Filtragem de Logs
    # -----------------------------------------------------------------------
    def _build_logs_tab(self):
        # Card: Resumo do Ticket Ativo
        ticket_header_card = create_card_frame(self.tab_logs)
        ticket_header_card.pack(fill="x", pady=(0, 8), padx=1)

        th_inner = tk.Frame(ticket_header_card, bg=THEME["bg_surface"], padx=12, pady=8)
        th_inner.pack(fill="both", expand=True)

        self.logs_ticket_header_lbl = tk.Label(
            th_inner,
            text="Ticket Ativo: (Nenhum)",
            font=("Segoe UI", 9, "bold"),
            bg=THEME["bg_surface"],
            fg=THEME["accent_hover"],
            wraplength=520,
            justify="left",
        )
        self.logs_ticket_header_lbl.pack(side="left", fill="x", expand=True)

        btn_change_tkt = create_secondary_button(
            th_inner,
            text="Alterar Ticket",
            command=lambda: self.notebook.select(self.tab_ticket),
        )
        btn_change_tkt.pack(side="right")

        # Card: Subpastas do Ticket (NOVO DESIGN COM CHECKBOXES E MULTINÍVEL)
        subdirs_card = create_card_frame(self.tab_logs)
        subdirs_card.pack(fill="both", expand=True, pady=(0, 8), padx=1)

        sd_inner = tk.Frame(subdirs_card, bg=THEME["bg_surface"], padx=12, pady=10)
        sd_inner.pack(fill="both", expand=True)

        # Header do Card de Pastas
        header_row = tk.Frame(sd_inner, bg=THEME["bg_surface"])
        header_row.pack(fill="x", pady=(0, 6))

        sd_title = tk.Label(
            header_row,
            text="1. Subpastas do Ticket (todos os níveis):",
            font=("Segoe UI", 9, "bold"),
            bg=THEME["bg_surface"],
            fg=THEME["fg_primary"],
        )
        sd_title.pack(side="left")

        self.subdirs_counter_lbl = tk.Label(
            header_row,
            text="0 pastas",
            font=("Segoe UI", 8),
            bg=THEME["bg_surface"],
            fg=THEME["fg_secondary"],
        )
        self.subdirs_counter_lbl.pack(side="right")

        # Barra de Ações Rápidas & Busca de Pastas
        toolbar_frame = tk.Frame(sd_inner, bg=THEME["bg_surface"])
        toolbar_frame.pack(fill="x", pady=(0, 8))

        btn_select_all = create_secondary_button(
            toolbar_frame,
            text="Selecionar Todas",
            command=self._on_select_all_subdirs,
        )
        btn_select_all.pack(side="left", padx=(0, 6))

        btn_deselect_all = create_secondary_button(
            toolbar_frame,
            text="Desmarcar Todas",
            command=self._on_deselect_all_subdirs,
        )
        btn_deselect_all.pack(side="left", padx=(0, 6))

        btn_only_logs = create_secondary_button(
            toolbar_frame,
            text="Apenas com Logs",
            command=self._on_select_only_with_logs,
        )
        btn_only_logs.pack(side="left", padx=(0, 6))

        btn_reload_sd = create_secondary_button(
            toolbar_frame,
            text="🔄 Recarregar",
            command=self._refresh_subdirectories,
        )
        btn_reload_sd.pack(side="left", padx=(0, 8))

        # Campo de filtro textual rápido
        self.search_folder_var = tk.StringVar()
        self.search_folder_var.trace_add("write", lambda *args: self._render_subdirectories_list())
        search_entry = create_styled_entry(
            toolbar_frame,
            textvariable=self.search_folder_var,
            font=("Segoe UI", 8),
        )
        search_entry.pack(side="right", fill="x", expand=True)

        lbl_search_icon = tk.Label(
            toolbar_frame,
            text="🔍 Filtrar:",
            font=("Segoe UI", 8),
            bg=THEME["bg_surface"],
            fg=THEME["fg_secondary"],
        )
        lbl_search_icon.pack(side="right", padx=(0, 4))

        # Container Rolável Moderno com Canvas + Checkboxes
        canvas_container = tk.Frame(
            sd_inner,
            bg=THEME["bg_input"],
            bd=1,
            relief="solid",
            highlightthickness=1,
            highlightbackground=THEME["border"],
        )
        canvas_container.pack(fill="both", expand=True, pady=(0, 4))

        self.canvas = tk.Canvas(
            canvas_container,
            bg=THEME["bg_input"],
            highlightthickness=0,
            bd=0,
        )
        self.scrollbar = ttk.Scrollbar(canvas_container, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas, bg=THEME["bg_input"])

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        # Ajusta largura do frame interno ao redimensionar canvas
        self.canvas.bind(
            "<Configure>",
            lambda e: self.canvas.itemconfig(self.canvas_window, width=e.width)
        )

        # Suporte a scroll com mouse wheel
        self._bind_mousewheel(self.canvas)
        self._bind_mousewheel(self.scrollable_frame)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        # Card: Intervalo de Data e Hora
        time_card = create_card_frame(self.tab_logs)
        time_card.pack(fill="x", pady=(0, 8), padx=1)

        tc_inner = tk.Frame(time_card, bg=THEME["bg_surface"], padx=12, pady=8)
        tc_inner.pack(fill="both", expand=True)

        tc_title = tk.Label(
            tc_inner,
            text="2. Intervalo de Data e Hora para o Filtro:",
            font=("Segoe UI", 9, "bold"),
            bg=THEME["bg_surface"],
            fg=THEME["fg_primary"],
        )
        tc_title.pack(anchor="w", pady=(0, 4))

        grid_time = tk.Frame(tc_inner, bg=THEME["bg_surface"])
        grid_time.pack(fill="x", pady=(0, 4))
        grid_time.columnconfigure(0, weight=1)
        grid_time.columnconfigure(1, weight=1)
        grid_time.columnconfigure(2, weight=1)
        grid_time.columnconfigure(3, weight=1)

        now = datetime.now()
        today_str = now.strftime("%Y-%m-%d")

        # Linha 1: Labels
        tk.Label(grid_time, text="Data Inicial *", font=("Segoe UI", 8, "bold"), bg=THEME["bg_surface"], fg=THEME["fg_primary"]).grid(row=0, column=0, sticky="w", padx=(0, 4))
        tk.Label(grid_time, text="Hora Inicial", font=("Segoe UI", 8, "bold"), bg=THEME["bg_surface"], fg=THEME["fg_primary"]).grid(row=0, column=1, sticky="w", padx=(4, 8))
        tk.Label(grid_time, text="Data Final *", font=("Segoe UI", 8, "bold"), bg=THEME["bg_surface"], fg=THEME["fg_primary"]).grid(row=0, column=2, sticky="w", padx=(8, 4))
        tk.Label(grid_time, text="Hora Final", font=("Segoe UI", 8, "bold"), bg=THEME["bg_surface"], fg=THEME["fg_primary"]).grid(row=0, column=3, sticky="w", padx=(4, 0))

        # Linha 2: Inputs
        self.dt_ini_var = tk.StringVar(value=today_str)
        self.tm_ini_var = tk.StringVar(value="00:00")
        self.dt_fim_var = tk.StringVar(value=today_str)
        self.tm_fim_var = tk.StringVar(value="23:59")

        self.entry_dt_ini = create_styled_entry(grid_time, textvariable=self.dt_ini_var)
        self.entry_dt_ini.grid(row=1, column=0, sticky="ew", padx=(0, 4), pady=(2, 0))

        self.entry_tm_ini = create_styled_entry(grid_time, textvariable=self.tm_ini_var)
        self.entry_tm_ini.grid(row=1, column=1, sticky="ew", padx=(4, 8), pady=(2, 0))

        self.entry_dt_fim = create_styled_entry(grid_time, textvariable=self.dt_fim_var)
        self.entry_dt_fim.grid(row=1, column=2, sticky="ew", padx=(8, 4), pady=(2, 0))

        self.entry_tm_fim = create_styled_entry(grid_time, textvariable=self.tm_fim_var)
        self.entry_tm_fim.grid(row=1, column=3, sticky="ew", padx=(4, 0), pady=(2, 0))

        # Atalhos rápidos de data
        shortcuts_frame = tk.Frame(tc_inner, bg=THEME["bg_surface"])
        shortcuts_frame.pack(fill="x", pady=(4, 0))

        tk.Label(shortcuts_frame, text="Atalhos:", font=("Segoe UI", 8), bg=THEME["bg_surface"], fg=THEME["fg_secondary"]).pack(side="left", padx=(0, 6))

        btn_today = create_secondary_button(shortcuts_frame, text="Hoje", command=self._set_range_today)
        btn_today.pack(side="left", padx=(0, 4))

        btn_yesterday = create_secondary_button(shortcuts_frame, text="Ontem", command=self._set_range_yesterday)
        btn_yesterday.pack(side="left", padx=(0, 4))

        btn_last_7days = create_secondary_button(shortcuts_frame, text="Últimos 7 dias", command=self._set_range_last_7days)
        btn_last_7days.pack(side="left")

        # Botão de Ação Principal
        action_bar = tk.Frame(self.tab_logs, bg=THEME["bg_base"])
        action_bar.pack(fill="x", pady=(0, 6))

        self.btn_filter_logs = create_primary_button(
            action_bar,
            text="⚡ Filtrar e Extrair Logs",
            command=self._on_filter_logs,
        )
        self.btn_filter_logs.pack(side="left")

        # Card de Feedback / Resultados da Filtragem
        self.logs_feedback_card = tk.Frame(
            self.tab_logs,
            bg=THEME["bg_surface"],
            bd=1,
            relief="solid",
            highlightthickness=1,
            highlightbackground=THEME["border"],
        )

        self.logs_feedback_inner = tk.Frame(self.logs_feedback_card, bg=THEME["bg_surface"], padx=12, pady=8)
        self.logs_feedback_inner.pack(fill="both", expand=True)

        self.logs_status_lbl = tk.Label(
            self.logs_feedback_inner,
            text="",
            font=("Segoe UI", 9),
            bg=THEME["bg_surface"],
            fg=THEME["fg_primary"],
            wraplength=600,
            justify="left",
        )
        self.logs_status_lbl.pack(anchor="w")

        self.logs_actions_row = tk.Frame(self.logs_feedback_inner, bg=THEME["bg_surface"])
        self.btn_open_logs_dir = create_secondary_button(
            self.logs_actions_row,
            text="📁 Abrir Pasta logs_filtrados no Explorer",
            command=self._on_open_logs_dir,
        )
        self.btn_open_logs_dir.pack(side="left")

    def _bind_mousewheel(self, widget: Any):
        def _on_wheel(event):
            delta = -1 * int(event.delta / 120) if event.delta else 0
            self.canvas.yview_scroll(delta, "units")
        widget.bind("<MouseWheel>", _on_wheel)

    def _bind_events(self):
        self.base_dir_var.trace_add("write", lambda *args: self._update_ticket_preview())
        self.cliente_var.trace_add("write", lambda *args: self._update_ticket_preview())
        self.ticket_var.trace_add("write", lambda *args: self._update_ticket_preview())

        self.entry_cliente.bind("<Return>", lambda e: self.entry_ticket.focus())
        self.entry_ticket.bind("<Return>", lambda e: self._on_create_ticket())

    # -----------------------------------------------------------------------
    # Handlers e Lógica de Gestão de Tickets
    # -----------------------------------------------------------------------
    def _update_ticket_preview(self):
        base_dir = self.base_dir_var.get().strip()
        cliente = self.cliente_var.get().strip()
        ticket = self.ticket_var.get().strip()

        if not base_dir:
            self.ticket_preview_lbl.config(text="Destino: Aguardando seleção do diretório inicial...", fg=THEME["fg_secondary"])
            return

        clean_cli = sanitize_component(cliente) or "<CLIENTE>"
        clean_tkt = sanitize_component(ticket) or "<TICKET>"
        target_name = f"{clean_cli}_{clean_tkt}"
        full_path = Path(base_dir) / target_name

        self.ticket_preview_lbl.config(
            text=f"Destino: {full_path}",
            fg=THEME["accent_hover"] if (cliente and ticket) else THEME["fg_secondary"],
        )

    def _on_browse_base_dir(self):
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
            self.config["last_base_dir"] = norm_path
            save_config(self.config)

    def _on_create_ticket(self):
        base_dir = self.base_dir_var.get().strip()
        cliente = self.cliente_var.get().strip()
        ticket = self.ticket_var.get().strip()

        success, msg, target_path = create_ticket_directory(base_dir, cliente, ticket)
        if success and target_path:
            self.ticket_status_lbl.config(text=f"✓ {msg}", fg=THEME["success"])
            self.config["last_base_dir"] = base_dir
            self._on_ticket_activated(target_path, switch_tab=True)
            self.ticket_var.set("")
        else:
            self.ticket_status_lbl.config(text=f"✗ {msg}", fg=THEME["danger"])

    def _on_open_existing_ticket(self):
        initial = self.base_dir_var.get().strip()
        if not initial or not Path(initial).exists():
            initial = str(Path.home())

        selected = filedialog.askdirectory(
            parent=self.root,
            title="Selecione a Pasta de um Ticket Existente",
            initialdir=initial,
        )
        if selected:
            ticket_path = Path(selected).resolve()
            self._on_ticket_activated(ticket_path, switch_tab=True)
            self.ticket_status_lbl.config(text=f"✓ Ticket aberto com sucesso: {ticket_path.name}", fg=THEME["success"])

    def _on_ticket_activated(self, ticket_path: Path, switch_tab: bool = False):
        self.active_ticket_path = ticket_path
        self.config["last_active_ticket"] = str(ticket_path)
        save_config(self.config)

        self.active_ticket_lbl.config(text=str(ticket_path))
        self.logs_ticket_header_lbl.config(text=f"Ticket Ativo: {ticket_path.name} ({ticket_path})")

        self._refresh_subdirectories()

        if switch_tab:
            self.notebook.select(self.tab_logs)

    def _on_copy_active_ticket_path(self):
        if self.active_ticket_path:
            self.root.clipboard_clear()
            self.root.clipboard_append(str(self.active_ticket_path))
            self.ticket_status_lbl.config(text="✓ Caminho copiado para a área de transferência!", fg=THEME["success"])

    # -----------------------------------------------------------------------
    # Handlers e Lógica de Filtragem de Logs e Subpastas
    # -----------------------------------------------------------------------
    def _refresh_subdirectories(self):
        self.subdirs_data.clear()
        if not self.active_ticket_path or not self.active_ticket_path.exists():
            self._render_subdirectories_list()
            return

        infos = get_ticket_subdirectories_info(self.active_ticket_path)
        for item in infos:
            var = tk.BooleanVar(value=True)  # Selecionada por padrão
            self.subdirs_data.append({
                "path": item["path"],
                "log_count": item["log_count"],
                "has_logs": item["has_logs"],
                "var": var,
            })

        self._render_subdirectories_list()

    def _render_subdirectories_list(self):
        # Limpa widgets existentes no scrollable_frame
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        if not self.active_ticket_path or not self.active_ticket_path.exists():
            empty_lbl = tk.Label(
                self.scrollable_frame,
                text="Nenhum ticket ativo selecionado. Crie ou abra um ticket na aba anterior.",
                font=("Segoe UI", 9, "italic"),
                bg=THEME["bg_input"],
                fg=THEME["fg_muted"],
                pady=16,
            )
            empty_lbl.pack(fill="x", padx=12)
            self.subdirs_counter_lbl.config(text="0 pastas")
            return

        if not self.subdirs_data:
            empty_lbl = tk.Label(
                self.scrollable_frame,
                text="📁 Nenhuma subpasta encontrada dentro do ticket ativo.\nCrie subpastas com arquivos .log para realizar a filtragem.",
                font=("Segoe UI", 9, "italic"),
                bg=THEME["bg_input"],
                fg=THEME["fg_muted"],
                pady=16,
                justify="center",
            )
            empty_lbl.pack(fill="x", padx=12)
            self.subdirs_counter_lbl.config(text="0 pastas")
            return

        search_query = self.search_folder_var.get().strip().lower()
        displayed_count = 0
        selected_count = 0

        for idx, item in enumerate(self.subdirs_data):
            rel_path = item["path"]
            log_count = item["log_count"]
            var = item["var"]

            if var.get():
                selected_count += 1

            if search_query and search_query not in rel_path.lower():
                continue

            displayed_count += 1

            # Linha estilizada do item
            row = tk.Frame(
                self.scrollable_frame,
                bg=THEME["bg_input"] if (idx % 2 == 0) else THEME["bg_surface"],
                padx=8,
                pady=4,
            )
            row.pack(fill="x", expand=True)

            self._bind_mousewheel(row)

            # Checkbox estilizado
            chk = tk.Checkbutton(
                row,
                variable=var,
                text=f" 📁  {rel_path}",
                font=("Segoe UI", 9, "bold" if item["has_logs"] else "normal"),
                bg=row["bg"],
                fg=THEME["fg_primary"],
                selectcolor=THEME["bg_base"],
                activebackground=THEME["bg_hover"],
                activeforeground=THEME["fg_primary"],
                relief="flat",
                bd=0,
                cursor="hand2",
                anchor="w",
            )
            chk.pack(side="left", fill="x", expand=True)
            self._bind_mousewheel(chk)

            # Badge lateral com quantidade de arquivos .log
            if log_count > 0:
                badge = tk.Label(
                    row,
                    text=f" {log_count} log{'s' if log_count > 1 else ''} ",
                    font=("Segoe UI", 8, "bold"),
                    bg=THEME["bg_surface"] if (idx % 2 == 0) else THEME["bg_input"],
                    fg=THEME["accent_hover"],
                    bd=1,
                    relief="solid",
                    highlightthickness=0,
                )
            else:
                badge = tk.Label(
                    row,
                    text=" sem logs ",
                    font=("Segoe UI", 8),
                    bg=row["bg"],
                    fg=THEME["fg_muted"],
                )
            badge.pack(side="right", padx=(4, 2))
            self._bind_mousewheel(badge)

        self.subdirs_counter_lbl.config(
            text=f"{len(self.subdirs_data)} pasta(s) [{selected_count} selecionada(s)]"
        )

    def _on_select_all_subdirs(self):
        for item in self.subdirs_data:
            item["var"].set(True)
        self._render_subdirectories_list()

    def _on_deselect_all_subdirs(self):
        for item in self.subdirs_data:
            item["var"].set(False)
        self._render_subdirectories_list()

    def _on_select_only_with_logs(self):
        for item in self.subdirs_data:
            item["var"].set(item["has_logs"])
        self._render_subdirectories_list()

    def _set_range_today(self):
        today = datetime.now().strftime("%Y-%m-%d")
        self.dt_ini_var.set(today)
        self.tm_ini_var.set("00:00")
        self.dt_fim_var.set(today)
        self.tm_fim_var.set("23:59")

    def _set_range_yesterday(self):
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        self.dt_ini_var.set(yesterday)
        self.tm_ini_var.set("00:00")
        self.dt_fim_var.set(yesterday)
        self.tm_fim_var.set("23:59")

    def _set_range_last_7days(self):
        now = datetime.now()
        start = (now - timedelta(days=7)).strftime("%Y-%m-%d")
        today = now.strftime("%Y-%m-%d")
        self.dt_ini_var.set(start)
        self.tm_ini_var.set("00:00")
        self.dt_fim_var.set(today)
        self.tm_fim_var.set("23:59")

    def _show_logs_feedback(self, is_success: bool, message: str, output_dir: Optional[Path] = None):
        self.last_logs_output_dir = output_dir if is_success else None

        border_color = THEME["success"] if is_success else THEME["danger"]
        fg_color = THEME["success"] if is_success else THEME["danger"]

        self.logs_feedback_card.config(highlightbackground=border_color)
        self.logs_status_lbl.config(
            text=f"{'✓ ' if is_success else '✗ '}{message}",
            fg=fg_color,
        )

        if is_success and output_dir and output_dir.exists():
            self.logs_actions_row.pack(anchor="w", pady=(8, 0))
        else:
            self.logs_actions_row.pack_forget()

        self.logs_feedback_card.pack(fill="x", pady=(6, 0), padx=1)

    def _on_filter_logs(self):
        if not self.active_ticket_path or not self.active_ticket_path.exists():
            self._show_logs_feedback(False, "Selecione ou crie um Ticket antes de executar a filtragem.")
            return

        selected_subdirs = [item["path"] for item in self.subdirs_data if item["var"].get()]
        if not selected_subdirs:
            self._show_logs_feedback(False, "Selecione ao menos uma subpasta via checkbox para escanear.")
            return

        try:
            start_dt, end_dt = parse_datetime_range(
                self.dt_ini_var.get(),
                self.tm_ini_var.get(),
                self.dt_fim_var.get(),
                self.tm_fim_var.get(),
            )
        except ValueError as ex:
            self._show_logs_feedback(False, str(ex))
            return

        try:
            summary = process_ticket_logs(
                ticket_dir=self.active_ticket_path,
                selected_subdirs=selected_subdirs,
                start_dt=start_dt,
                end_dt=end_dt,
                output_folder_name="logs_filtrados",
            )

            total_scanned = summary["total_files_scanned"]
            total_written = summary["total_files_written"]
            total_blocks = summary["total_blocks_kept"]
            out_dir = summary["output_dir"]

            if total_written > 0:
                msg = (
                    f"Filtragem concluída com sucesso!\n"
                    f"• {total_scanned} arquivo(s) .log analisado(s)\n"
                    f"• {total_written} arquivo(s) gravado(s) com ocorrências no período\n"
                    f"• {total_blocks} bloco(s) de log extraído(s)\n"
                    f"• Destino: {out_dir}"
                )
                self._show_logs_feedback(True, msg, out_dir)
            else:
                msg = (
                    f"Filtragem concluída. {total_scanned} arquivo(s) .log analisado(s), "
                    f"porém nenhum registro foi encontrado no intervalo especificado. "
                    f"Nenhum arquivo vazio foi gerado."
                )
                self._show_logs_feedback(True, msg, None)

        except Exception as ex:
            self._show_logs_feedback(False, f"Erro durante o processamento de logs: {ex}")

    def _on_open_logs_dir(self):
        if self.last_logs_output_dir and self.last_logs_output_dir.exists():
            open_in_explorer(self.last_logs_output_dir)


def main():
    root = tk.Tk()
    app = NovoTicketApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
