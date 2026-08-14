# Analysis Orchestrator Plugin

Plugin orquestrador determinístico do ecossistema Toolbox para investigações técnicas e análise de incidentes.

## 🎯 Objetivo
Automatizar a execução integrada e sequencial dos 8 plugins de análise (`log-sanitizer`, `incident-filter`, `log-optimizer`, `log-cluster`, `log-timeline`, `har-optimizer`, `source-extractor` e `evidence-package`), gerando uma árvore estruturada de resultados, manifestos de integridade e resumos executivos.

## 🚀 Ações Suportadas
1. **`run_analysis`**: Executa o pipeline completo (com suporte a `dry_run: true` para simulação).
2. **`discover`**: Descobre e cataloga arquivos do diretório de análise e planeja as etapas sem executar.
3. **`run_plugin`**: Executa uma única etapa/plugin isoladamente sobre o diretório de análise.
4. **`validate_results`**: Valida a conformidade de uma pasta de resultados gerada anteriormente.
5. **`resume`**: Retoma a execução a partir de um manifesto de resultados anterior, executando etapas pendentes.

## 📁 Estrutura do Diretório de Resultados
```
analysis-directory/
├── logs/
├── har/
├── source/
├── metadata/
└── analysis-results-YYYYMMDD-HHMMSS/
    ├── manifest.json
    ├── execution-summary.json
    ├── sanitized/
    ├── filtered/
    ├── optimized/
    ├── clusters/
    ├── timelines/
    ├── source-extracts/
    ├── evidence/
    ├── reports/
    └── logs/
```

## 🔒 Segurança e Regras Determinísticas
- **Não utiliza IA**, LLMs ou modelos probabilísticos.
- Leitura não-destrutiva dos arquivos originais (nunca sobrescreve ou apaga a entrada).
- Proteção contra path traversal e criação estrita dentro do escopo de análise.
- Mascaramento e higienização estritos de secrets e credenciais.
