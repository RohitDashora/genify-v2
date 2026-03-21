-- Procedure: {{CATALOG}}.{{SCHEMA}}.analyze_table
-- Type: STORED PROCEDURE
-- Description: Runs ANALYZE TABLE COMPUTE STATISTICS FOR ALL COLUMNS and returns
--              the computed statistics via DESCRIBE EXTENDED.
-- Note: This is a procedure (not a function) because ANALYZE TABLE is a DDL command.
-- Usage: CALL {{CATALOG}}.{{SCHEMA}}.analyze_table('catalog', 'schema', 'table')

CREATE OR REPLACE PROCEDURE {{CATALOG}}.{{SCHEMA}}.analyze_table(
  p_catalog STRING,
  p_schema  STRING,
  p_table   STRING
)
SQL SECURITY INVOKER
LANGUAGE SQL
COMMENT 'Runs ANALYZE TABLE COMPUTE STATISTICS FOR ALL COLUMNS and returns the computed statistics'
BEGIN
  DECLARE full_table_name STRING;
  SET full_table_name = CONCAT(p_catalog, '.', p_schema, '.', p_table);

  -- Compute statistics for all columns
  EXECUTE IMMEDIATE CONCAT('ANALYZE TABLE ', full_table_name, ' COMPUTE STATISTICS FOR ALL COLUMNS');

  -- Return the table description with stats
  EXECUTE IMMEDIATE CONCAT('DESCRIBE EXTENDED ', full_table_name);
END;
