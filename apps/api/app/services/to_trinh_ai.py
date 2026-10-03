"""AI soạn phần nhận định của TỜ TRÌNH giá sàn (mục I, II, cung – cầu) — như Báo cáo tuần: AI viết
nháp từ dữ liệu THẬT ([to_trinh_ai_context]), chuyên viên soát & sửa rồi mới lưu. Không tự lưu.

Văn phải HỢP với phương án: phương án tăng thì lập luận làm rõ yếu tố hỗ trợ giá (nêu rủi ro cân bằng),
giảm thì làm rõ áp lực giảm. Kèm cảnh báo: số không đối chiếu được, từ tuyệt đối, từ tiếng Anh, câu nói
giá sàn ngược chiều phương án.
"""
from __future__ import annotations

import re
from typing import Any

from app.services import llm
from app.services import to_trinh_ai_context as ctx
from app.services.floor_draft_stage import proposal_sig
from app.services.floor_proposal import now_iso
from app.services.to_trinh_memo import futures_paras
from app.services.weekly_number_check import absolute_words, english_words, unverified_numbers

MAX_TOKENS = 5000   # như Báo cáo tuần: model suy luận tính cả token suy nghĩ vào hạn mức
SKIP = "(bỏ qua)"
SECTIONS = {"NGUON": "futures_note", "SAN": "futures", "VATCHAT_GHICHU": "physical_note",
            "VATCHAT": "physical", "CUNGCAU": "outlook"}
_HEAD_RE = re.compile(r"^#{2,}\s*([A-Z_]+)\s*$")
_LEAD_RE = re.compile(r"^\s*\*{0,2}([^:]{3,90}?):\*{0,2}\s+(.+)$")
_WAY_RE = re.compile(r"(?:điều chỉnh|đề xuất|đề nghị|kiến nghị)\s+(tăng|giảm)|(tăng|giảm)\s+giá sàn", re.I)

SYSTEM = """Bạn là chuyên viên Ban Thị trường Kinh doanh (Ban TTKD), Tập đoàn Công nghiệp Cao su Việt Nam (VRG), \
soạn phần nhận định trong TỜ TRÌNH điều chỉnh giá sàn gửi Tổng Giám đốc.

VĂN PHONG: hành chính, khách quan, câu đầy đủ, tiếng Việt chuẩn; không dùng tiếng Anh trừ tên sàn, chủng loại, \
tổ chức (ANRPC…). Không gạch đầu dòng, không markdown đậm/nghiêng.

SỐ LIỆU: chỉ dùng số có trong NGỮ CẢNH, viết kiểu Việt Nam (2.849 · 0,7% · +19 USD/tấn), giữ đúng chiều tăng/giảm \
của bảng. Không tự tính số mới. Sàn "nghỉ giao dịch / không có giá" thì nói rõ là nghỉ, không đoán giá.

SỰ KIỆN: chỉ nêu sự kiện, nguyên nhân, tổ chức có trong ngữ cảnh (tin tức, báo cáo tuần). Không bịa.

LẬP LUẬN — BẮT BUỘC hợp với CHIỀU ĐIỀU CHỈNH CỦA PHƯƠNG ÁN: phương án TĂNG → làm rõ các yếu tố hỗ trợ giá \
(giá các sàn tăng, lực mua, nguồn cung eo hẹp, tồn kho giảm…), nêu rủi ro một cách cân bằng; GIẢM → làm rõ áp lực \
giảm; GIỮ NGUYÊN → thị trường chưa có xu hướng rõ, cần thận trọng; TRÁI CHIỀU → giải thích vì sao từng nhóm chủng \
loại đi khác nhau. Tuyệt đối không kết luận ngược chiều phương án. Không dùng từ tuyệt đối (chắc chắn, hoàn toàn, 100%…)."""

_FORMAT = """VIẾT ĐÚNG KHUNG SAU (giữ nguyên các dòng ###, không thêm gì ngoài khung):
### NGUON
Một câu ghi nguồn bảng I, bắt đầu bằng "Nguồn:", nêu ngày khảo sát và sàn nghỉ lễ (nếu có).
### SAN
Mỗi sàn MỘT đoạn, đúng thứ tự và mở đầu bằng ĐÚNG nhãn sau, rồi 3–5 câu (diễn biến giá dẫn số bảng I → nguyên \
nhân/bối cảnh → tác động tới giá cao su Việt Nam):
{leads}
### VATCHAT_GHICHU
Một câu ghi chú ngày tham chiếu giá vật chất nếu cần (vd ngày ANRPC chưa công bố); không cần thì ghi "(bỏ qua)".
### VATCHAT
Một đến hai đoạn diễn giải bảng II (chủng loại tăng/giảm mạnh nhất, so với kỳ hạn, nguyên nhân).
### CUNGCAU
Một đến hai đoạn về cán cân cung – cầu và triển vọng ngắn hạn; câu cuối nêu cơ sở để đề xuất điều chỉnh giá sàn \
lần này theo đúng chiều phương án ({way})."""


def prompt(context: str, leads: list[str], way: str) -> str:
    lead_lines = "\n".join(f"- {x}" for x in leads) or "- (theo các sàn trong bảng I)"
    return f"NGỮ CẢNH:\n{context}\n\n{_FORMAT.format(leads=lead_lines, way=way)}"


def _split_lead(line: str, leads: list[str]) -> dict[str, str]:
    plain = line.strip().strip("*").strip()
    for lead in leads:
        head = lead.rstrip(":")
        if plain.lower().startswith(head.lower()):
            return {"lead": lead, "text": plain[len(head):].lstrip(" :*").strip()}
    m = _LEAD_RE.match(plain)
    return {"lead": m.group(1).strip() + ":", "text": m.group(2).strip()} if m else {"lead": "", "text": plain}


def parse(out: str, leads: list[str]) -> dict[str, Any]:
    """Văn theo khung '### NGUON'… → các phần của nội dung tờ trình (phần trống/không có → không trả)."""
    buckets: dict[str, list[str]] = {}
    cur = None
    for raw in (out or "").splitlines():
        m = _HEAD_RE.match(raw.strip())
        if m:
            cur = SECTIONS.get(m.group(1))
            continue
        line = re.sub(r"^\s*(?:[-•*]\s+)", "", raw).strip()
        if cur and line and line != SKIP:
            buckets.setdefault(cur, []).append(line)
    res: dict[str, Any] = {}
    for key, lines in buckets.items():
        if key in ("futures_note", "physical_note"):
            res[key] = " ".join(lines)
        elif key == "futures":
            res[key] = [_split_lead(x, leads) for x in lines]
        else:
            res[key] = [{"lead": "", "text": x} for x in lines]
    return res


def _texts(part: dict[str, Any]) -> list[str]:
    out = []
    for v in part.values():
        out += [v] if isinstance(v, str) else [f"{p['lead']} {p['text']}" for p in v]
    return out


def warnings(part: dict[str, Any], context: str, way: str) -> list[str]:
    lines = _texts(part)
    out = []
    nums = unverified_numbers(lines, context)
    if nums:
        out.append("Số chưa đối chiếu được với dữ liệu (kiểm tra lại): " + ", ".join(nums[:12]))
    if absolute_words(lines):
        out.append("Có từ ngữ tuyệt đối: " + ", ".join(absolute_words(lines)))
    if english_words(lines):
        out.append("Còn từ tiếng Anh: " + ", ".join(english_words(lines)))
    if way in ("tăng", "giảm"):
        for m in _WAY_RE.finditer("\n".join(lines)):
            said = (m.group(1) or m.group(2)).lower()
            if said != way:
                out.append(f"Có câu nói giá sàn \"{said}\" trong khi phương án {way} — xem lại: «{m.group(0)}».")
                break
    if "futures" not in part or "outlook" not in part:
        out.append("AI chưa viết đủ các phần (diễn giải theo sàn / cung – cầu) — giữ nội dung cũ ở phần thiếu.")
    return out


def generate(draft: dict, memo: dict, username: str | None) -> dict[str, Any]:
    """Nội dung tờ trình mới = `memo` hiện tại + phần AI viết lại (I, II, cung – cầu). Không lưu."""
    context = ctx.build(draft, memo["inventory"])
    way = ctx.direction(draft["proposal"].get("rows") or [])["word"]
    leads = [p["lead"] for p in memo.get("futures") or [] if p.get("lead")]
    leads = leads or [p["lead"] for p in futures_paras(draft["doc"].get("settlement") or [], draft["doc"].get("t1"))]
    part = parse(llm.complete(SYSTEM, prompt(context, leads, way), max_tokens=MAX_TOKENS), leads)
    warns = warnings(part, context, way)
    new = {**memo, **part}
    new["ai"] = {"at": now_iso(), "by": username, "sig": proposal_sig(draft["proposal"]), "warnings": warns}
    return {"memo": new, "warnings": warns}
