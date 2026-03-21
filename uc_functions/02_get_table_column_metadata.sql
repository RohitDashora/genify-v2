-- Function: {{CATALOG}}.{{SCHEMA}}.get_table_column_metadata
-- Type: TABLE function
-- Description: Returns full column metadata and comments for a given table
-- Usage: SELECT * FROM {{CATALOG}}.{{SCHEMA}}.get_table_column_metadata('catalog', 'schema', 'table')

CREATE OR REPLACE FUNCTION {{CATALOG}}.{{SCHEMA}}.get_table_column_metadata(
  p_catalog STRING,
  p_schema  STRING,
  p_table   STRING
)
RETURNS TABLE (
  column_name              STRING,
  ordinal_position         INT,
  data_type                STRING,
  is_nullable              STRING,
  column_default           STRING,
  column_comment           STRING,
  character_maximum_length INT,
  numeric_precision        INT,
  numeric_scale            INT
)
LANGUAGE SQL
COMMENT 'Returns full column metadata and comments for a given table'
RETURN
  SELECT
    c.column_name,
    CAST(c.ordinal_position AS INT) AS ordinal_position,
    c.full_data_type AS data_type,
    c.is_nullable,
    c.column_default,
    c.comment AS column_comment,
    CAST(c.character_maximum_length AS INT) AS character_maximum_length,
    CAST(c.numeric_precision AS INT) AS numeric_precision,
    CAST(c.numeric_scale AS INT) AS numeric_scale
  FROM system.information_schema.columns c
  WHERE c.table_catalog = p_catalog
    AND c.table_schema = p_schema
    AND c.table_name = p_table
  ORDER BY c.ordinal_position;
