# Deterministic SQL generation for CDDA table overview, schema, sample, and column profiling.

from __future__ import annotations

import re
from typing import Optional

TABLE_FQN_RE = re.compile(r"^[A-Za-z0-9_]+\.[A-Za-z0-9_]+\.[A-Za-z0-9_]+$")
MAX_SAMPLE_LIMIT = 50
MAX_SCHEMA_COLS = 500
MAX_PROFILE_COLS = 200
MAX_TOP_K = 20
MIN_SAMPLE_ROWS = 1000
MAX_SAMPLE_ROWS_PROFILE = 50000
WHERE_CLAUSE_RE = re.compile(r"^[A-Za-z0-9_\s\.=><!\(\)\'\"%\-,/]*$")
COLUMN_NAME_RE = re.compile(r"^[A-Za-z0-9_]+$")


class ValidationError(Exception):
    pass


def _validate_table_fqn(table_fqn: Optional[str]) -> str:
    if table_fqn is None or not table_fqn.strip():
        raise ValidationError("table_fqn is required")
    t = table_fqn.strip()
    if not TABLE_FQN_RE.match(t):
        raise ValidationError("Invalid table_fqn format. Expected catalog.schema.table")
    return t


def sql_table_overview(table_fqn: Optional[str]) -> str:
    t = _validate_table_fqn(table_fqn)
    return f"DESCRIBE DETAIL {t}"


def sql_table_schema(table_fqn: Optional[str]) -> str:
    t = _validate_table_fqn(table_fqn)
    return f"DESCRIBE TABLE {t}"


def sql_sample_rows(
    table_fqn: Optional[str],
    limit: int = 20,
    seed: int = 42,
    where_clause: Optional[str] = None,
    select_cols_csv: Optional[str] = None,
) -> str:
    t = _validate_table_fqn(table_fqn)
    n = max(1, min(int(limit), MAX_SAMPLE_LIMIT))
    s = int(seed)
    if select_cols_csv:
        parts = [p.strip() for p in select_cols_csv.split(",") if p.strip()][:50]
        if not all(COLUMN_NAME_RE.match(c) for c in parts):
            raise ValidationError("select_cols_csv must contain only valid column names (alphanumeric, underscore)")
        cols = ", ".join(parts)
        select_part = f"SELECT {cols}"
    else:
        select_part = "SELECT *"
    sql = f"{select_part} FROM {t}"
    if where_clause and where_clause.strip():
        w = where_clause.strip()
        if ";" in w or "--" in w or "/*" in w or not WHERE_CLAUSE_RE.match(w):
            raise ValidationError("Rejected where_clause (failed safety validation)")
        sql += f" WHERE {w}"
    sql += f" ORDER BY RAND({s}) LIMIT {n}"
    return sql


def sql_profile_columns_light(
    table_fqn: Optional[str],
    top_k: int = 20,
    sample_rows: int = 50000,
    column_names: Optional[list[str]] = None,
) -> list[str]:
    t = _validate_table_fqn(table_fqn)
    k = max(1, min(int(top_k), MAX_TOP_K))
    sr = max(MIN_SAMPLE_ROWS, min(int(sample_rows), MAX_SAMPLE_ROWS_PROFILE))
    if not column_names:
        return [sql_table_schema(t)]
    cols = [c.strip() for c in column_names if c and c.strip()]
    if not all(COLUMN_NAME_RE.match(c) for c in cols):
        raise ValidationError("column_names must contain only valid column names (alphanumeric, underscore)")
    cols = cols[:MAX_PROFILE_COLS]
    top_cols = cols[:MAX_TOP_K]
    select_parts = ["COUNT(*) AS n"]
    for i, c in enumerate(cols):
        select_parts.append(f"COUNT({c}) AS nn_{i}")
        select_parts.append(f"APPROX_COUNT_DISTINCT({c}) AS d_{i}")
    base_sql = (
        f"WITH s AS (SELECT {', '.join(cols)} FROM {t} TABLESAMPLE ({sr} ROWS)) "
        f"SELECT {', '.join(select_parts)} FROM s"
    )
    out = [base_sql]
    for c in top_cols:
        top_sql = (
            f"SELECT {c} AS val, COUNT(*) AS cnt FROM (SELECT {c} FROM {t} TABLESAMPLE ({sr} ROWS)) t "
            f"GROUP BY {c} ORDER BY cnt DESC LIMIT {k}"
        )
        out.append(top_sql)
    return out
