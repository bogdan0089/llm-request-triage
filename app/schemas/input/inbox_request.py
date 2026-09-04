from datetime import datetime

from pydantic import BaseModel, Field


class InboxRequest(BaseModel):
    """One row from the input CSV (inbox)."""

    id: str = Field(min_length=1)
    channel: str = Field(min_length=1)
    timestamp: datetime
    raw_text: str = Field(min_length=1)
