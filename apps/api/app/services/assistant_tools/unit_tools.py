"""Gói kỹ năng "Đơn vị thành viên" — thu mua · tiêu thụ · tồn kho · kế hoạch năm · tình trạng nộp.

Phục vụ tư vấn điều chỉnh giá sàn nên MỌI số phải xem được ở 3 cấp: TỔNG Tập đoàn · KHU VỰC ·
ĐƠN VỊ. Không viết SQL mới — bọc lại đúng service mà màn "Thống kê số liệu" (`unit_analytics.py`)
và Dashboard (`series.py`) đang dùng, để không bao giờ lệch số với các màn đó.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from app.services import member_unit_merge
from app.services import unit_daily_repo as udr
from app.services import unit_report_query as urq
from app.services import unit_report_rows as urr
from app.services import unit_report_status as urs
from app.services import unit_series_consumption as usc
from app.services import unit_series_purchase as usp
from app.services import unit_series_stock as uss

from ._common import clamp_from, cols, days_ago, dmy, err, num, safe_date, table, today

#: Đơn vị "độ" của giá thu mua: mủ nước tính theo TSC, mủ chén/mủ dây theo DRC (unit_report_query).
_DO_TYPE = {"latex": "TSC", "cup": "DRC", "lace": "DRC"}
_STOCK_GROUPS = ("warehouse", "structure", "region", "grade")

#: Trần doanh thu MỘT NGÀY của cả Tập đoàn — phát hiện dòng nhập sai đơn vị tính giá bán (đ/tấn
#: thay vì triệu đ/tấn ở `unit_report_rows.line_revenue_vnd`). Đo thực tế 2026: ngày cao điểm nhất
#: ~170 tỷ; đặt trần gấp ~30 lần để không bắt nhầm ngày giao lớn thật, chỉ bắt lỗi ×1.000.000 kiểu
#: đã gặp (3 dòng Cao Su Hà Tĩnh tháng 01–03/2026, xem báo cáo). LOẠI khỏi tổng + báo rõ ngày, KHÔNG
#: tự đoán số đúng thay người nhập.
REVENUE_SANITY_VND_PER_DAY = 5_000_000_000_000  # 5.000 tỷ đồng/ngày


def _sum_values(rows: list[dict]) -> dict[str, float]:
    """Cộng dồn `values` (nhóm→số) qua mọi ngày trong `rows` của chuỗi series."""
    out: dict[str, float] = {}
    for r in rows:
        for k, v in r.get("values", {}).items():
            out[k] = out.get(k, 0.0) + v
    return out


def _safe_revenue(rows: list[dict]) -> tuple[float, list[str]]:
    """Tổng doanh thu các ngày, LOẠI ngày vượt `REVENUE_SANITY_VND_PER_DAY` (nghi sai đơn vị tính).

    Trả kèm danh sách ngày bị loại để summary PHẢI nói ra — không âm thầm bỏ số liệu nghi sai.
    """
    total, bad_days = 0.0, []
    for r in rows:
        v = r.get("revenue_vnd") or 0.0
        if v > REVENUE_SANITY_VND_PER_DAY:
            bad_days.append(r["as_of"])
            continue
        total += v
    return total, bad_days


def _bad_revenue_note(bad_days: list[str]) -> str | None:
    if not bad_days:
        return None
    shown = ", ".join(dmy(d) for d in bad_days[:5]) + ("…" if len(bad_days) > 5 else "")
    return (f"{len(bad_days)} ngày có dòng doanh thu bất thường (nghi NHẬP SAI ĐƠN VỊ TÍNH giá bán) "
           f"bị LOẠI khỏi tổng, CẦN người kiểm tra chứng từ: {shown}.")


def _ranked(totals: dict[str, float], limit: int = 15) -> list[tuple[str, float]]:
    """Top N nhóm theo giá trị giảm dần — giữ summary gọn cho LLM (quy tắc ≤15 dòng)."""
    return sorted(totals.items(), key=lambda kv: -kv[1])[:limit]


# ── Tổng theo ĐƠN VỊ: phải lấy từ nguồn thô, KHÔNG qua các hàm chuỗi cho biểu đồ ──
# `unit_series_*` viết cho biểu đồ cột chồng nên `series_of` gộp cứng mọi đơn vị ngoài 8 nhóm lớn
# nhất vào bucket "Khác" (unit_series.MAX_KEYS) — hỏi đúng một đơn vị nhỏ sẽ bị trả lời "chưa có số
# liệu" dù số có thật (đo trên prod: Cao su Bình Long 407 tấn/53 ngày biến mất hoàn toàn).
# Ngoài ra phải `roll_by_company` để cộng phần của đơn vị ĐÃ SÁP NHẬP vào đơn vị hiện hành — đúng
# quy ước mọi bảng thống kê của dự án (Mang Yang → Chư Sê thiếu 126,7 tấn nếu quên).
def _purchase_by_company(date_from: str, date_to: str, material: str) -> dict[str, float]:
    qty_key = usp.MATERIALS[material][0]
    out: dict[str, float] = {}
    for e in udr.in_range("purchase", date_from, date_to, attach_contracts=False):
        qty = num(e["fields"].get(qty_key))
        if qty:                       # sản lượng 0 = "có tổ chức mua nhưng không mua được"
            out[e["company"]] = out.get(e["company"], 0.0) + qty
    return urq.roll_by_company(out)


def _consumption_by_company(date_from: str, date_to: str) -> dict[str, float]:
    out: dict[str, float] = {}
    for r in urr.consumption_rows(date_from, date_to)["rows"]:
        qty = num(r.get("qty"))
        if qty and r.get("company"):
            out[r["company"]] = out.get(r["company"], 0.0) + qty
    return urq.roll_by_company(out)


def _pick_company(totals: dict[str, float], wanted: str) -> tuple[str, float, str | None] | None:
    """Khớp tên đơn vị người dùng gõ (thường gõ tắt: 'Bình Long') với tên đầy đủ trong dữ liệu.

    Trả thêm ghi chú khi tên gõ là đơn vị ĐÃ SÁP NHẬP: số liệu của nó nay nằm ở đơn vị nhận, nói
    thẳng ra thay vì báo "không tìm thấy" (Bình Long → Lộc Ninh, Mang Yang → Chư sê…).
    """
    key = wanted.strip().casefold()
    for name, v in totals.items():
        if key == name.casefold():
            return name, v, None
    hits = [(n, v) for n, v in totals.items() if key in n.casefold()]
    if len(hits) == 1:
        return hits[0][0], hits[0][1], None
    for dead, alive in member_unit_merge.rollup_map().items():
        if key == dead.casefold() or key in dead.casefold():
            for name, v in totals.items():
                if name.casefold() == alive.casefold() or alive.casefold() in name.casefold():
                    return name, v, (f"'{dead}' đã sáp nhập vào '{alive}' — số dưới đây là của "
                                     f"đơn vị nhận, đã bao gồm phần của đơn vị cũ.")
    return None


# ── 1. Thu mua ────────────────────────────────────────────────────────────────
def _unit_purchase(args: dict) -> dict:
    bad = next((v for v in (args.get("date_from"), args.get("date_to")) if v and not safe_date(v)), None)
    if bad:  # ngày hỏng thả xuống SQL sẽ ném lỗi kèm nguyên văn câu truy vấn vào khung chat
        return err(f"Ngày '{bad}' không đúng định dạng YYYY-MM-DD.")
    date_from = safe_date(args.get("date_from")) or days_ago(29)
    date_to = safe_date(args.get("date_to")) or today()
    date_from = clamp_from(date_from, date_to)   # chặn câu hỏi kiểu "từ 2020 tới nay"
    material = args.get("material") if args.get("material") in usp.MATERIALS else "latex"
    group_by = args.get("group_by") if args.get("group_by") in ("total", "region", "company") else "region"
    label = urq.MATERIAL_LABELS.get(material, material)

    company = str(args.get("company") or "").strip()
    if company:
        group_by = "company"
    if group_by == "company":
        totals = _purchase_by_company(date_from, date_to, material)
    else:
        vol = usp.purchase_volume_series(date_from, date_to, material,
                                         "region" if group_by == "total" else group_by)
        totals = _sum_values(vol["rows"])
    total_qty = round(sum(totals.values()), 3)
    if company:
        hit = _pick_company(totals, company)
        if not hit:
            return err(f"Không tìm thấy đơn vị khớp '{company}' có số thu mua {label} trong kỳ "
                       f"{dmy(date_from)}–{dmy(date_to)}. Có {len(totals)} đơn vị có số trong kỳ này.")
        return {"summary": {"date_from": date_from, "date_to": date_to, "don_vi": hit[0],
                            "material_label": label, "san_luong_tan_quy_kho": round(hit[1], 3),
                            "ghi_chu": hit[2] or "Đã gộp số liệu của đơn vị đã sáp nhập vào đơn vị hiện hành."},
                "artifact": None,
                "source": f"unit_daily_report · thu mua {label} · {hit[0]} · {date_from}→{date_to}"}

    px = usp.purchase_series(date_from, date_to, basket="steady")
    daily = [r[material] for r in px["rows"] if r[material]["units"]]
    price = {"min": round(min(d["min"] for d in daily), 1) if daily else None,
             "max": round(max(d["max"] for d in daily), 1) if daily else None,
             "avg": round(sum(d["avg"] for d in daily) / len(daily), 1) if daily else None,
             "so_ngay_co_gia": len(daily), "don_vi": f"đồng/độ {_DO_TYPE[material]}"}

    top = _ranked(totals) if group_by != "total" else []
    art = table(f"Sản lượng thu mua {label} theo {group_by} ({date_from}→{date_to})",
               cols(("nhom", "Nhóm"), ("san_luong_tan", "Sản lượng (tấn quy khô)")),
               [{"nhom": k, "san_luong_tan": round(v, 3)} for k, v in top]) if top else None
    return {"summary": {"date_from": date_from, "date_to": date_to, "material": material,
                        "material_label": label, "group_by": group_by,
                        "tong_san_luong_tan_quy_kho": total_qty, "don_gia_thu_mua": price,
                        "so_nhom": len(totals) if group_by != "total" else None,
                        "ghi_chu": ("Đã gộp đơn vị đã sáp nhập vào đơn vị hiện hành."
                                    if group_by == "company" else None),
                        "top_nhom": [{"nhom": k, "san_luong_tan": round(v, 3)} for k, v in top] or None},
            "artifact": art,
            "source": f"unit_series_purchase · thu mua {label} · {date_from}→{date_to}"}


# ── 2. Tiêu thụ ───────────────────────────────────────────────────────────────
def _unit_consumption(args: dict) -> dict:
    bad = next((v for v in (args.get("date_from"), args.get("date_to")) if v and not safe_date(v)), None)
    if bad:  # ngày hỏng thả xuống SQL sẽ ném lỗi kèm nguyên văn câu truy vấn vào khung chat
        return err(f"Ngày '{bad}' không đúng định dạng YYYY-MM-DD.")
    date_from = safe_date(args.get("date_from")) or days_ago(29)
    date_to = safe_date(args.get("date_to")) or today()
    date_from = clamp_from(date_from, date_to)   # chặn câu hỏi kiểu "từ 2020 tới nay"
    group_by = args.get("group_by") if args.get("group_by") in ("total", "region", "company", "grade") else "region"

    company = str(args.get("company") or "").strip()
    if company:
        group_by = "company"
    rep = usc.consumption_series(date_from, date_to, "region" if group_by in ("total", "company") else group_by)
    rows = rep["rows"]
    total_qty = round(sum(r["total"] or 0.0 for r in rows), 3)
    total_revenue, bad_days = _safe_revenue(rows)
    missing = sum(r.get("revenue_missing_lines") or 0 for r in rows)
    totals = (_consumption_by_company(date_from, date_to) if group_by == "company"
              else _sum_values(rows))
    if company:
        hit = _pick_company(totals, company)
        if not hit:
            return err(f"Không tìm thấy đơn vị khớp '{company}' có số tiêu thụ trong kỳ "
                       f"{dmy(date_from)}–{dmy(date_to)}. Có {len(totals)} đơn vị có số trong kỳ này.")
        return {"summary": {"date_from": date_from, "date_to": date_to, "don_vi": hit[0],
                            "san_luong_tan": round(hit[1], 3),
                            "ghi_chu": (hit[2] or "Đã gộp số liệu của đơn vị đã sáp nhập vào đơn vị "
                                        "hiện hành.") + " Doanh thu chỉ có ở mức tổng/khu vực, "
                                       "không tách theo đơn vị ở đây."},
                "artifact": None,
                "source": f"hợp đồng bán · tiêu thụ · {hit[0]} · {date_from}→{date_to}"}

    top = _ranked(totals) if group_by != "total" else []
    art = table(f"Tiêu thụ theo {group_by} ({date_from}→{date_to})",
               cols(("nhom", "Nhóm"), ("san_luong_tan", "Sản lượng (tấn)")),
               [{"nhom": k, "san_luong_tan": round(v, 3)} for k, v in top]) if top else None
    notes = []
    if missing:
        notes.append(f"{missing} dòng bán bằng USD chưa khai tỷ giá — KHÔNG tính vào doanh thu ở trên.")
    bad_note = _bad_revenue_note(bad_days)
    if bad_note:
        notes.append(bad_note)
    return {"summary": {"date_from": date_from, "date_to": date_to, "group_by": group_by,
                        "tong_san_luong_tan": total_qty, "tong_doanh_thu_vnd": round(total_revenue, 0) or None,
                        "canh_bao_doanh_thu": " ".join(notes) or None,
                        "top_nhom": [{"nhom": k, "san_luong_tan": round(v, 3)} for k, v in top] or None},
            "artifact": art,
            "source": f"unit_series_consumption · tiêu thụ từ hợp đồng bán · {date_from}→{date_to}"}


# ── 3. Tồn kho ────────────────────────────────────────────────────────────────
def _unit_stock(args: dict) -> dict:
    if args.get("as_of") and not safe_date(args.get("as_of")):
        return err(f"Ngày '{args.get('as_of')}' không đúng định dạng YYYY-MM-DD.")
    as_of = safe_date(args.get("as_of")) or today()
    group_by = args.get("group_by") if args.get("group_by") in _STOCK_GROUPS else "structure"

    rep = uss.stock_series(as_of, as_of, group_by)
    if not rep["rows"]:
        return err(f"Chưa có số liệu tồn kho ngày {dmy(as_of)}.")
    row = rep["rows"][0]
    if not row["units_counted"]:
        return err(f"Chưa có đơn vị nào khai tồn kho ngày {dmy(as_of)} — KHÔNG lấy ảnh chụp ngày khác thay thế.")

    values = {k: round(v, 3) for k, v in row["values"].items()}
    art = table(f"Tồn kho theo {group_by} ngày {dmy(as_of)}",
               cols(("nhom", "Nhóm"), ("khoi_luong_tan", "Khối lượng (tấn)")),
               [{"nhom": k, "khoi_luong_tan": v} for k, v in values.items()])
    # LUÔN nói rõ số đơn vị có số — thiếu đơn vị mà im lặng thì người đọc tưởng tồn kho tụt (spec).
    notes = [f"{row['units_counted']} đơn vị có số liệu ngày này — nếu thấp hơn thường lệ là do "
            "thiếu đơn vị nhập, KHÔNG phải tồn kho giảm."]
    if as_of < uss.STOCK_START:
        notes.append(f"Trước {dmy(uss.STOCK_START)} dữ liệu tồn kho đơn vị chưa đủ độ phủ.")
    return {"summary": {"as_of": as_of, "group_by": group_by,
                        "tong_ton_kho_tan": row["total"], "so_don_vi_co_so_lieu": row["units_counted"],
                        "canh_bao": " ".join(notes), "co_cau": values},
            "artifact": art, "source": f"unit_series_stock · tồn kho ngày {as_of} (ảnh chụp, không cộng dồn)"}


# ── 4. Kế hoạch năm & % thực hiện ─────────────────────────────────────────────
def _unit_plan_progress(args: dict) -> dict:
    year = int(args.get("year") or today()[:4])
    group_by = args.get("group_by") if args.get("group_by") in ("region", "company") else "region"
    cur = date.fromisoformat(today())
    if year > cur.year:
        return err(f"Chưa có số liệu thực hiện cho năm {year} (năm tương lai).")

    plan_qty, plan_qty_total = urq.year_plan_by_group("plan_tonnes", group_by, None, None, year)
    plan_rev, plan_rev_total = urq.year_plan_by_group("plan_revenue_ty", group_by, None, None, year)
    # Kế hoạch doanh thu năm còn RẤT ít đơn vị khai (đo 2026: 1/67) trong khi thực hiện lấy TOÀN
    # TẬP ĐOÀN — % thực hiện vì vậy có thể vọt lên vô nghĩa (mẫu số quá hẹp), PHẢI nói rõ tỷ lệ khai.
    n_units_total = len(urq.report_units())
    n_rev_plan = sum(1 for p in udr.year_plan(year).values() if p.get("plan_revenue_ty"))

    y_from, y_to = f"{year}-01-01", (f"{year}-12-31" if year < cur.year else today())
    actual_qty: dict[str, float] = {}
    for material in usp.MATERIALS:                       # latex+cup+lace = đúng rổ so kế hoạch
        vol = usp.purchase_volume_series(y_from, y_to, material, group_by)
        for k, v in _sum_values(vol["rows"]).items():
            actual_qty[k] = actual_qty.get(k, 0.0) + v
    actual_qty_total = round(sum(actual_qty.values()), 3)

    rev = usc.consumption_series(y_from, y_to, "region")  # doanh thu chỉ tách được ở mức Tập đoàn
    actual_rev_vnd, bad_days = _safe_revenue(rev["rows"])
    actual_rev_total_ty = round(actual_rev_vnd / 1e9, 2)
    missing = sum(r.get("revenue_missing_lines") or 0 for r in rev["rows"])

    keys = sorted(set(plan_qty) | set(actual_qty))[:15]
    rows = [{"nhom": k, "ke_hoach_tan": plan_qty.get(k) or None,
            "thuc_hien_tan": round(actual_qty.get(k, 0.0), 3) or None,
            "pct_thuc_hien": round(actual_qty.get(k, 0.0) / plan_qty[k] * 100, 1) if plan_qty.get(k) else None}
           for k in keys]
    art = table(f"Kế hoạch & thực hiện thu mua {year} theo {group_by}",
               cols(("nhom", "Nhóm"), ("ke_hoach_tan", "Kế hoạch (tấn)"),
                    ("thuc_hien_tan", "Thực hiện (tấn)"), ("pct_thuc_hien", "% thực hiện")), rows)
    return {"summary": {
        "year": year, "group_by": group_by, "ky_thuc_hien": f"{y_from} → {y_to}",
        "san_luong_thu_mua": {"ke_hoach_tan_quy_kho": round(plan_qty_total, 3) or None,
                              "thuc_hien_tan_quy_kho": actual_qty_total,
                              "pct_thuc_hien": round(actual_qty_total / plan_qty_total * 100, 1)
                              if plan_qty_total else None},
        "doanh_thu": {"ke_hoach_ty_dong": round(plan_rev_total, 2) or None,
                     "thuc_hien_ty_dong_toan_tap_doan": actual_rev_total_ty,
                     "pct_thuc_hien": round(actual_rev_total_ty / plan_rev_total * 100, 1)
                     if plan_rev_total else None,
                     "ghi_chu": " ".join(filter(None, [
                         f"Doanh thu thực hiện mới tách được ở mức TOÀN TẬP ĐOÀN, chưa chia theo "
                         f"{group_by} (nguồn hiện có không đủ).",
                         f"Chỉ {n_rev_plan}/{n_units_total} đơn vị đã khai kế hoạch doanh thu năm — "
                         "% thực hiện doanh thu vì vậy CHƯA đại diện, đừng dùng để kết luận."
                         if n_rev_plan < n_units_total else None,
                         f"{missing} dòng bán USD thiếu tỷ giá chưa tính." if missing else None,
                         _bad_revenue_note(bad_days)]))},
        "top_nhom_san_luong": rows},
            "artifact": art,
            "source": f"unit_report_query.year_plan_by_group + unit_series_purchase/consumption · năm {year}"}


# ── 5. Tình trạng nộp báo cáo ─────────────────────────────────────────────────
def _submission_status(args: dict) -> dict:
    kind = args.get("kind") if args.get("kind") in ("purchase", "consumption") else "purchase"
    bad = next((v for v in (args.get("date_from"), args.get("date_to")) if v and not safe_date(v)), None)
    if bad:
        return err(f"Ngày '{bad}' không đúng định dạng YYYY-MM-DD.")
    date_from = safe_date(args.get("date_from")) or days_ago(6)
    date_to = safe_date(args.get("date_to")) or today()

    rep = urs.status_report(kind, date_from, date_to)
    totals = rep["totals"]
    all_missing = sorted((r for r in rep["rows"] if r["missing"] > 0), key=lambda r: -r["missing"])
    out = [{"don_vi": r["company"], "khu_vuc": r.get("region"), "so_ngay_thieu": r["missing"],
           "ngay_gan_nhat_da_nop": dmy(r.get("last_day")) if r.get("last_day") else "Chưa nộp lần nào"}
          for r in all_missing[:20]]
    art = table(f"Đơn vị còn thiếu báo cáo {kind} ({date_from}→{date_to})",
               cols(("don_vi", "Đơn vị"), ("khu_vuc", "Khu vực"), ("so_ngay_thieu", "Số ngày thiếu"),
                    ("ngay_gan_nhat_da_nop", "Ngày nộp gần nhất")), out)
    return {"summary": {"kind": kind, "date_from": date_from, "date_to": date_to,
                        "tong_don_vi_phai_nop": len(rep["rows"]),
                        "so_don_vi_con_thieu": len(all_missing),
                        "tong_o_thieu": totals["missing"],
                        "ty_le_da_nop_pct": round(totals["filled"] / totals["expected"] * 100, 1)
                        if totals["expected"] else None,
                        "top_don_vi_thieu": out},
            "artifact": art, "source": f"unit_report_status · {kind} · {date_from}→{date_to}"}


TOOLS: dict[str, dict[str, Any]] = {
    "get_unit_purchase": {"run": _unit_purchase, "schema": {
        "name": "get_unit_purchase",
        "description": "Sản lượng thu mua (TẤN QUY KHÔ) và đơn giá (ĐỒNG/ĐỘ TSC hoặc DRC) mủ nguyên "
                      "liệu của đơn vị thành viên. Xem tổng Tập đoàn hoặc chia theo khu vực/đơn vị.",
        "parameters": {"type": "object", "properties": {
            "date_from": {"type": "string", "description": "Từ ngày YYYY-MM-DD, mặc định 30 ngày gần nhất"},
            "date_to": {"type": "string", "description": "Đến ngày YYYY-MM-DD, mặc định hôm nay"},
            "material": {"type": "string", "enum": ["latex", "cup", "lace"],
                        "description": "Loại mủ nguyên liệu, mặc định latex (mủ nước)"},
            "group_by": {"type": "string", "enum": ["total", "region", "company"],
                        "description": "Cách chia sản lượng, mặc định region (khu vực)"},
            "company": {"type": "string", "description": "Hỏi ĐÚNG một đơn vị (gõ tên đầy đủ hoặc một phần, vd 'Bình Long') — trả riêng số của đơn vị đó, đã gộp cả đơn vị đã sáp nhập vào nó"}}}}},
    "get_unit_consumption": {"run": _unit_consumption, "schema": {
        "name": "get_unit_consumption",
        "description": "Sản lượng tiêu thụ (TẤN) và doanh thu (VNĐ) từ các lần giao hợp đồng bán hàng "
                      "của đơn vị thành viên. Xem tổng Tập đoàn hoặc chia theo khu vực/đơn vị/chủng loại.",
        "parameters": {"type": "object", "properties": {
            "date_from": {"type": "string", "description": "Từ ngày YYYY-MM-DD, mặc định 30 ngày gần nhất"},
            "date_to": {"type": "string", "description": "Đến ngày YYYY-MM-DD, mặc định hôm nay"},
            "group_by": {"type": "string", "enum": ["total", "region", "company", "grade"],
                        "description": "Cách chia sản lượng, mặc định region (khu vực)"},
            "company": {"type": "string", "description": "Hỏi ĐÚNG một đơn vị (tên đầy đủ hoặc một phần) — trả riêng sản lượng tiêu thụ của đơn vị đó, đã gộp đơn vị đã sáp nhập"}}}}},
    "get_unit_stock": {"run": _unit_stock, "schema": {
        "name": "get_unit_stock",
        "description": "Tồn kho thành phẩm (TẤN) tại MỘT NGÀY chốt (ảnh chụp, không cộng dồn) của đơn "
                      "vị thành viên. Kèm số đơn vị thực có số ngày đó — thiếu đơn vị thì phải nói rõ.",
        "parameters": {"type": "object", "properties": {
            "as_of": {"type": "string", "description": "Ngày chốt YYYY-MM-DD, mặc định hôm nay"},
            "group_by": {"type": "string", "enum": list(_STOCK_GROUPS),
                        "description": "Cách chia tồn kho, mặc định structure (đã ký/tồn tự do)"}}}}},
    "get_unit_plan_progress": {"run": _unit_plan_progress, "schema": {
        "name": "get_unit_plan_progress",
        "description": "Chỉ tiêu kế hoạch NĂM và % thực hiện: sản lượng thu mua (TẤN QUY KHÔ) chia theo "
                      "khu vực/đơn vị; doanh thu (TỶ ĐỒNG) chỉ có mức toàn Tập đoàn.",
        "parameters": {"type": "object", "properties": {
            "year": {"type": "integer", "description": "Năm kế hoạch, mặc định năm hiện tại"},
            "group_by": {"type": "string", "enum": ["region", "company"],
                        "description": "Cách chia sản lượng thu mua, mặc định region (khu vực)"}}}}},
    "get_submission_status": {"run": _submission_status, "schema": {
        "name": "get_submission_status",
        "description": "Đơn vị nào CHƯA NỘP báo cáo thu mua/tiêu thụ ngày trong một khoảng — bảng top "
                      "đơn vị thiếu nhiều ngày nhất kèm ngày nộp gần nhất.",
        "parameters": {"type": "object", "properties": {
            "kind": {"type": "string", "enum": ["purchase", "consumption"],
                     "description": "Loại báo cáo, mặc định purchase (thu mua)"},
            "date_from": {"type": "string", "description": "Từ ngày YYYY-MM-DD, mặc định 7 ngày gần nhất"},
            "date_to": {"type": "string", "description": "Đến ngày YYYY-MM-DD, mặc định hôm nay"}}}}},
}
