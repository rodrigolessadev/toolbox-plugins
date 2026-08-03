#!/usr/bin/env python3
"""
Plugin: Gerador de Marcações
Gera INSERTs SQL para a tabela R070ACC (SQL Server e Oracle).
Porta fiel do insert/page.tsx + insert-builder.ts do KapiNote.

v1.1.0 — Campos opcionais dinâmicos (comportamento do KapiNote):
  - Seletor de campos opcionais via combobox (igual ao Select do KapiNote).
  - Campos adicionados aparecem no formulário com botão de remoção.
  - Múltiplos horários (HORACC) com botão + Adicionar Horário.
  - Intervalo de datas e filtro por dias da semana.
"""
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import date, timedelta

# ─── Constantes ──────────────────────────────────────────────────────────

NUMERIC_FIELDS = {
    "NUMCRA","HORACC","SEQACC","TIPACC","CODPLT","CODRLG","CODFNC",
    "QTDACC","USOMAR","NUMEMP","TIPCOL","NUMCAD","CODREF","USOREF",
    "VALREF","CODSOR","FLAACC","CODBNF","STARLG","CODDSP","MOTIGN","NUMNSR",
}
DATE_FIELDS = {"DATACC", "DATAPU"}

INSERT_ORDER = [
    "NUMCRA","DATACC","HORACC","SEQACC","TIPACC","CODPLT","CODRLG","CODFNC",
    "DIRACC","QTDACC","ORIACC","USOMAR","NUMEMP","TIPCOL","NUMCAD",
    "DATAPU","CODREF","USOREF","VALREF","CODSOR","FLAACC","CODBNF",
    "STARLG","EXCPON","CODDSP","MOTIGN","NUMNSR",
]

# Campos que sempre aparecem no formulário
FIXED_FIELDS = [
    ("NUMCRA", "NumCra — Número do Crachá", "600000010"),
]

MAIN_FIELDS = [
    ("USOMAR", "UsoMar — Uso da Marcação",         "2"),
    ("NUMEMP", "NumEmp — Código da Empresa",        "1"),
    ("TIPCOL", "TipCol — Tipo de Colaborador",      "1"),
    ("NUMCAD", "NumCad — Cadastro do Colaborador",  "0"),
]

# Campos opcionais que o usuário pode adicionar dinamicamente
OPTIONAL_FIELDS = [
    ("SEQACC", "SeqAcc — Sequência do Registro",             "1"),
    ("TIPACC", "TipAcc — Tipo do Acesso",                    "1"),
    ("CODPLT", "CodPH — Código do Site",                     "1"),
    ("CODRLG", "CodRlg — Código do Coletor no Acesso",       "1"),
    ("CODFNC", "CodFnc — Código da Função no Acesso",        "0"),
    ("DIRACC", "DirAcc — Direção do Acesso",                 "E"),
    ("QTDACC", "QtdAcc — Quantidade no Acesso",              "1"),
    ("ORIACC", "OriAcc — Origem da Marcação",                "E"),
    ("DATAPU", "DatApu — Data de Apuração da Marcação",      "31-12-1900 00:00:00.000"),
    ("CODREF", "CodRef — Código da Refeição da Marcação",    "0"),
    ("USOREF", "UsoRef — Uso da Refeição",                   "0"),
    ("VALREF", "ValRef — Valor da Refeição",                 "0"),
    ("CODSOR", "CodSoR — Código da Solicitação no Relógio",  "0"),
    ("FLAACC", "FlaAcc — Flag do Acesso",                    "0"),
    ("CODBNF", "CodBnf — Código do Benefício",               "0"),
    ("STARLG", "StaRlg — Status do Coletor",                 "0"),
    ("EXCPON", "ExCon — Excluído do Ponto",                  "N"),
    ("CODDSP", "CodDsp — Código do Dispositivo",             "0"),
    ("MOTIGN", "MotIgn — Motivo Marcação Ignorada",          "0"),
    ("NUMNSR", "NumNSR — Número NSR",                        "0"),
]

OPTIONAL_DICT = {name: (label, default) for name, label, default in OPTIONAL_FIELDS}

DEFAULTS = {name: default for name, _, default in FIXED_FIELDS + MAIN_FIELDS + OPTIONAL_FIELDS}
DEFAULTS.update({
    "DATACC": "03-04-2025 00:00:00.000",
    "HORACC": "720",
})

WEEK_LABELS = ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"]

DARK = {
    "bg":       "#161a21",
    "bg2":      "#1f242d",
    "fg":       "#f0f2f5",
    "muted":    "#8b94a3",
    "border":   "#262c36",
    "accent":   "#6aa3ff",
    "success":  "#4cc38a",
    "danger":   "#ff6369",
    "input_bg": "#0e1014",
}


# ─── Lógica SQL ───────────────────────────────────────────────────────────

def time_to_minutes(t: str) -> str:
    h, m = map(int, t.split(":"))
    return str(h * 60 + m)


def escape_sql(v: str) -> str:
    return v.replace("'", "''")


def format_date(value: str, banco: str) -> str:
    if "/" in value.split(" ")[0]:
        parts = value.split(" ")
        d, mo, y = parts[0].split("/")
        value = f"{d}-{mo}-{y} {parts[1] if len(parts) > 1 else '00:00:00.000'}"
    if banco == "sqlserver":
        return f"'{value}'"
    without_ms = value.rsplit(".", 1)[0]
    return f"TO_DATE('{without_ms}', 'DD-MM-YYYY HH24:MI:SS')"


def format_value(field: str, value: str, banco: str) -> str:
    if field in NUMERIC_FIELDS:
        return value
    if field in DATE_FIELDS:
        return format_date(value, banco)
    return f"'{escape_sql(value)}'"


def date_range(start: date, end: date, js_weekdays: set) -> list:
    """Retorna datas no intervalo que caem nos dias selecionados.
    js_weekdays usa convenção JS: 0=Dom, 1=Seg, ..., 6=Sáb."""
    js_to_py = {0: 6, 1: 0, 2: 1, 3: 2, 4: 3, 5: 4, 6: 5}
    py_days = {js_to_py[w] for w in js_weekdays}
    result, cur = [], start
    while cur <= end:
        if cur.weekday() in py_days:
            result.append(cur)
        cur += timedelta(days=1)
    return result


def gerar_inserts(fields: dict, horarios: list, datas: list,
                  banco: str, selected_optional: list) -> str:
    """Gera os INSERTs SQL.

    Args:
        fields: {campo: valor} para campos fixos, principais e opcionais ativos.
        horarios: lista de strings "HH:MM".
        datas: lista de objetos date (vazia = sem filtro de data).
        banco: "sqlserver" ou "oracle".
        selected_optional: nomes dos campos opcionais que estão ativos no formulário.
    """
    lines = []
    active = [h for h in horarios if h]
    dates = datas if datas else [None]

    for hora in active:
        for d in dates:
            vm = {}
            for fname in INSERT_ORDER:
                if fname == "HORACC":
                    raw = time_to_minutes(hora)
                elif fname == "DATACC" and d is not None:
                    raw = d.strftime("%d-%m-%Y 00:00:00.000")
                elif fname in fields:
                    raw = fields[fname]
                else:
                    raw = DEFAULTS.get(fname, "0")
                vm[fname] = format_value(fname, raw, banco)

            cols = ",".join(INSERT_ORDER)
            vals = ",".join(vm[c] for c in INSERT_ORDER)
            lines.append(f"INSERT INTO R070ACC({cols}) VALUES({vals})")

    return "\n".join(lines)


# ─── UI ──────────────────────────────────────────────────────────────────

class GeradorMarcacoesApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("Gerador de Marcações")
        root.geometry("900x780")
        root.configure(bg=DARK["bg"])
        root.resizable(True, True)
        self._apply_style()
        self._build_ui()

    def _apply_style(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        for w, cfg in [
            ("TLabel",      {"background": DARK["bg"],  "foreground": DARK["fg"]}),
            ("TFrame",      {"background": DARK["bg"]}),
            ("TLabelframe", {"background": DARK["bg"],  "foreground": DARK["fg"]}),
            ("TLabelframe.Label", {
                "background": DARK["bg"], "foreground": DARK["muted"],
                "font": ("Segoe UI", 9, "bold"),
            }),
            ("TEntry",       {"fieldbackground": DARK["input_bg"], "foreground": DARK["fg"]}),
            ("TCheckbutton", {"background": DARK["bg"], "foreground": DARK["fg"]}),
            ("TRadiobutton", {"background": DARK["bg"], "foreground": DARK["fg"]}),
            ("TCombobox",    {"fieldbackground": DARK["input_bg"], "foreground": DARK["fg"]}),
        ]:
            style.configure(w, **cfg)

    def _build_ui(self):
        # ── Scroll principal ──
        canvas = tk.Canvas(self.root, bg=DARK["bg"], highlightthickness=0)
        sb = ttk.Scrollbar(self.root, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.main = ttk.Frame(canvas)
        wid = canvas.create_window((0, 0), window=self.main, anchor="nw")
        self.main.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(wid, width=e.width))
        canvas.bind_all("<MouseWheel>",
                        lambda e: canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))

        # ── Título ──
        ttk.Label(self.main, text="Gerador de Marcações",
                  font=("Segoe UI", 15, "bold")).pack(pady=(16, 4))

        # ── Banco ──
        self.banco_var = tk.StringVar(value="sqlserver")
        fb = ttk.Frame(self.main)
        fb.pack(pady=(0, 12))
        ttk.Label(fb, text="Banco:", foreground=DARK["muted"],
                  font=("Segoe UI", 9)).pack(side="left", padx=(0, 8))
        for val, lbl in [("sqlserver", "SQL Server"), ("oracle", "Oracle")]:
            ttk.Radiobutton(fb, text=lbl, variable=self.banco_var,
                            value=val).pack(side="left", padx=6)

        # ── Campos fixos + principais ──
        self.field_vars: dict[str, tk.StringVar] = {}
        ff = ttk.LabelFrame(self.main, text="Campos", padding=10)
        ff.pack(fill="x", padx=18, pady=(0, 6))
        for fname, flabel, fdefault in FIXED_FIELDS + MAIN_FIELDS:
            self._add_field_row(ff, fname, flabel, fdefault)

        # ── Campos opcionais ──
        self.opt_frame = ttk.LabelFrame(self.main, text="Campos Opcionais", padding=10)
        self.opt_frame.pack(fill="x", padx=18, pady=(0, 6))
        self.opt_rows: dict[str, tk.Frame] = {}  # fname -> row frame

        # Seletor
        sel_row = ttk.Frame(self.opt_frame)
        sel_row.pack(fill="x", pady=(0, 6))
        ttk.Label(sel_row, text="Adicionar campo:",
                  foreground=DARK["muted"], font=("Segoe UI", 9)).pack(side="left", padx=(0, 8))
        self.field_to_add = tk.StringVar()
        opt_values = [f"{name} — {label}" for name, label, _ in OPTIONAL_FIELDS]
        self.opt_combo = ttk.Combobox(
            sel_row, textvariable=self.field_to_add,
            values=opt_values, state="readonly",
            font=("Segoe UI", 9), width=48,
        )
        self.opt_combo.pack(side="left", padx=(0, 8))
        tk.Button(
            sel_row, text="Adicionar", font=("Segoe UI", 9),
            bg=DARK["accent"], fg="#fff", activebackground="#4a83df",
            relief="flat", cursor="hand2", padx=10, pady=4,
            command=self._add_optional_field,
        ).pack(side="left")

        # ── Horários ──
        self.hora_entries: list[tk.StringVar] = []
        fh = ttk.LabelFrame(self.main, text="Horários (HORACC)", padding=10)
        fh.pack(fill="x", padx=18, pady=(0, 6))
        self.hora_list_frame = ttk.Frame(fh)
        self.hora_list_frame.pack(fill="x")
        self._add_hora_row("08:00")
        tk.Button(
            fh, text="+ Adicionar Horário", font=("Segoe UI", 9),
            bg=DARK["bg2"], fg=DARK["accent"], relief="flat",
            cursor="hand2", padx=8, pady=4,
            command=lambda: self._add_hora_row(""),
        ).pack(anchor="w", pady=(6, 0))

        # ── Datas ──
        fd = ttk.LabelFrame(self.main, text="Intervalo de Datas (DATACC)", padding=10)
        fd.pack(fill="x", padx=18, pady=(0, 6))
        rd = ttk.Frame(fd)
        rd.pack(fill="x", pady=(0, 8))
        ttk.Label(rd, text="Início:", font=("Segoe UI", 9)).pack(side="left")
        self.start_var = tk.StringVar(value=date.today().isoformat())
        ttk.Entry(rd, textvariable=self.start_var, font=("Segoe UI", 10),
                  width=13).pack(side="left", padx=(4, 16))
        ttk.Label(rd, text="Fim:", font=("Segoe UI", 9)).pack(side="left")
        self.end_var = tk.StringVar(value=date.today().isoformat())
        ttk.Entry(rd, textvariable=self.end_var, font=("Segoe UI", 10),
                  width=13).pack(side="left", padx=4)
        ttk.Label(rd, text="(AAAA-MM-DD)", foreground=DARK["muted"],
                  font=("Segoe UI", 8)).pack(side="left", padx=4)

        ttk.Label(fd, text="Dias da semana:", foreground=DARK["muted"],
                  font=("Segoe UI", 9)).pack(anchor="w")
        wf = ttk.Frame(fd)
        wf.pack(anchor="w", pady=(4, 0))
        self.week_vars: dict[int, tk.BooleanVar] = {}
        for js_day, label in enumerate(WEEK_LABELS):
            var = tk.BooleanVar(value=(1 <= js_day <= 5))  # Seg–Sex padrão
            self.week_vars[js_day] = var
            ttk.Checkbutton(wf, text=label, variable=var).pack(side="left", padx=3)

        # ── Resultado ──
        fr = ttk.LabelFrame(self.main, text="SQL Gerado", padding=8)
        fr.pack(fill="both", expand=True, padx=18, pady=(0, 4))
        self.result_txt = scrolledtext.ScrolledText(
            fr, font=("Consolas", 9), bg=DARK["input_bg"], fg=DARK["fg"],
            insertbackground=DARK["fg"], relief="flat", state="disabled", height=12,
        )
        self.result_txt.pack(fill="both", expand=True)

        self.lbl_copied = ttk.Label(self.main, text="", foreground=DARK["success"],
                                    font=("Segoe UI", 9))
        self.lbl_copied.pack(pady=(2, 0))

        # ── Botões ──
        tk.Button(
            self.main, text="Gerar INSERT", font=("Segoe UI", 11, "bold"),
            bg=DARK["accent"], fg="#fff", activebackground="#4a83df",
            relief="flat", cursor="hand2", pady=9,
            command=self._do_generate,
        ).pack(fill="x", padx=18, pady=(4, 4))

        tk.Button(
            self.main, text="Copiar SQL", font=("Segoe UI", 10),
            bg=DARK["bg2"], fg=DARK["fg"], activebackground=DARK["border"],
            relief="flat", cursor="hand2", pady=7,
            command=self._copy_sql,
        ).pack(fill="x", padx=18, pady=(0, 16))

    # ── Helpers ──────────────────────────────────────────────────────────

    def _add_field_row(self, parent, fname: str, flabel: str, fdefault: str):
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=3)
        ttk.Label(row, text=flabel, width=44, anchor="w",
                  font=("Segoe UI", 9)).pack(side="left")
        var = tk.StringVar(value=fdefault)
        self.field_vars[fname] = var
        ttk.Entry(row, textvariable=var,
                  font=("Segoe UI", 10)).pack(side="left", fill="x", expand=True)

    def _add_hora_row(self, value: str = ""):
        row = ttk.Frame(self.hora_list_frame)
        row.pack(fill="x", pady=2)
        var = tk.StringVar(value=value)
        self.hora_entries.append(var)
        ttk.Entry(row, textvariable=var, font=("Segoe UI", 10),
                  width=10).pack(side="left")
        ttk.Label(row, text="HH:MM", foreground=DARK["muted"],
                  font=("Segoe UI", 8)).pack(side="left", padx=6)
        if len(self.hora_entries) > 1:
            def _rm(v=var, r=row):
                if v in self.hora_entries:
                    self.hora_entries.remove(v)
                r.destroy()
            tk.Button(
                row, text="✕", bg=DARK["bg2"], fg=DARK["danger"],
                relief="flat", cursor="hand2", font=("Segoe UI", 9),
                command=_rm,
            ).pack(side="left")

    def _add_optional_field(self):
        sel = self.field_to_add.get()
        if not sel:
            return
        fname = sel.split(" — ")[0].strip()
        if fname not in OPTIONAL_DICT:
            return
        if fname in self.opt_rows:
            return  # já adicionado

        label, default = OPTIONAL_DICT[fname]

        # Insere a linha antes do seletor (primeiro filho do opt_frame)
        anchor = self.opt_frame.winfo_children()[0]
        row = ttk.Frame(self.opt_frame)
        row.pack(fill="x", pady=3, before=anchor)
        self.opt_rows[fname] = row

        ttk.Label(row, text=f"{fname} — {label}", width=44, anchor="w",
                  font=("Segoe UI", 9)).pack(side="left")
        var = tk.StringVar(value=default)
        self.field_vars[fname] = var
        ttk.Entry(row, textvariable=var,
                  font=("Segoe UI", 10)).pack(side="left", fill="x", expand=True)

        def _rm(fn=fname, r=row):
            r.destroy()
            self.opt_rows.pop(fn, None)
            self.field_vars.pop(fn, None)

        tk.Button(
            row, text="✕", bg=DARK["bg2"], fg=DARK["danger"],
            relief="flat", cursor="hand2", font=("Segoe UI", 9),
            command=_rm,
        ).pack(side="left", padx=(6, 0))

        self.field_to_add.set("")

    def _do_generate(self):
        self.lbl_copied.configure(text="")
        fields = {k: v.get().strip() for k, v in self.field_vars.items()}
        horarios = [v.get().strip() for v in self.hora_entries if v.get().strip()]
        if not horarios:
            messagebox.showwarning("Atenção", "Adicione ao menos um horário.")
            return

        datas: list[date] = []
        ss, es = self.start_var.get().strip(), self.end_var.get().strip()
        if ss and es:
            try:
                sd, ed = date.fromisoformat(ss), date.fromisoformat(es)
                sel_days = {js for js, v in self.week_vars.items() if v.get()}
                datas = date_range(sd, ed, sel_days)
            except ValueError:
                messagebox.showerror("Erro", "Data inválida. Use AAAA-MM-DD.")
                return

        selected_optional = list(self.opt_rows.keys())
        sql = gerar_inserts(fields, horarios, datas, self.banco_var.get(),
                            selected_optional)

        self.result_txt.configure(state="normal")
        self.result_txt.delete("1.0", "end")
        self.result_txt.insert("1.0", sql)
        self.result_txt.configure(state="disabled")

    def _copy_sql(self):
        sql = self.result_txt.get("1.0", "end").strip()
        if sql:
            self.root.clipboard_clear()
            self.root.clipboard_append(sql)
            self.lbl_copied.configure(text="✓ SQL copiado.")
            self.root.after(2500, lambda: self.lbl_copied.configure(text=""))


def build_ui():
    root = tk.Tk()
    GeradorMarcacoesApp(root)
    root.mainloop()


if __name__ == "__main__":
    build_ui()
