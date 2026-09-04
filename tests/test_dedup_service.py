"""Tests for duplicate detection logic."""

from datetime import datetime

from app.schemas.output.triage_result import Category, Priority, TriageResult
from app.schemas.output.triaged_request import TriagedRequest
from app.services.dedup_service import mark_duplicates

_TRIAGE = TriageResult(
    category=Category.AUTOMATION,
    priority=Priority.MEDIUM,
    short_summary="Test summary.",
    needs_clarification=False,
    is_actionable=True,
    confidence=0.9,
)


def _make(req_id: str, text: str) -> TriagedRequest:
    return TriagedRequest(
        id=req_id,
        channel="slack",
        timestamp=datetime(2024, 1, 1),
        raw_text=text,
        triage=_TRIAGE,
    )


def test_identical_texts_marked_as_duplicate():
    text = "Хочемо автоматизувати щотижневий звіт по продажах."
    records = [_make("REQ-001", text), _make("REQ-002", text)]
    result = mark_duplicates(records)
    assert result[1].possible_duplicate_of == "REQ-001"
    assert result[0].possible_duplicate_of is None


def test_unrelated_texts_not_marked():
    records = [
        _make(
            "REQ-001",
            "Хочемо автоматизувати щотижневий звіт по продажах — зараз менеджери "
            "щопонеділка вручну збирають дані з таблиць і відправляють керівнику.",
        ),
        _make(
            "REQ-002",
            "Чи можна підключити корпоративну пошту до HR-системи, щоб листи про "
            "нових кандидатів одразу потрапляли в базу рекрутингу?",
        ),
    ]
    result = mark_duplicates(records)
    assert result[0].possible_duplicate_of is None
    assert result[1].possible_duplicate_of is None


def test_failed_request_skipped():
    records = [
        TriagedRequest(
            id="REQ-001",
            channel="slack",
            timestamp=datetime(2024, 1, 1),
            raw_text="Автоматизувати звіт.",
            triage=None,
            error="LLM failed",
        ),
        _make("REQ-002", "Автоматизувати звіт."),
    ]
    result = mark_duplicates(records)
    assert result[1].possible_duplicate_of is None
