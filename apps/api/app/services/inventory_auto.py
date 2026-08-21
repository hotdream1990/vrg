"""Tự tính TỒN KHO TẬP ĐOÀN theo tuần từ số liệu đơn vị thành viên đã nộp.

Trước đây chuyên viên gõ tay từng tuần theo báo cáo tuần chị Hạnh. Nay các đơn vị đã nhập biểu
"Tồn kho" hằng ngày, nên tổng của Tập đoàn có thể cộng thẳng từ đó mỗi khi đơn vị nộp/sửa.

Chốt với chủ đề án 20/08/2026 (đối chiếu số tay 07/08 và 24/07):
- **Tồn kho** = tổng khối **"Đã nhập kho"** của các đơn vị (KHÔNG cộng khối "Chưa nhập kho" —
  số tay của Ban TTKD sát khối này nhất: 50.115 vs 51.501 tấn, lệch 2,7%).
- **Tồn kho đã có HĐ** = tổng `min(đã ký HĐ chưa giao, đã nhập kho)` của **TỪNG** đơn vị. Cắt trần
  vì hợp đồng ký cả cho hàng chưa sản xuất (MeKong tồn 366 t nhưng đã ký 8.589 t) — cộng nguyên
  số hợp đồng thì phần "đã có HĐ" vượt quá cả tồn kho, trong khi theo định nghĩa nó NẰM TRONG
  tồn kho. Tỷ lệ HĐ/tồn của cách cắt trần (61-63%) bám sát số tay (68-71%).

Hai đường ghi, khác nhau ở chỗ có đè số người gõ hay không:
1. **Tự động** (công tắc `INVENTORY_AUTO`, mặc định TẮT) — chạy mỗi khi đơn vị nộp/sửa biểu Tồn
   kho, chỉ ghi tuần CHƯA có số hoặc tuần trước đó cũng do máy tính. Tuần chuyên viên đã nhập tay
   (`source` = manual/hanh_weekly) KHÔNG bao giờ bị đè.
2. **Đồng bộ thủ công 1 tuần** (`apply_week(force=True)`) — chuyên viên bấm nút, luôn dùng được kể
   cả khi công tắc đang tắt, và ĐƯỢC đè số tay (đó là thao tác cố ý).

Số tự tính chảy thẳng vào Command Center · Bản tin biến động · Trợ lý AI nên luôn kèm `note` ghi
rõ độ phủ (bao nhiêu đơn vị có số): thiếu đơn vị mà không nói ra thì người xem tưởng là số đủ.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from app.core.edit_window import today
from app.services import config_repo, inventory_repo

#: Công tắc tổng — để ở `app_config` (KHÔNG khai trong `CONFIG_SPEC`: đây là công tắc nghiệp vụ
#: của chuyên viên ngay trong màn Tồn kho, không phải cấu hình hệ thống của admin).
AUTO_KEY = "INVENTORY_AUTO"
_ON, _OFF = "on", "off"

#: Nguồn ghi vào `fact_inventory` để phân biệt với 'manual' (gõ tay) và 'hanh_weekly' (nạp PDF).
AUTO_SOURCE = "auto"

#: Ngày chốt tuần = **thứ Sáu** — đúng chu kỳ chuyên viên đang nhập (79/81 tuần trong DB là thứ Sáu).
ANCHOR_WEEKDAY = 4                  # date.weekday(): 0=Thứ Hai … 4=Thứ Sáu

#: Cửa sổ TÍNH LẠI: bản ghi ngày D có thể đổi số của các tuần chốt trong ngần này ngày sau đó (đơn
#: vị tick "không phát sinh" ở các ngày kế tiếp thì số ngày D còn được dùng cho tuần sau).
#: ⚠ KHÔNG phải "số ngày được phép đắp số cũ" — quy tắc lấy số nằm ở `unit_report_rows.stock_rows`.
MAX_AGE_DAYS = 7

DEFAULT_RECOMPUTE_WEEKS = 8
MAX_RECOMPUTE_WEEKS = 52

#: Job định kỳ tối thứ Sáu (đăng ký ở `services/scheduler.py`).
WEEKLY_JOB_NAME = "inventory-weekly"
#: Ghi vào `meta_crawl_run.sources` → trang Lịch chạy hiện "lần chạy gần nhất" và biết job đã lỡ.
WEEKLY_JOB_SOURCE = "inventory-auto"
#: Job tính lại 4 tuần gần nhất chứ không chỉ tuần vừa chốt: đơn vị nộp muộn thì tuần cũ được cập
#: nhật theo, và một lần chạy bù sau khi máy chủ tắt vài tuần vẫn lấp được các tuần đã lỡ.
WEEKLY_JOB_WEEKS = 4

#: Số tên đơn vị liệt kê trong ghi chú (dài hơn thì gộp phần đuôi).
_MAX_NAMES = 5


# ── Công tắc ───────────────────────────────────────────────────────────────────
def enabled() -> bool:
    """Công tắc tự động đang bật?"""
    return (config_repo.get_value(AUTO_KEY) or _OFF).strip().lower() == _ON


def save_config(on: bool, by: str | None = None) -> dict[str, Any]:
    """Bật/tắt tự động tính (chuyên viên tự bấm, không cần admin)."""
    config_repo.set_value(AUTO_KEY, _ON if on else _OFF, by)
    return config()


def config() -> dict[str, Any]:
    """Trạng thái cho màn cấu hình: công tắc + tham số chu kỳ + tuần chốt gần nhất."""
    return {
        "enabled": enabled(),
        "weekday_label": "Thứ Sáu hằng tuần",
        "recompute_window_days": MAX_AGE_DAYS,
        "recompute_weeks": DEFAULT_RECOMPUTE_WEEKS,
        "last_anchor": last_anchor().isoformat(),
    }


# ── Ngày chốt tuần ─────────────────────────────────────────────────────────────
def anchor_on_or_after(day: date) -> date:
    """Ngày chốt tuần đầu tiên ≥ `day` (chính nó nếu `day` đã là thứ Sáu)."""
    return day + timedelta(days=(ANCHOR_WEEKDAY - day.weekday()) % 7)


def last_anchor(ref: date | None = None) -> date:
    """Ngày chốt tuần gần nhất ĐÃ QUA (≤ hôm nay) — tuần đang chờ số."""
    d = ref or today()
    return d - timedelta(days=(d.weekday() - ANCHOR_WEEKDAY) % 7)


def anchors_for(as_of: str) -> list[str]:
    """Các tuần bị ảnh hưởng khi đơn vị nộp/sửa số liệu ngày `as_of`.

    Một bản ghi ngày D được tính cho ngày chốt A khi D ≤ A ≤ D + `MAX_AGE_DAYS` (đơn vị không nộp
    đúng ngày chốt thì số gần nhất của họ được dùng). Tuần chưa tới thì bỏ qua — chưa chốt xong.
    """
    day = date.fromisoformat(as_of)
    limit = today()
    out: list[str] = []
    a = anchor_on_or_after(day)
    while (a - day).days <= MAX_AGE_DAYS:
        if a <= limit:
            out.append(a.isoformat())
        a += timedelta(days=7)
    return out


# ── Tính số ────────────────────────────────────────────────────────────────────
def compute(as_of: str) -> dict[str, Any]:
    """Số tồn kho Tập đoàn tại ngày chốt `as_of`, cộng từ biểu Tồn kho của các đơn vị.

    Dùng lại NGUYÊN quy tắc của màn "Thống kê tồn kho" (`unit_report_stock`) để hai màn không bao
    giờ lệch nhau: đơn vị khai ngày nào lấy ngày đó, tick "không phát sinh tồn kho" thì giữ số lần
    khai gần nhất, không khai gì thì không có số.
    """
    from app.services import unit_report_stock

    rep = unit_report_stock.stock_report(as_of, group_by="company")
    ton = hd = 0.0
    for g in rep["rows"]:
        warehoused = g["warehoused"] or 0.0        # KHÔNG lấy `total`: chỉ khối "Đã nhập kho"
        ton += warehoused
        hd += min(g["signed_undelivered"] or 0.0, warehoused)
    cov = rep["coverage"]
    missing = [m["company"] for m in cov["missing"]]
    return {
        "as_of": as_of,
        "ton_kho": round(ton, 3) if cov["units_counted"] else None,
        "ton_kho_hd": round(hd, 3) if cov["units_counted"] else None,
        "units_counted": cov["units_counted"], "units_expected": cov["units_expected"],
        "missing": missing, "no_stock": [n["company"] for n in cov["no_stock"]],
        "note": _note(cov["units_counted"], cov["units_expected"], missing),
    }


def _note(counted: int, expected: int, missing: list[str]) -> str:
    """Ghi chú kèm số: LUÔN nói rõ độ phủ để không ai hiểu nhầm đây là số của đủ 100% đơn vị."""
    txt = f"Tự tính từ biểu Tồn kho của {counted}/{expected} đơn vị thành viên"
    if missing:
        head = ", ".join(missing[:_MAX_NAMES])
        more = len(missing) - _MAX_NAMES
        txt += f" — chưa có số: {head}" + (f" …và {more} đơn vị khác" if more > 0 else "")
    return txt


# ── Ghi vào chuỗi tuần ─────────────────────────────────────────────────────────
def apply_week(as_of: str, *, force: bool = False, by: str | None = None) -> dict[str, Any]:
    """Tính và ghi số tự tính cho 1 tuần. Trả `{written, reason, data, week}`.

    `force=False` (chạy tự động): tuần chuyên viên đã nhập tay/nạp PDF thì GIỮ NGUYÊN.
    `force=True`  (chuyên viên bấm nút đồng bộ tuần này): ghi đè, kể cả số tay.
    """
    data = compute(as_of)
    if not data["units_counted"]:
        return {"written": False, "reason": "no_data", "data": data, "week": None}
    cur = inventory_repo.get(as_of)
    if cur and not force and (cur.get("source") or "") != AUTO_SOURCE:
        return {"written": False, "reason": "manual", "data": data, "week": cur}
    week = inventory_repo.upsert(as_of, data["ton_kho"], data["ton_kho_hd"], data["note"],
                                 source=AUTO_SOURCE,
                                 audit_note="Tự tính tồn kho từ số liệu đơn vị thành viên",
                                 actor=by)
    return {"written": True, "reason": "ok", "data": data, "week": week}


def sync_for_date(as_of: str, by: str | None = None) -> list[str]:
    """Móc gọi khi đơn vị nộp/sửa biểu Tồn kho ngày `as_of` — cập nhật các tuần bị ảnh hưởng.

    Công tắc tắt thì KHÔNG làm gì (không có thao tác cố ý của chuyên viên thì chuỗi tuần không tự
    đổi). Lỗi ở đây không bao giờ được làm hỏng thao tác lưu của đơn vị → gọi trong try/except.
    """
    if not enabled():
        return []
    return [a for a in anchors_for(as_of) if apply_week(a, by=by)["written"]]


def sync_current_week(by: str | None = None) -> list[str]:
    """Móc gọi khi HỢP ĐỒNG BÁN đổi (thêm/sửa/xoá đợt giao) — chỉ tính lại TUẦN ĐANG CHẠY.

    Phần "đã có HĐ" suy từ hợp đồng nên một đợt giao mới về lý thuyết đụng mọi tuần từ ngày ký trở
    đi; tính lại hết mỗi lần lưu thì quá nặng và cũng vô ích (tuần cũ đã chốt). Tuần đang chạy giữ
    cho số mới nhất luôn đúng; muốn dựng lại tuần cũ thì bấm "Tính lại N tuần" ở màn Tồn kho.
    """
    if not enabled():
        return []
    a = last_anchor().isoformat()
    return [a] if apply_week(a, by=by)["written"] else []


def recompute(weeks: int = DEFAULT_RECOMPUTE_WEEKS, *, force: bool = False,
              by: str | None = None) -> dict[str, Any]:
    """Tính lại N tuần gần nhất (bật công tắc chỉ ăn từ lần đơn vị nộp SAU đó → nút lấy số đã có).

    Mặc định vẫn KHÔNG đè tuần nhập tay; `force=True` chỉ dùng khi chuyên viên chủ động chọn.
    """
    weeks = max(1, min(int(weeks), MAX_RECOMPUTE_WEEKS))
    anchor = last_anchor()
    written: list[str] = []
    kept_manual: list[str] = []
    empty: list[str] = []
    for i in range(weeks):
        d = (anchor - timedelta(days=7 * i)).isoformat()
        res = apply_week(d, force=force, by=by)
        (written if res["written"] else
         kept_manual if res["reason"] == "manual" else empty).append(d)
    return {"weeks": weeks, "written": written, "kept_manual": kept_manual, "no_data": empty}


# ── Job định kỳ tối thứ Sáu (+ chạy bù sau khi khởi động lại) ──────────────────
def run_weekly_job() -> dict[str, Any]:
    """Chốt tồn kho tuần theo lịch. Trả shape giống job quét giá để trang Lịch chạy dùng chung.

    LUÔN ghi 1 dòng `meta_crawl_run` (kể cả khi công tắc đang tắt): trang Lịch chạy lấy dòng này
    làm mốc "đã chạy", và cơ chế chạy bù cũng so theo nó — không ghi thì mỗi lần khởi động lại đều
    tưởng là còn nợ và chạy lại.
    """
    from app.services import price_repo

    run_id = price_repo.create_run(WEEKLY_JOB_SOURCE)
    if not enabled():
        note = "Tự tính tồn kho đang TẮT — không ghi tuần nào."
        price_repo.finish_run(run_id, "empty", 0, None)
        return _job_result(run_id, "empty", 0, note)
    try:
        res = recompute(WEEKLY_JOB_WEEKS, by=WEEKLY_JOB_NAME)
    except Exception as exc:                       # noqa: BLE001 - lỗi phải hiện ở trang Lịch chạy
        price_repo.finish_run(run_id, "error", 0, str(exc))
        return _job_result(run_id, "error", 0, str(exc))
    written = len(res["written"])
    note = (f"Đã ghi {written} tuần; giữ nguyên {len(res['kept_manual'])} tuần nhập tay, "
            f"{len(res['no_data'])} tuần chưa có số của đơn vị.")
    price_repo.finish_run(run_id, "ok" if written else "empty", written, None)
    return _job_result(run_id, "ok" if written else "empty", written, note)


def _job_result(run_id: int, status: str, rows: int, note: str) -> dict[str, Any]:
    """Khuôn kết quả job — giữ đúng shape của `scan_service` để UI Lịch chạy khỏi rẽ nhánh."""
    return {"records": [], "persisted": rows, "run_id": run_id,
            "sources": [{"source": WEEKLY_JOB_SOURCE, "status": status, "count": rows,
                         "note": note}]}
