"""Tests for the aggregates the spec requires in report.md."""

from datetime import datetime

from app.schemas.output.triage_result import Category, Priority, TriageResult
from app.schemas.output.triaged_request import TriagedRequest
from app.services.report_service import build_report


def _triage(
    category: Category = Category.AUTOMATION,
    priority: Priority = Priority.MEDIUM,
    department: str | None = None,
    needs_clarification: bool = False,
    question: str | None = None,
) -> TriageResult:
    return TriageResult(
        category=category,
        target_department=department,
        priority=priority,
        short_summary="Тестове саммарі.",
        needs_clarification=needs_clarification,
        clarification_question=question,
        is_actionable=True,
        confidence=0.9,
    )


_UNSET = object()


def _record(req_id: str, triage=_UNSET, **kwargs) -> TriagedRequest:
    # Sentinel, not None: an explicit triage=None means "the LLM failed here".
    return TriagedRequest(
        id=req_id,
        channel="slack",
        timestamp=datetime(2026, 1, 1),
        raw_text="Текст запиту.",
        triage=_triage() if triage is _UNSET else triage,
        **kwargs,
    )


def test_counts_requests_by_category():
    records = [
        _record("REQ-001", _triage(category=Category.AUTOMATION)),
        _record("REQ-002", _triage(category=Category.AUTOMATION)),
        _record("REQ-003", _triage(category=Category.BUG)),
    ]

    report = build_report(records)

    assert "| автоматизація | 2 |" in report
    assert "| баг/підтримка | 1 |" in report


def test_counts_requests_by_priority():
    records = [
        _record("REQ-001", _triage(priority=Priority.HIGH)),
        _record("REQ-002", _triage(priority=Priority.LOW)),
        _record("REQ-003", _triage(priority=Priority.LOW)),
    ]

    report = build_report(records)

    assert "| high | 1 |" in report
    assert "| medium | 0 |" in report
    assert "| low | 2 |" in report


def test_priority_rows_keep_high_medium_low_order():
    report = build_report([_record("REQ-001", _triage(priority=Priority.LOW))])

    assert report.index("| high |") < report.index("| medium |") < report.index("| low |")


def test_counts_requests_by_department():
    records = [
        _record("REQ-001", _triage(department="HR")),
        _record("REQ-002", _triage(department="HR")),
        _record("REQ-003", _triage(department="Продажі")),
    ]

    report = build_report(records)

    assert "| HR | 2 |" in report
    assert "| Продажі | 1 |" in report


def test_requests_without_department_are_grouped_as_unknown():
    report = build_report([_record("REQ-001", _triage(department=None))])

    assert "| невідомо | 1 |" in report


def test_lists_requests_needing_clarification_with_the_question():
    records = [
        _record("REQ-001", _triage()),
        _record(
            "REQ-002",
            _triage(needs_clarification=True, question="Які саме дані потрібні?"),
        ),
    ]

    report = build_report(records)

    assert "**REQ-002**" in report
    assert "Які саме дані потрібні?" in report
    assert "- **REQ-001**: Тестове саммарі." not in report


def test_lists_possible_duplicates():
    records = [
        _record("REQ-001"),
        _record("REQ-013", possible_duplicate_of="REQ-001"),
    ]

    report = build_report(records)

    assert "**REQ-013** may duplicate **REQ-001**" in report


def test_failed_requests_are_reported_and_excluded_from_counts():
    records = [
        _record("REQ-001", _triage(category=Category.AUTOMATION)),
        _record("REQ-002", triage=None, error="LLM failed after 3 attempts"),
    ]

    report = build_report(records)

    assert "**Total requests:** 2" in report
    assert "**Processed successfully:** 1" in report
    assert "**Failed:** 1" in report
    assert "| автоматизація | 1 |" in report
    assert "LLM failed after 3 attempts" in report


def test_sections_say_none_when_there_is_nothing_to_list():
    report = build_report([_record("REQ-001")])

    assert "## Needs Clarification\n\n_None._" in report
    assert "## Possible Duplicates\n\n_None._" in report
