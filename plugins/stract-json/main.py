#!/usr/bin/env python3
"""
Plugin: Stract JSON
Extrai valores de um campo específico de um JSON colado.
Porta fiel do json-stract-modal.tsx do KapiNote.
"""
import json
import tkinter as tk
from tkinter import ttk, messagebox


# ─── Lógica de extração ────────────────────────────────────────────────────

def extract_field(data, field: str) -> list[str]:
    """Extrai recursivamente os valores do campo em qualquer nível do JSON."""
    results: list[str] = []

    if isinstance(data, list):
        for item in data:
            results.extend(extract_field(item, field))

    elif isinstance(data, dict):
        # Campo direto
        if field in data:
            val = data[field]
            results.append(str(val) if isinstance(val, (int, float)) else f"'{val}'")

        # Suporte a objeto 'colaborador' aninhado
        if "colaborador" in data and isinstance(data["colaborador"], dict):
            col = data["colaborador"]
            if field in col:
                val = col[field]
                results.append(str(val) if isinstance(val, (int, float)) else f"'{val}'")

        # Recursão nas demais chaves
        for key, value in data.items():
            if isinstance(value, (dict, list)):
                results.extend(extract_field(value, field))

    return results


# ─── UI ───────────────────────────────────────────────────────────────────

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


def apply_dark(widget, bg=None, fg=None):
    try:
        widget.configure(
            bg=bg or DARK["bg"],
            fg=fg or DARK["fg"],
            insertbackground=DARK["fg"],
            relief="flat",
        )
    except tk.TclError:
        pass


def build_ui():
    root = tk.Tk()
    root.title("Stract JSON")
    root.geometry("580x560")
    root.configure(bg=DARK["bg"])
    root.resizable(True, True)

    style = ttk.Style()
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    style.configure("TLabel",  background=DARK["bg"],  foreground=DARK["fg"])
    style.configure("TButton", padding=6)
    style.configure("TEntry",  fieldbackground=DARK["input_bg"], foreground=DARK["fg"])
    style.configure("TFrame",  background=DARK["bg"])

    # ── Título ──
    ttk.Label(root, text="Stract JSON",
              font=("Segoe UI", 15, "bold")).pack(pady=(18, 2))
    ttk.Label(root, text="Cole o JSON e informe o campo para extrair os valores.",
              font=("Segoe UI", 9), foreground=DARK["muted"]).pack(pady=(0, 12))

    # ── Área de JSON ──
    frame_json = ttk.Frame(root)
    frame_json.pack(fill="both", expand=True, padx=18, pady=(0, 8))

    ttk.Label(frame_json, text="JSON", font=("Segoe UI", 9, "bold"),
              foreground=DARK["muted"]).pack(anchor="w")

    txt = tk.Text(frame_json, height=12, font=("Consolas", 10),
                  bg=DARK["input_bg"], fg=DARK["fg"],
                  insertbackground=DARK["fg"], relief="flat",
                  highlightthickness=1, highlightcolor=DARK["accent"],
                  highlightbackground=DARK["border"])
    txt.pack(fill="both", expand=True, pady=(4, 0))

    # ── Campo ──
    frame_field = ttk.Frame(root)
    frame_field.pack(fill="x", padx=18, pady=(4, 8))

    ttk.Label(frame_field, text="Campo", font=("Segoe UI", 9, "bold"),
              foreground=DARK["muted"]).pack(anchor="w")

    entry_field = ttk.Entry(frame_field, font=("Segoe UI", 11))
    entry_field.pack(fill="x", pady=(4, 0))
    entry_field.insert(0, "numeroCadastro")

    # ── Resultado ──
    frame_result = ttk.Frame(root)
    frame_result.pack(fill="x", padx=18, pady=(0, 6))

    lbl_result_title = ttk.Label(frame_result, text="", font=("Segoe UI", 9, "bold"))
    lbl_result_title.pack(anchor="w")

    result_var = tk.StringVar()
    result_box = tk.Text(frame_result, height=3, font=("Consolas", 10),
                         bg=DARK["bg2"], fg=DARK["fg"],
                         insertbackground=DARK["fg"], relief="flat",
                         highlightthickness=1, highlightbackground=DARK["border"],
                         state="disabled", cursor="hand2")
    result_box.pack(fill="x", pady=(4, 0))

    lbl_copied = ttk.Label(frame_result, text="", foreground=DARK["success"],
                           font=("Segoe UI", 9))
    lbl_copied.pack(anchor="w", pady=(2, 0))

    def copy_result(event=None):
        val = result_var.get()
        if val:
            root.clipboard_clear()
            root.clipboard_append(val)
            lbl_copied.configure(text="✓ Copiado para a área de transferência.")
            root.after(2000, lambda: lbl_copied.configure(text=""))

    result_box.bind("<Button-1>", copy_result)

    def do_extract():
        lbl_copied.configure(text="")
        raw = txt.get("1.0", "end").strip()
        field = entry_field.get().strip()

        if not raw:
            messagebox.showwarning("Atenção", "Cole um JSON antes de extrair.")
            return
        if not field:
            messagebox.showwarning("Atenção", "Informe o nome do campo.")
            return

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as e:
            messagebox.showerror("JSON inválido", f"Erro ao interpretar o JSON:\n{e}")
            return

        values = list(dict.fromkeys(extract_field(parsed, field)))  # mantém ordem, remove dupes

        result_box.configure(state="normal")
        result_box.delete("1.0", "end")

        if not values:
            lbl_result_title.configure(text="")
            result_box.insert("1.0", f'Campo "{field}" não encontrado no JSON.')
            result_box.configure(state="disabled")
            result_var.set("")
            return

        result_str = ", ".join(values)
        lbl_result_title.configure(text="Resultado (clique para copiar):")
        result_box.insert("1.0", result_str)
        result_box.configure(state="disabled")
        result_var.set(result_str)

    # ── Botões ──
    frame_btns = ttk.Frame(root)
    frame_btns.pack(fill="x", padx=18, pady=(4, 16))

    btn_extract = tk.Button(
        frame_btns, text="Extrair", font=("Segoe UI", 10, "bold"),
        bg=DARK["accent"], fg="#fff", activebackground="#4a83df",
        relief="flat", cursor="hand2", padx=18, pady=6,
        command=do_extract,
    )
    btn_extract.pack(side="left", padx=(0, 8))

    btn_clear = tk.Button(
        frame_btns, text="Limpar", font=("Segoe UI", 10),
        bg=DARK["bg2"], fg=DARK["fg"], activebackground=DARK["border"],
        relief="flat", cursor="hand2", padx=18, pady=6,
        command=lambda: [
            txt.delete("1.0", "end"),
            result_box.configure(state="normal"),
            result_box.delete("1.0", "end"),
            result_box.configure(state="disabled"),
            lbl_result_title.configure(text=""),
            lbl_copied.configure(text=""),
            result_var.set(""),
        ],
    )
    btn_clear.pack(side="left")

    entry_field.bind("<Return>", lambda e: do_extract())
    root.bind("<Control-Return>", lambda e: do_extract())

    entry_field.focus()
    root.mainloop()


if __name__ == "__main__":
    build_ui()
