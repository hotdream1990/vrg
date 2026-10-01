"""Job "Gửi cảnh báo bất thường cho đơn vị" — chạy HẰNG NGÀY ngay sau giờ chốt nhập liệu.

Màn Cảnh báo bất thường chỉ để XEM; job này đẩy chính các cảnh báo đó tới từng đơn vị qua hộp thư
Hỗ trợ & Thông báo (kèm email cho lãnh đạo đơn vị), để đơn vị biết ngay sau giờ chốt mình còn thiếu
hay nhập sai gì, thay vì chờ Ban gọi điện.

Luật (chốt 24/09/2026):
- Ngày VỪA hết hạn d0 = ngày số liệu có hạn nhập đúng bằng giờ chốt vừa qua (d0 = ngày chạy − N,
  N = cửa sổ nhập của đơn vị). Quét từ 01/01 năm của d0 tới d0 — mọi mục nêu ra đều ĐÃ quá hạn,
  không nhắc oan ngày đơn vị còn được nhập; link trong tin mở trang đúng khoảng này.
- Cùng bộ luật + ngưỡng với trang (`routers.anomalies.scan_range`), thu hẹp theo từng đơn vị như
  màn lãnh đạo đơn vị (`anomaly_scope.for_units` + đơn vị đã sáp nhập vào) — bỏ luật tính trên số
  gộp toàn Tập đoàn.
- MỖI đơn vị có cảnh báo = MỘT luồng riêng (giữ cách ly); mọi luồng cùng ngày chạy chung
  `batch_id` = `alert-<ngày chạy>` — cũng chính là dấu chống gửi trùng khi chạy lại trong ngày.
- Có luật quét LỖI (cờ `anomaly_rules.ERROR_FLAG`) → HUỶ cả đợt, không mở luồng nào: gửi thiếu
  hoặc gửi sai (đọc "đã nộp" lỗi ⇒ mọi đơn vị hoá ra "chưa nộp") rồi thì chạy lại trong ngày cũng
  không thay được. Lượt chạy ghi `error` kèm tên luật; batch chưa bị chiếm nên "Chạy ngay" gửi lại.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import text

from app.core import edit_window
from app.core.db import ensure_schema, session_scope
from app.core.entry_types import DEFAULT_AUDIENCE
from app.services import (
    anomaly_scope, mailer, member_unit_merge, member_unit_repo, price_repo, support_notify,
    support_repo, user_repo,
)
from app.services.anomaly_notify_content import PAGE_NAME, AlertContext, compose
from app.services.anomaly_rules import ERROR_FLAG

logger = logging.getLogger("vrg.anomaly_notify")

JOB_NAME = "anomaly-notify"
#: Ghi vào `meta_crawl_run.sources` → trang Lịch chạy hiện lần chạy gần nhất + cơ chế chạy bù.
JOB_SOURCE = "anomaly-notify"
#: 12:00 hằng ngày — chủ dự án chốt 24/09/2026: chừa một giờ sau giờ chốt 11:00 rồi mới gửi. Đổi giờ
#: chốt thì chỉnh giờ job ở trang Lịch chạy (chạy trước giờ chốt cũng không sai: job tự lấy giờ chốt
#: GẦN NHẤT ĐÃ QUA làm mốc).
JOB_DEFAULT = (12, 0, None)
AUTHOR = "system"
AUTHOR_NAME = "Hệ thống VRG (tự động)"
#: Cảnh báo tự động chỉ gửi LÃNH ĐẠO đơn vị (như trước khi có nhóm người nhận — chốt 01/10/2026).
AUDIENCE = DEFAULT_AUDIENCE
SENDER_LABEL = "Hệ thống cảnh báo tự động (sau giờ chốt nhập liệu)"
BATCH_PREFIX = "alert-"
_NAMES_IN_NOTE = 5
BROKEN_NOTE = "bỏ qua do lỗi dựng nội dung"


def alert_window(ref: datetime | None = None) -> tuple[date, date, datetime]:
    """(ngày chạy, d0, giờ chốt vừa qua) tại thời điểm `ref` (mặc định: bây giờ).

    d0 = ngày ngay trước ngày cũ nhất còn nhập được — tức ngày có hạn là giờ chốt gần nhất đã qua.
    Chạy trước giờ chốt hôm nay (chạy bù buổi sáng) thì mốc là giờ chốt HÔM QUA.
    """
    window = edit_window.member_window()
    d0 = edit_window.editable_from(window, ref or edit_window.now()) - timedelta(days=1)
    return d0 + timedelta(days=window), d0, edit_window.deadline(d0, window)


def _scan_per_unit(date_from: str, date_to: str) -> tuple[dict[str, dict], list[str]]:
    """Quét MỘT lần rồi thu hẹp theo từng đơn vị đang hoạt động → ({đơn vị: kết quả}, luật lỗi)."""
    from app.routers.anomalies import scan_range   # đúng hàm trang dùng (cùng ngưỡng cấu hình)

    full = scan_range(date_from, date_to)
    failed = [g["label"] for g in full["groups"] if g.get(ERROR_FLAG)]
    out = {}
    for u in member_unit_repo.list_units(include_inactive=False):
        if u.get("merged_into"):
            continue   # đơn vị đã sáp nhập không nhận riêng — cảnh báo của nó quy về đơn vị nhận
        name = u["name"]
        out[name] = anomaly_scope.for_units(full, member_unit_merge.expand([name]) or [name])
    return out, failed


def build_messages(ref: datetime | None = None) -> dict[str, Any]:
    """Dựng nội dung cho mọi đơn vị có cảnh báo — KHÔNG ghi DB (job dùng, và để in mẫu kiểm tra)."""
    run_day, d0, deadline = alert_window(ref)
    date_from, date_to = date(d0.year, 1, 1).isoformat(), d0.isoformat()
    per_unit, failed = _scan_per_unit(date_from, date_to)
    today = (ref or edit_window.now()).date()
    messages, broken = {}, []
    for unit, result in per_unit.items():
        try:
            msg = compose(AlertContext(unit, d0, deadline, today, date_from, date_to), result)
        except Exception:  # noqa: BLE001 - dòng lạ của 1 đơn vị không được chặn tin của cả đợt
            logger.exception("[cảnh báo tự động] dựng nội dung cho %s lỗi", unit)
            broken.append(unit)
            continue
        if msg:
            messages[unit] = msg
    return {"run_day": run_day, "d0": d0, "deadline": deadline, "date_from": date_from,
            "date_to": date_to, "units": len(per_unit), "failed_rules": failed,
            "compose_failed": broken, "messages": messages}


def _create(batch: str, messages: dict[str, dict]) -> tuple[list[tuple[int, str]], list[str]]:
    """Mở luồng cho đơn vị CHƯA nhận trong đợt `batch` → ([(id luồng, đơn vị)], [đơn vị bỏ qua])."""
    ensure_schema()
    with session_scope() as db:
        # Khoá theo đợt: chạy bù và bấm "Chạy ngay" trùng lúc thì lượt sau chờ lượt trước ghi xong
        # rồi mới đọc danh sách đã nhận — không có kẽ hở để hai lượt cùng mở luồng cho một đơn vị.
        db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:k))"), {"k": batch})
        done = set(db.execute(
            text("SELECT company FROM support_thread WHERE kind = :k AND batch_id = :b"),
            {"k": support_repo.KIND_ALERT, "b": batch}).scalars())
        created = [
            (support_repo.insert_thread(db, unit, support_repo.KIND_ALERT, msg["subject"],
                                        msg["body"], None, AUTHOR, AUTHOR_NAME, support_repo.HQ,
                                        batch, audience=AUDIENCE), unit)
            for unit, msg in messages.items() if unit not in done]
    return created, sorted(u for u in messages if u in done)


def _email(created: list[tuple[int, str]], messages: dict[str, dict]) -> None:
    """Email cho lãnh đạo từng đơn vị (bản tóm tắt + link tuyệt đối) — gửi TUẦN TỰ cả đợt trong
    một luồng nền (`support_notify.send_batch`) — kèm Web Push (không phụ thuộc SMTP). Lỗi mail /
    push không làm hỏng job: tin đã lưu."""
    base = mailer.base_url()
    users = user_repo.list_users()
    mails, pushes = [], []
    for tid, unit in created:
        msg = messages[unit]
        pushes.append(support_notify.unit_push(tid, unit, msg["subject"], "", audience=AUDIENCE,
                                               title=support_notify.PUSH_ALERT, users=users))
        extra = (f"Xem chi tiết tại {PAGE_NAME}: {base}{msg['link']}" if base else
                 f"Xem chi tiết: đăng nhập hệ thống VRG, vào mục {PAGE_NAME}.")
        try:
            mail = support_notify.unit_email(tid, unit, msg["subject"], msg["email"],
                                             SENDER_LABEL, extra, AUDIENCE, users)
        except Exception:  # noqa: BLE001 - tin đã lưu; email chỉ là kênh báo thêm
            logger.exception("[cảnh báo tự động] dựng email cho %s lỗi", unit)
            continue
        if mail:
            mails.append((unit, mail))
    support_notify.push_batch(pushes)   # cả đợt: một luồng nền, một kết nối
    support_notify.send_batch(mails)


def _units_with_leader() -> set[str]:
    return {c for u in user_repo.list_users()
            if u.get("role") == "leader" and u.get("is_active", True)
            for c in (u.get("member_units") or [])}


def _names(units: list[str]) -> str:
    more = len(units) - _NAMES_IN_NOTE
    return ", ".join(units[:_NAMES_IN_NOTE]) + (f" và {more} đơn vị khác" if more > 0 else "")


def send_alerts(ref: datetime | None = None) -> dict[str, Any]:
    """Quét → mở luồng cho đơn vị có cảnh báo (chưa nhận hôm nay) → email. Trả tóm tắt JSON được.

    Luật quét lỗi → `aborted`: không mở luồng, không email, batch để trống cho lần chạy lại."""
    built = build_messages(ref)
    broken = built["compose_failed"]
    res = {"batch_id": BATCH_PREFIX + built["run_day"].isoformat(), "d0": built["d0"].isoformat(),
           "date_from": built["date_from"], "date_to": built["date_to"],
           "failed_rules": built["failed_rules"], "compose_failed": broken,
           "aborted": bool(built["failed_rules"]), "created": [], "thread_ids": [], "skipped": [],
           "no_leader": [], "clean": 0}
    if res["aborted"]:
        return {**res, "note": f"HUỶ đợt gửi — luật quét bị lỗi (xem log): "
                               f"{', '.join(built['failed_rules'])}. Không mở luồng nào; khắc phục "
                               "rồi bấm \"Chạy ngay\" để gửi lại."}
    messages = built["messages"]
    created, skipped = _create(res["batch_id"], messages)
    _email(created, messages)
    leaders = _units_with_leader()
    no_leader = sorted(u for _, u in created if u not in leaders)
    clean = built["units"] - len(messages) - len(broken)
    parts = [f"Mốc {built['deadline']:%H:%M %d/%m/%Y} (hết hạn số liệu ngày {built['d0']:%d/%m/%Y}): "
             f"gửi {len(created)} đơn vị"]
    if skipped:
        parts.append(f"{len(skipped)} đơn vị đã nhận trong ngày nên bỏ qua")
    if no_leader:
        parts.append(f"{len(no_leader)} đơn vị chưa có tài khoản lãnh đạo (tin chỉ lưu trên hệ "
                     f"thống): {_names(no_leader)}")
    parts.append(f"{clean} đơn vị không có cảnh báo")
    if broken:
        parts.append(f"{BROKEN_NOTE} {len(broken)} đơn vị (xem log): {_names(broken)}")
    return {**res, "created": [u for _, u in created], "thread_ids": [t for t, _ in created],
            "skipped": skipped, "no_leader": no_leader, "clean": clean,
            "note": "; ".join(parts) + "."}


def run_job() -> dict[str, Any]:
    """Hàm job của scheduler — LUÔN ghi 1 dòng `meta_crawl_run` (mốc "đã chạy" + chạy bù).

    `error` = huỷ đợt (luật quét lỗi) · `warning` = đã gửi nhưng bỏ qua đơn vị dựng tin lỗi."""
    run_id = price_repo.create_run(JOB_SOURCE)
    try:
        res = send_alerts()
    except Exception as exc:  # noqa: BLE001 - lỗi phải hiện ở trang Lịch chạy, không làm chết scheduler
        logger.exception("[cảnh báo tự động] lỗi")
        price_repo.finish_run(run_id, "error", 0, str(exc))
        return _job_result(run_id, "error", 0, f"Lỗi khi gửi cảnh báo: {exc}")
    n = len(res["created"])
    status = ("error" if res["aborted"] else "warning" if res["compose_failed"] else
              "ok" if n else "empty")
    price_repo.finish_run(run_id, status, n, res["note"] if status in ("error", "warning") else None)
    return {**_job_result(run_id, status, n, res["note"]), "alerts": res}


def _job_result(run_id: int, status: str, rows: int, note: str) -> dict[str, Any]:
    """Khuôn kết quả giống `scan_service` để trang Lịch chạy hiện `note` sau khi bấm Chạy ngay."""
    return {"records": [], "persisted": rows, "run_id": run_id,
            "sources": [{"source": JOB_SOURCE, "status": status, "count": rows, "note": note}]}
