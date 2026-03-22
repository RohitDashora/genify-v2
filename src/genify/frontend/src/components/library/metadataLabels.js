/** Display names for completed_metadata.template_type (UI-only). */
export const TYPE_LABELS = {
  table_comment: 'Table comment',
  genie: 'Genie',
}

export function templateLabel(templateType) {
  if (!templateType) return ''
  return TYPE_LABELS[templateType] || templateType
}

/** Shared list filter chip styles (Library + Templates). */
export const FILTER_CHIP_BASE =
  'px-2.5 py-0.5 rounded-full text-xs font-medium border transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2'

export const FILTER_CHIP_SELECTED = 'border-brand-500 bg-brand-50 text-brand-800'

export const FILTER_CHIP_IDLE =
  'border-border-subtle bg-surface text-gray-600 hover:border-gray-300'
