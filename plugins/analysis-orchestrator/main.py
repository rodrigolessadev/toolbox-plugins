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


def _get_theme():
    try:
        from shared.theme_utils import (
            THEME,
            create_card_frame,
            create_info_banner,
            create_modal_window,
            create_primary_button,
            create_secondary_button,
            create_styled_entry,
            create_styled_text,
            setup_app_theme,
        )
        return {
            "THEME": THEME,
            "create_card_frame": create_card_frame,
            "create_info_banner": create_info_banner,
            "create_modal_window": create_modal_window,
            "create_primary_button": create_primary_button,
            "create_secondary_button": create_secondary_button,
            "create_styled_entry": create_styled_entry,
            "create_styled_text": create_styled_text,
            "setup_app_theme": setup_app_theme,
        }
    except ImportError:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from shared.theme_utils import (
            THEME,
            create_card_frame,
            create_info_banner,
            create_modal_window,
            create_primary_button,
            create_secondary_button,
            create_styled_entry,
            create_styled_text,
            setup_app_theme,
        )
        return {
            "THEME": THEME,
            "create_card_frame": create_card_frame,
            "create_info_banner": create_info_banner,
            "create_modal_window": create_modal_window,
            "create_primary_button": create_primary_button,
            "create_secondary_button": create_secondary_button,
            "create_styled_entry": create_styled_entry,
            "create_styled_text": create_styled_text,
            "setup_app_theme": setup_app_theme,
        }


def show_help_dialog(parent):
    """Exibe janela modal com instrucoes detalhadas de operacao utilizando o tema compartilhado."""
    theme_helpers = _get_theme()
    create_modal_window = theme_helpers["create_modal_window"]
    create_styled_text = theme_helpers["create_styled_text"]
    create_primary_button = theme_helpers["create_primary_button"]
    THEME = theme_helpers["THEME"]

    import tkinter as tk

    win = create_modal_window(parent, "Guia de Uso & Instruções — Analysis Orchestrator", "880x620")

    header_frame = tk.Frame(win, bg=THEME["bg_base"])
    header_frame.pack(fill="x", padx=20, pady=(16, 8))

    tk.Label(
        header_frame,
        text="📘 Guia de Uso do Analysis Orchestrator",
        font=("Segoe UI", 13, "bold"),
        bg=THEME["bg_base"],
        fg=THEME["accent"]
    ).pack(side="left")

    help_txt = create_styled_text(win, font=("Segoe UI", 9.5))
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

    btn_close = create_primary_button(win, "Fechar", win.destroy)
    btn_close.pack(pady=(0, 14))


def run_gui():
    """Interface gráfica Tkinter remodelada com Design System Soft Dark (Slate Navy)."""
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    theme_helpers = _get_theme()
    THEME = theme_helpers["THEME"]
    setup_app_theme = theme_helpers["setup_app_theme"]
    create_card_frame = theme_helpers["create_card_frame"]
    create_styled_entry = theme_helpers["create_styled_entry"]
    create_styled_text = theme_helpers["create_styled_text"]
    create_primary_button = theme_helpers["create_primary_button"]
    create_secondary_button = theme_helpers["create_secondary_button"]
    create_info_banner = theme_helpers["create_info_banner"]

    root = tk.Tk()
    root.title("Analysis Orchestrator — Toolbox")
    root.geometry("960x740")
    setup_app_theme(root)

    # 1. Header Frame
    header = ttk.Frame(root, style="TFrame")
    header.pack(fill="x", padx=18, pady=(14, 8))

    title_box = ttk.Frame(header, style="TFrame")
    title_box.pack(side="left")

    ttk.Label(title_box, text="Analysis Orchestrator", style="Title.TLabel").pack(side="left")
    
    badge = tk.Label(
        title_box,
        text="v1.0.1",
        font=("Segoe UI", 8, "bold"),
        bg=THEME["bg_hover"],
        fg=THEME["fg_secondary"],
        padx=6,
        pady=1
    )
    badge.pack(side="left", padx=(8, 0))

    btn_help = create_secondary_button(
        header,
        "ℹ️ Ajuda & Instruções",
        command=lambda: show_help_dialog(root)
    )
    btn_help.pack(side="right")

    # 2. Info Banner
    create_info_banner(
        root,
        "💡 Como usar: 1. Selecione o diretório com os dados da análise  •  2. Escolha a ação  •  3. Clique em 'Executar Ação'. Clique em 'Ajuda & Instruções' para o guia completo."
    ).pack(fill="x", padx=18, pady=(0, 10))

    # 3. Card de Configurações
    card_config = create_card_frame(root)
    card_config.pack(fill="x", padx=18, pady=(0, 10))

    card_inner = ttk.Frame(card_config, style="Card.TFrame")
    card_inner.pack(fill="x", padx=14, pady=12)

    ttk.Label(card_inner, text="Configurações da Investigação", style="Section.TLabel").pack(anchor="w", pady=(0, 8))

    dir_var = tk.StringVar()
    action_var = tk.StringVar(value="run_analysis")
    dry_var = tk.BooleanVar(value=False)

    # Linha do Diretório
    row_dir = ttk.Frame(card_inner, style="Card.TFrame")
    row_dir.pack(fill="x", pady=(0, 8))

    ttk.Label(row_dir, text="Diretório de Análise:", style="Card.TLabel").pack(side="left", padx=(0, 8))
    
    entry_dir = create_styled_entry(row_dir, textvariable=dir_var)
    entry_dir.pack(side="left", fill="x", expand=True, padx=(0, 8), ipady=3)

    def select_dir():
        dn = filedialog.askdirectory(title="Selecione o diretório de análise")
        if dn:
            dir_var.set(dn)

    btn_browse = create_secondary_button(row_dir, "Procurar...", command=select_dir)
    btn_browse.pack(side="left")

    # Linha de Opções
    row_opts = ttk.Frame(card_inner, style="Card.TFrame")
    row_opts.pack(fill="x")

    ttk.Label(row_opts, text="Ação:", style="Card.TLabel").pack(side="left", padx=(0, 8))
    
    cb_action = ttk.Combobox(
        row_opts,
        textvariable=action_var,
        values=["run_analysis", "discover", "validate_results", "resume"],
        width=18,
        state="readonly"
    )
    cb_action.pack(side="left", padx=(0, 18))

    chk_dry = ttk.Checkbutton(
        row_opts,
        text="Simulação (Dry Run)",
        variable=dry_var,
        style="Card.TCheckbutton"
    )
    chk_dry.pack(side="left")

    # 4. Card de Resultados & Console
    card_output = create_card_frame(root)
    card_output.pack(fill="both", expand=True, padx=18, pady=(0, 10))

    out_inner = ttk.Frame(card_output, style="Card.TFrame")
    out_inner.pack(fill="both", expand=True, padx=14, pady=12)

    ttk.Label(out_inner, text="Console de Execução & Relatório", style="Section.TLabel").pack(anchor="w", pady=(0, 6))

    out_text = create_styled_text(out_inner, font=("Consolas", 9.5))
    out_text.pack(fill="both", expand=True)

    # 5. Barra Inferior de Ações
    bottom_bar = ttk.Frame(root, style="TFrame")
    bottom_bar.pack(fill="x", padx=18, pady=(0, 14))

    lbl_status = ttk.Label(bottom_bar, text="Pronto.", style="Muted.TLabel")
    lbl_status.pack(side="left")

    def process():
        dn = dir_var.get().strip()
        if not dn:
            messagebox.showwarning("Aviso", "Selecione o diretório de análise antes de prosseguir.")
            return
        
        lbl_status.configure(text="Executando ação...")
        root.update_idletasks()
        
        payload = {
            "action": action_var.get(),
            "input": {"analysis_directory": dn},
            "options": {"dry_run": dry_var.get()}
        }
        resp = handle_ipc(payload)
        out_text.delete("1.0", tk.END)
        out_text.insert("1.0", json.dumps(resp, indent=2, ensure_ascii=False))
        
        if resp.get("status") == "success":
            lbl_status.configure(text="✓ Concluído com sucesso.")
        else:
            lbl_status.configure(text="⚠ Ocorreu uma falha na execução.")

    btn_run = create_primary_button(bottom_bar, "Executar Ação", command=process)
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
