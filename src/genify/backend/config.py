"""Configuration loader for Genify V2.

Reads from app.yaml at the project root and allows env var overrides.
"""
import os
import logging
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

_APP_YAML_PATH = Path(__file__).parent.parent / "app.yaml"


@dataclass(frozen=True)
class LLMConfig:
    endpoint_name: str = "databricks-gpt-5-2"
    max_tokens: int = 4000
    temperature: float = 0.7
    summarizer_endpoint_name: str = "databricks-gemini-2-5-flash"
    summarizer_max_tokens: int = 12000
    summarizer_temperature: float = 0.3
    max_prompt_tokens: int = 20000


@dataclass(frozen=True)
class LakebaseConfig:
    enabled: bool = True
    schema_name: str = "genify"
    pool_size: int = 5


@dataclass(frozen=True)
class ContextTruncationConfig:
    """Character caps for MCP/context text embedded in LLM prompts (see app.yaml context_truncation)."""

    planning_chars_per_key: int = 2000
    executor_section_chars_per_key: int = 2000
    prior_yaml_tail_chars: int = 3000
    interactive_known_data_chars: int = 2000


@dataclass(frozen=True)
class MCPServerConfig:
    name: str = ""
    type: str = ""
    app_name: str = ""
    uc_catalog: str = ""
    uc_schema: str = ""
    url: str = ""


@dataclass(frozen=True)
class YamlMergeConfig:
    """Section YAML merge: single top-level key, nested strip vs template, LLM retries (not MCP)."""

    merge_max_retries: int = 2
    nested_validation: str = "strip"  # off | strip
    canonical_json_enabled: bool = False
    format_on_persist_enabled: bool = False
    format_dump_width: int = 120
    format_multiline_literals: bool = False


@dataclass(frozen=True)
class MCPToolOverridesConfig:
    """Optional planner/gather overrides for MCP tools (see app.yaml mcp_tool_overrides)."""

    tool_hints: tuple[tuple[str, str], ...] = ()
    hidden_tools: frozenset[str] = frozenset()
    extra_tools: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True)
class AppConfig:
    llm: LLMConfig = field(default_factory=LLMConfig)
    lakebase: LakebaseConfig = field(default_factory=LakebaseConfig)
    context_truncation: ContextTruncationConfig = field(default_factory=ContextTruncationConfig)
    yaml_merge: YamlMergeConfig = field(default_factory=YamlMergeConfig)
    mcp_servers: tuple[MCPServerConfig, ...] = ()
    mcp_tool_overrides: MCPToolOverridesConfig = field(default_factory=MCPToolOverridesConfig)


def _load_yaml() -> dict:
    """Load app.yaml from disk."""
    if not _APP_YAML_PATH.exists():
        logger.warning(f"app.yaml not found at {_APP_YAML_PATH}, using defaults")
        return {}
    with open(_APP_YAML_PATH) as f:
        return yaml.safe_load(f) or {}


def _build_config(raw: dict) -> AppConfig:
    """Build AppConfig from raw YAML dict with env var overrides."""
    cfg = raw.get("config", {})

    llm_raw = cfg.get("llm", {})
    llm = LLMConfig(
        endpoint_name=os.getenv("LLM_ENDPOINT_NAME", llm_raw.get("endpoint_name", "databricks-gpt-5-2")),
        max_tokens=int(llm_raw.get("max_tokens", 4000)),
        temperature=float(llm_raw.get("temperature", 0.7)),
        summarizer_endpoint_name=os.getenv(
            "SUMMARIZER_ENDPOINT_NAME",
            llm_raw.get("summarizer_endpoint_name", "databricks-gemini-2-5-flash"),
        ),
        summarizer_max_tokens=int(llm_raw.get("summarizer_max_tokens", 12000)),
        summarizer_temperature=float(llm_raw.get("summarizer_temperature", 0.3)),
        max_prompt_tokens=int(llm_raw.get("max_prompt_tokens", 20000)),
    )

    lb_raw = cfg.get("lakebase", {})
    lakebase = LakebaseConfig(
        enabled=lb_raw.get("enabled", True),
        schema_name=lb_raw.get("schema", "genify"),
        pool_size=int(lb_raw.get("pool_size", 5)),
    )

    ct_raw = cfg.get("context_truncation") or {}
    context_truncation = ContextTruncationConfig(
        planning_chars_per_key=int(ct_raw.get("planning_chars_per_key", 2000)),
        executor_section_chars_per_key=int(ct_raw.get("executor_section_chars_per_key", 2000)),
        prior_yaml_tail_chars=int(ct_raw.get("prior_yaml_tail_chars", 3000)),
        interactive_known_data_chars=int(ct_raw.get("interactive_known_data_chars", 2000)),
    )

    ym_raw = cfg.get("yaml_merge") or {}
    yaml_merge = YamlMergeConfig(
        merge_max_retries=int(ym_raw.get("merge_max_retries", 2)),
        nested_validation=str(ym_raw.get("nested_validation", "strip")).lower(),
        canonical_json_enabled=bool(ym_raw.get("canonical_json_enabled", False)),
        format_on_persist_enabled=bool(ym_raw.get("format_on_persist_enabled", False)),
        format_dump_width=int(ym_raw.get("format_dump_width", 120)),
        format_multiline_literals=bool(ym_raw.get("format_multiline_literals", False)),
    )

    mcp_servers = tuple(
        MCPServerConfig(
            name=s.get("name", ""),
            type=s.get("type", ""),
            app_name=s.get("app_name", ""),
            uc_catalog=s.get("uc_catalog", ""),
            uc_schema=s.get("uc_schema", ""),
            url=s.get("url", ""),
        )
        for s in cfg.get("mcp_servers", [])
    )

    mto_raw = cfg.get("mcp_tool_overrides") or {}
    hints_raw = mto_raw.get("tool_hints") or {}
    if not isinstance(hints_raw, dict):
        hints_raw = {}
    tool_hints = tuple(sorted((str(k), str(v)) for k, v in hints_raw.items()))

    ht_raw = mto_raw.get("hidden_tools") or []
    hidden_tools = frozenset(str(x) for x in ht_raw) if isinstance(ht_raw, list) else frozenset()

    et_raw = mto_raw.get("extra_tools") or []
    extra_tools_list: list[dict[str, Any]] = []
    if isinstance(et_raw, list):
        for item in et_raw:
            if isinstance(item, dict) and item.get("name"):
                extra_tools_list.append(dict(item))
            else:
                logger.warning("mcp_tool_overrides.extra_tools: skipped invalid entry (need dict with name)")

    for hint_name, _ in tool_hints:
        if hint_name in hidden_tools:
            logger.warning(
                "mcp_tool_overrides: tool_hints entry %r is also in hidden_tools; hidden wins",
                hint_name,
            )

    for et in extra_tools_list:
        ename = str(et.get("name", ""))
        if ename in hidden_tools:
            logger.warning(
                "mcp_tool_overrides: extra_tools entry %r is also in hidden_tools; hidden wins (entry dropped at manifest build)",
                ename,
            )

    mcp_tool_overrides = MCPToolOverridesConfig(
        tool_hints=tool_hints,
        hidden_tools=hidden_tools,
        extra_tools=tuple(extra_tools_list),
    )

    return AppConfig(
        llm=llm,
        lakebase=lakebase,
        context_truncation=context_truncation,
        yaml_merge=yaml_merge,
        mcp_servers=mcp_servers,
        mcp_tool_overrides=mcp_tool_overrides,
    )


@lru_cache(maxsize=1)
def get_config() -> AppConfig:
    """Return the singleton AppConfig, loaded from app.yaml + env vars."""
    raw = _load_yaml()
    config = _build_config(raw)
    logger.info(f"Config loaded: LLM={config.llm.endpoint_name}, "
                f"Lakebase={config.lakebase.enabled}, "
                f"MCP servers={len(config.mcp_servers)}")
    return config
