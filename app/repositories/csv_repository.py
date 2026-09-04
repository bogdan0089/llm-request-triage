import csv
import logging
from pathlib import Path

from pydantic import ValidationError

from app.schemas.input.inbox_request import InboxRequest

logger = logging.getLogger(__name__)


def load_requests(path: Path) -> list[InboxRequest]:
    """Read CSV and return valid requests. Skips malformed rows with a warning."""
    requests: list[InboxRequest] = []

    with path.open(encoding="utf-8", newline="") as f:
        for line_no, row in enumerate(csv.DictReader(f), start=2):
            try:
                requests.append(InboxRequest.model_validate(row))
            except ValidationError as exc:
                logger.warning("Row %s skipped: %s", line_no, exc.errors())

    logger.info("Loaded %s requests from %s", len(requests), path.name)
    return requests
