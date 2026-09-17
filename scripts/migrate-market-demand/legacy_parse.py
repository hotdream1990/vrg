"""Tách ô chữ Nhu cầu thị trường CŨ thành các phiếu có trường (hàm thuần, không đụng DB).

Dữ liệu cũ (34 bản ghi / 6 đơn vị, 23/07 → 17/09/2026) viết theo vài MẪU CÂU cố định của từng đơn
vị — nhận ra được mẫu thì tách tự động; mục viết tự do thì lấy từ `legacy_manual.MANUAL` (soạn tay
sau khi đọc từng câu). Không khớp cả hai ⇒ báo lỗi, không đoán.

Nguyên tắc: KHÔNG bịa số liệu. Câu nào không nói rõ (không có số lượng, không có giá) thì để trống ô
đó; thời gian giao và kết quả là Ô CHỮ nên chép đúng lời đơn vị viết; nguyên văn cũ luôn được giữ ở
cuối Ghi chú.
"""
from __future__ import annotations

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


def delivery_text(raw: str | None, as_of: date) -> str:
    """Thời gian giao như đơn vị viết (viết hoa chữ đầu); ngày trơn ("14/8/2026", "31/7") viết đủ dd/mm/yyyy."""
    t = re.sub(r"\s+", " ", (raw or "").strip())
    if m := re.fullmatch(r"(\d{1,2})/(\d{1,2})(?:/(\d{4}))?", t):
        return date(int(m[3] or as_of.year), int(m[2]), int(m[1])).strftime("%d/%m/%Y")
    return t[:1].upper() + t[1:]


def sentence(raw: str | None) -> str:
    """Câu kết quả: gọn khoảng trắng, bỏ dấu chấm cuối, viết hoa chữ đầu."""
    t = re.sub(r"\s+", " ", (raw or "").strip()).rstrip(".").strip()
    return t[:1].upper() + t[1:]


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
    notes = [grade_note] if grade_note else []
    if g.get("addon"):
        notes.append(f"Mua thêm cho {g['addon'].strip()}")
    if g.get("result") and not g["result"].lower().lstrip().startswith("đã ký"):
        raise ValueError(f"Không đọc được kết quả: {g['result']!r}")
    return {
        "as_of": as_of.isoformat(), "customer": re.sub(r"^Khách hàng\s+", "", g["customer"].strip()),
        "grade": grade, "qty": vn_number(g["qty"]), "qty_unit": "ton",
        "price": price, "currency": cur,
        "delivery_place": normalize_place(g.get("place")),
        "delivery_time": delivery_text(g.get("time"), as_of),
        "result": sentence(g.get("result")),
        "extra_note": " · ".join(notes),
    }
