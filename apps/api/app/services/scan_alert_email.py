"""Email cảnh báo sau lượt quét giá THEO LỊCH — tỷ giá quá cũ / nguồn lỗi / ghi DB hỏng.

- Chỉ gửi khi đã khai `SYSTEM_ALERT_EMAILS` (CSV) VÀ SMTP (tab Email). Bỏ trống = tắt.
- Chống spam: cùng một TẬP vấn đề chỉ gửi 1 lần/ngày (giờ VN). Dấu vết lưu ở khoá nội bộ
  `SYSTEM_ALERT_LAST` = {"date": "YYYY-MM-DD", "sent": [chữ ký…]} — không khai trên UI.
- Không bao giờ làm hỏng lượt quét: mọi lỗi chỉ ghi log. Gửi thất bại thì KHÔNG đánh dấu đã gửi
  → lượt quét sau thử lại.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from collections.abc import Callable
from datetime import date, datetime
from typing import Any

from app.services import fx_freshness, mailer, scan_run_summary

logger = logging.getLogger("vrg.scan_alert")

RECIPIENTS_KEY = "SYSTEM_ALERT_EMAILS"
LAST_KEY = "SYSTEM_ALERT_LAST"

SendFn = Callable[[list[str], str, str], tuple[bool, str]]


def parse_recipients(raw: str | None) -> list[str]:
    """CSV (phẩy/chấm phẩy/xuống dòng) → địa chỉ hợp lệ, bỏ trùng, giữ thứ tự."""
    out: list[str] = []
    for part in re.split(r"[,;\s]+", raw or ""):
        addr = mailer.normalize(part)
        if addr and addr not in out:
            out.append(addr)
    return out


def issue_keys(result: dict[str, Any]) -> list[str]:
    """Danh tính ỔN ĐỊNH của từng vấn đề (không chứa giờ/số đếm) để so "cùng một tập vấn đề"."""
    keys: list[str] = []
    for src in result.get("sources") or []:
        if scan_run_summary.source_warning(src):
            # Chữ số trong ghi chú (ngày phiên, mã lỗi, ms…) đổi theo lượt → bỏ khỏi chữ ký.
            note = re.sub(r"\d+", "#", str(src.get("note") or ""))
            keys.append(f"src:{src.get('source')}:{src.get('status')}:{note}")
    for s in result.get("stale_fx") or []:
        keys.append(f"stale:{s.get('pair')}:{s.get('latest')}")
    db = str(result.get("db") or "ok")
    if db != "ok":
        keys.append(f"db:{db}")
    return sorted(set(keys))


def signature(keys: list[str]) -> str:
    return hashlib.sha256("|".join(keys).encode("utf-8")).hexdigest()[:16]


def _load_last(raw: str | None) -> dict[str, Any]:
    try:
        data = json.loads(raw or "")
    except (TypeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def already_sent(raw_last: str | None, sig: str, today: date) -> bool:
    last = _load_last(raw_last)
    return last.get("date") == today.isoformat() and sig in (last.get("sent") or [])


def mark_sent(raw_last: str | None, sig: str, today: date) -> str:
    """Thêm chữ ký vào danh sách hôm nay; sang ngày mới thì làm lại từ đầu."""
    last = _load_last(raw_last)
    sent = list(last.get("sent") or []) if last.get("date") == today.isoformat() else []
    if sig not in sent:
        sent.append(sig)
    return json.dumps({"date": today.isoformat(), "sent": sent})


def compose(result: dict[str, Any], now: datetime) -> tuple[str, str]:
    """(tiêu đề, nội dung) email tiếng Việt, văn bản thuần."""
    stale = result.get("stale_fx") or []
    warnings = list(result.get("warnings") or [])
    if str(result.get("db") or "ok") != "ok":
        warnings.append(f"Không ghi được kho giá ({result.get('db')})")
    topic = "tỷ giá quá cũ" if stale else "nguồn quét lỗi"
    subject = f"[VRG] Cảnh báo quét giá: {topic} ({now:%d/%m/%Y})"
    run = f" (lượt #{result['run_id']})" if result.get("run_id") else ""
    lines = [f"Lượt quét giá theo lịch lúc {now:%H:%M %d/%m/%Y}{run} phát hiện vấn đề:", ""]
    lines += [f"- {w}" for w in warnings]
    if stale:
        lines += ["", f"Ảnh hưởng: {fx_freshness.describe(stale)} — bản tin/báo cáo không quy đổi "
                      "được sang USD cho các sàn dùng tỷ giá này."]
    base = mailer.base_url()
    lines += ["", "Kiểm tra: trang Quét đa sàn → Nhật ký quét giá"
              + (f" ({base}/quet-da-san)." if base else "."),
              "", "Email tự động — cùng một tập vấn đề chỉ gửi 1 lần mỗi ngày."]
    return subject, "\n".join(lines)


def notify(result: dict[str, Any], *, send: SendFn | None = None,
           now: datetime | None = None) -> str:
    """Gửi email tóm tắt nếu lượt quét có vấn đề. Trả mã kết quả (để log/test) — KHÔNG ném lỗi."""
    from app.services import config_repo

    try:
        keys = issue_keys(result)
        if not keys:
            return "clean"
        recipients = parse_recipients(config_repo.get_value(RECIPIENTS_KEY))
        if not recipients:
            return "no_recipients"
        if send is None:
            if not mailer.is_configured():
                return "smtp_off"
            send = mailer.send
        moment = now or fx_freshness.now_vn()
        sig = signature(keys)
        raw_last = config_repo.get_value(LAST_KEY)
        if already_sent(raw_last, sig, moment.date()):
            return "duplicate"
        subject, body = compose(result, moment)
        ok, err = send(recipients, subject, body)
        if not ok:
            logger.warning("[scan-alert] gửi email thất bại: %s", err)
            return "send_failed"
        config_repo.set_value(LAST_KEY, mark_sent(raw_last, sig, moment.date()), by="system")
        return "sent"
    except Exception:  # noqa: BLE001 - cảnh báo hỏng không được làm hỏng lượt quét
        logger.warning("[scan-alert] lỗi khi xử lý cảnh báo", exc_info=True)
        return "error"
