"""Bố cục "Sơ đồ vận hành" (mimic SCADA kiểu màn RELCO) của từng nhà máy — file JSON trong
`plant_layouts/<khoá>.json`; bảng `scada_factory.layout_key` chọn file (null = không có sơ đồ).

Vì sao để file trong code thay vì bảng DB: bố cục là bản vẽ dây chuyền, chỉ đổi khi nhà máy lắp/tháo
thiết bị (hiếm) và cần review như code; tag trong đó phải khớp ĐÚNG tên Historian của nhà máy.
JSON không ghi được chú thích nên quy ước định dạng (hợp đồng BE ↔ FE:
plans/260930-nha-may-thong-minh-scada/so-do-van-hanh-contract.md) ghi tại đây:
  - Toạ độ theo khung `width × height` của từng khu. Node: (x, y) = góc TRÊN-TRÁI của khung w × h
    khi CHƯA xoay; `angle` (độ, chiều kim đồng hồ như SVG, âm = đầu bên phải nâng lên) xoay quanh
    TÂM khung — băng tải / vít tải dùng `w` = chiều dài.
  - Web đặt khối "nhãn + đèn + ô Hz/A" ở cạnh `label_pos` (top · bottom · left · right) của khung
    CHƯA xoay, ô nhiệt độ ở cạnh ĐỐI DIỆN → mỗi phía phải chừa ~60–80 đơn vị trống. Băng tải / vít
    tải nghiêng vì vậy đặt nhãn "left": khối trên/dưới khung chưa xoay sẽ đè lên thân nghiêng.
  - `metrics` [{key, tag, unit}] · `status_tag` (0/1, ≥ 0,5 = chạy; null = không có) · `temps`
    [{label, tag}] (°C) mang ĐÚNG tên tag Historian, kể cả tag nhà máy gõ sai ("Temperture",
    "BTCS1- Frequence") — sửa cho "đẹp" là truy vấn hỏng. `zone` hiện số `temps[0]`, `counter`
    hiện `metrics[0]` (số nguyên).
  - decor: `basin` (x, y, w, h) · `pipe` (points) · `arrow_text` (points, mũi tên ở điểm CUỐI xoay
    theo đoạn cuối — được chỉ sang trái; `text_xy` = chỗ đặt chữ, neo trái, y = giữa dòng; không có
    thì chữ nối sau đầu mũi tên; x, y = chỗ chữ, dự phòng) · `badge` (x, y = góc trên-trái, `text`).
  - `links`: cặp [từ, đến] thiết bị KỀ NHAU theo dòng chảy, web nối tâm hai khung (đường dài vẽ
    bằng `pipe`); khu vẽ bám màn RELCO để `[]` (RELCO không có nét nối).
Bổ sung v2 (plans/…/so-do-van-hanh-contract-v2.md, mọi trường đều tuỳ chọn):
  - Khu: `hidden: true` = giữ dữ liệu nhưng KHÔNG đưa lên web, không đọc tag (`visible_areas`);
    `usage_box` {x, y, w, h} = chỗ vẽ bảng "Thống kê tiêu thụ trong ngày" ngay trong sơ đồ.
  - Node: `info_xy` [x, y] = góc trên-trái khối nhãn + đèn + ô Hz/A (tuyệt đối, không xoay; có thì
    bỏ qua `label_pos`) · `temps_xy` [x, y] + `temps_cols` (1 | 2) = khối nhiệt độ · `variant`
    ("mill" tháp cán | "creper" máy 2 trục) cho `crusher`.
Tag còn được `valid_tag` kiểm lại lúc dựng câu OPENQUERY (scada_historian_sql) — file sai tên không
thể thành lỗ injection, chỉ thành lỗi đọc SCADA.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

LAYOUT_DIR = Path(__file__).with_name("plant_layouts")
#: Khoá bố cục = tên file không đuôi — chặt để khoá lạ (vd `../x`) không bao giờ thành đường dẫn.
KEY_RE = re.compile(r"^[a-z0-9_]{1,64}$")


def layout_keys() -> list[str]:
    """Các khoá bố cục có sẵn (admin chỉ được gán một trong số này)."""
    return sorted(p.stem for p in LAYOUT_DIR.glob("*.json") if KEY_RE.fullmatch(p.stem))


def layout_options() -> list[dict[str, str]]:
    """[{key, label}] cho ô chọn "Sơ đồ vận hành" ở form admin — thêm file bố cục là web tự thấy."""
    out = []
    for key in layout_keys():
        layout = get_layout(key) or {}
        out.append({"key": key, "label": str(layout.get("label") or key)})
    return out


@lru_cache(maxsize=16)
def get_layout(key: str) -> dict[str, Any] | None:
    """Bố cục theo khoá; khoá sai dạng / không có file → None. Cache trong bộ nhớ (file chỉ đổi khi
    deploy) → dict DÙNG CHUNG: nơi gọi không được sửa."""
    if not isinstance(key, str) or not KEY_RE.fullmatch(key):
        return None
    path = LAYOUT_DIR / f"{key}.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def visible_areas(layout: dict[str, Any]) -> list[dict[str, Any]]:
    """Khu đang hiện (`hidden` = giữ bản vẽ + tag cho lúc bật lại, nhưng người dùng không thấy)."""
    return [a for a in layout.get("areas") or [] if not a.get("hidden")]


def public_layout(layout: dict[str, Any]) -> dict[str, Any]:
    """Bố cục gửi web: chỉ khu đang hiện. Bản SAO nông — không đụng dict dùng chung trong cache."""
    return {**layout, "areas": visible_areas(layout)}


def find_area(layout: dict[str, Any], area_key: str) -> dict[str, Any] | None:
    """Khu đang hiện theo khoá; khu ẩn coi như không có (→ /plant/live trả 404)."""
    return next((a for a in visible_areas(layout) if a.get("key") == area_key), None)


def node_tags(node: dict[str, Any]) -> list[str]:
    """Tag của một thiết bị theo thứ tự: chỉ số (Hz/A/…) → trạng thái chạy → nhiệt độ."""
    status = [node["status_tag"]] if node.get("status_tag") else []
    return [*(m["tag"] for m in node.get("metrics") or []), *status,
            *(t["tag"] for t in node.get("temps") or [])]


def _dedupe(raw: list[str]) -> list[str]:
    """Bỏ trùng KHÔNG phân biệt hoa thường (Historian coi `abc` và `ABC` là một cột, trùng cột làm vỡ
    kết quả), giữ thứ tự xuất hiện."""
    seen: set[str] = set()
    out: list[str] = []
    for tag in raw:
        if tag.lower() not in seen:
            seen.add(tag.lower())
            out.append(tag)
    return out


def area_tags(layout: dict[str, Any], area_key: str) -> list[str] | None:
    """Mọi tag của một khu + tag điện của thanh trên (`power`). Khu không có / đang ẩn → None."""
    area = find_area(layout, area_key)
    if area is None:
        return None
    raw = [t for n in area.get("nodes") or [] for t in node_tags(n)]
    return _dedupe(raw + [p["tag"] for p in layout.get("power") or []])


def all_tags(layout: dict[str, Any]) -> list[str]:
    """Mọi tag của các khu ĐANG HIỆN + tag điện — đọc một lần/nhà máy rồi chia theo khu (review
    01/10/2026: mỗi khu một truy vấn = mở 4–5 kết nối SQL Server qua VPN mỗi 5 giây; cả 4 khu gộp
    ~205 tag, câu OPENQUERY ~5 KB, dưới giới hạn 8 KB). Khu ẩn không đọc — SCADA đỡ phải trả số
    không ai xem."""
    raw = [t for a in visible_areas(layout) for n in a.get("nodes") or [] for t in node_tags(n)]
    return _dedupe(raw + [p["tag"] for p in layout.get("power") or []])
