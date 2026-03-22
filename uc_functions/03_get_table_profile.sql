-- Function: {{CATALOG}}.{{SCHEMA}}.get_table_profile
-- Type: TABLE function
-- Description: Category/key/value profile rows (TABLE_INFO, COLUMN_STATS, TYPE_DISTRIBUTION,
--              COLUMN_DETAIL); p_catalog/p_schema/p_table are three name parts; Genify passes session table.
-- Usage: SELECT * FROM {{CATALOG}}.{{SCHEMA}}.get_table_profile('catalog', 'schema', 'table')
-- Filter: SELECT * FROM ... WHERE profile_category = 'TABLE_INFO'

CREATE OR REPLACE FUNCTION {{CATALOG}}.{{SCHEMA}}.get_table_profile(
  p_catalog STRING,
  p_schema  STRING,
  p_table   STRING
)
RETURNS TABLE (
  profile_category STRING,
  profile_key      STRING,
  profile_value    STRING
)
LANGUAGE SQL
COMMENT 'Structured profile for one UC table as category/key/value rows (not one wide row). Parameters p_catalog, p_schema, and p_table are the three name parts (not one FQN). profile_category values include TABLE_INFO (owner, timestamps, format), COLUMN_STATS, TYPE_DISTRIBUTION, and COLUMN_DETAIL (human-readable per-column line). Filter or scan profile_category to focus on one aspect.'
RETURN
  WITH table_info AS (
    SELECT table_type, table_owner, comment, created, created_by,
           last_altered, last_altered_by, data_source_format
    FROM system.information_schema.tables
    WHERE table_catalog = p_catalog
      AND table_schema = p_schema
      AND table_name = p_table
  ),
  col_stats AS (
    SELECT
      CAST(COUNT(*) AS STRING) AS total_columns,
      CAST(SUM(CASE WHEN is_nullable = 'YES' THEN 1 ELSE 0 END) AS STRING) AS nullable_columns,
      CAST(SUM(CASE WHEN is_nullable = 'NO' THEN 1 ELSE 0 END) AS STRING) AS non_nullable_columns,
      CAST(SUM(CASE WHEN column_default IS NOT NULL THEN 1 ELSE 0 END) AS STRING) AS columns_with_defaults,
      CAST(SUM(CASE WHEN comment IS NOT NULL AND comment != '' THEN 1 ELSE 0 END) AS STRING) AS columns_with_comments
    FROM system.information_schema.columns
    WHERE table_catalog = p_catalog
      AND table_schema = p_schema
      AND table_name = p_table
  ),
  col_type_dist AS (
    SELECT full_data_type, CAST(COUNT(*) AS STRING) AS cnt
    FROM system.information_schema.columns
    WHERE table_catalog = p_catalog
      AND table_schema = p_schema
      AND table_name = p_table
    GROUP BY full_data_type
  ),
  col_details AS (
    SELECT
      column_name,
      CAST(ordinal_position AS STRING) AS ordinal_position,
      full_data_type,
      is_nullable,
      COALESCE(column_default, 'N/A') AS column_default,
      COALESCE(comment, 'No comment') AS col_comment
    FROM system.information_schema.columns
    WHERE table_catalog = p_catalog
      AND table_schema = p_schema
      AND table_name = p_table
  )
  SELECT * FROM (
    SELECT 'TABLE_INFO' AS profile_category, 'table_type' AS profile_key, table_type AS profile_value FROM table_info
    UNION ALL SELECT 'TABLE_INFO', 'owner', table_owner FROM table_info
    UNION ALL SELECT 'TABLE_INFO', 'comment', COALESCE(comment, 'No comment') FROM table_info
    UNION ALL SELECT 'TABLE_INFO', 'created', CAST(created AS STRING) FROM table_info
    UNION ALL SELECT 'TABLE_INFO', 'created_by', created_by FROM table_info
    UNION ALL SELECT 'TABLE_INFO', 'last_altered', CAST(last_altered AS STRING) FROM table_info
    UNION ALL SELECT 'TABLE_INFO', 'last_altered_by', last_altered_by FROM table_info
    UNION ALL SELECT 'TABLE_INFO', 'data_source_format', data_source_format FROM table_info
    UNION ALL SELECT 'COLUMN_STATS', 'total_columns', total_columns FROM col_stats
    UNION ALL SELECT 'COLUMN_STATS', 'nullable_columns', nullable_columns FROM col_stats
    UNION ALL SELECT 'COLUMN_STATS', 'non_nullable_columns', non_nullable_columns FROM col_stats
    UNION ALL SELECT 'COLUMN_STATS', 'columns_with_defaults', columns_with_defaults FROM col_stats
    UNION ALL SELECT 'COLUMN_STATS', 'columns_with_comments', columns_with_comments FROM col_stats
    UNION ALL SELECT 'TYPE_DISTRIBUTION', full_data_type, cnt FROM col_type_dist
    UNION ALL SELECT 'COLUMN_DETAIL', column_name,
      CONCAT('pos=', ordinal_position, ' | type=', full_data_type, ' | nullable=', is_nullable,
             ' | default=', column_default, ' | comment=', col_comment)
      FROM col_details
  )
  ORDER BY profile_category, profile_key;
