"""Tách ô chữ Nhu cầu thị trường CŨ thành các phiếu có trường (hàm thuần, không đụng DB).

Dữ liệu cũ (34 bản ghi / 6 đơn vị, 23/07 → 17/09/2026) viết theo vài MẪU CÂU cố định của từng đơn
vị — nhận ra được mẫu thì tách tự động; mục viết tự do thì lấy từ `legacy_manual.MANUAL` (soạn tay
sau khi đọc từng câu). Không khớp cả hai ⇒ báo lỗi, không đoán.

Nguyên tắc: KHÔNG bịa số liệu. Câu nào không nói rõ (không có số lượng, không có giá, thời gian ghi
bằng chữ) thì để trống ô đó và ghi lại trong Ghi chú; nguyên văn cũ luôn được giữ ở cuối Ghi chú.
"""
from __future__ import annotations

import calendar
import re
from datetime import date

NUM = r"[\d.,]+"

#: Tên chủng loại đơn vị hay viết → tên trong danh mục `UNIT_GRADES`.
GRADE_ALIASES = {
    "latex": "LATEX", "ha": "LATEX",
    "svr3l": "SVR 3L", "svr 3l": "SVR 3L", "3l": "SVR 3L",
    "svr10": "SVR 10 / CSR 10", "svr 10": "SVR 10 / CSR 10", "csr 10": "SVR 10 / CSR 10",
    "svr cv60": "SVR CV60", "cv60": "SVR CV60", "svr cv50": "SVR CV 50",
    "skim": "Skim Block", "csr ngoại lệ": "Mủ ngoại lệ",
}

#: Mẫu câu theo đơn vị (khớp cả mục; nhóm tên = trường). Thứ tự không quan trọng.
PATTERNS = [
    # Tây Ninh: "Công ty X hỏi mua N tấn G, giá mua P triệu đồng/tấn, hàng giao tại Y, thời gian
    # giao hàng T. Kết quả: đã ký HĐMB số ... ngày ..."
    re.compile(
        rf"^(?P<customer>Công ty .+?)\s+hỏi mua (?P<more>thêm )?(?P<qty>{NUM}) tấn (?P<grade>[^,]+?)\s*,"
        rf"\s*giá mua (?P<price>{NUM}) (?P<cur>triệu đồng|usd)/tấn\s*(?P<addon>của HĐ [^,]+)?\s*,"
        rf"\s*hàng giao tại (?P<place>[^,]+),\s*thời gian giao hàng (?P<time>[^.]+?)\.\s*"
        rf"Kết quả\s*:\s*(?P<result>.+?)\.?\s*$", re.I | re.S),
    # Tây Ninh Siêm Riệp: "Công ty X yêu cầu/đề nghị mua N Tấn mủ G, đơn giá: P usd/tấn. Giao hàng
    # tại Y [ngày D]"
    re.compile(
        rf"^(?P<customer>Công ty .+?)\s+(?:yêu cầu|đề nghị) mua (?P<qty>{NUM}) Tấn mủ (?P<grade>[^,]+),"
        rf"\s*đơn giá:\s*(?P<price>{NUM}) (?P<cur>usd)/tấn\.\s*Giao hàng tại (?P<place>.+?)"
        rf"(?: ngày (?P<time>[\d/]+))?\s*[.;]?\s*$", re.I | re.S),
    # Dầu Tiếng: "Công ty X hỏi mua N tấn G, giá P USD/tấn[, FCA …], giao hàng tháng M/YYYY"
    re.compile(
        rf"^(?:Khách hàng )?(?P<customer>.+?) hỏi mua (?P<qty>{NUM}) tấn (?P<grade>[^,]+),"
        rf"\s*giá (?P<price>{NUM}) (?P<cur>USD|đồng)/tấn(?:,\s*(?P<place>FCA[^,]+))?,"
        rf"\s*giao hàng (?P<time>.+?)\.?\s*$", re.I | re.S),
    # Lai Châu: "X hỏi mua hàng với khối lượng N tấn, với giá giao tại Y là P đồng/ tấn"
    re.compile(
        rf"^(?P<customer>.+?) hỏi mua hàng với khối lượng (?P<qty>{NUM}) tấn,"
        rf"\s*với giá giao tại (?P<place>.+?) là (?P<price>{NUM}) (?P<cur>đồng)/\s*tấn\s*$", re.I | re.S),
    # Đồng Phú (HA): "Công ty X cần mua N Tấn G giao Y, thời gian Tháng M"
    re.compile(
        rf"^(?P<customer>Công ty .+?) cần mua (?P<qty>{NUM}) Tấn (?P<grade>\w+) giao (?P<place>.+?),"
        rf"\s*thời gian (?P<time>.+?)\s*$", re.I | re.S),
]

_RESULT = re.compile(r"đã ký (?P<kind>HĐMB|HĐ uỷ thác XK|Phụ kiện) số (?P<no>\S+) ngày "
                     r"(?P<d>\d{1,2}/\d{1,2}/\d{4})", re.I)
_RESULT_NOTE = {"hđ uỷ thác xk": "Hợp đồng uỷ thác xuất khẩu", "phụ kiện": "Phụ kiện hợp đồng"}


def split_items(text: str) -> list[str]:
    """Ô chữ → các mục (đánh số "1/", "1." ở đầu dòng hoặc giữa câu)."""
    parts = re.split(r"(?:^|\s)(?=\d{1,2}\s*[/.]\s+(?:Công ty|Khách hàng|[A-Z]))", text.strip())
    items = [re.sub(r"^\d{1,2}\s*[/.]\s+", "", p).strip() for p in parts if p.strip()]
    return items or [text.strip()]


def vn_number(raw: str) -> float:
    """Số kiểu Việt Nam → float: '2.146,13' · '137,8' · '54.800.000' · '2.380' · '1560'."""
    s = raw.strip().rstrip(".,")
    if "," in s:
        return float(s.replace(".", "").replace(",", "."))
    if re.fullmatch(r"\d{1,3}(\.\d{3})+", s):
        return float(s.replace(".", ""))
    return float(s)


def _dmy(raw: str, year: int | None = None) -> date:
    d, m, *y = [int(x) for x in raw.split("/")]
    return date(y[0] if y else year, m, d)


def _month_span(m1: int, m2: int, year: int) -> tuple[date, date]:
    return date(year, m1, 1), date(year, m2, calendar.monthrange(year, m2)[1])


def delivery_span(raw: str | None, as_of: date) -> tuple[date | None, date | None]:
    """Thời gian giao ghi bằng chữ → (từ ngày, đến ngày). Không hiểu thì (None, None)."""
    t = (raw or "").strip().lower()
    if not t:
        return None, None
    if m := re.fullmatch(r"đến (\d{1,2}/\d{1,2}/\d{4})", t):
        return None, _dmy(m[1])
    if m := re.fullmatch(r"t(\d{1,2})\+(\d{1,2})/(\d{4})", t):
        return _month_span(int(m[1]), int(m[2]), int(m[3]))
    if m := re.fullmatch(r"tháng (\d{1,2})(?:/(\d{4}))?", t):
        return _month_span(int(m[1]), int(m[1]), int(m[2] or as_of.year))
    if re.fullmatch(r"\d{1,2}/\d{1,2}(/\d{4})?", t):
        d = _dmy(t, as_of.year)
        return d, d
    return None, None


def normalize_grade(raw: str) -> tuple[str, str]:
    """(tên trong danh mục, ghi chú kèm) — HA là latex amoniac cao, ghi lại cho khỏi mất nghĩa."""
    key = re.sub(r"\s+", " ", raw.strip().lower())
    if key not in GRADE_ALIASES:
        raise ValueError(f"Chủng loại chưa có trong bảng quy đổi: {raw!r}")
    return GRADE_ALIASES[key], "Latex HA" if key == "ha" else ""


def normalize_place(raw: str | None) -> str:
    p = re.sub(r"\s+", " ", (raw or "").strip())
    if p.lower() == "kho":
        return "Tại kho"
    p = re.sub(r"(?i)cảng TPHCM", "cảng TP.HCM", p)
    return p[:1].upper() + p[1:]


def auto_item(fragment: str, as_of: date) -> dict | None:
    """Một mục chữ → phiếu (dict theo DemandItemIn, chưa có company). None = không khớp mẫu nào."""
    m = next((m for p in PATTERNS if (m := p.search(fragment))), None)
    if not m:
        return None
    g = m.groupdict()
    grade, grade_note = normalize_grade(g.get("grade") or "HA")
    price = vn_number(g["price"]) if g.get("price") else None
    cur = "USD" if (g.get("cur") or "").lower() == "usd" else "VND"
    if cur == "VND" and price and price > 1000:
        price = price / 1_000_000                     # "54.800.000 đồng/tấn" → 54,8 triệu
    frm, to = delivery_span(g.get("time"), as_of)
    notes = [grade_note] if grade_note else []
    if g.get("addon"):
        notes.append(f"Mua thêm cho {g['addon'].strip()}")
    item = {
        "as_of": as_of.isoformat(), "customer": re.sub(r"^Khách hàng\s+", "", g["customer"].strip()),
        "grade": grade, "qty": vn_number(g["qty"]), "qty_unit": "ton",
        "price": price, "currency": cur, "price_provisional": False,
        "delivery_place": normalize_place(g.get("place")),
        "delivery_from": frm and frm.isoformat(), "delivery_to": to and to.isoformat(),
        "status": "open", "contract_no": "", "contract_date": None,
    }
    if g.get("result"):
        r = _RESULT.search(g["result"])
        if not r:
            raise ValueError(f"Không đọc được kết quả: {g['result']!r}")
        item.update(status="signed", contract_no=r["no"], contract_date=_dmy(r["d"]).isoformat())
        if extra := _RESULT_NOTE.get(r["kind"].lower()):
            notes.append(extra)
    item["extra_note"] = " · ".join(notes)
    return item
