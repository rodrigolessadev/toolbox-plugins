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


domain_pkg = _load_domain()


def handle_ipc(input_data: dict) -> dict:
    """Processa requisicao via Protocolo IPC v1.0."""
    req_id = input_data.get("request_id", "req_default")
    action = input_data.get("action", "run_analysis")
    input_cfg = input_data.get("input", {})
    options = input_data.get("options", {})

    analysis_dir = input_cfg.get("analysis_directory") or input_data.get("analysis_directory") or input_data.get("directory")
    results_dir = input_cfg.get("results_directory") or input_data.get("results_directory")

    if action in ("run_analysis", "discover") and not analysis_dir:
        return {
            "protocol_version": "1.0",
            "request_id": req_id,
            "status": "error",
            "result": None,
            "error": {
                "code": "ANALYSIS_DIRECTORY_NOT_FOUND",
                "message": "Campo 'analysis_directory' nao fornecido.",
            },
            "warnings": [],
        }

    try:
        if action == "discover":
            res = domain_pkg.discover_analysis_directory(analysis_dir, options)
        elif action == "run_plugin":
            plugin_name = input_cfg.get("plugin") or options.get("plugin")
            if not plugin_name:
                return {
                    "protocol_version": "1.0",
                    "request_id": req_id,
                    "status": "error",
                    "result": None,
                    "error": {
                        "code": "PLUGIN_NOT_FOUND",
                        "message": "Nome do plugin nao informado para run_plugin.",
                    },
                    "warnings": [],
                }
            res = domain_pkg.run_single_plugin(analysis_dir, plugin_name, options)
        elif action == "validate_results":
            target_res_dir = results_dir or analysis_dir
            res = domain_pkg.validate_results_directory(target_res_dir)
        elif action == "resume":
            res = domain_pkg.resume_orchestration(results_dir or analysis_dir, options)
        else:  # run_analysis
            res = domain_pkg.run_orchestration(analysis_dir, options)

        return {
            "protocol_version": "1.0",
            "request_id": req_id,
            "status": "success",
            "result": res,
            "error": None,
            "warnings": res.get("warnings", []),
        }
    except ValueError as ve:
        err_str = str(ve)
        code = "INVALID_REQUEST"
        if "inexistente" in err_str.lower():
            code = "ANALYSIS_DIRECTORY_NOT_FOUND"
        elif "plugin" in err_str.lower() and "desconhecido" in err_str.lower():
            code = "PLUGIN_NOT_FOUND"
        return {
            "protocol_version": "1.0",
            "request_id": req_id,
            "status": "error",
            "result": None,
            "error": {"code": code, "message": err_str},
            "warnings": [],
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


def show_help_dialog(parent):
    """Exibe janela modal com instrucoes detalhadas de operacao."""
    import tkinter as tk
    from tkinter.scrolledtext import ScrolledText

    DARK = {
        "bg": "#0e1014",
        "bg2": "#161a21",
        "fg": "#e8eaed",
        "muted": "#8b94a3",
        "accent": "#6aa3ff",
        "border": "#2b3240"
    }

    win = tk.Toplevel(parent)
    win.title("Guia de Uso & Instruções — Analysis Orchestrator")
    win.geometry("860x620")
    win.configure(bg=DARK["bg"])
    win.transient(parent)
    win.grab_set()

    header_frame = tk.Frame(win, bg=DARK["bg"])
    header_frame.pack(fill="x", padx=20, pady=(16, 8))

    tk.Label(
        header_frame,
        text="📘 Guia de Uso do Analysis Orchestrator",
        font=("Segoe UI", 13, "bold"),
        bg=DARK["bg"],
        fg=DARK["accent"]
    ).pack(side="left")

    help_txt = ScrolledText(
        win,
        bg=DARK["bg2"],
        fg=DARK["fg"],
        insertbackground=DARK["fg"],
        font=("Segoe UI", 10),
        relief="solid",
        bd=1,
        highlightthickness=1,
        highlightbackground=DARK["border"]
    )
    help_txt.pack(fill="both", expand=True, padx=20, pady=10)

    guide_text = """================================================================================
                    ANALYSIS ORCHESTRATOR — GUIA DE OPERAÇÃO
================================================================================

O Analysis Orchestrator automatiza de forma determinística toda a esteira de análise 
e extração de evidências de incidentes, executando sanitização, filtragem, agrupamento, 
timelines, inspeção de tráfego HTTP/HAR, extração de código e geração de pacotes.

--------------------------------------------------------------------------------
1. COMO UTILIZAR O PLUGIN
--------------------------------------------------------------------------------
Passo 1: Clique em 'Procurar...' e selecione o diretório que contém os artefatos do 
         incidente a ser investigado.
Passo 2: Selecione a ação desejada no campo 'Ação'.
Passo 3: (Opcional) Marque 'Simulação (Dry Run)' caso queira apenas inspecionar o plano 
         de execução sem criar pastas nem gravar arquivos em disco.
Passo 4: Clique em 'Executar Ação' e visualize os detalhes da execução no console abaixo.

--------------------------------------------------------------------------------
2. AÇÕES DISPONÍVEIS
--------------------------------------------------------------------------------
• run_analysis:
  Executa a esteira analítica completa. Cria automaticamente um diretório versionado 
  'analysis-results-YYYYMMDD-HHMMSS' dentro da pasta de análise e gera todos os 
  relatórios e artefatos estruturados.

• discover:
  Realiza uma varredura recursiva de ativos (logs, HAR, pastas de fontes e metadados) 
  e exibe o plano previsto do pipeline sem gravar nada em disco.

• validate_results:
  Verifica a integridade de uma pasta de resultados previamente gerada, validando 
  a existência do 'manifest.json', 'execution-summary.json' e a integridade de todos 
  os arquivos derivados.

• resume:
  Retoma a execução do pipeline a partir de uma pasta de resultados existente.

--------------------------------------------------------------------------------
3. ESTRUTURA DE ARQUIVOS SUPORTADA
--------------------------------------------------------------------------------
O plugin reconhece automaticamente e sem necessidade de organização prévia:
• Logs: .log, .txt, .jsonl, .ndjson, .out, .err (ou dentro de uma pasta 'logs/').
• Tráfego HTTP: Arquivos .har (ou dentro de uma pasta 'har/').
• Código-fonte: Pastas 'source/' ou 'src/' contendo arquivos .py, .ts, .js, .java, etc.
• Metadados de Incidente: 'incident.json' ou 'metadata.json' contendo time_range, 
  services, levels, keywords e correlation_ids para guiar as filtragens.

--------------------------------------------------------------------------------
4. ARTEFATOS E RESULTADOS GERADOS
--------------------------------------------------------------------------------
Todos os resultados são gravados dentro de 'analysis-results-YYYYMMDD-HHMMSS/':
• manifest.json              -> Catálogo completo e versão do pipeline.
• execution-summary.json     -> Detalhamento do status de cada etapa executada.
• sanitized/                 -> Logs com credenciais e tokens mascarados.
• filtered/                  -> Logs filtrados pelos critérios do incidente.
• optimized/                 -> Redução estatística de logs e requisições HAR.
• clusters/                  -> Agrupamentos por similaridade de templates.
• timelines/                 -> Linha do tempo cronológica em UTC (JSON e Markdown).
• source-extracts/           -> Trechos de código extraídos por termos/funções.
• evidence/                  -> 5 artefatos padronizados para auditoria e relatórios.
• reports/summary.md         -> Relatório executivo consolidado em Markdown.

--------------------------------------------------------------------------------
5. SEGURANÇA E PRIVACIDADE
--------------------------------------------------------------------------------
• Execução 100% local e determinística (sem IA, APIs externas ou envio de dados).
• Os arquivos originais NUNCA são modificados ou sobrescritos.
• Mascaramento automático de JWT, Bearer tokens, senhas, chaves privadas, CPFs e CNPJs.
"""

    help_txt.insert("1.0", guide_text)
    help_txt.configure(state="disabled")

    btn_close = tk.Button(
        win,
        text="Fechar",
        font=("Segoe UI", 9, "bold"),
        bg=DARK["accent"],
        fg="#ffffff",
        relief="flat",
        padx=16,
        pady=5,
        cursor="hand2",
        command=win.destroy
    )
    btn_close.pack(pady=10)


def run_gui():
    """Interface grafica Tkinter (Dark Theme alinhado ao Toolbox)."""
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
    from tkinter.scrolledtext import ScrolledText

    root = tk.Tk()
    root.title("Analysis Orchestrator — Toolbox")
    root.geometry("960x740")
    root.configure(bg="#0e1014")

    DARK = {
        "bg": "#0e1014",
        "bg2": "#161a21",
        "bg_card": "#12151c",
        "input_bg": "#161a21",
        "fg": "#e8eaed",
        "muted": "#8b94a3",
        "accent": "#6aa3ff",
        "border": "#2b3240",
        "info_border": "#3b82f6"
    }

    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except Exception:
        pass

    style.configure(".", background=DARK["bg"], foreground=DARK["fg"])
    style.configure("TFrame", background=DARK["bg"])
    style.configure("TLabel", background=DARK["bg"], foreground=DARK["fg"], font=("Segoe UI", 10))
    style.configure("Title.TLabel", font=("Segoe UI", 13, "bold"), foreground=DARK["accent"])
    style.configure("TButton", padding=(10, 5), font=("Segoe UI", 9), background=DARK["bg2"], foreground=DARK["fg"])
    style.configure("Accent.TButton", background=DARK["accent"], foreground="#ffffff", font=("Segoe UI", 9, "bold"))
    style.configure("TCheckbutton", background=DARK["bg"], foreground=DARK["fg"])

    style.configure("TEntry",
        fieldbackground=DARK["input_bg"],
        foreground=DARK["fg"],
        insertcolor=DARK["fg"],
        bordercolor=DARK["border"],
        lightcolor=DARK["border"],
        darkcolor=DARK["border"]
    )
    style.map("TEntry",
        fieldbackground=[("focus", "#1f242d"), ("readonly", DARK["input_bg"])],
        foreground=[("disabled", DARK["muted"])],
        bordercolor=[("focus", DARK["accent"])]
    )

    style.configure("TCombobox",
        fieldbackground=DARK["input_bg"],
        background=DARK["bg2"],
        foreground=DARK["fg"],
        arrowcolor=DARK["fg"],
        bordercolor=DARK["border"]
    )
    style.map("TCombobox",
        fieldbackground=[("readonly", DARK["input_bg"]), ("focus", "#1f242d")],
        selectbackground=[("readonly", DARK["accent"])],
        selectforeground=[("readonly", "#ffffff")]
    )

    # Cores do popup do Combobox
    root.option_add("*TCombobox*Listbox.background", DARK["input_bg"])
    root.option_add("*TCombobox*Listbox.foreground", DARK["fg"])
    root.option_add("*TCombobox*Listbox.selectBackground", DARK["accent"])
    root.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")

    # Header
    top = ttk.Frame(root, style="TFrame")
    top.pack(fill="x", padx=16, pady=(12, 6))
    ttk.Label(top, text="Analysis Orchestrator Pipeline", style="Title.TLabel").pack(side="left")

    btn_help = tk.Button(
        top,
        text="ℹ️ Ajuda & Instruções",
        font=("Segoe UI", 9),
        bg=DARK["bg2"],
        fg=DARK["accent"],
        activebackground=DARK["border"],
        relief="solid",
        bd=1,
        padx=10,
        pady=2,
        cursor="hand2",
        command=lambda: show_help_dialog(root)
    )
    btn_help.pack(side="right")

    # Banner de Instruções Rápidas
    instruction_card = tk.Frame(root, bg=DARK["bg_card"], bd=1, relief="solid", highlightthickness=1, highlightbackground=DARK["border"])
    instruction_card.pack(fill="x", padx=16, pady=(0, 10))

    tk.Label(
        instruction_card,
        text="💡 Como usar: 1. Selecione a pasta com os dados da análise  •  2. Escolha a ação  •  3. Clique em 'Executar Ação'. Clique em 'Ajuda & Instruções' para detalhes.",
        font=("Segoe UI", 9),
        bg=DARK["bg_card"],
        fg=DARK["muted"]
    ).pack(padx=12, pady=6, anchor="w")

    dir_var = tk.StringVar()
    action_var = tk.StringVar(value="run_analysis")
    dry_var = tk.BooleanVar(value=False)

    row_dir = ttk.Frame(root, style="TFrame")
    row_dir.pack(fill="x", padx=16, pady=6)
    ttk.Label(row_dir, text="Diretório de Análise:").pack(side="left", padx=(0, 8))

    entry_dir = tk.Entry(
        row_dir,
        textvariable=dir_var,
        font=("Segoe UI", 10),
        bg=DARK["input_bg"],
        fg=DARK["fg"],
        insertbackground=DARK["fg"],
        relief="solid",
        bd=1,
        highlightthickness=1,
        highlightbackground=DARK["border"],
        highlightcolor=DARK["accent"]
    )
    entry_dir.pack(side="left", fill="x", expand=True, padx=(0, 8), ipady=4)

    def select_dir():
        dn = filedialog.askdirectory(title="Selecione o diretório de análise")
        if dn:
            dir_var.set(dn)

    btn_browse = tk.Button(
        row_dir,
        text="Procurar...",
        font=("Segoe UI", 9),
        bg=DARK["bg2"],
        fg=DARK["fg"],
        activebackground=DARK["border"],
        relief="solid",
        bd=1,
        padx=10,
        pady=2,
        cursor="hand2",
        command=select_dir
    )
    btn_browse.pack(side="left")

    row_opts = ttk.Frame(root, style="TFrame")
    row_opts.pack(fill="x", padx=16, pady=4)
    ttk.Label(row_opts, text="Ação:").pack(side="left", padx=(0, 8))
    ttk.Combobox(row_opts, textvariable=action_var, values=["run_analysis", "discover", "validate_results", "resume"], width=18, state="readonly").pack(side="left", padx=(0, 16))
    ttk.Checkbutton(row_opts, text="Simulação (Dry Run)", variable=dry_var).pack(side="left")

    out_text = ScrolledText(root, bg="#161a21", fg="#e8eaed", insertbackground="#e8eaed", font=("Consolas", 10))
    out_text.pack(fill="both", expand=True, padx=16, pady=10)

    def process():
        dn = dir_var.get().strip()
        if not dn:
            messagebox.showwarning("Aviso", "Selecione o diretório de análise.")
            return
        payload = {
            "action": action_var.get(),
            "input": {"analysis_directory": dn},
            "options": {"dry_run": dry_var.get()}
        }
        resp = handle_ipc(payload)
        out_text.delete("1.0", tk.END)
        out_text.insert("1.0", json.dumps(resp, indent=2, ensure_ascii=False))

    btn_row = ttk.Frame(root, style="TFrame")
    btn_row.pack(fill="x", padx=16, pady=(0, 12))

    btn_run = tk.Button(
        btn_row,
        text="Executar Ação",
        font=("Segoe UI", 10, "bold"),
        bg=DARK["accent"],
        fg="#ffffff",
        activebackground="#5090f0",
        relief="flat",
        padx=16,
        pady=6,
        cursor="hand2",
        command=process
    )
    btn_run.pack(side="right")

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
