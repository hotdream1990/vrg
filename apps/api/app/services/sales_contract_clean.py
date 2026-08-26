"""Chuẩn hoá + KIỂM TRA NGHIỆP VỤ một hợp đồng / đợt giao trước khi ghi (tách khỏi repo).

Mọi thông báo lỗi ở đây đi thẳng ra màn hình người nhập nên viết bằng tiếng Việt, nói rõ phải sửa
gì. Nguyên tắc chung: giá trị sai thì BÁO LỖI, tuyệt đối không lặng lẽ quy về mặc định — một
`ccy` viết thường bị ép về VNĐ từng làm doanh thu sai ~38 lần.
"""

from __future__ import annotations

import math
from datetime import date
from typing import Any

from app.core.market_meta import CONTRACT_TYPES, DELIVERY_TYPES, SALE_CHANNELS
from app.services import contract_docs, customer_repo, sales_contract_calc as calc


def _as_date(v, label: str, required: bool = False) -> date | None:
    s = str(v or "").strip()[:10]
    if not s:
        if required:
            raise ValueError(f"Thiếu {label}.")
        return None
    try:
        return date.fromisoformat(s)
    except ValueError as exc:
        raise ValueError(f"{label} không hợp lệ (YYYY-MM-DD).") from exc


def _num(v) -> float | None:
    """Số hợp lệ hoặc None — loại NaN/Infinity (xem `sales_contract_calc._num`)."""
    try:
        f = None if v in (None, "") else float(v)
    except (TypeError, ValueError):
        return None
    return None if f is not None and not math.isfinite(f) else f


def _money(v, label: str) -> float | None:
    """Ô tiền/sản lượng nhập tay — không được âm (âm làm số liệu kỳ bị trừ ngược)."""
    f = _num(v)
    if f is not None and f < 0:
        raise ValueError(f"{label} không được âm.")
    return f


def _int_id(v, label: str) -> int | None:
    """Khoá số dương hoặc None. `str(-1).isdigit()` là False nên số âm từng lặng lẽ thành None —
    một `parent_id` âm biến đợt giao thành hợp đồng, `id` âm biến 'sửa' thành 'thêm mới'."""
    s = str(v if v is not None else "").strip()
    if not s:
        return None
    if not s.isdigit() or int(s) <= 0:
        raise ValueError(f"{label} không hợp lệ.")
    return int(s)


def assert_unit_exists(name: str, label: str) -> None:
    """Tên đơn vị phải có thật trong `member_unit` — nếu không bản ghi thành mồ côi, không bộ lọc
    nào hiển thị được mà vẫn nằm trong bảng và vẫn được cộng vào tổng."""
    from app.services import member_unit_repo

    if name not in {u["name"] for u in member_unit_repo.list_units()}:
        raise ValueError(f"{label} “{name}” không có trong danh sách đơn vị thành viên.")


def assert_unit_can_sign(name: str, label: str) -> None:
    """Đơn vị ĐÃ SÁP NHẬP không ký hợp đồng MỚI nữa (chốt 24/08/2026).

    Chỉ chặn bản ghi mới ở cấp HỢP ĐỒNG / HỒ SƠ MẸ. Hợp đồng đã ký trước đó vẫn phải chạy cho hết:
    thêm đợt giao, điền ngày giao, chốt hoàn thành — nếu chặn luôn thì phần hàng đã cam kết của
    đơn vị cũ không giao nốt được, mà chuyển hợp đồng sang đơn vị mới lại làm sản lượng đã giao
    trước đó nhảy đơn vị.
    """
    from app.services import member_unit_merge

    if info := member_unit_merge.merged_info(name):
        tgt, at = info
        raise ValueError(
            f"{label} “{name}” đã sáp nhập vào “{tgt}” từ {at} — hợp đồng mới ký ở “{tgt}”. "
            f"Hợp đồng cũ của “{name}” vẫn thêm được đợt giao và chốt hoàn thành.")


def _assert_same_group(company: str, to_company: str) -> None:
    """Tiêu thụ NỘI BỘ chỉ trong nhóm công ty mẹ–con — bán ra ngoài nhóm là bán ngoài.

    Chặn ở đây chứ không chỉ ở form: lọt một hợp đồng "nội bộ" với đơn vị ngoài nhóm là chỉ tiêu
    tiêu thụ nội bộ của cả Tập đoàn sai, mà nhìn số không biết sai từ đâu.
    """
    from app.services import member_unit_repo

    peers = member_unit_repo.internal_targets().get(company) or []
    if to_company not in peers:
        raise ValueError(
            f"“{to_company}” không cùng nhóm công ty mẹ–con với “{company}” nên không phải tiêu thụ "
            "nội bộ. Gán Công ty mẹ ở màn Đơn vị thành viên, hoặc chọn hình thức khác."
            if peers else
            f"“{company}” chưa thuộc nhóm công ty mẹ–con nào nên không có tiêu thụ nội bộ. "
            "Gán Công ty mẹ ở màn Đơn vị thành viên trước.")


def _assert_master_ok(master_id: int, company: str) -> None:
    """Hợp đồng mẹ được nối tới phải có thật và CÙNG ĐƠN VỊ. Ngoài ra KHÔNG lấy gì từ nó —
    hợp đồng giữ nguyên khách hàng, loại hợp đồng, mọi thứ của chính nó.

    Import muộn để tránh vòng import: `master_contract_repo` đọc SQL sản lượng của
    `sales_contract_report`, mà module đó lại đi qua `sales_contract_repo` → file này.
    """
    from app.services import master_contract_repo

    master = master_contract_repo.get(master_id)
    if master is None:
        raise ValueError("Hợp đồng mẹ không còn tồn tại (có thể đã bị xoá).")
    if master["company"] != company:
        raise ValueError("Hợp đồng mẹ thuộc đơn vị khác.")


def clean(row: dict, company: str) -> dict[str, Any]:
    """Chuẩn hoá + kiểm tra 1 hợp đồng / đợt giao trước khi ghi (raise ValueError nếu sai)."""
    code = str(row.get("code") or "").strip()[:80]
    if not code:
        raise ValueError("Thiếu số hợp đồng / số đợt giao.")
    parent_id = _int_id(row.get("parent_id"), "Hợp đồng")
    is_child = parent_id is not None
    # HỢP ĐỒNG MẸ (HĐNT/HĐDH) — có nối = bản ghi này là PHỤ LỤC, số ở ô `code` là SỐ PHỤ LỤC.
    # Chỉ đặt ở HỢP ĐỒNG: đợt giao nằm bên trong phụ lục, nối thẳng vào hợp đồng mẹ sẽ bị đếm
    # hai lần khi cộng sản lượng đã ký của hợp đồng mẹ (xem `master_contract_repo._ANNEX_SQL`).
    master_id = None if is_child else _int_id(row.get("master_id"), "Hợp đồng mẹ")
    if master_id is not None:
        _assert_master_ok(master_id, company)
    delivery_type = str(row.get("delivery_type") or "single").strip()
    if delivery_type not in DELIVERY_TYPES:
        raise ValueError(f"Loại giao “{row.get('delivery_type')}” không hợp lệ.")
    # Đợt giao chỉ tính là ĐÃ GIAO khi có ngày giao; để trống = ĐANG CHỜ GIAO (đã lập đợt, hàng
    # chưa xuất) → chưa vào tiêu thụ, vẫn nằm trong phần chưa giao của hợp đồng.
    delivered_at = _as_date(row.get("delivered_at"), "Ngày giao")
    delivered = delivered_at is not None
    if is_child:
        delivery_type = "single"
    elif delivery_type == "multi" and delivered:
        raise ValueError("Hợp đồng giao nhiều lần không tự đánh dấu đã giao — hãy nhập đợt giao.")
    # Bản ghi này CÓ PHẢI một lần giao không: đợt giao, hoặc hợp đồng giao trọn 1 lần.
    is_batch = is_child or delivery_type == "single"
    # Loại HỢP ĐỒNG (dài hạn/chuyến) là chỉ tiêu báo cáo, ĐỘC LẬP loại giao. Chỉ khai ở hợp đồng —
    # đợt giao thừa kế của hợp đồng khi thống kê (xem `sales_contract_report.deliveries`).
    raw_ctype = str(row.get("contract_type") or "").strip()
    if raw_ctype and raw_ctype not in CONTRACT_TYPES:
        raise ValueError(f"Loại hợp đồng “{raw_ctype}” không hợp lệ.")
    contract_type = None if is_child else raw_ctype or None
    if contract_type is None and not is_child:
        raise ValueError("Thiếu loại hợp đồng (HĐ dài hạn / HĐ chuyến).")
    # Luật hồ sơ hợp đồng mẹ theo LOẠI HỢP ĐỒNG (chốt 24/08/2026):
    #   - HĐ CHUYẾN bán đứt từng chuyến, không nằm trong hợp đồng khung nào → không có hồ sơ mẹ.
    #   - HĐ DÀI HẠN luôn là PHỤ LỤC của một hợp đồng mẹ → bắt buộc chọn hồ sơ.
    # ⚠ Ép ở CẢ tạo mới LẪN sửa (chốt 24/08/2026, khách quyết): prod có 942 hợp đồng dài hạn nhập
    # trước khi có cấp hồ sơ mẹ — mỗi lần đơn vị sửa một cái là phải gắn hồ sơ, coi như dọn dần hồ
    # sơ cũ. Đổi lại, sửa một hợp đồng dài hạn cũ nay bị chặn cho tới khi chọn xong hồ sơ.
    # Các thao tác KHÔNG đi qua đây vẫn chạy bình thường: hoàn thành/mở lại hợp đồng, chuyển loại
    # giao, và mọi thao tác trên ĐỢT GIAO (đợt không mang loại hợp đồng).
    if contract_type == "spot" and master_id is not None:
        raise ValueError("HĐ chuyến không thuộc hợp đồng mẹ — bỏ chọn ô Hợp đồng mẹ, hoặc đổi "
                         "loại sang HĐ dài hạn.")
    if contract_type == "long_term" and master_id is None:
        raise ValueError("HĐ dài hạn là phụ lục của một hợp đồng mẹ — chọn hồ sơ ở ô Hợp đồng mẹ. "
                         "Chưa có hồ sơ thì lập ở màn Hợp đồng mẹ (HĐNT/HĐDH) trước.")
    raw_channel = str(row.get("channel") or "").strip()
    if raw_channel and raw_channel not in SALE_CHANNELS:
        raise ValueError(f"Hình thức tiêu thụ “{raw_channel}” không hợp lệ.")
    channel = raw_channel or None
    if delivered and not channel:
        raise ValueError("Thiếu hình thức tiêu thụ (Xuất khẩu/UTXK · Trong nước · Nội bộ).")
    to_company = str(row.get("to_company") or "").strip()[:120] or None
    if channel == "internal":
        if not to_company:
            raise ValueError("Tiêu thụ nội bộ phải chọn đơn vị nhận hàng.")
        assert_unit_exists(to_company, "Đơn vị nhận")
        if to_company == company:
            raise ValueError("Đơn vị nhận của tiêu thụ nội bộ phải khác đơn vị bán.")
        _assert_same_group(company, to_company)
    else:
        to_company = None

    # Ngày ký chỉ có ở HỢP ĐỒNG. Đợt giao KHÔNG có ngày ký riêng — form không hiện ô này nhưng vẫn
    # gửi kèm ngày mặc định (hôm nay), nhận vào là mọi đợt giao ngày cũ bị chặn oan bằng thông báo
    # "Ngày giao không thể trước ngày ký hợp đồng". Ngày ký của hợp đồng đã được kiểm ở
    # `sales_contract_repo.save` (so với ngày ký THẬT của hợp đồng cha).
    sign = None if is_child else _as_date(row.get("sign_date"), "Ngày ký", required=True)
    # Ngày mở đợt: đã BỎ khỏi form (05/08/2026) vì khối 3 nay tính trên hợp đồng, không theo vòng
    # đời từng đợt nữa. Chỉ lưu lại nguyên giá trị cũ (không kiểm, không tính toán) để bản ghi cũ
    # sửa lại vẫn giữ được dữ kiện đã nhập.
    start = _as_date(row.get("start_date"), "Ngày bắt đầu")
    expiry = _as_date(row.get("expiry_date"), "Thời hạn hợp đồng")
    if sign and expiry and expiry < sign:
        raise ValueError("Thời hạn hợp đồng phải sau ngày ký.")
    if sign and delivered_at and delivered_at < sign:
        raise ValueError("Ngày giao không thể trước ngày ký hợp đồng.")

    paid_at = _as_date(row.get("payment_date"), "Ngày thanh toán")
    # ⚠ Nối hợp đồng mẹ KHÔNG đụng tới khách hàng (chốt 24/08/2026): hợp đồng vẫn tự khai khách
    # như trước, `master_id` chỉ là liên kết hồ sơ. Bản trước từng ghi đè khách theo hợp đồng mẹ
    # — gắn một hợp đồng cũ vào hồ sơ là đổi luôn khách của nó, tức là đổi số liệu "theo khách
    # hàng" của một kỳ đã chốt. Yêu cầu là hợp đồng mẹ ảnh hưởng ÍT NHẤT tới luồng cũ.
    customer_id = _int_id(row.get("customer_id"), "Khách hàng")
    if customer_id is None and not is_child:
        raise ValueError("Hợp đồng phải gán một khách hàng của đơn vị.")
    if customer_id is not None:
        owner = customer_repo.owner_of(customer_id)
        if owner is None:
            raise ValueError("Khách hàng không còn tồn tại.")
        if owner != company:
            raise ValueError("Khách hàng thuộc danh mục của đơn vị khác.")

    return {
        "id": _int_id(row.get("id"), "Mã hợp đồng"),
        "company": company,
        "parent_id": parent_id,
        "master_id": master_id,
        "code": code,
        "customer_id": customer_id,
        "delivery_type": delivery_type,
        "contract_type": contract_type,
        "sign_date": sign.isoformat() if sign else None,
        "expiry_date": expiry.isoformat() if expiry else None,
        "start_date": start.isoformat() if start else None,
        # Quy khô ép ở MỌI trạng thái (kể cả hợp đồng chưa giao); TỶ GIÁ thì chỉ ép khi bản ghi
        # đã có NGÀY GIAO — lúc ký hợp đồng chưa biết tỷ giá ngày giao (chốt 22/08/2026).
        "lines": calc.clean_lines(row.get("lines"), require_fx=delivered),
        "delivered": delivered,
        "delivered_at": delivered_at.isoformat() if delivered_at else None,
        "channel": channel,
        "to_company": to_company,
        # Hoá đơn của MỘT LẦN GIAO. Hợp đồng giao-1-lần chính nó là một đợt nên vẫn có; hợp
        # đồng giao-nhiều-lần thì không — hoá đơn nằm ở từng đợt, để ở đây là tra nhầm chỗ.
        "invoice_no": (str(row.get("invoice_no") or "").strip()[:80] or None) if is_batch else None,
        "invoice_docs": contract_docs.normalize(row.get("invoice_docs") if is_batch else None),
        "payment_date": paid_at.isoformat() if paid_at else None,
        "payment_qty": _money(row.get("payment_qty"), "Sản lượng thanh toán"),
        "payment_docs": contract_docs.normalize(row.get("payment_docs"), None, None),
        "files": contract_docs.normalize(row.get("files"), None, None),
        "note": str(row.get("note") or "").strip()[:500] or None,
    }

