"""SNAPSHOT số liệu TUẦN toàn hệ thống — thu mua · tiêu thụ · tồn kho của TỪNG đơn vị.

Yêu cầu chủ dự án 24/09/2026: hết hạn nhập của ngày cuối tuần thì hệ thống tự chụp số liệu tuần,
làm bản lưu cố định để đối chiếu về sau.

Luật:
- **Tuần** = thứ Hai → Chủ nhật (ISO). Khoá bản lưu = ngày thứ Hai.
- **Đủ điều kiện chụp** khi đã qua hạn nhập của ngày Chủ nhật: `edit_window.deadline(CN, N)` với N
  là cửa sổ nhập của đơn vị (N = 1 ⇒ 11:00 thứ Hai). Trước mốc này đơn vị còn được sửa số tuần đó.
- **Số liệu** = NGUYÊN kết quả `unit_period_report.period_report` của tuần (mặc định GỘP đơn vị sáp
  nhập) — cùng nguồn với màn Báo cáo tổng hợp nên bản lưu khớp tuyệt đối với màn đó ở thời điểm
  chụp. Không viết lại công thức nào ở đây. Tồn kho theo đúng luật của báo cáo đó: số THỜI ĐIỂM của
  ngày cuối cùng CÓ nhập tồn trong tuần (kèm `stock_as_of`).
- **Chỉ chụp tuần GẦN NHẤT đủ điều kiện**, không chụp bù tuần cũ hơn — kể cả lần chạy đầu tiên: số
  liệu tuần cũ có thể đã được sửa sau hạn (đề nghị sửa được duyệt, admin sửa hộ), chụp muộn thì
  không còn là "số chốt đúng hạn" nữa, dựng hàng loạt bản lưu như vậy dễ gây hiểu nhầm.
- **Không bao giờ chụp đè** tuần đã có bản lưu. `taken_at` ghi giờ chụp thật (so với `deadline_at`
  để biết chụp trễ bao lâu nếu máy chủ tắt đúng giờ chạy). Web chỉ gắn nhãn "chụp sau hạn" khi trễ
  QUÁ 24 giờ (`LATE_AFTER_MS` ở `unit-week-snapshot-client.ts`): job chạy giờ cố định, đổi giờ chốt
  lệch vài giờ không được làm mọi tuần bị gắn nhãn.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from app.core import edit_window
from app.services import unit_period_report, unit_week_snapshot_repo as repo
from app.services.weekly_period import range_text

#: Job hằng ngày (đăng ký ở `services/scheduler.py`) — chạy ngay sau giờ chốt 11:00. Giờ job CỐ ĐỊNH,
#: không tự bám `EDIT_CUTOFF_HOUR`: admin đổi giờ chốt thì chỉnh giờ 2 job "unit-week-snapshot" và
#: "anomaly-notify" ở trang Lịch chạy (đặt ngay sau giờ chốt mới).
JOB_NAME = "unit-week-snapshot"
#: Ghi vào `meta_crawl_run.sources` → trang Lịch chạy hiện lần chạy gần nhất + biết job đã lỡ.
JOB_SOURCE = "unit-week-snapshot"
JOB_DEFAULT = (11, 10, None)          # (giờ, phút, thứ) — None = hằng ngày

KINDS = ("purchase", "consumption")
_VN = ZoneInfo("Asia/Ho_Chi_Minh")

#: Chỉ tiêu giá / tỷ lệ — KHÔNG cộng ở dòng Tổng cộng (giống file Excel và màn Báo cáo tổng hợp).
_NO_SUM = frozenset({"price_latex_avg", "price_cup_avg", "price_lace_avg", "pct_plan",
                     "avg_sell_price", "pct_plan_sales_spot", "pct_plan_revenue"})


# ── Tuần & hạn chụp ────────────────────────────────────────────────────────────
def sunday_on_or_before(d: date) -> date:
    return d - timedelta(days=(d.weekday() + 1) % 7)


def week_deadline(week_start: date) -> datetime:
    """Hạn nhập số liệu ngày Chủ nhật của tuần (giờ VN) = mốc sớm nhất được phép chụp."""
    return edit_window.deadline(week_start + timedelta(days=6), edit_window.member_window())


def due_week(ref: datetime | None = None) -> date:
    """Thứ Hai của tuần GẦN NHẤT đã qua hạn nhập ngày Chủ nhật, tính tại thời điểm `ref`."""
    n = edit_window._vn(ref)   # quy về giờ VN; mốc không kèm múi giờ coi như ĐÃ là giờ VN
    if n.tzinfo is None:       # …nhưng `deadline` luôn kèm múi giờ → gắn vào để so sánh được
        n = n.replace(tzinfo=_VN)
    window, hour = edit_window.member_window(), edit_window.cutoff_hour()
    sun = sunday_on_or_before(n.date())
    while edit_window.deadline(sun, window, hour) > n:
        sun -= timedelta(days=7)
    return sun - timedelta(days=6)


def week_info(week_start: date | str) -> dict[str, Any]:
    """Nhãn tuần cho người đọc: 'Tuần 38 (14/9 – 20/9/2026)'."""
    mon = date.fromisoformat(week_start) if isinstance(week_start, str) else week_start
    sun = mon + timedelta(days=6)
    iso = mon.isocalendar()
    return {"week_start": mon.isoformat(), "week_end": sun.isoformat(),
            "week_no": iso[1], "year": iso[0],
            "label": f"Tuần {iso[1]} ({range_text(mon, sun)})"}


# ── Dựng bản lưu (KHÔNG ghi) ──────────────────────────────────────────────────
def totals(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Dòng Tổng cộng: cộng mọi chỉ tiêu số (kể cả tồn theo chủng loại), bỏ giá/tỷ lệ/ngày."""
    out: dict[str, Any] = {"unit_count": len(rows),
                           "reporting_units": sum(1 for r in rows if r.get("days"))}
    for r in rows:
        for k, v in r.items():
            if k in _NO_SUM or isinstance(v, bool):
                continue
            if isinstance(v, (int, float)):
                out[k] = out.get(k, 0.0) + v
            elif isinstance(v, dict):
                sub = out.setdefault(k, {})
                for g, x in v.items():
                    if isinstance(x, (int, float)) and not isinstance(x, bool):
                        sub[g] = sub.get(g, 0.0) + x
    return out


def build(week_start: date) -> dict[str, Any]:
    """Số liệu tuần đúng như Báo cáo tổng hợp đang trả lúc này — chỉ tính, không ghi DB."""
    d_from = week_start.isoformat()
    d_to = (week_start + timedelta(days=6)).isoformat()
    reports = {k: unit_period_report.period_report(k, d_from, d_to) for k in KINDS}
    return {"week_start": d_from, "week_end": d_to, **reports,
            "totals": {k: totals(reports[k]["rows"]) for k in KINDS}}


# ── Chụp ───────────────────────────────────────────────────────────────────────
def take_due(by: str, ref: datetime | None = None) -> dict[str, Any]:
    """Chụp tuần gần nhất đủ điều kiện nếu CHƯA có bản lưu. Trả `{taken, reason, week, snapshot}`."""
    ws = due_week(ref)
    info = week_info(ws)
    # Kiểm trước khi dựng: dựng 2 biểu mất vài giây, tuần đã có bản lưu thì khỏi tốn công.
    row = repo.get_summary(info["week_start"])
    if row is None:
        row = repo.insert(build(ws), week_deadline(ws), by)
        if row is not None:
            return {"taken": True, "reason": "ok", "week": info, "snapshot": {**info, **row}}
        # Lượt chụp khác vừa ghi trước (job + admin bấm "Chụp ngay" cùng lúc) — giữ bản của họ.
        row = repo.get_summary(info["week_start"])
    return {"taken": False, "reason": "exists", "week": info, "snapshot": {**info, **(row or {})}}


def list_items() -> list[dict[str, Any]]:
    return [{**week_info(r["week_start"]), **r} for r in repo.list_summaries()]


def detail(week_start: str) -> dict[str, Any] | None:
    row = repo.get(week_start)
    return {**week_info(week_start), **row} if row else None


def status(ref: datetime | None = None) -> dict[str, Any]:
    """Tuần đang đủ điều kiện (đã chụp chưa) + tuần kế tiếp sẽ chụp lúc nào — cho màn hình."""
    ws = due_week(ref)
    nxt = ws + timedelta(days=7)
    return {
        "due": {**week_info(ws), "deadline_at": week_deadline(ws).isoformat(),
                "taken": repo.get_summary(ws.isoformat()) is not None},
        "next": {**week_info(nxt), "deadline_at": week_deadline(nxt).isoformat()},
    }


# ── Job định kỳ (+ chạy bù sau khi khởi động lại) ─────────────────────────────
def run_job() -> dict[str, Any]:
    """Chạy theo lịch. LUÔN ghi 1 dòng `meta_crawl_run` — cơ chế chạy bù so theo dòng này."""
    from app.services import price_repo

    run_id = price_repo.create_run(JOB_SOURCE)
    try:
        res = take_due(by="job")
    except Exception as exc:                  # noqa: BLE001 - lỗi phải hiện ở trang Lịch chạy
        price_repo.finish_run(run_id, "error", 0, str(exc))
        return _job_result(run_id, "error", 0, str(exc))
    label = res["week"]["label"]
    if res["taken"]:
        n = res["snapshot"]["totals"]["purchase"]["reporting_units"]
        note = f"Đã chụp số liệu {label} — {n} đơn vị có số thu mua trong tuần."
        price_repo.finish_run(run_id, "ok", 1, None)
        return _job_result(run_id, "ok", 1, note)
    note = f"{label} đã có bản lưu — không chụp lại (bản lưu cố định)."
    price_repo.finish_run(run_id, "empty", 0, None)
    return _job_result(run_id, "empty", 0, note)


def _job_result(run_id: int, status_: str, rows: int, note: str) -> dict[str, Any]:
    """Khuôn kết quả job — giữ đúng shape của `scan_service` để UI Lịch chạy khỏi rẽ nhánh."""
    return {"records": [], "persisted": rows, "run_id": run_id,
            "sources": [{"source": JOB_SOURCE, "status": status_, "count": rows, "note": note}]}
