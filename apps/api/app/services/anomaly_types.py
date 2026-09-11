"""Khai báo dùng chung cho màn "Cảnh báo bất thường" — danh mục luật + ngưỡng.

Mục đích của màn: admin nắm mọi bất thường trong số liệu đơn vị thành viên mà KHÔNG phải chạy
script thủ công. Quét trực tiếp mỗi lần mở trang (không lưu bảng kết quả) — chủ dự án chốt
11/09/2026.

Mỗi luật trả về một NHÓM cảnh báo cùng khuôn, để frontend vẽ bảng mà không cần biết luật nào:
    {key, label, desc, severity, columns: [{key, label}], rows: [...], count, units}
`rows` là danh sách dict phẳng, khoá trùng `columns[].key`.
"""
from __future__ import annotations

from typing import Any

#: Mức nghiêm trọng — quyết định màu thẻ và thứ tự hiển thị.
HIGH, MEDIUM, LOW = "high", "medium", "low"

#: Ngưỡng phát hiện, admin sửa ở Cấu hình hệ thống (nhóm `anomaly`). Đây là mốc PHÁT HIỆN chứ
#: không phải mốc nghiệp vụ: vượt ngưỡng nghĩa là "gần như chắc chắn gõ nhầm đơn vị tính".
#: Trị mặc định lấy đúng bộ đang dùng ở skill `bao-cao-nhap-lieu` (đã chạy thật nhiều đợt).
THRESHOLDS: dict[str, dict[str, Any]] = {
    "ANOMALY_RAW_PRICE_MAX": {
        "default": 1500, "label": "Giá mủ nguyên liệu — trần (đồng/độ)",
        "hint": "Mặt bằng 100–1.500 đ/độ. Vượt trần = nghi gõ nhầm đồng/kg hoặc đồng/tấn."},
    "ANOMALY_SALE_PRICE_MAX": {
        "default": 200, "label": "Giá bán quy đổi — trần (triệu đồng/tấn)",
        "hint": "Mặt bằng 40–70 triệu đ/tấn. Ngoại tệ quy về VNĐ bằng tỷ giá của chính dòng đó."},
    "ANOMALY_SALE_USD_MAX": {
        "default": 10000, "label": "Giá bán USD — trần (USD/tấn) khi thiếu tỷ giá",
        "hint": "Mặt bằng 1.400–2.200 USD/tấn. Chỉ áp khi dòng bán chưa khai tỷ giá."},
    "ANOMALY_REVENUE_DAY_MAX_TY": {
        "default": 5000, "label": "Doanh thu một ngày toàn Tập đoàn — trần (tỷ đồng)",
        "hint": "Ngày cao điểm thật ~170 tỷ. Vượt trần = nghi nhập giá sai 1.000 lần."},
    "ANOMALY_SILENT_DAYS": {
        "default": 7, "label": "Số ngày ngừng nộp thì cảnh báo",
        "hint": "Đơn vị có nghĩa vụ nộp mà không có bản ghi nào trong ngần này ngày gần nhất."},
    "ANOMALY_STOCK_JUMP_PCT": {
        "default": 50, "label": "Tồn kho nhảy bậc — ngưỡng (%)",
        "hint": "Tồn kho một đơn vị đổi hơn ngần này phần trăm so với ngày liền trước."},
}


def group(key: str, label: str, desc: str, severity: str,
          columns: list[tuple[str, str]], rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Đóng gói một nhóm cảnh báo theo đúng khuôn frontend đang chờ."""
    units = {r.get("don_vi") for r in rows if r.get("don_vi")}
    return {"key": key, "label": label, "desc": desc, "severity": severity,
            "columns": [{"key": k, "label": lb} for k, lb in columns],
            "rows": rows, "count": len(rows), "units": len(units)}
