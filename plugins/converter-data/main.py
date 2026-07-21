#!/usr/bin/env python3
"""
Plugin: Converter Data
Converte data + hora para número serial Excel/Lotus (base 30/12/1899).
Porta fiel do date-time-modal.tsx do KapiNote.
"""
import tkinter as tk
from tkinter import ttk
from datetime import datetime, timezone, timedelta


# ─── Lógica de conversão ──────────────────────────────────────────────────

BASE_DATE = datetime(1899, 12, 30, tzinfo=timezone.utc)


def to_excel_serial(date_str: str, time_str: str) -> float:
    """
    Converte 'YYYY-MM-DD' + 'HH:MM' para o número serial Excel.
    Parte inteira = dias desde 30/12/1899.
    Parte decimal = fração do dia.
    """
    year, month, day = map(int, date_str.split("-"))
    hour, minute = map(int, time_str.split(":"))
    target = datetime(year, month, day, hour, minute, 0, tzinfo=timezone.utc)
    diff_days = (target - BASE_DATE).total_seconds() / 86400
    return round(diff_days, 5)


# ─── UI ──────────────────────────────────────────────────────────────────

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


def build_ui():
    root = tk.Tk()
    root.title("Converter Data")
    root.geometry("380x360")
    root.configure(bg=DARK["bg"])
    root.resizable(False, False)

    style = ttk.Style()
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    style.configure("TLabel",  background=DARK["bg"],  foreground=DARK["fg"])
    style.configure("TFrame",  background=DARK["bg"])
    style.configure("TEntry",  fieldbackground=DARK["input_bg"], foreground=DARK["fg"])

    # ── Título ──
    ttk.Label(root, text="Conversor de Data e Hora",
              font=("Segoe UI", 14, "bold")).pack(pady=(20, 4))
    ttk.Label(root, text="Converte para número serial Excel (base 30/12/1899).",
              font=("Segoe UI", 9), foreground=DARK["muted"]).pack(pady=(0, 16))

    frame = ttk.Frame(root)
    frame.pack(padx=28, fill="x")

    # ── Data ──
    ttk.Label(frame, text="Data", font=("Segoe UI", 9, "bold"),
              foreground=DARK["muted"]).grid(row=0, column=0, sticky="w", pady=(0, 2))

    now = datetime.now()
    date_var = tk.StringVar(value=now.strftime("%Y-%m-%d"))
    entry_date = ttk.Entry(frame, textvariable=date_var, font=("Segoe UI", 11), width=20)
    entry_date.grid(row=1, column=0, sticky="ew", pady=(0, 12))
    ttk.Label(frame, text="Formato: AAAA-MM-DD", font=("Segoe UI", 8),
              foreground=DARK["muted"]).grid(row=2, column=0, sticky="w", pady=(0, 8))

    # ── Hora ──
    ttk.Label(frame, text="Hora", font=("Segoe UI", 9, "bold"),
              foreground=DARK["muted"]).grid(row=3, column=0, sticky="w", pady=(0, 2))

    time_var = tk.StringVar(value=now.strftime("%H:%M"))
    entry_time = ttk.Entry(frame, textvariable=time_var, font=("Segoe UI", 11), width=20)
    entry_time.grid(row=4, column=0, sticky="ew", pady=(0, 4))
    ttk.Label(frame, text="Formato: HH:MM", font=("Segoe UI", 8),
              foreground=DARK["muted"]).grid(row=5, column=0, sticky="w", pady=(0, 16))

    frame.columnconfigure(0, weight=1)

    # ── Resultado ──
    lbl_copied = ttk.Label(root, text="", foreground=DARK["success"], font=("Segoe UI", 9))
    lbl_copied.pack()

    result_var = tk.StringVar()
    result_btn = tk.Button(
        root, textvariable=result_var,
        font=("Segoe UI", 12), bg=DARK["bg2"], fg=DARK["fg"],
        activebackground=DARK["border"], relief="flat",
        cursor="hand2", padx=12, pady=8,
    )

    def copy_result():
        val = result_var.get()
        if val:
            root.clipboard_clear()
            root.clipboard_append(val)
            lbl_copied.configure(text="✓ Copiado!")
            root.after(2000, lambda: lbl_copied.configure(text=""))

    result_btn.configure(command=copy_result)

    def do_convert(event=None):
        lbl_copied.configure(text="")
        date_s = date_var.get().strip()
        time_s = time_var.get().strip()

        if not date_s or not time_s:
            return

        # Valida formato básico
        try:
            datetime.strptime(date_s, "%Y-%m-%d")
            datetime.strptime(time_s, "%H:%M")
        except ValueError:
            result_var.set("⚠ Data ou hora inválida")
            result_btn.pack(padx=28, fill="x", pady=(4, 0))
            return

        serial = to_excel_serial(date_s, time_s)
        result_var.set(str(serial))
        result_btn.pack(padx=28, fill="x", pady=(4, 0))
        lbl_copied.configure(text="Clique no resultado para copiar.")

    # ── Botão converter ──
    btn_conv = tk.Button(
        root, text="Converter",
        font=("Segoe UI", 11, "bold"),
        bg=DARK["accent"], fg="#fff",
        activebackground="#4a83df",
        relief="flat", cursor="hand2",
        padx=0, pady=8,
        command=do_convert,
    )
    btn_conv.pack(padx=28, fill="x", pady=(4, 8))

    entry_date.bind("<Return>", do_convert)
    entry_time.bind("<Return>", do_convert)
    root.bind("<Control-Return>", do_convert)

    entry_date.focus()
    root.mainloop()


if __name__ == "__main__":
    build_ui()
