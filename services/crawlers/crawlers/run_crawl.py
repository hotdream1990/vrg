"""CLI orchestrator: chạy tất cả nguồn, in bảng kết quả, tùy chọn lưu JSON.

  uv run python -m crawlers.run_crawl --source all
  uv run python -m crawlers.run_crawl --source anrpc,fx --out ../../data/raw/crawl.json

Cô lập lỗi: 1 nguồn hỏng không chặn nguồn khác.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .base.models import CrawlResult, Source, Status
from .exchanges import anrpc, lgm, sgx_sicom, shfe, tocom
from .macro import fx

CRAWLERS = {
    Source.ANRPC: anrpc.crawl,
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


def main() -> None:
    ap = argparse.ArgumentParser(description="Crawl chỉ số sàn cao su (VRG)")
    ap.add_argument("--source", default="all", help="all | anrpc,fx,sgx,shfe,tocom,lgm")
    ap.add_argument("--out", default=None, help="đường dẫn lưu JSON (vd data/raw/crawl.json)")
    args = ap.parse_args()

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
