from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class RuleCreateRequest(BaseModel):
    rule_name: Annotated[str, Field(alias="ruleName", min_length=1, max_length=100)]
    keyword: Annotated[str, Field(min_length=1, max_length=255)]
    score: Annotated[int, Field(ge=0, le=100)]
    action: Annotated[str, Field(pattern="^(ALLOW|REVIEW|BLOCK)$")]
    category: Annotated[str, Field(min_length=1, max_length=50)]
    enabled: bool = True

    model_config = ConfigDict(populate_by_name=True)


class RuleStatusUpdateRequest(BaseModel):
    enabled: bool


class RuleResponse(BaseModel):
    id: int
    rule_name: str = Field(alias="ruleName")
    keyword: str
    score: int
    action: str
    category: str
    enabled: bool
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

