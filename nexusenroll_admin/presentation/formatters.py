"""
presentation/formatters.py

Role: PRESENTATION TIER — plain-text table rendering.

No external dependencies (per project preference) — builds aligned
ASCII tables using only the standard library. Works generically off
lists of dicts (column name -> value), which is exactly what
ReportingService/Report.to_rows() and the entity-listing helpers in
main.py produce, so the same function renders reports AND plain
entity listings (course lists, student lists, etc.) without
duplicated formatting code (DRY).
"""


def render_table(rows: list, empty_message: str = "No data to display.") -> str:
    """
    Render a list of dicts as an aligned plain-text table.

    All dicts are expected to share the same keys (column order taken
    from the first row). Returns a printable multi-line string.
    """
    if not rows:
        return empty_message

    columns = list(rows[0].keys())
    str_rows = [[str(row.get(col, "")) for col in columns] for row in rows]

    widths = [len(col) for col in columns]
    for row in str_rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))

    def format_row(cells):
        return " | ".join(cell.ljust(widths[i]) for i, cell in enumerate(cells))

    header = format_row(columns)
    separator = "-+-".join("-" * w for w in widths)
    body = "\n".join(format_row(r) for r in str_rows)

    return f"{header}\n{separator}\n{body}"


def render_report(report) -> str:
    """Render a Report object (patterns/reports.py) as a titled plain-text table."""
    table = render_table(report.to_rows())
    return f"\n=== {report.title} ===\n{table}\n"
