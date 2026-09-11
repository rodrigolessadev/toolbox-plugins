export type MarkdownFieldMode = 'view' | 'edit';

export interface MarkdownFieldOptions {
  value?: string;
  mode?: MarkdownFieldMode;
  allowToggleEdit?: boolean;
  readOnly?: boolean;
  placeholder?: string;
  onSave?: (newContent: string) => void;
  onCancel?: () => void;
  onChange?: (content: string) => void;
}

export declare class MarkdownField {
  element: HTMLElement;
  constructor(options?: MarkdownFieldOptions);
  mount(target: HTMLElement | string): void;
  getValue(): string;
  setValue(val: string): void;
  getMode(): MarkdownFieldMode;
  setMode(mode: MarkdownFieldMode): void;
  save(): void;
  cancel(): void;
  destroy(): void;
}

export interface MarkdownReaderOptions {
  value?: string;
  allowToggleEdit?: boolean;
  readOnly?: boolean;
  placeholder?: string;
  onEditRequested?: () => void;
}

export declare class MarkdownReader {
  element: HTMLElement;
  constructor(options?: MarkdownReaderOptions);
  setValue(val: string): void;
  getValue(): string;
  destroy(): void;
}

export interface MarkdownEditorOptions {
  value?: string;
  placeholder?: string;
  onSave?: (newContent: string) => void;
  onCancel?: () => void;
  onChange?: (content: string) => void;
}

export declare class MarkdownEditor {
  element: HTMLElement;
  constructor(options?: MarkdownEditorOptions);
  save(): void;
  cancel(): void;
  focus(): void;
  setValue(val: string): void;
  getValue(): string;
  destroy(): void;
}

export interface TocItem {
  level: number;
  title: string;
  id: string;
}

export interface ParseResult {
  html: string;
  toc: TocItem[];
}

export declare function parseMarkdown(md: string): ParseResult;
export declare function sanitizeHtml(html: string): string;
export declare function escapeHtml(str: string): string;
export declare function slugify(text: string): string;
