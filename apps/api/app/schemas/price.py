"""Schema response cho endpoint giá (scan/latest/history)."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class PriceRow(BaseModel):
    source: str
    grade: str
    price: float
    currency: str
    unit: str
    price_type: str
    as_of: date
    contract: str | None = None


class PriceRecordEdit(BaseModel):
    """Thêm/sửa 1 bản ghi giá thủ công (trang quản lý đa sàn).

    `price` chặn NaN/Infinity: kiểu float của JSON cho phép 2 giá trị này, mà ghi được vào
    fact_price thì mọi màn đọc giá sau đó (bảng giá, lưới, bản tin) đều vỡ khi làm tròn
    (Decimal ném InvalidOperation) → 500 cho tất cả người dùng, không riêng người nhập.
    """

    as_of: date
    source: str
    grade: str
    contract: str = ""
    price_type: str
    price: float = Field(allow_inf_nan=False)
    currency: str
    unit: str


class ReutersParseRequest(BaseModel):
    """Yêu cầu phân giải chuỗi giá physical Reuters (paste từ MarketScreener)."""

    text: str
    as_of: date | None = None          # ngày do người dùng chọn (mặc định hôm nay)


class ReutersParsedRow(BaseModel):
    label: str
    grade: str | None = None
    native_price: float | None = None
    native_unit: str | None = None
    contract: str = ""
    usd_tonne: float | None = None     # USD/tấn đã quy đổi (giữ 1 số lẻ — xem _to_usd_tonne)
    status: str                        # ok | na | unmatched | no_unit | no_fx


class ReutersParseResult(BaseModel):
    as_of: date
    usd_thb: float | None = None       # USD/THB ĐÚNG NGÀY as_of (None nếu chưa có → baht/kg không nhập)
    note: str | None = None            # ghi chú kèm trong text Reuters, vd 'Prices as of July 16'
    note_as_of: date | None = None     # ngày suy từ ghi chú — lệch as_of ⇒ cảnh báo (giá của ngày khác)
    rows: list[ReutersParsedRow]


class SourceStatus(BaseModel):
    source: str
    status: str
    count: int
    note: str | None = None


class FxStaleItem(BaseModel):
    """1 cặp tỷ giá quá cũ (xem services/fx_freshness.py)."""

    pair: str                    # vd USD/JPY
    latest: date | None = None   # ngày mới nhất có giá; None = chưa có dữ liệu
    lag: int | None = None       # số ngày làm việc (T2–T6) đã trễ tính tới hôm nay


class FxHealth(BaseModel):
    """GET /api/prices/fx-health — tỷ giá nào đang quá cũ."""

    stale: list[FxStaleItem]
    checked_at: str
    threshold: int               # ngưỡng ngày làm việc (app_config FX_STALE_BUSINESS_DAYS)


class ScanResponse(BaseModel):
    """Kết quả quét: bản ghi + trạng thái nguồn + thông tin ghi DB + trạng thái tổng của lượt quét."""

    records: list[PriceRow]
    sources: list[SourceStatus]
    persisted: int          # số bản ghi ghi vào DB (0 nếu DB down)
    run_id: int | None = None
    db: str                 # "ok" | "skipped:<lý do>"
    # Thêm 09/2026 — có mặc định để client/nguồn gọi cũ không vỡ.
    status: str = "ok"      # "ok" | "warning" (nguồn lỗi / tỷ giá quá cũ) | "error" (ghi DB hỏng)
    warnings: list[str] = []
    stale_fx: list[FxStaleItem] = []


class ExchangeComponent(BaseModel):
    """1 dòng giá sàn dạng thành phần (native · tỷ giá · USD/T) — dashboard."""

    exchange: str
    grade: str
    native_price: float
    native_unit: str
    fx_pair: str | None = None
    fx_rate: float | None = None
    # USD/tấn giữ 1 SỐ LẺ (xem convert.r1) — phải là float. Để `int` thì mọi giá lẻ ,5 của MRB/SHFE
    # (vd 2238,5) làm pydantic ném ResponseValidationError → cả /api/prices/board trả 500.
    usd_tonne: float | None = None
    as_of: date


class FxRateItem(BaseModel):
    pair: str            # vd USD/JPY
    rate: float          # 1 USD = rate <ngoại tệ>
    as_of: date | None = None


class PriceBoard(BaseModel):
    """Bảng giá thành phần + tỷ giá cho dashboard Quét Đa sàn."""

    exchanges: list[ExchangeComponent]
    fx: list[FxRateItem]
    ingested_at: str | None = None


class HistoryPoint(BaseModel):
    as_of: date
    price: float


class HistorySeries(BaseModel):
    source: str
    grade: str
    points: list[HistoryPoint]


class PurchaseAutoSyncEdit(BaseModel):
    """Cấu hình tự động lấy giá mủ nguyên liệu từ đơn vị (xem `services/purchase_price_sync.py`).

    `companies` là danh sách ĐẦY ĐỦ các đơn vị được bật — đơn vị không có trong danh sách sẽ bị
    tắt. Gửi từng đơn vị một sẽ không diễn tả được thao tác "bỏ chọn".
    """

    enabled: bool
    companies: list[str] = []
