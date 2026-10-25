"""
Pydantic schemas and data contracts for Academic Services execution.
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ServiceInput(BaseModel):
    service_code: str = Field(..., description="Service code, e.g. '001', '002'")
    user_id: str = Field(..., description="UUID of the requesting user")
    content: str = Field(..., description="Primary text input or prompt from student")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Optional parameters like level, subject, difficulty")
    attachments: List[str] = Field(default_factory=list, description="Optional list of file IDs or URLs")


class ServiceExecutionResult(BaseModel):
    service_code: str
    service_name: str
    success: bool
    status: str = "completed"  # completed, requires_clarification, rejected_integrity, scheduled
    summary: str
    rendered_output: str
    structured_data: Dict[str, Any] = Field(default_factory=dict)
    follow_up_actions: List[Dict[str, str]] = Field(default_factory=list)
    disclaimer: Optional[str] = None
