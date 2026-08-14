#!/usr/bin/env python3
"""
Plugin: Analysis Orchestrator
Entrada: Protocolo IPC v1.0 (STDIN/STDOUT JSON) ou Interface Grafica Tkinter.
"""
import importlib.util
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


def _load_domain():
    spec = importlib.util.spec_from_file_location("analysis_orchestrator_domain_pkg", Path(__file__).parent / "domain.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


run_orchestration = _load_domain().run_orchestration


def handle_ipc(input_data: dict) -> dict:
    """Processa requisicao via Protocolo IPC v1.0."""
    req_id = input_data.get("request_id", "req_default")
    action = input_data.get("action", "run_analysis")
    input_cfg = input_data.get("input", {})
    options = input_data.get("options", {})

    analysis_dir = input_cfg.get("analysis_directory") or input_data.get("analysis_directory") or input_data.get("directory")
    if not analysis_dir:
        return {
            "protocol_version": "1.0",
            "request_id": req_id,
            "status": "error",
            "result": None,
            "error": {
                "code": "MISSING_ANALYSIS_DIRECTORY",
                "message": "Campo 'analysis_directory' nao fornecido.",
            },
            "warnings": [],
        }

    try:
        res = run_orchestration(analysis_dir, options)
        return {
            "protocol_version": "1.0",
            "request_id": req_id,
            "status": "success",
            "result": res,
            "error": None,
            "warnings": res.get("warnings", []),
        }
    except Exception as e:
        return {
            "protocol_version": "1.0",
            "request_id": req_id,
            "status": "error",
            "result": None,
            "error": {
                "code": "ORCHESTRATION_FAILED",
                "message": str(e),
            },
            "warnings": [],
        }


def run_gui():
    """Interface grafica Tkinter (Dark Theme alinhado ao Toolbox)."""
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
    from tkinter.scrolledtext import ScrolledText

    root = tk.Tk()
    root.title("Analysis Orchestrator — Toolbox")
    root.geometry("950x720")
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
    ttk.Label(top, text="🚀 Analysis Orchestrator Pipeline", style="Title.TLabel").pack(side="left")

    dir_var = tk.StringVar()

    row_dir = ttk.Frame(root, style="TFrame")
    row_dir.pack(fill="x", padx=16, pady=6)
    ttk.Label(row_dir, text="Diretório de Análise:").pack(side="left", padx=(0, 8))
    ttk.Entry(row_dir, textvariable=dir_var, width=50).pack(side="left", fill="x", expand=True, padx=(0, 8))

    def select_dir():
        dn = filedialog.askdirectory(title="Selecione o diretório de análise")
        if dn:
            dir_var.set(dn)

    ttk.Button(row_dir, text="Procurar...", command=select_dir).pack(side="left")

    out_text = ScrolledText(root, bg="#161a21", fg="#e8eaed", insertbackground="#e8eaed", font=("Consolas", 10))
    out_text.pack(fill="both", expand=True, padx=16, pady=10)

    def process():
        dn = dir_var.get().strip()
        if not dn:
            messagebox.showwarning("Aviso", "Selecione o diretório de análise.")
            return
        payload = {"input": {"analysis_directory": dn}}
        resp = handle_ipc(payload)
        out_text.delete("1.0", tk.END)
        out_text.insert("1.0", json.dumps(resp, indent=2, ensure_ascii=False))

    btn_row = ttk.Frame(root, style="TFrame")
    btn_row.pack(fill="x", padx=16, pady=(0, 12))
    ttk.Button(btn_row, text="Executar Análise Completa", style="Accent.TButton", command=process).pack(side="right")

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
                "warnings": [],
            }
            print(json.dumps(err_res, ensure_ascii=False), flush=True)
    else:
        run_gui()
