"""Phép CHỈNH phương án giá sàn nháp: tăng/giảm theo bước · số tiền · %, đặt mức, đưa về mô hình /
giá hiện hành, hoàn tác. Dùng chung cho Trợ lý AI (người dùng nói "tăng tí xíu") và ô sửa tay trên
giao diện — một chỗ tính duy nhất (xem `floor_proposal`).

Mỗi thay đổi ghi 1 mục nhật ký kèm giá trị TRƯỚC khi đổi ⇒ hoàn tác được từng bước.
"""
from __future__ import annotations

from typing import Any

from app.services import floor_proposal as fp
from app.services import floor_recommend as fr

OPS = ("step", "amount", "percent", "set", "reset_model", "reset_current", "undo")
FIELDS = ("fob", "vnd")
MAX_CHANGES = 20

_ALL = [g for _, g in fp.TT_GRADES]
#: Nhóm chủng loại người dùng hay gọi chung ("tăng cả nhóm SVR", "các dòng RSS").
GROUPS: dict[str, tuple[str, list[str]]] = {
    "all": ("mọi chủng loại", _ALL),
    "svr": ("nhóm SVR", [g for g in _ALL if g.startswith("SVR")]),
    "svr_cv": ("nhóm SVR CV", ["SVR CV 50", "SVR CV60"]),
    "rss": ("nhóm RSS", ["RSS 3", "RSS 1"]),
    "latex": ("LATEX", ["LATEX"]),
    "skim": ("Skim Block", ["Skim Block"]),
}
_UNIT = {"fob": "USD/tấn", "vnd": "đồng/tấn"}
_STEP = {"fob": fr.FOB_STEP, "vnd": fr.VND_STEP}
_SNAP = ("fob", "vnd", "vnd_manual", "origin")


def _key(s: str) -> str:
    return "".join(str(s).lower().split())


_ALIASES: dict[str, str] = {}
for _tt, _g in fp.TT_GRADES:
    _ALIASES[_key(_g)] = _g
    _ALIASES[_key(_tt)] = _g
    for _part in _g.split("/"):
        _ALIASES.setdefault(_key(_part), _g)


def resolve(names: list[str] | None) -> tuple[list[str], str]:
    """Tên chủng loại/nhóm → (danh sách khoá theo thứ tự tờ trình, mô tả phạm vi). Rỗng = mọi chủng loại."""
    if not names:
        return list(_ALL), GROUPS["all"][0]
    picked: set[str] = set()
    desc: list[str] = []
    for n in names:
        k = _key(n)
        if k in GROUPS:
            picked.update(GROUPS[k][1])
            desc.append(GROUPS[k][0])
        elif k in _ALIASES:
            picked.add(_ALIASES[k])
            desc.append(_ALIASES[k])
        else:
            raise fp.ProposalError(f"Không có chủng loại/nhóm '{n}'. Chủng loại: "
                                   + ", ".join(_ALL) + "; nhóm: " + ", ".join(GROUPS) + ".")
    return [g for g in _ALL if g in picked], ", ".join(desc)


def _num(ch: dict) -> float:
    v = fp._num(ch.get("value"))
    if v is None:
        raise fp.ProposalError(f"Thao tác '{ch.get('op')}' cần giá trị số (value).")
    return v


def _action(op: str, v: float | None, field: str, fields: set[str]) -> str:
    """Mô tả thao tác (chưa kèm phạm vi), số đã định dạng. `fields` = trường THỰC SỰ bị chỉnh (dòng
    chỉ có giá nội địa luôn chỉnh ô nội địa — trước đây câu ghi "5 USD/tấn" cho cả Skim Block)."""
    up = "Tăng" if (v or 0) > 0 else "Giảm"
    unit = _UNIT[field]
    if op == "step":
        n = abs(int(round(v)))
        size = " · ".join(f"{fp.fmt_int(n * _STEP[f])} {_UNIT[f]}" for f in FIELDS if f in fields)
        return f"{up} {n} bước ({size})"
    if op == "amount":
        return f"{up} {fp.fmt_int(abs(v))} {unit}"
    if op == "percent":
        return f"{up} {abs(v):g}%".replace(".", ",")
    if op == "set":
        return f"Đặt {fp.fmt_int(v)} {unit}"
    return "Đưa về mức mô hình" if op == "reset_model" else "Đưa về giá hiện hành"


def _new_value(op: str, cur: float | None, v: float | None, field: str, unit: str) -> float | None:
    if op == "set":
        return fp.whole(v)
    if cur is None:
        return None
    if op == "step":
        return cur + int(round(v)) * _STEP[field]
    if op == "amount":
        return fp.whole(cur + v)
    return fr.to_step(cur * (1 + v / 100), unit)  # percent → làm tròn theo bước ban hành


def _change_line(before: dict, row: dict) -> str:
    parts = []
    for f in FIELDS:
        if before.get(f) != row.get(f):
            parts.append(f"{'FOB' if f == 'fob' else 'nội địa'} {fp.fmt_int(before.get(f))} → "
                         f"{fp.fmt_int(row.get(f))} {_UNIT[f]}")
    return f"{row['grade']}: " + " · ".join(parts)


def _apply_row(row: dict, op: str, v: float | None, field: str, by: str) -> tuple[dict | None, str | None]:
    """1 dòng → (dòng mới | None nếu không đổi, cảnh báo | None)."""
    dom = fp.is_domestic(row["grade"])
    f = "vnd" if dom else field
    new = dict(row)
    if op == "reset_model":
        if (row["model_vnd"] if dom else row["model_fob"]) is None:
            return None, f"{row['grade']}: chưa có mức mô hình — giữ nguyên."
        new.update(fob=row["model_fob"], vnd=row["model_vnd"], vnd_manual=False, origin="model")
        for k in FIELDS:
            if new[k] is not None:
                fp.check_range(new[k], k, row["grade"])
    elif op == "reset_current":
        new.update(fob=row["prev_fob"], vnd=row["prev_vnd"], vnd_manual=False, origin="current")
    else:
        if dom and field == "fob" and op in ("amount", "set"):
            return None, f"{row['grade']} chỉ có giá nội địa — bỏ qua (chỉnh riêng bằng đồng/tấn)."
        val = _new_value(op, row.get(f), v, f, "VNĐ/T" if f == "vnd" else "USD/T")
        if val is None:
            return None, f"{row['grade']}: chưa có giá để chỉnh — dùng 'đặt mức' để nhập số."
        fp.check_range(val, f, row["grade"])
        new[f] = val
        if f == "fob" and not row.get("vnd_manual"):
            auto = fp.vnd_from_fob(row, val)
            if auto is not None:
                new["vnd"] = auto
        if f == "vnd" and not dom:
            new["vnd_manual"] = True
        new["origin"] = "ai" if by == "ai" else "manual"
    if all(new.get(k) == row.get(k) for k in ("fob", "vnd")):
        return None, (f"{row['grade']}: mức thay đổi nhỏ hơn 1 bước ban hành — giữ nguyên."
                      if op == "percent" else None)
    return fp.derive(new), None


def _undo(prop: dict) -> tuple[dict, str]:
    if not prop["log"]:
        raise fp.ProposalError("Chưa có thay đổi nào để hoàn tác.")
    last = prop["log"][-1]
    rows, lines = [], []
    for r in prop["rows"]:
        b = last["before"].get(r["grade"])
        if not b:
            rows.append(r)
            continue
        new = fp.derive({**r, **b})
        lines.append(_change_line(r, new))
        rows.append(new)
    # Câu mô tả dựng lại từ SỐ, không chép `text` của nhật ký: nhật ký đi qua trình duyệt (và bản
    # nháp dùng chung) nên chữ trong đó không được đưa thẳng cho LLM.
    msg = "Đã hoàn tác lần chỉnh gần nhất" + (": " + "; ".join(lines) if lines else " (không có số nào đổi)")
    return {**prop, "rows": rows, "log": prop["log"][:-1]}, msg


def apply(prop: dict[str, Any], changes: list[dict], by: str = "manual") -> tuple[dict, list[str], list[str]]:
    """Áp lần lượt các thay đổi lên phương án (đã sanitize). Trả (phương án mới, mô tả đã làm, cảnh báo).

    Dữ liệu sai (chủng loại lạ, số ngoài khoảng hợp lý…) → ProposalError, KHÔNG áp nửa chừng.
    """
    if not isinstance(changes, list) or not changes:
        raise fp.ProposalError("Chưa có thay đổi nào.")
    if len(changes) > MAX_CHANGES:
        raise fp.ProposalError(f"Tối đa {MAX_CHANGES} thay đổi mỗi lần.")
    by = by if by in ("ai", "manual") else "manual"
    applied: list[str] = []
    warnings: list[str] = []
    for ch in changes:
        if not isinstance(ch, dict) or ch.get("op") not in OPS:
            raise fp.ProposalError("Thao tác không hợp lệ. Dùng: " + ", ".join(OPS) + ".")
        op = ch["op"]
        if op == "undo":
            prop, msg = _undo(prop)
            applied.append(msg)
            continue
        field = ch.get("field") or "fob"
        if field not in FIELDS:
            raise fp.ProposalError("field phải là 'fob' hoặc 'vnd'.")
        v = None if op in ("reset_model", "reset_current") else _num(ch)
        if op == "step" and int(round(v)) == 0:
            raise fp.ProposalError("Số bước phải khác 0.")
        grades, scope = resolve(ch.get("grades"))
        before: dict[str, dict] = {}
        lines: list[str] = []
        rows = []
        for r in prop["rows"]:
            if r["grade"] not in grades:
                rows.append(r)
                continue
            new, warn = _apply_row(r, op, v, field, by)
            if warn:
                warnings.append(warn)
            if new is None:
                rows.append(r)
                continue
            before[r["grade"]] = {k: r.get(k) for k in _SNAP}
            lines.append(_change_line(r, new))
            if new["off_step"]:
                warnings.append(f"{r['grade']}: mức mới không phải bội bước ban hành (5 USD/tấn FOB · "
                                "50.000 đồng/tấn nội địa) — vẫn giữ đúng số theo yêu cầu.")
            rows.append(new)
        if not before:
            continue
        act = _action(op, v, field, {"vnd" if fp.is_domestic(g) else field for g in before})
        full = (f"{act}: {lines[0]}" if len(lines) == 1
                else f"{act} cho {scope}: " + "; ".join(lines))
        text = full if len(lines) <= 3 else f"{act} cho {scope} ({len(lines)} chủng loại)"
        prop = {**prop, "rows": rows,
                "log": (prop["log"] + [{"at": fp.now_iso(), "by": by, "text": text[:500],
                                        "before": before}])[-fp.LOG_MAX:]}
        applied.append(full)
    return prop, applied, warnings
