"""Service Báo cáo phân tích thị trường TUẦN (v2 — kỳ gộp 1–3 tuần).

Kỳ báo cáo = `weekly_period.period(week_key, span_weeks)`; span lưu trong payload. Bảng số tự dựng
từ giá mỗi lần mở (`weekly_report_tables` · `_gaps` · `_ranges` · `_latex`), không lưu. Narrative
lưu bền trong bảng `weekly_report`. Xuất PDF qua `weekly_report_pdf`.

⚠ Narrative trả về = ĐÚNG những gì đã lưu (+ mặc định rỗng) — KHÔNG nhét số tự tính vào các ô
ghi đè (v1 seed biên độ III.3 vào narrative → web autosave lưu cứng số seed, dữ liệu sửa sau không
cập nhật). Số tự tính nằm ở field cấp báo cáo (`latex_bands`, `latex_changes`…).
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any

from sqlalchemy import text

from app.core.db import ensure_schema, session_scope
from app.services import audit_repo, weekly_period, weekly_report_latex as latex
from app.services import weekly_report_tables as tables
from app.services.weekly_report_gaps import (
    exchange_day_gaps,
    exchange_gap_lines,
    group_exchange_series,
    physical_gap_lines,
)
from app.services.weekly_report_ranges import range_stat

# Tiêu đề Phần IV mặc định — thứ tự + tiêu đề theo báo cáo thật tuần 35–36. Báo cáo đã lưu giữ tiêu đề
# của nó. Đổi thứ tự ở đây thì đổi cả `weekly_ai_macro_prompts._DEFAULT_ORDER` + mã IV.n của nguồn mặc định.
MACRO_TITLES = [
    "1. Thị trường Năng lượng, Địa chính trị & Giá Cao su tổng hợp (Butadiene):",
    "2. Cung – Cầu:",
    "3. Tỷ giá và Tài chính Nhật Bản:",
    "4. Dữ liệu Kinh tế Trung Quốc & Các yếu tố khác:",
]

_NARRATIVE_LISTS = (
    "report_note", "summary_prev", "movement", "exchange_table_notes", "exchange_notes",
    "physical_table_notes", "physical_notes", "latex_notes", "forecast", "conclusion",
)
_PERIOD_KEYS = (
    "week_key", "week_no", "year", "span_weeks", "weeks", "last_week_no", "last_year",
    "date_range", "prev_week_no", "prev_year", "next_week_no", "next_year",
    "prev_col_label", "curr_col_label", "title_label", "span_label", "prev_label",
    "movement_label", "next_label", "list_label",
)


def week_key_for(d: date) -> str:
    return weekly_period.week_key_for(d)


# ── Payload đã lưu ──
def load_saved(week_key: str) -> dict[str, Any]:
    """Payload đã lưu của báo cáo (narrative + span + override) — {} nếu chưa có."""
    ensure_schema()
    with session_scope() as db:
        row = db.execute(text("SELECT payload FROM weekly_report WHERE week_key = :k"),
                         {"k": week_key}).mappings().first()
    if not row:
        return {}
    p = row["payload"]
    return p if isinstance(p, dict) else json.loads(p)


def saved_span(week_key: str) -> int:
    return weekly_period.clamp_span(load_saved(week_key).get("span_weeks", 1))


# ── Bảng số ──
def _market_tables(per: dict[str, Any]) -> dict[str, Any]:
    """Bảng + ghi chú + cao/thấp. `exchange_gap_days` là field NỘI BỘ (nhận định III.1 dùng, không có
    trong schema API): ngày thiếu cả kỳ theo (sàn, chủng loại), tách "không có giá" / "thiếu tỷ giá"."""
    market = tables.load_market(per)
    weeks, in_span = per["weeks"], per["weeks"][1:]
    ex, phys = market["exchange"], market["physical"]
    today = date.today()
    groups = group_exchange_series(tables.EXCHANGE_MAP, ex, tables.FX_PAIR_OF)
    gap_days = exchange_day_gaps(in_span, groups, today)
    no_fx = {(g["exchange"], g["grade"]): g["no_fx"] for g in gap_days}
    ex_stats = [range_stat(exc, g, {d: (c.get("usd"), tables.native_of(key, c)) for d, c in ex[key].items()},
                           in_span, tables.NATIVE_UNITS.get(key), no_fx.get((exc, g)))
                for exc, g, key in tables.EXCHANGE_MAP]
    ph_stats = [range_stat(None, g, {d: (v, None) for d, v in phys[g].items()}, in_span)
                for g, _ in tables.PHYSICAL_MAP]
    return {
        "exchange_rows": tables.exchange_rows(market, weeks),
        "physical_rows": tables.physical_rows(market, weeks),
        "exchange_gaps": exchange_gap_lines(in_span, groups, today),
        "exchange_gap_days": gap_days,
        "physical_gaps": physical_gap_lines(in_span, [(g, phys[g]) for g, _ in tables.PHYSICAL_MAP], today),
        "range_stats": [s for s in ex_stats if s],
        "physical_range_stats": [s for s in ph_stats if s],
        "fx_rows": tables.fx_rows(market, weeks),
    }


def _narrative(nar: dict[str, Any], span: int) -> dict[str, Any]:
    out: dict[str, Any] = {k: nar.get(k) or [] for k in _NARRATIVE_LISTS}
    out.update(
        span_weeks=span,
        macro=nar.get("macro") or [{"title": t, "bullets": []} for t in MACRO_TITLES],
        latex_override=nar.get("latex_override"),
        latex_change_override=nar.get("latex_change_override"),
        latex_prev=nar.get("latex_prev"), latex_curr=nar.get("latex_curr"),
        latex_change=nar.get("latex_change"),
    )
    return out


def build_report(week_key: str) -> dict[str, Any]:
    """Dựng báo cáo: kỳ theo span đã lưu + bảng tự tính từ giá + narrative đã lưu."""
    nar = load_saved(week_key)
    span = weekly_period.clamp_span(nar.get("span_weeks", 1))
    per = weekly_period.period(week_key, span)
    auto = latex.auto_bands(latex.load_values(per["date_from"], per["date_to"]), per["weeks"])
    bands, changes = latex.resolve(auto, *latex.overrides(nar, span))
    auto_bands, auto_changes = latex.resolve(auto, None, None)   # số tự tính, bất kể ghi đè
    return {
        **{k: per[k] for k in _PERIOD_KEYS},
        **_market_tables(per),
        "latex_bands": bands, "latex_changes": changes,
        "latex_auto_bands": auto_bands, "latex_auto_changes": auto_changes,
        "latex_prev": bands[-2], "latex_curr": bands[-1], "latex_change": changes[-1],
        "narrative": _narrative(nar, span),
    }


# ── Lưu / danh sách / xoá ──
def save_narrative(week_key: str, narrative: dict[str, Any]) -> dict[str, Any]:
    """Lưu bền narrative (+ span, override III.3) rồi trả báo cáo dựng lại."""
    payload = dict(narrative)
    payload["span_weeks"] = weekly_period.clamp_span(payload.get("span_weeks", 1))
    if isinstance(payload.get("latex_override"), list) or isinstance(payload.get("latex_change_override"), list):
        # Đã sang chế độ ghi đè v2 → bỏ trường v1, tránh số seed cũ "sống lại" khi xoá ghi đè.
        payload.update(latex_prev=None, latex_curr=None, latex_change=None)
    ensure_schema()
    with session_scope() as db:
        row = db.execute(text("SELECT payload FROM weekly_report WHERE week_key = :k"),
                         {"k": week_key}).mappings().first()
        before = dict(row["payload"]) if row else None
        db.execute(text("""
            INSERT INTO weekly_report (week_key, payload) VALUES (:k, CAST(:p AS jsonb))
            ON CONFLICT (week_key) DO UPDATE SET payload = EXCLUDED.payload, updated_at = now()
        """), {"k": week_key, "p": json.dumps(payload, ensure_ascii=False)})
    audit_repo.log("bulletin_weekly", "update" if before else "create", week_key,
                   before=before, after=payload, as_of=week_key,
                   note=f"Kỳ bắt đầu {week_key}", coalesce=True)
    return build_report(week_key)


def list_reports() -> list[dict[str, Any]]:
    ensure_schema()
    with session_scope() as db:
        rows = db.execute(text(
            "SELECT week_key, payload->>'span_weeks' AS span, updated_at "
            "FROM weekly_report ORDER BY week_key DESC"
        )).mappings().all()
    out = []
    for r in rows:
        per = weekly_period.period(str(r["week_key"]), r["span"] or 1)
        out.append({"week_key": per["week_key"], "week_no": per["week_no"], "year": per["year"],
                    "span_weeks": per["span_weeks"], "label": per["list_label"],
                    "updated": str(r["updated_at"]) if r["updated_at"] else None})
    return out


def _delete_attachments(week_key: str) -> int:
    try:
        # Import lười: nhánh đính kèm (weekly_attachment_service) phát triển song song — thiếu
        # module thì vẫn xoá được báo cáo (và test của service này chạy độc lập).
        from app.services import weekly_attachment_service
    except ImportError:
        return 0
    return weekly_attachment_service.delete_all(week_key)


def delete_report(week_key: str) -> bool:
    """Xoá báo cáo + toàn bộ tài liệu đính kèm của kỳ (đính kèm không ràng FK nên xoá riêng)."""
    ensure_schema()
    with session_scope() as db:
        row = db.execute(text("SELECT payload FROM weekly_report WHERE week_key = :k"),
                         {"k": week_key}).mappings().first()
        before = dict(row["payload"]) if row else None
        res = db.execute(text("DELETE FROM weekly_report WHERE week_key = :k"), {"k": week_key})
        deleted = res.rowcount > 0
    removed = _delete_attachments(week_key)
    if deleted:
        audit_repo.log("bulletin_weekly", "delete", week_key, before=before, as_of=week_key,
                       note=f"Xoá kèm {removed} tài liệu đính kèm" if removed else None)
    return deleted or removed > 0


# ── Xuất PDF ──
def generate_pdf(week_key: str):
    """Xuất PDF báo cáo từ bản đã lưu → đường dẫn file trong data/weekly-reports/."""
    from app.services import weekly_report_pdf

    return weekly_report_pdf.generate(build_report(week_key))
