"""Gói kỹ năng "Số liệu nội bộ Tập đoàn" cho Trợ lý AI.

Bọc: tồn kho thành phẩm · báo giá mủ thị trường (đủ các nhóm giá, không chỉ xuất khẩu VRG) ·
giá mủ nguyên liệu (mủ nước/chén/dây, lớp chuyên viên `vrg`) · bản tin/báo cáo phát hành gần
nhất · độ tươi dữ liệu (chống trả lời trên số cũ mà không cảnh báo).
"""
from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import text

from app.core import edit_window
from app.core.db import session_scope
from app.core.market_meta import PURCHASE_PRICE_UNIT, PURCHASE_SOURCE_HQ
from app.services import (
    bulletin_service, draft_repo, floor_recommend, floor_repo, inventory_daily, market_quote_repo,
    price_repo, weekly_report_service,
)
from app.services.assistant_tools._common import (
    NO_ARGS, clamp_days, cols, days_ago, dm, dmy, err, line, pct, table, today,
)

# ── get_inventory_trend: tồn kho THEO NGÀY từ biểu Tồn kho đơn vị (bỏ chuỗi tuần 24/09/2026) ──
#: Hướng tồn kho so với lần ban hành (luật chung `floor_recommend.inventory_lean`, ngưỡng ±3%) → câu
#: đọc nguyên văn, không để LLM tự suy dấu.
_LEAN_TEXT = {"up": "tồn kho tăng → nghiêng GIỮ/HẠ giá sàn", "down": "tồn kho giảm → ủng hộ NÂNG giá sàn",
              "flat": "đi ngang (trong ±3%) → không nghiêng", "mixed": "tổng và tự do trái chiều → không nghiêng"}
def _inventory_trend(args: dict) -> dict:
    days = clamp_days(args.get("days"), 60)
    # Mốc so sánh quan trọng nhất cho tư vấn giá sàn = lần ban hành gần nhất. Đo thực tế: chỉ có "đầu
    # kỳ 60 ngày" thì LLM gọi nhầm nó là "lần ban hành trước" (nói tồn kho +53% so với 25/08).
    sched = floor_repo.list_schedules(date_to=today())
    issued = str(sched[0]["as_of"]) if sched else None
    start = min(days_ago(days), issued) if issued else days_ago(days)
    snaps = inventory_daily.load(start, today())
    ser = [(d, v) for d, v in inventory_daily.series(snaps) if d >= days_ago(days)]
    if not ser:
        return err(f"Không có ngày nào đủ đơn vị nhập tồn kho trong {days} ngày gần nhất "
                   "(xem get_data_freshness để biết ngày có số mới nhất).")
    first, last = ser[0][0], ser[-1][0]
    # Cùng 1 hàm với màn Gợi ý giá sàn: % thay đổi chỉ trên đơn vị có số cả 2 ngày.
    inv = inventory_daily.at(snaps, last, first) or {}
    vs_issue = inventory_daily.at(snaps, last, issued) if issued else None
    lean = floor_recommend.inventory_lean(vs_issue)
    art = line(f"Tồn kho thành phẩm Tập đoàn theo ngày ({len(ser)} ngày)", [dm(d) for d, _ in ser],
               [{"name": "Tồn kho", "values": [round(v, 1) for _, v in ser]}], "tấn")
    return {"summary": {
        "ngay_gan_nhat": last, "ton_kho_tan": inv.get("ton_kho"),
        "da_ky_hd_chua_giao_tan": inv.get("ton_kho_hd"), "ton_tu_do_tan": inv.get("ton_free"),
        "so_don_vi_co_so_lieu": inv.get("units_counted"), "so_ngay": len(ser),
        "so_voi_lan_ban_hanh_gan_nhat": None if not vs_issue or not vs_issue.get("base_day") else {
            "ngay_ban_hanh": issued, "ngay_so_lieu_moc": vs_issue["base_day"],
            "ton_kho_tan": vs_issue["d_ton_kho"], "ton_kho_pct": vs_issue["d_ton_kho_pct"],
            "ton_tu_do_tan": vs_issue["d_free"], "ton_tu_do_pct": vs_issue["d_free_pct"],
            "so_don_vi_so_sanh": vs_issue["units_compared"],
            "tham_chieu_gia_san": _LEAN_TEXT[lean["direction"]] if lean else None},
        "thay_doi_tu_ngay_dau_ky": {"tu_ngay": first, "tan": inv.get("d_ton_kho"),
                                    "pct": inv.get("d_ton_kho_pct"),
                                    "so_don_vi_so_sanh": inv.get("units_compared")},
        "ghi_chu": f"Số theo ngày cộng từ biểu Tồn kho đơn vị (đã + chưa nhập kho), có từ "
                   f"{dmy(inventory_daily.STOCK_START)}. Tổng mỗi ngày phụ thuộc số đơn vị nhập; "
                   "% thay đổi chỉ tính trên đơn vị có số ở cả hai ngày. 'thay_doi_tu_ngay_dau_ky' là so "
                   "với NGÀY ĐẦU của khoảng tra cứu, KHÔNG phải lần ban hành giá sàn — so với lần ban hành "
                   "thì dùng 'so_voi_lan_ban_hanh_gan_nhat'."},
        "artifact": art, "source": f"biểu Tồn kho đơn vị · {len(ser)} ngày"}


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
    # Ngày tồn kho mới nhất ĐỦ đơn vị nhập (ngày đang nhập dở không tính là "tươi"). Quét 30 ngày
    # là đủ cho ca thường; chỉ khi cả tháng không có số mới quét lại từ đầu để nói đúng ngày cuối.
    inv_day = (max(inventory_daily.load(days_ago(30), today()), default=None)
               or max(inventory_daily.load(), default=None))
    rows.append(_fresh_row("Tồn kho thành phẩm (biểu đơn vị, theo ngày)",
                           date.fromisoformat(inv_day) if inv_day else None, today_d))
    runs = price_repo.recent_runs(limit=1)
    art = table("Độ tươi dữ liệu theo nhóm", cols(("nhom", "Nhóm dữ liệu"),
               ("ngay_moi_nhat", "Ngày mới nhất"), ("so_ngay_tre", "Số ngày trễ")), rows)
    return {"summary": {"hom_nay": today_d.isoformat(), "cac_nhom": rows,
                        "lan_quet_gan_nhat": runs[0] if runs else None},
            "artifact": art,
            "source": "fact_price · biểu Tồn kho đơn vị · market_quote · meta_crawl_run"}


# ── Registry ──
TOOLS: dict[str, dict[str, Any]] = {
    "get_inventory_trend": {
        "run": _inventory_trend,
        "schema": {"name": "get_inventory_trend",
                   "description": "Tồn kho thành phẩm Tập đoàn THEO NGÀY, đơn vị TẤN, cộng từ biểu Tồn kho đơn vị thành viên (có từ 24/07/2026): biểu đồ đường tồn kho + số mới nhất (đã ký HĐ chưa giao, tồn tự do) + thay đổi SO VỚI LẦN BAN HÀNH GIÁ SÀN GẦN NHẤT (tổng + tự do, kèm hướng tham chiếu) + thay đổi từ đầu khoảng tra cứu. days = số ngày gần nhất (mặc định 60).",
                   "parameters": {"type": "object", "properties": {
                       "days": {"type": "integer", "description": "số ngày gần nhất (mặc định 60)"}}}}},
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
