"""Bulletin service -- tạo draft từ data đã quét (fact_price DB), merge edits, generate PPTX.

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
    VRG_COMPANIES,
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

# Thêm bulletin vào sys.path (cần cho generate PPTX)
_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
_SERVICES = _ROOT / "services"
for sub in ["bulletin"]:
    p = str(_SERVICES / sub)
    if p not in sys.path:
        sys.path.insert(0, p)

# Map sàn/grade, tên sàn, cấu trúc canon: import từ app.core.market_meta (DRY).


def _build_raw_materials(report_date: date) -> tuple[list[RawMaterialRegion], str]:
    """Dựng 'Giá mủ nguyên liệu' theo công ty VRG từ fact_price (source=vrg).

    Trả (danh sách RawMaterialRegion theo VRG_COMPANIES, nguồn 'db'|'manual').
    CHỈ lấy giá ĐÚNG ngày báo cáo — công ty không có giá ngày đó sẽ không hiện.
    """
    purchase: dict[str, float] = {}
    companies: list[str] = list(VRG_COMPANIES)
    try:
        from app.services import member_unit_repo, price_repo

        purchase = price_repo.purchase_by_company_on_date(report_date.isoformat())
        companies = member_unit_repo.active_names() or companies
    except Exception as exc:  # noqa: BLE001 - DB down → để trống, admin nhập tay
        print(f"[bulletin] Không đọc được giá thu mua mủ nước: {exc}")

    # CHỈ liệt kê đơn vị CÓ giá (theo thứ tự đơn vị thành viên); đơn vị trống bị bỏ qua.
    items = [
        RawMaterialRegion(
            region=co,
            price=purchase[co],
            price_text=f"{int(round(purchase[co])):,}",
        )
        for co in companies
        if co in purchase
    ]
    return items, ("db" if purchase else "manual")


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
        return f"Giá sàn lần {sch['lan']}\n({d})"

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

                # Group by (source, grade) -> {as_of: (price, unit)}
                price_map: dict[tuple[str, str], dict[str, tuple[float, str]]] = {}
                fx_rates: dict[str, float] = {}

                for row in db_rows:
                    src = row["source"]
                    grade = row["grade"]
                    as_of = str(row["as_of"])
                    price = float(row["price"])
                    unit = row.get("unit", "")

                    if src == "fx":
                        fx_rates[grade] = price
                        continue

                    key = (src, grade)
                    if key not in price_map:
                        price_map[key] = {}
                    price_map[key][as_of] = (price, unit)

                def _convert_to_usd_tonne(price: float, unit: str) -> int | None:
                    """Convert price in original unit -> USD/tonne."""
                    if unit == "US$/kg":
                        return usd_kg_to_usd_tonne(price)
                    if unit == "US cents/kg":
                        return uscents_kg_to_usd_tonne(price)
                    if unit == "Sen/kg":
                        rate = fx_rates.get("USD/MYR")
                        return round(price * 10 / rate) if rate else None
                    if unit == "CNY/tonne":
                        rate = fx_rates.get("USD/CNY")
                        return cny_tonne_to_usd_tonne(price, rate) if rate else None
                    if unit == "JPY/kg":
                        rate = fx_rates.get("USD/JPY")
                        return jpy_kg_to_usd_tonne(price, rate) if rate else None
                    # Unknown unit -> try direct round
                    return round(price)

                real_dates = sorted({d for dp in price_map.values() for d in dp})
                latest_label = (
                    date.fromisoformat(real_dates[-1]).strftime("%d/%m/%Y")
                    if real_dates else None
                )
                # Chỉ tạo bản tin cho ĐÚNG ngày chọn; ngày đó không có giá thật thì để trống.
                has_data_on_date = report_date.isoformat() in real_dates
                t_str = report_date.isoformat()
                p_str = prev_date.isoformat()
                if not has_data_on_date:
                    price_map = {}  # không lấy data ngày khác thay thế

                world_computed: dict = {}
                phys_computed: dict = {}
                for (src, grade), date_prices in price_map.items():
                    # curr = ngày mới nhất của mặt hàng, prev = ngày liền trước
                    sorted_dates = sorted(date_prices.keys())
                    curr_entry = date_prices.get(t_str) or (
                        date_prices[sorted_dates[-1]] if sorted_dates else None
                    )
                    prev_entry = date_prices.get(p_str)
                    if prev_entry is None and len(sorted_dates) >= 2:
                        prev_entry = date_prices[sorted_dates[-2]]

                    curr_int = _convert_to_usd_tonne(*curr_entry) if curr_entry else None
                    prev_int = _convert_to_usd_tonne(*prev_entry) if prev_entry else None
                    chg = (curr_int - prev_int) if (curr_int and prev_int) else None
                    pct = round(chg / prev_int * 100, 1) if (chg is not None and prev_int) else None

                    mapping = _WORLD_GRADE_MAP.get((src, grade))
                    if mapping:
                        exchange, blt_grade = mapping
                        world_computed[(exchange, blt_grade)] = WorldPriceItem(
                            exchange=exchange, grade=blt_grade,
                            price_prev=prev_int, price_curr=curr_int,
                            change_abs=chg, change_pct=pct,
                        )

                    if src == "reuters":
                        phys_grade = _PHYSICAL_GRADE_MAP.get(grade)
                        if phys_grade:
                            phys_computed[phys_grade] = PhysicalPriceItem(
                                grade=phys_grade, price_prev=prev_int, price_curr=curr_int,
                                change_abs=chg, change_pct=pct,
                            )

                # Dựng ĐÚNG cấu trúc template: đủ dòng, đúng thứ tự; thiếu data → để trống (N/A).
                if has_data_on_date:
                    world_prices = [
                        world_computed.get(k)
                        or WorldPriceItem(exchange=k[0], grade=k[1])
                        for k in _CANON_WORLD
                    ]
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
    phys_src = "db" if physical_prices else "empty"
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
            description="RSS3, STR20, SMR20, SIR20 \u2014 đọc từ DB (Reuters)"
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
    """Convert BulletinDraft (API) → BulletinData (generator). Dùng chung cho PPTX & PDF."""
    from bulletin.models import BulletinData, PhysicalPriceRow, VrgFloorRow, WorldPriceRow

    rdate = datetime.strptime(draft.report_date, "%d/%m/%Y").date()
    pdate = datetime.strptime(draft.prev_date, "%d/%m/%Y").date()
    return BulletinData(
        report_date=rdate,
        prev_date=pdate,
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


def generate_pptx_from_draft(report_date: date) -> Path | None:
    """Generate file PPTX từ draft hiện tại."""
    from bulletin.generator import generate as gen_pptx

    draft = _drafts.get(report_date.isoformat()) or create_draft(report_date)
    data = _draft_to_bulletin_data(draft)
    rdate = data.report_date

    template = (
        _ROOT
        / "docs/bieu-mau/Tâm/Biểu mẫu -  Bản tin ngày 09-06-2026"
        / "Bản tin ngày 09-06-2026.pptx"
    )
    if not template.exists():
        return None

    date_str = rdate.strftime("%d-%m-%Y")
    output = data_dir() / f"bulletins/Ban-tin-ngay-{date_str}.pptx"
    output.parent.mkdir(parents=True, exist_ok=True)

    # Resolve custom image overrides (slot → shape_name → file_path)
    image_overrides = _resolve_image_overrides()

    result = gen_pptx(template, output, data, image_overrides=image_overrides)
    if result:
        _save_snapshot(output, draft)
    return result


# ── Image override resolution ──

# Mapping: slot_name → list of PPTX shape names that use this image
_SLOT_TO_SHAPES: dict[str, list[str]] = {
    "cover-front": ["Picture 2"],
    "cover-back": ["Picture 1"],
    "header-banner": ["Picture 18"],
    "footer-banner": ["Picture 21"],
    "logo-vrg": ["Picture 4"],
}


def _resolve_assets() -> dict[str, str]:
    """slot → đường dẫn ảnh active (custom nếu có, ngược lại default) — dùng cho PDF."""
    assets_dir = data_dir() / "bulletin-assets"
    custom_dir = assets_dir / "custom"
    out: dict[str, str] = {}
    for slot in _SLOT_TO_SHAPES:
        p = _find_asset(custom_dir, slot) or _find_asset(assets_dir, slot)
        if p:
            out[slot] = str(p)
    return out


def _resolve_image_overrides() -> dict[str, str] | None:
    """Check custom/ dir for overrides, return shape_name → file_path mapping."""
    assets_dir = data_dir() / "bulletin-assets"
    custom_dir = assets_dir / "custom"

    overrides: dict[str, str] = {}

    for slot, shape_names in _SLOT_TO_SHAPES.items():
        # Custom takes priority over default
        img_path = _find_asset(custom_dir, slot)
        if img_path:
            for shape_name in shape_names:
                overrides[shape_name] = str(img_path)

    return overrides if overrides else None


def _find_asset(directory: Path, slot: str) -> Path | None:
    """Find image file by slot name in directory (any supported extension)."""
    if not directory.exists():
        return None
    for ext in (".jpg", ".jpeg", ".png", ".webp"):
        p = directory / f"{slot}{ext}"
        if p.exists():
            return p
    return None
