"""Render a ready report's JSON payload as CSV or PDF, on demand.

No file is ever persisted — both formats are derived straight from
``Report.payload`` at download time, so there is nothing to store, clean up,
or point a ``file_url`` at. The payload shape differs per report type
(``weekly_summary``, ``project_status``, ``productivity_overview``,
``pr_flow_weekly``), so rendering flattens it into generic label/value rows
rather than hand-rolling a layout per type.
"""

import csv
import io
from typing import Any

from fpdf import FPDF, XPos, YPos

from devflow_api.core.models.report import Report

_TYPE_LABELS = {
    "weekly_summary": "Weekly Summary",
    "project_status": "Project Status",
    "productivity_overview": "Productivity Overview",
    "pr_flow_weekly": "Weekly PR Flow",
}

# fpdf2's core Helvetica font is latin-1 only; PR titles (unlike the rest of
# today's numeric/ISO-date payloads) routinely contain characters outside
# that range. Values are sanitized to latin-1 with replacement rather than
# embedding a TTF, and truncated since pdf.cell() does not wrap text.
_PDF_MAX_CELL_CHARS = 90


def _pdf_text(value: str) -> str:
    safe = value.encode("latin-1", "replace").decode("latin-1")
    if len(safe) > _PDF_MAX_CELL_CHARS:
        return safe[: _PDF_MAX_CELL_CHARS - 3] + "..."
    return safe


def _flatten(payload: dict[str, Any] | None, prefix: str = "") -> list[tuple[str, str]]:
    """Flatten a (possibly nested) payload dict into (label, value) pairs.

    A list of dicts (e.g. a report's ``bottlenecks`` items) is expanded into
    one indexed row group per item rather than joined into a single garbled
    cell; a list of scalars is still joined, since that shape already occurs
    in existing payloads and reads fine as one line.
    """
    rows: list[tuple[str, str]] = []
    if not payload:
        return rows
    for key, value in payload.items():
        label = f"{prefix}{key}"
        if isinstance(value, dict):
            rows.extend(_flatten(value, prefix=f"{label}."))
        elif isinstance(value, list):
            if any(isinstance(item, dict) for item in value):
                for i, item in enumerate(value):
                    if isinstance(item, dict):
                        rows.extend(_flatten(item, prefix=f"{label}[{i}]."))
                    else:
                        rows.append((f"{label}[{i}]", str(item)))
            else:
                rows.append((label, ", ".join(str(v) for v in value)))
        else:
            rows.append((label, str(value)))
    return rows


def _header_rows(report: Report) -> list[tuple[str, str]]:
    return [
        ("type", _TYPE_LABELS.get(report.type, report.type)),
        ("status", report.status),
        (
            "generated_at",
            report.generated_at.isoformat() if report.generated_at else "",
        ),
    ]


def render_csv(report: Report) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["field", "value"])
    for label, value in _header_rows(report):
        writer.writerow([label, value])
    for label, value in _flatten(report.payload):
        writer.writerow([label, value])
    return buffer.getvalue()


def render_pdf(report: Report) -> bytes:
    pdf = FPDF()
    pdf.add_page()

    pdf.set_font("Helvetica", "B", size=16)
    pdf.cell(
        0,
        10,
        text=_pdf_text(_TYPE_LABELS.get(report.type, report.type)),
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )
    pdf.ln(4)

    pdf.set_font("Helvetica", size=10)
    for label, value in [*_header_rows(report), *_flatten(report.payload)]:
        pdf.cell(60, 8, text=_pdf_text(label), border=1)
        pdf.cell(
            0, 8, text=_pdf_text(value), border=1, new_x=XPos.LMARGIN, new_y=YPos.NEXT
        )

    return bytes(pdf.output())
