# 🔌 Toolbox Plugins

Repositório oficial de plugins para o [Toolbox](https://github.com/rodrigolessadev/toolbox).

## 📦 Catálogo Oficial de Plugins

| Plugin | ID | Ícone Lucide | Descrição |
| :--- | :--- | :--- | :--- |
| **Analysis Orchestrator** | `analysis-orchestrator` | `workflow` | Orquestrador e analisador de divergências contratuais |
| **Calculadora de Jornadas** | `calc-jornadas` | `clock-3` | Calculadora de jornadas de trabalho e intervalos |
| **Converter Data** | `converter-data` | `calendar-sync` | Conversor de data para serial Excel e formatos ISO |
| **Gerador de AFD** | `gerador-afd` | `file-clock` | Gerador de Arquivo Fonte de Dados (AFD) |
| **Gerador de JSON** | `gerador-json` | `file-json` | Gerador de mock data JSON parametrizável |
| **Gerador de Marcações SQL** | `gerador-marcacoes` | `database` | Gerador de INSERTs SQL (R070ACC) |
| **HAR Kibana Planner** | `har-kibana-planner` | `search-code` | Analisador de tráfego HAR e logs Kibana |
| **Novo Ticket** | `novo-ticket` | `ticket` | Criação e abertura de tickets com filtro temporal de logs |
| **Stract JSON** | `stract-json` | `scan-search` | Extrator e formatador de campos JSON |
| **Stract Log** | `stract-log` | `file-search` | Filtro de blocos de log por nível/parâmetro/recorrência |
| **Validador de CPF** | `cpf` | `badge-check` | Validador e gerador de CPF com máscara e formatação |

---

## 🛒 Instalando via Marketplace

Abra o Toolbox, clique em 🛒 **Marketplace** e instale qualquer plugin com um clique.

## 🗂️ Catálogo

O arquivo `catalog.json` é a fonte de verdade do Marketplace, lido diretamente pelo Toolbox via:

```text
https://raw.githubusercontent.com/rodrigolessadev/toolbox-plugins/main/catalog.json
```

## 📁 Estrutura de Arquitetura `pywebview`

```text
toolbox-plugins/
├── catalog.json            # Catálogo oficial de todos os plugins
├── plugins/
│   ├── <plugin_id>/
│   │   ├── plugin.json     # Manifesto com metadados e ícone Lucide
│   │   ├── domain.py       # Regras de negócio puras em Python
│   │   ├── main.py         # Entry point pywebview e classe Api bridge
│   │   └── ui/             # Frontend autossuficiente (HTML/CSS/JS)
├── tests/                  # Suíte de testes unitários e de integração
├── pytest.ini              # Configuração global de marcadores e filtros
└── .github/
```

---

## 🧪 Execução de Testes & Convenções

A suíte de testes utiliza [`pytest.ini`](pytest.ini) e [`tests/conftest.py`](tests/conftest.py) com marcadores formais para isolamento e auto-skip de plataforma:

- **`windows_only`**: Testes que exigem Windows nativo, DPAPI (`crypt32.dll`), Windows Hello ou named pipes (pulados automaticamente com `SKIPPED` em ambientes Linux/macOS).
- **`optional_deps`**: Testes que dependem de bibliotecas opcionais (`pynacl`, `pykeepass`, `cryptography>=42.0.0`).
- **`plugin(name)`**: Marcador semântico associando cada arquivo ao respectivo plugin.

### Comandos de Validação Rápida:

```bash
# 1. Validação focada no plugin em modificação + integridade global (< 1s):
pytest tests/test_plugin_<id>.py tests/test_all_plugins_integrity.py -v

# 2. Execução filtrada por marcador de plugin:
pytest -m tarefas -v
pytest -m safe -v
pytest -m calc_jornadas -v

# 3. Execução agnóstica a plataforma (recomendada para Linux/CI):
pytest -m "not windows_only" -v

# 4. Execução global completa (com auto-skip limpo de testes de plataforma):
pytest -v
```
