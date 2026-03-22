-- Procedure: {{CATALOG}}.{{SCHEMA}}.analyze_table
-- Type: STORED PROCEDURE
-- Description: Procedure: ANALYZE TABLE ... COMPUTE STATISTICS then DESCRIBE EXTENDED;
--              p_catalog/p_schema/p_table are three UC name parts; mutates table statistics.
-- Note: This is a procedure (not a function) because ANALYZE TABLE is a DDL command.
-- Usage: CALL {{CATALOG}}.{{SCHEMA}}.analyze_table('catalog', 'schema', 'table')

CREATE OR REPLACE PROCEDURE {{CATALOG}}.{{SCHEMA}}.analyze_table(
  p_catalog STRING,
  p_schema  STRING,
  p_table   STRING
)
SQL SECURITY INVOKER
LANGUAGE SQL
COMMENT 'Stored procedure: runs ANALYZE TABLE ... COMPUTE STATISTICS FOR ALL COLUMNS then DESCRIBE EXTENDED for the same table. Parameters p_catalog, p_schema, and p_table are the three UC name parts. Mutates table statistics (DDL). Output shape depends on DESCRIBE EXTENDED; not a simple TABLE function.'
BEGIN
  DECLARE full_table_name STRING;
  SET full_table_name = CONCAT(p_catalog, '.', p_schema, '.', p_table);

  -- Compute statistics for all columns
  EXECUTE IMMEDIATE CONCAT('ANALYZE TABLE ', full_table_name, ' COMPUTE STATISTICS FOR ALL COLUMNS');

  -- Return the table description with stats
  EXECUTE IMMEDIATE CONCAT('DESCRIBE EXTENDED ', full_table_name);
END;
