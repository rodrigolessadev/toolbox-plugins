#!/usr/bin/env python3
"""
Plugin: Gerador de AFD
Gera arquivo AFD (Arquivo de Fonte de Dados) no padrão REP-C.
Porta fiel do afd/page.tsx do KapiNote.

Registros gerados:
  Tipo 1 — Cabeçalho do empregador
  Tipo 2 — Registro de estabelecimento
  Tipo 3 — Marcações de ponto (um por colaborador × horário × dia)
  Tipo 9 — Trailer (encerramento)

CRC16 conforme padrão REP (CCITT / XModem): polinômio 0x1021.
Download salva como ISO-8859-1 com CRLF, conforme spec.
"""
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
from datetime import datetime, date, timedelta
from pathlib import Path

# ─── CRC16 ────────────────────────────────────────────────────────────────

def calcular_crc16(data: str) -> str:
    """CRC16-CCITT (XModem), polinômio 0x1021, IV=0x0000."""
    crc = 0x0000
    for ch in data:
        crc ^= ord(ch) << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) if (crc & 0x8000) else (crc << 1)
            crc &= 0xFFFF
    return crc.to_bytes(2, "big").hex().upper().zfill(4)


# ─── Helpers de formatação ────────────────────────────────────────────────

def limpar_numero(s: str) -> str:
    return "".join(c for c in s if c.isdigit())


def pad_left(value, size: int) -> str:
    return str(value).zfill(size)


def pad_right(value: str, size: int) -> str:
    return value.ljust(size)


def format_dh(dt: datetime) -> str:
    """Formata datetime para o padrão AFD: yyyy-MM-ddTHH:mm:00-0300"""
    return dt.strftime("%Y-%m-%dT%H:%M:00-0300")


# ─── Geração do AFD ───────────────────────────────────────────────────────

def gerar_afd(
    rep_number: str,
    cnpj: str,
    razao_social: str,
    data_inicial: str,
    data_final: str,
    colaboradores: list[dict],
) -> str:
    """
    Gera o conteúdo do arquivo AFD.

    Args:
        rep_number: número do REP (até 17 dígitos).
        cnpj: CNPJ do empregador (com ou sem máscara).
        razao_social: razão social (até 150 chars).
        data_inicial: "AAAA-MM-DD".
        data_final: "AAAA-MM-DD".
        colaboradores: lista de dicts {"cpf": str, "horarios": list[str]}.
            Horários no formato "HHMM" (4 dígitos) ou "HH:MM".

    Returns:
        String com todo o conteúdo AFD (CRLF entre linhas).
    """
    linhas: list[str] = []
    nsr = 1
    now = datetime.now()

    rep_num_clean = pad_left(limpar_numero(rep_number), 17)
    cnpj_clean    = pad_left(limpar_numero(cnpj), 14)
    razao_padded  = pad_right(razao_social, 150)[:150]

    # ── Registro Tipo 1 — Cabeçalho ──
    reg1_base = (
        pad_left(0, 9) +
        "1" +
        "1" +
        cnpj_clean +
        pad_left("", 14) +
        razao_padded +
        rep_num_clean +
        data_inicial +
        data_final +
        format_dh(now) +
        "003" +
        "1" +
        "12345678000195" +
        pad_right("ModeloREP-C", 30)[:30]
    )
    linhas.append(reg1_base + calcular_crc16(reg1_base))

    # ── Registro Tipo 2 — Estabelecimento ──
    reg2_base = (
        pad_left(nsr, 9) +
        "2" +
        format_dh(now) +
        pad_left("10547292040", 14) +
        "1" +
        cnpj_clean +
        pad_left("", 14) +
        razao_padded +
        pad_right("Local de Trabalho", 100)
    )
    linhas.append(reg2_base + calcular_crc16(reg2_base))
    nsr += 1

    # ── Gera datas do intervalo ──
    try:
        d_ini = date.fromisoformat(data_inicial)
        d_fim = date.fromisoformat(data_final)
    except ValueError:
        raise ValueError(f"Datas inválidas: {data_inicial!r} / {data_final!r}")

    dias: list[date] = []
    cur = d_ini
    while cur <= d_fim:
        dias.append(cur)
        cur += timedelta(days=1)

    # ── Registros Tipo 3 — Marcações ──
    total_marcacoes = 0

    for colaborador in colaboradores:
        cpf = limpar_numero(colaborador.get("cpf", ""))
        if not cpf:
            continue

        for dia in dias:
            for h in colaborador.get("horarios", []):
                if not h:
                    continue

                # Normaliza horário: aceita "HHMM" ou "HH:MM"
                h_clean = h.replace(":", "").strip()
                if len(h_clean) < 4:
                    h_clean = h_clean.zfill(4)
                hh = h_clean[:2]
                mm = h_clean[2:4]

                try:
                    dt_marc = datetime(
                        dia.year, dia.month, dia.day,
                        int(hh), int(mm), 0,
                    )
                except ValueError:
                    continue  # hora inválida, pula

                reg3_base = (
                    pad_left(nsr, 9) +
                    "3" +
                    format_dh(dt_marc) +
                    pad_left(cpf, 12)
                )
                linhas.append(reg3_base + calcular_crc16(reg3_base))
                nsr += 1
                total_marcacoes += 1

    # ── Registro Tipo 9 — Trailer ──
    linhas.append(
        "999999999" +
        pad_left(1, 9) +
        pad_left(total_marcacoes, 9) +
        pad_left(0, 9) +
        pad_left(0, 9) +
        pad_left(0, 9) +
        pad_left(0, 9) +
        "9"
    )

    linhas.append("")  # linha final em branco (spec)
    return "\r\n".join(linhas)


def nome_arquivo(rep_number: str, cnpj: str) -> str:
    return f"AFD{limpar_numero(rep_number)}{limpar_numero(cnpj)}REP_C.TXT"


def process_gerar_afd(
    rep_number: str,
    cnpj: str,
    razao_social: str,
    data_inicial: str,
    data_final: str,
    colaboradores: list[dict],
) -> dict:
    """
    Função pura de domínio que valida entradas e gera o conteúdo do arquivo AFD REP-C.

    Returns:
        dict com chaves: success (bool), content (str), total_records (int), error (str|None)
    """
    rep_clean = rep_number.strip() if rep_number else ""
    cnpj_clean = cnpj.strip() if cnpj else ""
    razao_clean = razao_social.strip() if razao_social else ""

    if not rep_clean:
        return {"success": False, "content": "", "total_records": 0, "error": "Número do REP é obrigatório."}
    if not cnpj_clean:
        return {"success": False, "content": "", "total_records": 0, "error": "CNPJ é obrigatório."}
    if not razao_clean:
        return {"success": False, "content": "", "total_records": 0, "error": "Razão Social é obrigatória."}
    if not colaboradores:
        return {"success": False, "content": "", "total_records": 0, "error": "Ao menos um colaborador deve ser informado."}

    try:
        content = gerar_afd(
            rep_number=rep_clean,
            cnpj=cnpj_clean,
            razao_social=razao_clean,
            data_inicial=data_inicial,
            data_final=data_final,
            colaboradores=colaboradores,
        )
        lines = [l for l in content.split("\r\n") if l]
        return {"success": True, "content": content, "total_records": len(lines), "error": None}
    except Exception as e:
        return {"success": False, "content": "", "total_records": 0, "error": f"Erro na geração do AFD: {e}"}


# ─── UI ───────────────────────────────────────────────────────────────────

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from theme_utils import (
        DARK_TOKENS, setup_theme, create_primary_button,
        create_secondary_button, create_styled_text, StatusBanner
    )
except ImportError:
    DARK_TOKENS = {"bg_elev1": "#161a21", "bg_elev2": "#1f242d", "fg": "#e8eaed", "fg_muted": "#8b94a3", "border": "#262c36", "accent": "#6aa3ff", "input_bg": "#0e1014", "success": "#4cc38a", "danger": "#ff6369"}
    def setup_theme(r): pass
    def create_primary_button(p, text, command=None, **kw): return tk.Button(p, text=text, command=command, bg="#6aa3ff", fg="#fff", relief="flat")
    def create_secondary_button(p, text, command=None, **kw): return tk.Button(p, text=text, command=command, bg="#1f242d", fg="#eee", relief="flat")
    def create_styled_text(p, height=10, **kw): return tk.Text(p, height=height, bg="#0e1014", fg="#eee", relief="flat")
    class StatusBanner(ttk.Frame):
        def show_success(self, msg, **kw): pass
        def show_error(self, msg, **kw): pass
        def clear(self): pass


class GeradorAFDApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("Gerador de AFD REP-C — Toolbox")
        root.geometry("860x780")
        root.resizable(True, True)
        setup_theme(root)
        self._build_ui()


    def _apply_style(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        for w, cfg in [
            ("TLabel",      {"background": DARK["bg"],  "foreground": DARK["fg"]}),
            ("TFrame",      {"background": DARK["bg"]}),
            ("TLabelframe", {"background": DARK["bg"],  "foreground": DARK["fg"]}),
            ("TLabelframe.Label", {
                "background": DARK["bg"], "foreground": DARK["muted"],
                "font": ("Segoe UI", 9, "bold"),
            }),
            ("TEntry", {"fieldbackground": DARK["input_bg"], "foreground": DARK["fg"]}),
        ]:
            style.configure(w, **cfg)

    def _build_ui(self):
        # ── Scroll ──
        canvas = tk.Canvas(self.root, bg=DARK["bg"], highlightthickness=0)
        sb = ttk.Scrollbar(self.root, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.main = ttk.Frame(canvas)
        wid = canvas.create_window((0, 0), window=self.main, anchor="nw")
        self.main.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(wid, width=e.width))
        canvas.bind_all("<MouseWheel>",
                        lambda e: canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))

        # ── Título ──
        ttk.Label(self.main, text="Gerador de AFD",
                  font=("Segoe UI", 15, "bold")).pack(pady=(16, 2))
        ttk.Label(self.main, text="Arquivo de Fonte de Dados — REP-C",
                  foreground=DARK["muted"], font=("Segoe UI", 9)).pack(pady=(0, 12))

        # ── Cabeçalho do empregador ──
        fh = ttk.LabelFrame(self.main, text="Dados do Empregador", padding=10)
        fh.pack(fill="x", padx=18, pady=(0, 8))

        self.header_vars: dict[str, tk.StringVar] = {}
        today = date.today()
        fields = [
            ("rep_number",  "REP Number",   "12345678901234567"),
            ("cnpj",        "CNPJ",          "12.345.678/0001-58"),
            ("razao_social","Razão Social",  "Empresa Demonstracao Ltda"),
            ("data_inicial","Data Inicial",  today.isoformat()),
            ("data_final",  "Data Final",    today.isoformat()),
        ]
        for key, label, default in fields:
            row = ttk.Frame(fh)
            row.pack(fill="x", pady=3)
            ttk.Label(row, text=label, width=18, anchor="w",
                      font=("Segoe UI", 9)).pack(side="left")
            var = tk.StringVar(value=default)
            self.header_vars[key] = var
            ttk.Entry(row, textvariable=var,
                      font=("Segoe UI", 10)).pack(side="left", fill="x", expand=True)
            if key in ("data_inicial", "data_final"):
                ttk.Label(row, text="AAAA-MM-DD", foreground=DARK["muted"],
                          font=("Segoe UI", 8)).pack(side="left", padx=(6, 0))

        # ── Colaboradores ──
        fc = ttk.LabelFrame(self.main, text="Colaboradores", padding=10)
        fc.pack(fill="x", padx=18, pady=(0, 8))
        self.colab_frame = ttk.Frame(fc)
        self.colab_frame.pack(fill="x")
        self.colaboradores: list[dict] = []  # [{"cpf_var": ..., "hora_vars": [...], "frame": ...}]
        self._add_colaborador()

        tk.Button(
            fc, text="+ Adicionar Colaborador", font=("Segoe UI", 9),
            bg=DARK["bg2"], fg=DARK["accent"], relief="flat",
            cursor="hand2", padx=10, pady=4,
            command=self._add_colaborador,
        ).pack(anchor="w", pady=(8, 0))

        # ── Preview / resultado ──
        fr = ttk.LabelFrame(self.main, text="Conteúdo do AFD", padding=8)
        fr.pack(fill="both", expand=True, padx=18, pady=(0, 4))
        self.result_txt = scrolledtext.ScrolledText(
            fr, font=("Courier New", 8), bg=DARK["input_bg"], fg=DARK["fg"],
            insertbackground=DARK["fg"], relief="flat", state="disabled", height=14,
        )
        self.result_txt.pack(fill="both", expand=True)

        self.lbl_status = ttk.Label(self.main, text="", foreground=DARK["success"],
                                    font=("Segoe UI", 9))
        self.lbl_status.pack(pady=(2, 0))

        # ── Botões ──
        btn_frame = ttk.Frame(self.main)
        btn_frame.pack(fill="x", padx=18, pady=(4, 16))

        tk.Button(
            btn_frame, text="Gerar AFD", font=("Segoe UI", 11, "bold"),
            bg=DARK["accent"], fg="#fff", activebackground="#4a83df",
            relief="flat", cursor="hand2", pady=9,
            command=self._do_gerar,
        ).pack(side="left", fill="x", expand=True, padx=(0, 4))

        self.btn_baixar = tk.Button(
            btn_frame, text="Baixar Arquivo (.TXT)", font=("Segoe UI", 10),
            bg=DARK["bg2"], fg=DARK["fg"], activebackground=DARK["border"],
            relief="flat", cursor="hand2", pady=9,
            state="disabled",
            command=self._do_baixar,
        )
        self.btn_baixar.pack(side="left", fill="x", expand=True)

        self._afd_content: str = ""

    # ── Helpers ──────────────────────────────────────────────────────────

    def _add_colaborador(self):
        idx = len(self.colaboradores)
        frame = ttk.LabelFrame(
            self.colab_frame,
            text=f"Colaborador {idx + 1}",
            padding=8,
        )
        frame.pack(fill="x", pady=(0, 6))

        # CPF
        cpf_row = ttk.Frame(frame)
        cpf_row.pack(fill="x", pady=(0, 4))
        ttk.Label(cpf_row, text="CPF:", width=10, anchor="w",
                  font=("Segoe UI", 9)).pack(side="left")
        cpf_var = tk.StringVar()
        ttk.Entry(cpf_row, textvariable=cpf_var,
                  font=("Segoe UI", 10), width=20).pack(side="left")

        # Horários
        hora_frame = ttk.Frame(frame)
        hora_frame.pack(fill="x")
        ttk.Label(hora_frame, text="Horários (HHMM):", foreground=DARK["muted"],
                  font=("Segoe UI", 8)).pack(anchor="w")
        hora_list_frame = ttk.Frame(hora_frame)
        hora_list_frame.pack(fill="x")
        hora_vars: list[tk.StringVar] = []

        colab_entry = {
            "cpf_var": cpf_var,
            "hora_vars": hora_vars,
            "hora_list_frame": hora_list_frame,
            "frame": frame,
        }
        self.colaboradores.append(colab_entry)

        # Adiciona o primeiro horário
        self._add_horario_row(colab_entry)

        # Botão + horário
        tk.Button(
            frame, text="+ Horário", font=("Segoe UI", 8),
            bg=DARK["bg2"], fg=DARK["accent"], relief="flat",
            cursor="hand2", padx=6, pady=2,
            command=lambda ce=colab_entry: self._add_horario_row(ce),
        ).pack(anchor="w", pady=(4, 0))

        # Botão remover colaborador (somente se não for o primeiro)
        if idx > 0:
            def _rm_colab(ce=colab_entry):
                ce["frame"].destroy()
                self.colaboradores.remove(ce)

            tk.Button(
                frame, text="Remover colaborador", font=("Segoe UI", 8),
                bg=DARK["bg2"], fg=DARK["danger"], relief="flat",
                cursor="hand2", padx=6, pady=2,
                command=_rm_colab,
            ).pack(anchor="e", pady=(4, 0))

    def _add_horario_row(self, colab_entry: dict):
        row = ttk.Frame(colab_entry["hora_list_frame"])
        row.pack(fill="x", pady=1)
        var = tk.StringVar()
        colab_entry["hora_vars"].append(var)
        ttk.Entry(row, textvariable=var, font=("Segoe UI", 10),
                  width=8).pack(side="left")
        ttk.Label(row, text="HHMM ou HH:MM", foreground=DARK["muted"],
                  font=("Segoe UI", 8)).pack(side="left", padx=6)

        if len(colab_entry["hora_vars"]) > 1:
            def _rm(v=var, r=row, ce=colab_entry):
                if v in ce["hora_vars"]:
                    ce["hora_vars"].remove(v)
                r.destroy()

            tk.Button(
                row, text="✕", bg=DARK["bg2"], fg=DARK["danger"],
                relief="flat", cursor="hand2", font=("Segoe UI", 8),
                command=_rm,
            ).pack(side="left")

    def _do_gerar(self):
        self.lbl_status.configure(text="")
        self.btn_baixar.configure(state="disabled")
        self._afd_content = ""

        rep_number  = self.header_vars["rep_number"].get().strip()
        cnpj        = self.header_vars["cnpj"].get().strip()
        razao_social = self.header_vars["razao_social"].get().strip()
        data_inicial = self.header_vars["data_inicial"].get().strip()
        data_final   = self.header_vars["data_final"].get().strip()

        if not all([rep_number, cnpj, razao_social, data_inicial, data_final]):
            messagebox.showwarning("Atenção", "Preencha todos os dados do empregador.")
            return

        colaboradores = [
            {
                "cpf":      ce["cpf_var"].get().strip(),
                "horarios": [v.get().strip() for v in ce["hora_vars"] if v.get().strip()],
            }
            for ce in self.colaboradores
        ]

        cpf_validos = [c for c in colaboradores if c["cpf"]]
        if not cpf_validos:
            messagebox.showwarning("Atenção", "Informe o CPF de ao menos um colaborador.")
            return

        try:
            conteudo = gerar_afd(
                rep_number=rep_number,
                cnpj=cnpj,
                razao_social=razao_social,
                data_inicial=data_inicial,
                data_final=data_final,
                colaboradores=cpf_validos,
            )
        except ValueError as e:
            messagebox.showerror("Erro", str(e))
            return

        self._afd_content = conteudo
        self.result_txt.configure(state="normal")
        self.result_txt.delete("1.0", "end")
        self.result_txt.insert("1.0", conteudo)
        self.result_txt.configure(state="disabled")

        linhas = [l for l in conteudo.splitlines() if l]
        self.lbl_status.configure(
            text=f"✓ AFD gerado — {len(linhas)} registros."
        )
        self.btn_baixar.configure(state="normal")

    def _do_baixar(self):
        if not self._afd_content:
            return
        rep_number = self.header_vars["rep_number"].get().strip()
        cnpj       = self.header_vars["cnpj"].get().strip()
        sugestao   = nome_arquivo(rep_number, cnpj)

        filepath = filedialog.asksaveasfilename(
            title="Salvar AFD",
            initialfile=sugestao,
            defaultextension=".TXT",
            filetypes=[("Arquivo de texto", "*.TXT"), ("Todos os arquivos", "*.*")],
        )
        if not filepath:
            return

        try:
            Path(filepath).write_text(
                self._afd_content, encoding="iso-8859-1", newline=""
            )
            self.lbl_status.configure(
                text=f"✓ Arquivo salvo: {Path(filepath).name}"
            )
        except OSError as e:
            messagebox.showerror("Erro ao salvar", str(e))


def build_ui():
    root = tk.Tk()
    GeradorAFDApp(root)
    root.mainloop()


def run_protocol():
    """Modo Headless via Protocolo Toolbox IPC v1.0."""
    try:
        from toolbox_protocol import ToolboxProtocolHandler
    except ImportError:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "shared" / "python"))
        from toolbox_protocol import ToolboxProtocolHandler

    handler = ToolboxProtocolHandler()
    req = handler.read_request()
    if not req:
        return

    payload = req.get("payload", {})
    rep_number = payload.get("rep_number", "00000000000000001")
    cnpj = payload.get("cnpj", "00000000000000")
    razao_social = payload.get("razao_social", "EMPRESA DE TESTE S/A")
    data_inicial = payload.get("data_inicial", "01/01/2025")
    data_final = payload.get("data_final", "31/01/2025")
    colaboradores = payload.get("colaboradores", [])

    try:
        afd_content = gerar_afd(rep_number, cnpj, razao_social, data_inicial, data_final, colaboradores)
        handler.send_success(
            result={
                "afd_content": afd_content,
                "output": afd_content
            },
            output_message="Arquivo AFD gerado com sucesso."
        )
    except Exception as e:
        handler.send_error("INVALID_INPUT", f"Falha na geração do AFD: {e}")


if __name__ == "__main__":
    if not sys.stdin.isatty():
        run_protocol()
    else:
        build_ui()

