/**
 * Format a table_ref JSONB value into a display label.
 *
 * @param {object} tableRef - { catalog, schema, table?, tables? }
 * @returns {string}
 */
export function formatTableRef(tableRef) {
  if (!tableRef) return 'Unknown'
  if (tableRef.table) {
    return `${tableRef.catalog}.${tableRef.schema}.${tableRef.table}`
  }
  if (tableRef.tables?.length) {
    return `${tableRef.catalog}.${tableRef.schema}.* (${tableRef.tables.length} tables)`
  }
  return `${tableRef.catalog}.${tableRef.schema}.*`
}

/**
 * Format a table_fqn or derive label from table_ref.
 *
 * @param {string|null} tableFqn - explicit FQN (per-table row) or null (combined)
 * @param {object} tableRef - fallback for combined rows
 * @returns {{ label: string, isCombined: boolean }}
 */
export function formatCompletedLabel(tableFqn, tableRef) {
  if (tableFqn) {
    return { label: tableFqn, isCombined: false }
  }
  return { label: formatTableRef(tableRef), isCombined: true }
}
