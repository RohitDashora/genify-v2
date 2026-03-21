-- Function: {{CATALOG}}.{{SCHEMA}}.list_jobs
-- Type: TABLE function (uses http_request to call Databricks Jobs API)
-- Description: Lists Databricks jobs in the workspace. Returns job ID, name, creator, and creation time.
--              Use name_filter to search by job name.
-- Prerequisites: Requires a UC connection named 'databricks_workspace_api' configured for the workspace.
-- Usage: SELECT * FROM {{CATALOG}}.{{SCHEMA}}.list_jobs()
--        SELECT * FROM {{CATALOG}}.{{SCHEMA}}.list_jobs(50, 'etl')

CREATE OR REPLACE FUNCTION {{CATALOG}}.{{SCHEMA}}.list_jobs(
  max_results INT    DEFAULT 25    COMMENT 'Maximum number of jobs to return (default 25)',
  name_filter STRING DEFAULT NULL  COMMENT 'Optional substring filter on job name'
)
RETURNS TABLE (
  job_id       BIGINT,
  job_name     STRING,
  creator      STRING,
  created_time STRING
)
LANGUAGE SQL
NOT DETERMINISTIC
COMMENT 'Lists Databricks jobs in the workspace. Returns job ID, name, creator, and creation time. Use name_filter to search by job name.'
RETURN
  SELECT
    CAST(jobs.value:job_id AS BIGINT) AS job_id,
    jobs.value:settings.name::STRING AS job_name,
    jobs.value:creator_user_name::STRING AS creator,
    CAST(TIMESTAMP_MILLIS(CAST(jobs.value:created_time AS BIGINT)) AS STRING) AS created_time
  FROM (
    SELECT PARSE_JSON(
      http_request(
        conn => 'databricks_workspace_api',
        method => 'GET',
        path => '/2.1/jobs/list',
        params => CASE
          WHEN name_filter IS NOT NULL
            THEN MAP('limit', CAST(max_results AS STRING), 'name', name_filter)
          ELSE MAP('limit', CAST(max_results AS STRING))
        END
      ).text
    ) AS response
  ),
  LATERAL VARIANT_EXPLODE(response:jobs) AS jobs;
