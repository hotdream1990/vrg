"""Phương án giá sàn NHÁP trong phiên chat — Trợ lý lập/chỉnh theo lời người dùng.

Công cụ ở đây CÓ TRẠNG THÁI (`stateful`): nhận `ctx` của lượt hỏi (phương án hiện tại do frontend
gửi kèm + mức tư vấn) và ghi phương án mới vào `ctx`; `assistant_service` trả lại cho frontend.
Không ghi gì xuống DB — lưu bản nháp là thao tác riêng của người dùng trên giao diện.
Mọi phép tính ở `floor_proposal*` (LLM không tự cộng/làm tròn).
"""
from __future__ import annotations

from typing import Any

from app.core.market_meta import VRG_FLOOR_GRADES
from app.services import floor_proposal as fp
from app.services import floor_proposal_ops as ops
from app.services.assistant_tools._common import cols, dmy, table

_NOTE = ("Đây là PHƯƠNG ÁN NHÁP trong phiên chat — chưa ghi vào biểu giá sàn, không đổi số liệu hệ "
         "thống. Người dùng sửa tiếp được trên bảng phương án, xem trước tờ trình hoặc lưu bản nháp.")


def _fail(message: str) -> dict:
    """Lỗi của công cụ phương án — ghi rõ CHƯA đổi gì. Đo thực tế: với lỗi trơn, LLM vẫn trả lời
    "đã đưa về mức mô hình" trong khi công cụ đã từ chối."""
    return {"summary": {"error": message, "trang_thai": "KHÔNG THỰC HIỆN — phương án giữ nguyên, "
                                                        "phải nói rõ với người dùng là chưa đổi gì"}}


def _base_for(ctx: dict, wanted: str | None, default: str = "model") -> str:
    # "Chỉ tra số": Trợ lý không đưa mức mô hình (một dạng khuyến nghị) ⇒ luôn xuất phát từ giá hiện hành.
    if ctx.get("advice") == "data":
        return "current"
    return wanted if wanted in fp.BASES else default


def _lines(prop: dict, ctx: dict, grades: set[str] | None = None) -> list[str]:
    show_model = ctx.get("advice") != "data"
    return [fp.row_line(r, show_model) for r in prop["rows"] if grades is None or r["grade"] in grades]


def context_block(prop: dict, advice: str) -> str:
    """Khối hệ thống mô tả phương án đang mở — để LLM trả lời 'phương án giờ SVR 10 bao nhiêu'
    mà không phải gọi lại công cụ (số đã định dạng sẵn)."""
    lines = _lines(prop, {"advice": advice})
    return ("PHƯƠNG ÁN GIÁ SÀN NHÁP ĐANG MỞ TRONG PHIÊN (ngày " + dmy(prop["as_of"])
            + (f", so với lần ban hành {dmy(prop['prev_as_of'])}" if prop.get("prev_as_of") else "")
            + "; chưa lưu, KHÔNG phải giá chính thức). Bạn KHÔNG tự sửa được bảng này — mọi thay đổi "
            "(kể cả hoàn tác) PHẢI qua adjust_floor_proposal:\n- " + "\n- ".join(lines))


def _create(args: dict, ctx: dict) -> dict:
    cur = ctx.get("proposal")
    if cur and cur.get("log") and not args.get("replace"):
        # Lập lại = mất hết chỗ đã sửa (nhật ký cũng mất, không hoàn tác được) ⇒ phải hỏi người dùng.
        return _fail(f"Phương án đang mở đã có {len(cur['log'])} lần chỉnh. Lập lại từ đầu sẽ MẤT các "
                     "chỉnh sửa đó — hỏi người dùng xác nhận trước; đồng ý thì gọi lại với replace=true.")
    base = _base_for(ctx, args.get("base"))
    try:
        prop = fp.build(args.get("as_of"), base)
    except fp.ProposalError as exc:
        return _fail(str(exc))
    ctx["proposal"], ctx["changed"] = prop, True
    return {"summary": {
        "trang_thai": "Đã lập phương án nháp và hiện trên bảng bên cạnh khung chat.",
        "ngay": dmy(prop["as_of"]), "so_voi_lan_ban_hanh": dmy(prop.get("prev_as_of")),
        "xuat_phat": "mức mô hình" if base == "model" else "giá sàn hiện hành",
        "cac_dong": _lines(prop, ctx), "ghi_chu": _NOTE,
        **({"luu_y": "Mức tư vấn 'Chỉ tra số': phương án không kèm mức mô hình — không gợi ý 'đưa về "
                     "mô hình'; muốn dùng mức mô hình thì chuyển mức tư vấn."}
           if ctx.get("advice") == "data" else {})},
        "source": f"phương án nháp trong phiên · {dmy(prop['as_of'])}"}


def _changed_table(prop: dict, grades: set[str]) -> dict | None:
    rows = [{"grade": r["grade"], "fob": r.get("fob"), "fob_delta": r.get("fob_delta"),
             "vnd": r.get("vnd"), "vnd_delta": r.get("vnd_delta")}
            for r in prop["rows"] if r["grade"] in grades]
    return table("Phương án nháp — các dòng vừa chỉnh",
                 cols(("grade", "Chủng loại"), ("fob", "FOB (USD/tấn)"), ("fob_delta", "± so lần trước"),
                      ("vnd", "Nội địa (đồng/tấn)"), ("vnd_delta", "± so lần trước")), rows)


def _adjust(args: dict, ctx: dict) -> dict:
    changes = args.get("changes")
    if not isinstance(changes, list) or not changes:
        return _fail("Cần ít nhất một thay đổi (changes).")
    if ctx.get("advice") == "data" and any(isinstance(c, dict) and c.get("op") == "reset_model"
                                           for c in changes):
        return _fail("Chế độ 'Chỉ tra số' không dùng mức mô hình. Mời người dùng chuyển sang mức 'Theo "
                     "mô hình' hoặc 'Có điều chỉnh' ở đầu màn hình, hoặc tự nêu con số muốn đặt.")
    prop, created = ctx.get("proposal"), None
    try:
        if not prop:
            # Tự lập khi người dùng nói thẳng "tăng tí xíu": mặc định tính từ GIÁ HIỆN HÀNH. Đo thực tế:
            # hỏi "giá sàn mủ 10 hiện hành bao nhiêu? tăng lên tí xíu" mà xuất phát từ mức mô hình
            # (2.420) thì ra 2.425 — người dùng đang nhìn 2.220 và muốn 2.225.
            created = _base_for(ctx, args.get("base"), default="current")
            prop = fp.build(None, created)
        new, applied, warnings = ops.apply(prop, changes, by="ai")
    except fp.ProposalError as exc:
        return _fail(str(exc))
    touched = {r["grade"] for r, o in zip(new["rows"], prop["rows"])
               if (r.get("fob"), r.get("vnd")) != (o.get("fob"), o.get("vnd"))}
    ctx["proposal"], ctx["changed"] = new, True
    return {"summary": {
        "da_lam": applied or ["Không có dòng nào thay đổi."], "canh_bao": warnings,
        "moi_lap_phuong_an": ({"xuat_phat": "giá sàn hiện hành" if created == "current" else "mức mô hình"}
                              if created else False),
        "dong_da_doi": _lines(new, ctx, touched), "ghi_chu": _NOTE},
        "artifact": _changed_table(new, touched) if touched else None,
        "source": f"phương án nháp trong phiên · {dmy(new['as_of'])}"}


_GRADE_ENUM = list(VRG_FLOOR_GRADES) + list(ops.GROUPS)

TOOLS: dict[str, dict[str, Any]] = {
    "create_floor_proposal": {
        "run": _create, "stateful": True,
        "schema": {"name": "create_floor_proposal",
                   "description": "LẬP (hoặc lập lại từ đầu) PHƯƠNG ÁN GIÁ SÀN NHÁP trong phiên chat: bảng 14 chủng loại (FOB USD/tấn + nội địa đồng/tấn) hiện cạnh khung chat để người dùng sửa, xem trước tờ trình, lưu bản nháp. KHÔNG ghi vào biểu giá sàn. Chỉ gọi khi người dùng muốn lập phương án / bản nháp / tờ trình hoặc làm lại từ đầu.",
                   "parameters": {"type": "object", "properties": {
                       "as_of": {"type": "string", "description": "ngày tờ trình YYYY-MM-DD (mặc định hôm nay)"},
                       "base": {"type": "string", "enum": list(fp.BASES),
                                "description": "điểm xuất phát: model = mức mô hình (mặc định), current = giữ giá sàn hiện hành"},
                       "replace": {"type": "boolean",
                                   "description": "true CHỈ khi người dùng đã xác nhận bỏ các chỉnh sửa của phương án đang mở"}}}}},
    "adjust_floor_proposal": {
        "run": _adjust, "stateful": True,
        "schema": {"name": "adjust_floor_proposal",
                   "description": "CHỈNH phương án giá sàn nháp theo đúng yêu cầu của người dùng (chưa có phương án thì tự lập). Công cụ tự tính và làm tròn — KHÔNG tự tính số. 'tí xíu/chút/nhẹ' = op step value 1 (giảm: -1); 'X%' = op percent; 'X USD'/'X đồng' = op amount; 'lên/bằng X' = op set; 'như mô hình' = reset_model; 'giữ như lần trước' = reset_current; 'bỏ lần vừa rồi' = undo. FOB đổi thì giá nội địa tự tính theo; chỉ dùng field vnd khi người dùng nói rõ giá nội địa/đồng.",
                   "parameters": {"type": "object", "required": ["changes"], "properties": {
                       "base": {"type": "string", "enum": list(fp.BASES),
                                "description": "CHỈ dùng khi chưa có phương án: current = người dùng đang nói về giá sàn hiện hành (mặc định); model = đang nói về mức mô hình gợi ý"},
                       "changes": {"type": "array", "description": "các thay đổi, áp lần lượt", "items": {
                           "type": "object", "required": ["op"], "properties": {
                               "grades": {"type": "array", "items": {"type": "string", "enum": _GRADE_ENUM},
                                          "description": "chủng loại và/hoặc nhóm (all · svr · svr_cv · rss · latex · skim); bỏ trống = mọi chủng loại"},
                               "op": {"type": "string", "enum": list(ops.OPS)},
                               "value": {"type": "number", "description": "step: số bước ±; amount: ±số tiền; percent: ±%; set: mức mới (theo đơn vị của field)"},
                               "field": {"type": "string", "enum": list(ops.FIELDS),
                                         "description": "fob = FOB USD/tấn (mặc định) · vnd = nội địa đồng/tấn"}}}}}}}},
}
