from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class ModerationCheckRequest(BaseModel):
    user_id: Annotated[int, Field(alias="userId", ge=1)]
    title: Annotated[str, Field(min_length=1, max_length=255)]
    content: Annotated[str, Field(min_length=1)]
    price: Annotated[int, Field(ge=0)]
    category: Annotated[str, Field(min_length=1, max_length=50)]

    model_config = ConfigDict(populate_by_name=True)


class ModerationCheckResponse(BaseModel):
    decision: str
    risk_score: int = Field(alias="riskScore")
    matched_rules: list[str] = Field(alias="matchedRules")
    reason: str

    model_config = ConfigDict(populate_by_name=True)


class ModerationLogResponse(BaseModel):
    id: int
    user_id: int = Field(alias="userId")
    title: str
    content_hash: str = Field(alias="contentHash")
    risk_score: int = Field(alias="riskScore")
    decision: str
    matched_rules: list[str] = Field(alias="matchedRules")
    reason: str
    created_at: datetime = Field(alias="createdAt")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

