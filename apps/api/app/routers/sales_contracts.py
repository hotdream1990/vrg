"""Router HỢP ĐỒNG BÁN HÀNG 2 CẤP + số TIÊU THỤ / KHỐI 3 tính ra từ hợp đồng.

Dùng chung cho đơn vị thành viên và chuyên viên (`cap_or_member_scope`): đơn vị chỉ đụng được
hợp đồng của mình, chuyên viên có quyền `sales_contract` thấy mọi đơn vị.

KHÔNG áp cửa sổ nhập liệu N ngày ở đây — giống hợp đồng tồn kho cũ: ngày ký / ngày giao của một
hợp đồng hoàn toàn có thể nằm xa trong quá khứ, chặn theo cửa sổ sẽ khoá nhập hợp đồng cũ.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, UploadFile

from app.core.market_meta import (
    CONTRACT_CERTS,
    CONTRACT_TYPES,
    DELIVERY_TYPES,
    DRY_REQUIRED_GRADES,
    MASTER_CONTRACT_TYPES,
    PREMIUM_CURRENCIES,
    SALE_CHANNELS,
    SALE_CURRENCIES,
    UNIT_GRADES,
)
from app.core import security
from app.core.permissions import LEVEL_EDIT
from app.core.security import cap_or_member_scope
from app.schemas.sales_contract import CompletionIn, ContractIn, DeliveryTypeIn
from app.services.unit_report_query import roll_by_company
from app.services import (
    contract_files,
    customer_repo,
    master_contract_repo,
    member_unit_merge,
    member_unit_repo,
    sales_contract_consumption_excel,
    sales_contract_delivery_history,
    sales_contract_lifecycle,
    sales_contract_repo,
    sales_contract_report,
)

router = APIRouter(prefix="/api/sales-contracts", tags=["sales-contracts"])

Scope = Annotated[tuple[str, list[str] | None], Depends(cap_or_member_scope("sales_contract"))]
EditScope = Annotated[
    tuple[str, list[str] | None], Depends(cap_or_member_scope("sales_contract", LEVEL_EDIT))]


def _assert_company(companies: list[str] | None, company: str) -> None:
    if companies is not None and company not in companies:
        raise HTTPException(403, "Đơn vị không thuộc quyền quản lý của tài khoản.")


def _check_date(value: str | None, label: str) -> None:
    if value:
        try:
            date.fromisoformat(value)
        except ValueError as exc:
            raise HTTPException(400, f"{label} không hợp lệ (YYYY-MM-DD).") from exc


@router.get("/meta")
def meta(scope: Scope) -> dict:
    """Danh mục dùng cho form: đơn vị · chủng loại · hình thức · loại giao · loại tiền.

    KHÔNG kèm danh mục khách hàng: mỗi đơn vị có danh mục riêng nên tổng số khách tăng theo số
    đơn vị — web dùng ô tìm kiếm gọi `/api/customers?q=` thay vì tải cả danh mục về máy.
    """
    _, companies = scope
    units = member_unit_repo.list_units(include_inactive=False)
    active = {u["name"] for u in units}
    # Danh sách chọn khi TẠO MỚI: chỉ đơn vị đang hoạt động. Phạm vi của tài khoản đã gồm cả đơn
    # vị đã sáp nhập vào mình (để xem/giao nốt hợp đồng cũ) nhưng hợp đồng mới thì ký ở đơn vị
    # nhận — chốt với chủ dự án 27/08/2026.
    mine = ([u["name"] for u in units] if companies is None
            else [c for c in companies if c in active])
    return {
        "units": mine,
        # Nội tệ của từng đơn vị — form chỉ cho chọn VND · USD · nội tệ CỦA ĐƠN VỊ ĐÓ (chốt Q10:
        # trong nước bán VND, thêm USD khi xuất khẩu; nước ngoài mới có thêm LAK/KHR).
        "unit_currency": {u["name"]: (u.get("currency") or "VND") for u in units},
        "all_units": [u["name"] for u in units],
        # Đơn vị ĐÃ SÁP NHẬP: hợp đồng cũ của họ vẫn còn và vẫn chạy tiếp (thêm đợt giao, chốt
        # hoàn thành) nên phải LỌC được; chỉ không mở hợp đồng MỚI ở đó nữa. Danh sách này KHÔNG
        # trộn vào `units` — `units` là danh sách chọn khi tạo hợp đồng.
        "merged_units": [m["name"] for m in member_unit_merge.merged_units()
                         if companies is None or m["name"] in (companies or [])],
        # Đơn vị NHẬN khi tiêu thụ nội bộ — chỉ trong NHÓM công ty mẹ–con. Đơn vị không có tên ở đây
        # là đứng một mình → form ẩn luôn hình thức "Tiêu thụ nội bộ".
        "internal_targets": member_unit_repo.internal_targets(),
        "grades": list(UNIT_GRADES),
        "dry_required": sorted(DRY_REQUIRED_GRADES),
        "channels": SALE_CHANNELS,
        "delivery_types": DELIVERY_TYPES,
        "contract_types": CONTRACT_TYPES,
        "master_types": MASTER_CONTRACT_TYPES,
        "currencies": list(SALE_CURRENCIES),
        # Hàng có chứng chỉ + premium (26/08/2026) — dùng chung cho form hợp đồng bán và hợp đồng gốc.
        "certs": list(CONTRACT_CERTS),
        "premium_currencies": list(PREMIUM_CURRENCIES),
    }


def _lineage(companies: list[str] | None, company: str | None) -> list[str] | None:
    """Bộ lọc đơn vị có tính SÁP NHẬP: chọn đơn vị nhận là lấy luôn phần của đơn vị cũ.

    Chốt với chủ dự án 27/08/2026: hợp đồng đã gộp thì xem chung và tính số liệu tổng — lọc đúng
    một tên đơn vị thì phần hàng của đơn vị đã sáp nhập vào nó bị rơi ra ngoài.
    """
    if not company:
        return companies
    _assert_company(companies, company)
    return member_unit_merge.lineage(company)


@router.get("")
def list_contracts(scope: Scope, company: str | None = Query(None),
                   customer_id: list[int] | None = Query(None, description="Lọc 1 hoặc NHIỀU khách"),
                   status: str = Query("all", pattern="^(all|open|done|completed)$"),
                   date_from: str | None = Query(None, description="Ngày ký từ 'YYYY-MM-DD'"),
                   date_to: str | None = Query(None, description="Ngày ký đến 'YYYY-MM-DD'"),
                   q: str | None = Query(None, max_length=120),
                   channel: list[str] | None = Query(
                       None, description="Lọc hình thức tiêu thụ; '' = chưa khai hình thức"),
                   master_id: list[int] | None = Query(
                       None, description="Chỉ phụ lục của (các) hợp đồng mẹ này"),
                   unlinked: bool = Query(
                       False, description="Chỉ hợp đồng CHƯA gắn hợp đồng mẹ (ô chọn phụ lục)"),
                   page: int = Query(1, ge=1),
                   page_size: int = Query(25, ge=1, le=200)) -> dict:
    """MỘT TRANG hợp đồng kèm tiến độ giao → `{contracts, total, page, page_size}`.

    Phân trang Ở SERVER: danh sách dài thêm mỗi ngày (hiện đã hơn 3.000 hợp đồng), trả hết một
    lượt thì trình duyệt phải tải vài MB cho một màn hình chỉ hiện được vài chục dòng.
    """
    _, companies = scope
    _check_date(date_from, "Từ ngày")
    _check_date(date_to, "Đến ngày")
    companies = _lineage(companies, company)
    for c in channel or []:
        if c and c not in SALE_CHANNELS:
            raise HTTPException(400, f"Hình thức tiêu thụ “{c}” không hợp lệ.")
    res = sales_contract_report.parents_with_progress(
        companies, customer_ids=customer_id, status=None if status == "all" else status,
        q=q, date_from=date_from, date_to=date_to, channels=channel,
        master_ids=master_id, only_unlinked=unlinked,
        limit=page_size, offset=(page - 1) * page_size)
    rows = res["rows"]
    # Chỉ tra tên của đúng những khách xuất hiện TRONG TRANG — danh mục cả Tập đoàn rất dài.
    names = customer_repo.names_by_id(companies, sorted({
        r["customer_id"] for r in rows if r.get("customer_id")}))
    # Số HỢP ĐỒNG MẸ của phụ lục — tra riêng cho đúng các dòng trong trang (cùng cách làm với
    # tên khách hàng), thay vì join thêm một bảng vào câu truy vấn tiến độ vốn đã nhiều CTE.
    masters = master_contract_repo.codes_by_id(companies, sorted({
        r["master_id"] for r in rows if r.get("master_id")}))
    for r in rows:
        r["customer_name"] = names.get(r.get("customer_id") or 0)
        r["master_code"] = masters.get(r.get("master_id") or 0)
    # `totals` cộng TOÀN BỘ hợp đồng khớp lọc, không phải trang đang xem — bảng có phân trang nên
    # cộng ở web sẽ ra tổng của 25 dòng và bị đọc nhầm là tổng của cả bộ lọc.
    return {"contracts": rows, "total": res["total"], "totals": res["totals"],
            "page": page, "page_size": page_size}


def _consumption(scope_companies: list[str] | None, date_from: str, date_to: str,
                 company: str | None, customer_ids: list[int] | None,
                 grades: list[str] | None = None) -> dict:
    """Phần dùng chung của endpoint JSON và endpoint xuất Excel (tránh lệch số giữa 2 nơi)."""
    _check_date(date_from, "Từ ngày")
    _check_date(date_to, "Đến ngày")
    companies = _lineage(scope_companies, company)
    by_company = roll_by_company(
        sales_contract_report.consumption(date_from, date_to, companies, customer_ids, grades))
    # Bảng "tách theo khách hàng" chỉ cần tên của các khách CÓ trong kỳ ("0" = chưa gán khách).
    shown = sorted({int(k) for c in by_company.values() for k in c["by_customer"] if k != "0"})
    return {
        "date_from": date_from, "date_to": date_to,
        "by_company": by_company,
        # Lọc chủng loại áp cho CẢ cột "đã ký HĐ chưa giao" — không thì bảng có cột đã lọc
        # đứng cạnh cột chưa lọc, người đọc tưởng số vênh nhau.
        "undelivered": roll_by_company(
            sales_contract_report.undelivered_on(date_to, companies, grades)),
        "customers": {str(i): n for i, n in customer_repo.names_by_id(companies, shown).items()},
    }


@router.get("/consumption")
def consumption(scope: Scope, date_from: str = Query(...), date_to: str = Query(...),
                company: str | None = Query(None),
                customer_id: list[int] | None = Query(None),
                grade: list[str] | None = Query(None, description="Lọc 1 hoặc NHIỀU chủng loại")) -> dict:
    """TIÊU THỤ trong kỳ — tổng hợp từ các lần giao, KHÔNG còn ô nhập tay."""
    _, companies = scope
    return _consumption(companies, date_from, date_to, company, customer_id, grade)


@router.get("/consumption/deliveries")
def consumption_deliveries(scope: Scope, date_from: str = Query(...), date_to: str = Query(...),
                           company: str | None = Query(None),
                           customer_id: list[int] | None = Query(None),
                           grade: list[str] | None = Query(None),
                           page: int = Query(1, ge=1),
                           page_size: int = Query(50, ge=1,
                                                  le=sales_contract_delivery_history.MAX_PAGE_SIZE),
                           ) -> dict:
    """LỊCH SỬ từng lần giao của kỳ — để soát chi tiết đằng sau con số tổng hợp.

    Cùng bộ lọc với `/consumption` nên tổng của mọi trang khớp đúng bảng tổng hợp.
    """
    _, companies = scope
    _check_date(date_from, "Từ ngày")
    _check_date(date_to, "Đến ngày")
    companies = _lineage(companies, company)
    return sales_contract_delivery_history.history(
        date_from, date_to, companies, customer_id, grade, page=page, page_size=page_size)


@router.get("/consumption.xlsx")
def consumption_xlsx(scope: Scope, date_from: str = Query(...), date_to: str = Query(...),
                     company: str | None = Query(None),
                     customer_id: list[int] | None = Query(None),
                     grade: list[str] | None = Query(None)):
    """Xuất Excel Báo cáo tiêu thụ — sheet tổng hợp + sheet CHI TIẾT từng dòng bán.

    Dùng CHUNG số liệu với bảng trên web (`_consumption`) nên file và màn hình không thể lệch.
    """
    _, companies = scope
    companies = _lineage(companies, company)
    rep = _consumption(companies, date_from, date_to, None, customer_id, grade)
    data = sales_contract_consumption_excel.build(date_from, date_to, rep, companies,
                                                 customer_id, grade)
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition":
                 f'attachment; filename="bao-cao-tieu-thu-{date_from}-den-{date_to}.xlsx"'})


@router.get("/undelivered")
def undelivered(scope: Scope, as_of: str = Query(..., description="Tính tại ngày 'YYYY-MM-DD'"),
                company: str | None = Query(None)) -> dict:
    """ĐÃ KÝ HĐ CHƯA GIAO (khối 3) tại ngày — SL cam kết trừ tổng đã giao."""
    _, companies = scope
    _check_date(as_of, "Ngày")
    companies = _lineage(companies, company)
    return {"as_of": as_of,
            "by_company": roll_by_company(sales_contract_report.undelivered_on(as_of, companies))}


@router.get("/{contract_id}")
def get_contract(contract_id: int, scope: Scope) -> dict:
    """Chi tiết 1 hợp đồng + toàn bộ ĐỢT GIAO (mỗi đợt = 1 lần giao + 1 lần thanh toán)."""
    _, companies = scope
    c = sales_contract_repo.get(contract_id)
    if not c or (companies is not None and c["company"] not in companies):
        raise HTTPException(404, "Không tìm thấy hợp đồng trong phạm vi tài khoản.")
    kids = sales_contract_repo.children(contract_id) if c["parent_id"] is None else []
    if c["delivery_type"] == "multi":
        done = sum(k["qty"] for k in kids if k["delivered_at"])
        # "Đang chờ giao" = đợt đã lập, chưa điền ngày giao. Nó NẰM TRONG phần còn phải giao,
        # không phải một rổ tách riêng (khác cách tính trước 05/08/2026).
        pending = sum(k["qty"] for k in kids if not k["delivered_at"])
    else:
        done = c["qty"] if c["delivered_at"] else 0.0
        pending = 0.0
    # Tên khách trả kèm ở đây (không để web tự tra trong danh mục tải sẵn nữa — danh mục đã bỏ
    # khỏi /meta): thiếu nó là ô "Khách hàng" trên màn chi tiết luôn hiện "—".
    names = customer_repo.names_by_id([c["company"]],
                                      [c["customer_id"]] if c.get("customer_id") else [])
    # Hợp đồng mẹ (nếu là phụ lục) — màn chi tiết cần số HĐ mẹ, loại và CÔNG THỨC GIÁ: giá của
    # phụ lục vốn tính theo công thức ghi ở hợp đồng mẹ.
    master = master_contract_repo.get(c["master_id"]) if c.get("master_id") else None
    return {"contract": c, "children": kids, "delivered_qty": done, "pending_qty": pending,
            "master": master,
            # Tiền của HÀNG ĐÃ GIAO — khác tiền ghi trên hợp đồng vì đơn giá/sản lượng chốt ở đợt giao.
            "delivered_revenue": sales_contract_report.delivered_revenue(
                c, [k["revenue"] for k in kids if k["delivered_at"]]),
            # Chốt hoàn thành = hết nợ hàng (cùng luật với danh sách và với khối 3 của báo cáo).
            "remaining_qty": 0.0 if c.get("completed_at") else max(0.0, c["qty"] - done),
            "over_qty": max(0.0, done - c["qty"]),
            "max_qty": c["qty"] * sales_contract_repo.MAX_OVER_RATIO,
            "customer_name": names.get(c.get("customer_id") or 0)}


def _assert_delivery_window(username: str, contract_id: int | None, new_delivered_at: str | None,
                            company: str | None = None) -> None:
    """Cửa sổ sửa — chỉ áp cho LẦN GIAO, mốc là NGÀY GIAO (chốt 02/08/2026).

    Lần giao là bản ghi tiêu thụ, đúng thứ cửa sổ sửa sinh ra để bảo vệ: giao xong quá N ngày thì
    kỳ báo cáo đã chốt, sửa lùi là làm lệch số đã gửi đi.

    KHÔNG áp cho hợp đồng: hợp đồng ký từ lâu vẫn phải sửa và thêm đợt giao suốt
    vòng đời — khoá theo ngày ký là chặn đúng nghiệp vụ chính. Các mốc tương lai (thời hạn hợp đồng,
    ngày mở đợt, ngày thanh toán) cũng không đụng tới, vì `assert_editable` chặn cả ngày tương lai.

    Kiểm CẢ HAI đầu: ngày giao ĐANG lưu (không cho sửa/xoá lần giao đã khoá) và ngày giao MỚI gửi
    lên (không cho khai lùi ra ngoài cửa sổ).
    """
    old = sales_contract_repo.get(contract_id) if contract_id else None
    days = [old.get("delivered_at") if old else None, new_delivered_at]
    for as_of in days:
        if as_of:
            security.assert_edit_window(username, as_of)
    # CHỐT SỐ LIỆU: lần giao là bản ghi TIÊU THỤ — đơn vị đã chốt đến ngày X thì mọi lần giao
    # ≤ X phải đứng yên, nếu không con số tiêu thụ vừa xác nhận vẫn đổi được sau lưng (yêu cầu
    # 25/08/2026: "hợp đồng có thể cập nhật nhưng tiêu thụ sẽ bị chốt lại"). Hợp đồng và các đợt
    # giao SAU ngày chốt vẫn thêm/sửa bình thường.
    security.assert_not_data_locked(username, company or (old or {}).get("company"), *days)


@router.put("")
def save_contract(body: ContractIn, scope: EditScope) -> dict:
    """Thêm mới / cập nhật hợp đồng hoặc ĐỢT GIAO (đợt có ngày giao mới tính là đã giao)."""
    username, companies = scope
    _assert_company(companies, body.company)
    _assert_delivery_window(username, body.id, body.delivered_at, body.company)
    try:
        return {"contract": sales_contract_repo.save(body.model_dump(), body.company, username)}
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.put("/{contract_id}/completion")
def set_completion(contract_id: int, body: CompletionIn, scope: EditScope) -> dict:
    """HOÀN THÀNH hợp đồng (chốt ngày kết thúc) — `completed_at = null` là MỞ LẠI.

    Chốt xong, phần chênh giữa sản lượng hợp đồng và sản lượng thực giao rời khỏi
    "đã ký HĐ chưa giao" kể từ ngày hoàn thành.
    """
    username, companies = scope
    try:
        return {"contract": sales_contract_lifecycle.set_completion(
            contract_id, body.completed_at, companies, username,
            delivery={"delivered_at": body.delivered_at, "channel": body.channel,
                      "to_company": body.to_company, "no_delivery": body.no_delivery})}
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.put("/{contract_id}/delivery-type")
def set_delivery_type(contract_id: int, body: DeliveryTypeIn, scope: EditScope) -> dict:
    """Chuyển giao-1-lần ↔ giao-nhiều-lần tại chỗ (không phải xoá hợp đồng nhập lại).

    Hợp đồng giao-1-lần ĐÃ GIAO thì lần giao đó được dời xuống thành đợt giao đầu tiên, giữ
    nguyên ngày giao / hoá đơn / thanh toán / dòng chi tiết.
    """
    username, companies = scope
    # Chuyển loại giao của một hợp đồng ĐÃ GIAO là dời chỗ ghi nhận tiêu thụ → chặn nếu đã chốt.
    # CHỈ hàng rào chốt, KHÔNG thêm cửa sổ sửa: endpoint này xưa nay không bị cửa sổ chặn, siết
    # thêm ở đây là đổi hành vi ngoài phạm vi việc đang làm.
    _old = sales_contract_repo.get(contract_id) or {}
    security.assert_not_data_locked(username, _old.get("company"), _old.get("delivered_at"))
    try:
        return {"contract": sales_contract_lifecycle.set_delivery_type(
            contract_id, body.delivery_type, companies, username)}
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.delete("/{contract_id}")
def delete_contract(contract_id: int, scope: EditScope) -> dict:
    """Xoá 1 hợp đồng / đợt giao (hợp đồng còn đợt giao thì phải xoá các đợt trước)."""
    username, companies = scope
    _assert_delivery_window(username, contract_id, None)
    try:
        ok = sales_contract_repo.delete(contract_id, companies)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if not ok:
        raise HTTPException(404, "Không tìm thấy hợp đồng trong phạm vi tài khoản.")
    return {"ok": True}


@router.post("/file")
def upload_file(file: UploadFile, scope: EditScope) -> dict:
    """Upload hợp đồng scan / chứng từ thanh toán — trả tên file lưu để gắn vào bản ghi."""
    return contract_files.save(file)


@router.get("/file/{name}")
def get_file(name: str, scope: Scope, filename: str | None = Query(None)):
    """Tải file đã đính kèm (tên lưu uuid). Ép đúng MIME + chặn trình duyệt đoán kiểu.

    File nằm chung một thư mục phẳng nên phải kiểm file thuộc hợp đồng của đơn vị nào: thiếu bước
    này, tài khoản đơn vị A biết tên file là tải được bản scan hợp đồng của đơn vị B.
    """
    _, companies = scope
    # Hợp đồng mẹ dùng CHUNG thư mục lưu file với hợp đồng bán hàng → phải hỏi cả hai bảng,
    # thiếu một bảng là bản scan của bảng đó luôn trả 404.
    owners = (sales_contract_repo.companies_of_file(name)
              | master_contract_repo.companies_of_file(name))
    # Endpoint này CHỈ phục vụ file của hợp đồng bán hàng. File của module khác dùng chung thư mục
    # lưu trữ nên không chặn ở đây là mở đường đọc chéo module (chuyên viên chỉ có quyền hợp đồng
    # vẫn tải được file của biểu Thu mua/Tồn kho).
    if not owners:
        raise HTTPException(404, "Không tìm thấy file hợp đồng.")
    if companies is not None and not owners & set(companies):
        raise HTTPException(404, "Không tìm thấy file trong phạm vi tài khoản.")
    return contract_files.serve(name, filename)
