"""Đối chiếu giá sàn nội địa SVR 3L của Tập đoàn với giá mủ TƯ NHÂN (Mục 6 phiếu Báo giá mủ).

Hai quy tắc nghiệp vụ do chuyên viên Ban TTKD đưa ra (13/09/2026):
  1. Giá thành SVR 3L của tư nhân (đồng/tấn) = giá mủ (đồng/độ TSC) × 1,08 × 100.000 + chi phí gia
     công chế biến (mặc định 2.000.000, nhập theo từng phiếu). Bản sao web: `lib/private-latex-cost.ts`.
  2. Giá sàn nội địa SVR 3L của Tập đoàn HỢP LÝ NHẤT khi cao hơn giá thành tư nhân 700.000–1.000.000
     đồng/tấn.

Kết hợp với tồn kho để chọn điểm trong vùng: tồn kho TĂNG (áp lực bán) → mép dưới; GIẢM → mép trên;
đi ngang/không rõ → điểm giữa. Mọi hướng và mức đều TÍNH SẴN ở đây — không để LLM tự nhân dấu.
Đây là quy tắc kinh nghiệm, CHƯA đo tương quan trên lịch sử như rổ futures.
"""

from __future__ import annotations

from datetime import date
from typing import Any


from app.services import floor_recommend, floor_repo, market_quote_repo

PRIVATE_SVR3L_COEF = 1.08
DEFAULT_PROCESSING_COST = 2_000_000
TSC_TO_TONNE = 100_000
FLOOR_PREMIUM_MIN = 700_000
FLOOR_PREMIUM_MAX = 1_000_000
STALE_AFTER_DAYS = 7          # giá tư nhân cũ hơn chừng này ngày thì cảnh báo
_UNIT = "VNĐ/T"               # giá sàn nội địa → bước ban hành 50.000 đồng


def svr3l_cost(tsc_price: float, processing_cost: float | None = None) -> float:
    """Giá thành SVR 3L (đồng/tấn, làm tròn đồng) từ giá mủ đồng/độ TSC."""
    cost = DEFAULT_PROCESSING_COST if processing_cost is None else processing_cost
    return round(tsc_price * PRIVATE_SVR3L_COEF * TSC_TO_TONNE + cost)


def _vn(n: float) -> str:
    """Số kiểu Việt Nam: 3.049.000 (chấm phân cách nghìn)."""
    return f"{n:,.0f}".replace(",", ".")


def _position(value: float, band: tuple[float, float]) -> str:
    return "THẤP HƠN" if value < band[0] else "CAO HƠN" if value > band[1] else "TRONG"


def is_svr3l(grade: str) -> bool:
    return (grade or "").replace(" ", "").upper() == "SVR3L"


def _floor_svr3l(as_of: str) -> dict[str, Any] | None:
    """Giá sàn SVR 3L của lần ban hành gần nhất có hiệu lực ≤ as_of."""
    sched = floor_repo.list_schedules(date_to=as_of)
    if not sched:
        return None
    full = floor_repo.get_schedule(int(sched[0]["lan"])) or {}
    item = next((i for i in full.get("items", []) if is_svr3l(i["grade"])), None)
    if not item or item.get("domestic_vnd") is None:
        return None
    return {"lan": full["lan"], "title": full["title"], "ap_dung": full["as_of"],
            "noi_dia_vnd": float(item["domestic_vnd"]),
            "fob_usd": float(item["fob_usd"]) if item.get("fob_usd") is not None else None}


def _dmy(iso: str) -> str:
    return date.fromisoformat(iso).strftime("%d/%m/%Y")


def _inventory_trend(inv: dict[str, Any] | None) -> tuple[str, str]:
    """(xu hướng tồn kho, cách chọn điểm trong vùng) — `inv` = `inventory_daily.at`.

    Hướng lấy từ luật chung `floor_recommend.inventory_lean` (tồn kho tổng + tự do, ngưỡng ±3%) để
    khớp màn Gợi ý giá sàn và tín hiệu của Trợ lý AI. % tính trên đơn vị có số ở cả hai ngày.
    """
    lean = floor_recommend.inventory_lean(inv)
    if not lean:
        return "chưa đủ dữ liệu", "điểm giữa vùng (không có tín hiệu tồn kho)"
    pct = lambda v: "—" if v is None else f"{v:+.1f}%"  # noqa: E731
    span = (f", {_dmy(lean['base_day'])} → {_dmy(lean['day'])}"
            if lean.get("base_day") and lean.get("day") else "")
    moves = f"tổng {pct(lean['total_pct'])}, tự do {pct(lean['free_pct'])}{span}"
    if lean["direction"] == "up":
        return f"TĂNG ({moves})", "mép DƯỚI vùng (+700.000) vì tồn kho tăng (tổng hoặc phần tự do chưa có HĐ) là áp lực bán"
    if lean["direction"] == "down":
        return f"GIẢM ({moves})", "mép TRÊN vùng (+1.000.000) vì tồn kho giảm (tổng hoặc phần tự do), nguồn hàng chặt"
    if lean["direction"] == "mixed":
        return f"trái chiều ({moves})", "điểm giữa vùng (tồn kho tổng và tự do đi ngược nhau)"
    return f"đi ngang ({moves})", "điểm giữa vùng (tồn kho đi ngang)"


#: Trường ĐIỀU CHỈNH — chỉ dùng ở mức "Có điều chỉnh". Mức "Theo mô hình" phải giữ nguyên số mô hình
#: nên các trường này bị gỡ khỏi kết quả (hàng rào kỹ thuật, không chỉ dặn trong prompt — đo thực tế
#: LLM thấy "muc_de_xuat" là đem ra làm mức đề xuất dù luật bảo giữ số mô hình).
ADJUSTMENT_KEYS = ("muc_goi_y_theo_gia_tu_nhan", "cach_chon_diem_trong_vung", "dieu_chinh_can_thiet",
                   "dieu_chinh_pct", "muc_de_xuat_noi_dia_svr3l", "dieu_chinh_so_voi_mo_hinh",
                   "dieu_chinh_so_voi_mo_hinh_pct", "dieu_chinh_so_voi_gia_san_hien_hanh", "ket_luan")


def note_only(summary: dict[str, Any]) -> dict[str, Any]:
    """Bản dành cho mức "Theo mô hình": bỏ mọi mức điều chỉnh, chỉ giữ vị trí so với vùng làm ghi chú."""
    out = {k: v for k, v in summary.items() if k not in ADJUSTMENT_KEYS}
    out["huong_dan"] = ("Mức tư vấn Theo mô hình: GIỮ NGUYÊN số của mô hình. Khi nói giá sàn NỘI ĐỊA SVR 3L của "
                        "mô hình, dùng ĐÚNG muc_mo_hinh_noi_dia_uoc_tinh — TUYỆT ĐỐI không tự quy đổi FOB USD sang "
                        "VNĐ bằng tỷ giá hay tự tính ra số khác. Nêu NGUYÊN VĂN ghi_chu_vi_tri làm ghi chú tham khảo "
                        "(không tự so số với vùng), KHÔNG đưa ra mức giá sàn nào khác.")
    return out


def benchmark(as_of: str, inventory: dict[str, Any] | None = None,
              model_fob_svr3l: float | None = None) -> dict[str, Any] | None:
    """Đối chiếu tại `as_of`. None nếu chưa có giá mủ tư nhân hoặc chưa có giá sàn SVR 3L.

    `inventory` = bối cảnh tồn kho của engine gợi ý (floor_suggest `inventory`), `model_fob_svr3l`
    = mức FOB SVR 3L mô hình đề xuất — quy ra nội địa theo tỷ lệ nội địa/FOB của lần hiện hành.
    """
    units, floor = market_quote_repo.private_prices_by_unit(as_of), _floor_svr3l(as_of)
    if not units or not floor:
        return None
    cost_rows = []
    for u in sorted(units, key=lambda x: x["name"]):
        lo, hi = u["price"], u.get("price_max")
        mid = (lo + (hi if hi is not None else lo)) / 2
        cost_rows.append({
            "don_vi": u["name"], "ngay_gia": u["as_of"],
            "gia_mu": f"{lo:g}–{hi:g}" if hi is not None else f"{lo:g}",
            "gia_thanh_svr3l": svr3l_cost(mid, u.get("processing_cost")),
        })
    ref = round(sum(r["gia_thanh_svr3l"] for r in cost_rows) / len(cost_rows))
    band = (ref + FLOOR_PREMIUM_MIN, ref + FLOOR_PREMIUM_MAX)
    cur = floor["noi_dia_vnd"]
    if cur < band[0]:
        position, direction = f"THẤP hơn vùng hợp lý {_vn(band[0] - cur)} đồng/tấn", "hỗ trợ NÂNG"
    elif cur > band[1]:
        position, direction = f"CAO hơn vùng hợp lý {_vn(cur - band[1])} đồng/tấn", "hỗ trợ HẠ"
    else:
        position, direction = "NẰM TRONG vùng hợp lý", "trung tính (giữ trong vùng)"

    trend, how = _inventory_trend(inventory)
    # Mức gợi ý là một giá sàn ban hành được (bội 50.000 đồng): mép dưới làm tròn LÊN, mép trên làm
    # tròn XUỐNG để vẫn nằm trong vùng; điểm giữa làm tròn gần nhất.
    step = floor_recommend.to_step
    target = (step(band[0], _UNIT, "up") if trend.startswith("TĂNG")
              else step(band[1], _UNIT, "down") if trend.startswith("GIẢM")
              else step((band[0] + band[1]) / 2, _UNIT))
    newest = max(r["ngay_gia"] for r in cost_rows)
    old = [r["don_vi"] for r in cost_rows
           if (date.fromisoformat(as_of) - date.fromisoformat(r["ngay_gia"])).days > STALE_AFTER_DAYS]

    model_dom = None
    if model_fob_svr3l is not None and floor["fob_usd"]:
        model_dom = floor_recommend.to_step(cur * model_fob_svr3l / floor["fob_usd"], _UNIT)
    model_pos = None if model_dom is None else _position(model_dom, band)
    # Mức cuối: mô hình đã nằm trong vùng thì giữ mô hình; ngoài vùng (hoặc không có) thì lấy điểm
    # trong vùng đã chọn theo tồn kho. Tính ở đây để LLM chỉ việc đọc, không tự so sánh số.
    final = model_dom if model_pos == "TRONG" else target
    if model_dom is None:
        verdict = (f"Chưa có mức mô hình cho SVR 3L → đề xuất nội địa SVR 3L {_vn(final)} đồng/tấn "
                   f"({how}).")
    elif model_pos == "TRONG":
        verdict = (f"Mức mô hình {_vn(model_dom)} NẰM TRONG vùng hợp lý {_vn(band[0])}–{_vn(band[1])} "
                   f"→ giữ mức mô hình {_vn(final)} đồng/tấn.")
    else:
        verdict = (f"Mức mô hình {_vn(model_dom)} {model_pos} vùng hợp lý {_vn(band[0])}–{_vn(band[1])} "
                   f"→ kéo về {_vn(final)} đồng/tấn ({how}), tức {'+' if final >= model_dom else '−'}"
                   f"{_vn(abs(final - model_dom))} so với mô hình.")
    return {
        "ngay": as_of, "ngay_gia_moi_nhat": newest, "so_don_vi": len(cost_rows),
        "cach_lay_gia": f"giá MỚI NHẤT của từng đơn vị tư nhân trong {market_quote_repo.PRIVATE_PRICE_WINDOW_DAYS} "
                        "ngày gần nhất (mỗi dòng có ngày giá riêng)",
        "canh_bao_do_tuoi": (f"Giá của {', '.join(old)} đã cũ hơn {STALE_AFTER_DAYS} ngày — cần cập nhật trước khi dựa vào."
                             if old else None),
        "cong_thuc": (f"Giá thành SVR 3L = giá mủ (đồng/độ TSC) × {str(PRIVATE_SVR3L_COEF).replace('.', ',')} × "
                      f"100.000 + chi phí gia công chế biến của phiếu (mặc định {_vn(DEFAULT_PROCESSING_COST)} đồng/tấn); "
                      "khoảng giá lấy điểm giữa; giá thành tham chiếu = trung bình các đơn vị"),
        "don_vi_tu_nhan": cost_rows,
        "gia_thanh_tham_chieu": ref,
        "quy_tac": "Giá sàn nội địa SVR 3L hợp lý = giá thành tư nhân + 700.000 – 1.000.000 đồng/tấn "
                   "(ý kiến chuyên viên, chưa đo trên lịch sử)",
        "vung_gia_san_hop_ly": {"tu": band[0], "den": band[1]},
        "gia_san_hien_hanh": floor,
        "gia_san_hien_hanh_so_voi_vung": position, "huong_tac_dong": direction,
        "ton_kho_xu_huong": trend, "cach_chon_diem_trong_vung": how,
        "muc_goi_y_theo_gia_tu_nhan": target,
        "dieu_chinh_can_thiet": round(target - cur),
        "dieu_chinh_pct": round((target - cur) / cur * 100, 2),
        "muc_mo_hinh_noi_dia_uoc_tinh": model_dom,
        "muc_mo_hinh_so_voi_vung": None if model_pos is None else f"{model_pos} vùng hợp lý",
        "muc_de_xuat_noi_dia_svr3l": final,
        "dieu_chinh_so_voi_mo_hinh": None if model_dom is None else round(final - model_dom),
        "dieu_chinh_so_voi_mo_hinh_pct": None if model_dom is None else round((final - model_dom) / model_dom * 100, 2),
        "dieu_chinh_so_voi_gia_san_hien_hanh": round(final - cur),
        "ket_luan": verdict,
        "ghi_chu_vi_tri": (f"Giá sàn hiện hành {_vn(cur)} {position}"
                           + ("" if model_dom is None else
                              f"; mức mô hình {_vn(model_dom)} {model_pos} vùng hợp lý {_vn(band[0])}–{_vn(band[1])}")
                           + " (ghi chú tham khảo theo giá mủ tư nhân)."),
        "don_vi_tinh": "đồng/tấn (nội địa)",
    }
