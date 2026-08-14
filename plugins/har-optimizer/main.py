#!/usr/bin/env python3
"""
Plugin: HAR Optimizer
Entrada: Protocolo IPC v1.0 (STDIN/STDOUT JSON) ou Interface Gráfica Tkinter.
"""
import json
import sys
from pathlib import Path

if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import importlib.util
def _load_domain():
    spec = importlib.util.spec_from_file_location("har_optimizer_domain_pkg", Path(__file__).parent / "domain.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

optimize_har = _load_domain().optimize_har


def handle_ipc(input_data: dict) -> dict:
    """Processa requisição via protocolo IPC v1.0."""
    req_id = input_data.get("request_id", "req_default")
    options = input_data.get("options", {})
    file_path = input_data.get("input_file")
    raw_content = input_data.get("content")

    if file_path:
        p = Path(file_path)
        if not p.exists():
            return {
                "protocol_version": "1.0",
                "request_id": req_id,
                "status": "error",
                "result": None,
                "error": {
                    "code": "FILE_NOT_FOUND",
                    "message": f"Arquivo HAR não encontrado: {file_path}"
                },
                "warnings": []
            }
        try:
            raw_content = p.read_text(encoding="utf-8-sig", errors="replace")
        except Exception as e:
            return {
                "protocol_version": "1.0",
                "request_id": req_id,
                "status": "error",
                "result": None,
                "error": {
                    "code": "READ_ERROR",
                    "message": f"Erro ao ler arquivo HAR: {e}"
                },
                "warnings": []
            }

    if raw_content is None:
        return {
            "protocol_version": "1.0",
            "request_id": req_id,
            "status": "error",
            "result": None,
            "error": {
                "code": "INVALID_INPUT",
                "message": "Nenhum arquivo ou conteúdo HAR fornecido."
            },
            "warnings": []
        }

    try:
        res = optimize_har(raw_content, options)
        out_file = input_data.get("output_file")
        if out_file:
            Path(out_file).write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
            res["output_file"] = str(out_file)

        return {
            "protocol_version": "1.0",
            "request_id": req_id,
            "status": "success",
            "result": res,
            "error": None,
            "warnings": []
        }
    except Exception as e:
        return {
            "protocol_version": "1.0",
            "request_id": req_id,
            "status": "error",
            "result": None,
            "error": {
                "code": "OPTIMIZATION_FAILED",
                "message": str(e)
            },
            "warnings": []
        }


def run_gui():
    """Interface gráfica Tkinter (Dark Theme alinhado ao Toolbox)."""
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
    from tkinter.scrolledtext import ScrolledText

    root = tk.Tk()
    root.title("HAR Optimizer — Toolbox")
    root.geometry("850x650")
    root.configure(bg="#0e1014")

    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except Exception:
        pass

    style.configure(".", background="#0e1014", foreground="#e8eaed")
    style.configure("TFrame", background="#0e1014")
    style.configure("TLabel", background="#0e1014", foreground="#e8eaed", font=("Segoe UI", 10))
    style.configure("Title.TLabel", font=("Segoe UI", 13, "bold"), foreground="#6aa3ff")
    style.configure("TButton", padding=(10, 5), font=("Segoe UI", 9))
    style.configure("Accent.TButton", background="#6aa3ff", foreground="#ffffff", font=("Segoe UI", 9, "bold"))

    top = ttk.Frame(root, style="TFrame")
    top.pack(fill="x", padx=16, pady=12)
    ttk.Label(top, text="⚡ HAR Optimizer", style="Title.TLabel").pack(side="left")

    file_var = tk.StringVar()

    row_file = ttk.Frame(root, style="TFrame")
    row_file.pack(fill="x", padx=16, pady=6)
    ttk.Label(row_file, text="Arquivo .HAR:").pack(side="left", padx=(0, 8))
    ttk.Entry(row_file, textvariable=file_var, width=50).pack(side="left", fill="x", expand=True, padx=(0, 8))

    def select_file():
        fn = filedialog.askopenfilename(title="Selecione o arquivo .HAR", filetypes=[("HTTP Archive", "*.har"), ("JSON", "*.json"), ("Todos", "*.*")])
        if fn:
            file_var.set(fn)

    ttk.Button(row_file, text="Procurar...", command=select_file).pack(side="left")

    out_text = ScrolledText(root, bg="#161a21", fg="#e8eaed", insertbackground="#e8eaed", font=("Consolas", 10))
    out_text.pack(fill="both", expand=True, padx=16, pady=10)

    def process():
        fn = file_var.get().strip()
        if not fn:
            messagebox.showwarning("Aviso", "Selecione um arquivo .har.")
            return
        payload = {"input_file": fn, "options": {"mask_sensitive_data": True}}
        resp = handle_ipc(payload)
        out_text.delete("1.0", tk.END)
        out_text.insert("1.0", json.dumps(resp, indent=2, ensure_ascii=False))

    btn_row = ttk.Frame(root, style="TFrame")
    btn_row.pack(fill="x", padx=16, pady=(0, 12))
    ttk.Button(btn_row, text="Otimizar HAR", style="Accent.TButton", command=process).pack(side="right")

    root.mainloop()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--gui":
        run_gui()
    elif not sys.stdin.isatty():
        try:
            raw = sys.stdin.read()
            if raw.strip():
                data = json.loads(raw)
                res = handle_ipc(data)
                print(json.dumps(res, ensure_ascii=False), flush=True)
            else:
                run_gui()
        except Exception as e:
            err_res = {
                "protocol_version": "1.0",
                "request_id": "req_err",
                "status": "error",
                "result": None,
                "error": {"code": "PARSE_ERROR", "message": str(e)},
                "warnings": []
            }
            print(json.dumps(err_res, ensure_ascii=False), flush=True)
    else:
        run_gui()
