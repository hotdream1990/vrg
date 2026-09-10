"""Gói kỹ năng "Hợp đồng & khách hàng" — cam kết · đã giao · ĐÃ KÝ CHƯA GIAO · doanh thu · khách hàng.

Số "đã ký chưa giao" là áp lực bán thực tế của Tập đoàn nên ảnh hưởng trực tiếp tới quyết định
điều chỉnh giá sàn — đó là lý do gói này tồn tại.

KHÔNG viết SQL mới: mọi số ở đây bọc lại đúng service mà màn "Hợp đồng bán hàng" đang dùng
(`sales_contract_report`, `master_contract_repo`), để không bao giờ lệch số với màn hình.
⚠ Hợp đồng có 2 CẤP (hợp đồng MẸ chỉ là hồ sơ LIÊN KẾT, không tự nó có sản lượng — phụ lục/hợp
đồng thật mới có) và một hợp đồng có thể chia thành nhiều ĐỢT GIAO con — cộng nhầm tầng là ra số
gấp đôi (xem comment quanh `_fetch`/`consumption`/`_remaining_by_grade` trong `sales_contract_report.py`).
Các hàm gốc (`deliveries`, `consumption`, `undelivered_on`, `parents_with_progress`) đã tự xử lý
đúng việc này — ở đây CHỈ gọi và trình bày lại, không tự cộng theo cách khác.
"""

from __future__ import annotations

from typing import Any

from app.core.market_meta import MASTER_CONTRACT_TYPES
from app.services import customer_repo, master_contract_repo, member_unit_merge, sales_contract_report
from app.services import unit_report_query as urq

from ._common import clamp_from, cols, days_ago, dmy, err, safe_date, table, today

#: Số hợp đồng tối đa kéo về Python để cộng THEO ĐƠN VỊ (group_by=company) — `parents_with_progress`
#: gộp TOÀN BỘ Tập đoàn đúng ở SQL cho dòng Tổng cộng, nhưng chia theo đơn vị thì phải có từng dòng.
#: 5.000 ~ toàn bộ hợp đồng hiện có; vượt trần thì báo THIẾU thay vì lặng lẽ thiếu (xem `_contract_summary`).
_ROWS_CAP = 5000

#: Nhắc lại khác biệt hay bị nhầm: "còn phải giao" ở `get_contract_summary` tính tại THỜI ĐIỂM HIỆN
#: TẠI cho các hợp đồng KÝ trong kỳ hỏi — khác ẢNH CHỤP tại một ngày cụ thể của `get_undelivered_volume`
#: (không giới hạn ngày ký). Hỏi "đã ký chưa giao tại ngày X" phải dùng đúng tool kia.
_REMAINING_NOTE = ("Cột 'còn phải giao' tính tại THỜI ĐIỂM HIỆN TẠI cho các hợp đồng KÝ trong kỳ hỏi, "
                   "KHÁC ảnh chụp một ngày cụ thể — muốn ảnh chụp thì dùng get_undelivered_volume.")


def _top(totals: dict[str, float], limit: int = 15) -> list[tuple[str, float]]:
    """Top N nhóm theo giá trị giảm dần — giữ summary gọn cho LLM (quy tắc ≤15 dòng)."""
    return sorted(totals.items(), key=lambda kv: -kv[1])[:limit]


def _resolve_company(name: str) -> str | list[str] | None:
    """Khớp tên đơn vị người dùng gõ (gõ tắt, hoặc tên đơn vị ĐÃ SÁP NHẬP) về tên hiện hành.

    Trả về `list[str]` khi gõ tắt khớp NHIỀU đơn vị — gọi nơi phải báo rõ danh sách để người hỏi
    gõ lại cho cụ thể, thay vì lặng lẽ chọn bừa một đơn vị hoặc báo chung chung "không tìm thấy".
    """
    key = name.strip().casefold()
    units = [u["name"] for u in urq.report_units()]
    for u in units:
        if u.casefold() == key:
            return u
    hits = [u for u in units if key in u.casefold()]
    if len(hits) == 1:
        return hits[0]
    if len(hits) > 1:
        return hits
    for dead, alive in member_unit_merge.rollup_map().items():
        if key == dead.casefold() or key in dead.casefold():
            return alive
    return None


# ── 1. ĐÃ KÝ HỢP ĐỒNG CHƯA GIAO (khối 3) — áp lực bán tại một ngày ────────────
def _undelivered_volume(args: dict) -> dict:
    if args.get("as_of") and not safe_date(args.get("as_of")):
        return err(f"Ngày '{args.get('as_of')}' không đúng định dạng YYYY-MM-DD.")
    as_of = safe_date(args.get("as_of")) or today()
    group_by = args.get("group_by") if args.get("group_by") in ("total", "company", "grade") else "total"

    rolled = urq.roll_by_company(sales_contract_report.undelivered_on(as_of))
    if not rolled:
        return err(f"Không có hợp đồng nào ĐÃ KÝ CHƯA GIAO tại ngày {dmy(as_of)}.")
    total_qty = round(sum(v["qty"] for v in rolled.values()), 3)
    n_hop_dong = sum(len(v["items"]) for v in rolled.values())

    top_rows: list[dict] = []
    art = None
    if group_by == "company":
        ranked = _top({k: v["qty"] for k, v in rolled.items()})
        top_rows = [{"nhom": k, "khoi_luong_tan": round(v, 3)} for k, v in ranked]
        art = table(f"Đã ký HĐ chưa giao theo đơn vị (tại {dmy(as_of)})",
                   cols(("nhom", "Đơn vị"), ("khoi_luong_tan", "Khối lượng (tấn quy khô)")), top_rows)
    elif group_by == "grade":
        by_grade: dict[str, float] = {}
        for v in rolled.values():
            for g, q in v["by_grade"].items():
                by_grade[g] = by_grade.get(g, 0.0) + q
        ranked = _top(by_grade)
        top_rows = [{"nhom": k, "khoi_luong_tan": round(v, 3)} for k, v in ranked]
        art = table(f"Đã ký HĐ chưa giao theo chủng loại (tại {dmy(as_of)})",
                   cols(("nhom", "Chủng loại"), ("khoi_luong_tan", "Khối lượng (tấn quy khô)")), top_rows)

    return {"summary": {
        "as_of": as_of, "group_by": group_by, "don_vi": "tấn quy khô",
        "tong_khoi_luong_chua_giao_tan": total_qty, "so_hop_dong_con_hang": n_hop_dong,
        "so_don_vi_con_hang": len(rolled),
        "ghi_chu": "Ảnh chụp TẠI NGÀY as_of, không cộng dồn qua ngày khác. Hợp đồng MẸ (HĐNT/HĐDH) "
                  "không tính vào đây — chỉ hợp đồng/phụ lục thật mới có sản lượng.",
        "top_nhom": top_rows or None},
            "artifact": art,
            "source": f"sales_contract_report.undelivered_on · tại {dmy(as_of)}"}


# ── 2. Các ĐỢT GIAO trong kỳ (lọc theo NGÀY GIAO) ─────────────────────────────
def _contract_deliveries(args: dict) -> dict:
    bad = next((v for v in (args.get("date_from"), args.get("date_to")) if v and not safe_date(v)), None)
    if bad:  # ngày hỏng thả xuống SQL sẽ ném lỗi kèm NGUYÊN VĂN câu truy vấn vào khung chat
        return err(f"Ngày '{bad}' không đúng định dạng YYYY-MM-DD.")
    date_from = safe_date(args.get("date_from")) or days_ago(29)
    date_to = safe_date(args.get("date_to")) or today()
    date_from = clamp_from(date_from, date_to)
    group_by = args.get("group_by") if args.get("group_by") in (
        "total", "company", "grade", "customer") else "total"

    rolled = urq.roll_by_company(sales_contract_report.consumption(date_from, date_to))
    if not rolled:
        return err(f"Không có lần giao nào trong kỳ {dmy(date_from)}–{dmy(date_to)} (lọc theo NGÀY GIAO).")
    total_qty = round(sum(v["qty"] for v in rolled.values()), 3)
    total_deliveries = sum(v["deliveries"] for v in rolled.values())
    missing = [c for c, v in rolled.items() if v["revenue"] is None]
    # Quy ước ở tool này: thiếu 1 đơn vị là tổng KHÔNG BIẾT (None), không cộng phần còn lại rồi coi
    # như đủ. Khác `get_contract_summary` (bám đúng màn hình gốc: cộng phần biết được + ghi chú) —
    # nên cả hai đều phải NÓI RÕ quy ước, không để người đọc so hai con số rồi tưởng lệch số.
    total_revenue = None if missing else round(sum(v["revenue"] for v in rolled.values()), 0)
    avg_price_trieu = (round(total_revenue / total_qty / 1_000_000, 3)
                       if total_revenue and total_qty else None)

    top_rows: list[dict] = []
    art = None
    if group_by == "company":
        ranked = _top({k: v["qty"] for k, v in rolled.items()})
        top_rows = [{"nhom": k, "san_luong_tan": round(v, 3)} for k, v in ranked]
        art = table(f"Tiêu thụ theo đơn vị ({dmy(date_from)}→{dmy(date_to)})",
                   cols(("nhom", "Đơn vị"), ("san_luong_tan", "Sản lượng (tấn quy khô)")), top_rows)
    elif group_by == "grade":
        by_grade: dict[str, float] = {}
        for v in rolled.values():
            for g, q in v["by_grade"].items():
                by_grade[g] = by_grade.get(g, 0.0) + q
        ranked = _top(by_grade)
        top_rows = [{"nhom": k, "san_luong_tan": round(v, 3)} for k, v in ranked]
        art = table(f"Tiêu thụ theo chủng loại ({dmy(date_from)}→{dmy(date_to)})",
                   cols(("nhom", "Chủng loại"), ("san_luong_tan", "Sản lượng (tấn quy khô)")), top_rows)
    elif group_by == "customer":
        by_cu: dict[str, float] = {}
        for v in rolled.values():
            for cu, d in v["by_customer"].items():
                if cu != "0":
                    by_cu[cu] = by_cu.get(cu, 0.0) + d["qty"]
        ranked = _top(by_cu)
        names = customer_repo.names_by_id(None, [int(k) for k, _ in ranked]) if ranked else {}
        top_rows = [{"nhom": names.get(int(k), f"#{k}"), "san_luong_tan": round(v, 3)} for k, v in ranked]
        art = table(f"Tiêu thụ theo khách hàng ({dmy(date_from)}→{dmy(date_to)})",
                   cols(("nhom", "Khách hàng"), ("san_luong_tan", "Sản lượng (tấn quy khô)")), top_rows)

    return {"summary": {
        "date_from": date_from, "date_to": date_to, "group_by": group_by,
        "don_vi": "sản lượng tấn quy khô · doanh thu VNĐ · đơn giá triệu đồng/tấn",
        "tong_san_luong_tan": total_qty, "so_lan_giao": total_deliveries,
        "tong_doanh_thu_vnd": total_revenue, "don_gia_binh_quan_trieu_dong_tan": avg_price_trieu,
        "quy_uoc_doanh_thu": ("Thiếu đơn giá/tỷ giá ở ít nhất một đơn vị nên tổng doanh thu là "
                              "KHÔNG BIẾT (không cộng phần còn lại rồi coi như đủ)."
                              if total_revenue is None else "Đã đủ đơn giá và tỷ giá mọi dòng."),
        "ghi_chu": "Lọc theo NGÀY GIAO (delivered_at), KHÁC ngày ký hợp đồng." + (
            f" {len(missing)} đơn vị có lần giao thiếu tỷ giá — KHÔNG cộng được tổng doanh thu, "
            "để trống thay vì đoán." if missing else ""),
        "top_nhom": top_rows or None},
            "artifact": art,
            "source": f"sales_contract_report.consumption · giao {date_from}→{date_to}"}


# ── 3. Bức tranh hợp đồng trong kỳ (lọc theo NGÀY KÝ) ─────────────────────────
def _contract_summary(args: dict) -> dict:
    bad = next((v for v in (args.get("date_from"), args.get("date_to")) if v and not safe_date(v)), None)
    if bad:  # ngày hỏng thả xuống SQL sẽ ném lỗi kèm NGUYÊN VĂN câu truy vấn vào khung chat
        return err(f"Ngày '{bad}' không đúng định dạng YYYY-MM-DD.")
    date_from = safe_date(args.get("date_from")) or days_ago(29)
    date_to = safe_date(args.get("date_to")) or today()
    date_from = clamp_from(date_from, date_to)
    group_by = args.get("group_by") if args.get("group_by") in ("total", "company") else "total"

    if group_by == "total":
        res = sales_contract_report.parents_with_progress(None, date_from=date_from, date_to=date_to, limit=1)
        if not res["total"]:
            return err(f"Không có hợp đồng nào KÝ trong kỳ {dmy(date_from)}–{dmy(date_to)}.")
        t = res["totals"]
        notes = [_REMAINING_NOTE]
        if t["revenue_missing"]:
            notes.append(f"{int(t['revenue_missing'])} hợp đồng thiếu đơn giá/tỷ giá — KHÔNG nằm "
                         "trong doanh thu hợp đồng ở trên.")
        if t["delivered_revenue_missing"]:
            notes.append(f"{int(t['delivered_revenue_missing'])} lần giao thiếu tỷ giá — KHÔNG nằm "
                         "trong doanh thu đã giao ở trên.")
        return {"summary": {
            "date_from": date_from, "date_to": date_to, "loc_theo": "ngày KÝ hợp đồng",
            "don_vi": "tấn quy khô · doanh thu VNĐ (ghi trên hợp đồng, khác tiền thực đã thu)",
            "so_hop_dong": res["total"], "tong_cam_ket_tan": round(t["qty"], 3),
            "da_giao_tan": round(t["delivered_qty"], 3), "dang_cho_giao_tan": round(t["pending_qty"], 3),
            "con_phai_giao_tan": round(t["remaining_qty"], 3),
            "giao_vuot_hop_dong_tan": round(t["over_qty"], 3) or None,
            "doanh_thu_hop_dong_vnd": round(t["revenue"], 0),
            "doanh_thu_da_giao_vnd": round(t["delivered_revenue"], 0),
            "ghi_chu": " ".join(notes)},
                "artifact": None,
                "source": f"sales_contract_report.parents_with_progress · ký {date_from}→{date_to}"}

    res = sales_contract_report.parents_with_progress(None, date_from=date_from, date_to=date_to,
                                                       limit=_ROWS_CAP)
    rows = res["rows"]
    if not rows:
        return err(f"Không có hợp đồng nào KÝ trong kỳ {dmy(date_from)}–{dmy(date_to)}.")
    agg: dict[str, dict[str, float]] = {}
    for r in rows:
        a = agg.setdefault(r["company"], {"n": 0, "qty": 0.0, "delivered_qty": 0.0,
                                          "remaining_qty": 0.0, "revenue": 0.0, "revenue_missing": 0})
        a["n"] += 1
        a["qty"] += r["qty"]
        a["delivered_qty"] += r["delivered_qty"]
        a["remaining_qty"] += r["remaining_qty"]
        if r["revenue"] is None:
            a["revenue_missing"] += 1
        else:
            a["revenue"] += r["revenue"]
    agg = urq.roll_by_company(agg)
    ranked = sorted(agg.items(), key=lambda kv: -kv[1]["qty"])[:15]
    # Cờ thiếu tỷ giá phải gắn vào TỪNG DÒNG: chỉ báo một con số tổng ở ghi chú thì người đọc so
    # doanh thu giữa các đơn vị mà không biết đơn vị nào đang bị thiếu — dễ xếp hạng nhầm.
    rows_out = [{"don_vi": k, "so_hop_dong": int(v["n"]), "cam_ket_tan": round(v["qty"], 3),
                "da_giao_tan": round(v["delivered_qty"], 3), "con_lai_tan": round(v["remaining_qty"], 3),
                "doanh_thu_vnd": round(v["revenue"], 0),
                "hd_thieu_ty_gia": int(v["revenue_missing"]) or None} for k, v in ranked]
    art = table(f"Bức tranh hợp đồng theo đơn vị (ký {dmy(date_from)}→{dmy(date_to)})",
               cols(("don_vi", "Đơn vị"), ("so_hop_dong", "Số HĐ"), ("cam_ket_tan", "Cam kết (tấn)"),
                    ("da_giao_tan", "Đã giao (tấn)"), ("con_lai_tan", "Còn lại (tấn)"),
                    ("doanh_thu_vnd", "Doanh thu (VNĐ)"),
                    ("hd_thieu_ty_gia", "HĐ thiếu tỷ giá")), rows_out)
    total_missing = sum(int(v["revenue_missing"]) for v in agg.values())
    notes = [_REMAINING_NOTE]
    if res["total"] > len(rows):
        notes.append(f"Chỉ lấy {len(rows)}/{res['total']} hợp đồng khớp kỳ (đã đạt trần truy vấn) — "
                     "số theo đơn vị có thể THIẾU, thu hẹp khoảng ngày để chính xác hơn.")
    if total_missing:
        notes.append(f"{total_missing} hợp đồng thiếu đơn giá/tỷ giá — doanh thu theo đơn vị CHƯA "
                     "gồm phần này; cột 'HĐ thiếu tỷ giá' cho biết thiếu ở đơn vị nào, đừng so "
                     "doanh thu giữa các đơn vị khi cột đó khác rỗng.")
    return {"summary": {
        "date_from": date_from, "date_to": date_to, "loc_theo": "ngày KÝ hợp đồng", "group_by": "company",
        "don_vi": "tấn quy khô · doanh thu VNĐ", "so_don_vi": len(agg), "top_nhom": rows_out,
        "ghi_chu": " ".join(notes)},
            "artifact": art,
            "source": f"sales_contract_report.parents_with_progress · ký {date_from}→{date_to}"}


# ── 4. Khách hàng lớn trong kỳ (lọc theo NGÀY GIAO) ───────────────────────────
def _top_customers(args: dict) -> dict:
    bad = next((v for v in (args.get("date_from"), args.get("date_to")) if v and not safe_date(v)), None)
    if bad:  # ngày hỏng thả xuống SQL sẽ ném lỗi kèm NGUYÊN VĂN câu truy vấn vào khung chat
        return err(f"Ngày '{bad}' không đúng định dạng YYYY-MM-DD.")
    date_from = safe_date(args.get("date_from")) or days_ago(29)
    date_to = safe_date(args.get("date_to")) or today()
    date_from = clamp_from(date_from, date_to)
    limit = max(1, min(int(args.get("limit") or 10), 30))

    rows = sales_contract_report.deliveries(date_from, date_to)
    if not rows:
        return err(f"Không có lần giao nào trong kỳ {dmy(date_from)}–{dmy(date_to)}.")
    by_cu: dict[int, dict[str, Any]] = {}
    unassigned_qty = 0.0
    for r in rows:
        cu = r.get("customer_id")
        if not cu:
            unassigned_qty += r["qty"]
            continue
        a = by_cu.setdefault(cu, {"qty": 0.0, "revenue": 0.0, "missing": False, "n": 0})
        a["qty"] += r["qty"]
        a["n"] += 1
        if r["revenue"] is None:
            a["missing"] = True
        else:
            a["revenue"] += r["revenue"]
    for a in by_cu.values():
        if a.pop("missing"):
            a["revenue"] = None

    ranked = sorted(by_cu.items(), key=lambda kv: -kv[1]["qty"])[:limit]
    names = customer_repo.names_by_id(None, [cid for cid, _ in ranked]) if ranked else {}
    top = [{"khach_hang": names.get(cid, f"#{cid}"), "san_luong_tan": round(v["qty"], 3),
           "so_lan_giao": v["n"], "doanh_thu_vnd": None if v["revenue"] is None else round(v["revenue"], 0)}
          for cid, v in ranked]
    art = table(f"Khách hàng lớn theo sản lượng ({dmy(date_from)}→{dmy(date_to)})",
               cols(("khach_hang", "Khách hàng"), ("san_luong_tan", "Sản lượng (tấn quy khô)"),
                    ("so_lan_giao", "Số lần giao"), ("doanh_thu_vnd", "Doanh thu (VNĐ)")), top)
    ghi_chu = "Lọc theo NGÀY GIAO. Doanh thu để trống ở khách hàng có lần giao thiếu tỷ giá — KHÔNG suy đoán."
    if unassigned_qty > 1e-9:
        ghi_chu += (f" {round(unassigned_qty, 3)} tấn quy khô CHƯA GÁN khách hàng, không nằm trong "
                   "bảng xếp hạng — ĐỪNG cộng vào bất kỳ khách hàng nào ở trên.")
    return {"summary": {
        "date_from": date_from, "date_to": date_to, "don_vi": "tấn quy khô · doanh thu VNĐ",
        "so_khach_hang_co_giao_dich": len(by_cu), "top_khach_hang": top,
        "san_luong_chua_gan_khach_hang_tan": round(unassigned_qty, 3) or None, "ghi_chu": ghi_chu},
            "artifact": art,
            "source": f"sales_contract_report.deliveries · giao {date_from}→{date_to}"}


# ── 5. Hợp đồng MẸ (HĐNT/HĐDH) + tiến độ ký phụ lục ───────────────────────────
def _master_contracts(args: dict) -> dict:
    company_in = str(args.get("company") or "").strip()
    limit = max(1, min(int(args.get("limit") or 10), 30))
    companies = None
    if company_in:
        resolved = _resolve_company(company_in)
        if resolved is None:
            return err(f"Không tìm thấy đơn vị khớp '{company_in}'.")
        if isinstance(resolved, list):
            return err(f"'{company_in}' khớp {len(resolved)} đơn vị ({', '.join(resolved[:5])}) "
                      "— gõ tên cụ thể hơn.")
        companies = member_unit_merge.lineage(resolved)

    res = master_contract_repo.list_masters(companies, limit=limit)
    if not res["items"]:
        scope = f" của đơn vị '{company_in}'" if company_in else ""
        return err(f"Chưa có hợp đồng mẹ nào{scope}.")
    names = customer_repo.names_by_id(
        None, sorted({m["customer_id"] for m in res["items"] if m.get("customer_id")}))

    out = []
    for m in res["items"]:
        # Đã giao/còn lại của RIÊNG hồ sơ mẹ này lấy qua `master_ids` — annexes/annex_qty đã có sẵn
        # từ `list_masters` (đúng số phụ lục ĐÃ KÝ), không cần tính lại.
        prog = sales_contract_report.parents_with_progress(None, master_ids=[m["id"]], limit=1)
        t = prog["totals"]
        out.append({
            "don_vi": m["company"], "so_hop_dong_me": m["code"],
            "loai": MASTER_CONTRACT_TYPES.get(m["master_type"], m["master_type"]),
            "khach_hang": names.get(m.get("customer_id") or 0) or "(chưa gán khách hàng)",
            "ngay_ky": dmy(m.get("sign_date")),
            "so_phu_luc_da_ky": m["annexes"], "san_luong_phu_luc_da_ky_tan": round(m["annex_qty"], 3),
            "da_giao_tan": round(t["delivered_qty"], 3), "con_lai_tan": round(t["remaining_qty"], 3)})
    art = table("Hợp đồng mẹ (HĐNT/HĐDH) + tiến độ ký phụ lục",
               cols(("don_vi", "Đơn vị"), ("so_hop_dong_me", "Số HĐ mẹ"), ("loai", "Loại"),
                    ("khach_hang", "Khách hàng"), ("ngay_ky", "Ngày ký"),
                    ("so_phu_luc_da_ky", "Số phụ lục"),
                    ("san_luong_phu_luc_da_ky_tan", "SL phụ lục đã ký (tấn)"),
                    ("da_giao_tan", "Đã giao (tấn)"), ("con_lai_tan", "Còn lại (tấn)")), out)
    return {"summary": {
        "so_ho_so_khop_loc": res["total"], "hien_thi": len(out), "don_vi": "tấn quy khô", "items": out,
        "ghi_chu": "Hợp đồng MẸ chỉ là hồ sơ liên kết, TỰ NÓ KHÔNG có sản lượng — sản lượng/tiến độ "
                  "thật nằm ở các PHỤ LỤC (hợp đồng con trỏ về hồ sơ mẹ này), xem cột 'SL phụ lục "
                  "đã ký / Đã giao / Còn lại'."},
            "artifact": art,
            "source": f"master_contract_repo.list_masters + parents_with_progress · {len(out)} hồ sơ"}


TOOLS: dict[str, dict[str, Any]] = {
    "get_undelivered_volume": {"run": _undelivered_volume, "schema": {
        "name": "get_undelivered_volume",
        "description": "QUAN TRỌNG cho tư vấn giá sàn: sản lượng ĐÃ KÝ HỢP ĐỒNG NHƯNG CHƯA GIAO (khối "
                      "3) tại MỘT NGÀY, đơn vị TẤN QUY KHÔ — đây là áp lực bán thực tế của Tập đoàn. "
                      "Ảnh chụp tại ngày hỏi, KHÔNG cộng dồn qua ngày khác.",
        "parameters": {"type": "object", "properties": {
            "as_of": {"type": "string", "description": "Ngày tính (ảnh chụp) YYYY-MM-DD, mặc định hôm nay"},
            "group_by": {"type": "string", "enum": ["total", "company", "grade"],
                        "description": "Cách chia khối lượng, mặc định total (tổng Tập đoàn)"}}}}},
    "get_contract_deliveries": {"run": _contract_deliveries, "schema": {
        "name": "get_contract_deliveries",
        "description": "Sản lượng (TẤN QUY KHÔ), doanh thu (VNĐ) và đơn giá bình quân (TRIỆU ĐỒNG/TẤN) "
                      "từ các ĐỢT GIAO thực tế trong kỳ, lọc theo NGÀY GIAO (khác ngày ký hợp đồng).",
        "parameters": {"type": "object", "properties": {
            "date_from": {"type": "string", "description": "Từ ngày GIAO YYYY-MM-DD, mặc định 30 ngày gần nhất"},
            "date_to": {"type": "string", "description": "Đến ngày GIAO YYYY-MM-DD, mặc định hôm nay"},
            "group_by": {"type": "string", "enum": ["total", "company", "grade", "customer"],
                        "description": "Cách chia sản lượng, mặc định total (tổng Tập đoàn)"}}}}},
    "get_contract_summary": {"run": _contract_summary, "schema": {
        "name": "get_contract_summary",
        "description": "Bức tranh hợp đồng bán hàng trong kỳ, lọc theo NGÀY KÝ (khác ngày giao): số "
                      "hợp đồng, tổng cam kết, đã giao, còn phải giao (TẤN QUY KHÔ), doanh thu (VNĐ).",
        "parameters": {"type": "object", "properties": {
            "date_from": {"type": "string", "description": "Từ ngày KÝ YYYY-MM-DD, mặc định 30 ngày gần nhất"},
            "date_to": {"type": "string", "description": "Đến ngày KÝ YYYY-MM-DD, mặc định hôm nay"},
            "group_by": {"type": "string", "enum": ["total", "company"],
                        "description": "Cách chia, mặc định total (tổng Tập đoàn)"}}}}},
    "get_top_customers": {"run": _top_customers, "schema": {
        "name": "get_top_customers",
        "description": "Khách hàng lớn nhất theo sản lượng (TẤN QUY KHÔ) từ các đợt giao trong kỳ "
                      "(lọc theo NGÀY GIAO), kèm doanh thu (VNĐ) và số lần giao.",
        "parameters": {"type": "object", "properties": {
            "date_from": {"type": "string", "description": "Từ ngày GIAO YYYY-MM-DD, mặc định 30 ngày gần nhất"},
            "date_to": {"type": "string", "description": "Đến ngày GIAO YYYY-MM-DD, mặc định hôm nay"},
            "limit": {"type": "integer", "description": "Số khách hàng top, mặc định 10"}}}}},
    "get_master_contracts": {"run": _master_contracts, "schema": {
        "name": "get_master_contracts",
        "description": "Danh sách hợp đồng MẸ (HĐ nguyên tắc / HĐ dài hạn) gần đây kèm tiến độ ký phụ "
                      "lục (TẤN QUY KHÔ). Hợp đồng mẹ chỉ là hồ sơ liên kết — sản lượng thật nằm ở "
                      "phụ lục, không phải ở chính hồ sơ mẹ.",
        "parameters": {"type": "object", "properties": {
            "company": {"type": "string",
                       "description": "Lọc theo đơn vị (tên đầy đủ hoặc một phần), bỏ trống = mọi đơn vị"},
            "limit": {"type": "integer", "description": "Số hồ sơ gần đây nhất, mặc định 10"}}}}},
}
