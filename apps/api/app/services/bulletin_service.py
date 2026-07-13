"""Bulletin service -- tạo draft từ data đã quét (fact_price DB), merge edits, xuất PDF.

In-memory draft store (MVP). Sau này chuyển sang DB khi cần lịch sử.
"""

from __future__ import annotations

import sys
from datetime import date, datetime, timedelta
from pathlib import Path

from app.core.paths import data_dir
from app.core.market_meta import (
    CANON_PHYS as _CANON_PHYS,
    CANON_WORLD as _CANON_WORLD,
    EXCHANGE_NAMES as _EXCHANGE_NAMES,
    PHYSICAL_GRADE_MAP as _PHYSICAL_GRADE_MAP,
    VRG_FLOOR_GRADES,
    WORLD_GRADE_MAP as _WORLD_GRADE_MAP,
)
from app.schemas.bulletin import (
    BulletinDraft,
    BulletinDraftUpdate,
    PhysicalPriceItem,
    RawMaterialRegion,
    SectionStatus,
    VrgFloorItem,
    WorldPriceItem,
)

# Thêm bulletin vào sys.path (cần cho xuất PDF: convert / models / pdf_export)
_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
_SERVICES = _ROOT / "services"
for sub in ["bulletin"]:
    p = str(_SERVICES / sub)
    if p not in sys.path:
        sys.path.insert(0, p)

# Map sàn/grade, tên sàn, cấu trúc canon: import từ app.core.market_meta (DRY).


def _build_raw_materials(report_date: date) -> tuple[list[RawMaterialRegion], str]:
    """Dựng 'Giá mủ nguyên liệu' GOM THEO KHU VỰC từ fact_price (source=vrg).

    Mỗi khu vực = khoảng giá min–max của các đơn vị THUỘC khu vực CÓ giá đúng ngày báo cáo.
    Đơn vị chưa gán khu vực → BỎ QUA; khu vực không có giá ngày đó → không đưa vào báo cáo.
    """
    purchase: dict[str, float] = {}
    unit_region: dict[str, str | None] = {}
    region_order: list[str] = []
    try:
        from app.services import member_region_repo, member_unit_repo, price_repo

        purchase = price_repo.purchase_by_company_on_date(report_date.isoformat())
        unit_region = {u["name"]: u.get("region") for u in member_unit_repo.list_units()}
        region_order = member_region_repo.active_names()
    except Exception as exc:  # noqa: BLE001 - DB down → để trống, admin nhập tay
        print(f"[bulletin] Không đọc được giá thu mua mủ nước: {exc}")

    items = _regions_from_purchase(purchase, unit_region, region_order)
    return items, ("db" if items else "manual")


def _regions_from_purchase(purchase: dict[str, float], unit_region: dict[str, str | None],
                           region_order: list[str]) -> list[RawMaterialRegion]:
    """Gom giá theo khu vực → khoảng min–max (1 số nếu bằng nhau).

    Bỏ đơn vị chưa gán khu vực; liệt kê theo `region_order`, chỉ khu vực CÓ giá.
    """
    by_region: dict[str, list[float]] = {}
    for company, price in purchase.items():
        region = unit_region.get(company)
        if region:
            by_region.setdefault(region, []).append(price)

    items: list[RawMaterialRegion] = []
    for region in region_order:
        prices = by_region.get(region)
        if not prices:
            continue
        lo, hi = round(min(prices)), round(max(prices))
        rng = str(lo) if lo == hi else f"{lo}-{hi}"
        items.append(RawMaterialRegion(region=region, price=float(lo), price_text=rng))
    return items


def _coerce_int(v) -> int | None:
    return int(round(v)) if v is not None else None


def _build_vrg_floor(report_date: date):
    """Section III (Giá sàn VRG) từ biểu giá Tập đoàn — 2 lần mới nhất <= ngày báo cáo.

    Trả (prev_label, curr_label, prev_items, curr_items, src). Chưa có biểu giá → khung trống.
    """
    def to_items(sch) -> list[VrgFloorItem]:
        m = {it["grade"]: it for it in sch["items"]} if sch else {}
        return [
            VrgFloorItem(grade=g, fob_usd=_coerce_int(m.get(g, {}).get("fob_usd")),
                         domestic_vnd=_coerce_int(m.get(g, {}).get("domestic_vnd")))
            for g in VRG_FLOOR_GRADES
        ]

    def label(sch) -> str | None:
        if not sch:
            return None
        d = date.fromisoformat(sch["as_of"]).strftime("%d/%m/%Y")
        title = sch.get("title") or f"lần {sch['lan']}"
        return f"Giá sàn {title}\n({d})"

    curr = prev = None
    try:
        from app.services import floor_repo

        fl = floor_repo.floor_for_bulletin(report_date.isoformat())
        curr, prev = fl["curr"], fl["prev"]
    except Exception as exc:  # noqa: BLE001 - DB down → khung trống
        print(f"[bulletin] Không đọc được Giá sàn Tập đoàn: {exc}")

    if curr:
        return label(prev), label(curr), to_items(prev), to_items(curr), "db"
    # Chưa có biểu giá nào → khung trống theo chủng loại (admin nhập ở Giá sàn Tập đoàn).
    empty = [VrgFloorItem(grade=g) for g in VRG_FLOOR_GRADES]
    return None, None, [], empty, "empty"


# Hiển thị grade trong text (LATEX → "Latex" theo template).
_GRADE_DISP = {"LATEX": "Latex"}


def _vn_num(v: int) -> str:
    """Số kiểu VN: 2644 → '2.644'."""
    return f"{v:,}".replace(",", ".")


def _build_market_text(world_prices, physical_prices) -> tuple[list[str], str]:
    """Sinh text Section IV: tóm tắt giá sàn (kèm tăng/giảm) + giá physical — đúng định dạng template.

    Sàn 1 mặt hàng (OSE/SHANGHAI) → 'Sàn X: giao dịch ở mức V usd/tấn [tăng/giảm]'.
    Sàn nhiều mặt hàng (SGX/MRB) → có tiền tố tên mặt hàng cho từng cái.
    """
    by_exc: dict[str, list] = {}
    for wp in world_prices:
        by_exc.setdefault(wp.exchange, []).append(wp)

    # Luôn 4 slot cố định (OSE/SHANGHAI/SGX/MRB) để khớp đúng vị trí template; thiếu → "".
    ex_lines: list[str] = []
    for code in ("OSE", "SHANGHAI", "SGX", "MRE"):
        rows = [r for r in by_exc.get(code, []) if r.price_curr is not None]
        if not rows:
            ex_lines.append("")
            continue
        single = len(rows) == 1
        parts: list[str] = []
        for r in rows:
            chg = ""
            if r.change_abs not in (None, 0) and r.change_pct is not None:
                d = "tăng" if r.change_abs > 0 else "giảm"
                pct = f"{abs(r.change_pct):.1f}".replace(".", ",")
                chg = f" {d} {abs(int(r.change_abs)):02d} usd/tấn ({pct}%)"
            prefix = "" if single else f"{_GRADE_DISP.get(r.grade, r.grade)} "
            parts.append(f"{prefix}giao dịch ở mức {_vn_num(r.price_curr)} usd/tấn{chg}")
        ex_lines.append(f"{_EXCHANGE_NAMES[code]}: {'; '.join(parts)};")

    pp = [p for p in physical_prices if p.price_curr is not None]
    physical = "; ".join(
        f"{_GRADE_DISP.get(p.grade, p.grade)} giao dịch ở mức {_vn_num(p.price_curr)} usd/tấn"
        for p in pp
    )
    if physical:
        physical += ";"
    return ex_lines, physical


# ── In-memory draft store (1 draft per date, MVP) ──
_drafts: dict[str, BulletinDraft] = {}

# Field text admin sửa — được lưu bền vào bulletin_draft (giá luôn dựng lại từ DB).
_EDITABLE = ("exchange_summary", "physical_summary", "market_analysis", "source_urls")



def create_draft(report_date: date, use_crawlers: bool = True) -> BulletinDraft:
    """Tạo draft bản tin từ giá THẬT đã quét (DB).

    Ngày bản tin hiển thị = ngày dữ liệu thật mới nhất <= ngày chọn (KHÔNG gắn ngày
    tương lai). Mục III/III.2/IV chưa có nguồn tự động → admin tự nhập.
    """
    prev_date = report_date - timedelta(days=1)
    date_key = report_date.isoformat()
    # Nhãn ngày hiển thị — thay bằng ngày dữ liệu THẬT nếu DB có (tránh ngày tương lai)
    report_label = report_date.strftime("%d/%m/%Y")
    prev_label = prev_date.strftime("%d/%m/%Y")

    world_prices: list[WorldPriceItem] = []
    physical_prices: list[PhysicalPriceItem] = []
    exchange_summary: list[str] = []
    has_data_on_date = False
    latest_label: str | None = None
    # 2 phiên vật chất gần nhất THẬT (ISO) — khối physical dùng ĐÚNG ngày này, không đắp giá cũ.
    phys_curr_iso: str | None = None
    phys_prev_iso: str | None = None

    if use_crawlers:
        try:
            from app.services import price_repo

            # Mỗi (source, grade) lấy 2 bản ghi mới nhất <= ngày bản tin → luôn ưu tiên
            # giá THẬT sẵn có (không cần các sàn trùng ngày). Chỉ dùng mẫu khi DB trống.
            db_rows = price_repo.latest_two_for_bulletin(report_date.isoformat())

            if db_rows:
                from bulletin.convert import (
                    cny_tonne_to_usd_tonne,
                    jpy_kg_to_usd_tonne,
                    usd_kg_to_usd_tonne,
                    uscents_kg_to_usd_tonne,
                )

                # Group by (source, grade) -> {as_of: (price, unit)}. FX quy đổi theo NGÀY riêng.
                price_map: dict[tuple[str, str], dict[str, tuple[float, str]]] = {}
                for row in db_rows:
                    if row["source"] == "fx":
                        continue  # FX dùng tỷ giá ĐÚNG NGÀY (fx_series bên dưới), không last-wins
                    price_map.setdefault((row["source"], row["grade"]), {})[str(row["as_of"])] = (
                        float(row["price"]), row.get("unit", "")
                    )

                # Tỷ giá theo NGÀY → mỗi giá quy đổi bằng tỷ giá ĐÚNG ngày nó, KHỚP "Bảng tính giá".
                # KHÔNG carry-forward (không đắp tỷ giá ngày khác dựng số cho ngày này) — thiếu tỷ giá
                # đúng ngày thì giá đó không quy đổi (để trống), không lấy ngày gần nhất/cũ nhất.
                fx_by_day: dict[str, dict[str, float]] = {}
                fx_from = (report_date - timedelta(days=150)).isoformat()
                for r in price_repo.prices_since(["fx"], date_from=fx_from, date_to=report_date.isoformat()):
                    fx_by_day.setdefault(r["grade"], {})[str(r["as_of"])] = float(r["price"])

                def _fx_at(pair: str, d: str) -> float | None:
                    """Tỷ giá ĐÚNG NGÀY d — KHÔNG carry-forward. Thiếu → None (giá đó không quy đổi)."""
                    return fx_by_day.get(pair, {}).get(d)

                def _convert_to_usd_tonne(price: float, unit: str, as_of: str) -> int | None:
                    """Quy đổi giá gốc → USD/tấn dùng tỷ giá của ĐÚNG ngày `as_of`."""
                    if unit == "US$/kg":
                        return usd_kg_to_usd_tonne(price)
                    if unit == "US cents/kg":
                        return uscents_kg_to_usd_tonne(price)
                    if unit == "Sen/kg":
                        rate = _fx_at("USD/MYR", as_of)
                        return round(price * 10 / rate) if rate else None
                    if unit == "CNY/tonne":
                        rate = _fx_at("USD/CNY", as_of)
                        return cny_tonne_to_usd_tonne(price, rate) if rate else None
                    if unit == "JPY/kg":
                        rate = _fx_at("USD/JPY", as_of)
                        return jpy_kg_to_usd_tonne(price, rate) if rate else None
                    return round(price)

                real_dates = sorted({d for dp in price_map.values() for d in dp})
                latest_label = (
                    date.fromisoformat(real_dates[-1]).strftime("%d/%m/%Y")
                    if real_dates else None
                )
                # Chỉ tạo bản tin cho ĐÚNG ngày chọn; ngày đó không có giá thật thì để trống.
                has_data_on_date = report_date.isoformat() in real_dates
                t_str = report_date.isoformat()
                if not has_data_on_date:
                    price_map = {}  # không lấy data ngày khác thay thế

                # Giá vật chất LẤY ĐÚNG NGÀY BÁO CÁO — ngày đó không có giá reuters thì để trống
                # ("không có"), KHÔNG lùi về phiên cũ. prev = phiên reuters gần nhất TRƯỚC ngày
                # báo cáo (chỉ để tính +/-).
                _reuters_dates = sorted({d for (s, _g), dp in price_map.items() if s == "reuters"
                                         for d in dp})
                phys_curr_iso = t_str
                phys_prev_iso = max((d for d in _reuters_dates if d < t_str), default=None)
                # Giá thế giới: phiên thế giới liền trước ngày báo cáo (để so + gắn nhãn cột prev
                # cho đúng phiên, kể cả khi report_date-1 rơi vào cuối tuần).
                _world_dates = sorted({d for (s, g), dp in price_map.items()
                                       if _WORLD_GRADE_MAP.get((s, g)) for d in dp})
                world_prev_iso = max((d for d in _world_dates if d < t_str), default=None)
                if world_prev_iso:
                    prev_label = date.fromisoformat(world_prev_iso).strftime("%d/%m/%Y")

                world_computed: dict = {}
                phys_computed: dict = {}
                for (src, grade), date_prices in price_map.items():
                    mapping = _WORLD_GRADE_MAP.get((src, grade))
                    if mapping:
                        # curr = ĐÚNG ngày báo cáo (thiếu → "—", vd OSE chưa có phiên) — KHÔNG lùi
                        # về phiên cũ; prev = phiên thế giới liền trước để so & tính +/-.
                        wc = date_prices.get(t_str)
                        wp = date_prices.get(world_prev_iso) if world_prev_iso else None
                        curr_int = _convert_to_usd_tonne(*wc, t_str) if wc else None
                        prev_int = _convert_to_usd_tonne(*wp, world_prev_iso) if wp else None
                        chg = (curr_int - prev_int) if (curr_int and prev_int) else None
                        pct = round(chg / prev_int * 100, 1) if (chg is not None and prev_int) else None
                        exchange, blt_grade = mapping
                        world_computed[(exchange, blt_grade)] = WorldPriceItem(
                            exchange=exchange, grade=blt_grade,
                            price_prev=prev_int, price_curr=curr_int,
                            change_abs=chg, change_pct=pct,
                        )

                    if src == "reuters":
                        phys_grade = _PHYSICAL_GRADE_MAP.get(grade)
                        # curr = ĐÚNG ngày báo cáo (thiếu → "—", KHÔNG đắp phiên cũ vào cột này);
                        # prev = phiên liền trước để so. Hiện dòng nếu CÓ giá ở curr HOẶC prev.
                        ce = date_prices.get(phys_curr_iso) if phys_grade else None
                        pe = date_prices.get(phys_prev_iso) if (phys_grade and phys_prev_iso) else None
                        if phys_grade and (ce is not None or pe is not None):
                            cv = _convert_to_usd_tonne(*ce, phys_curr_iso) if ce else None
                            pv = _convert_to_usd_tonne(*pe, phys_prev_iso) if pe else None
                            pchg = (cv - pv) if (cv and pv) else None
                            ppct = round(pchg / pv * 100, 1) if (pchg is not None and pv) else None
                            phys_computed[phys_grade] = PhysicalPriceItem(
                                grade=phys_grade, price_prev=pv, price_curr=cv,
                                change_abs=pchg, change_pct=ppct,
                            )

                # Dựng ĐÚNG cấu trúc template: đủ dòng, đúng thứ tự; thiếu data → để trống (N/A).
                if has_data_on_date:
                    world_prices = [
                        world_computed.get(k)
                        or WorldPriceItem(exchange=k[0], grade=k[1])
                        for k in _CANON_WORLD
                    ]
                    # Chỉ dựng bảng vật chất khi CÓ giá đúng ngày báo cáo; không có → để trống ("không có").
                    if phys_computed:
                        physical_prices = [
                            phys_computed.get(g) or PhysicalPriceItem(grade=g)
                            for g in _CANON_PHYS
                        ]

        except Exception as exc:
            print(f"[bulletin] DB read error (dùng sample data): {exc}")

    # Section IV — tự sinh text tóm tắt giá sàn + physical (đúng định dạng template).
    exchange_summary, physical_summary = _build_market_text(world_prices, physical_prices)

    # Giá mủ nguyên liệu (giá thu mua mủ nước) theo công ty VRG — đọc từ fact_price (source=vrg).
    raw_materials, rm_src = _build_raw_materials(report_date)
    # Giá sàn VRG (Section III) — đọc từ biểu giá Tập đoàn (2 lần mới nhất <= ngày báo cáo).
    fl_prev_label, fl_curr_label, fl_prev, fl_curr, fl_src = _build_vrg_floor(report_date)

    # Chỉ dùng giá THẬT đúng ngày chọn; không có thì báo rõ "không có dữ liệu".
    world_src = "db" if world_prices else "empty"
    # Physical: "db" chỉ khi có giá vật chất thật (không chỉ vì list đủ dòng khung).
    phys_src = "db" if any(p.price_curr is not None for p in physical_prices) else "empty"
    phys_prev_label = date.fromisoformat(phys_prev_iso).strftime("%d/%m/%Y") if phys_prev_iso else prev_label
    phys_curr_label = date.fromisoformat(phys_curr_iso).strftime("%d/%m/%Y") if phys_curr_iso else report_label
    phys_stale = phys_curr_iso is not None and phys_curr_iso < report_date.isoformat()
    if has_data_on_date:
        _empty = "Chưa có dữ liệu — hãy chạy Quét Đa sàn"
    elif latest_label:
        _empty = f"Không có dữ liệu cho ngày {report_label} (mới nhất: {latest_label})"
    else:
        _empty = f"Không có dữ liệu cho ngày {report_label} — hãy chạy Quét Đa sàn"

    data_sources = [
        SectionStatus(
            section="I. Giá CSTN thế giới",
            source=world_src,
            description="TOCOM, SHFE, SGX, MRB \u2014 đọc từ DB (Quét Đa Sàn)"
            if world_src == "db"
            else _empty,
        ),
        SectionStatus(
            section="II. Giá vật chất (Reuters)",
            source=phys_src,
            description=(
                f"RSS3, STR20, SMR20, SIR20 \u2014 phiên vật chất gần nhất {phys_curr_label}"
                + (f" (cũ hơn ngày báo cáo {report_label})" if phys_stale else "")
            )
            if phys_src == "db"
            else _empty,
        ),
        SectionStatus(
            section="III. Giá sàn VRG",
            source=fl_src,
            description="Biểu giá Tập đoàn (2 lần mới nhất) — đọc từ DB"
            if fl_src == "db"
            else "Chưa có biểu giá — nhập ở 'Giá sàn Tập đoàn' (Quản lý số liệu)",
        ),
        SectionStatus(
            section="III.2 Giá mủ nguyên liệu",
            source=rm_src,
            description="Giá thu mua mủ nước theo công ty VRG — đọc từ DB (source=vrg)"
            if rm_src == "db"
            else "Chưa có giá thu mua — nhập ở 'Giá mủ nguyên liệu' (Quản lý số liệu)",
        ),
        SectionStatus(
            section="IV. Phân tích thị trường",
            source="manual",
            description="Chưa tích hợp AI \u2014 admin tự viết/chỉnh sửa",
        ),
    ]

    draft = BulletinDraft(
        report_date=report_label,
        prev_date=prev_label,
        world_prices=world_prices,
        physical_prices=physical_prices,
        physical_prev_label=phys_prev_label,
        physical_curr_label=phys_curr_label,
        physical_stale=phys_stale,
        vrg_floor_prev_label=fl_prev_label or "Lần trước (chưa có)",
        vrg_floor_curr_label=fl_curr_label or f"Giá sàn ({report_label})",
        vrg_floor_prev=fl_prev,
        vrg_floor_curr=fl_curr,
        raw_materials=raw_materials,
        exchange_summary=exchange_summary,
        physical_summary=physical_summary,
        market_analysis=[],
        source_urls=[],
        data_sources=data_sources,
    )

    # Áp overrides admin đã lưu (nếu có) → mở lại thấy đúng phần đã sửa; giá vẫn dựng mới từ DB.
    try:
        from app.services import draft_repo
        overrides = draft_repo.get_overrides(date_key)
    except Exception as exc:  # noqa: BLE001 - DB down → bỏ qua, dùng bản vừa dựng
        print(f"[bulletin] Không đọc được nháp đã lưu: {exc}")
        overrides = None
    if overrides:
        for f in _EDITABLE:
            if overrides.get(f) is not None:
                setattr(draft, f, overrides[f])

    _drafts[date_key] = draft
    return draft


def get_draft(report_date: date) -> BulletinDraft | None:
    return _drafts.get(report_date.isoformat())


def update_draft(report_date: date, updates: BulletinDraftUpdate) -> BulletinDraft:
    """Merge admin edits vào draft + LƯU BỀN vào DB (bulletin_draft). Tự dựng lại draft từ DB
    nếu bộ nhớ chưa có (restart / phiên khác) → Lưu luôn chạy, giữ nguyên text admin."""
    draft = _drafts.get(report_date.isoformat()) or create_draft(report_date)

    for field, value in updates.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(draft, field, value)

    _drafts[report_date.isoformat()] = draft
    try:
        from app.services import draft_repo
        draft_repo.save_draft(report_date.isoformat(), {f: getattr(draft, f) for f in _EDITABLE})
    except Exception as exc:  # noqa: BLE001 - DB down → vẫn giữ nháp trong RAM
        print(f"[bulletin] Không lưu được nháp vào DB: {exc}")
    return draft


def list_saved_drafts() -> list[dict]:
    """Danh sách nháp đã lưu (cho trang danh sách bản tin)."""
    from app.services import draft_repo
    return draft_repo.list_drafts()


def delete_saved_draft(report_date: date) -> int:
    """Xoá nháp 1 ngày (DB + bộ nhớ)."""
    _drafts.pop(report_date.isoformat(), None)
    from app.services import draft_repo
    return draft_repo.delete_draft(report_date.isoformat())


def _draft_to_bulletin_data(draft: BulletinDraft):
    """Convert BulletinDraft (API) → BulletinData (dùng cho xuất PDF)."""
    from bulletin.models import BulletinData, PhysicalPriceRow, VrgFloorRow, WorldPriceRow

    rdate = datetime.strptime(draft.report_date, "%d/%m/%Y").date()
    pdate = datetime.strptime(draft.prev_date, "%d/%m/%Y").date()

    def _pdate(label: str):
        try:
            return datetime.strptime(label, "%d/%m/%Y").date()
        except (ValueError, TypeError):
            return None

    return BulletinData(
        report_date=rdate,
        prev_date=pdate,
        physical_prev_date=_pdate(draft.physical_prev_label),
        physical_curr_date=_pdate(draft.physical_curr_label),
        world_prices=[
            WorldPriceRow(exchange=w.exchange, grade=w.grade, unit=w.unit,
                          price_prev=w.price_prev, price_curr=w.price_curr)
            for w in draft.world_prices
        ],
        physical_prices=[
            PhysicalPriceRow(grade=p.grade, price_prev=p.price_prev, price_curr=p.price_curr)
            for p in draft.physical_prices
        ],
        vrg_floor_prev_label=draft.vrg_floor_prev_label,
        vrg_floor_curr_label=draft.vrg_floor_curr_label,
        vrg_floor_prev=[VrgFloorRow(**v.model_dump()) for v in draft.vrg_floor_prev],
        vrg_floor_curr=[VrgFloorRow(**v.model_dump()) for v in draft.vrg_floor_curr],
        raw_material_regions={rm.region: rm.price_text for rm in draft.raw_materials},
        market_exchange_summary=draft.exchange_summary,
        market_physical_summary=draft.physical_summary,
        market_analysis=draft.market_analysis,
        source_urls=draft.source_urls,
    )


def _save_snapshot(output: Path, draft: BulletinDraft) -> None:
    """Lưu snapshot JSON cạnh file xuất để trang chi tiết đọc lại."""
    try:
        output.with_suffix(".json").write_text(draft.model_dump_json(indent=2), encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        print(f"[bulletin] Không lưu được snapshot JSON: {exc}")


def generate_pdf_from_draft(report_date: date) -> Path | None:
    """Generate PDF từ draft (HTML → Chromium → PDF: nhảy trang + header/footer lặp)."""
    from bulletin.pdf_export import generate_pdf

    draft = _drafts.get(report_date.isoformat()) or create_draft(report_date)
    data = _draft_to_bulletin_data(draft)
    date_str = data.report_date.strftime("%d-%m-%Y")
    output = data_dir() / f"bulletins/Ban-tin-ngay-{date_str}.pdf"
    output.parent.mkdir(parents=True, exist_ok=True)
    result = generate_pdf(data, _resolve_assets(), output)
    if result:
        _save_snapshot(output, draft)
    return result


# ── Image assets (bìa/banner/logo) dùng cho PDF ──

# Các slot ảnh của bản tin (custom ghi đè default nếu có).
_ASSET_SLOTS = ("cover-front", "cover-back", "header-banner", "footer-banner", "logo-vrg")


def _resolve_assets() -> dict[str, str]:
    """slot → đường dẫn ảnh active (custom nếu có, ngược lại default) — dùng cho PDF."""
    assets_dir = data_dir() / "bulletin-assets"
    custom_dir = assets_dir / "custom"
    out: dict[str, str] = {}
    for slot in _ASSET_SLOTS:
        p = _find_asset(custom_dir, slot) or _find_asset(assets_dir, slot)
        if p:
            out[slot] = str(p)
    return out


def _find_asset(directory: Path, slot: str) -> Path | None:
    """Find image file by slot name in directory (any supported extension)."""
    if not directory.exists():
        return None
    for ext in (".jpg", ".jpeg", ".png", ".webp"):
        p = directory / f"{slot}{ext}"
        if p.exists():
            return p
    return None
