/**
 * @toolbox-plugins/shared-markdown - Distribuição Compartilhada para Plugins
 */
import './markdown-field.js';

const md = (typeof window !== 'undefined' && window.ToolboxMarkdown) || {};

export const MarkdownField = md.MarkdownField;
export const MarkdownReader = md.MarkdownReader;
export const MarkdownEditor = md.MarkdownEditor;
export const parseMarkdown = md.parseMarkdown;
export const sanitizeHtml = md.sanitizeHtml;
export const escapeHtml = md.escapeHtml;
export const slugify = md.slugify;
export const highlightSyntax = md.highlightSyntax;

export default md;
