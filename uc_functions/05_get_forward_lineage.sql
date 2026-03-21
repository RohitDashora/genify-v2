-- Function: {{CATALOG}}.{{SCHEMA}}.get_forward_lineage
-- Type: TABLE function
-- Description: Returns forward (downstream) lineage for a given table with job/pipeline details.
--              Shows all target tables that the specified table feeds data INTO.
-- Usage: SELECT * FROM {{CATALOG}}.{{SCHEMA}}.get_forward_lineage('catalog.schema.table')

CREATE OR REPLACE FUNCTION {{CATALOG}}.{{SCHEMA}}.get_forward_lineage(
  table_full_name STRING
)
RETURNS TABLE (
  source_table    STRING,
  source_type     STRING,
  target_table    STRING,
  target_type     STRING,
  entity_type     STRING,
  entity_id       STRING,
  job_id          STRING,
  job_name        STRING,
  pipeline_id     STRING,
  pipeline_name   STRING,
  notebook_id     STRING,
  dashboard_id    STRING,
  created_by      STRING,
  last_event_time TIMESTAMP
)
LANGUAGE SQL
COMMENT 'Returns forward (downstream) lineage for a given table with job/pipeline details. Shows all target tables that the specified table feeds data INTO. Usage: SELECT * FROM {{CATALOG}}.{{SCHEMA}}.get_forward_lineage("catalog.schema.table")'
RETURN
  SELECT
    l.source_table_full_name AS source_table,
    l.source_type,
    l.target_table_full_name AS target_table,
    l.target_type,
    l.entity_type,
    l.entity_id,
    l.entity_metadata.job_info.job_id AS job_id,
    j.name AS job_name,
    l.entity_metadata.dlt_pipeline_info.dlt_pipeline_id AS pipeline_id,
    p.name AS pipeline_name,
    l.entity_metadata.notebook_id AS notebook_id,
    COALESCE(l.entity_metadata.dashboard_id, l.entity_metadata.legacy_dashboard_id) AS dashboard_id,
    l.created_by,
    MAX(l.event_time) AS last_event_time
  FROM system.access.table_lineage l
  LEFT JOIN system.lakeflow.jobs j
    ON l.entity_metadata.job_info.job_id = j.job_id
    AND l.workspace_id = j.workspace_id
    AND j.delete_time IS NULL
  LEFT JOIN system.lakeflow.pipelines p
    ON l.entity_metadata.dlt_pipeline_info.dlt_pipeline_id = p.pipeline_id
    AND l.workspace_id = p.workspace_id
    AND p.delete_time IS NULL
  WHERE l.source_table_full_name = table_full_name
    AND l.target_table_full_name IS NOT NULL
  GROUP BY ALL
  ORDER BY last_event_time DESC;
