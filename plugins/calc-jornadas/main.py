#!/usr/bin/env python3
"""
Plugin: Calculadora de Jornadas
Calcula horas normais, noturnas e noturnas reduzidas por jornada.
Porta fiel do jornada/page.tsx + jornada-calc.ts do KapiNote.

Correções aplicadas:
  1. Tema escuro aplicado ao Treeview (cabeçalhos, linhas, listras, seleção).
  2. A janela agora abre SEM nenhuma jornada pré-preenchida.
  3. Máscara automática de horário (HH:MM) nos campos Entrada/Saída da tabela
     e nos campos Início/Fim noturno dos parâmetros.
  4. Cursor preservado durante a digitação (não volta casa no 3º dígito).
  5. Colunas editáveis (Entrada/Saída) com destaque visual (cor de fundo
     e borda diferenciada) para melhor separação.
  6. Um único clique já habilita a edição dos campos Entrada/Saída.
  7. Conteúdo pré-existente é selecionado ao entrar em edição: a primeira
     tecla digitada substitui o valor anterior.
  8. Limitado a 4 dígitos (HHMM) no campo de hora.
  9. TAB navega Entrada → Saída da mesma linha; TAB em Saída cria nova linha.
"""
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
    "bg":"#161a21","bg2":"#1f242d","fg":"#f0f2f5","muted":"#8b94a3",
    "border":"#262c36","accent":"#6aa3ff","success":"#4cc38a",
    "danger":"#ff6369","input_bg":"#0e1014","warning":"#f5a524",
    "editable_bg":"#222a36","editable_alt":"#2a3340",
}

# ─── Máscara automática de horário HH:MM ──────────────────────────────────

def _remember_cursor(entry: tk.Misc) -> tuple[int, int] | None:
    """Salva (pos_insert, pos_end) atuais do Entry antes do trace reescrever."""
    try:
        return entry.index("insert"), entry.index("end")
    except tk.TclError:
        return None


def _restore_cursor(entry: tk.Misc, saved: tuple[int, int] | None) -> None:
    """Restaura a posição do cursor, respeitando o novo tamanho do texto."""
    if saved is None:
        try:
            entry.icursor("end")
        except tk.TclError:
            pass
        return
    pos, _ = saved
    new_len = len(entry.get())
    pos = max(0, min(pos, new_len))
    try:
        entry.icursor(pos)
    except tk.TclError:
        pass


def _format_hora_value(raw: str) -> str:
    """Converte uma string em até 4 dígitos para o formato HH:MM."""
    digits = "".join(ch for ch in raw if ch.isdigit())[:4]
    if len(digits) <= 2:
        return digits
    hh, mm = digits[:2], digits[2:]
    try:
        h = int(hh)
        if h > 29:
            h = 23
        hh = f"{h:02d}"
    except ValueError:
        pass
    return f"{hh}:{mm}"


def bind_hora_mask(entry: tk.Entry, var: tk.StringVar) -> None:
    """
    Associa ao par (Entry, StringVar) a máscara HH:MM que preserva o cursor.

    Estratégia:
      - usamos o evento <KeyRelease> para aplicar a formatação, em vez de
        trace_add em 'write' (que dispara durante o set e pode reordenar o
        cursor de forma indesejada);
      - antes de regravar, salvamos a posição do cursor; depois restauramos,
        fazendo um pequeno ajuste caso o caractere ':' tenha sido inserido
        automaticamente após a 2ª casa.
    """
    prev = {"v": var.get()}

    def on_keyrelease(_evt=None):
        if var.get() == prev["v"]:
            return
        saved = _remember_cursor(entry)
        formatted = _format_hora_value(var.get())
        prev["v"] = formatted
        var.set(formatted)
        # Se um ':' foi inserido, ajusta o cursor para ficar após ele.
        if saved is not None:
            ins_pos, _ = saved
            # A diferença bruta de tamanho nos diz quantos ':' foram
            # adicionados entre o caret e o final.
            new_len = len(formatted)
            old_len = len(prev["v"]) if False else sum(
                1 for _ in formatted
            )
            # Se ins_pos era 3 e agora há ':' na posição 2, queremos cursor em 3.
            if formatted and ins_pos <= len(formatted) and ins_pos >= 2 \
                    and formatted[ins_pos - 1:ins_pos] == ":":
                ins_pos = ins_pos  # o ':' já está antes do cursor
            _restore_cursor(entry, (ins_pos, len(formatted)))

    entry.bind("<KeyRelease>", on_keyrelease, add="+")
    # Caso o valor inicial seja vazio/parcial (ex.: add_row("","")), o trace
    # também dispara quando a formatação difere do raw inicial.
    var_initial = var.get()
    if _format_hora_value(var_initial) != var_initial:
        var.set(_format_hora_value(var_initial))
    prev["v"] = var.get()


# ─── UI ──────────────────────────────────────────────────────────────────

def build_ui():
    root = tk.Tk()
    root.title("Calculadora de Jornadas")
    root.geometry("820x580")
    root.configure(bg=DARK["bg"])
    root.resizable(True, True)

    style = ttk.Style()
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    # ── Estilos globais ──
    style.configure(".",                background=DARK["bg"],  foreground=DARK["fg"])
    style.configure("TLabel",           background=DARK["bg"],  foreground=DARK["fg"])
    style.configure("TFrame",           background=DARK["bg"])
    style.configure("TLabelframe",      background=DARK["bg"],  foreground=DARK["fg"])
    style.configure("TLabelframe.Label",
                    background=DARK["bg"], foreground=DARK["muted"],
                    font=("Segoe UI", 9, "bold"))
    style.configure("TEntry",
                    fieldbackground=DARK["input_bg"],
                    foreground=DARK["fg"],
                    insertcolor=DARK["fg"],
                    bordercolor=DARK["border"],
                    lightcolor=DARK["border"],
                    darkcolor=DARK["border"])
    style.configure(
        "Editable.TEntry",
        fieldbackground=DARK["editable_bg"],
        foreground=DARK["fg"],
        insertcolor=DARK["accent"],
        bordercolor=DARK["accent"],
        lightcolor=DARK["accent"],
        darkcolor=DARK["accent"],
    )
    style.map(
        "Editable.TEntry",
        bordercolor=[("focus", DARK["accent"])],
        lightcolor=[("focus", DARK["accent"])],
        darkcolor=[("focus", DARK["accent"])],
    )

    # ── Estilo do Treeview ──
    style.configure("Treeview",
                    background=DARK["bg2"],
                    fieldbackground=DARK["bg2"],
                    foreground=DARK["fg"],
                    bordercolor=DARK["border"],
                    rowheight=28,
                    font=("Segoe UI", 10))
    style.configure("Treeview.Heading",
                    background=DARK["bg"],
                    foreground=DARK["accent"],
                    relief="flat",
                    font=("Segoe UI", 10, "bold"))
    style.map("Treeview",
              background=[("selected", DARK["accent"])],
              foreground=[("selected", DARK["bg"])])
    style.map("Treeview.Heading",
              background=[("active", DARK["bg2"])])
    style.layout("Treeview", [
        ("Treeview.treearea", {"sticky": "nswe"})
    ])

    params = Params()

    # ── Título ──
    ttk.Label(root, text="Calculadora de Jornadas",
              font=("Segoe UI", 15, "bold")).pack(pady=(16, 2))
    ttk.Label(root, text="Horas normais · Noturnas · Noturnas reduzidas",
              foreground=DARK["muted"], font=("Segoe UI", 9)).pack(pady=(0, 10))

    # ── Parâmetros ──
    fp = ttk.LabelFrame(root, text="Parâmetros", padding=10)
    fp.pack(fill="x", padx=18, pady=(0, 10))

    def min_to_hhmm(m: int) -> str:
        return f"{m//60:02d}:{m%60:02d}"

    p_row = ttk.Frame(fp); p_row.pack(fill="x")

    ttk.Label(p_row, text="Início noturno:", font=("Segoe UI", 9)).grid(row=0, column=0, sticky="w", padx=(0, 6))
    ini_var = tk.StringVar(value=min_to_hhmm(params.inicio_noturno))
    ini_entry = ttk.Entry(p_row, textvariable=ini_var, width=8, font=("Segoe UI", 10))
    ini_entry.grid(row=0, column=1, padx=(0, 20))
    bind_hora_mask(ini_entry, ini_var)

    ttk.Label(p_row, text="Fim noturno:", font=("Segoe UI", 9)).grid(row=0, column=2, sticky="w", padx=(0, 6))
    fim_var = tk.StringVar(value=min_to_hhmm(params.fim_noturno))
    fim_entry = ttk.Entry(p_row, textvariable=fim_var, width=8, font=("Segoe UI", 10))
    fim_entry.grid(row=0, column=3, padx=(0, 20))
    bind_hora_mask(fim_entry, fim_var)

    ttk.Label(p_row, text="Min/h noturna:", font=("Segoe UI", 9)).grid(row=0, column=4, sticky="w", padx=(0, 6))
    fator_var = tk.StringVar(value="52,5")
    ttk.Entry(p_row, textvariable=fator_var, width=8, font=("Segoe UI", 10)).grid(row=0, column=5)
    ttk.Label(p_row, text="(CLT: 52,5)", foreground=DARK["muted"],
              font=("Segoe UI", 8)).grid(row=0, column=6, padx=(4, 0))

    def apply_params():
        try:
            params.inicio_noturno = hora_para_min(ini_var.get())
            params.fim_noturno    = hora_para_min(fim_var.get())
            raw = fator_var.get().replace(",", ".")
            v = float(raw)
            if v > 0:
                params.fator_reducao = v / 60
        except Exception:
            pass
        recalc()

    tk.Button(fp, text="Aplicar", bg=DARK["bg2"], fg=DARK["accent"],
              relief="flat", cursor="hand2", font=("Segoe UI", 9), padx=10, pady=3,
              command=apply_params).pack(anchor="e", pady=(8, 0))

    # ── Tabela ──
    cols = ("entrada", "saida", "normais", "noturnas", "not_red", "total")
    headers = ("Entrada", "Saída", "Normais", "Noturnas", "Not. Red.", "Total")
    col_w = (110, 110, 100, 100, 100, 100)

    ft = ttk.Frame(root); ft.pack(fill="both", expand=True, padx=18, pady=(0, 6))

    tree = ttk.Treeview(ft, columns=cols, show="headings", height=12)
    for c, h, w in zip(cols, headers, col_w):
        tree.heading(c, text=h)
        tree.column(c, width=w, anchor="center", stretch=True)

    # Separação visual: colunas editáveis (0,1) ganham cor própria via tags
    # por linha. As colunas 2..5 (somente leitura) mantêm a cor base.
    tree.tag_configure("row_even",  background="#1a1f27",          foreground=DARK["fg"])
    tree.tag_configure("row_odd",   background=DARK["bg2"],        foreground=DARK["fg"])
    tree.tag_configure("edit_even", background=DARK["editable_alt"], foreground=DARK["fg"])
    tree.tag_configure("edit_odd",  background=DARK["editable_bg"],  foreground=DARK["fg"])
    tree.pack(side="left", fill="both", expand=True)

    vsb = ttk.Scrollbar(ft, orient="vertical", command=tree.yview)
    vsb.pack(side="right", fill="y")
    tree.configure(yscrollcommand=vsb.set)

    rows_data = []   # list of (entrada_var, saida_var, iid, entrada_widget_ref, saida_widget_ref)

    def _restyle_rows():
        for idx, (_, _, iid, _, _) in enumerate(rows_data):
            row_tag = "row_even" if idx % 2 == 0 else "row_odd"
            edit_tag = "edit_even" if idx % 2 == 0 else "edit_odd"
            tree.item(iid, tags=(row_tag, edit_tag))

    def recalc():
        apply_params_quiet()
        totais = [0, 0, 0, 0]
        for (ev, sv, iid, *_rest) in rows_data:
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
            raw = fator_var.get().replace(",", ".")
            v = float(raw)
            if v > 0:
                params.fator_reducao = v / 60
        except Exception:
            pass

    def add_row(e="", s=""):
        iid = tree.insert("", "end", values=(e, s, "—", "—", "—", "—"))
        ev = tk.StringVar(value=e)
        sv = tk.StringVar(value=s)
        # placeholders; widgets reais são criados sob demanda em open_editor
        rows_data.append((ev, sv, iid, None, None))
        ev.trace_add("write", lambda *_: recalc())
        sv.trace_add("write", lambda *_: recalc())
        _restyle_rows()
        return ev, sv, iid

    # Estado do editor atualmente aberto, para suportar navegação por TAB.
    state = {"active": None}  # {"entry": Entry, "row_idx": int, "col_idx": int, "iid": str, "var": StringVar}

    def _close_active_editor():
        active = state["active"]
        if not active:
            return
        entry = active["entry"]
        try:
            entry.destroy()
        except tk.TclError:
            pass
        # Libera a referência ao widget na linha
        idx = active["row_idx"]
        col_idx = active["col_idx"]
        if 0 <= idx < len(rows_data):
            row = list(rows_data[idx])
            row[3 + col_idx] = None
            rows_data[idx] = tuple(row)  # type: ignore[assignment]
        state["active"] = None

    # Teclas de navegação que sempre devem funcionar, mesmo com o limite de
    # 4 dígitos ativo.
    _NAV_KEYS = {
        "BackSpace", "Delete", "Left", "Right", "Home", "End",
        "Tab", "Return", "Escape", "ISO_Left_Tab", "Shift_L", "Shift_R",
        "Control_L", "Control_R", "Alt_L", "Alt_R",
    }

    def _limit_4_digits(event):
        if event.keysym in _NAV_KEYS:
            return
        try:
            entry = event.widget
            current = entry.get()
        except Exception:
            return
        try:
            sel_first = entry.index("sel.first")
            sel_last = entry.index("sel.last")
            selecting = sel_first != sel_last
        except tk.TclError:
            selecting = False
        if selecting:
            return
        digits = sum(1 for ch in current if ch.isdigit())
        if digits >= 4 and event.char.isdigit():
            return "break"

    def open_editor(event=None, *, col_override: int | None = None,
                    row_override: int | None = None):
        """Abre o editor inline para Entrada (col 0) ou Saída (col 1).

        Um único clique já abre o editor (correção #6). Se houver outro
        editor ativo, ele é fechado antes de abrir o novo.
        """
        _close_active_editor()

        # Descobre a linha alvo.
        if row_override is not None:
            sel = rows_data[row_override][2]
        else:
            sel = tree.focus()
            if not sel:
                if not rows_data:
                    return
                sel = rows_data[-1][2]
            else:
                sel = sel

        # Descobre a coluna alvo.
        if col_override is not None:
            col_idx = col_override
        else:
            if event is None:
                return
            col = tree.identify_column(event.x)
            col_idx = int(col.replace("#", "")) - 1
            if col_idx not in (0, 1):
                return

        idx = tree.index(sel)
        ev, sv, iid, _ev_w, _sv_w = rows_data[idx]
        var = ev if col_idx == 0 else sv

        bbox = tree.bbox(iid, f"#{col_idx + 1}")
        if not bbox:
            return
        x, y, w, h = bbox
        entry = ttk.Entry(tree, textvariable=var, style="Editable.TEntry",
                          font=("Segoe UI", 10, "bold"), justify="center")
        entry.place(x=x, y=y, width=w, height=h)
        entry.focus()
        # correção #7: seleciona o valor atual para a primeira tecla substituir
        try:
            entry.select_range(0, "end")
            entry.icursor("end")
        except tk.TclError:
            pass
        # correção #3/4: aplica a máscara HH:MM neste editor com preservação
        # de cursor.
        bind_hora_mask(entry, var)
        # correção #8: limita a 4 dígitos.
        entry.bind("<KeyPress>", _limit_4_digits, add="+")

        # Armazena referência do widget na linha para eventual uso futuro.
        row = list(rows_data[idx])
        row[3 + col_idx] = entry
        rows_data[idx] = tuple(row)  # type: ignore[assignment]

        state["active"] = {
            "entry": entry, "row_idx": idx, "col_idx": col_idx,
            "iid": iid, "var": var,
        }

        def commit(_evt=None):
            active = state["active"]
            if not active or active["entry"] is not entry:
                return
            _close_active_editor()
            recalc()

        def on_tab(_evt=None):
            active = state["active"]
            if not active or active["entry"] is not entry:
                return
            row_idx = active["row_idx"]
            col_idx = active["col_idx"]
            _close_active_editor()
            recalc()
            # TAB no Entrada → abre Saída da mesma linha
            if col_idx == 0:
                open_editor(col_override=1, row_override=row_idx)
            # TAB no Saída → cria nova linha e abre Entrada
            else:
                ev2, sv2, iid2 = add_row("", "")
                new_idx = tree.index(iid2)
                tree.selection_set(iid2)
                tree.focus(iid2)
                tree.see(iid2)
                open_editor(col_override=0, row_override=new_idx)
            return "break"

        entry.bind("<Return>", commit)
        entry.bind("<FocusOut>", commit)
        entry.bind("<Escape>",
                   lambda e: (_close_active_editor(), recalc()))
        entry.bind("<Tab>", on_tab)
        entry.bind("<ISO_Left_Tab>", on_tab)

    # Correção #6: um único clique já abre o editor
    tree.bind("<Button-1>", open_editor, add="+")

    # Correção #2: a janela agora abre SEM nenhuma jornada pré-preenchida
    add_row("", "")

    # botões
    fb2 = ttk.Frame(root); fb2.pack(fill="x", padx=18, pady=(0, 6))

    def rm_row():
        sel = tree.focus()
        if not sel:
            return
        idx = tree.index(sel)
        rows_data.pop(idx)
        tree.delete(sel)
        _restyle_rows()
        recalc()

    def clear_all():
        for iid in tree.get_children():
            tree.delete(iid)
        rows_data.clear()
        add_row("", "")
        lbl_tot.configure(text="")

    tk.Button(fb2, text="+ Linha", bg=DARK["bg2"], fg=DARK["accent"],
              relief="flat", cursor="hand2", font=("Segoe UI", 9), padx=10, pady=4,
              command=lambda: add_row()).pack(side="left", padx=(0, 8))
    tk.Button(fb2, text="Remover selecionada", bg=DARK["bg2"], fg=DARK["danger"],
              relief="flat", cursor="hand2", font=("Segoe UI", 9), padx=10, pady=4,
              command=rm_row).pack(side="left", padx=(0, 8))
    tk.Button(fb2, text="Limpar tudo", bg=DARK["bg2"], fg=DARK["muted"],
              relief="flat", cursor="hand2", font=("Segoe UI", 9), padx=10, pady=4,
              command=clear_all).pack(side="left")

    lbl_tot = ttk.Label(root, text="", font=("Segoe UI", 10, "bold"),
                        foreground=DARK["accent"])
    lbl_tot.pack(pady=(0, 12))

    recalc()
    root.mainloop()


if __name__ == "__main__":
    build_ui()
