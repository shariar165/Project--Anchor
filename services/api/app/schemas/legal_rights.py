from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
import uuid


class LegalRightStep(BaseModel):
    en: str
    bn: str | None = None


class LegalRightCreate(BaseModel):
    category: str = Field(max_length=40)
    title_en: str = Field(min_length=2, max_length=200)
    title_bn: str | None = Field(default=None, max_length=200)
    summary_en: str
    summary_bn: str | None = None
    full_text_en: str
    full_text_bn: str | None = None
    penalty_en: str | None = None
    penalty_bn: str | None = None
    where_to_invoke_en: str | None = None
    where_to_invoke_bn: str | None = None
    citation: str = Field(max_length=200)
    steps: list[LegalRightStep] = Field(default_factory=list)
    illustration: str = Field(default="scale", max_length=40)
    accent: str = Field(default="#C44536", max_length=9)
    sort_order: int = 0
    published: bool = True


class LegalRightResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    category: str
    title_en: str
    title_bn: str | None
    summary_en: str
    summary_bn: str | None
    full_text_en: str
    full_text_bn: str | None
    penalty_en: str | None
    penalty_bn: str | None
    where_to_invoke_en: str | None
    where_to_invoke_bn: str | None
    citation: str
    steps: list
    illustration: str
    accent: str
    sort_order: int
    published: bool
    created_at: datetime
