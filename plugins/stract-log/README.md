# Plugin Stract Log

Filtra arquivos de log por **nível**, **parâmetro adicional** e regra de
**recorrência**, salvando o resultado em um arquivo `.log` no mesmo diretório
do arquivo de origem.

## Como executar

O Toolbox descobre este plugin automaticamente. Digite `stract-log` na barra
de pesquisa e pressione **Enter**.

## Campos da interface

| Campo | Descrição |
|-------|-----------|
| Arquivo | Caminho do arquivo de log (botão para procurar no disco) |
| Level | Lista com os níveis mais comuns — `SEVERE`, `WARNING`, `INFO`, `FINE`, `ERROR` |
| Parâmetro adicional | Texto opcional que deve aparecer no bloco de log |
| Recorrências | Quando marcado, agrupa blocos com o mesmo conteúdo (ignorando data) e mantém apenas a ocorrência *Mais recente* ou *Mais antiga* |
| Ocorrência | `Mais recente` (padrão) ou `Mais antiga`. Habilitado somente quando *Recorrências* está marcado |

## Saída

O resultado é gravado em
`<diretório do arquivo>/<nome>-stract-<YYYYMMDD-HHMMSS>.log` com os blocos
filtrados na mesma ordem em que aparecem no arquivo original.

## Requisitos

- Python 3.7+ (Tkinter é nativo)
