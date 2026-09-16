# Changelog

Todas as mudanças relevantes no ecossistema de plugins do Toolbox serão registradas neste arquivo.

O formato é baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/),
e este projeto adere ao [Versionamento Semântico](https://semver.org/lang/pt-BR/).

## [Não publicado]

### ♻️ Refactor / Arquitetura
- **Centralização de Versão e Ícone na Barra de Tarefas (`shared/web_utils.py`):**
  - Padronizada a barra de títulos de todos os 15 plugins abertos via `create_plugin_window()` para o formato oficial: `"{Nome} v{X.Y.Z} — Toolbox"`, extraindo a versão automaticamente do `plugin.json` ou de `version`/`plugin_dir`.
  - Centralizada a rotina Win32 (`WM_SETICON`, `LoadImageW`, `EnumWindows`, `AppUserModelID`) no módulo `shared/web_utils.py`, vinculada automaticamente ao evento `shown` da janela.
  - Eliminadas mais de 300 linhas de código Win32 duplicado em 13 arquivos `domain.py` e em `safe/main.py`, substituindo por delegações concisas.
  - Adicionado asset oficial `.ico` para o plugin `tarefas` (`ui/assets/check-square.ico`) e alias `cloud-cog.ico` para `logon-aws` (#236).

## [1.1.1] - 2026-09-16

### ♻️ Refactor / Testing
- **Segmentação de Testes no Pytest:** Implementado arquivo central `pytest.ini` e `tests/conftest.py` com suporte aos marcadores `windows_only`, `optional_deps` e marcadores semânticos por plugin (`plugin("<id>")`).
- **Auto-skip de Plataforma:** Testes dependentes de APIs exclusivas do Windows (DPAPI, Windows Hello, Win32 Session Lock e Clipboard) agora são automaticamente pulados com status `SKIPPED` em ambientes Linux e macOS.
- **Resiliência para Dependências Opcionais:** Testes com dependência de `pynacl`, `pykeepass` e KDFs criptográficos específicos (`Argon2id`) agora executam importações defensivas via `pytest.importorskip`.
