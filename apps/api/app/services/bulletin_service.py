"""Bulletin service -- tạo draft từ data đã quét (fact_price DB), merge edits, generate PPTX.

In-memory draft store (MVP). Sau này chuyển sang DB khi cần lịch sử.
"""

from __future__ import annotations

import sys
from datetime import date, datetime, timedelta
from pathlib import Path

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

# ── Giá trị khởi tạo cho các mục admin tự nhập (III/III.2/IV) — KHÔNG phải giá thị trường ──

_DEFAULT_VRG_FLOOR = [
    VrgFloorItem(grade="SVR CV 50", fob_usd=2510, domestic_vnd=64500000, is_fake=True),
    VrgFloorItem(grade="SVR CV60", fob_usd=2490, domestic_vnd=63950000, is_fake=True),
    VrgFloorItem(grade="SVR L", fob_usd=2460, domestic_vnd=63200000, is_fake=True),
    VrgFloorItem(grade="SVR 3L Mix", fob_usd=2465, domestic_vnd=63300000, is_fake=True),
    VrgFloorItem(grade="SVR 3L", fob_usd=2450, domestic_vnd=62900000, is_fake=True),
    VrgFloorItem(grade="SVR 5S", fob_usd=2440, domestic_vnd=62650000, is_fake=True),
    VrgFloorItem(grade="SVR 5", fob_usd=2430, domestic_vnd=62400000, is_fake=True),
    VrgFloorItem(grade="SVR 10 Mix", fob_usd=2300, domestic_vnd=59000000, is_fake=True),
    VrgFloorItem(grade="SVR 10", fob_usd=2280, domestic_vnd=58500000, is_fake=True),
    VrgFloorItem(grade="SVR 20", fob_usd=2260, domestic_vnd=57950000, is_fake=True),
    VrgFloorItem(grade="RSS 3", fob_usd=2490, domestic_vnd=63950000, is_fake=True),
    VrgFloorItem(grade="RSS 1", fob_usd=2510, domestic_vnd=64450000, is_fake=True),
    VrgFloorItem(grade="LATEX", fob_usd=1760, domestic_vnd=45500000, is_fake=True),
]

_DEFAULT_RAW_MATERIALS = [
    RawMaterialRegion(region="B\u00ecnh D\u01b0\u01a1ng", price_text="573 \u0111/\u0111\u1ed9 TSC", is_fake=True),
    RawMaterialRegion(region="B\u00ecnh Ph\u01b0\u1edbc", price_text="538-580 \u0111/\u0111\u1ed9 TSC", is_fake=True),
    RawMaterialRegion(region="B\u00ecnh Thu\u1eadn", price_text="545 \u0111/\u0111\u1ed9 TSC", is_fake=True),
    RawMaterialRegion(region="T\u00e2y Ninh", price_text="570 \u0111/\u0111\u1ed9 TSC", is_fake=True),
]

_DEFAULT_ANALYSIS = [
    "Giá cao su kỳ hạn tại Nhật Bản giảm do thị trường kỳ vọng nguồn cung cao su toàn cầu sẽ gia tăng trong thời gian tới.",
    "Nhiều nhà máy sản xuất cao su tổng hợp tại Trung Quốc đã nâng công suất hoạt động sau khi hoàn tất các đợt bảo trì.",
    "Tuy nhiên, Đồng yên yếu giúp các tài sản được định giá bằng Đồng yên trở nên rẻ hơn đối với nhà đầu tư nước ngoài.",
]


# ── Grade mapping (crawler → bulletin) ──

_WORLD_GRADE_MAP = {
    ("tocom", "RSS3"): ("OSE", "RSS3"),
    ("tocom", "TSR20"): ("OSE", "TSR20"),
    ("shfe", "RU"): ("SHANGHAI", "RSS3"),
    ("sgx", "RSS3"): ("SGX", "RSS3"),
    ("sgx", "TSR20"): ("SGX", "TSR20"),
    ("lgm", "SMRCV"): ("MRE", "SMRCV"),
    ("lgm", "SMR20"): ("MRE", "SMR20"),
    ("lgm", "LATEX"): ("MRE", "LATEX"),
}

_PHYSICAL_GRADE_MAP = {"RSS3": "RSS3", "STR20": "STR20", "SMR20": "SMR20", "SIR20": "SIR20"}

_EXCHANGE_NAMES = {
    "OSE": "Sàn TOCOM (Nhật Bản)",
    "SHANGHAI": "Sàn SHFE (Thượng Hải - Trung Quốc)",
    "SGX": "Sàn SGX (Singapore)",
    "MRE": "Sàn MRB (Malaysia)",
}


# ── In-memory draft store (1 draft per date, MVP) ──
_drafts: dict[str, BulletinDraft] = {}



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

                    # World prices
                    mapping = _WORLD_GRADE_MAP.get((src, grade))
                    if mapping:
                        exchange, blt_grade = mapping
                        world_prices.append(WorldPriceItem(
                            exchange=exchange, grade=blt_grade,
                            price_prev=prev_int, price_curr=curr_int,
                            change_abs=chg, change_pct=pct,
                            is_fake=False,
                        ))

                    # Physical prices (ANRPC)
                    if src == "anrpc":
                        phys_grade = _PHYSICAL_GRADE_MAP.get(grade)
                        if phys_grade:
                            physical_prices.append(PhysicalPriceItem(
                                grade=phys_grade, price_prev=prev_int, price_curr=curr_int,
                                change_abs=chg, change_pct=pct, is_fake=False,
                            ))

                # Auto exchange summary
                by_exc: dict[str, list[WorldPriceItem]] = {}
                for wp in world_prices:
                    by_exc.setdefault(wp.exchange, []).append(wp)
                for code, name in _EXCHANGE_NAMES.items():
                    rows = by_exc.get(code, [])
                    if rows:
                        parts = [f"{r.grade} ở mức {r.price_curr:,} usd/tấn" for r in rows if r.price_curr]
                        if parts:
                            exchange_summary.append(f"{name}: {'; '.join(parts)};")

        except Exception as exc:
            print(f"[bulletin] DB read error (dùng sample data): {exc}")

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
            section="II. Giá vật chất (ANRPC)",
            source=phys_src,
            description="RSS3, STR20, SMR20, SIR20 \u2014 đọc từ DB (ANRPC)"
            if phys_src == "db"
            else _empty,
        ),
        SectionStatus(
            section="III. Giá sàn VRG",
            source="manual",
            description="Chưa có nguồn tự động \u2014 admin tự nhập/cập nhật",
        ),
        SectionStatus(
            section="III.2 Giá mủ nguyên liệu",
            source="manual",
            description="Chưa có nguồn tự động \u2014 admin tự nhập/cập nhật",
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
        vrg_floor_prev_label="Giá sàn lần trước",
        vrg_floor_curr_label=f"Giá sàn ({report_label})",
        vrg_floor_prev=list(_DEFAULT_VRG_FLOOR),
        vrg_floor_curr=list(_DEFAULT_VRG_FLOOR),
        raw_materials=list(_DEFAULT_RAW_MATERIALS),
        exchange_summary=exchange_summary,
        physical_summary="",
        market_analysis=list(_DEFAULT_ANALYSIS),
        source_urls=["https://intl.sci99.com/annualreport/", "https://vietnambiz.vn/"],
        data_sources=data_sources,
    )

    _drafts[date_key] = draft
    return draft


def get_draft(report_date: date) -> BulletinDraft | None:
    return _drafts.get(report_date.isoformat())


def update_draft(report_date: date, updates: BulletinDraftUpdate) -> BulletinDraft | None:
    """Merge admin edits vào draft hiện có."""
    draft = _drafts.get(report_date.isoformat())
    if not draft:
        return None

    for field, value in updates.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(draft, field, value)

    return draft


def generate_pptx_from_draft(report_date: date) -> Path | None:
    """Generate file PPTX từ draft hiện tại."""
    from bulletin.generator import generate as gen_pptx
    from bulletin.models import BulletinData, PhysicalPriceRow, VrgFloorRow, WorldPriceRow

    draft = _drafts.get(report_date.isoformat())
    if not draft:
        return None

    rdate = datetime.strptime(draft.report_date, "%d/%m/%Y").date()
    pdate = datetime.strptime(draft.prev_date, "%d/%m/%Y").date()

    # Convert draft → BulletinData
    data = BulletinData(
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

    template = (
        _ROOT
        / "docs/bieu-mau/Tâm/Biểu mẫu -  Bản tin ngày 09-06-2026"
        / "Bản tin ngày 09-06-2026.pptx"
    )
    if not template.exists():
        return None

    date_str = rdate.strftime("%d-%m-%Y")
    output = _ROOT / f"data/bulletins/Ban-tin-ngay-{date_str}.pptx"
    output.parent.mkdir(parents=True, exist_ok=True)

    # Resolve custom image overrides (slot → shape_name → file_path)
    image_overrides = _resolve_image_overrides()

    result = gen_pptx(template, output, data, image_overrides=image_overrides)

    # Lưu snapshot JSON cạnh file PPTX để xem chi tiết về sau (read-only)
    if result:
        try:
            output.with_suffix(".json").write_text(
                draft.model_dump_json(indent=2), encoding="utf-8"
            )
        except Exception as exc:  # noqa: BLE001
            print(f"[bulletin] Không lưu được snapshot JSON: {exc}")

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


def _resolve_image_overrides() -> dict[str, str] | None:
    """Check custom/ dir for overrides, return shape_name → file_path mapping."""
    assets_dir = _ROOT / "data" / "bulletin-assets"
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
