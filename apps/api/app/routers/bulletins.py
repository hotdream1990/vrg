"""Router Bản tin ngày — tạo draft, cập nhật, xuất PPTX, quản lý hình ảnh."""

from __future__ import annotations

import re
import shutil
from datetime import date, datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse

from app.schemas.bulletin import BulletinDraft, BulletinDraftUpdate
from app.services.bulletin_service import (
    create_draft,
    generate_pptx_from_draft,
    get_draft,
    update_draft,
)

router = APIRouter(prefix="/api/bulletins", tags=["bulletins"])

# ── Image assets paths ──
_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
_ASSETS_DIR = _ROOT / "data" / "bulletin-assets"
_CUSTOM_DIR = _ASSETS_DIR / "custom"
_OUTPUT_DIR = _ROOT / "data" / "bulletins"

# Valid image slots
_IMAGE_SLOTS = {"cover-front", "cover-back", "header-banner", "footer-banner", "logo-vrg"}

# Extension map
_EXT_MAP = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


# ── Draft endpoints ──


@router.post("/draft", response_model=BulletinDraft)
def api_create_draft(
    report_date: str | None = Query(None, description="DD-MM-YYYY, mặc định hôm qua"),
    crawl: bool = Query(True, description="Chạy crawler để lấy giá thật?"),
):
    """Tạo draft bản tin mới — quét giá từ crawlers + fill sample data."""
    rdate = _parse_date(report_date)
    return create_draft(rdate, use_crawlers=crawl)


@router.get("/draft", response_model=BulletinDraft)
def api_get_draft(
    report_date: str | None = Query(None, description="DD-MM-YYYY"),
):
    """Lấy draft hiện có (đã tạo trước đó)."""
    rdate = _parse_date(report_date)
    draft = get_draft(rdate)
    if not draft:
        raise HTTPException(404, f"Chưa có draft cho ngày {rdate.isoformat()}")
    return draft


@router.put("/draft", response_model=BulletinDraft)
def api_update_draft(
    updates: BulletinDraftUpdate,
    report_date: str | None = Query(None, description="DD-MM-YYYY"),
):
    """Cập nhật phần editable trong draft (giá sàn, phân tích, ...)."""
    rdate = _parse_date(report_date)
    draft = update_draft(rdate, updates)
    if not draft:
        raise HTTPException(404, f"Chưa có draft cho ngày {rdate.isoformat()}")
    return draft


@router.post("/generate")
def api_generate_pptx(
    report_date: str | None = Query(None, description="DD-MM-YYYY"),
):
    """Xuất PPTX từ draft hiện tại → download file."""
    rdate = _parse_date(report_date)
    path = generate_pptx_from_draft(rdate)
    if not path:
        raise HTTPException(
            404,
            "Không thể tạo PPTX. Kiểm tra: (1) Draft tồn tại? (2) File template có sẵn?",
        )
    return FileResponse(
        str(path),
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        filename=path.name,
    )


# ── Published bulletins (đã xuất) ──


@router.get("/published")
def api_list_published():
    """Liệt kê các bản tin đã xuất (file PPTX trong data/bulletins/), mới nhất trước."""
    items: list[dict] = []
    if _OUTPUT_DIR.exists():
        for p in sorted(_OUTPUT_DIR.glob("Ban-tin-ngay-*.pptx"), reverse=True):
            st = p.stat()
            items.append({
                "filename": p.name,
                "report_date": _date_from_filename(p.name),
                "size": st.st_size,
                "modified": datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds"),
                "download_url": f"/api/bulletins/published/{p.name}",
            })
    return {"bulletins": items}


@router.get("/published/{filename}")
def api_download_published(filename: str):
    """Tải 1 bản tin đã xuất. Chỉ cho .pptx trong data/bulletins/ (chặn path traversal)."""
    safe = Path(filename).name
    if not safe.endswith(".pptx"):
        raise HTTPException(400, "Chỉ tải được file .pptx")
    path = _OUTPUT_DIR / safe
    if not path.exists():
        raise HTTPException(404, f"Không tìm thấy bản tin '{safe}'")
    return FileResponse(
        str(path),
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        filename=safe,
    )


@router.get("/published/{filename}/detail", response_model=BulletinDraft)
def api_published_detail(filename: str):
    """Chi tiết 1 bản tin đã xuất: ưu tiên snapshot JSON, nếu chưa có thì dựng lại từ DB."""
    safe = Path(filename).name
    if not safe.endswith(".pptx"):
        raise HTTPException(400, "Tên file không hợp lệ")
    pptx = _OUTPUT_DIR / safe
    if not pptx.exists():
        raise HTTPException(404, f"Không tìm thấy bản tin '{safe}'")

    sidecar = pptx.with_suffix(".json")
    if sidecar.exists():
        return BulletinDraft.model_validate_json(sidecar.read_text(encoding="utf-8"))

    # Fallback: bản tin xuất trước khi có snapshot → dựng lại từ DB theo ngày trong tên file
    ds = _date_from_filename(safe)
    if not ds:
        raise HTTPException(404, "Không xác định được ngày bản tin từ tên file")
    d, m, y = ds.split("/")
    return create_draft(date(int(y), int(m), int(d)), use_crawlers=True)


# ── Image settings endpoints ──


@router.get("/images")
def api_list_images():
    """Liệt kê tất cả hình ảnh: default + custom (nếu có)."""
    result: list[dict] = []
    for slot in sorted(_IMAGE_SLOTS):
        item: dict = {"slot": slot, "label": _SLOT_LABELS.get(slot, slot)}

        # Default image
        default = _find_file(_ASSETS_DIR, slot)
        item["default_url"] = f"/api/bulletins/images/{slot}?source=default" if default else None

        # Custom image (override)
        custom = _find_file(_CUSTOM_DIR, slot)
        item["custom_url"] = f"/api/bulletins/images/{slot}?source=custom" if custom else None

        # Active = custom if exists, else default
        item["active_source"] = "custom" if custom else ("default" if default else None)
        item["active_url"] = (
            f"/api/bulletins/images/{slot}" if (custom or default) else None
        )

        result.append(item)
    return {"images": result}


@router.get("/images/{slot}")
def api_get_image(
    slot: str,
    source: str = Query("active", description="active|default|custom"),
):
    """Serve hình ảnh theo slot. source=active trả custom nếu có, fallback default."""
    if slot not in _IMAGE_SLOTS:
        raise HTTPException(404, f"Slot '{slot}' không hợp lệ. Có: {sorted(_IMAGE_SLOTS)}")

    path = None
    if source == "custom":
        path = _find_file(_CUSTOM_DIR, slot)
    elif source == "default":
        path = _find_file(_ASSETS_DIR, slot)
    else:  # active
        path = _find_file(_CUSTOM_DIR, slot) or _find_file(_ASSETS_DIR, slot)

    if not path:
        raise HTTPException(404, f"Không có hình cho slot '{slot}' (source={source})")

    media = "image/png" if path.suffix == ".png" else "image/jpeg"
    return FileResponse(str(path), media_type=media)


@router.post("/images/{slot}")
def api_upload_image(slot: str, file: UploadFile):
    """Upload hình mới cho slot (lưu vào custom/, không ghi đè default)."""
    if slot not in _IMAGE_SLOTS:
        raise HTTPException(400, f"Slot '{slot}' không hợp lệ")

    ct = file.content_type or ""
    ext = _EXT_MAP.get(ct)
    if not ext:
        raise HTTPException(400, f"Chỉ chấp nhận JPEG/PNG/WEBP. Nhận: {ct}")

    _CUSTOM_DIR.mkdir(parents=True, exist_ok=True)

    # Remove old custom for this slot (any extension)
    for old in _CUSTOM_DIR.glob(f"{slot}.*"):
        old.unlink()

    dest = _CUSTOM_DIR / f"{slot}{ext}"
    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    size = dest.stat().st_size
    return {
        "slot": slot,
        "source": "custom",
        "url": f"/api/bulletins/images/{slot}?source=custom",
        "size": size,
        "filename": dest.name,
    }


@router.delete("/images/{slot}")
def api_delete_custom_image(slot: str):
    """Xóa custom image → revert về default."""
    if slot not in _IMAGE_SLOTS:
        raise HTTPException(400, f"Slot '{slot}' không hợp lệ")

    deleted = False
    for old in _CUSTOM_DIR.glob(f"{slot}.*"):
        old.unlink()
        deleted = True

    if not deleted:
        raise HTTPException(404, f"Không có custom image cho slot '{slot}'")

    return {"slot": slot, "reverted_to": "default"}


# ── Helpers ──

_SLOT_LABELS = {
    "cover-front": "Hình bìa đầu",
    "cover-back": "Hình bìa cuối",
    "header-banner": "Banner trên (header)",
    "footer-banner": "Banner dưới (footer)",
    "logo-vrg": "Logo VRG",
}


def _find_file(directory: Path, slot: str) -> Path | None:
    """Tìm file theo slot name (bỏ qua extension)."""
    if not directory.exists():
        return None
    for ext in (".jpg", ".jpeg", ".png", ".webp"):
        p = directory / f"{slot}{ext}"
        if p.exists():
            return p
    return None


def _date_from_filename(name: str) -> str | None:
    """Ban-tin-ngay-DD-MM-YYYY.pptx → 'DD/MM/YYYY'."""
    m = re.search(r"(\d{2})-(\d{2})-(\d{4})", name)
    return f"{m.group(1)}/{m.group(2)}/{m.group(3)}" if m else None


def _parse_date(s: str | None) -> date:
    """Parse DD-MM-YYYY hoặc fallback hôm qua."""
    if not s:
        return date.today() - timedelta(days=1)
    parts = s.split("-")
    return date(int(parts[2]), int(parts[1]), int(parts[0]))

