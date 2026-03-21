#!/usr/bin/env python3
"""Update Genify app resource bindings via Databricks SDK HTTP client.

PATCHes /api/2.0/apps/{name}. Uses plain JSON so older CLIs/SDKs that reject some
fields in ``databricks apps update --json`` are avoided.

Lakebase on the app (resource name ``postgres`` in app.yaml):

- **Provisioned** — ``database``: ``instance_name``, ``database_name``, ``permission``.
- **Autoscaling** — ``postgres``: ``branch``, ``database`` (full resource paths).

Environment (set by deploy.sh / common.sh):
  PROFILE, GENIFY_APP, WAREHOUSE_ID, LLM_ENDPOINT, SUMMARIZER_ENDPOINT

  One of:
    LAKEBASE_INSTANCE_NAME + LAKEBASE_DATABASE_NAME  (Provisioned)
    POSTGRES_BRANCH + POSTGRES_DATABASE            (Autoscaling)
"""
from __future__ import annotations

import os
import sys

from databricks.sdk import WorkspaceClient


def _require(name: str) -> str:
    v = (os.environ.get(name) or "").strip()
    if not v:
        print(f"ERROR: environment variable {name} is required.", file=sys.stderr)
        sys.exit(1)
    return v


def _lakebase_postgres_resource() -> dict:
    """Return the 4th resource block for the ``postgres`` key (name fixed in app.yaml)."""
    inst = (os.environ.get("LAKEBASE_INSTANCE_NAME") or "").strip()
    dbn = (os.environ.get("LAKEBASE_DATABASE_NAME") or "").strip()
    branch = (os.environ.get("POSTGRES_BRANCH") or "").strip()
    path_db = (os.environ.get("POSTGRES_DATABASE") or "").strip()

    if inst and dbn:
        return {
            "name": "postgres",
            "database": {
                "instance_name": inst,
                "database_name": dbn,
                "permission": "CAN_CONNECT_AND_CREATE",
            },
        }
    if branch and path_db:
        return {
            "name": "postgres",
            "postgres": {
                "branch": branch,
                "database": path_db,
                "permission": "CAN_CONNECT_AND_CREATE",
            },
        }
    print(
        "ERROR: Set lakebase_instance_name + lakebase_database_name (Provisioned), "
        "or postgres_branch + postgres_database (Autoscaling).",
        file=sys.stderr,
    )
    sys.exit(1)


def main() -> None:
    profile = _require("PROFILE")
    app_name = _require("GENIFY_APP")
    wh = (os.environ.get("WAREHOUSE_ID") or "").strip()
    llm = _require("LLM_ENDPOINT")
    summ = _require("SUMMARIZER_ENDPOINT")

    if not wh:
        print("ERROR: WAREHOUSE_ID must be non-empty (set warehouse_id in deploy.config.yaml).", file=sys.stderr)
        sys.exit(1)

    body = {
        "description": "AI-powered metadata generator for Unity Catalog & Genie Spaces",
        "resources": [
            {"name": "sql-warehouse", "sql_warehouse": {"id": wh, "permission": "CAN_USE"}},
            {
                "name": "interview-endpoint",
                "serving_endpoint": {"name": llm, "permission": "CAN_QUERY"},
            },
            {
                "name": "summarizer-endpoint",
                "serving_endpoint": {"name": summ, "permission": "CAN_QUERY"},
            },
            _lakebase_postgres_resource(),
        ],
    }

    client = WorkspaceClient(profile=profile)
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    client.api_client.do("PATCH", f"/api/2.0/apps/{app_name}", body=body, headers=headers)
    print("    App resources updated (SDK PATCH).")


if __name__ == "__main__":
    main()
