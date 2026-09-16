"""Quyền theo mục dữ liệu — phân quyền chuyên viên nhập liệu (editor).

Nguyên tắc: admin = TẤT CẢ (mức Sửa); editor = theo danh sách `permissions` của tài khoản;
executive (Lãnh đạo Tập đoàn) = mọi mục NGHIỆP VỤ ở mức Xem (`EXECUTIVE_CAPS`);
viewer (Người xem) = KHÔNG có mục số liệu nào (chỉ xem dashboard/bản tin ở tầng UI).

Hai cấp quyền — các mục NHẬP LIỆU (`SPLIT_CAPS`) tách riêng Xem và Sửa:
  - `"raw_material"`       → mức Sửa (xem + nhập/sửa/xoá)
  - `"raw_material:view"`  → mức Xem (chỉ đọc, mọi thao tác ghi bị chặn 403)
Mục không thuộc `SPLIT_CAPS` (màn phân tích/bản tin) chỉ có 1 cấp — luôn quy về Sửa.

Lưu ý tương thích ngược: bản ghi cũ chỉ có key trần (vd `"physical"`) nên key trần = mức Sửa,
tức tài khoản đang có quyền giữ nguyên quyền sau khi nâng cấp — không cần migration dữ liệu.
"""

from __future__ import annotations

# key quyền → nhãn hiển thị (dùng cho trang Quản trị người dùng)
DATA_CAPS: dict[str, str] = {
    "market_quote": "Báo giá mủ thị trường (gồm giá mủ tư nhân)",
    "raw_material": "Giá mủ nguyên liệu",
    "floor": "Giá sàn Tập đoàn",
    "physical": "Giá Physical",
    "inventory": "Tồn kho",
    "member_unit": "Đơn vị thành viên",
    "auto_data": "Số liệu tự động (bảng giá sàn · tỷ giá · quét đa sàn)",
    "market_demand": "Nhu cầu thị trường (mọi đơn vị)",
    "unit_daily": "Báo cáo đơn vị theo ngày (thu mua · tồn kho — mọi đơn vị)",
    "sales_contract": "Hợp đồng & khách hàng (mọi đơn vị)",
    # Quyền truy cập các màn phân tích/bản tin (xem + thao tác). Không có = ẩn khỏi menu + chặn API.
    "floor_suggest": "Gợi ý giá sàn",
    "bulletin_daily": "Bản tin ngày",
    "bulletin_weekly": "Báo cáo tuần",
    "market_movement": "Bản tin biến động",
    "assistant": "Trợ lý AI (hỏi đáp số liệu + tư vấn giá sàn)",
    "support": "Hỗ trợ & Thông báo (hộp thư với lãnh đạo đơn vị + nhắc lịch)",
    "audit": "Nhật ký hoạt động (xem vết chỉnh sửa số liệu)",
    # 1 cấp, KHÔNG thuộc EXECUTIVE_CAPS: duyệt là thao tác GHI số liệu thay đơn vị (15/09/2026).
    "edit_request": "Duyệt đề nghị sửa số liệu của đơn vị",
}
CAP_KEYS = frozenset(DATA_CAPS)

#: Các mục nhập liệu có tách 2 cấp Xem/Sửa. Ngoài danh sách này = 1 cấp (luôn là Sửa).
SPLIT_CAPS = frozenset({
    "market_quote", "raw_material", "floor", "physical", "inventory",
    "member_unit", "auto_data", "market_demand", "unit_daily", "sales_contract",
    "support",
})

#: Lãnh đạo Tập đoàn xem được mọi báo cáo · thống kê · AI, KHÔNG gồm các mục thiên về vận hành/kỹ
#: thuật: `member_unit` (danh mục cấu hình đơn vị), `support` (hộp thư nghiệp vụ của Ban với đơn vị),
#: `audit` (nhật ký thao tác). Thêm mục nghiệp vụ mới thì cân nhắc thêm vào đây.
EXECUTIVE_CAPS = frozenset({
    "market_quote", "raw_material", "floor", "physical", "inventory", "auto_data",
    "market_demand", "unit_daily", "sales_contract",
    "floor_suggest", "bulletin_daily", "bulletin_weekly", "market_movement", "assistant",
})

LEVEL_VIEW = "view"
LEVEL_EDIT = "edit"
_RANK = {LEVEL_VIEW: 1, LEVEL_EDIT: 2}
_SEP = ":"


def parse_cap(entry: str) -> tuple[str, str] | None:
    """`"physical:view"` → `("physical", "view")`. Key trần → mức Sửa. Sai định dạng → None."""
    if not isinstance(entry, str):
        return None
    key, _, suffix = entry.partition(_SEP)
    if key not in CAP_KEYS:
        return None
    if key not in SPLIT_CAPS:  # mục 1 cấp — bỏ qua hậu tố, luôn là Sửa
        return key, LEVEL_EDIT
    if not suffix:
        return key, LEVEL_EDIT
    return (key, suffix) if suffix in _RANK else None


def format_cap(key: str, level: str) -> str:
    """Chuẩn hoá về dạng lưu: mức Sửa = key trần, mức Xem = `key:view`."""
    return key if level == LEVEL_EDIT else f"{key}{_SEP}{level}"


def clean_caps(permissions: list[str] | None) -> list[str]:
    """Lọc bỏ mục sai/trùng, chuẩn hoá định dạng, sắp theo thứ tự DATA_CAPS (trước khi lưu DB)."""
    levels: dict[str, str] = {}
    for entry in permissions or []:
        parsed = parse_cap(entry)
        if not parsed:
            continue
        key, level = parsed
        if _RANK[level] > _RANK.get(levels.get(key, ""), 0):  # trùng key → giữ mức cao hơn
            levels[key] = level
    return [format_cap(k, levels[k]) for k in DATA_CAPS if k in levels]


def effective_caps(role: str, permissions: list[str] | None) -> dict[str, str]:
    """Quyền THỰC của 1 tài khoản: `{key: level}`.

    admin→tất cả (Sửa) · executive→`EXECUTIVE_CAPS` (Xem, bỏ qua `permissions`) · editor→theo list ·
    còn lại→rỗng.
    """
    if role == "admin":
        return {k: LEVEL_EDIT for k in DATA_CAPS}
    if role == "executive":
        return {k: LEVEL_VIEW for k in DATA_CAPS if k in EXECUTIVE_CAPS}
    if role != "editor":
        return {}
    caps: dict[str, str] = {}
    for entry in permissions or []:
        parsed = parse_cap(entry)
        if parsed and _RANK[parsed[1]] > _RANK.get(caps.get(parsed[0], ""), 0):
            caps[parsed[0]] = parsed[1]
    return caps


def has_cap(caps: dict[str, str], key: str, level: str = LEVEL_VIEW) -> bool:
    """Tài khoản (với `caps` từ `effective_caps`) có đạt mức quyền yêu cầu cho mục `key` không."""
    return _RANK.get(caps.get(key, ""), 0) >= _RANK[level]
