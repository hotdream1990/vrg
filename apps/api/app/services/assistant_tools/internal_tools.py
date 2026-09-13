"""Gói kỹ năng "Số liệu nội bộ Tập đoàn" cho Trợ lý AI.

Bọc: tồn kho thành phẩm · báo giá mủ thị trường (đủ các nhóm giá, không chỉ xuất khẩu VRG) ·
giá mủ nguyên liệu (mủ nước/chén/dây, lớp chuyên viên `vrg`) · bản tin/báo cáo phát hành gần
nhất · độ tươi dữ liệu (chống trả lời trên số cũ mà không cảnh báo).
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import text

from app.core import edit_window
from app.core.db import session_scope
from app.core.market_meta import PURCHASE_PRICE_UNIT, PURCHASE_SOURCE_HQ
from app.services import (
    bulletin_service, draft_repo, inventory_repo, market_quote_repo, price_repo,
    weekly_report_service,
)
from app.services.assistant_tools._common import (
    NO_ARGS, clamp_days, cols, days_ago, dm, dmy, err, line, pct, table, today,
)

# ── get_inventory_trend (chuyển nguyên từ assistant_tools.py cũ) ──
def _inventory_trend(args: dict) -> dict:
    weeks = clamp_days(args.get("weeks"), 26)
    ser = list(reversed(inventory_repo.series(limit=weeks)))
    if not ser:
        return err("Chưa có dữ liệu tồn kho.")
    labels = [dm(r["as_of"]) for r in ser]
    tk = [r.get("ton_kho") for r in ser]
    hd = [r.get("ton_kho_hd") for r in ser]
    art = line(f"Tồn kho thành phẩm theo tuần ({len(ser)} tuần)", labels,
              [{"name": "Tồn kho", "values": tk}, {"name": "Đã có HĐ", "values": hd}], "tấn")
    last = ser[-1]
    return {"summary": {"tuan_gan_nhat": last["as_of"], "ton_kho_tan": last.get("ton_kho"),
                        "ton_kho_da_co_hd_tan": last.get("ton_kho_hd"), "so_tuan": len(ser)},
            "artifact": art, "source": f"fact_inventory · {len(ser)} tuần"}


# ── get_market_quote (mở rộng đủ 4 nhóm giá thay vì chỉ export_vrg) ──
# key trong payload phiếu → (nhãn hiển thị, đơn vị) — khớp _SECTION_MODES của market_quote_repo.
_QUOTE_GROUPS = [
    ("export_vrg", "Xuất khẩu VRG", "USD/tấn"),
    ("domestic_vrg", "Nội địa VRG", "đồng/tấn"),
    ("domestic_private", "Nội địa — tư nhân", "đồng/tấn"),
    ("domestic_export", "Xuất khẩu — hàng tư nhân", "đồng/tấn"),
]


def _market_quote(args: dict) -> dict:
    as_of = str(args.get("as_of") or "").strip()
    if not as_of:
        lst = market_quote_repo.list_quotes(limit=1)
        if not lst:
            return err("Chưa có phiếu báo giá mủ thị trường nào.")
        as_of = lst[0]["as_of"]
    q = market_quote_repo.get_quote(as_of)
    if not q:
        return err(f"Không có phiếu báo giá mủ thị trường ngày {dmy(as_of)}.")
    grades: set[str] = set()
    prices_by_key = {}
    for key, _label, _unit in _QUOTE_GROUPS:
        p = (q.get(key) or {}).get("prices") or {}
        prices_by_key[key] = p
        grades.update(p.keys())
    rows = [{"grade": g, **{key: prices_by_key[key].get(g) for key, _l, _u in _QUOTE_GROUPS}}
            for g in sorted(grades)]
    columns = cols(("grade", "Chủng loại"),
                   *[(key, f"{label} ({unit})") for key, label, unit in _QUOTE_GROUPS])
    art = table(f"Báo giá mủ thị trường · {dmy(as_of)}", columns, rows)
    # Mục 6 — giá mủ tư nhân: một giá hoặc khoảng giá "min–max" theo từng đơn vị tư nhân.
    num = lambda v: f"{v:.0f}" if float(v).is_integer() else f"{v}"  # noqa: E731
    private = {name: (f"{num(p['price'])}–{num(p['price_max'])}" if p.get("price_max") is not None
                      else num(p["price"]))
               for name, p in (q.get("private_prices") or {}).items() if p.get("price") is not None}
    # Đơn vị tư nhân báo giá vào ngày khác nhau → kèm giá MỚI NHẤT của từng đơn vị (ngày giá riêng),
    # để câu hỏi "giá mủ tư nhân hiện nay" không chỉ thấy các đơn vị có trong đúng phiếu ngày này.
    latest = [{"don_vi": r["name"], "ngay_gia": dmy(r["as_of"]),
               "gia": (f"{num(r['price'])}–{num(r['price_max'])}" if r.get("price_max") is not None
                       else num(r["price"]))}
              for r in sorted(market_quote_repo.private_prices_by_unit(as_of), key=lambda x: x["name"])]
    return {"summary": {"as_of": as_of, "gia_theo_nhom": rows,
                        "gia_mu_tu_nhan": private,
                        "gia_mu_tu_nhan_moi_nhat_tung_don_vi": latest,
                        "don_vi_gia_mu_tu_nhan": "đồng/độ TSC",
                        "ghi_chu": q.get("footer") or ""},
            "artifact": art, "source": f"market_quote · phiếu ngày {dmy(as_of)}"}


# ── get_raw_material_prices (giá mủ NGUYÊN LIỆU — nội địa, chưa AI nào chạm tới) ──
# material (tham số tool, cũng là "slot" của price_repo) → price_type + nhãn tiếng Việt.
_PRICE_TYPE_OF_MATERIAL = {v: k for k, v in price_repo.PURCHASE_TYPE_SLOT.items()}
_MATERIAL_LABEL = {"latex": "mủ nước", "cup": "mủ chén", "lace": "mủ dây"}


def _raw_material_prices(args: dict) -> dict:
    material = str(args.get("material") or "latex").lower().strip()
    if material not in _PRICE_TYPE_OF_MATERIAL:
        return err(f"Chủng loại nguyên liệu '{material}' không hợp lệ (chỉ nhận latex/cup/lace).")
    days = clamp_days(args.get("days"), 30)
    by_mode = str(args.get("by") or "overall").lower().strip()
    price_type = _PRICE_TYPE_OF_MATERIAL[material]
    unit = PURCHASE_PRICE_UNIT[price_type]
    label = _MATERIAL_LABEL[material]

    # Lớp `vrg` (chuyên viên chốt) — mặc định, dùng cho bản tin/báo cáo. Hàm đã tự loại giá 0
    # ("không có giá") và không carry-forward: mỗi (đơn vị, ngày) chỉ tính khi CÓ bản ghi thật.
    data = price_repo.purchase_prices_in_range(days_ago(days), today(), source=PURCHASE_SOURCE_HQ)
    by_date: dict[str, list[float]] = {}
    by_company: dict[str, list[tuple[str, float]]] = {}
    for (company, d), slots in data.items():
        v = slots.get(material)
        if v is None:
            continue
        by_date.setdefault(d, []).append(v)
        by_company.setdefault(company, []).append((d, v))
    if not by_date:
        return err(f"Không có giá thu mua {label} (lớp chuyên viên) trong {days} ngày qua.")

    if by_mode == "company":
        rows = []
        for company, pts in sorted(by_company.items()):
            vals = [v for _, v in pts]
            latest_d, latest_v = max(pts, key=lambda x: x[0])
            rows.append({"don_vi": company, "binh_quan_ky": round(sum(vals) / len(vals)),
                        "gia_gan_nhat": round(latest_v), "ngay_gan_nhat": dm(latest_d)})
        art = table(f"Giá thu mua {label} theo đơn vị ({unit}, {days} ngày)",
                   cols(("don_vi", "Đơn vị"), ("binh_quan_ky", f"BQ kỳ ({unit})"),
                        ("gia_gan_nhat", f"Gần nhất ({unit})"), ("ngay_gan_nhat", "Ngày")), rows)
        return {"summary": {"material": material, "don_vi_tinh": unit, "so_ngay": days,
                            "so_don_vi_co_gia": len(rows), "theo_don_vi": rows},
                "artifact": art,
                "source": f"fact_price · vrg/{price_type} · {days} ngày · theo đơn vị"}

    dates = sorted(by_date)
    values = [round(sum(by_date[d]) / len(by_date[d])) for d in dates]
    art = line(f"Giá thu mua {label} bình quân Tập đoàn ({unit}, {days} ngày)",
              [dm(d) for d in dates], [{"name": label, "values": values}], unit)
    first, last = values[0], values[-1]
    return {"summary": {"material": material, "don_vi_tinh": unit, "so_ngay_co_du_lieu": len(dates),
                        "gia_dau_ky": first, "gia_cuoi_ky": last, "thay_doi_pct": pct(last, first)},
            "artifact": art,
            "source": f"fact_price · vrg/{price_type} · {days} ngày · bình quân Tập đoàn"}


# ── get_latest_bulletin (KHÔNG chạy lại crawler — chỉ đọc nháp/báo cáo ĐÃ LƯU) ──
def _latest_daily_bulletin() -> dict:
    drafts = bulletin_service.list_saved_drafts()
    if not drafts:
        return err("Chưa có bản tin ngày nào được lưu.")
    rd = drafts[0]["report_date"]
    overrides = draft_repo.get_overrides(rd) or {}
    paras = [str(p).strip() for p in (overrides.get("market_analysis") or []) if str(p).strip()]
    nhan_dinh = " ".join(paras)[:800] if paras else "Chưa có nhận định (Mục IV) được soạn cho ngày này."
    recent = drafts[:5]
    art = table("Bản tin ngày — gần đây", cols(("ngay", "Ngày"), ("cap_nhat", "Cập nhật lúc")),
               [{"ngay": dmy(d["report_date"]),
                 "cap_nhat": str(d["updated_at"])[:16].replace("T", " ")} for d in recent])
    return {"summary": {"loai": "daily", "ngay_bao_cao": rd, "nhan_dinh_muc_IV": nhan_dinh,
                        "tong_so_ban_tin_da_luu": len(drafts)},
            "artifact": art, "source": f"bulletin_draft · bản tin ngày {dmy(rd)}"}


def _latest_weekly_report() -> dict:
    reports = weekly_report_service.list_reports()
    if not reports:
        return err("Chưa có báo cáo tuần nào được lưu.")
    latest = reports[0]
    rep = weekly_report_service.build_report(latest["week_key"])
    nar = rep.get("narrative") or {}
    paras = [str(p).strip() for p in (nar.get("conclusion") or nar.get("movement") or [])
             if str(p).strip()]
    tom_tat = " ".join(paras)[:800] if paras else "Chưa có nhận định kết luận cho tuần này."
    recent = reports[:5]
    art = table("Báo cáo tuần — gần đây", cols(("tuan", "Tuần"), ("cap_nhat", "Cập nhật lúc")),
               [{"tuan": r["label"], "cap_nhat": str(r["updated"])[:16].replace("T", " ")}
                for r in recent])
    return {"summary": {"loai": "weekly", "tuan": latest["label"], "tom_tat_ket_luan": tom_tat,
                        "tong_so_bao_cao_da_luu": len(reports)},
            "artifact": art, "source": f"weekly_report · {latest['label']}"}


def _latest_bulletin(args: dict) -> dict:
    kind = str(args.get("kind") or "daily").lower().strip()
    return _latest_weekly_report() if kind == "weekly" else _latest_daily_bulletin()


# ── get_data_freshness (chống trả lời trên số cũ mà không cảnh báo) ──
# (nhãn hiển thị, mệnh đề WHERE trên fact_price) — mệnh đề là hằng số mã nguồn, không phải input
# người dùng nên ghép chuỗi trực tiếp vào SQL vẫn an toàn.
_FRESH_GROUPS = [
    # ⚠ Không có nguồn nào tên 'ose' trong fact_price: sàn Nhật lưu dưới mã `tocom`, "OSE" chỉ là
    # nhãn hiển thị trên bản tin. Tách thành 2 dòng là báo "OSE chưa có dữ liệu" sai sự thật.
    ("Sàn SHFE (Thượng Hải)", "source = 'shfe'"),
    ("Sàn SGX (Singapore)", "source = 'sgx'"),
    ("Sàn OSE/TOCOM (Nhật)", "source = 'tocom'"),
    ("Sàn MRB/LGM (Malaysia)", "source = 'lgm'"),
    ("Tỷ giá", "source = 'fx'"),
    ("Giá physical quốc tế (Reuters)", "source = 'reuters'"),
    ("Giá mủ nguyên liệu — chuyên viên",
     "source = 'vrg' AND price_type IN ('purchase','purchase_cup','purchase_lace')"),
    ("Giá mủ nguyên liệu — đơn vị tự khai",
     "source = 'vrg_unit' AND price_type IN ('purchase','purchase_cup','purchase_lace')"),
]


def _fresh_row(label: str, latest, today_d) -> dict:  # noqa: ANN001 - latest là date|None từ DB
    if latest is None:
        return {"nhom": label, "ngay_moi_nhat": "chưa có dữ liệu", "so_ngay_tre": None}
    return {"nhom": label, "ngay_moi_nhat": dmy(str(latest)), "so_ngay_tre": (today_d - latest).days}


def _data_freshness(_: dict) -> dict:
    today_d = edit_window.today()
    rows = []
    with session_scope() as db:
        for label, cond in _FRESH_GROUPS:
            latest = db.execute(text(f"SELECT MAX(as_of) FROM fact_price WHERE {cond}")).scalar()
            rows.append(_fresh_row(label, latest, today_d))
        mq = db.execute(text("SELECT MAX(as_of) FROM market_quote")).scalar()
        rows.append(_fresh_row("Báo giá mủ thị trường (phiếu)", mq, today_d))
        inv = db.execute(text("SELECT MAX(as_of) FROM fact_inventory")).scalar()
        rows.append(_fresh_row("Tồn kho thành phẩm (tuần)", inv, today_d))
    runs = price_repo.recent_runs(limit=1)
    art = table("Độ tươi dữ liệu theo nhóm", cols(("nhom", "Nhóm dữ liệu"),
               ("ngay_moi_nhat", "Ngày mới nhất"), ("so_ngay_tre", "Số ngày trễ")), rows)
    return {"summary": {"hom_nay": today_d.isoformat(), "cac_nhom": rows,
                        "lan_quet_gan_nhat": runs[0] if runs else None},
            "artifact": art,
            "source": "fact_price · fact_inventory · market_quote · meta_crawl_run"}


# ── Registry ──
TOOLS: dict[str, dict[str, Any]] = {
    "get_inventory_trend": {
        "run": _inventory_trend,
        "schema": {"name": "get_inventory_trend",
                   "description": "Tồn kho thành phẩm Tập đoàn theo tuần, đơn vị TẤN (biểu đồ đường: tồn kho & đã có hợp đồng). weeks = số tuần gần nhất (mặc định 26).",
                   "parameters": {"type": "object", "properties": {
                       "weeks": {"type": "integer", "description": "số tuần gần nhất (mặc định 26)"}}}}},
    "get_market_quote": {
        "run": _market_quote,
        "schema": {"name": "get_market_quote",
                   "description": "Báo giá mủ thị trường 1 ngày: so sánh 4 nhóm giá theo chủng loại SVR — xuất khẩu VRG (USD/tấn), nội địa VRG (đồng/tấn), nội địa tư nhân (đồng/tấn), xuất khẩu hàng tư nhân (đồng/tấn); kèm giá mủ tư nhân của phiếu và giá mủ tư nhân MỚI NHẤT của từng đơn vị trong 14 ngày (đồng/độ TSC, một giá hoặc khoảng giá, có ngày giá). as_of tùy chọn (YYYY-MM-DD, mặc định phiếu mới nhất).",
                   "parameters": {"type": "object", "properties": {
                       "as_of": {"type": "string", "description": "ngày phiếu YYYY-MM-DD (mặc định mới nhất)"}}}}},
    "get_raw_material_prices": {
        "run": _raw_material_prices,
        "schema": {"name": "get_raw_material_prices",
                   "description": "Giá THU MUA mủ nguyên liệu nội địa (lớp chuyên viên `vrg`, dùng cho bản tin/báo cáo) — đơn vị tính: mủ nước = đồng/độ TSC; mủ chén và mủ dây = đồng/độ DRC. Giá 0 nghĩa là 'không có giá', đã loại khỏi mọi trung bình. material ∈ {latex: mủ nước, cup: mủ chén, lace: mủ dây}. by='overall' trả xu hướng bình quân Tập đoàn (biểu đồ đường); by='company' trả bảng giá bình quân/gần nhất theo từng đơn vị thành viên.",
                   "parameters": {"type": "object", "properties": {
                       "material": {"type": "string", "enum": ["latex", "cup", "lace"],
                                   "description": "latex=mủ nước, cup=mủ chén, lace=mủ dây (mặc định latex)"},
                       "days": {"type": "integer", "description": "số ngày gần nhất (mặc định 30)"},
                       "by": {"type": "string", "enum": ["overall", "company"],
                             "description": "overall=bình quân Tập đoàn, company=theo từng đơn vị (mặc định overall)"}}}}},
    "get_latest_bulletin": {
        "run": _latest_bulletin,
        "schema": {"name": "get_latest_bulletin",
                   "description": "Bản tin/báo cáo ĐÃ PHÁT HÀNH gần nhất (đọc nháp đã lưu, KHÔNG bịa nội dung) — tiêu đề, ngày/tuần, tóm tắt nhận định chính, và danh sách vài bản gần nhất. kind='daily' (Bản tin ngày, mặc định) hoặc 'weekly' (Báo cáo tuần).",
                   "parameters": {"type": "object", "properties": {
                       "kind": {"type": "string", "enum": ["daily", "weekly"],
                               "description": "daily=bản tin ngày, weekly=báo cáo tuần (mặc định daily)"}}}}},
    "get_data_freshness": {
        "run": _data_freshness,
        "schema": {"name": "get_data_freshness",
                   "description": "Độ TƯƠI dữ liệu: ngày mới nhất + số ngày trễ của từng nhóm số liệu chính (sàn quốc tế, tỷ giá, physical, giá mủ nguyên liệu 2 lớp, báo giá mủ, tồn kho) + lần quét tự động gần nhất. DÙNG TRƯỚC khi kết luận xu hướng để biết số liệu có đang cũ hay không.",
                   "parameters": NO_ARGS}},
}
