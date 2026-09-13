"""Gói "Giá sàn & tư vấn" — công cụ đối chiếu giá sàn SVR 3L với giá mủ TƯ NHÂN (kết hợp tồn kho).

Logic nghiệp vụ nằm ở `services/private_price_benchmark.py` (dùng chung với `get_floor_context`);
module này chỉ bọc thành công cụ cho Trợ lý + dựng bảng hiển thị.
"""
from __future__ import annotations

from typing import Any

from app.services import floor_suggest, private_price_benchmark
from app.services.assistant_tools._common import cols, dmy, err, safe_date, table, today


def engine_context(as_of: str) -> tuple[dict | None, float | None]:
    """(tồn kho, mức FOB SVR 3L mô hình đề xuất) từ engine gợi ý — thiếu thì (None, None)."""
    try:
        s = floor_suggest.suggest(as_of)
    except Exception:  # noqa: BLE001 - engine thiếu dữ liệu vẫn đối chiếu được, chỉ mất tồn kho
        return None, None
    if s.get("error"):
        return None, None
    fob = next((it.get("suggested") for it in s.get("items", [])
                if private_price_benchmark.is_svr3l(it.get("grade", ""))), None)
    return s.get("inventory"), fob


def _private_benchmark(args: dict) -> dict:
    as_of = safe_date(args.get("as_of")) or today()
    inv, fob = engine_context(as_of)
    b = private_price_benchmark.benchmark(as_of, inv, fob)
    if not b:
        return err(f"Chưa đối chiếu được tại {dmy(as_of)}: cần phiếu Báo giá mủ có giá mủ tư nhân "
                   "và biểu giá sàn có giá nội địa SVR 3L.")
    floor = b["gia_san_hien_hanh"]
    rows: list[dict[str, Any]] = [
        {"hang_muc": f"{r['don_vi']} ({dmy(r['ngay_gia'])})", "gia_mu": r["gia_mu"], "gia_tri": r["gia_thanh_svr3l"]}
        for r in b["don_vi_tu_nhan"]]
    rows += [
        {"hang_muc": "Giá thành tham chiếu (trung bình tư nhân)", "gia_mu": "", "gia_tri": b["gia_thanh_tham_chieu"]},
        {"hang_muc": "Vùng giá sàn hợp lý — từ", "gia_mu": "", "gia_tri": b["vung_gia_san_hop_ly"]["tu"]},
        {"hang_muc": "Vùng giá sàn hợp lý — đến", "gia_mu": "", "gia_tri": b["vung_gia_san_hop_ly"]["den"]},
        {"hang_muc": f"Giá sàn hiện hành ({floor['title']})", "gia_mu": "", "gia_tri": floor["noi_dia_vnd"]},
        {"hang_muc": "Mức gợi ý theo giá tư nhân + tồn kho", "gia_mu": "", "gia_tri": b["muc_goi_y_theo_gia_tu_nhan"]},
    ]
    art = table(f"Giá sàn SVR 3L so với giá mủ tư nhân ({b['so_don_vi']} đơn vị, giá mới nhất {dmy(b['ngay_gia_moi_nhat'])})",
                cols(("hang_muc", "Hạng mục (ngày giá)"), ("gia_mu", "Giá mủ (đồng/độ TSC)"),
                     ("gia_tri", "Giá thành / giá sàn (đồng/tấn)")), rows)
    return {"summary": b, "artifact": art,
            "source": f"Báo giá mủ Mục 6 · giá tư nhân tới {dmy(b['ngay_gia_moi_nhat'])} · giá sàn {floor['title']}"}


def for_model_mode(res: dict) -> dict:
    """Mức "Theo mô hình": gỡ các mức điều chỉnh khỏi cả phần gửi LLM lẫn bảng hiển thị."""
    if "summary" not in res or "error" in res.get("summary", {}):
        return res
    out = {**res, "summary": private_price_benchmark.note_only(res["summary"])}
    art = res.get("artifact")
    if art and art.get("rows"):
        out["artifact"] = {**art, "rows": [r for r in art["rows"] if not str(r.get("hang_muc", "")).startswith("Mức gợi ý")]}
    return out


TOOLS: dict[str, dict[str, Any]] = {
    "get_private_price_benchmark": {
        "run": _private_benchmark,
        "schema": {"name": "get_private_price_benchmark",
                   "description": "ĐỐI CHIẾU giá sàn nội địa SVR 3L của Tập đoàn với giá mủ TƯ NHÂN: quy giá mủ tư nhân ra giá thành SVR 3L, dựng VÙNG GIÁ SÀN HỢP LÝ (= giá thành tư nhân + 700.000–1.000.000 đồng/tấn theo chuyên viên), cho biết giá sàn hiện hành thấp/trong/cao hơn vùng, KẾT HỢP xu hướng tồn kho để ra mức gợi ý trong vùng, và ước tính mức của mô hình có nằm trong vùng không. Gọi khi tư vấn điều chỉnh giá sàn (nhất là SVR 3L / giá nội địa) hoặc khi hỏi về giá mủ tư nhân.",
                   "parameters": {"type": "object", "properties": {
                       "as_of": {"type": "string", "description": "ngày YYYY-MM-DD (mặc định hôm nay)"}}}}},
}
