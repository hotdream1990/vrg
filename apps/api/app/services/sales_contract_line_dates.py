"""NGÀY HIỆU LỰC theo dòng chủng loại của HỢP ĐỒNG (chốt 30/09/2026) — các luật kiểm tra.

Hợp đồng ký 10 tấn ngày 10, ngày 15 thêm 6 tấn: đơn vị thêm DÒNG MỚI 6 tấn hiệu lực từ 15 ⇒ "đã ký
HĐ chưa giao" 10–14 là 10 tấn, từ 15 là 16 tấn (không khai ngày thì 16 tấn tính ngược về tận ngày
ký). Giảm thì sửa thẳng số của dòng — không có dòng âm (chủ dự án chọn). Phép tính nằm ở
`sales_contract_report._BLOCK3_SQL`; file này giữ các luật để ngày của dòng không mâu thuẫn với các
mốc khác của hợp đồng: ngày ký · ngày giao · các đợt giao · ngày hoàn thành.
"""

from __future__ import annotations

from datetime import date
from typing import Any


def _dmy(d: date | str) -> str:
    s = d.isoformat() if isinstance(d, date) else str(d)[:10]
    return f"{s[8:10]}/{s[5:7]}/{s[:4]}"


def parse(ln: dict, where: str, sign_date: date | None, delivered_at: date | None) -> str | None:
    """Ngày hiệu lực của một dòng (YYYY-MM-DD) hoặc None = theo ngày ký. Raise ValueError nếu sai.

    Trùng ngày ký vẫn GIỮ nguyên, không quy về trống: sửa nhầm ngày ký rồi sửa lại (10 → 15 → 10)
    không được làm dòng "từ 15" lặng lẽ thành "từ 10" — tức là cộng ngược phần tăng vào 10–14.
    """
    s = str(ln.get("from_date") or "").strip()[:10]
    if not s:
        return None
    try:
        d = date.fromisoformat(s)
    except ValueError as exc:
        raise ValueError(f"{where}: ngày hiệu lực không hợp lệ (YYYY-MM-DD).") from exc
    if sign_date and d < sign_date:
        raise ValueError(f"{where}: ngày hiệu lực {_dmy(d)} trước ngày ký hợp đồng "
                         f"{_dmy(sign_date)} — chỉ được từ ngày ký trở đi.")
    # Hợp đồng giao 1 lần: lần giao gồm MỌI dòng, dòng hiệu lực sau ngày giao là hàng được giao
    # trước khi có trong hợp đồng.
    if delivered_at and d > delivered_at:
        raise ValueError(f"{where}: ngày hiệu lực {_dmy(d)} sau ngày giao {_dmy(delivered_at)} — "
                         "hàng đã giao thì dòng phải có hiệu lực từ ngày giao trở về trước.")
    return d.isoformat()


def grade_starts(lines: list[dict[str, Any]] | None, sign_date: str | None) -> dict[str, str]:
    """{chủng loại: ngày SỚM NHẤT có dòng hiệu lực} của một hợp đồng — dòng không ngày = ngày ký."""
    out: dict[str, str] = {}
    for ln in lines or []:
        g = ln.get("grade") or ""
        d = str(ln.get("from_date") or "")[:10] or str(sign_date or "")[:10]
        if g and (g not in out or d < out[g]):
            out[g] = d
    return out


def latest_start(lines: list[dict[str, Any]] | None) -> str | None:
    """Ngày hiệu lực muộn nhất của các dòng có khai ngày riêng — None nếu mọi dòng theo ngày ký."""
    days = [str(ln.get("from_date"))[:10] for ln in lines or [] if ln.get("from_date")]
    return max(days) if days else None


def assert_batch_not_before_grade(starts: dict[str, str], delivered_at: str | None,
                                  lines: list[dict[str, Any]] | None, what: str) -> None:
    """Lần giao có chủng loại mà MỌI dòng chủng loại đó trên hợp đồng chưa hiệu lực vào ngày giao.

    Chỉ xét chủng loại CÓ trên hợp đồng: giao chủng loại không có trên hợp đồng là chuyện đã có từ
    trước, khối 3 trừ vào tổng (`spill`). Còn chủng loại thêm sau mà ngày hiệu lực muộn hơn ngày
    giao thì những ngày ở giữa bị tính như giao nhầm chủng loại — tổng vẫn đúng nhưng phần tách theo
    chủng loại ghi sai tên (rà soát 30/09/2026: SVR 3L giao 12/09, dòng SVR 3L hiệu lực 15/09 ⇒ ngày
    12–14 báo "SVR 10 còn 4 tấn" trong khi SVR 10 chưa giao tấn nào).
    """
    if not delivered_at:
        return
    day = str(delivered_at)[:10]
    for ln in lines or []:
        g = ln.get("grade") or ""
        start = starts.get(g)
        if start and day < start:
            raise ValueError(
                f"{what} ngày {_dmy(day)} có {g} nhưng dòng {g} của hợp đồng hiệu lực từ "
                f"{_dmy(start)} — sửa ngày hiệu lực của dòng trên hợp đồng (không sau ngày giao) "
                "hoặc sửa ngày giao.")
