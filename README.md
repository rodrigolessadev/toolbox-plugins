# 🔌 Toolbox Plugins

Repositório oficial de plugins para o [Toolbox](https://github.com/rodrigolessadev/toolbox).

## 📦 Plugins disponíveis

| Plugin | Descrição | Versão |
|--------|-----------|--------|
| cpf | Validador e gerador de CPF | 1.0.0 |
| gerador-json | Gerador de mock data JSON | 1.0.0 |
| gerador-marcacoes | Gerador de INSERTs SQL (R070ACC) | 1.0.0 |
| calc-jornadas | Calculadora de jornadas de trabalho | 1.0.1 |
| stract-json | Extrator de campos de JSON | 1.0.0 |
| converter-data | Conversor de data para serial Excel | 1.0.0 |
| stract-log | Filtro de blocos de log por nível/parâmetro/recorrência | 1.0.0 |

## 🛒 Instalando via Marketplace

Abra o Toolbox, clique em 🛒 Marketplace e instale com um clique.

## 🗂️ Catálogo

O arquivo `catalog.json` é a fonte de verdade do Marketplace.
Ele é lido diretamente pelo Toolbox via:

```
https://raw.githubusercontent.com/rodrigolessadev/toolbox-plugins/main/catalog.json
```

## 📁 Estrutura

```
toolbox-plugins/
├── catalog.json            # catálogo de todos os plugins
├── plugins/
│   ├── cpf/                # código-fonte do plugin
│   ├── gerador-json/
│   ├── stract-log/
│   └── ...
└── .github/
    └── workflows/
        └── release.yml     # publica ZIPs automaticamente via tag
```

## 🚀 Publicando uma nova versão de um plugin

1. Edite o código do plugin em `plugins/<id>/`
2. Atualize `version` no `plugin.json` do plugin
3. Atualize `version` e `download_url` no `catalog.json`
4. Crie uma tag no formato `<id>-<versão>`:
   ```bash
   git tag stract-log-1.0.0
   git push origin stract-log-1.0.0
   ```

O GitHub Actions cria automaticamente o ZIP e publica na Release.

## 🧩 Estrutura de um plugin

Cada plugin é um ZIP com:

```
meu-plugin.zip
├── plugin.json     # metadados obrigatórios
├── main.py         # entrypoint (ou .js, .exe, etc.)
└── ...
```

`plugin.json` mínimo:

```json
{
  "name": "Meu Plugin",
  "version": "1.0.0",
  "description": "O que faz",
  "language": "python",
  "entry": "main.py"
}
```

## 📝 Licença

MIT
