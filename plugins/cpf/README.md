# Plugin CPF

Validador e gerador de CPF com interface Tkinter.

## Como funciona

O Toolbox detecta a pasta `plugins/cpf/` automaticamente ao iniciar. Quando
o usuário digita `cpf` e pressiona Enter, o Toolbox executa o comando
configurado em `plugin.json`:

```json
{
  "name": "cpf",
  "version": "1.0.0",
  "entry": "pythonw main.py"
}
```

Isso abre a janela do plugin de forma independente.

## Recursos

- Validação completa pelo algoritmo dos dígitos verificadores
- Geração de CPFs válidos aleatórios
- Formatação automática com máscara
- Cópia para área de transferência
- UI dark mode com Tkinter

## Requisitos

- Python 3.7+ (Tkinter é nativo)

## Personalização

Edite `main.py` para alterar o comportamento. Não é necessário recompilar o
Toolbox.
