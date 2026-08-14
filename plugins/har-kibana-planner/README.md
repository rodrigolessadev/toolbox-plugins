# HAR Kibana Planner Plugin

## Objetivo do Plugin
O **HAR Kibana Planner** analisa arquivos HTTP Archive (HAR 1.2) gerados pelo DevTools dos navegadores, extrai sinais determinísticos de correlação (Trace IDs, Request IDs, Correlation IDs, Business IDs, falhas e rotas) e gera um **Plano Estruturado de Consultas** (Elasticsearch Query DSL e Kibana Query Language - KQL) para localizar logs relevantes no Kibana/Elasticsearch.

O plugin não executa chamadas de rede contra o cluster, atuando como um gerador de estratégias declarativas para posterior consumo por analistas ou MCPs (Model Context Protocol).

---

## Diferença entre Horário do HAR e Horário dos Logs (Clock Skew)
- O navegador registra o `startedDateTime` com base no relógio da máquina do usuário.
- Servidores de aplicação e bancos de dados utilizam NTP sincronizado com seus próprios fusos e latências de rede.
- O plugin aplica automaticamente uma tolerância de **Clock Skew** (`clock_skew_ms`, padrão: 5000ms) somada a janelas de contexto pré e pós requisição (`context_before_ms` e `context_after_ms`, padrão: 10000ms) para evitar perda de logs que ocorreram milissegundos antes ou depois da percepção do browser.

---

## Configuração de Mapeamento de Campos (`field_mapping`)
```json
{
  "field_mapping": {
    "timestamp": ["@timestamp", "timestamp", "event.created"],
    "service": ["service.name", "service", "app"],
    "request_id": ["request.id", "request_id", "requestId"],
    "trace_id": ["trace.id", "trace_id", "traceId"],
    "span_id": ["span.id", "span_id", "spanId"],
    "correlation_id": ["correlation.id", "correlation_id", "correlationId"],
    "http_method": ["http.request.method", "method"],
    "http_status": ["http.response.status_code", "status_code", "status"],
    "url_path": ["url.path", "http.request.path", "path"]
  }
}
```

---

## Regras de Mascaramento e Segurança
- `Authorization`, `Proxy-Authorization`, `Cookie`, `Set-Cookie`, `x-api-key`, `apikey` e `JWTs` são totalmente sanitizados (`[REDACTED]`).
- O arquivo HAR original **nunca é modificado**.
- Nenhum script embutido ou payload é executado.

---

## Estratégias de Consulta por Prioridade
1. **`trace_id`**: Correlação exata ponta a ponta distribuída (APM/OpenTelemetry).
2. **`request_id`**: Correlação exata de requisição no gateway/proxy reverso.
3. **`correlation_id`**: Identificador de fluxo assíncrono ou mensageria.
4. **`order_id` / `transaction_id`**: Identificador de transação de negócio.
5. **Serviço + Endpoint + Intervalo**: Fallback estruturado para rastreamento de falhas.
6. **Método + Host + Path + Intervalo**: Fallback de rota web.
7. **Intervalo Temporal da Sessão**: Janela global de observabilidade.

---

## Como Conectar a um MCP de Kibana
O payload gerado em `query_plan[].query_dsl` e `query_plan[].kql` segue as especificações oficiais do Elasticsearch e pode ser repassado diretamente para ferramentas como:
- `@modelcontextprotocol/server-elasticsearch`
- Scripts de busca via Python `elasticsearch-py`
- Barra de pesquisa Discover do Kibana via KQL.
