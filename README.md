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
│   │   ├── ui/             # Frontend autossuficiente (HTML/CSS/JS)
│   │   └── tests/          # Testes unitários e isolamento
└── .github/
```
