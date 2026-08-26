"""SÁP NHẬP đơn vị thành viên — đơn vị A nhập vào đơn vị B kể từ một NGÀY HIỆU LỰC.

Nguyên tắc (chốt 24/08/2026): **tôn trọng số liệu trước sáp nhập**. Sáp nhập chỉ ghi 2 cột
metadata trên `member_unit` (`merged_into`, `merged_at`) và KHÔNG đụng tới một dòng số liệu nào —
mọi bản ghi cũ giữ nguyên `company` = tên đơn vị cũ.

Khác hẳn ĐỔI TÊN (`member_unit_repo.rename_unit`) vốn ghi đè `company` ở mọi bảng: đổi tên là một
pháp nhân đổi tên, còn sáp nhập là HAI pháp nhân. Ghi đè lịch sử của A sang B thì vĩnh viễn không
trả lời được câu "A lúc chưa sáp nhập làm được bao nhiêu" — đúng thứ mà tính năng này sinh ra để
trả lời. Hệ quả tốt kèm theo: **gỡ sáp nhập** chỉ là xoá 2 cột, không phải khôi phục dữ liệu.

Từ ngày hiệu lực:
- Đơn vị cũ `is_active = false` → biến khỏi mọi danh sách nhập liệu (phần lớn endpoint ghi đã chặn
  sẵn bằng `active_names()`), và `assert_can_enter` chặn ghi cho ngày >= ngày hiệu lực với thông
  báo chỉ rõ phải nhập vào đâu. Ngày TRƯỚC đó vẫn sửa được — số liệu cũ còn nguyên quyền chỉnh.
- Tài khoản đơn vị chuyển hẳn sang đơn vị mới (`app_user.member_units`).
- Báo cáo mặc định GỘP theo "dòng đời": số của A cộng vào B (xem `rollup_rows` / `expand`).
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any

from sqlalchemy import text

from app.core.db import ensure_schema, session_scope
from app.services import audit_repo, member_unit_repo


def _iso(v: Any) -> str | None:
    """date/str/None → 'YYYY-MM-DD' (so sánh ngày trong module này luôn là so sánh chuỗi ISO)."""
    if v is None or v == "":
        return None
    return v.isoformat() if isinstance(v, date) else str(v)[:10]


def _dmy(v: Any) -> str:
    """'2026-09-01' → '01/09/2026' cho câu thông báo người dùng đọc."""
    s = _iso(v)
    return f"{s[8:10]}/{s[5:7]}/{s[:4]}" if s else ""


def _units() -> dict[str, dict[str, Any]]:
    return {u["name"]: u for u in member_unit_repo.list_units()}


# ── Dòng đời đơn vị (A → B → C) ───────────────────────────────────────────────
def merge_map() -> dict[str, str]:
    """{đơn vị đã sáp nhập: đơn vị nhận TRỰC TIẾP}. Rỗng khi chưa có sáp nhập nào."""
    return {n: u["merged_into"] for n, u in _units().items() if u.get("merged_into")}


def _walk(name: str, mm: dict[str, str], at: dict[str, str], as_of: str | None) -> str:
    """Đi hết chuỗi sáp nhập A→B→C để ra đơn vị hiện hành TẠI NGÀY `as_of`.

    `as_of=None` = tính đến hiện tại (đi hết chuỗi). Có `as_of` thì chỉ đi qua những lần sáp nhập
    đã có hiệu lực tính đến ngày đó — kỳ báo cáo kết thúc TRƯỚC ngày sáp nhập thì lúc ấy hai đơn vị
    còn độc lập, gộp vào nhau là dựng một pháp nhân chưa tồn tại (và với tồn kho là cộng trùng
    chính lô hàng đó). `seen` chặn vòng của dữ liệu cũ.
    """
    seen, cur = {name}, name
    while (nxt := mm.get(cur)) and nxt not in seen:
        if as_of is not None and (not at.get(cur) or at[cur] > as_of):
            break
        seen.add(nxt)
        cur = nxt
    return cur


def _merged_at_map() -> dict[str, str]:
    return {n: _iso(u.get("merged_at")) for n, u in _units().items() if u.get("merged_into")}


def current_name(name: str, as_of: str | None = None) -> str:
    """Tên đơn vị hiện hành tương ứng với `name` tại ngày `as_of` (chưa sáp nhập → chính nó)."""
    return _walk(name, merge_map(), _merged_at_map(), _iso(as_of))


def rollup_map(as_of: str | None = None) -> dict[str, str]:
    """{đơn vị đã sáp nhập: đơn vị hiện hành} tính đến ngày `as_of` — dùng để GỘP số liệu báo cáo."""
    mm, at, day = merge_map(), _merged_at_map(), _iso(as_of)
    return {n: cur for n in mm if (cur := _walk(n, mm, at, day)) != n}


def lineage(name: str, as_of: str | None = None) -> list[str]:
    """`name` + MỌI đơn vị đã sáp nhập vào nó (kể cả gián tiếp). Dùng để CỘNG số liệu của cả dòng đời."""
    roll = rollup_map(as_of)
    return [name, *sorted(src for src, dst in roll.items() if dst == name)]


def expand(companies: list[str] | None, as_of: str | None = None) -> list[str] | None:
    """Mở rộng bộ lọc đơn vị theo dòng đời: chọn B là lấy luôn số của A đã sáp nhập vào B.

    None (không lọc) giữ nguyên None — không lọc thì vốn đã có đủ mọi đơn vị.
    """
    if not companies:
        return companies
    roll = rollup_map(as_of)
    keep = set(companies)
    return [*companies, *sorted(src for src, dst in roll.items() if dst in keep and src not in keep)]


def rollup_rows(rows: list[dict[str, Any]], region_of: dict[str, str | None] | None = None,
                as_of: str | None = None, *, key: str = "company",
                date_key: str | None = None) -> list[dict[str, Any]]:
    """Đổi tên đơn vị trên các dòng chi tiết về ĐƠN VỊ HIỆN HÀNH (gộp số liệu trước sáp nhập).

    Nhãn giữ ĐÚNG tên đơn vị hiện hành, không thêm "(gồm A)" (chốt 24/08/2026) — bảng số liệu phải
    đọc như mọi kỳ khác. Khu vực lấy theo đơn vị hiện hành, nếu không dòng cũ mang khu vực của đơn
    vị đã sáp nhập và bị tách thành nhóm riêng khi nhóm theo khu vực.

    Mốc thời gian để xét "đã sáp nhập hay chưa": `as_of` (một mốc cho cả bảng, thường là ngày cuối
    kỳ) hoặc `date_key` (lấy theo NGÀY CỦA TỪNG DÒNG — dùng cho bảng diễn biến theo ngày, để dòng
    của những ngày trước sáp nhập vẫn đứng tên đơn vị cũ).
    """
    day = None if date_key else _iso(as_of)
    roll = rollup_map(day)
    if not roll:
        return rows
    mm, at = merge_map(), _merged_at_map()
    out = []
    for r in rows:
        name = r.get(key)
        cur = (_walk(name, mm, at, _iso(r.get(date_key))) if date_key else roll.get(name))
        if not cur or cur == name:
            out.append(r)
            continue
        r = {**r, key: cur}
        if region_of is not None:
            r["region"] = region_of.get(cur)
        out.append(r)
    return out


def merged_units() -> list[dict[str, Any]]:
    """Các đơn vị ĐÃ sáp nhập: [{name, merged_into, merged_at}] — cho ô lọc "tách" ở màn thống kê."""
    return [{"name": n, "merged_into": u["merged_into"], "merged_at": _iso(u.get("merged_at"))}
            for n, u in sorted(_units().items()) if u.get("merged_into")]


def active_on(name: str, as_of: str | None) -> bool:
    """Đơn vị `name` còn là đơn vị ĐỘC LẬP tại ngày `as_of` chưa? (chưa sáp nhập / trước ngày hiệu lực)."""
    u = _units().get(name)
    if not u or not u.get("merged_into"):
        return True
    at = _iso(u.get("merged_at"))
    return bool(as_of and at and _iso(as_of) < at)


def merged_info(name: str) -> tuple[str, str] | None:
    """(đơn vị nhận, ngày hiệu lực 'dd/mm/yyyy') nếu `name` đã sáp nhập; None nếu chưa."""
    u = _units().get(name)
    if not u or not u.get("merged_into"):
        return None
    return u["merged_into"], _dmy(u.get("merged_at"))


# ── Gác ghi số liệu ───────────────────────────────────────────────────────────
def assert_can_enter(company: str, as_of: str | None = None, *,
                     require_known: bool = True) -> None:
    """Chặn ghi số liệu vào đơn vị không hợp lệ. Raise ValueError kèm câu chỉ rõ phải làm gì.

    `as_of` = NGÀY CỦA SỐ LIỆU (không phải hôm nay): số liệu của ngày TRƯỚC khi sáp nhập vẫn thuộc
    đơn vị cũ nên vẫn được sửa/bổ sung; chỉ số liệu từ ngày hiệu lực trở đi mới bị đẩy sang đơn vị
    mới. Không truyền `as_of` = thao tác không gắn với ngày cụ thể → coi như "từ nay", chặn.

    `require_known=False` cho những chỗ đã có gác riêng chặt hơn (tài khoản đơn vị thành viên chỉ
    ghi được cho đơn vị được gán): ở đó, một đơn vị bị xoá khỏi danh mục mà tài khoản vẫn còn gán
    thì không được biến thành "không nhập được gì nữa" — chỉ luật sáp nhập mới chặn.
    """
    u = _units().get(company)
    if u is None:
        if not require_known:
            return
        raise ValueError(f"Đơn vị “{company}” không có trong danh sách đơn vị thành viên.")
    if tgt := u.get("merged_into"):
        at = _iso(u.get("merged_at"))
        if not (as_of and at and _iso(as_of) < at):
            raise ValueError(f"Đơn vị “{company}” đã sáp nhập vào “{tgt}” từ {_dmy(at)} — "
                             f"số liệu từ ngày đó trở đi nhập vào “{tgt}”.")
        return
    if not u.get("is_active", True):
        raise ValueError(f"Đơn vị “{company}” đang ẩn khỏi danh sách nên không nhận số liệu mới.")


# ── Thao tác sáp nhập / gỡ sáp nhập ───────────────────────────────────────────
def _move_accounts(db, src: str, dst: str) -> list[str]:
    """Chuyển tài khoản đơn vị từ `src` sang `dst` (giữ thứ tự, bỏ trùng). Trả về username đã chuyển.

    Chốt 24/08/2026: chuyển HẲN — tài khoản không giữ lại đơn vị cũ. Số liệu trước sáp nhập vẫn còn
    nguyên trong hệ thống, do Tập đoàn tra cứu.
    """
    rows = db.execute(
        text("SELECT username, member_units FROM app_user "
             "WHERE member_units @> jsonb_build_array(CAST(:src AS text))"),
        {"src": src}).mappings().all()
    moved = []
    for r in rows:
        units, seen, new = list(r["member_units"] or []), set(), []
        for u in units:
            u = dst if u == src else u
            if u not in seen:
                seen.add(u)
                new.append(u)
        db.execute(text("UPDATE app_user SET member_units = CAST(:mu AS jsonb) WHERE username = :u"),
                   {"mu": json.dumps(new, ensure_ascii=False), "u": r["username"]})
        moved.append(r["username"])
    return moved


def _break_parent_cycle(db, name: str) -> None:
    """Cắt vòng trong cây mẹ–con nếu việc dời đơn vị con vừa tạo ra vòng (A→B→C→A).

    Cây mẹ–con vốn được `member_unit_repo.set_parent` canh không cho có vòng, nhưng ở đây các
    đơn vị con bị dời hàng loạt nên phải tự kiểm lại. Có vòng thì gỡ liên kết mẹ của `name` —
    mất một liên kết còn hơn để `internal_targets` đi vòng vô tận.
    """
    parent_of = lambda n: db.execute(                                     # noqa: E731
        text("SELECT parent_company FROM member_unit WHERE name = :n"), {"n": n}).scalar()
    seen, cur = {name}, parent_of(name)
    while cur and cur not in seen:
        seen.add(cur)
        cur = parent_of(cur)
    if cur is not None:            # dừng vì gặp lại một tên đã đi qua = có vòng
        db.execute(text("UPDATE member_unit SET parent_company = NULL WHERE name = :n"),
                   {"n": name})


def merge(src: str, dst: str, effective: str) -> dict[str, Any]:
    """Sáp nhập đơn vị `src` vào `dst` kể từ ngày `effective`. Raise ValueError nếu không hợp lệ."""
    ensure_schema()
    units = _units()
    eff = _iso(effective)
    if not eff:
        raise ValueError("Phải chọn ngày hiệu lực sáp nhập.")
    try:
        date.fromisoformat(eff)
    except ValueError as exc:
        raise ValueError("Ngày hiệu lực không hợp lệ (YYYY-MM-DD).") from exc
    if src not in units:
        raise ValueError(f"Không có đơn vị “{src}”.")
    if dst not in units:
        raise ValueError(f"Không có đơn vị nhận “{dst}”.")
    if src == dst:
        raise ValueError("Không thể sáp nhập một đơn vị vào chính nó.")
    if tgt := units[src].get("merged_into"):
        raise ValueError(f"“{src}” đã sáp nhập vào “{tgt}” từ {_dmy(units[src].get('merged_at'))}. "
                         "Gỡ sáp nhập trước nếu muốn làm lại.")
    if tgt := units[dst].get("merged_into"):
        raise ValueError(f"Đơn vị nhận “{dst}” đã sáp nhập vào “{tgt}” — hãy chọn thẳng “{tgt}”.")
    if not units[dst].get("is_active", True):
        raise ValueError(f"Đơn vị nhận “{dst}” đang ẩn khỏi danh sách — bật lại trước khi sáp nhập.")
    # Vòng lặp (A→B→A) không thể xảy ra khi đơn vị nhận buộc phải chưa sáp nhập, nhưng dữ liệu cũ
    # có thể đã lỡ có vòng — kiểm lại cho chắc, rẻ hơn nhiều so với một cây sáp nhập lặp vô hạn.
    if _walk(dst, merge_map(), _merged_at_map(), None) == src:
        raise ValueError(f"Sáp nhập “{src}” vào “{dst}” sẽ tạo vòng lặp trong chuỗi sáp nhập.")

    before = dict(units[src])
    with session_scope() as db:
        db.execute(
            text("UPDATE member_unit SET merged_into = :dst, merged_at = CAST(:eff AS date), "
                 "is_active = false WHERE name = :src"),
            {"dst": dst, "eff": eff, "src": src})
        # Đơn vị con đang trỏ về đơn vị cũ chuyển sang trỏ đơn vị mới — bỏ sót thì cây mẹ–con gãy
        # và "tiêu thụ nội bộ" của các đơn vị con mất luôn danh sách đơn vị nhận.
        # ⚠ Nếu chính ĐƠN VỊ NHẬN đang là con của đơn vị bị sáp nhập (công ty mẹ nhập vào công ty
        # con) thì gán thẳng sẽ thành "tự làm mẹ của chính mình" → gỡ luôn liên kết đó.
        children = db.execute(text("SELECT name FROM member_unit WHERE parent_company = :src"),
                              {"src": src}).scalars().all()
        db.execute(
            text("UPDATE member_unit SET parent_company = CASE WHEN name = :dst THEN NULL "
                 "ELSE :dst END WHERE parent_company = :src"),
            {"dst": dst, "src": src})
        _break_parent_cycle(db, dst)
        moved = _move_accounts(db, src, dst)

    after = _units().get(src)
    audit_repo.log("member_unit", "update", src, before=before, after=after, company=src,
                   note=f"Sáp nhập: {src} → {dst} từ {_dmy(eff)} "
                        f"(số liệu trước ngày này giữ nguyên ở {src}; "
                        f"{len(moved)} tài khoản, {len(children)} đơn vị con chuyển sang {dst})")
    return {"merged_into": dst, "merged_at": eff, "accounts_moved": moved,
            "children_moved": list(children)}


def unmerge(name: str) -> dict[str, Any]:
    """Gỡ sáp nhập: đơn vị hoạt động độc lập trở lại. Số liệu không phải khôi phục (chưa hề bị đụng).

    KHÔNG tự trả tài khoản về đơn vị cũ: lúc sáp nhập tài khoản đã chuyển hẳn sang đơn vị mới và
    có thể đã nhập số liệu ở đó — đoán ngược lại là sai. Cấp lại ở màn Người dùng.
    """
    ensure_schema()
    before = _units().get(name)
    if not before:
        raise ValueError(f"Không có đơn vị “{name}”.")
    if not before.get("merged_into"):
        raise ValueError(f"Đơn vị “{name}” không ở trạng thái đã sáp nhập.")
    with session_scope() as db:
        db.execute(text("UPDATE member_unit SET merged_into = NULL, merged_at = NULL, "
                        "is_active = true WHERE name = :n"), {"n": name})
    audit_repo.log("member_unit", "update", name, before=before, after=_units().get(name),
                   company=name,
                   note=f"Gỡ sáp nhập: {name} hoạt động độc lập trở lại "
                        f"(trước đó thuộc {before['merged_into']}). Tài khoản KHÔNG tự trả về.")
    return {"name": name, "was_merged_into": before["merged_into"]}
