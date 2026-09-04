from difflib import SequenceMatcher

from app.schemas.output.triaged_request import TriagedRequest

SIMILARITY_THRESHOLD = 0.35


def mark_duplicates(records: list[TriagedRequest]) -> list[TriagedRequest]:
    """Flag near-duplicate requests by comparing raw_text with difflib.

    Each request is compared against all earlier ones and points at the first
    match, so a chain of restatements all resolve to the original. Failed
    requests are skipped: without a triage result there is nothing to dedupe.
    """
    comparable = [r for r in records if r.triage is not None]

    for index, record in enumerate(comparable):
        for earlier in comparable[:index]:
            ratio = SequenceMatcher(
                None,
                earlier.raw_text.lower(),
                record.raw_text.lower(),
            ).ratio()

            if ratio >= SIMILARITY_THRESHOLD:
                record.possible_duplicate_of = earlier.id
                break

    return records
