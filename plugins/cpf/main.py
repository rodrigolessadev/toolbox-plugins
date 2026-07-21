#!/usr/bin/env python3
"""
Plugin: Validador e Gerador de CPF
----------------------------------
Demonstra como criar um plugin Tkinter (UI desktop) que o Toolbox
executa como processo independente.

Recebe argumentos via sys.argv:
  --validate 12345678909   valida um CPF
  --generate               gera um CPF válido e imprime
Sem argumentos, abre a interface.
"""

import random
import sys
import tkinter as tk
from tkinter import ttk, messagebox


def only_digits(s: str) -> str:
    return "".join(c for c in s if c.isdigit())


def is_valid_cpf(cpf: str) -> bool:
    cpf = only_digits(cpf)
    if len(cpf) != 11:
        return False
    if cpf == cpf[0] * 11:
        return False

    def digit(s, factor):
        total = sum(int(d) * (factor - i) for i, d in enumerate(s))
        rest = (total * 10) % 11
        return 0 if rest == 10 else rest

    d1 = digit(cpf[:9], 10)
    d2 = digit(cpf[:10], 11)
    return cpf[-2:] == f"{d1}{d2}"


def format_cpf(cpf: str) -> str:
    cpf = only_digits(cpf)
    if len(cpf) != 11:
        return cpf
    return f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"


def generate_cpf() -> str:
    base = [random.randint(0, 9) for _ in range(9)]

    def digit(factor):
        total = sum(d * (factor - i) for i, d in enumerate(base))
        rest = (total * 10) % 11
        return 0 if rest == 10 else rest

    d1 = digit(10)
    d2 = digit(11)
    return "".join(str(d) for d in base + [d1, d2])


def open_ui():
    root = tk.Tk()
    root.title("Validador de CPF")
    root.geometry("420x320")
    root.configure(bg="#1f242d")

    style = ttk.Style()
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    style.configure("TLabel", background="#1f242d", foreground="#f0f2f5")
    style.configure("TButton", padding=6)
    style.configure("TEntry", fieldbackground="#161a21", foreground="#f0f2f5")

    title = ttk.Label(root, text="Validador & Gerador de CPF", font=("Segoe UI", 14, "bold"))
    title.pack(pady=(20, 8))

    input_frame = ttk.Frame(root)
    input_frame.pack(pady=8, padx=20, fill="x")

    ttk.Label(input_frame, text="CPF:").pack(anchor="w")
    entry = ttk.Entry(input_frame, font=("Consolas", 12))
    entry.pack(fill="x", pady=4)

    def do_validate():
        cpf = entry.get()
        if is_valid_cpf(cpf):
            messagebox.showinfo("Resultado", f"✅ CPF válido\n{format_cpf(cpf)}")
        else:
            messagebox.showwarning("Resultado", "❌ CPF inválido")

    def do_generate():
        cpf = generate_cpf()
        entry.delete(0, tk.END)
        entry.insert(0, format_cpf(cpf))

    btn_frame = ttk.Frame(root)
    btn_frame.pack(pady=12)

    ttk.Button(btn_frame, text="Validar", command=do_validate).pack(side="left", padx=4)
    ttk.Button(btn_frame, text="Gerar", command=do_generate).pack(side="left", padx=4)
    ttk.Button(btn_frame, text="Limpar", command=lambda: entry.delete(0, tk.END)).pack(side="left", padx=4)

    ttk.Label(root, text="Dica: gere um CPF e valide para testar.", foreground="#8b94a3").pack(pady=(10, 0))

    entry.focus()
    root.mainloop()


def main():
    args = sys.argv[1:]
    if "--validate" in args:
        idx = args.index("--validate")
        if idx + 1 < len(args):
            cpf = args[idx + 1]
            print("VÁLIDO" if is_valid_cpf(cpf) else "INVÁLIDO")
            return
    if "--generate" in args:
        print(generate_cpf())
        return
    # Sem argumentos, abre a interface.
    open_ui()


if __name__ == "__main__":
    main()
