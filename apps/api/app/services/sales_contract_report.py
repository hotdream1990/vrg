"""Tổng hợp TIÊU THỤ và KHỐI 3 (đã ký HĐ chưa giao) TỪ HỢP ĐỒNG — thay cho ô nhập tay cũ.

Hai con số hệ thống tự tính (chốt 30/07/2026), đơn vị KHÔNG nhập trực tiếp nữa:
  - **Tiêu thụ** = tổng các ĐỢT ĐÃ GIAO (đợt giao, hoặc hợp đồng giao-1-lần đã đánh dấu giao)
    có `delivered_at` nằm trong kỳ báo cáo.
  - **Khối 3** = sản lượng CỦA HỢP ĐỒNG − tổng đã giao tính tới ngày báo cáo (chốt 05/08/2026),
    cho tới khi hợp đồng được đánh dấu HOÀN THÀNH. Trước đây chỉ đếm phần đã chia thành đợt; nay
    tính trên hợp đồng vì đơn vị KHÔNG nhập hợp đồng khung — mỗi hợp đồng là một lô hàng thật.
Sản lượng đọc từ dòng chi tiết nên tách được theo chủng loại; doanh thu quy về ĐỒNG (xem `calc`).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text

from app.core import vn_text
from app.core.db import ensure_schema, session_scope
from app.services import sales_contract_calc as calc
from app.services.sales_contract_repo import _COLS, _row

_SELECT = f"SELECT {', '.join(_COLS)} FROM sales_contract"

#: Tổng sản lượng (tấn) của một cột `lines` jsonb — phải cho ra đúng số như `calc.total_qty`.
_QTY_SQL = ("COALESCE((SELECT sum(COALESCE(NULLIF(e->>'qty', '')::numeric, 0)) "
            "FROM jsonb_array_elements(%s) e), 0)")

#: Thành tiền (ĐỒNG) của một cột `lines` jsonb — phải cho ra đúng số như `calc.total_revenue_vnd`:
#: VND tính theo TRIỆU đồng/tấn, ngoại tệ nhân tỷ giá, và **NULL khi có bất kỳ dòng nào thiếu đơn
#: giá/tỷ giá** (thiếu là KHÔNG BIẾT, không được cộng phần còn lại rồi coi như đủ).
#: Chỉ dùng cho DÒNG TỔNG CỘNG — tổng phải tính trên toàn bộ hợp đồng khớp lọc, không thể gom ở
#: Python vì trang chỉ tải 25 dòng. `test_contract_totals_match_the_rows` khoá 2 công thức bằng nhau.
_REV_SQL = ("(SELECT CASE WHEN count(*) FILTER (WHERE v IS NULL) > 0 THEN NULL "
            "            ELSE COALESCE(sum(v), 0) END "
            "   FROM (SELECT NULLIF(e->>'qty', '')::numeric * NULLIF(e->>'price', '')::numeric "
            "                * CASE WHEN COALESCE(NULLIF(e->>'ccy', ''), 'VND') = 'VND' "
            "                       THEN 1000000 ELSE NULLIF(e->>'fx', '')::numeric END AS v "
            "           FROM jsonb_array_elements(%s) e) t)")


def _fetch(companies: list[str] | None, extra: list[str] | None = None,
           params: dict | None = None) -> list[dict[str, Any]]:
    """Đọc hợp đồng theo bộ lọc — dữ liệu nhỏ nên gom về Python tính cho dễ đọc/dễ kiểm."""
    ensure_schema()
    where, args = ["1 = 1"], dict(params or {})
    if companies is not None:
        if not companies:
            return []
        where.append("company = ANY(:cs)")
        args["cs"] = list(companies)
    where.extend(extra or [])
    with session_scope() as db:
        rows = db.execute(text(f"{_SELECT} WHERE {' AND '.join(where)} ORDER BY company, id"),
                          args).mappings().all()
    return [_row(r) for r in rows]


def _by_grade(lines) -> dict[str, float]:
    """{chủng loại: sản lượng TIÊU THỤ THỰC TẾ} — latex/mủ NL tính theo QUY KHÔ (xem `calc.sale_qty`)."""
    out: dict[str, float] = {}
    for ln in lines or []:
        out[ln.get("grade") or ""] = out.get(ln.get("grade") or "", 0.0) + calc.sale_qty(ln)
    return out


def deliveries(date_from: str, date_to: str, companies: list[str] | None = None,
               customer_ids: list[int] | None = None,
               grades: list[str] | None = None) -> list[dict[str, Any]]:
    """Các LẦN GIAO có ngày giao trong [date_from, date_to] — nguồn số tiêu thụ của kỳ.

    Đợt giao KHÔNG mang khách hàng lẫn loại hợp đồng (cả hai gán ở hợp đồng) → gắn `customer_id`
    và `contract_type` của hợp đồng vào từng lần giao, nếu không thì không lọc/thống kê theo khách hàng
    và không tách được chỉ tiêu "HĐ dài hạn / HĐ chuyến".

    `grades` lọc theo CHỦNG LOẠI ở mức DÒNG: một lần giao có thể gồm nhiều chủng loại, nên phải
    bỏ các dòng không khớp rồi TÍNH LẠI sản lượng/quy khô/thành tiền của lần giao đó. Giữ nguyên
    cả lần giao là cộng luôn sản lượng của chủng loại người dùng không chọn.
    """
    rows = _fetch(companies,
                  ["delivered", "delivered_at IS NOT NULL",
                   "delivered_at >= CAST(:df AS date)", "delivered_at <= CAST(:dt AS date)"],
                  {"df": date_from, "dt": date_to})
    # Hợp đồng giao-1-lần thì chính nó là "hợp đồng mẹ"; đợt giao lấy mã của mẹ ở vòng dưới.
    for r in rows:
        r["parent_code"] = r["code"]
    parent_ids = sorted({r["parent_id"] for r in rows if r["parent_id"] is not None})
    if parent_ids:
        owner = {p["id"]: (p["customer_id"], p["contract_type"], p["code"])
                 for p in _fetch(None, ["id = ANY(:ps)"], {"ps": parent_ids})}
        for r in rows:
            if r["parent_id"] is not None:
                r["customer_id"], r["contract_type"], r["parent_code"] = owner.get(
                    r["parent_id"], (None, None, None))
    if customer_ids:
        keep = set(customer_ids)
        rows = [r for r in rows if r.get("customer_id") in keep]
    if grades:
        rows = _only_grades(rows, grades)
    # Số SẢN LƯỢNG của mọi báo cáo tiêu thụ lấy theo QUY KHÔ khi dòng có quy khô (PA1 — 04/08/2026).
    # Ghi đè ngay tại đây để mọi nơi đọc `deliveries()` (báo cáo kỳ, thống kê, tiêu thụ) cùng một số;
    # `revenue` vẫn tính trên mủ nước nên KHÔNG đụng tới. `qty_wet` giữ lại số cân thực tế của
    # latex/mủ nguyên liệu để báo cáo hiện được cả hai gốc số.
    for r in rows:
        r["qty"] = calc.total_sale_qty(r["lines"])
        r["qty_wet"] = calc.total_wet_qty(r["lines"])
    return rows


def _only_grades(rows: list[dict[str, Any]], grades: list[str]) -> list[dict[str, Any]]:
    """Giữ lại các dòng chi tiết thuộc `grades` rồi tính lại số tổng của từng lần giao.

    Lần giao không còn dòng nào khớp thì bị loại hẳn — kể cả khỏi số ĐẾM lần giao, vì với chủng
    loại đang lọc thì lần giao đó không tồn tại.
    """
    keep, out = set(grades), []
    for r in rows:
        lines = [ln for ln in (r.get("lines") or []) if (ln.get("grade") or "") in keep]
        if not lines:
            continue
        out.append({**r, "lines": lines,
                    "qty": calc.total_sale_qty(lines), "qty_dry": calc.total_qty_dry(lines),
                    "qty_wet": calc.total_wet_qty(lines),
                    "revenue": calc.total_revenue_vnd(lines)})
    return out


def consumption(date_from: str, date_to: str, companies: list[str] | None = None,
                customer_ids: list[int] | None = None,
                grades: list[str] | None = None) -> dict[str, dict[str, Any]]:
    """{đơn vị: số tiêu thụ trong kỳ} — cộng dồn sản lượng/doanh thu, tách theo hình thức.

    `revenue` = None khi CÓ lần giao thiếu tỷ giá → báo cáo hiển thị "—" thay vì một số sai.
    `by_customer` tách sản lượng/doanh thu theo khách hàng (yêu cầu C1 của khách).
    """
    out: dict[str, dict[str, Any]] = {}
    for c in deliveries(date_from, date_to, companies, customer_ids, grades):
        acc = out.setdefault(c["company"], {
            "qty": 0.0, "qty_dry": 0.0, "qty_wet": 0.0, "revenue": 0.0, "revenue_missing": False,
            "deliveries": 0, "by_channel": {}, "by_grade": {}, "by_customer": {}, "by_type": {},
            "by_type_channel": {},
        })
        cu = str(c.get("customer_id") or 0)
        cus = acc["by_customer"].setdefault(cu, {"qty": 0.0, "revenue": 0.0})
        cus["qty"] += c["qty"]
        cus["revenue"] += c["revenue"] or 0.0
        acc["qty"] += c["qty"]
        acc["qty_dry"] += c["qty_dry"]
        acc["qty_wet"] += c["qty_wet"]
        acc["deliveries"] += 1
        if c["revenue"] is None:
            acc["revenue_missing"] = True
        else:
            acc["revenue"] += c["revenue"]
        ch = c.get("channel") or "domestic"
        acc["by_channel"][ch] = acc["by_channel"].get(ch, 0.0) + c["qty"]
        # Loại hợp đồng lấy từ mẹ (đã gắn ở `deliveries`); dữ liệu chưa khai gom vào khoá rỗng
        # thay vì dồn vào một loại — dồn là làm sai chỉ tiêu dài hạn/chuyến.
        ct = c.get("contract_type") or ""
        acc["by_type"][ct] = acc["by_type"].get(ct, 0.0) + c["qty"]
        # Mẫu báo cáo cần ô chéo (dài hạn × xuất khẩu, chuyến × trong nước…) nên giữ luôn bảng chéo.
        acc["by_type_channel"][f"{ct}|{ch}"] = acc["by_type_channel"].get(f"{ct}|{ch}", 0.0) + c["qty"]
        for g, q in _by_grade(c["lines"]).items():
            acc["by_grade"][g] = acc["by_grade"].get(g, 0.0) + q
    for acc in out.values():
        if acc.pop("revenue_missing"):
            acc["revenue"] = None
    return out


#: Sản lượng theo CHỦNG LOẠI của một cột `lines` jsonb, mỗi dòng chi tiết một bản ghi.
#: Lấy CẢ HAI gốc số: `qty` = mủ nước ghi trên giấy, `qty_sale` = quy khô đã khai (thành phẩm không
#: có quy khô thì chính số lượng đã là số khô — quy ước của `calc.sale_qty`). `_remaining_by_grade`
#: chọn gốc theo từng dòng: dòng nào cam kết có khai quy khô thì trừ trên khô, không thì trừ trên nước.
_GRADE_SQL = ("COALESCE(NULLIF(e->>'grade', ''), '(chưa khai)') AS grade, "
              "COALESCE(NULLIF(e->>'qty', '')::numeric, 0) AS qty, "
              "COALESCE(NULLIF(e->>'qty_dry', '')::numeric, 0) AS qty_dry, "
              "COALESCE(NULLIF(NULLIF(e->>'qty_dry', '')::numeric, 0), "
              "NULLIF(e->>'qty', '')::numeric, 0) AS qty_sale")

#: Khối 3 tại ngày :d = cam kết của HỢP ĐỒNG − đã giao tính tới hết ngày đó, tách theo chủng loại.
#: Gom ở SQL chứ không kéo cả bảng về Python: lưới nhập liệu gọi hàm này MỘT LẦN CHO MỖI NGÀY,
#: mà số hợp đồng thì tăng đều (đã hơn 3.000) — quét cả bảng 30 lần là treo màn hình.
_BLOCK3_SQL = """
WITH parent AS (
    SELECT id, company, code, customer_id, sign_date, expiry_date, lines, delivered_at
    FROM sales_contract
    WHERE parent_id IS NULL
      AND (sign_date IS NULL OR sign_date <= CAST(:d AS date))
      AND (completed_at IS NULL OR completed_at > CAST(:d AS date))
      {scope}
), commit_g AS (
    SELECT p.id, {grade_sql} FROM parent p CROSS JOIN LATERAL jsonb_array_elements(p.lines) e
), done_g AS (
    SELECT p.id, {grade_sql} FROM parent p CROSS JOIN LATERAL jsonb_array_elements(p.lines) e
     WHERE p.delivered_at IS NOT NULL AND p.delivered_at <= CAST(:d AS date)
    UNION ALL
    SELECT k.parent_id AS id, {grade_sql}
      FROM sales_contract k CROSS JOIN LATERAL jsonb_array_elements(k.lines) e
     WHERE k.parent_id IN (SELECT id FROM parent)
       AND k.delivered_at IS NOT NULL AND k.delivered_at <= CAST(:d AS date)
), c AS (SELECT id, grade, sum(qty) AS qty, sum(qty_dry) AS qty_dry FROM commit_g GROUP BY 1, 2
), d AS (SELECT id, grade, sum(qty) AS qty, sum(qty_sale) AS qty_sale, sum(qty_dry) AS qty_dry,
                count(*) FILTER (WHERE qty_dry = 0) AS no_dry FROM done_g GROUP BY 1, 2
), dtot AS (SELECT id, sum(qty_sale) AS qty_sale FROM done_g GROUP BY 1)
SELECT p.id, p.company, p.code, p.customer_id, p.sign_date, p.expiry_date,
       c.grade, c.qty AS commit_wet, c.qty_dry AS commit_dry,
       COALESCE(dtot.qty_sale, 0) AS done_sale_total,
       COALESCE(d.qty, 0) AS done_wet, COALESCE(d.qty_sale, 0) AS done_sale,
       COALESCE(d.qty_dry, 0) AS done_dry, COALESCE(d.no_dry, 0) AS done_no_dry
  FROM parent p
  JOIN c ON c.id = p.id
  LEFT JOIN d ON d.id = p.id AND d.grade = c.grade
  LEFT JOIN dtot ON dtot.id = p.id
 ORDER BY p.company, p.id
"""


def _remaining_by_grade(rows: list[dict[str, Any]]) -> tuple[float, dict[str, float]]:
    """Phần CHƯA GIAO của một hợp đồng: tổng và tách theo chủng loại.

    Trừ THẲNG trên số đã khai, KHÔNG suy ra tỷ lệ khô rồi quy đổi (chốt 18/08/2026) — đơn vị chỉ
    khai hai con số nước/khô chứ không khai tỷ lệ nào, tự suy ra tỷ lệ là bịa thêm dữ kiện.

    Gốc số chọn theo TỪNG DÒNG cam kết, vì cam kết và đã giao phải trừ nhau trên cùng một gốc:
      · CẢ cam kết LẪN mọi đợt giao của chủng loại đó đều có số khô → trừ trên KHÔ;
      · còn lại → trừ trên MỦ NƯỚC. Thành phẩm thì nước = khô nên không khác gì; latex mà một bên
        bỏ trống ô quy khô thì bên đó KHÔNG BIẾT khô bao nhiêu — ghép số khô của bên này với số
        nước của bên kia sẽ đẻ ra phần dư ảo, hoặc trừ vống lên thành đã giao hết.
    Chọn theo dòng chứ không theo cả hợp đồng: một tờ hợp đồng bán cả latex lẫn thành phẩm thì dòng
    thành phẩm — vốn đã là hàng khô — không được ăn theo gốc số của dòng latex.

    Tổng luôn là `cam kết − đã giao` (không âm). Phần theo chủng loại lấy hiệu của từng chủng loại,
    rồi HẠ ĐỀU cho khớp tổng: giao vượt ở chủng loại này / giao chủng loại khác với hợp đồng sẽ làm
    tổng hai bên lệch nhau, khi đó cột tổng và bảng chi tiết phải kể cùng một câu chuyện.
    """
    commit_total = done_total = 0.0
    by_grade: dict[str, float] = {}
    for r in rows:
        # Chỉ trừ trên KHÔ khi CẢ HAI bên đều có số khô. Đợt giao bỏ trống ô quy khô là KHÔNG BIẾT
        # nó khô bao nhiêu — mượn tạm số mủ nước của nó để trừ vào cam kết khô sẽ trừ vống lên,
        # hợp đồng còn hàng mà báo đã giao hết.
        on_dry = float(r["commit_dry"] or 0) > 0 and not int(r["done_no_dry"] or 0)
        commit = float((r["commit_dry"] if on_dry else r["commit_wet"]) or 0)
        done = float((r["done_dry"] if on_dry else r["done_wet"]) or 0)
        commit_total += commit
        done_total += done
        left = commit - done
        if left > 1e-9:
            by_grade[r["grade"]] = by_grade.get(r["grade"], 0.0) + left
    # Hàng đã giao của chủng loại KHÔNG có trên hợp đồng vẫn phải trừ vào tổng — nếu không, giao
    # nhầm chủng loại sẽ để lại một phần dư không bao giờ hết. Phần này tính theo quy khô.
    spill = float(rows[0]["done_sale_total"] or 0) - sum(float(r["done_sale"] or 0) for r in rows)
    total = max(0.0, commit_total - done_total - max(0.0, spill))
    spread = sum(by_grade.values())
    if spread > total + 1e-9 and spread > 0:
        by_grade = {g: q * total / spread for g, q in by_grade.items()}
    return total, by_grade


def undelivered_on(as_of: str, companies: list[str] | None = None,
                   grades: list[str] | None = None) -> dict[str, dict[str, Any]]:
    """{đơn vị: {qty, by_grade, items}} — ĐÃ KÝ HĐ CHƯA GIAO tại ngày `as_of` (khối 3).

    Chốt 05/08/2026 — tính TRÊN HỢP ĐỒNG: `sản lượng hợp đồng − đã giao tính tới ngày as_of`.
    Một hợp đồng nằm trong khối 3 từ **ngày ký** cho tới khi giao hết, hoặc tới ngày được đánh dấu
    **hoàn thành** (thực giao lệch với hợp đồng là chuyện thường — chốt hoàn thành để phần chênh
    rời khỏi khối này).

    Phép trừ chạy trên SỐ QUY KHÔ đã khai của từng dòng (latex/mủ nguyên liệu lấy ô "Quy khô",
    thành phẩm thì chính số lượng đã là số khô) — cùng đơn vị tính với cột sản lượng tiêu thụ đứng
    ngay bên cạnh, và KHÔNG quy đổi theo tỷ lệ nào cả — xem `_remaining_by_grade`.
    """
    ensure_schema()
    scope, params = "", {"d": as_of}
    if companies is not None:
        if not companies:
            return {}
        scope, params["cs"] = "AND company = ANY(:cs)", list(companies)
    sql = _BLOCK3_SQL.format(scope=scope, grade_sql=_GRADE_SQL)
    with session_scope() as db:
        # Tắt JIT cho RIÊNG truy vấn này. `jsonb_array_elements` làm Postgres ước lượng 243.000
        # dòng trong khi thực tế ~2.600 → vượt `jit_above_cost` nên nó biên dịch lại toàn bộ mỗi
        # lượt gọi rồi vứt đi. Đo trên prod 21/09/2026: Emission 56ms trong Execution 144ms;
        # tắt JIT còn 66ms/lượt. Khối này bị gọi MỘT LẦN MỖI NGÀY của ảnh chụp nên 60 ngày là
        # gần 4 giây chỉ để biên dịch. `SET LOCAL` chỉ áp trong giao dịch hiện tại.
        db.execute(text("SET LOCAL jit = off"))
        rows = db.execute(text(sql), params).mappings().all()

    per_contract: dict[int, list[dict[str, Any]]] = {}
    for r in rows:
        per_contract.setdefault(r["id"], []).append(dict(r))

    out: dict[str, dict[str, Any]] = {}
    for lines in per_contract.values():
        head = lines[0]
        total, by_grade = _remaining_by_grade(lines)
        if grades:
            by_grade = {g: q for g, q in by_grade.items() if g in grades}
            total = sum(by_grade.values())
        if total <= 1e-9:
            continue
        acc = out.setdefault(head["company"], {"qty": 0.0, "by_grade": {}, "items": []})
        acc["qty"] += total
        for g, q in by_grade.items():
            acc["by_grade"][g] = acc["by_grade"].get(g, 0.0) + q
        acc["items"].append({
            "id": head["id"], "code": head["code"], "parent_id": None,
            "customer_id": head["customer_id"],
            "sign_date": str(head["sign_date"]) if head["sign_date"] else None,
            "expiry_date": str(head["expiry_date"]) if head["expiry_date"] else None,
            "qty": sum(float(r["commit_wet"] or 0) for r in lines),
            "remaining": total, "by_grade": by_grade,
        })
    return out


def delivered_revenue(contract: dict[str, Any], kid_revenues: list[float | None]) -> float | None:
    """TIỀN CỦA HÀNG THỰC GIAO (đồng) — KHÁC `revenue` là tiền ghi trên hợp đồng đã ký.

    Sản lượng và đơn giá của từng đợt được chốt lúc giao, nên tổng tiền đã giao lệch với tiền hợp
    đồng là chuyện bình thường (chốt 10/08/2026 — khách cần cả hai số để đối chiếu). Hợp đồng giao
    1 lần: giao rồi thì tiền đã giao chính là tiền hợp đồng, chưa giao thì bằng 0.

    None = có dòng ngoại tệ thiếu tỷ giá → màn hình hiện “—”, KHÔNG hiện 0 (0 bị đọc là bán không
    thu tiền). Một đợt thiếu tỷ giá là cả tổng không biết, không cộng phần còn lại rồi coi là đủ.
    """
    if contract["delivery_type"] == "multi":
        return None if any(v is None for v in kid_revenues) else float(sum(kid_revenues))
    return contract["revenue"] if contract["delivered_at"] else 0.0


def _attach_delivered_revenue(rows: list[dict[str, Any]]) -> None:
    """Gắn `delivered_revenue` cho MỘT TRANG hợp đồng — một truy vấn cho cả trang.

    Đọc dòng chi tiết của các đợt ĐÃ GIAO rồi quy đổi bằng chính `calc` mà hợp đồng dùng, thay vì
    viết lại công thức quy đổi bằng SQL: hai bản sao của một công thức sẽ lệch nhau lúc nào không hay.
    """
    ids = [r["id"] for r in rows if r["delivery_type"] == "multi"]
    kids: dict[int, list[float | None]] = {}
    if ids:
        ensure_schema()
        with session_scope() as db:
            got = db.execute(text("SELECT parent_id, lines FROM sales_contract "
                                  "WHERE parent_id = ANY(:ps) AND delivered_at IS NOT NULL"),
                             {"ps": ids}).mappings().all()
        for k in got:
            kids.setdefault(k["parent_id"], []).append(calc.total_revenue_vnd(k["lines"] or []))
    for r in rows:
        r["delivered_revenue"] = delivered_revenue(r, kids.get(r["id"], []))


def parents_with_progress(companies: list[str] | None = None, *,
                          customer_ids: list[int] | None = None,
                          status: str | None = None, q: str | None = None,
                          date_from: str | None = None, date_to: str | None = None,
                          channels: list[str] | None = None,
                          master_ids: list[int] | None = None,
                          only_unlinked: bool = False,
                          limit: int = 25, offset: int = 0) -> dict[str, Any]:
    """MỘT TRANG hợp đồng kèm tiến độ giao → `{"rows": [...], "total": <tổng khớp lọc>}`.

    Lọc · tính tiến độ · sắp xếp · cắt trang đều làm Ở SQL. Danh sách hợp đồng dài thêm mỗi ngày
    (mỗi lần giao là một bản ghi) nên kéo hết về Python rồi mới cắt là vừa chậm vừa nặng đường
    truyền — mà màn hình chỉ hiện được vài chục dòng.

    Tiến độ của một hợp đồng:
      - `delivered_qty` đã giao · `remaining_qty` = **sản lượng hợp đồng − đã giao** (còn phải
        giao); hợp đồng ĐÃ CHỐT HOÀN THÀNH thì bằng 0 — chốt xong là hết trách nhiệm giao
      - `pending_qty` phần đã LẬP ĐỢT nhưng chưa điền ngày giao (nằm trong `remaining_qty`)
      - `over_qty` phần giao VƯỢT hợp đồng (thực giao được lệch, xem `repo.MAX_OVER_RATIO`)
      - `delivered_revenue` TIỀN của hàng đã giao — lệch với `revenue` (tiền hợp đồng) là bình
        thường, xem `delivered_revenue()`

    `master_ids` = chỉ phụ lục của (các) HỢP ĐỒNG MẸ này — xem trọn một hồ sơ ở màn danh sách thay
    vì phải mở modal chi tiết của hồ sơ.
    `only_unlinked` = chỉ hợp đồng CHƯA gắn hợp đồng mẹ — dùng cho ô chọn phụ lục ở màn hợp đồng
    mẹ: bày cả hợp đồng đã thuộc hồ sơ khác chỉ để người dùng chọn rồi bị chặn.

    `channels` lọc theo HÌNH THỨC TIÊU THỤ (xuất khẩu / trong nước / nội bộ) — dùng `[""]` để tìm
    các hợp đồng CHƯA KHAI hình thức. Hình thức nằm ở LẦN GIAO chứ không ở hợp đồng, nên hợp đồng
    giao-nhiều-lần phải xét cả các đợt của nó; mỗi dòng trả về kèm `channels` (các hình thức có
    trong hợp đồng) để bảng hiện được cột này.
    """
    where = ["parent_id IS NULL"]
    params: dict[str, Any] = {"lim": max(1, limit), "off": max(0, offset)}
    if companies is not None:
        if not companies:
            return {"rows": [], "total": 0}
        where.append("company = ANY(:cs)")
        params["cs"] = list(companies)
    if customer_ids:
        where.append("customer_id = ANY(:cu)")
        params["cu"] = list(customer_ids)
    if master_ids:
        where.append("master_id = ANY(:mids)")
        params["mids"] = [int(i) for i in master_ids]
    if only_unlinked:
        where.append("master_id IS NULL")
    if date_from:
        where.append("(sign_date IS NULL OR sign_date >= CAST(:df AS date))")
        params["df"] = date_from
    if date_to:
        where.append("(sign_date IS NULL OR sign_date <= CAST(:dt AS date))")
        params["dt"] = date_to
    if q:
        # Tìm KHÔNG DẤU (giống ô chọn khách hàng): số hợp đồng phần lớn là chữ không dấu, nhưng
        # ghi chú thì có dấu — gõ "chuyen tu hop dong ton kho" vẫn phải ra.
        where.append(f"({vn_text.fold_sql('code')} LIKE :q OR {vn_text.fold_sql('note')} LIKE :q)")
        params.update(vn_text.FOLD_PARAMS)
        params["q"] = f"%{vn_text.fold(q)}%"
    # "Còn hàng chưa giao" bỏ qua hợp đồng đã chốt hoàn thành — chốt xong là hết trách nhiệm giao.
    keep = {"open": "completed_at IS NULL AND remaining_qty > 1e-9",
            # `remaining_qty` của hợp đồng ĐÃ CHỐT nay bằng 0 → phải loại chúng ra, không thì
            # "Đã giao đủ" gom cả hợp đồng chốt lúc chưa giao gì.
            "done": "completed_at IS NULL AND remaining_qty <= 1e-9",
            "completed": "completed_at IS NOT NULL"}.get(status or "", "TRUE")
    # Lọc hình thức PHẢI đặt ở đây (sau khi đã gom `channels` của hợp đồng + các đợt), không đặt
    # được trong CTE `parent`: hợp đồng giao-nhiều-lần bản thân nó không mang hình thức nào.
    if channels:
        want = [c for c in channels if c]
        blank = len(want) < len(channels)      # có chọn "chưa khai hình thức"
        cond = []
        if want:
            cond.append("channels && :ch")
            params["ch"] = want
        if blank:
            cond.append("cardinality(channels) = 0")
        keep += " AND (" + " OR ".join(cond) + ")"
    sql = f"""
        WITH parent AS (
            SELECT {', '.join(_COLS)}, {_QTY_SQL % 'lines'} AS pqty,
                   {_REV_SQL % 'lines'} AS prev
            FROM sales_contract WHERE {' AND '.join(where)}
        ), kid AS (
            SELECT k.parent_id, count(*) AS n,
                   COALESCE(sum({_QTY_SQL % 'k.lines'})
                            FILTER (WHERE k.delivered_at IS NOT NULL), 0) AS done,
                   COALESCE(sum({_QTY_SQL % 'k.lines'})
                            FILTER (WHERE k.delivered_at IS NULL), 0) AS pending,
                   COALESCE(sum({_REV_SQL % 'k.lines'})
                            FILTER (WHERE k.delivered_at IS NOT NULL), 0) AS done_rev,
                   -- Đếm riêng số đợt KHÔNG quy đổi được: `sum()` bỏ qua NULL nên không đếm thì
                   -- một đợt thiếu tỷ giá sẽ lặng lẽ biến mất khỏi tổng tiền đã giao.
                   count(*) FILTER (WHERE k.delivered_at IS NOT NULL
                                      AND {_REV_SQL % 'k.lines'} IS NULL) AS done_rev_missing,
                   COALESCE(array_agg(DISTINCT k.channel)
                            FILTER (WHERE k.channel IS NOT NULL), '{{}}') AS kid_channels
            FROM sales_contract k
            WHERE k.parent_id IN (SELECT id FROM parent) GROUP BY 1
        ), progress AS (
            SELECT p.*, COALESCE(kid.n, 0) AS children,
                   -- Tiền của hàng đã giao — cùng luật với `delivered_revenue()` ở Python.
                   CASE WHEN p.delivery_type = 'multi'
                        THEN CASE WHEN COALESCE(kid.done_rev_missing, 0) > 0 THEN NULL
                                  ELSE COALESCE(kid.done_rev, 0) END
                        WHEN p.delivered_at IS NOT NULL THEN p.prev ELSE 0 END AS delivered_rev,
                   -- Hình thức của hợp đồng = của chính nó (giao 1 lần) + của mọi đợt giao.
                   COALESCE(kid.kid_channels, '{{}}')
                     || CASE WHEN p.channel IS NULL THEN '{{}}'::text[]
                             ELSE ARRAY[p.channel] END AS channels,
                   CASE WHEN p.delivery_type = 'multi' THEN COALESCE(kid.done, 0)
                        WHEN p.delivered_at IS NOT NULL THEN p.pqty ELSE 0 END AS delivered_qty,
                   -- Chỉ đợt đã LẬP mà chưa có ngày giao mới là "đang chờ giao"; hợp đồng giao
                   -- 1 lần chưa giao thì toàn bộ nằm ở "còn phải giao", không tách rổ riêng.
                   CASE WHEN p.delivery_type = 'multi' THEN COALESCE(kid.pending, 0)
                        ELSE 0 END AS pending_qty
            FROM parent p LEFT JOIN kid ON kid.parent_id = p.id
        ), scored AS (
            SELECT g.*,
                   -- CHỐT HOÀN THÀNH LÀ HẾT NỢ HÀNG: phần chênh giữa hợp đồng và thực giao rời khỏi
                   -- "còn phải giao" kể từ ngày chốt — đúng luật khối 3 đang dùng (`_BLOCK3_SQL`
                   -- loại hợp đồng đã hoàn thành). Trước 27/08/2026 câu này trừ thuần
                   -- `pqty - delivered_qty` nên một hợp đồng chốt xong mà chưa giao gì vẫn hiện
                   -- "còn phải giao" nguyên sản lượng, và dòng Tổng cộng cộng luôn phần đó —
                   -- lệch hẳn với con số "đã ký HĐ chưa giao" trên báo cáo (đo prod: 4 hợp đồng,
                   -- 327,635 tấn đếm thừa).
                   CASE WHEN g.completed_at IS NOT NULL THEN 0
                        ELSE GREATEST(g.pqty - g.delivered_qty, 0) END AS remaining_qty,
                   GREATEST(g.delivered_qty - g.pqty, 0) AS over_qty
            FROM progress g
        )
    """
    # Hai câu dùng CHUNG phần lọc ở trên: một câu lấy đúng trang đang xem, một câu cộng TOÀN BỘ
    # hợp đồng khớp lọc (dòng "Tổng cộng"). Không cộng ở Python được — trang chỉ có 25 dòng, mà
    # cộng cả nghìn dòng ở máy người dùng thì phải tải hết dữ liệu về, đúng thứ phân trang tránh.
    page_sql = f"""{sql}
        SELECT * FROM scored WHERE {keep}
        ORDER BY sign_date DESC NULLS LAST, company DESC, id DESC
        LIMIT :lim OFFSET :off
    """
    sum_sql = f"""{sql}
        SELECT count(*) AS n,
               COALESCE(sum(pqty), 0) AS qty,
               COALESCE(sum(delivered_qty), 0) AS delivered_qty,
               COALESCE(sum(pending_qty), 0) AS pending_qty,
               COALESCE(sum(remaining_qty), 0) AS remaining_qty,
               COALESCE(sum(over_qty), 0) AS over_qty,
               COALESCE(sum(children), 0) AS children,
               COALESCE(sum(prev), 0) AS revenue,
               count(*) FILTER (WHERE prev IS NULL) AS revenue_missing,
               COALESCE(sum(delivered_rev), 0) AS delivered_revenue,
               count(*) FILTER (WHERE delivered_rev IS NULL) AS delivered_revenue_missing
        FROM scored WHERE {keep}
    """
    ensure_schema()
    with session_scope() as db:
        rows = db.execute(text(page_sql), params).mappings().all()
        agg = db.execute(text(sum_sql), params).mappings().first()
    out = []
    for r in rows:
        item = _row(r)
        for k in ("pqty", "prev", "delivered_rev"):
            item.pop(k, None)
        item["children"] = int(item["children"])
        item["channels"] = sorted(set(item.get("channels") or []))
        # `sum()` của Postgres trả về numeric → psycopg dựng thành Decimal, JSON hoá thành CHUỖI
        # ("30.0") làm web tính toán/so sánh sai. Ép float ngay tại đây.
        for k in ("delivered_qty", "pending_qty", "remaining_qty", "over_qty"):
            item[k] = float(item[k] or 0)
        out.append(item)
    _attach_delivered_revenue(out)
    return {"rows": out, "total": int(agg["n"]), "totals": _totals(agg)}


def _totals(agg) -> dict[str, Any]:
    """Dòng TỔNG CỘNG của toàn bộ hợp đồng khớp lọc (không phải của trang đang xem).

    Tiền: cộng phần quy đổi được và báo riêng `*_missing` = số hợp đồng KHÔNG quy đổi được (thiếu
    đơn giá / thiếu tỷ giá). Bỏ cả tổng thành "—" chỉ vì vài hợp đồng thiếu tỷ giá là làm mất một
    con số hữu ích; im lặng cộng thiếu lại càng tệ — nên vừa cộng vừa nói rõ còn thiếu bao nhiêu.
    """
    out = {k: float(agg[k] or 0) for k in
           ("qty", "delivered_qty", "pending_qty", "remaining_qty", "over_qty",
            "revenue", "delivered_revenue")}
    out["children"] = int(agg["children"] or 0)
    out["revenue_missing"] = int(agg["revenue_missing"] or 0)
    out["delivered_revenue_missing"] = int(agg["delivered_revenue_missing"] or 0)
    return out
