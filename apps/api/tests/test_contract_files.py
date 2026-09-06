"""Danh sách định dạng file đính kèm được nhận (chứng từ hợp đồng · Hỗ trợ & Thông báo).

Đây là ALLOWLIST có yếu tố bảo mật: file được phục vụ lại cho trình duyệt, nên SVG/HTML (chèn
được JavaScript, chạy dưới chính tên miền hệ thống) phải bị từ chối. Test khoá cả 2 chiều.
"""

from __future__ import annotations

import io

import pytest
from fastapi import HTTPException, UploadFile
from starlette.datastructures import Headers

from app.services import attachment_store as store
from app.services import contract_files as cf


def _up(filename: str, content_type: str) -> UploadFile:
    return UploadFile(
        file=io.BytesIO(b"x" * 32), filename=filename,
        headers=Headers({"content-type": content_type}),
    )


@pytest.mark.parametrize(("name", "ct", "ext"), [
    ("hop-dong.pdf", "application/pdf", ".pdf"),
    ("scan.JPG", "image/jpeg", ".jpg"),
    ("anh.png", "image/png", ".png"),
    ("phu-luc.docx",
     "application/vnd.openxmlformats-officedocument.wordprocessingml.document", ".docx"),
    ("bang-ke.xlsx",
     "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", ".xlsx"),
    ("hoa-don.xml", "text/xml", ".xml"),
    ("bo-ho-so.zip", "application/zip", ".zip"),
    ("scan.tiff", "image/tiff", ".tiff"),
    # iPhone: Windows/Chrome thường KHÔNG khai được kiểu MIME của HEIC → phải nhận theo đuôi file.
    ("IMG_0042.HEIC", "", ".heic"),
    ("hop-dong.docx", "application/octet-stream", ".docx"),
])
def test_nhan_dung_dinh_dang_chung_tu(name: str, ct: str, ext: str) -> None:
    assert store.ext_of(_up(name, ct)) == ext


@pytest.mark.parametrize(("name", "ct"), [
    ("script.svg", "image/svg+xml"),      # SVG nhúng được JavaScript
    ("trang.html", "text/html"),          # HTML chạy ngay dưới tên miền hệ thống
    ("chay.exe", "application/x-msdownload"),
    ("khong-duoi", "application/octet-stream"),
])
def test_tu_choi_dinh_dang_ngoai_danh_sach(name: str, ct: str) -> None:
    assert store.ext_of(_up(name, ct)) is None
    with pytest.raises(HTTPException) as e:
        cf.save(_up(name, ct))
    assert e.value.status_code == 400


def test_loai_khong_xem_thang_thi_ep_tai_ve() -> None:
    """Chỉ PDF/ảnh thường mới mở thẳng trong trình duyệt; còn lại phải tải về (chống đoán kiểu)."""
    assert store.TYPES[".pdf"][1] is True
    assert store.TYPES[".jpg"][1] is True
    for ext in (".zip", ".docx", ".xml", ".heic"):
        assert store.TYPES[ext][1] is False
