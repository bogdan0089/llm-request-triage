import logging

from app.core.exceptions import LLMResponseError
from app.schemas.input.inbox_request import InboxRequest
from app.schemas.output.triaged_request import TriagedRequest
from app.services.llm_client import GeminiTriageClient

logger = logging.getLogger(__name__)


class TriageService:
    """Orchestrator: runs every inbox request through the LLM and collects results."""

    def __init__(self, client: GeminiTriageClient | None = None) -> None:
        self._client = client or GeminiTriageClient()

    def run(self, requests: list[InboxRequest]) -> list[TriagedRequest]:
        total = len(requests)
        records: list[TriagedRequest] = []

        for index, request in enumerate(requests, start=1):
            logger.info("[%s/%s] %s", index, total, request.id)
            records.append(self._process(request))

        failed = sum(1 for record in records if record.triage is None)
        logger.info("Processed %s requests, failed: %s", total, failed)
        return records

    def _process(self, request: InboxRequest) -> TriagedRequest:
        """Process one request. LLM failure becomes an error record, not a crash."""
        try:
            triage, attempts = self._client.classify(request)
        except LLMResponseError as exc:
            logger.error("%s: classification failed — %s", request.id, exc)
            return TriagedRequest.from_request(request, error=str(exc), attempts=exc.attempts)

        return TriagedRequest.from_request(request, triage=triage, attempts=attempts)
