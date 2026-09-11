# @toolbox-plugins/shared-markdown

Componente unificado de visualização e edição de Markdown (`MarkdownField`) para o ecossistema Toolbox Plugins.

## 📦 Instalação / Importação

### Via ES Module
```javascript
import { MarkdownField, MarkdownReader, MarkdownEditor, parseMarkdown } from '@toolbox-plugins/shared-markdown';
import '@toolbox-plugins/shared-markdown/style.css';
```

### Via Browser / pywebview
```html
<link rel="stylesheet" href="../../shared/ui/toolbox-theme.css">
<link rel="stylesheet" href="../../shared/ui/markdown/markdown-field.css">
<script type="module" src="../../shared/ui/markdown/index.js"></script>
```

---

## 🚀 Uso Rápido

### Modo Programático
```javascript
const field = new MarkdownField({
  value: '# Minha Tarefa\n- [ ] Estudar arquitetura\n- [x] Concluir testes',
  mode: 'view',
  allowToggleEdit: true,
  onSave: (newContent) => {
    console.log('Conteúdo salvo:', newContent);
  },
  onCancel: () => {
    console.log('Edição cancelada');
  }
});

field.mount('#container');
```

### Via Custom Element
```html
<markdown-field 
  value="# Descrição da Tarefa" 
  mode="view" 
  allow-toggle-edit>
</markdown-field>
```

---

## 🛠️ API

### `MarkdownField`
- `value`: `string`
- `mode`: `'view' | 'edit'` (padrão: `'view'`)
- `allowToggleEdit`: `boolean` (exibe botão "Editar" no modo leitor)
- `readOnly`: `boolean` (desabilita qualquer capacidade de edição)
- `placeholder`: `string`
- `onSave`: `(newContent: string) => void`
- `onCancel`: `() => void`
- `onChange`: `(content: string) => void`
- Métodos: `mount()`, `getValue()`, `setValue()`, `getMode()`, `setMode()`, `save()`, `cancel()`, `destroy()`.
