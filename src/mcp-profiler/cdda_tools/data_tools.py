"""Table-profiling tools: profile_table, get_schema, sample_rows, profile_columns_light."""
from __future__ import annotations

import json
from typing import Any, Optional

from server.client_factory import SqlSession

from . import statement_execution as stmt
from . import sql_for_cdda as sqlgen


def _envelope(status: str, data: Any, warnings: list[str] | None = None, errors: list[str] | None = None) -> dict:
    return {
        "status": status,
        "warnings": warnings or [],
        "errors": errors or [],
        "data": data if data is not None else {},
    }


def _row_to_dict(columns: list[str], row: list[Any]) -> dict[str, Any]:
    return dict(zip(columns, row)) if columns and row else {}


def profile_table(session: SqlSession, table_fqn: str) -> dict[str, Any]:
    """High-level table stats via DESCRIBE DETAIL."""
    try:
        statement = sqlgen.sql_table_overview(table_fqn)
    except sqlgen.ValidationError as e:
        return _envelope("error", {}, errors=[str(e)])
    out = stmt.execute_sql(session, statement)
    if out["status"] != "ok":
        return out
    data = out.get("data", {})
    columns = data.get("columns", [])
    rows = data.get("rows", [])
    if not rows:
        return _envelope("ok", {"fqn": table_fqn})
    row_dict = _row_to_dict(columns, rows[0])
    size_bytes = row_dict.get("sizeInBytes") or row_dict.get("size_in_bytes")
    if size_bytes is not None and not isinstance(size_bytes, (int, float)):
        try:
            size_bytes = int(size_bytes)
        except (TypeError, ValueError):
            size_bytes = None
    partition_cols = row_dict.get("partitionColumns") or row_dict.get("partition_columns") or []
    if isinstance(partition_cols, str):
        try:
            partition_cols = json.loads(partition_cols) if partition_cols.startswith("[") else [partition_cols]
        except json.JSONDecodeError:
            partition_cols = [partition_cols]
    return _envelope("ok", {
        "fqn": table_fqn,
        "storage_location": row_dict.get("location") or row_dict.get("storage_location"),
        "num_files": row_dict.get("numFiles"),
        "size_bytes": size_bytes,
        "last_updated_ts": str(row_dict.get("lastModified") or row_dict.get("last_modified") or ""),
        "partition_cols": partition_cols,
    })


def get_schema(session: SqlSession, table_fqn: str) -> dict[str, Any]:
    """Table schema — columns with name, type, nullable."""
    try:
        statement = sqlgen.sql_table_schema(table_fqn)
    except sqlgen.ValidationError as e:
        return _envelope("error", {}, errors=[str(e)])
    out = stmt.execute_sql(session, statement)
    if out["status"] != "ok":
        return out
    data = out.get("data", {})
    columns = data.get("columns", [])
    rows = data.get("rows", [])
    col_names = [c.lower() if c else "" for c in columns]
    name_idx = next((i for i, n in enumerate(col_names) if n in ("col_name", "name", "column_name")), 0)
    type_idx = next((i for i, n in enumerate(col_names) if n in ("data_type", "type", "datatype")), 1 if name_idx == 0 else 0)
    nullable_idx = next((i for i, n in enumerate(col_names) if n in ("nullable", "null")), -1)
    cols = []
    for r in rows[:sqlgen.MAX_SCHEMA_COLS]:
        name = r[name_idx] if name_idx < len(r) else None
        dtype = r[type_idx] if type_idx < len(r) else None
        nullable = r[nullable_idx] if 0 <= nullable_idx < len(r) else True
        if isinstance(nullable, str):
            nullable = nullable.lower() in ("true", "yes", "1")
        cols.append({"name": name, "type": dtype, "nullable": bool(nullable)})
    warnings = []
    if len(rows) > sqlgen.MAX_SCHEMA_COLS:
        warnings.append(f"Column list truncated to first {sqlgen.MAX_SCHEMA_COLS} columns.")
    return _envelope("ok", {
        "fqn": table_fqn,
        "column_count": len(rows),
        "columns": cols,
    }, warnings=warnings)


def sample_rows(
    session: SqlSession,
    table_fqn: str,
    limit: int = 20,
) -> dict[str, Any]:
    """Random sample of rows."""
    try:
        statement = sqlgen.sql_sample_rows(table_fqn, limit=limit)
    except sqlgen.ValidationError as e:
        return _envelope("error", {}, errors=[str(e)])
    out = stmt.execute_sql(session, statement)
    if out["status"] != "ok":
        return out
    data = out.get("data", {})
    columns = data.get("columns", [])
    raw_rows = data.get("rows", [])
    rows = [_row_to_dict(columns, r) for r in raw_rows]
    n = max(1, min(limit, sqlgen.MAX_SAMPLE_LIMIT))
    return _envelope("ok", {
        "fqn": table_fqn,
        "limit_applied": n,
        "rows": rows,
    })


def profile_columns_light(
    session: SqlSession,
    table_fqn: str,
    top_k: int = 20,
) -> dict[str, Any]:
    """Light column profiling — null rate, distinct estimate, top values."""
    sqls = sqlgen.sql_profile_columns_light(table_fqn, top_k=top_k, sample_rows=50000, column_names=None)
    if len(sqls) != 1:
        return _envelope("error", {}, errors=["Expected single DESCRIBE SQL when column_names is None"])
    out = stmt.execute_sql(session, sqls[0])
    if out["status"] != "ok":
        return out
    data = out.get("data", {})
    cols_meta = data.get("columns", [])
    rows = data.get("rows", [])
    col_names = [c.lower() if c else "" for c in cols_meta]
    name_idx = next((i for i, n in enumerate(col_names) if n in ("col_name", "name", "column_name")), 0)
    type_idx = next((i for i, n in enumerate(col_names) if n in ("data_type", "type", "datatype")), 1 if name_idx == 0 else 0)
    raw_names = [r[name_idx] for r in rows if name_idx < len(r) and r[name_idx]][:sqlgen.MAX_PROFILE_COLS]
    raw_types = [str(r[type_idx]) if type_idx < len(r) else None for r in rows if name_idx < len(r) and r[name_idx]][:sqlgen.MAX_PROFILE_COLS]
    while len(raw_types) < len(raw_names):
        raw_types.append(None)
    pairs = [(str(n).strip(), t) for n, t in zip(raw_names, raw_types)
             if n and isinstance(n, str) and sqlgen.COLUMN_NAME_RE.match(str(n).strip())]
    column_names = [p[0] for p in pairs]
    column_types = [p[1] for p in pairs]
    if not column_names:
        return _envelope("ok", {"fqn": table_fqn, "columns": [], "sample_rows_used": 0, "top_k_used": top_k})
    try:
        sqls = sqlgen.sql_profile_columns_light(table_fqn, top_k=top_k, sample_rows=50000, column_names=column_names)
    except sqlgen.ValidationError as e:
        return _envelope("error", {}, errors=[str(e)])
    base_out = stmt.execute_sql(session, sqls[0])
    if base_out["status"] != "ok":
        return base_out
    bdata = base_out.get("data", {})
    bcols = bdata.get("columns", [])
    brows = bdata.get("rows", [])
    if not brows:
        return _envelope("ok", {"fqn": table_fqn, "columns": [], "sample_rows_used": 0, "top_k_used": top_k})
    bdict = _row_to_dict(bcols, brows[0])
    n = 0
    try:
        n = int(bdict.get("n") or 0)
    except (TypeError, ValueError):
        pass
    out_cols = []
    for i, c in enumerate(column_names):
        nn = bdict.get(f"nn_{i}")
        d = bdict.get(f"d_{i}")
        null_rate = None
        if n and nn is not None:
            try:
                null_rate = 1.0 - (int(nn) / n)
            except (TypeError, ValueError):
                pass
        distinct_est = float(d) if d is not None else None
        col_type = column_types[i] if i < len(column_types) else None
        out_cols.append({
            "name": c,
            "type": col_type,
            "null_rate": null_rate,
            "distinct_estimate": distinct_est,
            "top_values": [],
        })
    for idx, top_sql in enumerate(sqls[1:]):
        if idx >= len(column_names):
            break
        tout = stmt.execute_sql(session, top_sql)
        if tout["status"] != "ok":
            continue
        tdata = tout.get("data", {})
        tcols = tdata.get("columns", [])
        trows = tdata.get("rows", [])
        val_idx = next((i for i, n in enumerate(tcols) if n and n.lower() in ("val", "value", column_names[idx])), 0)
        cnt_idx = next((i for i, n in enumerate(tcols) if n and n.lower() in ("cnt", "count")), 1)
        top_values = [
            {"value": r[val_idx] if val_idx < len(r) else None,
             "count": int(r[cnt_idx]) if cnt_idx < len(r) and r[cnt_idx] is not None else 0}
            for r in trows
        ]
        if idx < len(out_cols):
            out_cols[idx]["top_values"] = top_values
    return _envelope("ok", {
        "fqn": table_fqn,
        "sample_rows_used": n,
        "top_k_used": top_k,
        "columns": out_cols,
    })
