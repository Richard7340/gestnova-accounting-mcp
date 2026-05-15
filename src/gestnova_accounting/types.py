"""Shared pydantic types for the accounting engine."""
from datetime import date
from decimal import Decimal
from typing import Literal, Optional
from pydantic import BaseModel, Field


Country = Literal["ES", "MX"]


class Money(BaseModel):
    """Amount with currency. All computations use Decimal internally."""
    amount: Decimal
    currency: str = "EUR"

    class Config:
        json_encoders = {Decimal: lambda v: float(v)}


class RuleRef(BaseModel):
    """Reference to a legal rule that was applied to a calculation."""
    rule: str
    country: Country
    effective_from: date
    effective_until: Optional[date] = None
    source: str


class ToolResult(BaseModel):
    """Common base for tool outputs. All tools include rulesApplied."""
    rules_applied: list[RuleRef] = Field(default_factory=list, alias="rulesApplied")
    calculation_id: Optional[str] = None
    warnings: list[str] = Field(default_factory=list)

    class Config:
        populate_by_name = True
