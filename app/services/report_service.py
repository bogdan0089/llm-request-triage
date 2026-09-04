from collections import defaultdict

from app.schemas.output.triaged_request import TriagedRequest


def build_report(records: list[TriagedRequest]) -> str:
    """Render aggregate statistics over triaged requests as a Markdown report."""
    by_category: dict[str, int] = defaultdict(int)
    by_priority: dict[str, int] = defaultdict(int)
    by_department: dict[str, int] = defaultdict(int)
    needs_clarification: list[TriagedRequest] = []
    duplicates: list[TriagedRequest] = []
    failed: list[TriagedRequest] = []

    for record in records:
        if record.possible_duplicate_of is not None:
            duplicates.append(record)

        if record.triage is None:
            failed.append(record)
            continue

        by_category[record.triage.category.value] += 1
        by_priority[record.triage.priority.value] += 1

        dept = record.triage.target_department or "невідомо"
        by_department[dept] += 1

        if record.triage.needs_clarification:
            needs_clarification.append(record)

    lines: list[str] = []

    lines.append("# Triage Report\n")
    lines.append(f"**Total requests:** {len(records)}  ")
    lines.append(f"**Processed successfully:** {len(records) - len(failed)}  ")
    lines.append(f"**Failed:** {len(failed)}\n")

    lines.append("## By Category\n")
    lines.append("| Category | Count |")
    lines.append("|---|---|")
    for cat, count in sorted(by_category.items(), key=lambda x: -x[1]):
        lines.append(f"| {cat} | {count} |")

    lines.append("\n## By Priority\n")
    lines.append("| Priority | Count |")
    lines.append("|---|---|")
    for priority in ("high", "medium", "low"):
        count = by_priority.get(priority, 0)
        lines.append(f"| {priority} | {count} |")

    lines.append("\n## By Department\n")
    lines.append("| Department | Count |")
    lines.append("|---|---|")
    for dept, count in sorted(by_department.items(), key=lambda x: -x[1]):
        lines.append(f"| {dept} | {count} |")

    lines.append("\n## Needs Clarification\n")
    if needs_clarification:
        for record in needs_clarification:
            question = record.triage.clarification_question or "—"
            lines.append(f"- **{record.id}**: {record.triage.short_summary}")
            lines.append(f"  - *Question:* {question}")
    else:
        lines.append("_None._")

    lines.append("\n## Possible Duplicates\n")
    if duplicates:
        for record in duplicates:
            lines.append(f"- **{record.id}** may duplicate **{record.possible_duplicate_of}**")
    else:
        lines.append("_None._")

    if failed:
        lines.append("\n## Failed Requests\n")
        for record in failed:
            lines.append(f"- **{record.id}**: {record.error}")

    return "\n".join(lines) + "\n"
