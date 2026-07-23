#!/usr/bin/env python3
"""
Plugin: Stract Log
Filtra blocos de log por nível, parâmetro adicional e regra de recorrência
(mais recente / mais antiga) e salva o resultado em um arquivo .log.

Um "bloco" começa em uma linha com o formato:
    <prefixo> [DD-MM-YYYY HH:MM:SS] <LEVEL>: <mensagem>
e continua nas linhas seguintes até a próxima linha que case o mesmo padrão
ou até o fim do arquivo. Linhas que começam com whitespace, "	at ",
"Caused by:", "..." ou exceções multilinha (stack traces) são tratadas como
continuação.
"""
from __future__ import annotations

import os
import re
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox, ttk
from typing import List, Optional, Tuple


# ─── Regex e parser ────────────────────────────────────────────────────────

# Cabeçalho de um bloco: "prefixo [data] LEVEL: mensagem"
# Capturas: 1=prefixo (ex: "sync "), 2=timestamp, 3=level, 4=conteúdo
BLOCK_HEADER_RE = re.compile(
    r"^(\S.*?)?\s*\[(\d{2}-\d{2}-\d{4}\s+\d{2}:\d{2}:\d{2})\]\s+"
    r"(SEVERE|WARNING|INFO|FINE|ERROR|FINEST|FINER|CONFIG|DEBUG|TRACE|ALL|OFF)\s*:\s*(.*)$"
)

LEVELS = ["SEVERE", "WARNING", "INFO", "FINE", "ERROR", "FINEST", "FINER", "CONFIG", "DEBUG", "TRACE"]


def parse_blocks(text: str) -> List[dict]:
    """Divide o texto em blocos. Cada bloco = header + linhas de continuação.

    Linhas vazias entre blocos são descartadas; linhas vazias dentro de um
    bloco (ex: antes de uma stack trace) são preservadas como continuação.
    """
    lines = text.splitlines()
    blocks: List[dict] = []
    current: Optional[dict] = None

    for line in lines:
        m = BLOCK_HEADER_RE.match(line)
        if m:
            if current is not None:
                blocks.append(current)
            prefix = (m.group(1) or "").strip()
            current = {
                "prefix": prefix,
                "timestamp": m.group(2).strip(),
                "level": m.group(3).strip().upper(),
                "header": m.group(4).strip(),
                "lines": [line],
            }
        else:
            if current is None:
                # Conteúdo antes do primeiro header: ignora.
                continue
            # Continuação do bloco atual (stack traces, XML, etc.)
            current["lines"].append(line)

    if current is not None:
        blocks.append(current)

    # Texto "completo" do bloco (para a regra de recorrência).
    for b in blocks:
        b["full_text"] = "\n".join(b["lines"])

    return blocks


def body_signature(block: dict) -> str:
    """Assinatura do bloco sem timestamp — usada para detectar recorrência."""
    # Remove o trecho de data/hora para comparar só o conteúdo.
    return re.sub(
        r"\[\d{2}-\d{2}-\d{4}\s+\d{2}:\d{2}:\d{2}\]\s+",
        "[TS] ",
        block["full_text"],
    ).strip()


def parse_timestamp(ts: str) -> datetime:
    return datetime.strptime(ts, "%d-%m-%Y %H:%M:%S")


# ─── Lógica de filtragem ───────────────────────────────────────────────────

def filter_blocks(
    blocks: List[dict],
    level: str,
    extra_param: str,
    group_repetitions: bool,
    keep: str,
) -> List[dict]:
    """Aplica os filtros e (opcionalmente) agrupa recorrências."""
    level = (level or "").strip().upper()
    extra = (extra_param or "").strip()

    # 1) Filtro por nível e parâmetro.
    filtered: List[dict] = []
    for b in blocks:
        if level and b["level"] != level:
            continue
        if extra and extra.lower() not in b["full_text"].lower():
            continue
        filtered.append(b)

    # 2) Regra de recorrência.
    if not group_repetitions:
        return filtered

    # Agrupa por assinatura preservando ordem da primeira aparição.
    groups: dict[str, List[dict]] = {}
    order: List[str] = []
    for b in filtered:
        sig = body_signature(b)
        if sig not in groups:
            groups[sig] = []
            order.append(sig)
        groups[sig].append(b)

    # Mantém a ocorrência escolhida. "items" está em ordem de aparição no
    # arquivo (do mais antigo para o mais recente).
    keep_recent = (keep or "recente").lower().startswith("rec")
    result: List[dict] = []
    for sig in order:
        items = groups[sig]
        chosen = items[-1] if keep_recent else items[0]
        result.append(chosen)
    return result


# ─── Persistência ──────────────────────────────────────────────────────────

def write_output(source_path: str, blocks: List[dict]) -> str:
    base_dir = os.path.dirname(os.path.abspath(source_path))
    base_name = os.path.splitext(os.path.basename(source_path))[0]
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_path = os.path.join(base_dir, f"{base_name}-stract-{stamp}.log")
    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        for b in blocks:
            f.write(b["full_text"])
            f.write("\n")
    return out_path


# ─── UI ────────────────────────────────────────────────────────────────────

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


def build_ui() -> None:
    root = tk.Tk()
    root.title("Stract Log")
    root.geometry("680x420")
    root.configure(bg=DARK["bg"])
    root.resizable(True, True)

    style = ttk.Style()
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    style.configure("TLabel",   background=DARK["bg"],  foreground=DARK["fg"])
    style.configure("TButton",  padding=6)
    style.configure("TEntry",   fieldbackground=DARK["input_bg"], foreground=DARK["fg"])
    style.configure("TCombobox", fieldbackground=DARK["input_bg"], foreground=DARK["fg"])
    style.configure("TCheckbutton", background=DARK["bg"], foreground=DARK["fg"])
    style.configure("TRadiobutton", background=DARK["bg"], foreground=DARK["fg"])
    style.configure("TFrame",   background=DARK["bg"])
    style.configure("TLabelframe", background=DARK["bg"], foreground=DARK["fg"])
    style.configure("TLabelframe.Label", background=DARK["bg"], foreground=DARK["muted"])

    # ── Título ──
    ttk.Label(root, text="Stract Log",
              font=("Segoe UI", 15, "bold")).pack(pady=(18, 2))
    ttk.Label(root, text="Filtra blocos de log por nível, parâmetro e recorrência.",
              font=("Segoe UI", 9), foreground=DARK["muted"]).pack(pady=(0, 12))

    form = ttk.Frame(root)
    form.pack(fill="x", padx=18)

    # ── Arquivo ──
    ttk.Label(form, text="Arquivo", font=("Segoe UI", 9, "bold"),
              foreground=DARK["muted"]).grid(row=0, column=0, sticky="w", pady=(0, 4))
    file_frame = ttk.Frame(form)
    file_frame.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(0, 10))
    form.columnconfigure(0, weight=1)

    file_var = tk.StringVar()
    entry_file = ttk.Entry(file_frame, textvariable=file_var, font=("Segoe UI", 10))
    entry_file.pack(side="left", fill="x", expand=True)

    def pick_file() -> None:
        path = filedialog.askopenfilename(
            title="Selecionar arquivo de log",
            filetypes=[("Arquivos de log", "*.log *.txt"), ("Todos os arquivos", "*.*")],
        )
        if path:
            file_var.set(path)

    tk.Button(
        file_frame, text="Procurar…", font=("Segoe UI", 9),
        bg=DARK["bg2"], fg=DARK["fg"], activebackground=DARK["border"],
        relief="flat", cursor="hand2", padx=12, pady=4, command=pick_file,
    ).pack(side="left", padx=(8, 0))

    # ── Level ──
    ttk.Label(form, text="Level", font=("Segoe UI", 9, "bold"),
              foreground=DARK["muted"]).grid(row=2, column=0, sticky="w", pady=(0, 4))
    level_var = tk.StringVar(value=LEVELS[0])
    combo_level = ttk.Combobox(
        form, textvariable=level_var, values=LEVELS,
        state="readonly", font=("Segoe UI", 10),
    )
    combo_level.grid(row=3, column=0, sticky="ew", pady=(0, 10))

    # ── Parâmetro adicional ──
    ttk.Label(form, text="Parâmetro adicional",
              font=("Segoe UI", 9, "bold"),
              foreground=DARK["muted"]).grid(row=4, column=0, sticky="w", pady=(0, 4))
    entry_param = ttk.Entry(form, font=("Segoe UI", 10))
    entry_param.grid(row=5, column=0, sticky="ew", pady=(0, 10))

    # ── Recorrências (toggle) ──
    recur_var = tk.BooleanVar(value=False)

    # ── Ocorrência (radios) — inicialmente desabilitados ──
    keep_var = tk.StringVar(value="recente")

    def on_recur_toggle() -> None:
        state = "normal" if recur_var.get() else "disabled"
        radio_recente.configure(state=state)
        radio_antiga.configure(state=state)

    check_recur = ttk.Checkbutton(
        form, text="Recorrências (agrupar blocos com o mesmo conteúdo)",
        variable=recur_var, command=on_recur_toggle,
    )
    check_recur.grid(row=6, column=0, sticky="w", pady=(0, 4))

    radio_frame = ttk.Frame(form)
    radio_frame.grid(row=7, column=0, sticky="w", pady=(0, 12))
    radio_recente = ttk.Radiobutton(
        radio_frame, text="Mais recente", value="recente", variable=keep_var,
    )
    radio_recente.pack(side="left", padx=(0, 16))
    radio_antiga = ttk.Radiobutton(
        radio_frame, text="Mais antiga", value="antiga", variable=keep_var,
    )
    radio_antiga.pack(side="left")

    on_recur_toggle()

    # ── Status ──
    status_var = tk.StringVar(value="")
    lbl_status = ttk.Label(root, textvariable=status_var,
                           font=("Segoe UI", 9), foreground=DARK["muted"])
    lbl_status.pack(anchor="w", padx=20, pady=(4, 0))

    # ── Botão Executar ──
    def do_extract() -> None:
        path = file_var.get().strip()
        if not path:
            messagebox.showwarning("Atenção", "Selecione um arquivo de log.")
            return
        if not os.path.isfile(path):
            messagebox.showerror("Arquivo inválido", f"Não foi possível ler:\n{path}")
            return

        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                text = f.read()
        except OSError as e:
            messagebox.showerror("Erro de leitura", str(e))
            return

        blocks = parse_blocks(text)
        if not blocks:
            messagebox.showinfo(
                "Sem blocos",
                "Nenhuma linha de log no formato esperado foi encontrada.",
            )
            return

        result = filter_blocks(
            blocks,
            level=level_var.get(),
            extra_param=entry_param.get(),
            group_repetitions=recur_var.get(),
            keep=keep_var.get(),
        )

        if not result:
            messagebox.showinfo(
                "Nada encontrado",
                "Nenhum bloco corresponde aos filtros informados.",
            )
            status_var.set("0 blocos selecionados.")
            return

        try:
            out_path = write_output(path, result)
        except OSError as e:
            messagebox.showerror("Erro ao salvar", str(e))
            return

        msg = f"{len(result)} bloco(s) salvo(s) em:\n{out_path}"
        status_var.set(msg)
        messagebox.showinfo("Concluído", msg)

    btn_frame = ttk.Frame(root)
    btn_frame.pack(fill="x", padx=18, pady=(12, 16))

    btn_run = tk.Button(
        btn_frame, text="Filtrar e salvar", font=("Segoe UI", 10, "bold"),
        bg=DARK["accent"], fg="#fff", activebackground="#4a83df",
        relief="flat", cursor="hand2", padx=18, pady=6, command=do_extract,
    )
    btn_run.pack(side="left")

    btn_clear = tk.Button(
        btn_frame, text="Limpar", font=("Segoe UI", 10),
        bg=DARK["bg2"], fg=DARK["fg"], activebackground=DARK["border"],
        relief="flat", cursor="hand2", padx=18, pady=6,
        command=lambda: [
            file_var.set(""),
            level_var.set(LEVELS[0]),
            entry_param.delete(0, "end"),
            recur_var.set(False),
            keep_var.set("recente"),
            on_recur_toggle(),
            status_var.set(""),
        ],
    )
    btn_clear.pack(side="left", padx=(8, 0))

    root.bind("<Control-Return>", lambda e: do_extract())
    entry_param.bind("<Return>", lambda e: do_extract())
    root.mainloop()


if __name__ == "__main__":
    build_ui()
