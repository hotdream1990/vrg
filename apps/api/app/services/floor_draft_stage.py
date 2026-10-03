"""Bước của bản nháp giá sàn: Nháp → Dự thảo → Tờ trình → Áp dụng (plans/261003-quy-trinh-gia-san).

Mỗi phần chỉ sửa ở ĐÚNG bước của nó (server chặn, không tin giao diện): số phương án ở Nháp · tỷ giá
chú thích hình dự thảo ở Dự thảo · nội dung tờ trình ở Tờ trình. Đi tới từng nấc một; TRẢ VỀ được thẳng bước
bất kỳ phía trước (vd lãnh đạo không duyệt tờ trình → về Nháp sửa số), kèm lý do; lui không xoá gì.
Áp dụng có trong quy trình nhưng CHƯA làm — chưa ghi biểu giá sàn chính thức.
"""
from __future__ import annotations

import hashlib
import json

STAGES = ("nhap", "du_thao", "to_trinh", "ap_dung")
LABEL = {"nhap": "Nháp", "du_thao": "Dự thảo", "to_trinh": "Tờ trình", "ap_dung": "Áp dụng"}
#: Bước được sửa từng phần (tiêu đề + ghi chú: mọi bước trừ Áp dụng).
EDITABLE = {"proposal": "nhap", "sheet": "du_thao", "memo": "to_trinh"}
_PART = {"proposal": "số phương án", "sheet": "tỷ giá chú thích hình dự thảo", "memo": "nội dung tờ trình"}
APPLY_NOT_READY = ("Bước Áp dụng chưa triển khai: giá sàn chính thức vẫn nhập ở màn Giá sàn Tập đoàn "
                   "sau khi Tổng Giám đốc duyệt.")


class StageError(ValueError):
    """Thao tác không hợp với bước hiện tại — thông điệp tiếng Việt đưa thẳng cho người dùng."""


def normalize(stage: str | None) -> str:
    return stage if stage in STAGES else "nhap"


def proposal_sig(prop: dict | None) -> str:
    """Chữ ký số phương án (mức FOB · nội địa từng dòng) — đổi số là đổi chữ ký. Dùng để biết nội dung
    tờ trình AI soạn có còn khớp số hiện tại không."""
    rows = [(r.get("grade"), r.get("fob"), r.get("vnd")) for r in (prop or {}).get("rows") or []]
    return hashlib.sha1(json.dumps(rows, default=str).encode()).hexdigest()[:12]


def check_edit(stage: str, part: str) -> None:
    """Ném StageError nếu `part` không sửa được ở bước `stage`."""
    want = EDITABLE[part]
    if stage == want:
        return
    if stage == "ap_dung":
        raise StageError("Bản nháp đã ở bước Áp dụng — không sửa được nữa.")
    raise StageError(f"Chỉ sửa {_PART[part]} ở bước {LABEL[want]} (bản nháp đang ở bước {LABEL[stage]}). "
                     f"Chuyển về bước {LABEL[want]} để sửa.")


def missing_numbers(prop: dict) -> list[str]:
    """Dòng còn thiếu số — chưa đủ thì chưa chốt dự thảo được."""
    out = []
    for r in prop.get("rows") or []:
        need_fob = r.get("unit") != "VNĐ/T"
        if r.get("vnd") is None or (need_fob and r.get("fob") is None):
            out.append(r.get("label") or r.get("grade"))
    return out


def check_move(current: str, target: str, prop: dict) -> None:
    """Tới: một nấc, tới Dự thảo cần đủ số, Áp dụng chưa mở. Trả về: bước nào phía trước cũng được."""
    if target not in STAGES:
        raise StageError("Bước không hợp lệ.")
    i, j = STAGES.index(current), STAGES.index(target)
    if i == j:
        raise StageError(f"Bản nháp đã ở bước {LABEL[target]}.")
    if j > i + 1:
        raise StageError(f"Chỉ chuyển tới được bước kế tiếp (đang ở bước {LABEL[current]}); "
                         "trả về thì chọn được bước bất kỳ phía trước.")
    if target == "ap_dung":
        raise StageError(APPLY_NOT_READY)
    if target == "du_thao" and current == "nhap":
        miss = missing_numbers(prop)
        if miss:
            raise StageError("Chưa chốt dự thảo được — còn thiếu số ở: " + ", ".join(miss) + ".")
