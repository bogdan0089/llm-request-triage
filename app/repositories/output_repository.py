import json
import logging
from pathlib import Path

from app.schemas.output.triaged_request import TriagedRequest

logger = logging.getLogger(__name__)


def write_json(records: list[TriagedRequest], path: Path) -> None:
    """Write the full structured result for all requests to a JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [record.model_dump(mode="json") for record in records]
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Wrote %s records to %s", len(records), path)


def write_text(content: str, path: Path) -> None:
    """Write a text report to disk."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    logger.info("Wrote report to %s", path)
