#!/usr/bin/env python3
"""
Plugin: Calculadora de Jornadas
Calcula horas normais, noturnas e noturnas reduzidas por jornada.
Porta fiel do jornada/page.tsx + jornada-calc.ts do KapiNote.
"""
import tkinter as tk
from tkinter import ttk
from dataclasses import dataclass, field
from typing import Optional

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
    "bg":"#161a21","bg2":"#1f242d","fg":"#f0f2f5","muted":"#8b94a3",
    "border":"#262c36","accent":"#6aa3ff","success":"#4cc38a",
    "danger":"#ff6369","input_bg":"#0e1014","warning":"#f5a524",
}


# ─── UI ──────────────────────────────────────────────────────────────────

def build_ui():
    root = tk.Tk()
    root.title("Calculadora de Jornadas")
    root.geometry("780x560")
    root.configure(bg=DARK["bg"])
    root.resizable(True, True)

    style = ttk.Style()
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    style.configure("TLabel",      background=DARK["bg"],  foreground=DARK["fg"])
    style.configure("TFrame",      background=DARK["bg"])
    style.configure("TLabelframe", background=DARK["bg"],  foreground=DARK["fg"])
    style.configure("TLabelframe.Label",
                    background=DARK["bg"], foreground=DARK["muted"],
                    font=("Segoe UI",9,"bold"))
    style.configure("TEntry", fieldbackground=DARK["input_bg"], foreground=DARK["fg"])

    params = Params()

    # ── Título ──
    ttk.Label(root, text="Calculadora de Jornadas",
              font=("Segoe UI",15,"bold")).pack(pady=(16,2))
    ttk.Label(root, text="Horas normais · Noturnas · Noturnas reduzidas",
              foreground=DARK["muted"], font=("Segoe UI",9)).pack(pady=(0,10))

    # ── Parâmetros ──
    fp = ttk.LabelFrame(root, text="Parâmetros", padding=10)
    fp.pack(fill="x", padx=18, pady=(0,10))

    def min_to_hhmm(m: int) -> str:
        return f"{m//60:02d}:{m%60:02d}"

    p_row = ttk.Frame(fp); p_row.pack(fill="x")

    ttk.Label(p_row, text="Início noturno:", font=("Segoe UI",9)).grid(row=0,column=0,sticky="w",padx=(0,6))
    ini_var = tk.StringVar(value=min_to_hhmm(params.inicio_noturno))
    ttk.Entry(p_row, textvariable=ini_var, width=8, font=("Segoe UI",10)).grid(row=0,column=1,padx=(0,20))

    ttk.Label(p_row, text="Fim noturno:", font=("Segoe UI",9)).grid(row=0,column=2,sticky="w",padx=(0,6))
    fim_var = tk.StringVar(value=min_to_hhmm(params.fim_noturno))
    ttk.Entry(p_row, textvariable=fim_var, width=8, font=("Segoe UI",10)).grid(row=0,column=3,padx=(0,20))

    ttk.Label(p_row, text="Min/h noturna:", font=("Segoe UI",9)).grid(row=0,column=4,sticky="w",padx=(0,6))
    fator_var = tk.StringVar(value="52,5")
    ttk.Entry(p_row, textvariable=fator_var, width=8, font=("Segoe UI",10)).grid(row=0,column=5)
    ttk.Label(p_row, text="(CLT: 52,5)", foreground=DARK["muted"],
              font=("Segoe UI",8)).grid(row=0,column=6,padx=(4,0))

    def apply_params():
        try:
            params.inicio_noturno = hora_para_min(ini_var.get())
            params.fim_noturno    = hora_para_min(fim_var.get())
            raw = fator_var.get().replace(",",".")
            v = float(raw)
            if v > 0:
                params.fator_reducao = v / 60
        except Exception:
            pass
        recalc()

    tk.Button(fp, text="Aplicar", bg=DARK["bg2"], fg=DARK["accent"],
              relief="flat", cursor="hand2", font=("Segoe UI",9), padx=10, pady=3,
              command=apply_params).pack(anchor="e", pady=(8,0))

    # ── Tabela ──
    cols = ("entrada","saida","normais","noturnas","not_red","total")
    headers = ("Entrada","Saída","Normais","Noturnas","Not. Red.","Total")
    col_w = (100,100,90,90,90,90)

    ft = ttk.Frame(root); ft.pack(fill="both", expand=True, padx=18, pady=(0,6))

    tree = ttk.Treeview(ft, columns=cols, show="headings", height=12)
    for c, h, w in zip(cols, headers, col_w):
        tree.heading(c, text=h)
        tree.column(c, width=w, anchor="center")
    tree.pack(side="left", fill="both", expand=True)

    vsb = ttk.Scrollbar(ft, orient="vertical", command=tree.yview)
    vsb.pack(side="right", fill="y")
    tree.configure(yscrollcommand=vsb.set)

    rows_data = []   # list of (entrada_var, saida_var, iid)

    def recalc():
        apply_params_quiet()
        totais = [0, 0, 0, 0]
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
                    ))
                    totais[0] += r.minutos_normais
                    totais[1] += r.minutos_noturnos
                    totais[2] += r.minutos_noturnos_red
                    totais[3] += r.total_minutos
                except Exception:
                    tree.item(iid, values=(e, s, "—", "—", "—", "erro"))
            else:
                tree.item(iid, values=(e, s, "—", "—", "—", "—"))
        # totais
        if totais[3] > 0:
            lbl_tot.configure(
                text=f"TOTAL  Normais: {min_para_hora(totais[0])}  "
                     f"Noturnas: {min_para_hora(totais[1])}  "
                     f"Not.Red.: {min_para_hora(totais[2])}  "
                     f"Total: {min_para_hora(totais[3])}"
            )
        else:
            lbl_tot.configure(text="")

    def apply_params_quiet():
        try:
            params.inicio_noturno = hora_para_min(ini_var.get())
            params.fim_noturno    = hora_para_min(fim_var.get())
            raw = fator_var.get().replace(",",".")
            v = float(raw)
            if v > 0:
                params.fator_reducao = v / 60
        except Exception:
            pass

    def add_row(e="", s=""):
        iid = tree.insert("", "end", values=(e, s, "—", "—", "—", "—"))
        ev = tk.StringVar(value=e)
        sv = tk.StringVar(value=s)
        rows_data.append((ev, sv, iid))
        ev.trace_add("write", lambda *_: recalc())
        sv.trace_add("write", lambda *_: recalc())
        return ev, sv, iid

    def open_editor(event):
        sel = tree.focus()
        if not sel:
            return
        col = tree.identify_column(event.x)
        col_idx = int(col.replace("#","")) - 1
        if col_idx not in (0, 1):
            return
        idx = tree.index(sel)
        ev, sv, _ = rows_data[idx]
        var = ev if col_idx == 0 else sv

        bbox = tree.bbox(sel, col)
        if not bbox:
            return
        x, y, w, h = bbox
        entry = ttk.Entry(tree, textvariable=var, font=("Segoe UI",10), width=8)
        entry.place(x=x, y=y, width=w, height=h)
        entry.focus()

        def done(e=None):
            entry.destroy()
            recalc()

        entry.bind("<Return>", done)
        entry.bind("<FocusOut>", done)
        entry.bind("<Tab>", done)

    tree.bind("<Double-1>", open_editor)

    add_row("08:00","17:00")

    # botões
    fb2 = ttk.Frame(root); fb2.pack(fill="x", padx=18, pady=(0,6))

    def rm_row():
        sel = tree.focus()
        if not sel:
            return
        idx = tree.index(sel)
        if len(rows_data) <= 1:
            return
        rows_data.pop(idx)
        tree.delete(sel)
        recalc()

    tk.Button(fb2, text="+ Linha", bg=DARK["bg2"], fg=DARK["accent"],
              relief="flat", cursor="hand2", font=("Segoe UI",9), padx=10, pady=4,
              command=lambda: add_row()).pack(side="left", padx=(0,8))
    tk.Button(fb2, text="Remover selecionada", bg=DARK["bg2"], fg=DARK["danger"],
              relief="flat", cursor="hand2", font=("Segoe UI",9), padx=10, pady=4,
              command=rm_row).pack(side="left", padx=(0,8))
    tk.Button(fb2, text="Limpar tudo", bg=DARK["bg2"], fg=DARK["muted"],
              relief="flat", cursor="hand2", font=("Segoe UI",9), padx=10, pady=4,
              command=lambda: [rows_data.clear(),
                               [tree.delete(i) for i in tree.get_children()],
                               add_row(), lbl_tot.configure(text="")]).pack(side="left")

    lbl_tot = ttk.Label(root, text="", font=("Segoe UI",10,"bold"),
                        foreground=DARK["accent"])
    lbl_tot.pack(pady=(0,12))

    recalc()
    root.mainloop()


if __name__ == "__main__":
    build_ui()
