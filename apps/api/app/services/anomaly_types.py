"""Khai báo dùng chung cho màn "Cảnh báo bất thường" — danh mục luật + ngưỡng.

Mục đích của màn: admin nắm mọi bất thường trong số liệu đơn vị thành viên mà KHÔNG phải chạy
script thủ công. Quét trực tiếp mỗi lần mở trang (không lưu bảng kết quả) — chủ dự án chốt
11/09/2026.

Mỗi luật trả về một NHÓM cảnh báo cùng khuôn, để frontend vẽ bảng mà không cần biết luật nào:
    {key, label, desc, severity, columns: [{key, label}], rows: [...], count, units}
`rows` là danh sách dict phẳng, khoá trùng `columns[].key`.
"""
from __future__ import annotations

from datetime import date
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


def vn_date(iso: str) -> str:
    """'2026-09-16' → '16/09/2026'. Mô tả cảnh báo hiện thẳng cho người dùng (cả lãnh đạo đơn vị),
    nên theo đúng cách ghi ngày của các màn khác thay vì dạng ISO của máy."""
    parts = str(iso)[:10].split("-")
    return f"{parts[2]}/{parts[1]}/{parts[0]}" if len(parts) == 3 else str(iso)


def vn_day_runs(days: list[date], with_year: bool) -> str:
    """Danh sách ngày (tăng dần) → '14/09, 16/09, 20/09–25/09': ngày liền nhau gộp thành một đoạn
    để đơn vị thiếu cả tháng không hiện ra 30 ngày rời. Kỳ nằm gọn trong một năm thì bỏ năm."""
    fmt = "%d/%m/%Y" if with_year else "%d/%m"
    runs: list[tuple[date, date]] = []
    for d in days:
        if runs and (d - runs[-1][1]).days == 1:
            runs[-1] = (runs[-1][0], d)
        else:
            runs.append((d, d))
    return ", ".join(a.strftime(fmt) if a == b else f"{a.strftime(fmt)}–{b.strftime(fmt)}"
                     for a, b in runs)


def vn_num(value: float) -> str:
    """1500 → '1.500' — dấu chấm ngăn nghìn như mọi con số khác trên giao diện."""
    return f"{value:,.0f}".replace(",", ".")


def group(key: str, label: str, desc: str, severity: str,
          columns: list[tuple[str, str]], rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Đóng gói một nhóm cảnh báo theo đúng khuôn frontend đang chờ."""
    units = {r.get("don_vi") for r in rows if r.get("don_vi")}
    return {"key": key, "label": label, "desc": desc, "severity": severity,
            "columns": [{"key": k, "label": lb} for k, lb in columns],
            "rows": rows, "count": len(rows), "units": len(units)}


def finalize(date_from: str, date_to: str, groups: list[dict[str, Any]]) -> dict[str, Any]:
    """Xếp nhóm + dựng tổng quan → đúng khuôn kết quả frontend chờ.

    MỌI nhóm CÓ cảnh báo lên trước, rồi mới tới nhóm rỗng; trong mỗi phần mới xét mức nghiêm
    trọng. Xếp mức trước thì ngày hệ thống sạch, ba nhóm "Nghiêm trọng · 0 dòng" chiếm hết đầu
    trang còn việc thật (chưa nộp · thiếu đơn giá) bị đẩy xuống — đọc ngược hẳn thông điệp.
    """
    sev_rank = {HIGH: 0, MEDIUM: 1, LOW: 2}
    groups = sorted(groups, key=lambda g: (0 if g["count"] else 1, sev_rank.get(g["severity"], 9)))
    all_units: set[str] = set()
    counts = {HIGH: 0, MEDIUM: 0, LOW: 0}
    total = 0
    for g in groups:
        total += g["count"]
        counts[g["severity"]] = counts.get(g["severity"], 0) + g["count"]
        all_units |= {r.get("don_vi") for r in g["rows"] if r.get("don_vi")}
    summary = {"total": total, "high": counts[HIGH], "medium": counts[MEDIUM],
               "low": counts[LOW], "units": len(all_units)}
    return {"date_from": date_from, "date_to": date_to, "groups": groups, "summary": summary}
