import logging

from app.core.config import settings
from app.core.logging import setup_logging
from app.repositories.csv_repository import load_requests
from app.repositories.output_repository import write_json, write_text
from app.services.dedup_service import mark_duplicates
from app.services.report_service import build_report
from app.services.triage_service import TriageService

logger = logging.getLogger(__name__)


def main() -> None:
    setup_logging()

    requests = load_requests(settings.input_csv)
    records = TriageService().run(requests)
    records = mark_duplicates(records)

    write_json(records, settings.output_dir / "output.json")

    report = build_report(records)
    write_text(report, settings.output_dir / "report.md")
    logger.info("Report written to %s", settings.output_dir / "report.md")


if __name__ == "__main__":
    main()
