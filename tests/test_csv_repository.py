"""Tests for CSV loading: valid rows are parsed, malformed rows are skipped."""

from pathlib import Path

from app.repositories.csv_repository import load_requests

HEADER = "id,channel,timestamp,raw_text\n"
VALID_ROW = "REQ-001,Slack,2026-06-08 09:14,Автоматизувати щотижневий звіт.\n"


def _write_csv(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "input.csv"
    path.write_text(HEADER + body, encoding="utf-8")
    return path


def test_loads_valid_row(tmp_path):
    requests = load_requests(_write_csv(tmp_path, VALID_ROW))

    assert len(requests) == 1
    assert requests[0].id == "REQ-001"
    assert requests[0].channel == "Slack"
    assert requests[0].raw_text == "Автоматизувати щотижневий звіт."


def test_timestamp_is_parsed_into_datetime(tmp_path):
    requests = load_requests(_write_csv(tmp_path, VALID_ROW))

    assert requests[0].timestamp.year == 2026
    assert requests[0].timestamp.hour == 9
    assert requests[0].timestamp.minute == 14


def test_row_with_empty_id_is_skipped(tmp_path):
    body = VALID_ROW + ",Slack,2026-06-08 10:00,Текст без ідентифікатора.\n"

    requests = load_requests(_write_csv(tmp_path, body))

    assert [r.id for r in requests] == ["REQ-001"]


def test_row_with_unparsable_timestamp_is_skipped(tmp_path):
    body = VALID_ROW + "REQ-002,Slack,не дата,Текст із битою датою.\n"

    requests = load_requests(_write_csv(tmp_path, body))

    assert [r.id for r in requests] == ["REQ-001"]


def test_row_with_empty_text_is_skipped(tmp_path):
    body = VALID_ROW + "REQ-002,Slack,2026-06-08 10:00,\n"

    requests = load_requests(_write_csv(tmp_path, body))

    assert [r.id for r in requests] == ["REQ-001"]


def test_valid_rows_after_a_broken_one_are_still_loaded(tmp_path):
    body = (
        "REQ-001,Slack,не дата,Битий рядок.\n"
        "REQ-002,Telegram,2026-06-08 10:00,Валідний рядок.\n"
    )

    requests = load_requests(_write_csv(tmp_path, body))

    assert [r.id for r in requests] == ["REQ-002"]


def test_broken_row_is_logged_with_its_line_number(tmp_path, caplog):
    body = VALID_ROW + "REQ-002,Slack,не дата,Битий рядок.\n"

    load_requests(_write_csv(tmp_path, body))

    assert "Row 3 skipped" in caplog.text


def test_empty_file_returns_empty_list(tmp_path):
    assert load_requests(_write_csv(tmp_path, "")) == []
