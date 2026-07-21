"""Nhập/xuất số liệu báo cáo đơn vị bằng Excel — TẢI MẪU · ĐỌC FILE (xem trước) · GHI.

Mỗi loại biểu khai báo cột MỘT chỗ (`SPECS`) rồi dùng chung cho cả sinh file mẫu lẫn đọc file
người dùng nộp → mẫu và bộ đọc không bao giờ lệch nhau.

4 loại (`kind`):
  purchase   — Thu mua: 1 dòng / (đơn vị, ngày)
  sales      — Tiêu thụ: NHIỀU dòng / (đơn vị, ngày) → tách theo cột "Nguồn mủ" thành 2 mảng
               `sales` (mủ thu mua) và `sales_own` (mủ khai thác)
  stock      — Tồn kho: NHIỀU dòng / (đơn vị, ngày) → gom thành 3 khối tồn kho (chưa nhập kho ·
               đã nhập kho · đã ký HĐ) + ô nguyên liệu chưa sản xuất
  plan       — Kế hoạch năm: 1 dòng / (đơn vị, năm)

Ghi có MERGE: nhập Tiêu thụ không xoá Tồn kho của cùng bản ghi ngày đó và ngược lại.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

from app.core.market_meta import UNIT_STOCK_GRADES
from app.services import member_unit_repo, price_repo, unit_daily_repo
from app.services.unit_daily_fields import SALE_TABLES

TY = 1_000_000_000

CONTRACTS = {"Dài hạn": "long_term", "Chuyến": "spot"}
CHANNELS = {"XK / UTXK": "export", "Nội tiêu": "domestic"}
# Nguồn mủ của dòng tiêu thụ → ghi vào bảng nào (khớp `SALE_TABLES` ở unit_daily_fields).
# File cũ không có cột này: dòng trống mặc định là mủ thu mua (giữ nguyên cách hiểu trước đây).
SALE_SOURCES = {"Mủ thu mua": "sales", "Mủ khai thác": "sales_own"}
# 3 khối tồn kho nhập theo dòng (khối 4 "nguyên liệu chưa sản xuất" là 1 ô riêng, không theo dòng).
CUP_BASES = {"Độ TSC": "tsc", "Độ DRC": "drc"}
CCYS = {"VND": "VND", "USD": "USD"}
STOCK_GROUPS = {
    "Chế biến chưa nhập kho": "not_warehoused",
    "Đã nhập kho": "warehoused",
    "Đã ký HĐ": "signed_undelivered",
}
GRADES = list(UNIT_STOCK_GRADES)


@dataclass
class Col:
    key: str
    title: str
    unit: str = ""
    required: bool = False
    type: str = "num"                       # num | text | date | year | enum
    choices: dict[str, str] | None = None   # enum: {nhãn hiển thị: giá trị lưu}
    width: int = 16


@dataclass
class Spec:
    title: str
    sheet: str
    note: str
    cols: list[Col] = field(default_factory=list)


_UNIT_COL = Col("company", "Đơn vị", required=True, type="text", width=26)
_DATE_COL = Col("as_of", "Ngày", "dd/mm/yyyy", required=True, type="date")

SPECS: dict[str, Spec] = {
    "purchase": Spec(
        "BIỂU NHẬP — THU MUA", "Thu mua",
        "Mỗi dòng = 1 đơn vị / 1 ngày. Đơn giá ghi vào kho 'Giá mủ nguyên liệu'. "
        "Mủ nước luôn theo độ TSC; mủ chén theo cột 'Đơn giá mủ chén tính theo'.",
        [_UNIT_COL, _DATE_COL,
         Col("latex_wet", "SL thu mua mủ nước", "tấn"),
         Col("coagulum", "SL thu mua mủ chén", "tấn"),
         Col("price_latex", "Đơn giá mủ nước", "đồng/độ TSC", width=18),
         Col("price_cup", "Đơn giá mủ chén", "đồng/độ", width=18),
         Col("cup_basis", "Đơn giá mủ chén tính theo", "mặc định Độ TSC", type="enum",
             choices=CUP_BASES, width=22),
         Col("finished_qty", "SL thu mua thành phẩm", "tấn", width=20),
         Col("price_finished_vnd", "Đơn giá thành phẩm (VNĐ)", "triệu đ/tấn", width=22),
         Col("price_finished_fx", "Đơn giá thành phẩm (ngoại tệ)", "USD/tấn", width=24)]),
    "sales": Spec(
        "BIỂU NHẬP — TIÊU THỤ", "Tiêu thụ",
        "Mỗi dòng = 1 hợp đồng bán. Cùng (đơn vị, ngày) có thể nhiều dòng — hệ thống tự gộp. "
        "Cột 'Nguồn mủ' tách mủ thu mua / mủ khai thác (lưu riêng, tổng vẫn cộng chung). "
        "File này GHI ĐÈ TOÀN BỘ phần Tiêu thụ của ngày đó (cả 2 nguồn mủ) — dòng nào không có "
        "trong file sẽ bị xoá; phần Tồn kho giữ nguyên. "
        "Các file đính kèm (bộ Hợp đồng · phiếu xuất kho · hoá đơn) tải lên trên web — "
        "Excel không mang file được.",
        [_UNIT_COL, _DATE_COL,
         Col("source", "Nguồn mủ", "để trống = mủ thu mua", type="enum",
             choices=SALE_SOURCES, width=18),
         Col("contract", "Loại HĐ", required=True, type="enum", choices=CONTRACTS),
         Col("channel", "Hình thức", required=True, type="enum", choices=CHANNELS, width=18),
         Col("grade", "Loại mủ", required=True, type="enum",
             choices={g: g for g in GRADES}, width=20),
         Col("qty", "Số lượng", "tấn"),
         Col("price", "Giá bán", "triệu đ/tấn khi VND · USD/tấn khi USD", width=26),
         Col("sales_ccy", "Giá bán bằng", "VND | USD", type="enum", choices=CCYS, width=14),
         Col("warehouse_date", "Ngày xuất kho", "dd/mm/yyyy", type="date", width=18),
         Col("invoice_date", "Ngày xuất hoá đơn", "dd/mm/yyyy", type="date", width=18)]),
    "stock": Spec(
        "BIỂU NHẬP — TỒN KHO", "Tồn kho",
        "Mỗi dòng = 1 dòng tồn kho (số THỜI ĐIỂM cuối ngày, không cộng dồn). "
        "Nhóm 'Đã ký HĐ' mới cần Đơn giá / Lịch giao (file HĐ scan đính kèm trên web).",
        [_UNIT_COL, _DATE_COL,
         Col("group", "Nhóm", required=True, type="enum", choices=STOCK_GROUPS, width=20),
         Col("grade", "Chủng loại", required=True, type="enum",
             choices={g: g for g in GRADES}, width=20),
         Col("qty", "Số lượng", "tấn"),
         Col("price", "Đơn giá", "chỉ nhóm đã ký HĐ", width=18),
         Col("stock_ccy", "Đơn giá bằng", "VND | USD", type="enum", choices=CCYS, width=14),
         Col("delivery_date", "Lịch giao", "dd/mm/yyyy", type="date"),
         Col("stock_material", "Tồn kho nguyên liệu chưa sản xuất (quy khô)",
             "tấn", width=34)]),
    "plan": Spec(
        "BIỂU NHẬP — KẾ HOẠCH NĂM", "Kế hoạch năm",
        "Mỗi dòng = 1 đơn vị / 1 năm. Số liệu nhập 1 lần, cập nhật khi có thay đổi.",
        [_UNIT_COL, Col("year", "Năm", required=True, type="year", width=10),
         Col("plan_tonnes", "Kế hoạch thu mua", "tấn", width=20),
         Col("signed_lt_tonnes", "HĐ dài hạn đã ký", "tấn", width=20),
         Col("carry_lt_tonnes", "HĐ dài hạn năm trước chuyển sang", "tấn", width=28),
         Col("carry_spot_tonnes", "HĐ chuyến năm trước chuyển sang", "tấn", width=28)]),
}

_HEAD_FILL = PatternFill("solid", fgColor="D9E7D5")
_REQ_FILL = PatternFill("solid", fgColor="FCE9E7")


def template_columns(kind: str, allowed_units: list[str] | None) -> tuple[list[Col], str | None]:
    """Cột của file mẫu + đơn vị mặc định.

    Tài khoản chỉ quản 1 đơn vị → BỎ cột 'Đơn vị' (khỏi gõ tên mình), khi nhập tự gán đơn vị đó.
    """
    spec = SPECS[kind]
    only = allowed_units[0] if allowed_units and len(allowed_units) == 1 else None
    cols = [c for c in spec.cols if not (only and c.key == "company")]
    return cols, only


def build_template(kind: str, allowed_units: list[str] | None = None) -> bytes:
    """Sinh file Excel mẫu: header + đơn vị tính + ô chọn sẵn (dropdown) + sheet Danh mục."""
    spec = SPECS[kind]
    units = allowed_units if allowed_units else member_unit_repo.active_names()
    cols, only = template_columns(kind, allowed_units)
    wb = Workbook()
    ws = wb.active
    ws.title = spec.sheet

    ws.cell(row=1, column=1, value=spec.title).font = Font(bold=True, size=14)
    note = spec.note + (f"  ·  Áp dụng cho đơn vị: {only}" if only else "")
    ws.cell(row=2, column=1, value=note).font = Font(italic=True, color="666666")
    ws.cell(row=3, column=1, value="Cột tô đỏ là BẮT BUỘC. Không đổi tên/thứ tự cột.").font = Font(
        italic=True, size=9, color="B03A2E")

    head = 5
    for i, c in enumerate(cols, start=1):
        cell = ws.cell(row=head, column=i, value=c.title)
        cell.font = Font(bold=True, size=10)
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.fill = _REQ_FILL if c.required else _HEAD_FILL
        u = ws.cell(row=head + 1, column=i, value=c.unit)
        u.font = Font(size=8, italic=True, color="666666")
        u.alignment = Alignment(horizontal="center", wrap_text=True)
        ws.column_dimensions[get_column_letter(i)].width = c.width

    # Danh mục tham chiếu + dropdown cho cột đơn vị / enum.
    ref = wb.create_sheet("Danh mục")
    ref.cell(row=1, column=1, value="Đơn vị").font = Font(bold=True)
    for r, u in enumerate(units, start=2):
        ref.cell(row=r, column=1, value=u)
    ref.column_dimensions["A"].width = 28

    first, last = head + 2, head + 501          # 500 dòng cho người dùng nhập
    for i, c in enumerate(cols, start=1):
        letter = get_column_letter(i)
        if c.key == "company" and units:
            dv = DataValidation(
                type="list",
                formula1=f"='Danh mục'!$A$2:$A${len(units) + 1}",
                allow_blank=True)
            ws.add_data_validation(dv)
            dv.add(f"{letter}{first}:{letter}{last}")
        elif c.type == "enum" and c.choices:
            dv = DataValidation(
                type="list", formula1='"' + ",".join(c.choices.keys()) + '"', allow_blank=True)
            ws.add_data_validation(dv)
            dv.add(f"{letter}{first}:{letter}{last}")

    ws.freeze_panes = ws.cell(row=first, column=1)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _as_date(v: Any) -> str | None:
    if isinstance(v, datetime):
        return v.date().isoformat()
    if isinstance(v, date):
        return v.isoformat()
    s = str(v or "").strip()
    if not s:
        return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _as_num(v: Any) -> float | None:
    if v is None or (isinstance(v, str) and not v.strip()):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace(" ", "")
    # Người dùng hay gõ kiểu vi-VN: "1.234,5"
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def parse_upload(kind: str, data: bytes,
                 allowed_units: list[str] | None = None) -> dict[str, Any]:
    """Đọc file người dùng nộp → danh sách dòng đã chuẩn hoá + lỗi từng dòng (để XEM TRƯỚC)."""
    spec = SPECS[kind]
    try:
        wb = load_workbook(io.BytesIO(data), data_only=True)
    except Exception as exc:                                  # noqa: BLE001
        raise ValueError("Không đọc được file — hãy dùng đúng file mẫu (.xlsx).") from exc
    ws = wb[spec.sheet] if spec.sheet in wb.sheetnames else wb.worksheets[0]

    units = set(member_unit_repo.active_names())
    allowed = set(allowed_units) if allowed_units is not None else None
    default_company = allowed_units[0] if allowed_units and len(allowed_units) == 1 else None

    # Dò cột theo TIÊU ĐỀ (không theo vị trí cố định) → chịu được khi thiếu/đổi chỗ cột.
    head = 5
    titles = {}
    for i in range(1, ws.max_column + 1):
        t = str(ws.cell(row=head, column=i).value or "").strip()
        if t:
            titles.setdefault(t, i)
    idx: dict[str, int | None] = {c.key: titles.get(c.title) for c in spec.cols}
    missing = [c.title for c in spec.cols
               if c.required and idx[c.key] is None and not (c.key == "company" and default_company)]
    if missing:
        raise ValueError("File thiếu cột bắt buộc: " + ", ".join(missing) + ". Hãy dùng đúng file mẫu.")
    rows: list[dict[str, Any]] = []
    for r in range(head + 2, ws.max_row + 1):
        raw = [ws.cell(row=r, column=idx[c.key]).value if idx[c.key] else None for c in spec.cols]
        if all(v is None or str(v).strip() == "" for v in raw):
            continue
        rec: dict[str, Any] = {"_row": r, "_errors": []}
        for c, v in zip(spec.cols, raw):
            if c.key == "company" and idx["company"] is None and default_company:
                rec["company"] = default_company     # mẫu không có cột Đơn vị → gán đơn vị của tài khoản
                continue
            if c.type == "date":
                val = _as_date(v)
                if val is None and (c.required or (v not in (None, ""))):
                    rec["_errors"].append(f"{c.title}: ngày không hợp lệ")
            elif c.type == "year":
                n = _as_num(v)
                val = int(n) if n else None
                if val is None or not (2020 <= val <= 2100):
                    val = None
                    rec["_errors"].append(f"{c.title}: năm không hợp lệ")
            elif c.type == "enum":
                label = str(v or "").strip()
                val = (c.choices or {}).get(label)
                if val is None and label:
                    rec["_errors"].append(f"{c.title}: '{label}' không hợp lệ")
                elif val is None and c.required:
                    rec["_errors"].append(f"{c.title}: bắt buộc")
            elif c.type == "text":
                val = str(v).strip() if v not in (None, "") else None
            else:
                val = _as_num(v)
                if val is None and v not in (None, ""):
                    rec["_errors"].append(f"{c.title}: không phải số")
            rec[c.key] = val
            if c.required and rec.get(c.key) in (None, "") and not rec["_errors"]:
                rec["_errors"].append(f"{c.title}: bắt buộc")

        if rec.get("company") and rec["company"] not in units:
            rec["_errors"].append(f"Đơn vị '{rec['company']}' không có trong danh mục")
        elif allowed is not None and rec.get("company") and rec["company"] not in allowed:
            rec["_errors"].append(f"Đơn vị '{rec['company']}' không thuộc quyền của tài khoản")
        rows.append(rec)

    _mark_actions(kind, rows)
    ok = sum(1 for r in rows if not r["_errors"])
    return {
        "kind": kind, "rows": rows,
        # Nhãn cột tiếng Việt để bảng xem trước hiển thị dễ đọc (không phải khoá thô).
        "columns": [{"key": c.key, "title": c.title, "unit": c.unit} for c in spec.cols
                    if not (c.key == "company" and idx["company"] is None and default_company)],
        "summary": {"total": len(rows), "ok": ok, "error": len(rows) - ok},
    }


def _mark_actions(kind: str, rows: list[dict]) -> None:
    """Đánh dấu mỗi dòng sẽ TẠO MỚI hay GHI ĐÈ số đã có (để người dùng biết trước khi xác nhận)."""
    if kind == "plan":
        for r in rows:
            if r.get("company") and r.get("year"):
                cur = unit_daily_repo.year_plan(int(r["year"]), [r["company"]])
                r["_action"] = "update" if cur.get(r["company"]) else "create"
        return
    daily_kind = "purchase" if kind == "purchase" else "consumption"
    seen: dict[tuple[str, str], bool] = {}
    for r in rows:
        c, d = r.get("company"), r.get("as_of")
        if not c or not d:
            continue
        key = (c, d)
        if key not in seen:
            seen[key] = unit_daily_repo.has_entry(daily_kind, d, c)
        r["_action"] = "update" if seen[key] else "create"


def _sale_line(r: dict, ccy: str, fx: float | None) -> dict:
    """1 dòng Excel → 1 dòng bán để lưu.

    Gán loại tiền + tỷ giá xuống TỪNG DÒNG (Excel chỉ hỏi 1 lần cho cả file) để số đã lưu khớp
    đúng cách web tính lại doanh thu — mở phiếu ra lưu lại không bị đổi số.
    """
    return {
        "contract": r["contract"], "channel": r["channel"], "grade": r["grade"],
        "qty": r.get("qty"), "price": r.get("price"), "ccy": ccy, "fx": fx,
        "warehouse_date": r.get("warehouse_date"), "invoice_date": r.get("invoice_date"),
    }


def commit_rows(kind: str, rows: list[dict], username: str | None,
                allowed_units: list[str] | None = None) -> dict[str, Any]:
    """Ghi các dòng HỢP LỆ vào hệ thống (bỏ qua dòng có lỗi). Trả số bản ghi đã ghi."""
    # Client gửi lại danh sách dòng nên phải KIỂM LẠI ở đây (không tin bước xem trước):
    # đơn vị phải có thật và thuộc quyền tài khoản.
    valid_units = set(member_unit_repo.active_names())
    if allowed_units is not None:
        valid_units &= set(allowed_units)
    good = [r for r in rows
            if not (r.get("_errors") or []) and r.get("company") in valid_units]
    if kind == "plan":
        n = 0
        for r in good:
            unit_daily_repo.set_year_plan(int(r["year"]), r["company"], r.get("plan_tonnes"),
                                          r.get("signed_lt_tonnes"), r.get("carry_lt_tonnes"),
                                          r.get("carry_spot_tonnes"), username)
            n += 1
        return {"saved": n, "skipped": len(rows) - len(good), "warnings": []}

    currencies = member_unit_repo.currency_by_name()
    warnings: list[str] = []

    # Gom theo (đơn vị, ngày)
    grouped: dict[tuple[str, str], list[dict]] = {}
    for r in good:
        if r.get("company") and r.get("as_of"):
            grouped.setdefault((r["company"], r["as_of"]), []).append(r)

    saved = 0
    for (company, as_of), items in grouped.items():
        if kind == "purchase":
            it = items[-1]                                     # 1 dòng / ngày (lấy dòng cuối)
            fields = {k: it.get(k) for k in
                      ("latex_wet", "coagulum", "finished_qty", "price_finished_vnd", "price_finished_fx")
                      if it.get(k) is not None}
            # Cách tính độ của mủ chén phải gán TRƯỚC khi ghi, không thì không được lưu.
            basis = next((r.get("cup_basis") for r in items if r.get("cup_basis")), None)
            if basis:
                fields["cup_basis"] = basis
            unit_daily_repo.upsert("purchase", as_of, company, fields, username)
            for key, ptype in (("price_latex", "purchase"), ("price_cup", "purchase_cup")):
                if it.get(key) is not None:
                    price_repo.upsert_record({
                        "as_of": as_of, "source": "vrg", "grade": company, "contract": "",
                        "price_type": ptype, "price": float(it[key]),
                        "currency": "VND",
                        "unit": ("đồng/độ DRC" if ptype == "purchase_cup" and basis == "drc"
                                 else "đồng/độ TSC")})
        else:
            # MERGE: giữ nguyên phần còn lại của bản ghi ngày đó.
            cur = unit_daily_repo.entries_on("consumption", as_of).get(company) or {}
            fields = dict(cur.get("fields") or {})
            if kind == "sales":
                # Doanh thu về BASE = đồng. Loại tiền của giá bán lấy theo ô đã chọn trên form
                # (`sales_ccy`); bản ghi chưa có thì suy từ đơn vị (nước ngoài → USD).
                ccy = (next((r.get("sales_ccy") for r in items if r.get("sales_ccy")), None)
                       or fields.get("sales_ccy")
                       or ("VND" if currencies.get(company, "VND") == "VND" else "USD"))
                fields["sales_ccy"] = ccy
                fx = _as_num(fields.get("fx_revenue")) if ccy == "USD" else None
                # File Tiêu thụ mang CẢ 2 nguồn mủ (cột "Nguồn mủ") → ghi đè trọn phần tiêu thụ;
                # nguồn nào không có dòng nào trong file thì thành rỗng.
                for table in SALE_TABLES:
                    fields[table] = [_sale_line(r, ccy, fx) for r in items
                                     if (r.get("source") or "sales") == table]
                gross = sum((r.get("qty") or 0) * (r.get("price") or 0) for r in items)
                if ccy == "VND":
                    fields["revenue"] = round(gross * 1_000_000)   # giá là triệu đ/tấn
                elif fx:
                    fields["revenue"] = round(gross * fx)
                else:
                    fields.pop("revenue", None)   # thiếu tỷ giá → không đoán bừa doanh thu
                    warnings.append(
                        f"{company} {as_of}: chưa có tỷ giá USD nên chưa tính được doanh thu "
                        f"(nhập tỷ giá ở màn Báo cáo tiêu thụ rồi lưu lại).")
            else:
                # Tồn kho = số THỜI ĐIỂM, đơn vị TẤN (mẫu tuần mục 11–14).
                sccy = next((r.get("stock_ccy") for r in items if r.get("stock_ccy")), None)
                if sccy:
                    fields["stock_ccy"] = sccy
                pick = lambda g: [r for r in items if r.get("group") == g]  # noqa: E731
                fields["stock_not_warehoused"] = [
                    {"grade": r["grade"], "qty": r.get("qty")} for r in pick("not_warehoused")]
                fields["stock_warehoused"] = [
                    {"grade": r["grade"], "qty": r.get("qty")} for r in pick("warehoused")]
                fields["stock_signed_undelivered"] = [
                    {"grade": r["grade"], "qty": r.get("qty"), "price": r.get("price"),
                     "delivery_date": r.get("delivery_date")} for r in pick("signed_undelivered")]
                mat = next((r.get("stock_material") for r in items
                            if r.get("stock_material") is not None), None)
                if mat is not None:
                    fields["stock_material"] = mat
            unit_daily_repo.upsert("consumption", as_of, company, fields, username)
        saved += 1
    return {"saved": saved, "skipped": len(rows) - len(good), "warnings": warnings}
