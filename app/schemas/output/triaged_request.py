from datetime import datetime

from pydantic import BaseModel

from app.schemas.input.inbox_request import InboxRequest
from app.schemas.output.triage_result import TriageResult


class TriagedRequest(BaseModel):
    """Final record for one request: input data + LLM result + processing metadata."""

    id: str
    channel: str
    timestamp: datetime
    raw_text: str

    triage: TriageResult | None = None

    possible_duplicate_of: str | None = None

    error: str | None = None
    attempts: int = 0

    @classmethod
    def from_request(
        cls,
        request: InboxRequest,
        triage: TriageResult | None = None,
        error: str | None = None,
        attempts: int = 0,
    ) -> "TriagedRequest":
        """Build a final record from the input request and LLM output."""
        return cls(
            id=request.id,
            channel=request.channel,
            timestamp=request.timestamp,
            raw_text=request.raw_text,
            triage=triage,
            error=error,
            attempts=attempts,
        )
