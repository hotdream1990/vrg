"""Danh mục Lịch sử truy cập: tên trang tiếng Việt + loại sự kiện.

Vì sao server giữ bảng tên trang (không nhận nhãn do web gửi lên): nhãn hiện thẳng trên màn tra
cứu của admin — nhận chữ tuỳ ý từ client là mở đường cho dữ liệu rác/giả mạo. Web chỉ gửi đường
dẫn; thiếu nhãn thì hiện nguyên đường dẫn (vẫn tra được), không bao giờ chặn việc ghi.

Trang mới thêm vào `App.tsx` nhớ khai một dòng ở đây, nếu không nhật ký sẽ hiện đường dẫn thô.
"""

from __future__ import annotations

#: Đường dẫn (đã chuẩn hoá) → tên trang. Đoạn động dùng ':id' (vd '/ho-tro/12' → '/ho-tro/:id').
PAGES: dict[str, str] = {
    "/": "Dashboard",
    "/login": "Đăng nhập",
    "/ho-so": "Hồ sơ cá nhân",
    # Số liệu thị trường
    "/quet-da-san": "Quét Đa sàn",
    "/quet-da-san/records": "Quét Đa sàn — bản ghi",
    "/quan-ly-so-lieu/bang-gia-san": "Bảng tính giá các sàn",
    "/quan-ly-so-lieu/ty-gia": "Tỷ giá",
    "/quan-ly-so-lieu/gia-san-tap-doan": "Giá sàn Tập đoàn",
    "/quan-ly-so-lieu/gia-physical": "Giá Physical",
    "/quan-ly-so-lieu/bao-gia-mu": "Báo giá mủ thị trường",
    "/quan-ly-so-lieu/gia-mu-nguyen-lieu": "Giá mủ nguyên liệu",
    "/quan-ly-so-lieu/ton-kho": "Tồn kho Tập đoàn",
    "/quan-ly-so-lieu/don-vi-thanh-vien": "Đơn vị thành viên",
    # Số liệu đơn vị
    "/bao-cao-thu-mua": "Thu mua (theo ngày)",
    "/bao-cao-ton-kho": "Tồn kho (theo ngày)",
    "/bao-cao-tieu-thu": "Báo cáo tiêu thụ",
    "/nhu-cau-thi-truong": "Nhu cầu thị trường",
    "/ke-hoach-nam": "Kế hoạch năm",
    "/chot-so-lieu": "Chốt số liệu đơn vị",
    "/de-nghi-sua": "Đề nghị sửa số liệu (của tôi)",
    "/duyet-de-nghi-sua": "Duyệt đề nghị sửa",
    "/duyet-de-nghi-sua/:id": "Duyệt đề nghị sửa — chi tiết",
    # Hợp đồng
    "/hop-dong": "Hợp đồng & đợt giao",
    "/hop-dong/khach-hang": "Khách hàng",
    "/hop-dong/hop-dong-me": "Hợp đồng mẹ (HĐNT/HĐDH)",
    # Báo cáo & thống kê
    "/bao-cao-tong-hop": "Báo cáo tổng hợp",
    "/thong-ke/thu-mua": "Thống kê thu mua",
    "/thong-ke/tieu-thu": "Thống kê tiêu thụ",
    "/thong-ke/ton-kho": "Thống kê tồn kho",
    "/thong-ke/tinh-trang-nop": "Theo dõi nộp báo cáo",
    "/thong-ke-hop-dong": "Hợp đồng cũ (trước 30/07)",
    # Phân tích & bản tin
    "/goi-y-gia-san": "Gợi ý giá sàn",
    "/ban-tin": "Bản tin ngày",
    "/ban-tin/tao": "Bản tin ngày — soạn",
    "/ban-tin/xem/:id": "Bản tin ngày — xem",
    "/ban-tin/tuan": "Báo cáo tuần",
    "/ban-tin-bien-dong": "Bản tin biến động",
    "/tro-ly-ai": "Trợ lý AI",
    "/tro-ly-ai/lich-su": "Trợ lý AI — lịch sử hỏi đáp",
    # Nhà máy thông minh
    "/nha-may-thong-minh/chi-so": "Nhà máy thông minh — Giám sát chỉ số",
    # Hỗ trợ
    "/ho-tro": "Hỗ trợ & Thông báo",
    "/ho-tro/nhac-lich": "Nhắc lịch",
    "/ho-tro/dot/:id": "Hỗ trợ — đợt gửi",
    "/ho-tro/:id": "Hỗ trợ — chi tiết thẻ",
    # Quản trị
    "/quan-tri/nguoi-dung": "Người dùng",
    "/quan-tri/cau-hinh": "Cấu hình hệ thống",
    "/quan-tri/lich-chay": "Lịch chạy",
    "/quan-tri/nhat-ky": "Nhật ký hoạt động",
    "/quan-tri/truy-cap": "Lịch sử truy cập",
    "/canh-bao-bat-thuong": "Cảnh báo bất thường",
}

#: Loại sự kiện → nhãn hiển thị.
EVENTS: dict[str, str] = {
    "login": "Đăng nhập",
    "login_failed": "Đăng nhập thất bại",
    "page": "Xem trang",
}

#: Đường dẫn dài hơn bấy nhiêu ký tự thì cắt (không có trang thật nào dài vậy).
MAX_PATH = 120


def normalize_path(raw: str) -> str:
    """Đường dẫn trình duyệt → dạng gom nhóm được: bỏ query/hash, đoạn cuối động → ':id'.

    '/ho-tro/12?tab=1' → '/ho-tro/:id' · '/ban-tin/xem/abc.pdf' → '/ban-tin/xem/:id'.
    Không khớp trang nào thì trả nguyên (đã cắt ngắn) để vẫn tra cứu được.
    """
    path = (raw or "").split("?")[0].split("#")[0].strip()[:MAX_PATH]
    if not path.startswith("/"):
        path = "/" + path
    if len(path) > 1:
        path = path.rstrip("/")
    if path in PAGES:
        return path
    head, _, tail = path.rpartition("/")
    if tail:
        candidate = f"{head}/:id"
        if candidate in PAGES:
            return candidate
    return path


def page_label(path: str) -> str:
    """Tên trang tiếng Việt; chưa khai trong PAGES → rỗng (màn tra cứu hiện đường dẫn thô)."""
    return PAGES.get(path, "")
