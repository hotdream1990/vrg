"""So khớp chữ tiếng Việt KHÔNG DẤU cho các ô tìm kiếm (gõ "sai gon" ra "Sài Gòn").

Dùng `translate()` của Postgres thay vì extension `unaccent`: tạo extension đòi quyền superuser,
dựng DB mới ở nơi khác mà thiếu quyền là app không khởi động được. `translate()` có sẵn mọi nơi và
bảng chữ cái tiếng Việt là đóng — liệt kê ra là đủ.

⚠ Hai chuỗi truyền cho `translate()` PHẢI dài bằng nhau: chuỗi nguồn dài hơn thì Postgres **XOÁ**
các ký tự thừa, tên khách mất chữ và tìm mãi không ra. Vì vậy bảng chữ dựng theo cặp
`{chữ không dấu: các biến thể có dấu}` rồi sinh ra hai chuỗi — không thể lệch nhau.
"""

from __future__ import annotations

#: {ký tự không dấu: mọi biến thể CÓ DẤU của nó} — gồm cả `đ`, thứ `unaccent` bản cũ hay bỏ sót.
_FOLD: dict[str, str] = {
    "a": "áàảãạăắằẳẵặâấầẩẫậ",
    "d": "đ",
    "e": "éèẻẽẹêếềểễệ",
    "i": "íìỉĩị",
    "o": "óòỏõọôốồổỗộơớờởỡợ",
    "u": "úùủũụưứừửữự",
    "y": "ýỳỷỹỵ",
}

_LOWER_MARKS = "".join(_FOLD.values())
_LOWER_PLAIN = "".join(plain * len(marks) for plain, marks in _FOLD.items())
#: Kèm cả CHỮ HOA có dấu: `lower()` của Postgres phụ thuộc locale của DB, gặp locale `C` thuần thì
#: "SÀI GÒN" không hạ được thành "sài gòn". Có sẵn bản hoa trong bảng thì lệch locale cũng khớp.
MARKS = _LOWER_MARKS + _LOWER_MARKS.upper()
PLAIN = _LOWER_PLAIN + _LOWER_PLAIN

_TABLE = str.maketrans(MARKS, PLAIN)

#: Tham số bind cho `fold_sql()` — nhớ `params.update(FOLD_PARAMS)` ở mỗi câu truy vấn dùng nó.
FOLD_PARAMS: dict[str, str] = {"_vn_marks": MARKS, "_vn_plain": PLAIN}


def fold(text: str) -> str:
    """Bỏ dấu + hạ chữ thường ở phía Python (dùng cho từ khoá người dùng gõ)."""
    return text.lower().translate(_TABLE)


def fold_sql(column: str) -> str:
    """Biểu thức SQL bỏ dấu + hạ chữ thường của một cột, so bằng `LIKE` (đã lower cả hai vế)."""
    return f"translate(lower({column}), :_vn_marks, :_vn_plain)"
