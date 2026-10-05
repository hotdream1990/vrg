"""Sửa hợp đồng / đợt giao SAU KHI số liệu đã chốt — mở đúng những ô không dịch con số nào.

Yêu cầu chủ dự án 29/08/2026: *"cho phép chỉnh sửa các nội dung mà không làm ảnh hưởng số liệu
thống kê dù đã chốt. Ví dụ cập nhật chứng từ, số hợp đồng, cập nhật HĐ mẹ…"*.

Cách làm: KHÔNG liệt kê "ô nào được sửa" rồi kiểm từng ô — làm thế thì thêm một ô mới vào schema
là nó lọt qua hàng rào theo mặc định. Thay vào đó chụp lại **ảnh chụp các ô CÓ ẢNH HƯỞNG SỐ LIỆU**
(`STAT_FIELDS`) của bản cũ và bản mới rồi so: giống hệt ⇒ lần sửa này không dịch con số nào ⇒ cho
qua. Thêm ô mới mà quên phân loại thì nó KHÔNG nằm trong ảnh chụp, tức là mặc định được coi là an
toàn — nên `STAT_FIELDS` phải phủ đủ, và test `test_sales_contract_lock.py` khoá lại danh sách này.

⚠ Đây CHỈ là hàng rào của tài khoản ĐƠN VỊ THÀNH VIÊN (chuyên viên/quản trị xưa nay không bị chặn).
Quyền xem/sửa theo đơn vị vẫn kiểm riêng ở `_assert_company` — module này không đụng tới.
"""

from __future__ import annotations

from datetime import date
from typing import Any

#: Ô LÀM DỊCH SỐ ĐÃ BÁO CÁO — đổi bất kỳ ô nào ở đây thì vẫn bị chặn khi đã chốt.
#:
#: Vì sao từng ô nằm đây:
#:   company · parent_id · delivery_type — số liệu thuộc về đơn vị nào, là hợp đồng hay đợt giao.
#:   contract_type      — chỉ tiêu "phụ lục hợp đồng mẹ / HĐ chuyến" của báo cáo tiêu thụ.
#:   customer_id        — báo cáo "tiêu thụ theo khách hàng" quy sản lượng về khách này.
#:   sign_date          — "đã ký HĐ chưa giao" LỌC theo ngày ký ≤ ngày báo cáo
#:                        (`sales_contract_report.py`), lùi ngày ký là dịch số tồn cam kết.
#:   start_date         — ô cũ của vòng đời đợt giao; vẫn khoá để bản ghi cũ không bị lay.
#:   delivered_at       — MỐC ghi nhận tiêu thụ: dời ngày là chuyển sản lượng sang kỳ khác.
#:   channel·to_company — cơ cấu XK / trong nước / nội bộ và đơn vị nhận hàng nội bộ.
#:   source             — tiêu thụ mủ khai thác / mủ thu mua (03/10/2026).
#:   lines              — chủng loại · sản lượng · quy khô · đơn giá · loại tiền · tỷ giá · ngày
#:                        hiệu lực của dòng (`from_date`, 30/09/2026).
#:   payment_qty        — sản lượng thanh toán (số lượng, đơn vị đã xác nhận cùng đợt chốt).
#:   premium·premium_ccy— khoản tiền cộng thêm của hàng có chứng chỉ.
STAT_FIELDS: tuple[str, ...] = (
    "company", "parent_id", "delivery_type", "contract_type", "customer_id",
    "sign_date", "start_date", "delivered_at", "channel", "to_company", "source",
    "lines", "payment_qty", "premium", "premium_ccy",
)

#: Ô VẪN SỬA ĐƯỢC sau khi chốt — (khoá, nhãn người dùng đọc). Dùng cho câu báo lỗi và cho
#: `/api/sales-contracts/meta` để form hiện đúng danh sách, khỏi viết tay ở hai nơi.
EDITABLE_WHEN_LOCKED: tuple[tuple[str, str], ...] = (
    ("code", "Số hợp đồng / số đợt giao"),
    ("master_id", "Hợp đồng mẹ (nối/đổi hồ sơ)"),
    ("invoice_no", "Số hoá đơn"),
    ("invoice_docs", "File hoá đơn"),
    ("payment_date", "Ngày thanh toán"),
    ("payment_docs", "Chứng từ thanh toán"),
    ("files", "File hợp đồng đính kèm"),
    ("certs", "Chứng chỉ (PEFC · EUDR · VRG GREEN)"),
    ("expiry_date", "Thời hạn hợp đồng"),
    ("note", "Ghi chú"),
)

#: Câu liệt kê cho người dùng (dùng trong thông báo lỗi).
EDITABLE_LABELS: str = " · ".join(label for _, label in EDITABLE_WHEN_LOCKED)

#: ĐƠN VỊ TỰ SỬA NGUỒN TIÊU THỤ của lần giao đã khoá — mở CÓ HẠN, hết ngày này tự khoá lại
#: (chủ dự án chốt 05/10/2026). Lần giao nhập trước khi có ô nguồn đều được gán "Khai thác", đơn vị
#: phải rà lại cả những lần quá cửa sổ sửa / đã chốt; đi «Đề nghị sửa» thì Ban duyệt từng lần giao.
#: Đổi nguồn không đổi tổng sản lượng hay doanh thu, chỉ đổi cách chia — nên mở một đường RIÊNG
#: (`PUT /{id}/source`) thay vì nới `STAT_FIELDS`: đường lưu chung vẫn giữ nguyên hàng rào, và quá
#: hạn là `source` lại như mọi ô số liệu khác.
SOURCE_SELF_EDIT_UNTIL = date(2026, 10, 8)


def source_self_edit_open() -> bool:
    """Còn trong hạn đơn vị tự sửa nguồn không (tính theo giờ Việt Nam, hết NGÀY hạn mới đóng)."""
    from app.core import edit_window

    return edit_window.today() <= SOURCE_SELF_EDIT_UNTIL


def _num(v: Any) -> float | None:
    """Số về một dạng duy nhất — 5 và 5.0 phải so ra BẰNG NHAU, nếu không mọi lần lưu lại đều
    bị coi là đã sửa số liệu (jsonb trả 5.0, form gửi 5)."""
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _txt(v: Any) -> str | None:
    """Chuỗi rỗng và None là MỘT — form gửi "" cho ô bỏ trống, DB lưu NULL."""
    s = str(v).strip() if v is not None else ""
    return s or None


def _from_key(ln: dict, sign_date: Any, is_child: bool) -> str | None:
    """Ngày hiệu lực của dòng về một dạng: đợt giao không có ô này, trùng ngày ký = để trống
    (server lưu NULL) — form gửi đúng ngày ký thì vẫn phải so ra BẰNG bản trong DB."""
    d = (_txt(ln.get("from_date")) or "")[:10] or None
    return None if is_child or d == (_txt(sign_date) or "")[:10] else d


def _lines_key(lines: Any, sign_date: Any = None, is_child: bool = False) -> tuple:
    """Khoá so sánh của các dòng chi tiết — 6 ô quyết định sản lượng và doanh thu + NGÀY HIỆU LỰC
    (30/09/2026: dời ngày hiệu lực là dời phần "đã ký HĐ chưa giao" sang ngày khác).

    Không so nguyên dict: bản trong DB đã qua `sales_contract_calc.clean_lines` nên chỉ còn đúng các
    khoá đó, còn payload từ form có thể mang thêm ô phụ; so nguyên dict là lần lưu nào cũng báo "đã đổi".
    """
    out = []
    for ln in lines if isinstance(lines, list) else []:
        if not isinstance(ln, dict):
            continue
        out.append((
            _txt(ln.get("grade")), _num(ln.get("qty")), _num(ln.get("qty_dry")),
            _num(ln.get("price")), _txt(ln.get("ccy")) or "VND", _num(ln.get("fx")),
            _from_key(ln, sign_date, is_child),
        ))
    return tuple(out)


_NUM_FIELDS = frozenset({"parent_id", "customer_id", "payment_qty", "premium"})


def stat_snapshot(row: dict[str, Any]) -> dict[str, Any]:
    """Ảnh chụp CHỈ các ô ảnh hưởng số liệu — hai ảnh giống nhau nghĩa là không con số nào dịch."""
    snap: dict[str, Any] = {}
    for f in STAT_FIELDS:
        if f == "lines":
            snap[f] = _lines_key(row.get(f), row.get("sign_date"), bool(row.get("parent_id")))
        elif f in _NUM_FIELDS:
            snap[f] = _num(row.get(f))
        else:
            snap[f] = _txt(row.get(f))
    return snap


def is_safe_edit(old: dict[str, Any] | None, new: dict[str, Any]) -> bool:
    """Lần lưu này có giữ nguyên mọi con số đã báo cáo không?

    `old = None` (thêm mới) LUÔN là False: bản ghi mới trong vùng đã chốt là thêm số liệu vào kỳ
    đã xác nhận, không phải "sửa nội dung không ảnh hưởng".
    """
    if old is None:
        return False
    return stat_snapshot(old) == stat_snapshot(new)


def assert_delivery_fences(username: str, contract_id: int | None, new_delivered_at: str | None,
                           company: str | None = None, old: dict | None = None) -> None:
    """Hai hàng rào thời gian của hợp đồng/đợt giao — mốc là NGÀY GIAO (chốt 02/08/2026).

    Cửa sổ sửa chỉ áp cho LẦN GIAO: lần giao là bản ghi tiêu thụ, giao xong quá N ngày thì kỳ báo
    cáo đã chốt, sửa lùi là làm lệch số đã gửi đi. KHÔNG áp cho hợp đồng: hợp đồng ký từ lâu vẫn
    phải sửa và thêm đợt giao suốt vòng đời. Các mốc tương lai (thời hạn, ngày thanh toán) cũng
    không đụng tới, vì `assert_editable` chặn cả ngày tương lai.

    Kiểm CẢ HAI đầu: ngày giao ĐANG lưu (không cho sửa/xoá lần giao đã khoá) và ngày giao MỚI gửi
    lên (không cho khai lùi ra ngoài cửa sổ). Dùng chung cho router hợp đồng và luồng «Đề nghị sửa»
    (`edit_request_ops_contract`) — một luật, một chỗ.
    """
    from app.core import security
    from app.services import sales_contract_repo

    old = old if old is not None else (sales_contract_repo.get(contract_id) if contract_id else None)
    days = [old.get("delivered_at") if old else None, new_delivered_at]
    for as_of in days:
        if as_of:
            security.assert_edit_window(username, as_of)
    # CHỐT SỐ LIỆU: lần giao ≤ ngày chốt phải đứng yên (yêu cầu 25/08/2026: "hợp đồng có thể cập
    # nhật nhưng tiêu thụ sẽ bị chốt lại"). Hợp đồng và các đợt giao SAU ngày chốt vẫn thêm/sửa.
    security.assert_not_data_locked(username, company or (old or {}).get("company"), *days,
                                    safe_fields=EDITABLE_LABELS)


def assert_switch_fences(username: str, old: dict[str, Any] | None) -> None:
    """Hàng rào thời gian của việc CHUYỂN LOẠI GIAO (giao 1 lần ↔ giao nhiều lần).

    CHỈ hàng rào CHỐT SỐ LIỆU, KHÔNG có cửa sổ sửa — endpoint `/delivery-type` xưa nay như vậy.
    Chuyển loại giao không dịch con số nào (lần giao được dời nguyên vẹn xuống đợt giao đầu tiên)
    nhưng nó đổi CHỖ ghi nhận, nên kỳ đã chốt thì đơn vị phải đi qua «Đề nghị sửa».
    Dùng chung cho router hợp đồng và `edit_request_ops_contract` — một luật, một chỗ.
    """
    from app.core import security

    old = old or {}
    security.assert_not_data_locked(username, old.get("company"), old.get("delivered_at"))
