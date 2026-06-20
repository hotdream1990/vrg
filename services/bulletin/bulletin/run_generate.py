"""CLI entry point: generate bản tin ngày.

  # Chỉ fill giá từ crawlers (auto):
  uv run python -m bulletin.run_generate

  # Chỉ định ngày + template + output:
  uv run python -m bulletin.run_generate --date 2026-06-18 --template path/to/template.pptx

  # Với file JSON bổ sung (giá sàn VRG, phân tích):
  uv run python -m bulletin.run_generate --supplement data.json
"""

from __future__ import annotations

import argparse
import json
from datetime import date, timedelta
from pathlib import Path

from .generator import generate
from .models import BulletinData, VrgFloorRow


# Template mặc định: file mẫu gốc từ VRG
_DEFAULT_TEMPLATE = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "docs/bieu-mau/Tâm/Biểu mẫu -  Bản tin ngày 09-06-2026"
    / "Bản tin ngày 09-06-2026.pptx"
)


def _parse_supplement(path: Path, data: BulletinData) -> None:
    """Đọc file JSON bổ sung (giá sàn VRG, mủ, phân tích) và merge vào data."""
    raw = json.loads(path.read_text(encoding="utf-8"))

    # Giá sàn VRG
    if "vrg_floor_prev_label" in raw:
        data.vrg_floor_prev_label = raw["vrg_floor_prev_label"]
    if "vrg_floor_curr_label" in raw:
        data.vrg_floor_curr_label = raw["vrg_floor_curr_label"]
    if "vrg_floor_prev" in raw:
        data.vrg_floor_prev = [VrgFloorRow(**r) for r in raw["vrg_floor_prev"]]
    if "vrg_floor_curr" in raw:
        data.vrg_floor_curr = [VrgFloorRow(**r) for r in raw["vrg_floor_curr"]]

    # Giá mủ nguyên liệu
    if "raw_material_regions" in raw:
        data.raw_material_regions = raw["raw_material_regions"]

    # Phân tích thị trường
    if "market_analysis" in raw:
        data.market_analysis = raw["market_analysis"]
    if "market_physical_summary" in raw:
        data.market_physical_summary = raw["market_physical_summary"]
    if "source_urls" in raw:
        data.source_urls = raw["source_urls"]


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate bản tin thị trường cao su ngày (PPTX)")
    ap.add_argument("--date", type=str, default=None,
                    help="Ngày bản tin DD-MM-YYYY (mặc định: hôm qua)")
    ap.add_argument("--template", type=str, default=None,
                    help="Đường dẫn file PPTX template")
    ap.add_argument("--out", type=str, default=None,
                    help="Đường dẫn output (mặc định: data/bulletins/Ban-tin-ngay-DD-MM-YYYY.pptx)")
    ap.add_argument("--supplement", type=str, default=None,
                    help="File JSON bổ sung (giá sàn VRG, phân tích thị trường)")
    ap.add_argument("--no-crawl", action="store_true",
                    help="Không chạy crawler, chỉ dùng data từ --supplement")
    args = ap.parse_args()

    # Parse date
    if args.date:
        parts = args.date.split("-")
        report_date = date(int(parts[2]), int(parts[1]), int(parts[0]))
    else:
        report_date = date.today() - timedelta(days=1)

    # Build data
    if args.no_crawl:
        data = BulletinData(
            report_date=report_date,
            prev_date=report_date - timedelta(days=1),
        )
    else:
        from .data_mapper import build_from_crawl
        data = build_from_crawl(report_date)

    # Merge supplement
    if args.supplement:
        _parse_supplement(Path(args.supplement), data)

    # Paths
    template = Path(args.template) if args.template else _DEFAULT_TEMPLATE
    if not template.exists():
        print(f"❌ Template không tồn tại: {template}")
        print("   Cần file PPTX mẫu gốc. Xem docs/bieu-mau/")
        raise SystemExit(1)

    date_str = report_date.strftime("%d-%m-%Y")
    if args.out:
        output = Path(args.out)
    else:
        output = (
            Path(__file__).resolve().parent.parent.parent.parent
            / f"data/bulletins/Ban-tin-ngay-{date_str}.pptx"
        )

    # Generate
    result = generate(template, output, data)
    print(f"✅ Đã tạo bản tin: {result}")
    print(f"   Ngày: {report_date.strftime('%d/%m/%Y')}")
    print(f"   World prices: {len(data.world_prices)} dòng")
    print(f"   Physical prices: {len(data.physical_prices)} dòng")
    if data.vrg_floor_curr:
        print(f"   VRG floor prices: {len(data.vrg_floor_curr)} dòng")
    if data.market_exchange_summary:
        print(f"   Exchange summary: {len(data.market_exchange_summary)} sàn")
    if data.market_analysis:
        print(f"   Market analysis: {len(data.market_analysis)} đoạn")


if __name__ == "__main__":
    main()
