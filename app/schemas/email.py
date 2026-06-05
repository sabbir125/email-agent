from pydantic import BaseModel, Field
from datetime import datetime
from typing import Literal


class RawEmail(BaseModel):
    """Schema for raw email data from the mock JSON source."""

    id: str
    from_address: str = Field(alias="from")
    subject: str
    body: str
    received_at: datetime

    model_config = {"populate_by_name": True}


class ClassificationResult(BaseModel):
    """Schema for OpenAI classification response."""

    important: bool
    priority: Literal["HIGH", "MEDIUM", "LOW"]
    category: Literal[
        "PAYMENT_ISSUE",
        "SERVER_DOWN",
        "CUSTOMER_COMPLAINT",
        "ACCOUNT_ACCESS",
        "GENERAL_SUPPORT",
        "NEWSLETTER",
        "SPAM",
    ]
    confidence: int = Field(ge=0, le=100)
    reason: str


class EmailResponse(BaseModel):
    """Schema for email API response."""

    email_id: str
    sender: str
    subject: str
    body: str
    important: bool
    priority: str
    category: str
    confidence: int
    reason: str
    received_at: datetime
    processed_at: datetime

    model_config = {"from_attributes": True}


class StatsResponse(BaseModel):
    """Schema for /stats endpoint response."""

    total: int
    important: int
    ignored: int
