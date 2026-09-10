"""Tiện ích dùng chung cho các bộ công cụ Trợ lý AI.

Mỗi tool trả `{summary, artifact?, source?}`:
  - `summary`  dữ liệu gọn cho LLM đọc (KHÔNG bịa — số nào cũng từ DB),
  - `artifact` bảng/biểu đồ để frontend hiển thị,
  - `source`   câu trích nguồn hiện dưới câu trả lời.

Quy tắc BẮT BUỘC khi viết tool mới:
  1. Số nào cũng phải kèm ĐƠN VỊ trong nhãn hoặc trường riêng — không để LLM tự quy đổi.
  2. Giá 0 của sàn = phiên No Trading (dùng `is_no_trading`), không phải "giá bằng 0".
  3. Không lấy số liệu ngày khác đắp cho ngày được hỏi — thiếu thì nói thiếu.
"""
from __future__ import annotations

import sys

from app.core import edit_window
from app.core.paths import bulletin_dir

_BULLETIN = bulletin_dir()
if str(_BULLETIN) not in sys.path:
    sys.path.insert(0, str(_BULLETIN))

from bulletin.convert import NO_TRADING, is_no_trading  # noqa: E402,F401 - quy ước giá 0 dùng chung

#: JSON-schema rỗng cho tool không nhận tham số.
NO_ARGS = {"type": "object", "properties": {}}

#: Danh mục sàn quốc tế THẬT trong `fact_price.source` (mã crawler → tên hiển thị).
#: ⚠ Không có nguồn nào tên "ose": sàn Nhật lưu dưới mã `tocom`, "OSE" chỉ là nhãn hiển thị trên
#: bản tin (xem `market_meta.WORLD_GRADE_MAP`). Người dùng vẫn quen gọi "OSE" nên xem `SOURCE_ALIAS`.
EXCH = {"shfe": "SHFE (Thượng Hải)", "sgx": "SGX (Singapore)",
        "tocom": "OSE/TOCOM (Nhật)", "lgm": "MRB/LGM (Malaysia)"}

#: Tên người dùng hay gõ → mã nguồn thật. Thiếu bảng này thì hỏi "giá OSE" là tool trả rỗng.
SOURCE_ALIAS = {"ose": "tocom", "jpx": "tocom", "shanghai": "shfe", "mrb": "lgm",
                "mre": "lgm", "singapore": "sgx"}


def source_key(name: str) -> str:
    """Chuẩn hoá mã sàn người dùng/LLM đưa vào về đúng `fact_price.source`."""
    key = str(name or "").lower().strip()
    return SOURCE_ALIAS.get(key, key)


def table(title: str, columns: list[dict], rows: list[dict]) -> dict | None:
    """Artifact bảng. Không có dòng nào → None (đừng gửi bảng rỗng cho người dùng)."""
    return {"type": "table", "title": title, "columns": columns, "rows": rows} if rows else None


def line(title: str, labels: list[str], series: list[dict], y_label: str = "") -> dict | None:
    """Artifact biểu đồ đường."""
    return {"type": "line", "title": title, "labels": labels, "series": series,
            "y_label": y_label} if labels else None


def cols(*pairs: tuple[str, str]) -> list[dict]:
    """`cols(("grade", "Chủng loại"), ...)` → cột cho artifact bảng."""
    return [{"key": k, "label": lb} for k, lb in pairs]


def dm(iso: str) -> str:
    """`2026-09-10` → `10/09` (nhãn trục ngày)."""
    p = str(iso)[:10].split("-")
    return f"{p[2]}/{p[1]}" if len(p) == 3 else str(iso)


def dmy(iso: str | None) -> str:
    """`2026-09-10` → `10/09/2026`."""
    p = str(iso or "")[:10].split("-")
    return f"{p[2]}/{p[1]}/{p[0]}" if len(p) == 3 else str(iso or "—")


def today() -> str:
    return edit_window.today().isoformat()


def days_ago(n: int) -> str:
    from datetime import timedelta
    return (edit_window.today() - timedelta(days=int(n))).isoformat()


#: Trần khoảng tra cứu của một câu hỏi. Người dùng chat có thể bảo "so từ 2020 tới nay" và LLM sẽ
#: đặt đúng như vậy — mỗi lượt hỏi gọi tool tối đa 8 lần nên phải kẹp lại, đúng luật "cấm tải hết
#: dữ liệu" của dự án.
MAX_LOOKBACK_DAYS = 400


def clamp_days(days: int | None, default: int) -> int:
    """Số ngày tra cứu hợp lệ: >0 và không vượt trần."""
    try:
        n = int(days) if days else default
    except (TypeError, ValueError):
        n = default
    return max(1, min(n, MAX_LOOKBACK_DAYS))


def safe_date(value: str | None) -> str | None:
    """`'2026-09-10'` → chính nó; chuỗi hỏng → None.

    Vì sao cần: LLM tự dựng ngày từ câu nói ("từ Tết tới giờ", "quý vừa rồi") nên chuỗi hỏng là
    chuyện thường. Thả xuống SQL thì Postgres ném lỗi kèm NGUYÊN VĂN câu truy vấn — cả tên cột nội
    bộ lẫn comment nghiệp vụ — rồi lọt vào khung chat của người dùng.
    """
    from datetime import date
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10]).isoformat()
    except ValueError:
        return None


def clamp_from(date_from: str, date_to: str) -> str:
    """Kéo `date_from` lên nếu khoảng vượt trần (giữ nguyên `date_to` — người dùng quan tâm gần đây)."""
    from datetime import date, timedelta
    try:
        a, b = date.fromisoformat(date_from[:10]), date.fromisoformat(date_to[:10])
    except ValueError:
        return date_from
    floor = b - timedelta(days=MAX_LOOKBACK_DAYS)
    return max(a, floor).isoformat()


def err(message: str) -> dict:
    """Kết quả tool khi không có dữ liệu — LLM phải nói 'chưa có số liệu', không suy đoán."""
    return {"summary": {"error": message}}


def pct(new: float | None, old: float | None) -> float | None:
    """Thay đổi % (làm tròn 2 số). Thiếu vế nào hoặc mốc cũ = 0 → None."""
    if new is None or old in (None, 0):
        return None
    return round((float(new) - float(old)) / float(old) * 100, 2)


def num(v) -> float | None:  # noqa: ANN001 - nhận mọi kiểu từ jsonb
    try:
        return float(v) if v is not None and v != "" else None
    except (TypeError, ValueError):
        return None
