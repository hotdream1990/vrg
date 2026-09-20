"""Quy tắc & tiện ích DÙNG CHUNG cho các bảng thống kê (lọc · gộp nhóm · bình quân).

Quy tắc số liệu (giữ đúng như biểu mẫu & form nhập):
- Sản lượng, doanh thu: **cộng dồn**.
- Giá: **bình quân gia quyền theo sản lượng** (không phải trung bình cộng).
- Giá mủ nước/mủ chén tính theo **đồng/độ** (TSC hoặc DRC), giá thành phẩm & giá bán theo
  **triệu đ/tấn** — KHÔNG quy đổi chéo, mỗi loại một chỉ tiêu bình quân riêng.
- Dòng nhập USD mà thiếu tỷ giá → KHÔNG tính vào doanh thu/giá BQ và được **cảnh báo** (không đoán số).
"""

from __future__ import annotations

from typing import Any, Callable

from app.services import member_unit_merge, member_unit_repo, unit_daily_repo
from app.services.unit_report_rows import MATERIAL_LABELS, SOURCE_LABELS

#: Nhãn cho ô CHƯA KHAI — hiện rõ là thiếu dữ liệu, thay vì để chuỗi rỗng hay đoán bừa một loại.
UNKNOWN_LABEL = "(chưa khai)"
#: Đơn vị chưa gán khu vực — cùng một nhãn cho cả gộp nhóm lẫn gộp kế hoạch, lệch chữ là dòng kế
#: hoạch không khớp được với dòng sản lượng và % hiện ra trống.
NO_REGION_LABEL = "(Chưa gán khu vực)"

CONTRACT_LABELS = {"long_term": "HĐ dài hạn", "spot": "HĐ chuyến"}
# Đủ 3 hình thức của cơ chế hợp đồng — thiếu "internal" thì tiêu thụ nội bộ hiện ra chuỗi thô.
CHANNEL_LABELS = {"export": "XK / UTXK", "domestic": "Tiêu thụ trong nước",
                  "internal": "Tiêu thụ nội bộ"}


def label_of(labels: dict[str, str], v: str | None) -> str:
    """Nhãn của một giá trị enum; giá trị lạ/thiếu → "(chưa khai)" chứ KHÔNG lọt chuỗi thô ra UI."""
    return labels.get(v or "", UNKNOWN_LABEL)


#: Dấu nối khoá nhóm GHÉP ĐÔI (đơn vị × chủng loại) — ký tự điều khiển ASCII nên không thể trùng
#: với tên đơn vị hay tên chủng loại do người dùng đặt.
PAIR_SEP = "\u001f"


def pair(scope: str, grade: str | None) -> str:
    return f"{scope}{PAIR_SEP}{grade or UNKNOWN_LABEL}"


def unpair(key: str) -> tuple[str, str]:
    scope, _, grade = key.partition(PAIR_SEP)
    return scope, grade


#: group_by → hàm lấy nhãn nhóm của 1 dòng chi tiết.
GROUPERS: dict[str, Callable[[dict], str | None]] = {
    "company": lambda r: r.get("company"),
    "region": lambda r: r.get("region") or NO_REGION_LABEL,
    "day": lambda r: r.get("as_of"),
    "grade": lambda r: r.get("grade"),
    "material": lambda r: MATERIAL_LABELS.get(r.get("material") or ""),
    "contract": lambda r: label_of(CONTRACT_LABELS, r.get("contract")),
    "channel": lambda r: label_of(CHANNEL_LABELS, r.get("channel")),
    "source": lambda r: SOURCE_LABELS.get(r.get("source") or ""),
    # Ghép đôi — phục vụ bảng chéo "đơn vị × chủng loại" của màn Chỉ số đơn vị. Nhờ đi qua đúng
    # các hàm gộp sẵn có, giá bình quân ở từng ô vẫn là BQ GIA QUYỀN chứ không phải trung bình cộng.
    "company+grade": lambda r: pair(r.get("company") or "", r.get("grade")),
    "region+grade": lambda r: pair(r.get("region") or NO_REGION_LABEL, r.get("grade")),
}


#: Mặc định các bảng thống kê GỘP số liệu của đơn vị đã sáp nhập vào đơn vị hiện hành (chốt
#: 24/08/2026) — người xem cần con số đầy đủ của đơn vị đang tồn tại. Bật `split_merged` để TÁCH
#: ra xem riêng giai đoạn trước sáp nhập.
def region_of_units() -> dict[str, str | None]:
    """{tên đơn vị: khu vực} cho MỌI đơn vị (kể cả đã sáp nhập) — dùng khi quy dòng về đơn vị mới."""
    return {u["name"]: u.get("region") for u in member_unit_repo.list_units()}


def report_units(split_merged: bool = False) -> list[dict]:
    """Khung đơn vị của báo cáo: đang hoạt động, cộng thêm đơn vị ĐÃ SÁP NHẬP khi xem TÁCH.

    Xem GỘP thì đơn vị đã sáp nhập KHÔNG có dòng riêng ở bất kỳ kỳ nào — số của họ nằm trong dòng
    của đơn vị nhận (luật 27/08/2026). Xem TÁCH thì họ trở lại khung, nếu không số của họ biến mất
    khỏi bảng dù vẫn còn nguyên trong kho dữ liệu — đúng thứ tính năng sáp nhập cam kết giữ lại.
    """
    units = member_unit_repo.list_units(include_inactive=False)
    if split_merged:
        merged = [u for u in member_unit_repo.list_units() if u.get("merged_into")]
        units = sorted(units + merged, key=lambda u: (u.get("sort_order") or 0, u["name"]))
    return units


def sum_deep(a: Any, b: Any) -> Any:
    """Cộng 2 khối số liệu cùng khuôn của 2 đơn vị trong cùng dòng đời (dùng khi GỘP sáp nhập).

    Số cộng lại, dict lồng cộng theo từng khoá, danh sách nối lại, cờ true/false thì OR. Các khối
    này (`contracts_on`, `sales_contract_report.consumption`, kế hoạch năm) đều là số ở lá nên phép
    cộng đệ quy giữ đúng nghĩa — cùng một phép cộng mà báo cáo vẫn làm khi cộng nhiều ngày.
    """
    if isinstance(a, bool) or isinstance(b, bool):
        return bool(a) or bool(b)
    if a is None:
        return b
    if b is None:
        return a
    if isinstance(a, dict) and isinstance(b, dict):
        return {k: sum_deep(a.get(k), b.get(k)) for k in {**a, **b}}
    if isinstance(a, list) and isinstance(b, list):
        return [*a, *b]
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return a + b
    return b


def roll_by_company(by_company: dict[str, Any], split_merged: bool = False) -> dict[str, Any]:
    """Gộp các khối {đơn vị: số liệu} của đơn vị đã sáp nhập vào đơn vị hiện hành.

    Dùng cho những bảng trả về theo ĐƠN VỊ chứ không theo dòng (tiêu thụ từ hợp đồng, đã ký chưa
    giao, kế hoạch năm): xem gộp thì đơn vị nhận phải hiện MỘT dòng gồm cả phần của đơn vị cũ.
    """
    roll = {} if split_merged else member_unit_merge.rollup_map()
    if not roll:
        return by_company
    out: dict[str, Any] = {}
    for name, data in by_company.items():
        cur = roll.get(name, name)
        out[cur] = sum_deep(out[cur], data) if cur in out else data
    return out


def merge_view(companies: list[str] | None, split_merged: bool) -> list[str] | None:
    """Bộ lọc đơn vị SAU khi đã gộp: tên đơn vị đã sáp nhập quy về đơn vị hiện hành.

    Chọn nhầm đơn vị cũ trong lúc đang xem GỘP mà không quy đổi thì bảng trống trơn — dòng của họ
    lúc đó đã mang tên đơn vị mới, không khớp bộ lọc nào.
    """
    if split_merged or not companies:
        return companies
    roll = member_unit_merge.rollup_map()
    return list(dict.fromkeys(roll.get(c, c) for c in companies))


def merge_scope(companies: list[str] | None, split_merged: bool) -> list[str] | None:
    """Danh sách đơn vị dùng để TRUY VẤN dữ liệu: khi gộp, chọn B phải kéo theo dữ liệu cũ của A."""
    if split_merged:
        return companies
    return member_unit_merge.expand(merge_view(companies, split_merged))


def merge_rollup(rows: list[dict], split_merged: bool) -> list[dict]:
    """Quy các dòng của đơn vị đã sáp nhập về đơn vị hiện hành (bỏ qua khi đang xem TÁCH).

    Không cắt theo ngày: dòng của MỌI kỳ đều mang tên đơn vị hiện hành (luật 27/08/2026).
    """
    if split_merged:
        return rows
    return member_unit_merge.rollup_rows(rows, region_of_units())


def dmy(iso: str | None) -> str:
    """'2026-07-23' → '23/07/2026' (chuẩn VN) cho các câu cảnh báo người dùng đọc."""
    if not iso or len(iso) < 10:
        return iso or ""
    return f"{iso[8:10]}/{iso[5:7]}/{iso[:4]}"


def split_csv(csv: str | None) -> list[str] | None:
    """'a,b' → ['a','b'] (rỗng/None → None = không lọc)."""
    if not csv:
        return None
    vals = [s.strip() for s in csv.split(",") if s.strip()]
    return vals or None


def filter_scope(rows: list[dict], companies: list[str] | None, regions: list[str] | None) -> list[dict]:
    """Lọc theo đơn vị + khu vực (dùng chung cho mọi bảng)."""
    out = rows
    if companies:
        keep = set(companies)
        out = [r for r in out if r["company"] in keep]
    if regions:
        keep = set(regions)
        out = [r for r in out if (r.get("region") or "") in keep]
    return out


def avg(total: float, qty: float) -> float | None:
    return (total / qty) if qty else None


#: Kế hoạch là chỉ tiêu NĂM của một ĐƠN VỊ → chỉ gắn được cho nhóm đơn vị/khu vực. Nhóm theo
#: ngày / loại mủ / chủng loại thì một chỉ tiêu năm không chia nhỏ ra được — để TRỐNG còn hơn chia bừa.
PLAN_DIMS = ("company", "region")


def year_plan_by_group(plan_key: str, group_by: str, companies: list[str] | None,
                       regions: list[str] | None, year: int,
                       split_merged: bool = False) -> tuple[dict[str, float], float]:
    """Chỉ tiêu NĂM `plan_key` của màn "Kế hoạch năm" → ({khoá nhóm: tấn}, tổng theo bộ lọc).

    Mẫu số lấy theo DANH SÁCH ĐƠN VỊ khớp bộ lọc, không phải theo đơn vị có phát sinh số liệu:
    đơn vị được giao kế hoạch mà kỳ này chưa phát sinh gì vẫn phải nằm trong mẫu số — bỏ ra là %
    tự đẹp lên.

    Khi GỘP đơn vị đã sáp nhập, chỉ tiêu của đơn vị cũ cộng vào đơn vị hiện hành: tử số đã gồm sản
    lượng của đơn vị cũ, mẫu số bỏ chỉ tiêu của họ ra thì % thực hiện tự đẹp lên.
    """
    units = report_units(split_merged=True)     # luôn xét cả đơn vị đã sáp nhập…
    roll = {} if split_merged else member_unit_merge.rollup_map()   # …rồi quy về đơn vị hiện hành
    if companies:
        keep = set(merge_scope(companies, split_merged) or [])
        units = [u for u in units if u["name"] in keep]
    view = set(merge_view(companies, split_merged) or [])
    region_of = region_of_units()
    plans = unit_daily_repo.year_plan(year)
    by_key: dict[str, float] = {}
    total = 0.0
    for u in units:
        cur = roll.get(u["name"], u["name"])
        region = region_of.get(cur) if cur != u["name"] else u.get("region")
        if regions and (region or "") not in set(regions):
            continue
        if view and cur not in view:      # đơn vị cũ đã gộp về đơn vị KHÁC bộ lọc → không tính
            continue
        n = (plans.get(u["name"]) or {}).get(plan_key) or 0.0
        if not n:
            continue
        total += n
        if group_by in PLAN_DIMS:
            k = cur if group_by == "company" else (region or NO_REGION_LABEL)
            by_key[k] = by_key.get(k, 0.0) + n
    return by_key, total


def sort_groups(groups: dict[str, dict], group_by: str) -> list[dict]:
    """Ngày → tăng dần; còn lại → theo nhãn (A→Z)."""
    key = "key" if group_by == "day" else "label"
    return sorted(groups.values(), key=lambda g: g[key])
