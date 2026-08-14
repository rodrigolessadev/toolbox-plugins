"""
Tema DARK compartilhado por todos os plugins do toolbox-plugins.

Porta fiel do design system dark usado nos plugins existentes
(calc-jornadas, gerador-marcacoes, stract-json, converter-data).

Cada chave do dicionario DARK mapeia 1:1 para uma opcao nativa do
tkinter / ttk, mantendo a identidade visual consistente entre plugins.
"""

# Paleta inspirada no app KapiNote (Tailwind + Radix) e ja validada
# nos 4 plugins Python publicados no toolbox-plugins.
DARK = {
    # Superficies
    "bg":            "#161a21",  # fundo da janela (equivalente a bg-zinc-900)
    "bg2":           "#1f242d",  # fundo de frame/container (bg-zinc-800)
    "bg3":           "#262c36",  # fundo de widget elevado (bg-zinc-700)
    "input_bg":      "#0e1014",  # fundo de campos de texto (input)
    # Bordas
    "border":        "#2c3340",  # borda padrao (border-zinc-700)
    "input_border":  "#3a4150",  # borda de campos de entrada
    # Texto
    "fg":            "#f0f2f5",  # texto primario (text-zinc-100)
    "muted":         "#8b94a3",  # texto secundario (text-zinc-400)
    # Acentos semanticos
    "accent":        "#6aa3ff",  # primario (bg-blue-400)
    "success":       "#4cc38a",  # positivo (text-emerald-400)
    "danger":        "#ff6369",  # destrutivo (text-rose-400)
    "warning":       "#f5a624",  # alerta (text-amber-400)
}

# Constantes tipograficas e de espacamento (mapeamento Tailwind -> tkinter).
# Nao cobrem 100% das classes Tailwind; cobrem as usadas nos 5 modais do
# KapiNote. Adicione mais aqui conforme novos plugins precisarem.
TYPOGRAPHY = {
    "font_family": "Segoe UI",
    "sizes": {
        "xs": 8,   # text-xs
        "sm": 9,   # text-sm
        "base": 10,  # text-base
        "lg": 11,  # text-lg
        "xl": 13,  # text-xl
    },
    "weights": {
        "normal":  "",
        "medium":  "bold",   # font-medium
        "semibold":"bold",   # font-semibold
        "bold":    "bold",   # font-bold
    },
}

SPACING = {
    # Espacamento Tailwind em pixels (1 unidade = 4px).
    "p-1":  4,
    "p-2":  8,
    "p-3":  12,
    "p-4":  16,
    "p-6":  24,
    "p-8":  32,
}


def apply_dark_style(style):
    """
    Aplica o tema DARK em um ttk.Style.

    Use no main.py do plugin:
        from theme import DARK, apply_dark_style
        style = ttk.Style(root)
        style.theme_use("clam")
        apply_dark_style(style)
    """
    # Frames / Labels
    style.configure("TFrame", background=DARK["bg"])
    style.configure("Card.TFrame", background=DARK["bg2"])
    style.configure("TLabel", background=DARK["bg"], foreground=DARK["fg"],
                    font=(TYPOGRAPHY["font_family"], TYPOGRAPHY["sizes"]["sm"]))
    style.configure("Muted.TLabel", background=DARK["bg"], foreground=DARK["muted"],
                    font=(TYPOGRAPHY["font_family"], TYPOGRAPHY["sizes"]["xs"]))
    style.configure("Heading.TLabel", background=DARK["bg"], foreground=DARK["fg"],
                    font=(TYPOGRAPHY["font_family"], TYPOGRAPHY["sizes"]["lg"], "bold"))

    # LabelFrame (usado para secoes como "Campos", "Horarios", "SQL Gerado")
    style.configure("TLabelframe", background=DARK["bg2"], foreground=DARK["fg"],
                    bordercolor=DARK["border"], relief="flat", borderwidth=1)
    style.configure("TLabelframe.Label", background=DARK["bg2"], foreground=DARK["fg"],
                    font=(TYPOGRAPHY["font_family"], TYPOGRAPHY["sizes"]["sm"], "bold"))

    # Botoes
    style.configure("TButton", background=DARK["bg3"], foreground=DARK["fg"],
                    bordercolor=DARK["border"], focusthickness=0, padding=(12, 6),
                    font=(TYPOGRAPHY["font_family"], TYPOGRAPHY["sizes"]["sm"]))
    style.map("TButton",
              background=[("active", DARK["accent"]), ("pressed", DARK["accent"])],
              foreground=[("active", "#ffffff"), ("pressed", "#ffffff")])
    style.configure("Accent.TButton", background=DARK["accent"], foreground="#ffffff",
                    bordercolor=DARK["accent"], focusthickness=0, padding=(14, 7),
                    font=(TYPOGRAPHY["font_family"], TYPOGRAPHY["sizes"]["sm"], "bold"))
    style.map("Accent.TButton",
              background=[("active", "#5493f0"), ("pressed", "#4580d8")])
    style.configure("Danger.TButton", background=DARK["bg3"], foreground=DARK["danger"],
                    bordercolor=DARK["danger"], focusthickness=0, padding=(10, 5),
                    font=(TYPOGRAPHY["font_family"], TYPOGRAPHY["sizes"]["xs"]))
    style.map("Danger.TButton",
              background=[("active", DARK["danger"])],
              foreground=[("active", "#ffffff")])

    # Entradas de texto
    style.configure("TEntry", fieldbackground=DARK["input_bg"], foreground=DARK["fg"],
                    insertcolor=DARK["fg"], bordercolor=DARK["input_border"],
                    lightcolor=DARK["input_border"], darkcolor=DARK["input_border"],
                    padding=(8, 6),
                    font=(TYPOGRAPHY["font_family"], TYPOGRAPHY["sizes"]["sm"]))
    style.configure("TCombobox", fieldbackground=DARK["input_bg"], foreground=DARK["fg"],
                    background=DARK["bg3"], arrowcolor=DARK["muted"],
                    bordercolor=DARK["input_border"], padding=(8, 4),
                    font=(TYPOGRAPHY["font_family"], TYPOGRAPHY["sizes"]["sm"]))

    # Checkbox
    style.configure("TCheckbutton", background=DARK["bg"], foreground=DARK["fg"],
                    focusthickness=0,
                    font=(TYPOGRAPHY["font_family"], TYPOGRAPHY["sizes"]["sm"]))
    style.map("TCheckbutton",
              background=[("active", DARK["bg"])],
              indicatorcolor=[("selected", DARK["accent"]),
                              ("deselected", DARK["input_bg"])])

    # Radio
    style.configure("TRadiobutton", background=DARK["bg"], foreground=DARK["fg"],
                    focusthickness=0,
                    font=(TYPOGRAPHY["font_family"], TYPOGRAPHY["sizes"]["sm"]))

    # Scrollbar
    style.configure("Vertical.TScrollbar", background=DARK["bg3"],
                    troughcolor=DARK["bg2"], bordercolor=DARK["border"],
                    arrowcolor=DARK["muted"])


def style_widget_text(widget, color_key="fg", bold=False, size="sm"):
    """
    Atalho para aplicar cor/tamanho/peso a widgets que nao sao ttk
    (tk.Text, tk.Listbox, etc.).
    """
    widget.configure(
        foreground=DARK[color_key],
        font=(TYPOGRAPHY["font_family"],
              TYPOGRAPHY["sizes"][size],
              "bold" if bold else ""),
    )
