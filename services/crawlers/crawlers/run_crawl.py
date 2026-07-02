"""CLI orchestrator: chạy tất cả nguồn, in bảng kết quả, tùy chọn lưu JSON.

  uv run python -m crawlers.run_crawl --source all
  uv run python -m crawlers.run_crawl --source fx,shfe --out ../../data/raw/crawl.json

Cô lập lỗi: 1 nguồn hỏng không chặn nguồn khác.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .base.models import CrawlResult, Source, Status
from .exchanges import lgm, sgx_sicom, shfe, tocom
from .macro import fx

# Giá physical (Asian rubber, chuỗi Reuters) nhập tay trên UI (trang Giá Physical) — không crawl.
CRAWLERS = {
    Source.FX: fx.crawl,
    Source.SGX: sgx_sicom.crawl,
    Source.SHFE: shfe.crawl,
    Source.TOCOM: tocom.crawl,
    Source.LGM: lgm.crawl,
}

_ICON = {Status.OK: "✓", Status.EMPTY: "·", Status.BLOCKED: "⚠", Status.ERROR: "✗"}


def run(sources: list[Source] | None = None) -> list[CrawlResult]:
    results: list[CrawlResult] = []
    for src, fn in CRAWLERS.items():
        if sources and src not in sources:
            continue
        try:
            results.append(fn())
        except Exception as exc:  # noqa: BLE001 - cô lập từng nguồn
            results.append(CrawlResult(source=src, status=Status.ERROR, note=str(exc)))
    return results


def render(results: list[CrawlResult]) -> str:
    lines = ["", "=== CHỈ SỐ SÀN / GIÁ THAM CHIẾU ==="]
    head = f"{'NGUỒN':6} {'GRADE':10} {'GIÁ':>12} {'ĐƠN VỊ':12} {'LOẠI':11} {'NGÀY':10}"
    lines += [head, "-" * len(head)]
    for r in results:
        for rec in r.records:
            lines.append(
                f"{r.source.value:6} {rec.grade:10} {rec.price:>12.4f} "
                f"{rec.unit:12} {rec.price_type:11} {rec.as_of.isoformat():10}"
            )
    lines += ["", "=== TRẠNG THÁI NGUỒN ==="]
    for r in results:
        note = f" — {r.note}" if r.note else ""
        lines.append(
            f"  {_ICON.get(r.status, '?')} {r.source.value:6} {r.status.value:8} "
            f"{len(r.records)} bản ghi{note}"
        )
    return "\n".join(lines)


# Nguồn hỗ trợ nạp lịch sử → backfill chart thật. SHFE/TOCOM theo ngày; FX đọc bảng lịch sử
# (~7 phiên) trên exchangerates → khớp tuyệt đối data live (lấp khi lỡ quên quét vài phiên).
HISTORY = {Source.SHFE: shfe.history, Source.TOCOM: tocom.history, Source.FX: fx.history}


def backfill(sources: list[Source], days: int) -> list:
    """Gom bản ghi lịch sử từ các nguồn hỗ trợ (bỏ qua nguồn không hỗ trợ)."""
    records = []
    for src in sources:
        fn = HISTORY.get(src)
        if fn:
            records.extend(fn(days))
    return records


def main() -> None:
    ap = argparse.ArgumentParser(description="Crawl chỉ số sàn cao su (VRG)")
    ap.add_argument("--source", default="all", help="all | fx,sgx,shfe,tocom,lgm")
    ap.add_argument("--out", default=None, help="đường dẫn lưu JSON (vd data/raw/crawl.json)")
    ap.add_argument("--backfill", action="store_true", help="nạp lịch sử (chỉ nguồn có file theo ngày: shfe,tocom)")
    ap.add_argument("--days", type=int, default=90, help="số phiên lịch sử khi --backfill")
    args = ap.parse_args()

    if args.backfill:
        srcs = list(HISTORY) if args.source == "all" else [Source(s) for s in args.source.split(",")]
        records = backfill(srcs, args.days)
        payload = [json.loads(r.model_dump_json()) for r in records]
        if args.out:
            out = Path(args.out)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        print(f"backfill {[s.value for s in srcs]} ({args.days}d): {len(records)} bản ghi")
        return

    sources = None if args.source == "all" else [Source(s) for s in args.source.split(",")]
    results = run(sources)
    print(render(results))

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        payload = [json.loads(r.model_dump_json()) for r in results]
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nĐã lưu: {out}")


if __name__ == "__main__":
    main()
