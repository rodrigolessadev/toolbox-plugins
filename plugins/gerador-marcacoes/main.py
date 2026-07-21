#!/usr/bin/env python3
"""
Plugin: Gerador de Marcações
Gera INSERTs SQL para a tabela R070ACC (SQL Server e Oracle).
Porta fiel do insert/page.tsx + insert-builder.ts do KapiNote.
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

DEFAULTS = {
    "NUMCRA":"600000010","DATACC":"03-04-2025 00:00:00.000",
    "HORACC":"720","USOMAR":"2","NUMEMP":"1","TIPCOL":"1","NUMCAD":"0",
    "SEQACC":"1","TIPACC":"1","CODPLT":"1","CODRLG":"1","CODFNC":"0",
    "DIRACC":"E","QTDACC":"1","ORIACC":"E","DATAPU":"31-12-1900 00:00:00.000",
    "CODREF":"0","USOREF":"0","VALREF":"0","CODSOR":"0","FLAACC":"0",
    "CODBNF":"0","STARLG":"0","EXCPON":"N","CODDSP":"0","MOTIGN":"0","NUMNSR":"0",
}

FIXED_LABELS = {
    "NUMCRA": "NumCra — Número do Crachá",
    "USOMAR": "UsoMar — Uso da Marcação",
    "NUMEMP": "NumEmp — Código da Empresa",
    "TIPCOL": "TipCol — Tipo de Colaborador",
    "NUMCAD": "NumCad — Cadastro do Colaborador",
}

WEEK_LABELS = ["Dom","Seg","Ter","Qua","Qui","Sex","Sáb"]

DARK = {
    "bg":"#161a21","bg2":"#1f242d","fg":"#f0f2f5","muted":"#8b94a3",
    "border":"#262c36","accent":"#6aa3ff","success":"#4cc38a",
    "danger":"#ff6369","input_bg":"#0e1014",
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
    js_to_py = {0:6,1:0,2:1,3:2,4:3,5:4,6:5}
    py_days = {js_to_py[w] for w in js_weekdays}
    result, cur = [], start
    while cur <= end:
        if cur.weekday() in py_days:
            result.append(cur)
        cur += timedelta(days=1)
    return result

def gerar_inserts(fields: dict, horarios: list, datas: list, banco: str) -> str:
    lines = []
    active = [h for h in horarios if h]
    dates  = datas if datas else [None]
    for hora in active:
        for d in dates:
            vm = {}
            for fname in INSERT_ORDER:
                raw = fields.get(fname, DEFAULTS.get(fname, "0"))
                if fname == "HORACC":
                    raw = time_to_minutes(hora)
                elif fname == "DATACC" and d is not None:
                    raw = d.strftime("%d-%m-%Y 00:00:00.000")
                vm[fname] = format_value(fname, raw, banco)
            cols = ",".join(INSERT_ORDER)
            vals = ",".join(vm[c] for c in INSERT_ORDER)
            lines.append(f"INSERT INTO R070ACC({cols}) VALUES({vals})")
    return "\n".join(lines)


# ─── UI ──────────────────────────────────────────────────────────────────

def build_ui():
    root = tk.Tk()
    root.title("Gerador de Marcações")
    root.geometry("860x700")
    root.configure(bg=DARK["bg"])
    root.resizable(True, True)

    style = ttk.Style()
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    for w, cfg in [
        ("TLabel",     {"background":DARK["bg"],  "foreground":DARK["fg"]}),
        ("TFrame",     {"background":DARK["bg"]}),
        ("TLabelframe",{"background":DARK["bg"],  "foreground":DARK["fg"]}),
        ("TLabelframe.Label",{"background":DARK["bg"],"foreground":DARK["muted"],"font":("Segoe UI",9,"bold")}),
        ("TEntry",     {"fieldbackground":DARK["input_bg"],"foreground":DARK["fg"]}),
        ("TCheckbutton",{"background":DARK["bg"],"foreground":DARK["fg"]}),
        ("TRadiobutton",{"background":DARK["bg"],"foreground":DARK["fg"]}),
    ]:
        style.configure(w, **cfg)

    # scroll
    canvas = tk.Canvas(root, bg=DARK["bg"], highlightthickness=0)
    sb = ttk.Scrollbar(root, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=sb.set)
    canvas.pack(side="left", fill="both", expand=True)
    sb.pack(side="right", fill="y")
    main = ttk.Frame(canvas)
    wid = canvas.create_window((0,0), window=main, anchor="nw")
    main.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.bind("<Configure>", lambda e: canvas.itemconfig(wid, width=e.width))

    # título
    ttk.Label(main, text="Gerador de Marcações",
              font=("Segoe UI",15,"bold")).pack(pady=(16,4))

    # banco
    banco_var = tk.StringVar(value="sqlserver")
    fb = ttk.Frame(main); fb.pack(pady=(0,12))
    ttk.Label(fb, text="Banco:", foreground=DARK["muted"], font=("Segoe UI",9)).pack(side="left",padx=(0,8))
    for val, lbl in [("sqlserver","SQL Server"),("oracle","Oracle")]:
        ttk.Radiobutton(fb, text=lbl, variable=banco_var, value=val).pack(side="left",padx=6)

    # campos fixos
    field_vars = {}
    ff = ttk.LabelFrame(main, text="Campos", padding=10)
    ff.pack(fill="x", padx=18, pady=(0,10))
    for fname, flabel in FIXED_LABELS.items():
        row = ttk.Frame(ff); row.pack(fill="x", pady=3)
        ttk.Label(row, text=flabel, width=38, anchor="w", font=("Segoe UI",9)).pack(side="left")
        var = tk.StringVar(value=DEFAULTS[fname])
        field_vars[fname] = var
        ttk.Entry(row, textvariable=var, font=("Segoe UI",10)).pack(side="left",fill="x",expand=True)

    # horários
    hora_entries = []
    fh = ttk.LabelFrame(main, text="Horários (HORACC)", padding=10)
    fh.pack(fill="x", padx=18, pady=(0,10))
    hl_frame = ttk.Frame(fh); hl_frame.pack(fill="x")

    def add_hora(value=""):
        row = ttk.Frame(hl_frame); row.pack(fill="x", pady=2)
        var = tk.StringVar(value=value)
        hora_entries.append(var)
        ttk.Entry(row, textvariable=var, font=("Segoe UI",10), width=10).pack(side="left")
        ttk.Label(row, text="HH:MM", foreground=DARK["muted"], font=("Segoe UI",8)).pack(side="left",padx=6)
        if len(hora_entries) > 1:
            def rm(v=var, r=row):
                hora_entries.remove(v); r.destroy()
            tk.Button(row, text="✕", bg=DARK["bg2"], fg=DARK["danger"],
                      relief="flat", cursor="hand2", font=("Segoe UI",9), command=rm).pack(side="left")

    add_hora("08:00")
    tk.Button(fh, text="+ Horário", bg=DARK["bg2"], fg=DARK["accent"],
              relief="flat", cursor="hand2", font=("Segoe UI",9), padx=8, pady=4,
              command=add_hora).pack(anchor="w", pady=(6,0))

    # datas
    fd = ttk.LabelFrame(main, text="Intervalo de Datas (DATACC)", padding=10)
    fd.pack(fill="x", padx=18, pady=(0,10))
    rd = ttk.Frame(fd); rd.pack(fill="x", pady=(0,8))
    ttk.Label(rd, text="Início:", font=("Segoe UI",9)).pack(side="left")
    start_var = tk.StringVar(value=date.today().isoformat())
    ttk.Entry(rd, textvariable=start_var, font=("Segoe UI",10), width=13).pack(side="left",padx=(4,16))
    ttk.Label(rd, text="Fim:", font=("Segoe UI",9)).pack(side="left")
    end_var = tk.StringVar(value=date.today().isoformat())
    ttk.Entry(rd, textvariable=end_var, font=("Segoe UI",10), width=13).pack(side="left",padx=4)
    ttk.Label(rd, text="(AAAA-MM-DD)", foreground=DARK["muted"], font=("Segoe UI",8)).pack(side="left",padx=4)

    ttk.Label(fd, text="Dias da semana:", foreground=DARK["muted"], font=("Segoe UI",9)).pack(anchor="w")
    wf = ttk.Frame(fd); wf.pack(anchor="w", pady=(4,0))
    week_vars = {}
    for js_day, label in enumerate(WEEK_LABELS):
        var = tk.BooleanVar(value=(1 <= js_day <= 5))
        week_vars[js_day] = var
        ttk.Checkbutton(wf, text=label, variable=var).pack(side="left",padx=3)

    # resultado
    fr = ttk.LabelFrame(main, text="SQL Gerado", padding=8)
    fr.pack(fill="both", expand=True, padx=18, pady=(0,4))
    result_txt = scrolledtext.ScrolledText(
        fr, font=("Consolas",9), bg=DARK["input_bg"], fg=DARK["fg"],
        insertbackground=DARK["fg"], relief="flat", state="disabled", height=12)
    result_txt.pack(fill="both", expand=True)

    lbl_copied = ttk.Label(main, text="", foreground=DARK["success"], font=("Segoe UI",9))
    lbl_copied.pack(pady=(2,0))

    def do_generate():
        fields = {k: v.get().strip() for k, v in field_vars.items()}
        horarios = [v.get().strip() for v in hora_entries if v.get().strip()]
        if not horarios:
            messagebox.showwarning("Atenção", "Adicione ao menos um horário.")
            return
        datas = []
        ss, es = start_var.get().strip(), end_var.get().strip()
        if ss and es:
            try:
                sd, ed = date.fromisoformat(ss), date.fromisoformat(es)
                sel = {js for js, v in week_vars.items() if v.get()}
                datas = date_range(sd, ed, sel)
            except ValueError:
                messagebox.showerror("Erro", "Data inválida. Use AAAA-MM-DD.")
                return
        sql = gerar_inserts(fields, horarios, datas, banco_var.get())
        result_txt.configure(state="normal")
        result_txt.delete("1.0","end")
        result_txt.insert("1.0", sql)
        result_txt.configure(state="disabled")
        lbl_copied.configure(text="")

    def copy_sql():
        sql = result_txt.get("1.0","end").strip()
        if sql:
            root.clipboard_clear(); root.clipboard_append(sql)
            lbl_copied.configure(text="✓ SQL copiado.")
            root.after(2500, lambda: lbl_copied.configure(text=""))

    tk.Button(main, text="Gerar INSERT", font=("Segoe UI",11,"bold"),
              bg=DARK["accent"], fg="#fff", activebackground="#4a83df",
              relief="flat", cursor="hand2", pady=9,
              command=do_generate).pack(fill="x", padx=18, pady=(4,4))

    tk.Button(main, text="Copiar SQL", font=("Segoe UI",10),
              bg=DARK["bg2"], fg=DARK["fg"], activebackground=DARK["border"],
              relief="flat", cursor="hand2", pady=7,
              command=copy_sql).pack(fill="x", padx=18, pady=(0,16))

    root.mainloop()


if __name__ == "__main__":
    build_ui()
