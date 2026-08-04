"""Render a ready report's JSON payload as CSV or PDF, on demand.

No file is ever persisted — both formats are derived straight from
``Report.payload`` at download time, so there is nothing to store, clean up,
or point a ``file_url`` at. The payload shape differs per report type
(``weekly_summary``, ``project_status``, ``productivity_overview``), so
rendering flattens it into generic label/value rows rather than hand-rolling
a layout per type.
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
}


def _flatten(payload: dict[str, Any] | None, prefix: str = "") -> list[tuple[str, str]]:
    """Flatten a (possibly nested) payload dict into (label, value) pairs."""
    rows: list[tuple[str, str]] = []
    if not payload:
        return rows
    for key, value in payload.items():
        label = f"{prefix}{key}"
        if isinstance(value, dict):
            rows.extend(_flatten(value, prefix=f"{label}."))
        elif isinstance(value, list):
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
        text=_TYPE_LABELS.get(report.type, report.type),
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )
    pdf.ln(4)

    pdf.set_font("Helvetica", size=10)
    for label, value in [*_header_rows(report), *_flatten(report.payload)]:
        pdf.cell(60, 8, text=label, border=1)
        pdf.cell(0, 8, text=value, border=1, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    return bytes(pdf.output())
