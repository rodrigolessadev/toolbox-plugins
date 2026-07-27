#!/usr/bin/env python3
"""
Plugin: Calculadora de Jornadas
Calcula horas normais, noturnas e noturnas reduzidas por jornada.
"""
import re
import tkinter as tk
from tkinter import ttk
from dataclasses import dataclass

# ─── Lógica de cálculo ────────────────────────────────────────────────────

@dataclass
class Params:
    inicio_noturno: int = 22 * 60   # minutos desde 00:00
    fim_noturno: int    =  5 * 60
    fator_reducao: float = 52.5 / 60  # ≈ 0.875

@dataclass
class Resultado:
    total_minutos: int
    minutos_normais: int
    minutos_noturnos: int
    minutos_noturnos_red: int

def hora_para_min(s: str) -> int:
    h, m = map(int, s.split(":"))
    return h * 60 + m

def min_para_hora(m: int) -> str:
    m = abs(round(m))
    return f"{m // 60:02d}:{m % 60:02d}"

def calc_noturno(entrada: int, saida: int, p: Params) -> int:
    if saida <= entrada:
        saida += 24 * 60
    D = 24 * 60
    periodos = [
        (p.inicio_noturno,        D),
        (0,                       p.fim_noturno),
        (p.inicio_noturno + D,    2 * D),
        (D,                       p.fim_noturno + D),
    ]
    total = 0
    for pi, pf in periodos:
        oi, of = max(entrada, pi), min(saida, pf)
        if of > oi:
            total += of - oi
    return total

def calcular_jornada(entrada_s: str, saida_s: str, p: Params) -> Resultado:
    entrada = hora_para_min(entrada_s)
    saida   = hora_para_min(saida_s)
    if saida <= entrada:
        saida += 24 * 60
    total   = saida - entrada
    noturno = calc_noturno(entrada, saida, p)
    normal  = total - noturno
    red     = round(noturno / p.fator_reducao)
    return Resultado(
        total_minutos        = normal + red,
        minutos_normais      = normal,
        minutos_noturnos     = noturno,
        minutos_noturnos_red = red,
    )

# ─── Tema ─────────────────────────────────────────────────────────────────

DARK = {
    "bg":"#161a21","bg2":"#1f242d","bg3":"#262c36","fg":"#f0f2f5",
    "muted":"#8b94a3","border":"#2c3340","accent":"#6aa3ff",
    "success":"#4cc38a","danger":"#ff6369","input_bg":"#0e1014",
    "input_border":"#3a4150","warning":"#f5a624",
}


# ─── Editor de célula com máscara HH:MM ───────────────────────────────────

class TimeCell:
    """Editor in-place de uma célula de hora com máscara e auto-avanço."""

    def __init__(self, parent, tree, row_idx: int, col_idx: int,
                 var: tk.StringVar, on_commit, on_advance):
        self.parent = parent
        self.tree = tree
        self.row_idx = row_idx
        self.col_idx = col_idx
        self.var = var
        self.on_commit = on_commit
        self.on_advance = on_advance
        self._suppress = False

        iid = tree.get_children()[row_idx]
        bbox = tree.bbox(iid, f"#{col_idx+1}")
        if not bbox:
            return
        x, y, w, h = bbox

        self.entry = ttk.Entry(
            parent, textvariable=var, font=("Segoe UI", 10),
            justify="center",
        )
        self.entry.place(x=x, y=y, width=w, height=h)
        self.entry.focus()
        self.entry.icursor("end")
        self.entry.select_range(0, "end")

        self.entry.bind("<KeyRelease>", self._on_key)
        self.entry.bind("<Return>", self._commit_and_advance)
        self.entry.bind("<Tab>", self._on_tab)
        self.entry.bind("<FocusOut>", self._on_focus_out)
        self.entry.bind("<Escape>", self._cancel)

    def _normalize_digits(self, s: str) -> str:
        return re.sub(r"\D", "", s)[:4]

    def _on_key(self, event):
        if self._suppress:
            return
        if event.keysym in ("Tab","Return","Escape","Left","Right","Up","Down",
                            "BackSpace","Delete","Home","End","Shift_L","Shift_R",
                            "Control_L","Control_R"):
            return
        if event.char and event.char.isdigit():
            cur = self.var.get()
            digits = re.sub(r"\D", "", cur)
            if len(digits) >= 4:
                return "break"
            new_digits = (digits + event.char)[-4:]
            self._suppress = True
            if len(new_digits) <= 2:
                masked = new_digits
            else:
                masked = new_digits[:2] + ":" + new_digits[2:]
            self.var.set(masked)
            self.entry.icursor("end")
            self._suppress = False
            if len(new_digits) == 4:
                self.entry.after(50, self._commit_and_advance)
            return "break"
        if event.char and event.keysym not in ("BackSpace","Delete"):
            return "break"
        return None

    def _on_tab(self, event):
        self._commit_and_advance(event, advance_to_next_row=True)
        return "break"

    def _on_focus_out(self, event):
        self.entry.after(80, self._commit_only)

    def _commit_only(self, event=None):
        try:
            if not self.entry.winfo_exists():
                return
        except tk.TclError:
            return
        self._format_and_commit()
        self._destroy()

    def _commit_and_advance(self, event=None, advance_to_next_row=False):
        self._format_and_commit()
        self._destroy()
        if self.on_advance:
            self.on_advance(self.row_idx, self.col_idx, advance_to_next_row)

    def _cancel(self, event=None):
        self._destroy()

    def _format_and_commit(self):
        digits = self._normalize_digits(self.var.get())
        if not digits:
            self.var.set("")
        elif len(digits) <= 2:
            self.var.set(f"{int(digits):02d}:00")
        else:
            hh = int(digits[:2])
            mm = int(digits[2:])
            hh = min(hh, 23)
            mm = min(mm, 59)
            self.var.set(f"{hh:02d}:{mm:02d}")
        if self.on_commit:
            self.on_commit()

    def _destroy(self):
        try:
            self.entry.destroy()
        except tk.TclError:
            pass


# ─── UI ──────────────────────────────────────────────────────────────────

def build_ui():
    root = tk.Tk()
    root.title("Calculadora de Jornadas")
    root.geometry("900x620")
    root.configure(bg=DARK["bg"])
    root.resizable(True, True)

    style = ttk.Style()
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    style.configure("TLabel",      background=DARK["bg"],  foreground=DARK["fg"])
    style.configure("TFrame",      background=DARK["bg"])
    style.configure("Card.TFrame", background=DARK["bg2"])
    style.configure("TLabelframe", background=DARK["bg2"],  foreground=DARK["fg"])
    style.configure("TLabelframe.Label",
                    background=DARK["bg2"], foreground=DARK["muted"],
                    font=("Segoe UI",9,"bold"))
    style.configure("TEntry",
                    fieldbackground=DARK["input_bg"],
                    foreground=DARK["fg"],
                    insertcolor=DARK["fg"],
                    bordercolor=DARK["input_border"],
                    lightcolor=DARK["input_border"],
                    darkcolor=DARK["input_border"])
    style.map("TEntry",
              bordercolor=[("focus", DARK["accent"])],
              lightcolor=[("focus", DARK["accent"])],
              darkcolor=[("focus", DARK["accent"])])

    params = Params()
    active_cell: list = [None]

    # ── Header ──
    header = ttk.Frame(root)
    header.pack(fill="x", padx=20, pady=(18,4))
    ttk.Label(header, text="Calculadora de Jornadas",
              font=("Segoe UI", 16, "bold")).pack(side="left")
    ttk.Label(header, text="Horas normais · Noturnas · Noturnas reduzidas",
              foreground=DARK["muted"], font=("Segoe UI", 9)).pack(side="left", padx=(14,0), pady=(6,0))

    btn_limpar = tk.Button(
        header, text="Limpar", bg=DARK["bg2"], fg=DARK["muted"],
        activebackground=DARK["bg3"], activeforeground=DARK["fg"],
        relief="flat", cursor="hand2", font=("Segoe UI", 9),
        padx=14, pady=6, bd=0,
    )
    btn_limpar.pack(side="right")

    # ── Parâmetros colapsáveis ──
    params_state = {"open": False}

    params_header = tk.Frame(root, bg=DARK["bg2"], cursor="hand2", bd=0, highlightthickness=0)
    params_header.pack(fill="x", padx=20, pady=(14,0), ipady=8)

    lbl_params_chevron = tk.Label(
        params_header, text="▶  Parâmetros de cálculo",
        bg=DARK["bg2"], fg=DARK["fg"],
        font=("Segoe UI", 10, "bold"), cursor="hand2", padx=14, pady=4,
    )
    lbl_params_chevron.pack(side="left", fill="x", expand=True)

    params_body = tk.Frame(root, bg=DARK["bg2"], bd=0, highlightthickness=0)

    body_inner = tk.Frame(params_body, bg=DARK["bg2"])
    body_inner.pack(fill="x", padx=20, pady=12)

    def min_to_hhmm(m: int) -> str:
        return f"{m//60:02d}:{m%60:02d}"

    def make_field(parent, label_text, row, col, var, hint=None, width=8):
        ttk.Label(parent, text=label_text, font=("Segoe UI", 9)).grid(
            row=row, column=col, sticky="w", padx=(0,6), pady=2
        )
        ttk.Entry(parent, textvariable=var, width=width, font=("Segoe UI", 10),
                  justify="center").grid(row=row, column=col+1, padx=(0,16), pady=2)
        if hint:
            ttk.Label(parent, text=hint, foreground=DARK["muted"],
                      font=("Segoe UI", 8)).grid(row=row, column=col+2, sticky="w", padx=(0,16))

    ini_var = tk.StringVar(value=min_to_hhmm(params.inicio_noturno))
    fim_var = tk.StringVar(value=min_to_hhmm(params.fim_noturno))
    fator_var = tk.StringVar(value="52,5")

    make_field(body_inner, "Início noturno:", 0, 0, ini_var)
    make_field(body_inner, "Fim noturno:",    0, 3, fim_var)
    make_field(body_inner, "Min/h noturna:",  0, 6, fator_var, hint="(CLT: 52,5)")

    def apply_params_quiet():
        try:
            params.inicio_noturno = hora_para_min(ini_var.get())
            params.fim_noturno    = hora_para_min(fim_var.get())
            raw = fator_var.get().replace(",", ".")
            v = float(raw)
            if v > 0:
                params.fator_reducao = v / 60
        except Exception:
            pass

    def apply_params_and_recalc():
        apply_params_quiet()
        recalc()

    btn_apply = tk.Button(
        body_inner, text="Aplicar", bg=DARK["accent"], fg="#0a0d12",
        activebackground="#5495f5", activeforeground="#0a0d12",
        relief="flat", cursor="hand2", font=("Segoe UI", 9, "bold"),
        padx=18, pady=4, bd=0, command=apply_params_and_recalc,
    )
    btn_apply.grid(row=0, column=9, padx=(8,0), pady=2)

    def toggle_params(event=None):
        params_state["open"] = not params_state["open"]
        if params_state["open"]:
            lbl_params_chevron.configure(text="▼  Parâmetros de cálculo")
            params_body.pack(fill="x", padx=20, pady=(0,8), after=params_header)
        else:
            params_body.pack_forget()
            lbl_params_chevron.configure(text="▶  Parâmetros de cálculo")

    params_header.bind("<Button-1>", toggle_params)
    lbl_params_chevron.bind("<Button-1>", toggle_params)

    # ── Tabela ──
    cols = ("entrada","saida","normais","noturnas","not_red","total","acao")
    headers = ("Entrada","Saída","Normais","Noturnas","Not. Red.","Total","")
    col_w = (110, 110, 100, 100, 100, 100, 50)

    table_card = tk.Frame(root, bg=DARK["bg2"], bd=0, highlightthickness=0)
    table_card.pack(fill="both", expand=True, padx=20, pady=(8,0))

    tree_frame = tk.Frame(table_card, bg=DARK["bg2"], bd=0, highlightthickness=0)
    tree_frame.pack(fill="both", expand=True, padx=2, pady=2)

    tree = ttk.Treeview(tree_frame, columns=cols, show="headings", height=10)
    for c, h, w in zip(cols, headers, col_w):
        tree.heading(c, text=h)
        tree.column(c, width=w, anchor="center", stretch=(c in ("normais","noturnas","not_red","total")))

    style.configure("Treeview",
                    background=DARK["bg2"],
                    fieldbackground=DARK["bg2"],
                    foreground=DARK["fg"],
                    bordercolor=DARK["bg2"],
                    rowheight=34)
    style.configure("Treeview.Heading",
                    background=DARK["bg3"],
                    foreground=DARK["muted"],
                    font=("Segoe UI", 9, "bold"),
                    relief="flat")
    style.map("Treeview.Heading",
              background=[("active", DARK["bg3"])])

    tree.pack(side="left", fill="both", expand=True)

    vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
    vsb.pack(side="right", fill="y")
    tree.configure(yscrollcommand=vsb.set)

    rows_data: list = []

    def recalc():
        if active_cell[0] is not None:
            return
        apply_params_quiet()
        for (ev, sv, iid) in rows_data:
            e, s = ev.get().strip(), sv.get().strip()
            if e and s:
                try:
                    r = calcular_jornada(e, s, params)
                    tree.item(iid, values=(
                        e, s,
                        min_para_hora(r.minutos_normais),
                        min_para_hora(r.minutos_noturnos),
                        min_para_hora(r.minutos_noturnos_red),
                        min_para_hora(r.total_minutos),
                        "🗑",
                    ))
                except Exception:
                    tree.item(iid, values=(e, s, "—", "—", "—", "erro", "🗑"))
            else:
                tree.item(iid, values=(e, s, "—", "—", "—", "—", "🗑"))

    def add_row(e="", s=""):
        iid = tree.insert("", "end", values=(e, s, "—", "—", "—", "—", "🗑"))
        ev = tk.StringVar(value=e)
        sv = tk.StringVar(value=s)
        rows_data.append((ev, sv, iid))
        ev.trace_add("write", lambda *_: recalc())
        sv.trace_add("write", lambda *_: recalc())
        return ev, sv, iid

    def open_editor(row_idx, col_idx):
        if row_idx >= len(rows_data):
            return
        if col_idx not in (0, 1):
            return
        ev, sv, iid = rows_data[row_idx]
        var = ev if col_idx == 0 else sv

        def on_commit():
            pass

        def on_advance(from_row, from_col, force_next_row):
            if from_col == 0:
                open_editor(from_row, 1)
            else:
                next_row = from_row + 1
                if next_row >= len(rows_data):
                    add_row()
                open_editor(next_row, 0)

        cell = TimeCell(root, tree, row_idx, col_idx, var, on_commit, on_advance)
        active_cell[0] = cell
        old_destroy = cell._destroy
        def wrapped_destroy():
            old_destroy()
            if active_cell[0] is cell:
                active_cell[0] = None
        cell._destroy = wrapped_destroy

    def on_tree_click(event):
        region = tree.identify_region(event.x, event.y)
        if region != "cell":
            return
        iid = tree.identify_row(event.y)
        col = tree.identify_column(event.x)
        if not iid or not col:
            return
        col_idx = int(col.replace("#", "")) - 1
        row_idx = tree.index(iid)
        if col_idx in (0, 1):
            open_editor(row_idx, col_idx)
        elif col_idx == 6:
            delete_row(row_idx)

    def delete_row(row_idx):
        if row_idx >= len(rows_data):
            return
        if len(rows_data) <= 1:
            ev, sv, iid = rows_data[0]
            ev.set("")
            sv.set("")
            return
        ev, sv, iid = rows_data.pop(row_idx)
        tree.delete(iid)
        recalc()

    tree.bind("<Button-1>", on_tree_click)
    tree.bind("<Double-1>", on_tree_click)

    add_row("08:00", "17:00")

    # ── Rodapé: Adicionar linha ──
    footer = tk.Frame(root, bg=DARK["bg"], bd=0, highlightthickness=0)
    footer.pack(fill="x", padx=20, pady=(10,16))

    def on_add():
        add_row()
        new_idx = len(rows_data) - 1
        root.after(80, lambda: open_editor(new_idx, 0))

    btn_add = tk.Button(
        footer, text="+ Adicionar linha",
        bg=DARK["accent"], fg="#0a0d12",
        activebackground="#5495f5", activeforeground="#0a0d12",
        relief="flat", cursor="hand2", font=("Segoe UI", 10, "bold"),
        padx=18, pady=7, bd=0, command=on_add,
    )
    btn_add.pack(side="left")

    def on_clear():
        rows_data.clear()
        for iid in tree.get_children():
            tree.delete(iid)
        add_row()
        recalc()

    btn_limpar.configure(command=on_clear)

    recalc()
    root.mainloop()


if __name__ == "__main__":
    build_ui()
