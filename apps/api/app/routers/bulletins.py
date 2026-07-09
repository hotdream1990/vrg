"""Router Bản tin ngày — tạo draft, cập nhật, xuất PDF, quản lý hình ảnh."""

from __future__ import annotations

import logging
import re
import shutil
from datetime import date, datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse

from app.core.paths import data_dir
from app.core.security import get_current_user, require_editor
from app.schemas.bulletin import BulletinDraft, BulletinDraftUpdate
from app.services.bulletin_service import (
    create_draft,
    delete_saved_draft,
    generate_pdf_from_draft,
    get_draft,
    list_saved_drafts,
    update_draft,
)

logger = logging.getLogger("vrg.api")

router = APIRouter(prefix="/api/bulletins", tags=["bulletins"])

# Thao tác GHI cần admin/editor; các GET DỮ LIỆU cần đăng nhập (_auth); riêng phần phục vụ
# ảnh thô <img> (GET /images/{slot}) để mở vì trình duyệt không gắn được Bearer.
_editor = [Depends(require_editor)]
_auth = [Depends(get_current_user)]

# ── Image assets paths (ghi runtime → /app/data qua volume, xem paths.data_dir) ──
_DATA_DIR = data_dir()
_ASSETS_DIR = _DATA_DIR / "bulletin-assets"
_CUSTOM_DIR = _ASSETS_DIR / "custom"
_OUTPUT_DIR = _DATA_DIR / "bulletins"

# Valid image slots
_IMAGE_SLOTS = {"cover-front", "cover-back", "header-banner", "footer-banner", "logo-vrg"}

# Extension map
_EXT_MAP = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


# ── Draft endpoints ──


@router.post("/draft", response_model=BulletinDraft, dependencies=_editor)
def api_create_draft(
    report_date: str | None = Query(None, description="DD-MM-YYYY, mặc định hôm qua"),
    crawl: bool = Query(True, description="Chạy crawler để lấy giá thật?"),
):
    """Tạo draft bản tin mới — đọc giá thật từ DB (KHÔNG còn số liệu mẫu)."""
    rdate = _parse_date(report_date)
    return create_draft(rdate, use_crawlers=crawl)


@router.get("/draft", response_model=BulletinDraft, dependencies=_auth)
def api_get_draft(
    report_date: str | None = Query(None, description="DD-MM-YYYY"),
):
    """Lấy draft hiện có (đã tạo trước đó)."""
    rdate = _parse_date(report_date)
    draft = get_draft(rdate)
    if not draft:
        raise HTTPException(404, f"Chưa có draft cho ngày {rdate.isoformat()}")
    return draft


@router.put("/draft", response_model=BulletinDraft, dependencies=_editor)
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


@router.get("/drafts", dependencies=_auth)
def api_list_drafts() -> dict:
    """Danh sách nháp đã lưu (mới nhất trước) — cho trang danh sách bản tin."""
    return {"drafts": list_saved_drafts()}


@router.delete("/draft", dependencies=_editor)
def api_delete_draft(report_date: str | None = Query(None, description="DD-MM-YYYY")) -> dict:
    """Xoá nháp 1 ngày (DB + bộ nhớ)."""
    return {"deleted": delete_saved_draft(_parse_date(report_date))}


@router.post("/market-analysis", dependencies=_editor)
def api_market_analysis() -> dict:
    """AI lấy tin thị trường (vietnambiz) + viết các đoạn 'Phân tích & nhận định' cho Section IV."""
    from app.services import llm, market_analysis
    try:
        return market_analysis.generate()
    except llm.LLMNotConfigured as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.error("Tạo phân tích AI thất bại", exc_info=exc)
        raise HTTPException(502, "Lỗi tạo phân tích AI — kiểm tra cấu hình LLM hoặc log máy chủ.") from exc


@router.post("/generate-pdf", dependencies=_editor)
def api_generate_pdf(
    report_date: str | None = Query(None, description="DD-MM-YYYY"),
):
    """Xuất PDF từ draft (HTML → Chromium: trang đầu/cuối + header/footer + nhảy trang)."""
    rdate = _parse_date(report_date)
    path = generate_pdf_from_draft(rdate)
    if not path:
        raise HTTPException(404, "Không thể tạo PDF. Kiểm tra draft và cấu hình render.")
    return FileResponse(str(path), media_type="application/pdf", filename=path.name)


# ── Published bulletins (đã xuất) ──


@router.get("/published", dependencies=_auth)
def api_list_published():
    """Liệt kê các bản tin đã xuất (PDF trong data/bulletins/), mới nhất trước."""
    items: list[dict] = []
    if _OUTPUT_DIR.exists():
        files = list(_OUTPUT_DIR.glob("Ban-tin-ngay-*.pdf"))
        for p in sorted(files, key=lambda x: (x.stem, x.suffix), reverse=True):
            st = p.stat()
            items.append({
                "filename": p.name,
                "report_date": _date_from_filename(p.name),
                "format": p.suffix.lstrip(".").upper(),
                "size": st.st_size,
                "modified": datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds"),
                "download_url": f"/api/bulletins/published/{p.name}",
            })
    return {"bulletins": items}


@router.get("/published/{filename}", dependencies=_auth)
def api_download_published(filename: str):
    """Tải 1 bản tin đã xuất (.pdf) trong data/bulletins/ (chặn path traversal)."""
    safe = Path(filename).name
    if not safe.endswith(".pdf"):
        raise HTTPException(400, "Chỉ tải được file .pdf")
    path = _OUTPUT_DIR / safe
    if not path.exists():
        raise HTTPException(404, f"Không tìm thấy bản tin '{safe}'")
    return FileResponse(str(path), media_type="application/pdf", filename=safe)


@router.get("/published/{filename}/detail", response_model=BulletinDraft, dependencies=_auth)
def api_published_detail(filename: str):
    """Chi tiết 1 bản tin đã xuất: ưu tiên snapshot JSON, nếu chưa có thì dựng lại từ DB."""
    safe = Path(filename).name
    if not safe.endswith(".pdf"):
        raise HTTPException(400, "Tên file không hợp lệ")
    fpath = _OUTPUT_DIR / safe
    if not fpath.exists():
        raise HTTPException(404, f"Không tìm thấy bản tin '{safe}'")

    sidecar = fpath.with_suffix(".json")
    if sidecar.exists():
        return BulletinDraft.model_validate_json(sidecar.read_text(encoding="utf-8"))

    # Fallback: bản tin xuất trước khi có snapshot → dựng lại từ DB theo ngày trong tên file
    ds = _date_from_filename(safe)
    if not ds:
        raise HTTPException(404, "Không xác định được ngày bản tin từ tên file")
    d, m, y = ds.split("/")
    return create_draft(date(int(y), int(m), int(d)), use_crawlers=True)


# ── Image settings endpoints ──


@router.get("/images", dependencies=_auth)
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


@router.post("/images/{slot}", dependencies=_editor)
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


@router.delete("/images/{slot}", dependencies=_editor)
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
    """Ban-tin-ngay-DD-MM-YYYY.pdf → 'DD/MM/YYYY'."""
    m = re.search(r"(\d{2})-(\d{2})-(\d{4})", name)
    return f"{m.group(1)}/{m.group(2)}/{m.group(3)}" if m else None


def _parse_date(s: str | None) -> date:
    """Parse DD-MM-YYYY hoặc fallback hôm qua."""
    if not s:
        return date.today() - timedelta(days=1)
    parts = s.split("-")
    return date(int(parts[2]), int(parts[1]), int(parts[0]))

