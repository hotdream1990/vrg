"""8 luật quét "CẢNH BÁO BẤT THƯỜNG" (admin) — chạy trực tiếp mỗi lần mở trang, không lưu bảng.

Tái dùng ĐÚNG luật nghiệp vụ đã chạy thật ở skill `bao-cao-nhap-lieu`
(`.claude/skills/bao-cao-nhap-lieu/scripts/collect.sql`, nhóm A/B/C/D/G) — không tự nghĩ lại,
tránh cảnh ba nơi báo ba số khác nhau. 3 luật mới (doanh thu · sáp nhập · ngừng nộp) viết riêng
cho màn này theo đúng đặc tả `plans/reports/anomaly-rules.md`.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from sqlalchemy import text

from app.core.db import ensure_schema, session_scope
from app.core.market_meta import PURCHASE_PRICE_TYPES, PURCHASE_SOURCE_UNIT
from app.services import member_unit_repo, unit_daily_fields, unit_daily_repo, unit_report_rows
from app.services.anomaly_types import (
    HIGH, LOW, MEDIUM, THRESHOLDS, finalize, group, vn_date, vn_num,
)

logger = logging.getLogger("vrg.anomaly_rules")

TY = 1_000_000_000
#: Hụt tồn kho quá ngần này % khi gộp sau sáp nhập thì cảnh báo (chốt cùng đợt với 8 luật này —
#: không phải ngưỡng admin sửa được ở Cấu hình hệ thống nên KHÔNG đưa vào `anomaly_types.THRESHOLDS`).
MERGE_STOCK_GAP_PCT = 10.0
#: Loại mủ nguyên liệu thu mua — dùng chung nhãn với `unit_report_rows` (DRY, khỏi định nghĩa lại).
_MATERIALS = unit_report_rows.MATERIAL_LABELS
#: (loại mủ, ô sản lượng, loại giá trong kho) — dựng từ hằng số dùng chung để thêm loại mủ mới
#: KHÔNG phải sửa ở đây. Viết tay `IN ('purchase', 'purchase_cup')` là bỏ quên MỦ DÂY: luật
#: thiếu-đơn-giá từng nêu oan Chưmomray 09/09/2026 (đã khai `purchase_lace` = 520,5 đ/độ).
_MATS = tuple((mat, qty_key, ptype) for mat, qty_key, _price_key, ptype
              in unit_report_rows.PURCHASE_MATERIALS)


def _th(thresholds: dict[str, float], key: str) -> float:
    return thresholds.get(key) or THRESHOLDS[key]["default"]


def _num(v: Any) -> float | None:
    try:
        return None if v is None else float(v)
    except (TypeError, ValueError):
        return None


def _active_units() -> list[dict[str, Any]]:
    return member_unit_repo.list_units(include_inactive=False)


def _run(builder, *args) -> dict[str, Any]:
    """Chạy 1 luật, KHÔNG để lỗi của luật này làm hỏng cả lần quét (yêu cầu #5)."""
    try:
        return builder(*args)
    except Exception:  # noqa: BLE001 — cố ý bắt mọi lỗi, đây là điểm chặn cuối
        logger.exception("Lỗi khi quét luật %s", getattr(builder, "__name__", builder))
        key = getattr(builder, "_key", "unknown")
        label = getattr(builder, "_label", key)
        return group(key, label, "Lỗi khi quét luật này — xem log server.", MEDIUM, [], [])


def _rule(key: str, label: str):
    """Decorator gắn key/label vào hàm luật, để `_run` báo đúng tên khi bắt lỗi."""
    def deco(fn):
        fn._key, fn._label = key, label
        return fn
    return deco


# ── HIGH — wrong_raw_price (nhóm B collect.sql) ───────────────────────────────────────────────
@_rule("wrong_raw_price", "Giá mủ nguyên liệu sai đơn vị tính")
def _wrong_raw_price(date_from: str, date_to: str, thresholds: dict[str, float]) -> dict[str, Any]:
    """Đơn giá mủ nước/mủ chén tự khai (`vrg_unit`) vượt trần đồng/độ — nghi gõ nhầm đồng/kg,tấn.

    KHÔNG giới hạn `date_from`: lỗi còn tồn trên hệ thống thì còn phải sửa bất kể nhập từ bao giờ
    (đúng ý `collect.sql` nhóm B) — chỉ chặn trên bởi `date_to` (không tính lỗi "trong tương lai").
    """
    ceiling = _th(thresholds, "ANOMALY_RAW_PRICE_MAX")
    label_of = {ptype: _MATERIALS[mat] for mat, _qty_key, ptype in _MATS}
    ensure_schema()
    with session_scope() as db:
        rows = db.execute(text(
            "SELECT grade AS company, price_type, max(price) AS max_price, count(*) AS n "
            "FROM fact_price WHERE source = :src AND price_type = ANY(:ptypes) "
            "AND price > :ceiling AND as_of <= CAST(:dt AS date) "
            "GROUP BY grade, price_type ORDER BY grade, price_type"),
            {"ceiling": ceiling, "dt": date_to, "src": PURCHASE_SOURCE_UNIT,
             "ptypes": list(PURCHASE_PRICE_TYPES)}).mappings().all()
    out = [{"don_vi": r["company"], "loai_mu": label_of.get(r["price_type"], r["price_type"]),
            "gia_lon_nhat_dong_do": round(r["max_price"]), "so_o_sai": r["n"]} for r in rows]
    return group("wrong_raw_price", "Giá mủ nguyên liệu sai đơn vị tính",
                f"Đơn giá mủ nguyên liệu vượt {vn_num(ceiling)} đồng/độ (mức đúng thường "
                "100–1.500) — nhiều khả năng gõ nhầm sang đồng/kg hoặc đồng/tấn.", HIGH,
                [("don_vi", "Đơn vị"), ("loai_mu", "Loại mủ"),
                 ("gia_lon_nhat_dong_do", "Giá lớn nhất (đồng/độ)"), ("so_o_sai", "Số ô sai")], out)


# ── HIGH — wrong_sale_price (nhóm C collect.sql) ──────────────────────────────────────────────
@_rule("wrong_sale_price", "Giá bán sai đơn vị tính")
def _wrong_sale_price(date_from: str, date_to: str, thresholds: dict[str, float]) -> dict[str, Any]:
    """Giá bán ở `sales_contract.lines` (KHÔNG đọc `unit_daily_report.sales*` đã chết) vượt mặt bằng.

    4 loại tiền: VND soi thẳng (đã là triệu đ/tấn); có tỷ giá thì quy MỌI ngoại tệ (USD/LAK/KHR)
    về triệu đ/tấn bằng ĐÚNG tỷ giá của dòng rồi mới soi — không áp ngưỡng USD cho LAK/KHR (bẫy
    07/09/2026). Thiếu tỷ giá thì chỉ giữ ngưỡng riêng cho USD, LAK/KHR thiếu tỷ giá KHÔNG đoán.
    Loại tiền trống mới suy theo mặc định của đơn vị (trong nước VND · nước ngoài USD).
    KHÔNG giới hạn `date_from` (lỗi tồn đọng), chặn trên bởi `date_to`.
    """
    vnd_ceiling = _th(thresholds, "ANOMALY_SALE_PRICE_MAX")
    usd_ceiling = _th(thresholds, "ANOMALY_SALE_USD_MAX")
    ensure_schema()
    sql = text("""
        SELECT company, count(*) AS n, min(d) AS d_from, max(d) AS d_to, max(price) AS max_price,
               string_agg(DISTINCT ccy, ',' ORDER BY ccy) AS ccys,
               -- VND không cần tỷ giá: chỉ báo "thiếu" với dòng ngoại tệ, kẻo lãnh đạo đơn vị đi tìm
               -- tỷ giá cho một hợp đồng tiền Việt.
               bool_or(no_fx AND ccy <> 'VND') AS missing_fx,
               string_agg(DISTINCT code, ', ' ORDER BY code) AS codes
          FROM (
            SELECT c.company,
                   COALESCE(NULLIF(c.code, ''), '(chưa có mã)') AS code,
                   COALESCE(c.delivered_at, c.start_date, c.sign_date, c.completed_at) AS d,
                   COALESCE(NULLIF(ln->>'ccy', ''),
                            CASE WHEN COALESCE(u.currency, 'VND') = 'VND' THEN 'VND'
                                 ELSE COALESCE(u.currency, 'USD') END) AS ccy,
                   (ln->>'price')::numeric AS price,
                   NULLIF(ln->>'fx', '')::numeric AS fx,
                   (ln->>'fx' IS NULL) AS no_fx
              FROM sales_contract c
              LEFT JOIN member_unit u ON u.name = c.company
              CROSS JOIN LATERAL jsonb_array_elements(COALESCE(c.lines, '[]'::jsonb)) AS ln
             WHERE (ln->>'price') ~ '^[0-9.]+$'
          ) t
         WHERE COALESCE(d, CURRENT_DATE) <= CAST(:dt AS date)
           AND CASE WHEN ccy = 'VND'    THEN price > :vnd_ceiling
                    WHEN fx IS NOT NULL THEN price * fx / 1e6 > :vnd_ceiling
                    WHEN ccy = 'USD'    THEN price > :usd_ceiling
                    ELSE false END
         GROUP BY company ORDER BY count(*) DESC, company
    """)
    with session_scope() as db:
        rows = db.execute(sql, {"dt": date_to, "vnd_ceiling": vnd_ceiling,
                                "usd_ceiling": usd_ceiling}).mappings().all()
    out = [{"don_vi": r["company"], "so_dong": r["n"],
            "tu_ngay": str(r["d_from"]) if r["d_from"] else "", "den_ngay": str(r["d_to"]) if r["d_to"] else "",
            "gia_lon_nhat": round(r["max_price"]), "loai_tien": r["ccys"],
            "thieu_ty_gia": bool(r["missing_fx"]), "ma_hop_dong": r["codes"]} for r in rows]
    return group("wrong_sale_price", "Giá bán sai đơn vị tính",
                f"Giá bán trong hợp đồng vượt {vn_num(vnd_ceiling)} triệu đ/tấn (mức đúng thường "
                "40–70) — nhiều khả năng gõ đồng thay cho triệu đồng. Giá ngoại tệ được quy đổi "
                "bằng tỷ giá ghi trên chính dòng đó.", HIGH,
                [("don_vi", "Đơn vị"), ("so_dong", "Số dòng sai"), ("tu_ngay", "Từ ngày"),
                 ("den_ngay", "Đến ngày"), ("gia_lon_nhat", "Giá lớn nhất (đang nhập, triệu đ/tấn)"),
                 ("loai_tien", "Loại tiền"), ("thieu_ty_gia", "Thiếu tỷ giá"),
                 ("ma_hop_dong", "Mã hợp đồng")], out)


# ── HIGH — revenue_outlier ─────────────────────────────────────────────────────────────────────
@_rule("revenue_outlier", "Doanh thu một ngày bất thường")
def _revenue_outlier(date_from: str, date_to: str, thresholds: dict[str, float]) -> dict[str, Any]:
    """Tổng doanh thu quy VNĐ MỘT NGÀY của cả Tập đoàn vượt trần — nghi một dòng nhập sai 1.000 lần.

    Dùng `unit_report_rows.consumption_rows` (nguồn `sales_contract` lần giao, ĐÃ xử lý đúng 4
    loại tiền — xem `_delivery_rows`) để không viết lại công thức doanh thu lần thứ hai.
    """
    ceiling_vnd = _th(thresholds, "ANOMALY_REVENUE_DAY_MAX_TY") * TY
    rows = unit_report_rows.consumption_rows(date_from, date_to)["rows"]
    by_day: dict[str, float] = {}
    top_by_day: dict[str, tuple[str, float]] = {}   # ngày → (đơn vị đóng góp lớn nhất, doanh thu)
    for r in rows:
        rev = r.get("revenue_vnd")
        if rev is None:
            continue
        day = r["as_of"]
        by_day[day] = by_day.get(day, 0.0) + rev
        cur = top_by_day.get(day)
        if cur is None or rev > cur[1]:
            top_by_day[day] = (r["company"], rev)
    out = []
    for day, total in sorted(by_day.items()):
        if total > ceiling_vnd:
            top_company, top_rev = top_by_day.get(day, ("", 0.0))
            out.append({"ngay": day, "tong_doanh_thu_ty_dong": round(total / TY, 1),
                        "don_vi": top_company,
                        "doanh_thu_don_vi_ty_dong": round(top_rev / TY, 1)})
    return group("revenue_outlier", "Doanh thu một ngày bất thường",
                f"Tổng doanh thu quy VNĐ một ngày toàn Tập đoàn vượt {vn_num(ceiling_vnd / TY)} tỷ "
                "đồng (ngày cao điểm thật ~170 tỷ) — nghi một dòng nhập giá sai 1.000 lần.", HIGH,
                [("ngay", "Ngày"), ("tong_doanh_thu_ty_dong", "Tổng doanh thu (tỷ đồng)"),
                 ("don_vi", "Đơn vị đóng góp lớn nhất"),
                 ("doanh_thu_don_vi_ty_dong", "Doanh thu đơn vị đó (tỷ đồng)")], out)


# ── HIGH — missing_merge_stock ────────────────────────────────────────────────────────────────
def _stock_sum(payload: dict | None) -> float:
    """Tổng tồn kho thành phẩm 1 bản ghi ngày = khối 1 (chưa nhập kho) + khối 2 (đã nhập kho)."""
    total = 0.0
    for block in ("stock_warehoused", "stock_not_warehoused"):
        for ln in (payload or {}).get(block) or []:
            total += _num((ln or {}).get("qty")) or 0.0
    return total


def _latest_stock(db, company: str, before: str | None, on_or_after: str | None,
                  until: str) -> tuple[str, float] | None:
    """Bản ghi tồn kho GẦN mốc nhất của 1 đơn vị — `before` (< mốc) hoặc `on_or_after` (>= mốc)."""
    if before is not None:
        row = db.execute(text(
            "SELECT as_of, payload FROM unit_daily_report WHERE company = :c AND kind = 'consumption' "
            "AND as_of < CAST(:d AS date) ORDER BY as_of DESC LIMIT 1"),
            {"c": company, "d": before}).mappings().first()
    else:
        row = db.execute(text(
            "SELECT as_of, payload FROM unit_daily_report WHERE company = :c AND kind = 'consumption' "
            "AND as_of >= CAST(:d AS date) AND as_of <= CAST(:u AS date) "
            "ORDER BY as_of ASC LIMIT 1"),
            {"c": company, "d": on_or_after, "u": until}).mappings().first()
    if not row:
        return None
    return str(row["as_of"]), _stock_sum(row["payload"])


@_rule("missing_merge_stock", "Đơn vị nhận chưa gộp tồn kho sau sáp nhập")
def _missing_merge_stock(date_from: str, date_to: str, thresholds: dict[str, float]) -> dict[str, Any]:
    """So tổng tồn kho (khối 1+2) TRƯỚC mốc sáp nhập của CẢ HAI đơn vị với SAU mốc của đơn vị nhận.

    Hụt quá `MERGE_STOCK_GAP_PCT` ⇒ đơn vị nhận chưa khai gộp kho của đơn vị đã sáp nhập vào số
    của mình. CHƯA có báo cáo nào sau mốc (đơn vị nhận chưa kịp nộp) → KHÔNG kết luận (nguyên tắc
    "không dựng dữ liệu ngày khác thay thế" — thiếu thì bỏ qua, không đoán).
    """
    ensure_schema()
    with session_scope() as db:
        pairs = db.execute(text(
            "SELECT name AS src, merged_into AS dst, merged_at FROM member_unit "
            "WHERE merged_into IS NOT NULL AND merged_at IS NOT NULL "
            "AND merged_at <= CAST(:dt AS date) ORDER BY merged_at"),
            {"dt": date_to}).mappings().all()
        out = []
        for p in pairs:
            src, dst, at = p["src"], p["dst"], str(p["merged_at"])
            before_src = _latest_stock(db, src, at, None, date_to)
            before_dst = _latest_stock(db, dst, at, None, date_to)
            after_dst = _latest_stock(db, dst, None, at, date_to)
            if not before_src or not before_dst or not after_dst:
                continue   # thiếu 1 trong 3 mốc thì không đủ căn cứ kết luận
            expected = before_src[1] + before_dst[1]
            actual = after_dst[1]
            if expected <= 0:
                continue
            gap_pct = (expected - actual) / expected * 100
            if gap_pct > MERGE_STOCK_GAP_PCT:
                out.append({
                    "don_vi": dst, "doi_tac_sap_nhap": src, "ngay_sap_nhap": at,
                    "ton_truoc_gop_tan": round(expected, 1),
                    "ton_sau_gop_tan": round(actual, 1),
                    "hut_tan": round(expected - actual, 1),
                    "hut_phan_tram": round(gap_pct, 1),
                })
    return group("missing_merge_stock", "Đơn vị nhận chưa gộp tồn kho sau sáp nhập",
                f"Tồn kho sau khi gộp hụt quá {MERGE_STOCK_GAP_PCT:.0f}% so với tổng 2 đơn vị "
                "trước sáp nhập — đơn vị nhận có thể chưa khai gộp kho của đơn vị cũ.", HIGH,
                [("don_vi", "Đơn vị nhận"), ("doi_tac_sap_nhap", "Đơn vị đã sáp nhập"),
                 ("ngay_sap_nhap", "Ngày hiệu lực"),
                 ("ton_truoc_gop_tan", "Tồn trước gộp — kỳ vọng (tấn)"),
                 ("ton_sau_gop_tan", "Tồn sau gộp — thực tế (tấn)"),
                 ("hut_tan", "Hụt (tấn)"), ("hut_phan_tram", "Hụt (%)")], out)


# ── Dữ liệu dùng chung cho not_submitted + silent_unit (1 lượt hỏi DB, 2 luật cùng đọc) ────────
def _submission_days(date_from: str, date_to: str) -> dict[str, dict[str, list[str]]]:
    """{đơn vị: {kind: [ngày ĐÃ nộp thật, tăng dần]}} — luật "đã nộp" khớp `unit_daily_fields.has_data`."""
    out: dict[str, dict[str, list[str]]] = {}
    for kind in ("purchase", "consumption"):
        for e in unit_daily_repo.in_range(kind, date_from, date_to, attach_contracts=False):
            if unit_daily_fields.has_data(kind, e["fields"]):
                out.setdefault(e["company"], {"purchase": [], "consumption": []})[kind].append(e["as_of"])
    return out


#: Ngày biểu Tiêu thụ–Tồn kho BẮT ĐẦU được thu thập trên hệ thống (tài khoản đơn vị cấp giữa 07/2026).
#: Không có mốc này thì quét từ đầu năm sẽ báo MỌI đơn vị "thiếu ~200 ngày" — số đúng mà kết luận
#: sai, và bảng cảnh báo mất hết giá trị vì đơn vị nộp đủ 100% cũng bị nêu tên.
STOCK_START = "2026-07-24"


# ── MEDIUM — not_submitted (nhóm A collect.sql) ───────────────────────────────────────────────
@_rule("not_submitted", "Chưa nộp / thiếu một phần")
def _not_submitted(date_from: str, date_to: str, thresholds: dict[str, float],
                   submitted: dict[str, dict[str, list[str]]]) -> dict[str, Any]:
    """Số ngày ĐÃ nộp so với tổng số ngày trong kỳ, theo 2 biểu — đơn vị không có KH thu mua thì
    cột Thu mua là "không áp dụng" (KHÔNG tính là thiếu), khớp `unit_daily_repo.companies_with_purchase_plan`."""
    total_days = (date.fromisoformat(date_to) - date.fromisoformat(date_from)).days + 1
    # Biểu Tồn kho có kỳ RIÊNG: chỉ tính từ ngày hệ thống bắt đầu thu thập biểu đó trở đi.
    stock_from = max(date_from, STOCK_START)
    stock_days = max(0, (date.fromisoformat(date_to) - date.fromisoformat(stock_from)).days + 1)
    year = date.fromisoformat(date_to).year
    needs_purchase = unit_daily_repo.companies_with_purchase_plan(year)
    out = []
    for u in _active_units():
        name = u["name"]
        got = submitted.get(name, {"purchase": [], "consumption": []})
        thieu_thu_mua = (total_days - len(got["purchase"])) if name in needs_purchase else 0
        # Chỉ đếm ngày tồn kho NẰM TRONG kỳ riêng của biểu đó, không đếm ngày trước khi có biểu.
        da_nop_ton = sum(1 for d in got["consumption"] if str(d) >= stock_from)
        thieu_ton_kho = stock_days - da_nop_ton
        if thieu_thu_mua <= 0 and thieu_ton_kho <= 0:
            continue
        out.append({
            "don_vi": name, "khu_vuc": u.get("region") or "",
            "bieu_thu_mua": (f"{thieu_thu_mua}/{total_days} ngày thiếu"
                            if name in needs_purchase else "Không áp dụng"),
            "bieu_ton_kho": f"{thieu_ton_kho}/{stock_days} ngày thiếu",
        })
    return group("not_submitted", "Chưa nộp / thiếu một phần",
                f"Số ngày còn thiếu của 2 biểu. Thu mua: từ {vn_date(date_from)} đến "
                f"{vn_date(date_to)} ({total_days} ngày). Tiêu thụ–Tồn kho: từ {vn_date(stock_from)} "
                f"đến {vn_date(date_to)} ({stock_days} ngày), vì biểu này bắt đầu nộp từ "
                f"{vn_date(STOCK_START)}. Đơn vị không được giao kế hoạch thu mua thì cột Thu mua "
                "ghi \"Không áp dụng\".", MEDIUM,
                [("don_vi", "Đơn vị"), ("khu_vuc", "Khu vực"),
                 ("bieu_thu_mua", "Biểu Thu mua"), ("bieu_ton_kho", "Biểu Tiêu thụ–Tồn kho")], out)


# ── MEDIUM — missing_price (nhóm D collect.sql) ───────────────────────────────────────────────
@_rule("missing_price", "Có thu mua nhưng thiếu đơn giá")
def _missing_price(date_from: str, date_to: str, thresholds: dict[str, float]) -> dict[str, Any]:
    """Ngày có tổ chức thu mua (production ≠ `no_purchase`) mà kho giá `vrg_unit` chưa có đơn giá.

    Bỏ qua loại mủ đơn vị đã KHAI RÕ "không có giá" (`unit_daily_fields.declared_no_price` — cờ
    `no_price_*` hoặc đơn giá nội tệ = 0), khác hẳn "quên khai" (chốt 07/09/2026).

    Đối chiếu THEO TỪNG LOẠI MỦ (mủ nước ↔ `purchase` · mủ chén ↔ `purchase_cup` · mủ dây ↔
    `purchase_lace`). Xét chung "ngày đó có giá nào không" như trước vừa nêu oan vừa bỏ lọt:
    ngày chỉ mua mủ dây mà đã khai giá vẫn bị nêu (Chưmomray 09/09/2026), còn ngày có giá mủ
    nước nhưng quên giá mủ chén thì lọt lưới.
    """
    ensure_schema()
    # Ô sản lượng đọc qua CASE có chốt chặn regex: payload là jsonb tự do, ép kiểu thẳng sẽ ném
    # lỗi nếu có bản ghi lỡ lưu chuỗi. Mệnh đề dựng từ `_MATS` nên thêm loại mủ là tự có mặt.
    lacks = " OR ".join(
        f"(CASE WHEN r.payload->>'{qty_key}' ~ '^[0-9.]+$' "
        f"      THEN (r.payload->>'{qty_key}')::numeric ELSE 0 END > 0 "
        f" AND NOT ('{ptype}' = ANY(COALESCE(p.have, ARRAY[]::text[]))))"
        for _mat, qty_key, ptype in _MATS)
    # Giá gom MỘT LẦN theo khoảng ngày cố định rồi LEFT JOIN — KHÔNG hỏi `fact_price` bằng truy vấn
    # con theo từng dòng. `fact_price` là hypertable (~140 chunk): truy vấn con tương quan không
    # loại được chunk lúc lập kế hoạch → chi phí ước lượng vượt ngưỡng JIT, Postgres bỏ ~5 giây
    # BIÊN DỊCH trong khi chạy thật chỉ ~20ms (đo 13/09/2026, cả trang chờ vì luật này).
    with session_scope() as db:
        rows = db.execute(text(
            "WITH p AS ("
            "  SELECT grade AS company, as_of, array_agg(DISTINCT price_type) AS have "
            "  FROM fact_price WHERE source = :src AND price_type = ANY(:ptypes) "
            "  AND as_of BETWEEN CAST(:a AS date) AND CAST(:b AS date) "
            "  GROUP BY grade, as_of) "
            "SELECT r.as_of, r.company, r.payload, COALESCE(p.have, ARRAY[]::text[]) AS have "
            "FROM unit_daily_report r "
            "LEFT JOIN p ON p.company = r.company AND p.as_of = r.as_of "
            "WHERE r.kind = 'purchase' AND r.payload <> '{}'::jsonb "
            "AND r.as_of BETWEEN CAST(:a AS date) AND CAST(:b AS date) "
            "AND COALESCE((r.payload->>'no_purchase')::bool, false) = false "
            f"AND ({lacks}) "
            "ORDER BY r.company, r.as_of"),
            {"a": date_from, "b": date_to, "src": PURCHASE_SOURCE_UNIT,
             "ptypes": list(PURCHASE_PRICE_TYPES)}).mappings().all()
    out = []
    for r in rows:
        payload = dict(r["payload"] or {})
        declared = unit_daily_fields.declared_no_price(payload)
        have = set(r["have"] or [])
        missing = {mat: _num(payload.get(qty_key)) or 0.0
                  for mat, qty_key, ptype in _MATS
                  if mat not in declared and ptype not in have
                  and (_num(payload.get(qty_key)) or 0) > 0}
        if not missing:
            continue
        out.append({"don_vi": r["company"], "ngay": str(r["as_of"]),
                    "loai_mu": ", ".join(_MATERIALS[m] for m in missing),
                    "san_luong_tan": round(sum(missing.values()), 2)})
    return group("missing_price", "Có thu mua nhưng thiếu đơn giá",
                "Ngày có sản lượng thu mua nhưng chưa nhập đơn giá của đúng loại mủ đó, và cũng "
                "chưa khai là ngày không có giá.",
                MEDIUM, [("don_vi", "Đơn vị"), ("ngay", "Ngày"), ("loai_mu", "Loại mủ thiếu giá"),
                        ("san_luong_tan", "Sản lượng (tấn)")], out)


# ── MEDIUM — silent_unit ──────────────────────────────────────────────────────────────────────
@_rule("silent_unit", "Đơn vị ngừng nộp nhiều ngày")
def _silent_unit(date_from: str, date_to: str, thresholds: dict[str, float],
                 submitted: dict[str, dict[str, list[str]]]) -> dict[str, Any]:
    """Đơn vị đang hoạt động mà KHÔNG có bản ghi nào (biểu nào cũng được) trong N ngày gần nhất."""
    silent_days = int(_th(thresholds, "ANOMALY_SILENT_DAYS"))
    until = date.fromisoformat(date_to)
    out = []
    for u in _active_units():
        name = u["name"]
        got = submitted.get(name, {"purchase": [], "consumption": []})
        last = max([*got["purchase"], *got["consumption"]], default=None)
        gap = (until - date.fromisoformat(last)).days if last else \
            (until - date.fromisoformat(date_from)).days + 1
        if gap >= silent_days:
            out.append({"don_vi": name, "khu_vuc": u.get("region") or "",
                        "ngay_nop_gan_nhat": last or "Chưa từng nộp trong kỳ",
                        "so_ngay_ngung_nop": gap})
    out.sort(key=lambda r: -r["so_ngay_ngung_nop"])
    return group("silent_unit", "Đơn vị ngừng nộp nhiều ngày",
                f"Đơn vị đang hoạt động không nộp biểu nào (Thu mua lẫn Tiêu thụ–Tồn kho) trong "
                f"{silent_days} ngày gần nhất, tính đến {vn_date(date_to)}.", MEDIUM,
                [("don_vi", "Đơn vị"), ("khu_vuc", "Khu vực"),
                 ("ngay_nop_gan_nhat", "Ngày nộp gần nhất"),
                 ("so_ngay_ngung_nop", "Số ngày ngừng nộp")], out)


# ── LOW — plan_missing (nhóm G collect.sql) ───────────────────────────────────────────────────
@_rule("plan_missing", "Kế hoạch năm khai thiếu")
def _plan_missing(date_from: str, date_to: str, thresholds: dict[str, float]) -> dict[str, Any]:
    """5 chỉ tiêu Kế hoạch năm — chỉ ô NULL mới là bỏ trống, số 0 là ĐÃ KHAI (chốt nghiệp vụ)."""
    year = date.fromisoformat(date_to).year
    fields = (("plan_tonnes", "KH thu mua"), ("plan_sales_spot_tonnes", "KH tiêu thụ HĐ chuyến"),
              ("signed_lt_tonnes", "HĐ dài hạn đã ký"),
              ("carry_lt_tonnes", "HĐ dài hạn năm trước chuyển sang"),
              ("carry_spot_tonnes", "HĐ chuyến năm trước chuyển sang"))
    ensure_schema()
    with session_scope() as db:
        plans = {r["company"]: dict(r) for r in db.execute(text(
            "SELECT * FROM unit_purchase_plan WHERE year = :y"), {"y": year}).mappings().all()}
    out = []
    for u in _active_units():
        name = u["name"]
        p = plans.get(name)
        missing = [label for key, label in fields if p is None or p.get(key) is None]
        if not missing:
            continue
        out.append({"don_vi": name, "khu_vuc": u.get("region") or "",
                    "o_con_thieu": ", ".join(missing), "so_o_thieu": len(missing)})
    return group("plan_missing", "Kế hoạch năm khai thiếu",
                f"Đơn vị chưa khai đủ 5 chỉ tiêu Kế hoạch năm {year}. Ô để trống là chưa khai; "
                "nhập số 0 vẫn tính là đã khai.", LOW,
                [("don_vi", "Đơn vị"), ("khu_vuc", "Khu vực"),
                 ("o_con_thieu", "Ô còn thiếu"), ("so_o_thieu", "Số ô thiếu")], out)


def scan(date_from: str, date_to: str, thresholds: dict[str, float]) -> dict[str, Any]:
    """Quét toàn bộ 8 luật, trả {date_from, date_to, groups, summary}. Không ném exception."""
    try:
        submitted = _submission_days(date_from, date_to)
    except Exception:  # noqa: BLE001 — lỗi ở đây không được kéo sập not_submitted lẫn silent_unit
        logger.exception("Lỗi khi đọc dữ liệu nộp báo cáo (not_submitted + silent_unit)")
        submitted = {}
    groups = [
        _run(_wrong_raw_price, date_from, date_to, thresholds),
        _run(_wrong_sale_price, date_from, date_to, thresholds),
        _run(_revenue_outlier, date_from, date_to, thresholds),
        _run(_missing_merge_stock, date_from, date_to, thresholds),
        _run(_not_submitted, date_from, date_to, thresholds, submitted),
        _run(_missing_price, date_from, date_to, thresholds),
        _run(_silent_unit, date_from, date_to, thresholds, submitted),
        _run(_plan_missing, date_from, date_to, thresholds),
    ]
    return finalize(date_from, date_to, groups)
