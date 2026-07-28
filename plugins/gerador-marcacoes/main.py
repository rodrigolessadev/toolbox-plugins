"""
Gerador de Marcacoes (INSERT para R070ACC)
===========================================

Porta fiel do app/(main)/(routes)/insert/page.tsx + _components/insert-builder.ts
do projeto KapiNote (https://github.com/rodrigolessadev/kapinote).

Gera INSERTs SQL para a tabela R070ACC (TOTVS / Protheus), com suporte a:
  * 5 campos principais (NUMCRA, USOMAR, NUMEMP, TIPCOL, NUMCAD)
  * ate 20 campos opcionais (SEQACC, TIPACC, CODPLT, ...) adicionaveis sob demanda
  * Multiplos horarios por dia (gera um INSERT por horario)
  * Filtragem por dia da semana (0=Dom ... 6=Sab)
  * Dialetos SQL Server (GETDATE / ISNULL) e Oracle (SYSDATE / NVL / TO_DATE)
  * Helpers de dialeto (fn_data_atual, fn_isnull, traduzir_tipo) portados do TS

Execucao:
    python main.py --name "Gerador de Marcacoes" \\
                   --commands-file <path> --data-dir <path>

O toolbox ja executa com `cwd = pasta do plugin`, entao:
    from theme import DARK, apply_dark_style
funciona sem manipulacao de sys.path.
"""

import argparse
import re
import sys
import tkinter as tk
from datetime import date, datetime
from pathlib import Path
from tkinter import messagebox, ttk
from tkinter.scrolledtext import ScrolledText

# Logica pura separada (testavel sem tkinter).
from insert_builder import (
    date_range, escape_sql_string, fn_data_atual, fn_isnull,
    format_date_value, format_value, gerar_inserts, time_to_minutes,
    traduzir_tipo, DEFAULTS, NUMERIC_FIELDS, DATE_FIELDS, INSERT_ORDER,
    OPTIONAL_DEFAULTS,
)

# Tema compartilhado (plugins/_shared/theme.py). O toolbox ja roda com
# cwd = pasta do plugin, mas adicionamos a pasta mae para resolver
# quando este plugin vive em plugins/gerador-marcacoes/.
_THEME_PARENT = Path(__file__).resolve().parent.parent
if str(_THEME_PARENT) not in sys.path:
    sys.path.insert(0, str(_THEME_PARENT))
try:
    from _shared.theme import DARK, apply_dark_style, style_widget_text
except ImportError:
    # Fallback: tema inline (caso o _shared ainda nao tenha sido publicado)
    DARK = {
        "bg": "#161a21", "bg2": "#1f242d", "bg3": "#262c36",
        "fg": "#f0f2f5", "muted": "#8b94a3", "border": "#2c3340",
        "accent": "#6aa3ff", "success": "#4cc38a",
        "danger": "#ff6369", "warning": "#f5a624",
        "input_bg": "#0e1014", "input_border": "#3a4150",
    }
    def apply_dark_style(style):  # noqa: F811
        style.configure("TFrame", background=DARK["bg"])
        style.configure("TLabel", background=DARK["bg"], foreground=DARK["fg"])
        style.configure("TButton", background=DARK["bg3"], foreground=DARK["fg"])
    def style_widget_text(widget, color_key="fg", bold=False, size="sm"):
        widget.configure(foreground=DARK[color_key])


# ---------------------------------------------------------------------------
# Constantes de UI (derivadas de insert_builder.OPTIONAL_DEFAULTS)
# ---------------------------------------------------------------------------

MAIN_FIELDS = {
    "NUMCRA": "NumCra - Numero do Cracha",
    "USOMAR": "UsoMar - Uso da Marcacao",
    "NUMEMP": "NumEmp - Codigo da Empresa",
    "TIPCOL": "TipCol - Tipo de Colaborador",
    "NUMCAD": "NumCad - Cadastro do Colaborador",
}

# Lista de campos opcionais (Select Radix do KapiNote).
OPTIONAL_FIELDS = [
    ("SEQACC", "SeqAcc - Sequencia do Registro",            OPTIONAL_DEFAULTS["SEQACC"]),
    ("TIPACC", "TipAcc - Tipo do Acesso",                    OPTIONAL_DEFAULTS["TIPACC"]),
    ("CODPLT", "CodPlt - Codigo do Coletor",                OPTIONAL_DEFAULTS["CODPLT"]),
    ("CODRLG", "CodRlg - Codigo do Relogio",                OPTIONAL_DEFAULTS["CODRLG"]),
    ("CODFNC", "CodFnc - Codigo da Funcao",                 OPTIONAL_DEFAULTS["CODFNC"]),
    ("DIRACC", "DirAcc - Direcao do Acesso",                OPTIONAL_DEFAULTS["DIRACC"]),
    ("QTDACC", "QtdAcc - Quantidade no Acesso",             OPTIONAL_DEFAULTS["QTDACC"]),
    ("ORIACC", "OriAcc - Origem da Marcacao",               OPTIONAL_DEFAULTS["ORIACC"]),
    ("DATAPU", "DatApu - Data de Apuracao",                 OPTIONAL_DEFAULTS["DATAPU"]),
    ("CODREF", "CodRef - Codigo da Refeicao",               OPTIONAL_DEFAULTS["CODREF"]),
    ("USOREF", "UsoRef - Uso da Refeicao",                  OPTIONAL_DEFAULTS["USOREF"]),
    ("VALREF", "ValRef - Valor da Refeicao",                OPTIONAL_DEFAULTS["VALREF"]),
    ("CODSOR", "CodSoR - Codigo da Solicitacao no Relogio", OPTIONAL_DEFAULTS["CODSOR"]),
    ("FLAACC", "FlaAcc - Flag do Acesso",                   OPTIONAL_DEFAULTS["FLAACC"]),
    ("CODBNF", "CodBnf - Codigo do Beneficio",              OPTIONAL_DEFAULTS["CODBNF"]),
    ("STARLG", "StaRlg - Status do Coletor",                OPTIONAL_DEFAULTS["STARLG"]),
    ("EXCPON", "ExCon - Excluido do Ponto",                 OPTIONAL_DEFAULTS["EXCPON"]),
    ("CODDSP", "CodDsp - Codigo do Dispositivo",            OPTIONAL_DEFAULTS["CODDSP"]),
    ("MOTIGN", "MotIgn - Motivo Marcacao Ignorada",         OPTIONAL_DEFAULTS["MOTIGN"]),
    ("NUMNSR", "NumNSR - Numero NSR",                       OPTIONAL_DEFAULTS["NUMNSR"]),
]
OPTIONAL_BY_NAME = {n: (l, d) for n, l, d in OPTIONAL_FIELDS}

# Dias da semana: 0=Dom, 1=Seg, ..., 6=Sab (mesma convencao do JS getDay)
WEEKDAY_LABELS = ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sab"]


# ---------------------------------------------------------------------------
# UI - Tkinter
# ---------------------------------------------------------------------------

class GeradorMarcacoesApp:
    def __init__(self, root: tk.Tk, name: str, commands_file: str, data_dir: str):
        self.root = root
        self.name = name
        self.commands_file = commands_file
        self.data_dir = data_dir

        # Variaveis de estado
        self.field_vars = {}             # StringVar por campo (principais + opcionais)
        self.horario_vars = []           # List[StringVar] para horarios dinamicos
        self.optional_rows = {}          # { name: row_frame }
        self.dia_vars = [tk.IntVar(value=1 if i in (1, 2, 3, 4, 5) else 0)
                         for i in range(7)]  # seg-sex marcados por padrao
        self.banco_var = tk.StringVar(value="sqlserver")

        self._setup_window()
        self._build_styles()
        self._build_ui()
        self._bind_close()

    # -- janela / estilos ----------------------------------------------------

    def _setup_window(self):
        self.root.title(self.name)
        self.root.configure(bg=DARK["bg"])
        self.root.geometry("900x720")
        self.root.minsize(820, 640)

    def _build_styles(self):
        self.style = ttk.Style(self.root)
        try:
            self.style.theme_use("clam")
        except tk.TclError:
            pass
        apply_dark_style(self.style)

    # -- construcao da UI ----------------------------------------------------

    def _build_ui(self):
        main = ttk.Frame(self.root, padding=16)
        main.pack(fill="both", expand=True)

        # Titulo
        ttk.Label(main, text=self.name, style="Heading.TLabel").pack(anchor="w")
        ttk.Label(main, text="Gera INSERTs para a tabela R070ACC (TOTVS / Protheus).",
                  style="Muted.TLabel").pack(anchor="w", pady=(0, 12))

        # === Secao: Campos Principais ===
        self._build_main_fields(main)

        # === Secao: Campos Opcionais (Patch 5) ===
        self._build_optional_fields(main)

        # === Secao: Horarios (HORACC) ===
        self._build_horarios(main)

        # === Secao: Datas (DATACC) ===
        self._build_datas(main)

        # === Secao: Banco ===
        self._build_banco(main)

        # === Botao Gerar ===
        btn_row = ttk.Frame(main)
        btn_row.pack(fill="x", pady=(8, 12))
        ttk.Button(btn_row, text="Gerar INSERTs", style="Accent.TButton",
                   command=self._on_gerar).pack(side="left")
        ttk.Button(btn_row, text="Limpar", style="TButton",
                   command=self._on_limpar).pack(side="left", padx=(8, 0))

        # === Secao: SQL Gerado ===
        self._build_output(main)

    def _build_main_fields(self, parent):
        frame = ttk.LabelFrame(parent, text="Campos Principais", padding=12)
        frame.pack(fill="x", pady=(0, 10))
        for name, label in MAIN_FIELDS.items():
            row = ttk.Frame(frame)
            row.pack(fill="x", pady=3)
            ttk.Label(row, text=label, width=42, anchor="w").pack(side="left")
            var = tk.StringVar(value=DEFAULTS[name])
            self.field_vars[name] = var
            ttk.Entry(row, textvariable=var).pack(side="left", fill="x", expand=True)

    def _build_optional_fields(self, parent):
        frame = ttk.LabelFrame(parent, text="Adicionar Campo Opcional", padding=12)
        frame.pack(fill="x", pady=(0, 10))

        top = ttk.Frame(frame)
        top.pack(fill="x")
        self.opt_var = tk.StringVar()
        ttk.Combobox(top, textvariable=self.opt_var, state="readonly", width=14,
                     values=[n for n, _, _ in OPTIONAL_FIELDS]).pack(side="left", padx=(0, 8))
        ttk.Button(top, text="+ Adicionar", command=self._add_optional).pack(side="left")

        self.opt_container = ttk.Frame(frame)
        self.opt_container.pack(fill="x", pady=(8, 0))

    def _build_horarios(self, parent):
        frame = ttk.LabelFrame(parent, text="Horarios (HORACC)", padding=12)
        frame.pack(fill="x", pady=(0, 10))

        self.horario_container = ttk.Frame(frame)
        self.horario_container.pack(fill="x")
        # Adiciona um horario inicial
        self._add_horario()

        btn_row = ttk.Frame(frame)
        btn_row.pack(fill="x", pady=(8, 0))
        ttk.Button(btn_row, text="+ Horario", command=self._add_horario).pack(side="left")
        ttk.Button(btn_row, text="Limpar horarios", command=self._clear_horarios).pack(side="left", padx=(8, 0))

    def _build_datas(self, parent):
        frame = ttk.LabelFrame(parent, text="Datas (DATACC)", padding=12)
        frame.pack(fill="x", pady=(0, 10))

        row1 = ttk.Frame(frame)
        row1.pack(fill="x")
        ttk.Label(row1, text="Data inicial (AAAA-MM-DD):", width=28, anchor="w").pack(side="left")
        self.data_inicio_var = tk.StringVar(value=date.today().strftime("%Y-%m-%d"))
        ttk.Entry(row1, textvariable=self.data_inicio_var, width=14).pack(side="left", padx=(0, 16))

        ttk.Label(row1, text="Data final (AAAA-MM-DD):", width=24, anchor="w").pack(side="left")
        self.data_fim_var = tk.StringVar(value=date.today().strftime("%Y-%m-%d"))
        ttk.Entry(row1, textvariable=self.data_fim_var, width=14).pack(side="left")

        # Dias da semana
        ttk.Label(frame, text="Dias da semana:").pack(anchor="w", pady=(8, 4))
        dias_row = ttk.Frame(frame)
        dias_row.pack(fill="x")
        for i, label in enumerate(WEEKDAY_LABELS):
            ttk.Checkbutton(dias_row, text=label, variable=self.dia_vars[i]).pack(side="left", padx=4)

    def _build_banco(self, parent):
        frame = ttk.LabelFrame(parent, text="Banco de Dados", padding=12)
        frame.pack(fill="x", pady=(0, 10))
        ttk.Radiobutton(frame, text="SQL Server (GETDATE / ISNULL)",
                        variable=self.banco_var, value="sqlserver").pack(side="left", padx=(0, 16))
        ttk.Radiobutton(frame, text="Oracle (SYSDATE / NVL / TO_DATE)",
                        variable=self.banco_var, value="oracle").pack(side="left")

    def _build_output(self, parent):
        frame = ttk.LabelFrame(parent, text="SQL Gerado", padding=12)
        frame.pack(fill="both", expand=True, pady=(0, 4))
        self.output = ScrolledText(frame, height=10, wrap="none",
                                   bg=DARK["input_bg"], fg=DARK["fg"],
                                   insertbackground=DARK["fg"],
                                   relief="flat", borderwidth=1)
        self.output.pack(fill="both", expand=True)
        # Tags para colorir SQL (Patch 3: CodeBox substituido por tags leve)
        self.output.tag_configure("kw", foreground=DARK["accent"])
        self.output.tag_configure("str", foreground=DARK["success"])
        btn_row = ttk.Frame(frame)
        btn_row.pack(fill="x", pady=(8, 0))
        ttk.Button(btn_row, text="Copiar SQL", command=self._on_copy).pack(side="left")
        ttk.Button(btn_row, text="Salvar em .sql", command=self._on_save).pack(side="left", padx=(8, 0))

    # -- acoes dos botoes ----------------------------------------------------

    def _add_horario(self):
        row = ttk.Frame(self.horario_container)
        row.pack(fill="x", pady=2)
        var = tk.StringVar(value="08:00")
        self.horario_vars.append(var)
        ttk.Entry(row, textvariable=var, width=10).pack(side="left")
        ttk.Button(row, text="x", style="Danger.TButton", width=3,
                   command=lambda r=row, v=var: self._remove_horario(r, v)).pack(side="left", padx=(6, 0))

    def _remove_horario(self, row, var):
        if len(self.horario_vars) <= 1:
            return
        self.horario_vars.remove(var)
        row.destroy()

    def _clear_horarios(self):
        for w in self.horario_container.winfo_children():
            w.destroy()
        self.horario_vars.clear()
        self._add_horario()

    def _add_optional(self):
        name = self.opt_var.get()
        if not name or name in self.optional_rows:
            return
        label, default = OPTIONAL_BY_NAME[name]
        row = ttk.Frame(self.opt_container)
        row.pack(fill="x", pady=3)
        ttk.Label(row, text=label, width=42, anchor="w").pack(side="left")
        var = tk.StringVar(value=default)
        self.field_vars[name] = var
        self.optional_rows[name] = row
        ttk.Entry(row, textvariable=var).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="x", style="Danger.TButton", width=3,
                   command=lambda n=name, r=row: self._remove_optional(n, r)).pack(side="left", padx=(6, 0))
        self.opt_var.set("")

    def _remove_optional(self, name, row):
        if name in self.field_vars:
            del self.field_vars[name]
        if name in self.optional_rows:
            del self.optional_rows[name]
        row.destroy()

    def _on_gerar(self):
        try:
            fields = {n: v.get() for n, v in self.field_vars.items()}
            horarios = [v.get() for v in self.horario_vars if v.get()]
            selected_optional = list(self.optional_rows.keys())
            banco = self.banco_var.get()
            inicio = datetime.strptime(self.data_inicio_var.get(), "%Y-%m-%d").date()
            fim = datetime.strptime(self.data_fim_var.get(), "%Y-%m-%d").date()
            if fim < inicio:
                raise ValueError("Data final deve ser >= data inicial.")
            dias = {i for i, v in enumerate(self.dia_vars) if v.get() == 1}
            datas = date_range(inicio, fim, dias)
            sql = gerar_inserts(fields, horarios, datas, banco, selected_optional)
            self._render_sql(sql)
        except ValueError as e:
            messagebox.showerror("Erro de validacao", str(e))
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao gerar SQL: {e}")

    def _render_sql(self, sql: str):
        self.output.delete("1.0", "end")
        # Coloracao leve: keywords e strings
        keywords = ("INSERT", "INTO", "VALUES", "TO_DATE", "GETDATE", "SYSDATE",
                    "ISNULL", "NVL")
        for line in sql.splitlines():
            upper = line.upper()
            tokens = re.split(r"(\s+|'[^']*')", line)
            for tok in tokens:
                if not tok:
                    continue
                if tok.strip().upper() in keywords:
                    self.output.insert("end", tok, "kw")
                elif tok.startswith("'") and tok.endswith("'"):
                    self.output.insert("end", tok, "str")
                else:
                    self.output.insert("end", tok)
            self.output.insert("end", "\n")

    def _on_copy(self):
        sql = self.output.get("1.0", "end").strip()
        if not sql:
            messagebox.showinfo("Copiar", "Nada para copiar.")
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(sql)

    def _on_save(self):
        sql = self.output.get("1.0", "end").strip()
        if not sql:
            messagebox.showinfo("Salvar", "Nada para salvar.")
            return
        path = Path(self.data_dir) / "marcacoes.sql" if self.data_dir else Path("marcacoes.sql")
        try:
            path.write_text(sql, encoding="utf-8")
            messagebox.showinfo("Salvar", f"Arquivo salvo em:\n{path}")
        except OSError as e:
            messagebox.showerror("Salvar", f"Falha ao salvar: {e}")

    def _on_limpar(self):
        for v in self.field_vars.values():
            v.set("")
        self._clear_horarios()
        for r in self.optional_rows.values():
            r.destroy()
        self.optional_rows.clear()
        self.output.delete("1.0", "end")

    def _bind_close(self):
        self.root.protocol("WM_DELETE_WINDOW", self.root.destroy)

    def run(self):
        self.root.mainloop()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser(description="Gerador de Marcacoes (INSERT R070ACC)")
    p.add_argument("--name", required=True)
    p.add_argument("--commands-file", required=True)
    p.add_argument("--data-dir", required=True)
    return p.parse_args()


def main():
    args = parse_args()
    root = tk.Tk()
    app = GeradorMarcacoesApp(root, args.name, args.commands_file, args.data_dir)
    app.run()


if __name__ == "__main__":
    main()
