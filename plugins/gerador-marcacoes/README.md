# Gerador de Marcações (INSERT R070ACC)

Plugin do **toolbox** (https://github.com/rodrigolessadev/toolbox) que gera
`INSERT`s SQL para a tabela `R070ACC` do TOTVS / Protheus, a partir de
cabeçalho + horários + intervalo de datas. Suporta os dialetos **SQL Server**
e **Oracle**.

> **Porta fiel** do app/(main)/(routes)/insert/page.tsx do
> [KapiNote](https://github.com/rodrigolessadev/kapinote), portada para
> Python/Tk na v2.0.0.

## Instalação

Via marketplace do toolbox: o plugin aparece automaticamente ao
adicionar a entrada `gerador-marcacoes` no `catalog.json` do repositório
`toolbox-plugins`. Clique em **Instalar** no painel de marketplace.

Instalação manual: copie a pasta `gerador-marcacoes/` para
`<data_dir>/plugins/` e reinicie o toolbox.

## Uso

1. Abra o toolbox e clique em **Gerador de Marcações**.
2. Preencha os 5 campos principais (NUMCRA, USOMAR, NUMEMP, TIPCOL, NUMCAD).
3. Opcional: clique em **+ Adicionar** no bloco *Adicionar Campo Opcional*
   para incluir qualquer um dos 20 campos opcionais disponíveis.
4. Adicione um ou mais horários (formato `HH:MM`).
5. Defina o intervalo de datas e marque os dias da semana.
6. Escolha o dialeto (SQL Server ou Oracle).
7. Clique em **Gerar INSERTs** — o SQL aparece no painel inferior.
8. Use **Copiar SQL** ou **Salvar em .sql** para exportar.

## Mudanças na v2.0.0 (em relação à v1.x)

A v2.0.0 fecha os gaps de paridade com o `insert/page.tsx` do KapiNote:

| Patch | O que era | O que ficou |
|---|---|---|
| **1. Separação de campos** | `FIXED_LABELS` misturava 3 fixos + 4 principais | `MAIN_FIELDS` com 5 entradas; DATACC/HORACC são widgets próprios |
| **2. Lista de opcionais** | 20 campos do Select Radix do KapiNote estavam ausentes | `OPTIONAL_FIELDS` (20 entradas) + UI `ttk.Combobox` para adicionar |
| **3. CodeBox → ScrolledText** | Resultado era exibido num `Dialog` com `highlight.js` | `ScrolledText` com colorização leve (tags `kw` / `str`) — consistente com os outros 4 plugins |
| **4. Helpers de dialeto** | `fnDataAtual`, `traduzirTipo`, `fnIsnull` não existiam em Python | Portados do `insert-builder.ts` |
| **5. UI de opcionais** | Não havia como adicionar campo opcional | `ttk.Combobox` + botão **+ Adicionar** + botão **x** para remover |

Também: import de `_shared/theme.py` (paleta DARK padronizada entre plugins).

## Testes

```bash
cd toolbox-plugins/plugins/gerador-marcacoes
python -m pytest tests/
```

Cobre: dialetos SQL Server vs Oracle, múltiplos horários, múltiplas datas,
filtro por dia da semana, campos opcionais (presentes e ausentes), escape
de strings, helpers de dialeto, validações (horários vazios, datas vazias).

## Estrutura

```
gerador-marcacoes/
├── plugin.json            # manifesto do plugin (lido pelo executor.rs)
├── main.py                # UI Tk + logica portada do insert-builder.ts
├── tests/
│   └── test_insert_builder.py
├── README.md
└── (opcional) theme.py    # se o _shared ainda nao foi publicado,
                           # copie daqui para a raiz do plugin.
```

## Dependências

- Python 3.10+
- `tkinter` (já vem na stdlib)
- `pytest` (apenas para os testes)

Nenhuma dependência externa em runtime.

## Compatibilidade com o toolbox

- Requer toolbox ≥ 1.0.0 (caminho `python` nativo no `executor.rs`).
- Plugin é executado como subprocesso Python isolado (uma janela OS-level
  por plugin), com `cwd = pasta do plugin`.
- O tema `_shared/theme.py` é resolvido via `sys.path.insert(0, ../)`
  no `main.py`, então o plugin funciona mesmo se o `_shared` for
  publicado depois.
