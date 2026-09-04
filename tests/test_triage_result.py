"""Tests for TriageResult schema validation and field normalisation."""

import pytest
from pydantic import ValidationError

from app.schemas.output.triage_result import Category, Priority, TriageResult

VALID_PAYLOAD = {
    "category": "автоматизація",
    "priority": "medium",
    "short_summary": "Автоматизувати звітність відділу продажів.",
    "requested_actions": ["Створити скрипт", "Надіслати звіт"],
    "needs_clarification": False,
    "is_actionable": True,
    "confidence": 0.9,
}


def test_valid_payload():
    result = TriageResult.model_validate(VALID_PAYLOAD)
    assert result.category == Category.AUTOMATION
    assert result.priority == Priority.MEDIUM
    assert result.confidence == 0.9


def test_invalid_category_raises():
    payload = {**VALID_PAYLOAD, "category": "невідома категорія"}
    with pytest.raises(ValidationError):
        TriageResult.model_validate(payload)


def test_confidence_out_of_range_raises():
    payload = {**VALID_PAYLOAD, "confidence": 1.5}
    with pytest.raises(ValidationError):
        TriageResult.model_validate(payload)


def test_empty_to_none_normalises_no_value_tokens():
    payload = {**VALID_PAYLOAD, "target_department": "не зрозуміло"}
    result = TriageResult.model_validate(payload)
    assert result.target_department is None


def test_empty_to_none_keeps_real_value():
    payload = {**VALID_PAYLOAD, "target_department": "HR"}
    result = TriageResult.model_validate(payload)
    assert result.target_department == "HR"


def test_clean_actions_removes_duplicates():
    payload = {**VALID_PAYLOAD, "requested_actions": ["Зробити звіт", "зробити звіт", "Надіслати"]}
    result = TriageResult.model_validate(payload)
    assert result.requested_actions == ["Зробити звіт", "Надіслати"]


def test_clean_actions_removes_empty_strings():
    payload = {**VALID_PAYLOAD, "requested_actions": ["Зробити звіт", "", "  "]}
    result = TriageResult.model_validate(payload)
    assert result.requested_actions == ["Зробити звіт"]
