"""Pydantic request/response models for Genify V2 API."""
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

class TemplateCreate(BaseModel):
    type: str = Field(..., description="Template type: table_comment or genie")
    name: str = Field(..., description="Human-readable template name")
    yaml_content: str = Field(..., description="Full YAML template content")
    notes: Optional[str] = None
    activate: bool = Field(False, description="Activate this template on creation")


class TemplateUpdate(BaseModel):
    yaml_content: Optional[str] = None
    name: Optional[str] = None
    notes: Optional[str] = None


class TemplateResponse(BaseModel):
    id: UUID
    type: str
    version: int
    name: str
    yaml_content: str
    is_active: bool
    created_by: str
    created_at: datetime
    updated_at: datetime
    notes: Optional[str] = None


class TemplateListItem(BaseModel):
    id: UUID
    type: str
    version: int
    name: str
    is_active: bool
    created_by: str
    created_at: datetime
    updated_at: datetime
    notes: Optional[str] = None


class CloneRequest(BaseModel):
    notes: Optional[str] = None


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------

class TableRef(BaseModel):
    """Single table or multi-table reference."""
    catalog: str
    schema_name: str = Field(..., alias="schema")
    table: Optional[str] = None
    tables: Optional[list[dict[str, str]]] = None

    model_config = {"populate_by_name": True}


class SessionCreate(BaseModel):
    template_type: str = Field(..., description="table_comment or genie")
    mode: str = Field("interactive", description="hands_off or interactive")
    table_ref: TableRef
    output_format: str = Field("yaml", description="yaml or markdown")


class SessionResponse(BaseModel):
    id: UUID
    user_email: str
    template_type: str
    template_version: int
    mode: str
    status: str
    table_ref: Any
    plan: Optional[Any] = None
    current_step: int
    generated_yaml: str
    conversation: list[Any]
    output_format: str
    error_message: Optional[str] = None
    pending_question: Optional[dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None


class SessionListItem(BaseModel):
    id: UUID
    template_type: str
    mode: str
    status: str
    table_ref: Any
    current_step: int
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None


class AnswerRequest(BaseModel):
    answer: str = Field(..., description="User's answer to the agent's question")


# ---------------------------------------------------------------------------
# Completed Metadata
# ---------------------------------------------------------------------------

class CompletedResponse(BaseModel):
    id: UUID
    session_id: Optional[UUID] = None
    user_email: str
    template_type: str
    table_ref: Any
    yaml_content: str
    markdown_content: Optional[str] = None
    table_fqn: Optional[str] = None
    version: int
    created_at: datetime
    updated_at: datetime


class CompletedListItem(BaseModel):
    id: UUID
    template_type: str
    table_ref: Any
    table_fqn: Optional[str] = None
    version: int
    created_at: datetime
    updated_at: datetime


class CompletedUpdate(BaseModel):
    yaml_content: str = Field(..., description="Updated YAML content")


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    status: str
    lakebase: bool
    llm: bool
    mcp_servers: dict[str, bool] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Catalog (for UI picker)
# ---------------------------------------------------------------------------

class CatalogListResponse(BaseModel):
    catalogs: list[str]


class SchemaListResponse(BaseModel):
    schemas: list[str]


class TableListItem(BaseModel):
    name: str
    type: Optional[str] = None
    comment: Optional[str] = None


class TableListResponse(BaseModel):
    tables: list[TableListItem]
