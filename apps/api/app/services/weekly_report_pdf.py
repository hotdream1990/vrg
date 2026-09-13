"""Xuất PDF Báo cáo tuần — map dict báo cáo sang dataclass của package `services/weekly_report`.

Hợp đồng dataclass: plans/260913-weekly-report-v2/plan.md mục D (WeekCol · TableRow · MacroSection ·
WeeklyReportData). File: `Bao-cao-tuan-{span_label, '/' → '-'}.pdf` (vd Bao-cao-tuan-35-36-2026.pdf).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from app.core.paths import data_dir, services_dir


def _pdf_pkg():
    wr = str(services_dir() / "weekly_report")
    if wr not in sys.path:
        sys.path.insert(0, wr)
    from weekly import models, pdf_export  # noqa: E402
    return models, pdf_export


def _assets() -> dict[str, str]:
    wa = data_dir() / "weekly-report-assets"
    ba = data_dir() / "bulletin-assets"
    return {
        "cover-front": str(wa / "cover-front.jpg"),
        "cover-back": str(wa / "cover-back.jpg"),
        "header-banner": str(ba / "header-banner.png"),
        "footer-banner": str(ba / "footer-banner.png"),
        "logo-vrg": str(ba / "logo-vrg.png"),
    }


def to_pdf_data(rep: dict[str, Any], models: Any):
    nar = rep["narrative"]

    def rows(key: str) -> list:
        return [models.TableRow(r["exchange"], r["grade"], list(r["values"])) for r in rep[key]]

    return models.WeeklyReportData(
        title_label=rep["title_label"], date_range=rep["date_range"], span_label=rep["span_label"],
        prev_label=rep["prev_label"], movement_label=rep["movement_label"],
        next_label=rep["next_label"],
        weeks=[models.WeekCol(w["week_no"], w["year"], w["label"]) for w in rep["weeks"]],
        report_note=nar.get("report_note", []),
        summary_prev=nar.get("summary_prev", []), movement=nar.get("movement", []),
        exchange_rows=rows("exchange_rows"), exchange_gaps=rep["exchange_gaps"],
        exchange_table_notes=nar.get("exchange_table_notes", []),
        exchange_notes=nar.get("exchange_notes", []),
        physical_rows=rows("physical_rows"), physical_gaps=rep["physical_gaps"],
        physical_table_notes=nar.get("physical_table_notes", []),
        physical_notes=nar.get("physical_notes", []),
        latex_bands=rep["latex_bands"], latex_changes=rep["latex_changes"],
        latex_notes=nar.get("latex_notes", []),
        macro=[models.MacroSection(s["title"], s.get("bullets", [])) for s in nar.get("macro", [])],
        forecast=nar.get("forecast", []), conclusion=nar.get("conclusion", []),
    )


def pdf_filename(span_label: str) -> str:
    return f"Bao-cao-tuan-{span_label.replace('/', '-')}.pdf"


def generate(rep: dict[str, Any]) -> Path:
    """PDF từ báo cáo đã dựng → đường dẫn file trong data/weekly-reports/."""
    models, pdf_export = _pdf_pkg()
    out = data_dir() / "weekly-reports" / pdf_filename(rep["span_label"])
    return pdf_export.generate_pdf(to_pdf_data(rep, models), _assets(), out)
