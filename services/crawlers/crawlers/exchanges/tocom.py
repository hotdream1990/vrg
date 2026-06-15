"""TOCOM / JPX — RSS3: Settlement của kỳ hạn có Trading Value lớn nhất.

Nguồn: file cdf_dyr (PDF, trang 12) — spec lay-gia-cac-san.md. Cần parser PDF.
Chưa implement (open item, ưu tiên sau). Trả BLOCKED — RSS3 tạm có từ ANRPC (BKK RSS3).
"""

from __future__ import annotations

from ..base.models import CrawlResult, Source, Status


def crawl() -> CrawlResult:
    return CrawlResult(
        source=Source.TOCOM,
        status=Status.BLOCKED,
        note=(
            "RSS3 phát hành dạng PDF (cdf_dyr, trang 12) — cần parser PDF + chọn kỳ hạn "
            "max Trading Value. Chưa implement; tạm thời dùng BKK RSS3 từ ANRPC."
        ),
    )
