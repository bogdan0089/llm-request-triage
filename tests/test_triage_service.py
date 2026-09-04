"""Tests that a single failing request never aborts the whole run."""

from datetime import datetime

from app.core.exceptions import LLMResponseError
from app.schemas.input.inbox_request import InboxRequest
from app.schemas.output.triage_result import Category, Priority, TriageResult
from app.services.triage_service import TriageService

_OK = TriageResult(
    category=Category.AUTOMATION,
    priority=Priority.MEDIUM,
    short_summary="Test summary.",
    needs_clarification=False,
    is_actionable=True,
    confidence=0.9,
)


def _make(req_id: str) -> InboxRequest:
    return InboxRequest(
        id=req_id,
        channel="slack",
        timestamp=datetime(2026, 1, 1),
        raw_text="Автоматизувати щотижневий звіт.",
    )


class FailingClient:
    """Fails on one specific id, succeeds on the rest."""

    def __init__(self, fail_on: str) -> None:
        self.fail_on = fail_on

    def classify(self, request: InboxRequest) -> tuple[TriageResult, int]:
        if request.id == self.fail_on:
            raise LLMResponseError("model returned an empty response", attempts=3)
        return _OK, 1


def test_failed_request_does_not_abort_the_run():
    requests = [_make("REQ-001"), _make("REQ-002"), _make("REQ-003")]
    records = TriageService(client=FailingClient(fail_on="REQ-002")).run(requests)

    assert len(records) == 3
    assert [r.id for r in records] == ["REQ-001", "REQ-002", "REQ-003"]


def test_failed_request_is_recorded_with_error_and_attempts():
    records = TriageService(client=FailingClient(fail_on="REQ-002")).run([_make("REQ-002")])

    failed = records[0]
    assert failed.triage is None
    assert failed.error == "model returned an empty response"
    assert failed.attempts == 3


def test_successful_requests_keep_their_triage():
    records = TriageService(client=FailingClient(fail_on="REQ-002")).run(
        [_make("REQ-001"), _make("REQ-002")]
    )

    assert records[0].triage is not None
    assert records[0].triage.category == Category.AUTOMATION
    assert records[1].triage is None
