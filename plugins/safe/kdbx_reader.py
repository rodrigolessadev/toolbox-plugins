"""
Módulo de Leitura Direta, Inspeção e Sincronização de Bases KeePass (.kdbx) - Issue #217.
Permite ler arquivos KDBX v3 e v4 diretamente via pykeepass (sem GUI), com fallback
opcional para o utilitário de linha de comando oficial keepassxc-cli.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

try:
    from .logger import get_logger
except ImportError:
    try:
        from logger import get_logger
    except ImportError:
        import logging
        def get_logger(name="safe"):
            return logging.getLogger(name)

logger = get_logger("safe.kdbx")


class KdbxReaderError(Exception):
    """Exceção base para falhas de leitura ou validação de KDBX."""
    pass


class KdbxAuthenticationError(KdbxReaderError):
    """Exceção levantada quando a senha ou arquivo chave é inválido."""
    pass


class KdbxNotFoundError(KdbxReaderError):
    """Exceção levantada quando o arquivo KDBX ou keyfile não existe."""
    pass


def find_keepassxc_cli_binary() -> Optional[str]:
    """Tenta localizar o binário keepassxc-cli no PATH ou em locais padrão do Windows."""
    # 1. Checa PATH
    cli_in_path = shutil.which("keepassxc-cli")
    if cli_in_path:
        return cli_in_path

    # 2. Checa caminhos padrão no Windows
    if sys.platform == "win32":
        standard_paths = [
            r"C:\Program Files\KeePassXC\keepassxc-cli.exe",
            r"C:\Program Files (x86)\KeePassXC\keepassxc-cli.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\KeePassXC\keepassxc-cli.exe"),
        ]
        for p in standard_paths:
            if os.path.isfile(p):
                return p

    return None


class KdbxReader:
    """
    Controlador para leitura direta, testes e importação de entradas de arquivos .kdbx.
    Prioriza pykeepass e realiza fallback para keepassxc-cli quando aplicável.
    """

    @staticmethod
    def test_kdbx_credentials(
        kdbx_path: Union[str, Path],
        password: Optional[str] = None,
        keyfile_path: Optional[Union[str, Path]] = None,
    ) -> Tuple[bool, str]:
        """
        Testa se o arquivo .kdbx pode ser aberto com a combinação fornecida de senha e keyfile.
        Retorna (sucesso, mensagem).
        """
        path_obj = Path(kdbx_path)
        if not path_obj.exists() or not path_obj.is_file():
            return False, f"Arquivo .kdbx não encontrado: {kdbx_path}"

        if keyfile_path:
            kf_obj = Path(keyfile_path)
            if not kf_obj.exists() or not kf_obj.is_file():
                return False, f"Arquivo de chave (keyfile) não encontrado: {keyfile_path}"

        # 1. Tenta via pykeepass
        try:
            import pykeepass
            try:
                kp = pykeepass.PyKeePass(
                    str(path_obj),
                    password=password if password else None,
                    keyfile=str(keyfile_path) if keyfile_path else None,
                )
                entry_count = len(kp.entries)
                return True, f"Base KeePass validada com sucesso! ({entry_count} entradas encontradas)"
            except (pykeepass.exceptions.CredentialsError, pykeepass.exceptions.HeaderChecksumError):
                return False, "Senha mestra ou arquivo de chave incorreto."
            except Exception as e:
                logger.warning(f"Falha ao validar KDBX com pykeepass ({e}). Tentando fallback CLI...")
        except ImportError:
            logger.info("pykeepass não instalado. Utilizando keepassxc-cli para validação.")

        # 2. Fallback para keepassxc-cli
        cli_bin = find_keepassxc_cli_binary()
        if not cli_bin:
            return False, "Não foi possível validar o arquivo KDBX (pykeepass indisponível e keepassxc-cli não encontrado)."

        cmd = [cli_bin, "ls", "-q", "-f", str(path_obj)]
        if keyfile_path:
            cmd.extend(["-k", str(keyfile_path)])
        if not password:
            cmd.append("--no-password")

        try:
            stdin_input = f"{password}\n" if password else None
            res = subprocess.run(
                cmd,
                input=stdin_input,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if res.returncode == 0:
                return True, "Base KeePass validada com sucesso via keepassxc-cli."
            else:
                return False, "Falha na autenticação do KDBX (senha incorreta ou chave inválida)."
        except Exception as e:
            return False, f"Erro ao executar keepassxc-cli: {e}"

    @staticmethod
    def read_entries(
        kdbx_path: Union[str, Path],
        password: Optional[str] = None,
        keyfile_path: Optional[Union[str, Path]] = None,
        search_query: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Lê todas as entradas do arquivo .kdbx recursivamente, normalizando-as para o schema do Cofre.
        """
        path_obj = Path(kdbx_path)
        if not path_obj.exists() or not path_obj.is_file():
            raise KdbxNotFoundError(f"Arquivo KDBX não encontrado: {kdbx_path}")

        if keyfile_path:
            kf_obj = Path(keyfile_path)
            if not kf_obj.exists() or not kf_obj.is_file():
                raise KdbxNotFoundError(f"Keyfile não encontrado: {keyfile_path}")

        # Método 1: pykeepass nativo
        try:
            import pykeepass
            try:
                kp = pykeepass.PyKeePass(
                    str(path_obj),
                    password=password if password else None,
                    keyfile=str(keyfile_path) if keyfile_path else None,
                )
                return KdbxReader._extract_entries_from_pykeepass(kp, search_query=search_query)
            except (pykeepass.exceptions.CredentialsError, pykeepass.exceptions.HeaderChecksumError) as e:
                raise KdbxAuthenticationError("Senha mestra ou arquivo de chave incorreto.") from e
            except Exception as e:
                logger.warning(f"Erro inesperado no pykeepass: {e}. Tentando fallback keepassxc-cli...")
        except ImportError:
            pass

        # Método 2: keepassxc-cli export -q -f xml
        cli_bin = find_keepassxc_cli_binary()
        if not cli_bin:
            raise KdbxReaderError("pykeepass e keepassxc-cli indisponíveis para extração.")

        return KdbxReader._extract_entries_from_cli(
            cli_bin, path_obj, password=password, keyfile_path=keyfile_path, search_query=search_query
        )

    @staticmethod
    def _extract_entries_from_pykeepass(kp: Any, search_query: Optional[str] = None) -> List[Dict[str, Any]]:
        """Extrai dados dos objetos Entry do pykeepass."""
        results: List[Dict[str, Any]] = []
        clean_q = (search_query or "").strip().lower()

        for entry in kp.entries:
            title = entry.title or "Entrada KeePass"
            username = entry.username or ""
            password = entry.password or ""
            url = entry.url or ""
            notes = entry.notes or ""
            tags = list(entry.tags) if entry.tags else []
            group_name = entry.group.name if entry.group else ""

            # Filtro de busca se informado
            if clean_q:
                haystack = f"{title} {username} {url} {notes} {' '.join(tags)} {group_name}".lower()
                if clean_q not in haystack:
                    continue

            # Extrai custom properties / string fields
            custom_props: Dict[str, Any] = {}
            if hasattr(entry, "custom_properties") and entry.custom_properties:
                for k, v in entry.custom_properties.items():
                    custom_props[k] = v

            # TOTP / OTP se configurado
            totp_val = None
            if hasattr(entry, "otp") and entry.otp:
                try:
                    totp_val = entry.otp
                except Exception:
                    pass

            entry_uuid = str(entry.uuid) if getattr(entry, "uuid", None) else ""

            # Normalização para o schema do Cofre Seguro
            metadata: Dict[str, Any] = {
                "source": "kdbx_direct",
                "kdbx_uuid": entry_uuid,
                "group": group_name,
                "url": url,
                "notes": notes,
                "custom_fields": custom_props,
                "has_totp": bool(totp_val or entry.custom_properties.get("otp")),
            }
            if totp_val:
                metadata["totp_current"] = totp_val

            final_tags = ["kdbx"]
            if group_name and group_name.lower() not in ("root", "geral"):
                final_tags.append(group_name)
            for t in tags:
                if t not in final_tags:
                    final_tags.append(t)

            results.append({
                "id": f"kdbx_{entry_uuid or title}",
                "title": title,
                "username_or_key": username,
                "password": password,
                "payload": password,
                "category": "password",
                "url": url,
                "notes": notes,
                "tags": final_tags,
                "metadata": metadata,
            })

        return results

    @staticmethod
    def _extract_entries_from_cli(
        cli_bin: str,
        kdbx_path: Path,
        password: Optional[str] = None,
        keyfile_path: Optional[Union[str, Path]] = None,
        search_query: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Extrai entradas usando keepassxc-cli exportando em formato XML."""
        cmd = [cli_bin, "export", "-q", "-f", "xml", str(kdbx_path)]
        if keyfile_path:
            cmd.extend(["-k", str(keyfile_path)])
        if not password:
            cmd.append("--no-password")

        stdin_input = f"{password}\n" if password else None
        try:
            res = subprocess.run(
                cmd,
                input=stdin_input,
                capture_output=True,
                text=True,
                timeout=15,
            )
            if res.returncode != 0:
                raise KdbxAuthenticationError("Falha ao exportar XML via keepassxc-cli (verifique senha ou keyfile).")

            from importers import parse_safe_xml
            raw_entries = parse_safe_xml(res.stdout)

            clean_q = (search_query or "").strip().lower()
            results: List[Dict[str, Any]] = []

            for r in raw_entries:
                title = r.get("title", "")
                username = r.get("username_or_key", "")
                meta = r.get("metadata") or {}
                url = meta.get("url", "")
                notes = meta.get("notes", "")
                tags = r.get("tags") or ["kdbx"]

                if clean_q:
                    haystack = f"{title} {username} {url} {notes} {' '.join(tags)}".lower()
                    if clean_q not in haystack:
                        continue

                results.append({
                    "id": f"kdbx_cli_{title}",
                    "title": title,
                    "username_or_key": username,
                    "password": r.get("payload", ""),
                    "payload": r.get("payload", ""),
                    "category": r.get("category", "password"),
                    "url": url,
                    "notes": notes,
                    "tags": tags,
                    "metadata": meta,
                })

            return results
        except subprocess.TimeoutExpired:
            raise KdbxReaderError("Tempo limite excedido ao chamar keepassxc-cli.")
        except Exception as e:
            if isinstance(e, (KdbxAuthenticationError, KdbxReaderError)):
                raise
            raise KdbxReaderError(f"Erro no fallback CLI: {e}") from e

    @staticmethod
    def sync_remote_sftp(
        ssh_host: str,
        remote_path: str,
        ssh_user: Optional[str] = None,
        ssh_port: int = 22,
        local_cache_path: Optional[Union[str, Path]] = None,
    ) -> Path:
        """
        Baixa de forma segura o arquivo .kdbx de um servidor remoto via SCP/SFTP do OpenSSH nativo do Windows.
        Retorna o caminho do arquivo local sincronizado.
        """
        if not local_cache_path:
            cache_dir = Path(tempfile.gettempdir()) / "toolbox_safe_kdbx_cache"
            cache_dir.mkdir(parents=True, exist_ok=True)
            local_target = cache_dir / Path(remote_path).name
        else:
            local_target = Path(local_cache_path)
            local_target.parent.mkdir(parents=True, exist_ok=True)

        user_host = f"{ssh_user}@{ssh_host}" if ssh_user else ssh_host
        remote_target = f"{user_host}:{remote_path}"

        scp_bin = shutil.which("scp") or r"C:\Windows\System32\OpenSSH\scp.exe"
        if not os.path.isfile(scp_bin):
            raise KdbxReaderError(f"Utilitário SCP não encontrado no sistema: {scp_bin}")

        cmd = [scp_bin, "-P", str(ssh_port), "-o", "BatchMode=yes", remote_target, str(local_target)]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if res.returncode != 0:
                raise KdbxReaderError(f"Erro ao sincronizar via SCP: {res.stderr.strip() or 'Falha na conexão SSH.'}")
            return local_target
        except subprocess.TimeoutExpired:
            raise KdbxReaderError("Tempo limite excedido ao transferir arquivo KDBX remoto.")
        except Exception as e:
            if isinstance(e, KdbxReaderError):
                raise
            raise KdbxReaderError(f"Falha na sincronização remota: {e}") from e
