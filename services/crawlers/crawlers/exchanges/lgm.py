"""LGM Malaysia — giá physical FOB: SMR CV, SMR20, Latex (US Cents/Kg).

Nguồn: lgm.gov.my (form chọn ngày) — spec lay-gia-cac-san.md. Latex: giá/tỷ giá×10.
Form cần phiên/tham số → chưa implement (open item). Trả BLOCKED — SMR20 tạm có từ ANRPC.
"""

from __future__ import annotations

from ..base.models import CrawlResult, Source, Status


def crawl() -> CrawlResult:
    return CrawlResult(
        source=Source.LGM,
        status=Status.BLOCKED,
        note=(
            "Giá physical FOB (SMR CV/SMR20/Latex) qua form chọn ngày, cần phiên/tham số. "
            "Chưa implement; tạm thời SMR20 lấy từ ANRPC."
        ),
    )
