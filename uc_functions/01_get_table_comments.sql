-- Function: {{CATALOG}}.{{SCHEMA}}.get_table_comments
-- Type: TABLE function
-- Description: Returns all comments (table-level and column-level) for a given table
-- Usage: SELECT * FROM {{CATALOG}}.{{SCHEMA}}.get_table_comments('catalog', 'schema', 'table')

CREATE OR REPLACE FUNCTION {{CATALOG}}.{{SCHEMA}}.get_table_comments(
  p_catalog STRING,
  p_schema  STRING,
  p_table   STRING
)
RETURNS TABLE (
  column_name    STRING,
  column_comment STRING,
  table_comment  STRING
)
LANGUAGE SQL
COMMENT 'Returns all comments (table-level and column-level) for a given table'
RETURN
  SELECT
    c.column_name,
    c.comment AS column_comment,
    t.comment AS table_comment
  FROM system.information_schema.columns c
  JOIN system.information_schema.tables t
    ON c.table_catalog = t.table_catalog
    AND c.table_schema = t.table_schema
    AND c.table_name = t.table_name
  WHERE c.table_catalog = p_catalog
    AND c.table_schema = p_schema
    AND c.table_name = p_table
  ORDER BY c.ordinal_position;
