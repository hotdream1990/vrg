"""Gói "Giá sàn & tư vấn điều chỉnh" — lý do tồn tại chính của Trợ lý.

Giá sàn = giá bán TỐI THIỂU cho hợp đồng chuyến do Tập đoàn ban hành. Mọi con số ở đây là
GỢI Ý tham khảo; quyết định cuối thuộc Ban lãnh đạo — system prompt bắt buộc nhắc điều đó.
"""
from __future__ import annotations

from datetime import date
from typing import Any

from app.core.market_meta import VRG_FLOOR_GRADES
from app.services import floor_repo, floor_suggest, private_price_benchmark
from app.services.assistant_tools._common import cols, dm, dmy, err, line, pct, table, today

_ACTION = {"raise": "NÂNG", "lower": "HẠ", "hold": "GIỮ"}
_CONFIDENCE = {"high": "cao", "medium": "trung bình", "low": "thấp"}
_DEFAULT_GRADE = "SVR 10 / CSR 10"
#: Đơn vị đề xuất theo chủng loại — ghi trên TỪNG dòng: đo thực tế LLM từng đọc FOB 2.566 USD/tấn
#: thành "2.566.000 đồng/tấn" và LATEX "+184 đồng/độ TSC" khi bảng không nói đơn vị từng dòng.
_UNIT_TEXT = {"USD/T": "USD/tấn (FOB)", "VNĐ/T": "VNĐ/tấn (nội địa)"}
#: Số của một chỉ số cũ hơn chừng này ngày so với ngày hỏi thì ghi chú rõ (sàn nghỉ lễ, chưa quét).
_STALE_DAYS = 3


def _norm(grade: str) -> set[str]:
    """Các cách gọi của 1 chủng loại: 'SVR 10 / CSR 10' → {'svr10', 'csr10'} (bỏ khoảng trắng, hoa thường)."""
    return {"".join(part.lower().split()) for part in str(grade).split("/") if part.strip()}


def _grade_filter(items: list[dict], grade: str | None) -> list[dict] | None:
    """Dòng của chủng loại người hỏi; None nếu không khớp chủng loại nào. Không hỏi riêng → mọi dòng."""
    if not grade:
        return items
    want = "".join(str(grade).lower().split())
    hit = [it for it in items if want in _norm(it["grade"]) or want == "".join(it["grade"].lower().split())]
    return hit or None


#: Thứ tự ảnh hưởng tới lần điều chỉnh (tương quan biến động %, 83 lần ban hành — cùng bảng
#: `_FACTOR_RANKING` trong prompt). Trả drivers theo thứ tự này: hỏi "yếu tố nào mạnh nhất" thì LLM
#: đọc từ trên xuống — để thứ tự cột của mô hình (mủ nước đầu tiên) là nó xếp mủ nước lên đầu.
_DRIVER_RANK = ("SHFE RU", "MRB SMR20", "SGX TSR20", "OSE RSS3", "Giá mủ nước")


def _vn_int(n: float) -> str:
    """58786 → '58.786' (chấm ngăn nghìn kiểu Việt Nam)."""
    return f"{n:,.0f}".replace(",", ".")


_UNIT_SHORT = {"USD/T": "USD/tấn FOB", "VNĐ/T": "đồng/tấn (nội địa)"}


def _item_line(it: dict) -> str:
    """Câu tóm tắt 1 dòng đề xuất, SỐ ĐÃ ĐỊNH DẠNG sẵn để LLM chép nguyên văn.

    Đo thực tế: để LLM tự định dạng số nguyên 2340 thành kiểu Việt Nam, có lượt nó viết
    "23.400 → 23.550 USD/tấn" (nhân 10). Chép chuỗi có sẵn thì không còn chỗ sai.
    """
    unit = _UNIT_SHORT.get(it.get("unit"), it.get("unit") or "")
    d, dp = it.get("delta"), it.get("delta_pct")
    chg = ("" if d is None else " (không đổi)" if d == 0
           else f" ({'+' if d > 0 else '−'}{_vn_int(abs(d))}"
                + ("" if dp is None else f", {dp:+.1f}%".replace(".", ",")) + ")")
    conf = _CONFIDENCE.get(it.get("confidence"), it.get("confidence"))
    return (f"{it['grade']}: {_vn_int(it['prev'])} → {_vn_int(it['suggested'])} {unit}{chg} · "
            f"{_ACTION.get(it.get('action'), it.get('action'))}" + (f" · độ tin cậy {conf}" if conf else ""))


def _driver_rows(drivers: list[dict], as_of: str) -> list[dict]:
    """Biến động từng chỉ số kèm NGÀY CỦA SỐ — sàn nghỉ nhiều phiên thì số không phải của ngày hỏi."""
    rank = {name: i for i, name in enumerate(_DRIVER_RANK)}
    out = []
    for d in sorted(drivers, key=lambda x: rank.get(x["index"], len(rank))):
        row = {"chi_so": d["index"], "hang_anh_huong": rank.get(d["index"], len(rank)) + 1,
               "thay_doi_pct": d["change_pct"],
               "ngay_so_moi": dmy(d["cur_date"]) if d.get("cur_date") else None,
               "ngay_so_lan_truoc": dmy(d["prev_date"]) if d.get("prev_date") else None}
        if d.get("cur_date"):
            late = (date.fromisoformat(as_of) - date.fromisoformat(d["cur_date"])).days
            if late > _STALE_DAYS:
                row["ghi_chu"] = f"số mới nhất cách ngày hỏi {late} ngày (phiên gần nhất có số)"
        out.append(row)
    return out


def _schedule_items(lan: int) -> dict[str, dict]:
    full = floor_repo.get_schedule(int(lan)) or {}
    return {it["grade"]: it for it in full.get("items", [])}


def _floor_prices(args: dict) -> dict:
    """Giá sàn của một lần ban hành (mặc định lần mới nhất) + chênh lệch so lần liền trước."""
    as_of = str(args.get("as_of") or "").strip()
    sched = floor_repo.list_schedules()
    if not sched:
        return err("Chưa có biểu giá sàn nào.")
    cur = next((s for s in sched if str(s["as_of"]) == as_of), None) if as_of else sched[0]
    if cur is None:
        return err(f"Không có lần ban hành nào áp dụng từ {dmy(as_of)}. "
                   f"Lần gần nhất: {dmy(sched[0]['as_of'])}.")
    i = sched.index(cur)
    prev = sched[i + 1] if i + 1 < len(sched) else None
    items = _schedule_items(cur["lan"])
    prev_items = _schedule_items(prev["lan"]) if prev else {}
    out = []
    for g, it in items.items():
        p = prev_items.get(g) or {}
        out.append({"grade": g, "fob_usd": it.get("fob_usd"), "domestic_vnd": it.get("domestic_vnd"),
                    "fob_lan_truoc": p.get("fob_usd"),
                    "thay_doi_pct": pct(it.get("fob_usd"), p.get("fob_usd"))})
    art = table(f"Giá sàn Tập đoàn · {cur['title']} (áp dụng {dmy(cur['as_of'])})",
                cols(("grade", "Chủng loại"), ("fob_usd", "FOB (USD/tấn)"),
                     ("domestic_vnd", "Nội địa (VNĐ/tấn)"), ("fob_lan_truoc", "FOB lần trước"),
                     ("thay_doi_pct", "Thay đổi %")), out)
    return {"summary": {"title": cur["title"], "as_of": str(cur["as_of"]),
                        "dispatch_no": cur.get("dispatch_no"),
                        "lan_truoc": dmy(prev["as_of"]) if prev else None,
                        "don_vi": "FOB = USD/tấn · Nội địa = VNĐ/tấn", "items": out},
            "artifact": art, "source": f"vrg_floor_price · {cur['title']} · {dmy(cur['as_of'])}"}


def _floor_history(args: dict) -> dict:
    """Lịch sử các lần ban hành: mức FOB của 1 chủng loại qua từng lần + biên độ điều chỉnh."""
    grade = str(args.get("grade") or _DEFAULT_GRADE).strip()
    limit = int(args.get("limit") or 12)
    sched = floor_repo.list_schedules()
    if not sched:
        return err("Chưa có biểu giá sàn nào.")
    picked = list(reversed(sched[:limit]))            # cũ → mới cho biểu đồ
    rows, values, labels = [], [], []
    prev_fob = None
    for s in picked:
        it = _schedule_items(s["lan"]).get(grade) or {}
        fob = it.get("fob_usd")
        rows.append({"ngay": dmy(s["as_of"]), "lan": s["title"], "fob_usd": fob,
                     "domestic_vnd": it.get("domestic_vnd"),
                     "thay_doi_pct": pct(fob, prev_fob)})
        if fob is not None:
            labels.append(dm(s["as_of"]))
            values.append(float(fob))
        prev_fob = fob if fob is not None else prev_fob
    if not values:
        return err(f"Chủng loại '{grade}' chưa có giá FOB trong các lần ban hành gần đây.")
    moves = [r["thay_doi_pct"] for r in rows if r["thay_doi_pct"] is not None]
    art = line(f"Giá sàn FOB {grade} qua {len(values)} lần ban hành", labels,
               [{"name": grade, "values": values}], "USD/tấn")
    return {"summary": {"grade": grade, "don_vi": "USD/tấn", "n_lan": len(rows),
                        "moi_nhat": values[-1], "cu_nhat": values[0],
                        "thay_doi_pct_toan_ky": pct(values[-1], values[0]),
                        "bien_do_tb_moi_lan_pct": round(sum(abs(m) for m in moves) / len(moves), 2)
                        if moves else None, "lich_su": rows},
            "artifact": art, "source": f"vrg_floor_price · {len(rows)} lần ban hành"}


def _suggest_floor(args: dict) -> dict:
    """Tư vấn NÂNG/GIỮ/HẠ từng chủng loại, kèm chỉ số dẫn hướng và bối cảnh tồn kho."""
    as_of = str(args.get("as_of") or today())
    try:
        s = floor_suggest.suggest(as_of)
    except Exception as exc:  # noqa: BLE001 - engine thiếu dữ liệu thì báo, đừng làm hỏng lượt hỏi
        return err(f"Không tính được gợi ý: {exc}")
    if s.get("error"):
        return err(s["error"])
    picked = _grade_filter(s.get("items", []), args.get("grade"))
    if picked is None:
        return err(f"Không có chủng loại giá sàn '{args.get('grade')}'. Chủng loại hợp lệ: "
                   + ", ".join(VRG_FLOOR_GRADES) + ".")
    # Tên trường tách bạch "giá hiện hành" với "mức mô hình": đo thực tế ở mức Có điều chỉnh, với tên
    # cũ hien_tai/de_xuat LLM ghi giá hiện hành 2.340 làm "Mức mô hình" (đúng ra 2.355).
    out = [{"grade": it["grade"], "don_vi": _UNIT_TEXT.get(it.get("unit"), it.get("unit")),
            "gia_san_hien_hanh": it.get("prev"), "muc_mo_hinh_de_xuat": it.get("suggested"),
            "hanh_dong": _ACTION.get(it.get("action"), it.get("action")),
            "chenh_so_voi_hien_hanh": it.get("delta"), "chenh_so_voi_hien_hanh_pct": it.get("delta_pct"),
            "nguong_giu_nguyen": it.get("band"),
            "do_tin_cay": _CONFIDENCE.get(it.get("confidence"), it.get("confidence")),
            "canh_bao": [_CAUTION[c] for c in it.get("cautions", [])],
            "tom_tat": _item_line(it) if it.get("prev") is not None else None}
           for it in picked if it.get("suggested") is not None]
    if not out:
        return err(f"Chưa đủ dữ liệu để gợi ý giá sàn tại ngày {dmy(as_of)}.")
    art = table(f"Gợi ý điều chỉnh giá sàn ({dmy(as_of)})",
                cols(("grade", "Chủng loại"), ("don_vi", "Đơn vị"), ("gia_san_hien_hanh", "Giá hiện tại"),
                     ("muc_mo_hinh_de_xuat", "Đề xuất"), ("hanh_dong", "Hành động"),
                     ("chenh_so_voi_hien_hanh", "Δ"), ("chenh_so_voi_hien_hanh_pct", "Δ%"),
                     ("do_tin_cay", "Độ tin cậy")), out)
    return {"summary": {
        "as_of": as_of, "lan_truoc": dmy(s.get("prev_as_of")),
        "bien_dong_ro_chi_so_pct": s.get("basket_change_pct"),
        "drivers": _driver_rows(s.get("drivers", []), as_of),
        "ton_kho": s.get("inventory"), "tham_chieu_ton_kho": _lean_text(s.get("inventory_lean")),
        "items": out,
        "note": "Mức đề xuất = giá sàn lần ban hành trước + mức thay đổi của mô hình đa biến (giá mủ nước "
                "+ 4 futures: MRB SMR20 · SGX TSR20 · SHFE RU · OSE RSS3) từ ngày đó tới nay, làm tròn "
                "theo bước ban hành (5 USD/tấn; 50.000 đồng/tấn với Skim Block). |Δ| ≤ nguong_giu_nguyen "
                "(= sai số TB backtest) ⇒ GIỮ. Nêu mức giá của chủng loại nào thì CHÉP NGUYÊN câu tom_tat của dòng đó (số đã định dạng sẵn). chenh_so_voi_hien_hanh = muc_mo_hinh_de_xuat − gia_san_hien_hanh. Mỗi dòng có đơn vị riêng (don_vi) — FOB là USD/tấn, KHÔNG "
                "phải đồng. Tồn kho tổng/tự do là THAM CHIẾU nghiêng, không đổi số mô hình — ngược hướng "
                "đề xuất thì đã hạ độ tin cậy và ghi canh_bao. Đây là GỢI Ý tham khảo, quyết định cuối "
                "thuộc Ban lãnh đạo."},
        "artifact": art, "source": f"engine gợi ý giá sàn · {dmy(as_of)}"}


def _scenarios(args: dict) -> dict:
    """Kịch bản Giảm/Cơ sở/Tăng: áp cú sốc ± lên rổ chỉ số rồi dự báo lại từng chủng loại."""
    as_of = str(args.get("as_of") or today())
    # Biên độ luôn DƯƠNG: hỏi "thị trường giảm 5%" LLM truyền −5 ⇒ Bear/Bull đảo nhau (đo thực tế: trả
    # 2.465 USD cho kịch bản giảm trong khi giá hiện hành 2.340). Hướng giảm đọc ở cột bear_giam.
    shock = abs(float(args.get("shock_pct") or 0)) or None
    try:
        s = floor_suggest.scenarios(as_of, shock_pct=shock)
    except Exception as exc:  # noqa: BLE001
        return err(f"Không dựng được kịch bản: {exc}")
    if s.get("error"):
        return err(s["error"])
    items = [it for it in s.get("items", []) if it.get("base") is not None]
    if not items:
        return err(f"Chưa đủ dữ liệu để dựng kịch bản tại ngày {dmy(as_of)}.")
    out = [{"grade": it["grade"], "don_vi": it.get("unit"), "hien_tai": it.get("prev"),
            "bear_giam": it.get("bear"), "base_co_so": it.get("base"), "bull_tang": it.get("bull")}
           for it in items]
    art = table(f"Kịch bản giá sàn ({dmy(as_of)}) · sốc rổ chỉ số ±{s.get('shock_pct')}%",
                cols(("grade", "Chủng loại"), ("hien_tai", "Hiện tại"), ("bear_giam", "Bear (giảm)"),
                     ("base_co_so", "Base (cơ sở)"), ("bull_tang", "Bull (tăng)"),
                     ("don_vi", "Đơn vị")), out)
    return {"summary": {"as_of": as_of, "shock_pct": s.get("shock_pct"), "items": out,
                        "note": "Cú sốc mặc định = 1 độ lệch chuẩn biến động rổ chỉ số giữa 2 lần ban hành."},
            "artifact": art, "source": f"engine kịch bản giá sàn · {dmy(as_of)}"}


# ── Tín hiệu bên lề cho việc ĐIỀU CHỈNH khỏi mức engine ──
# Trọng số = mức ảnh hưởng đo trên 80 lần ban hành (docs/project/tro-ly-ai-kha-nang.md):
# "mạnh" = biến của mô hình (4 futures + giá mủ nước) — đã nằm trong mức đề xuất; "bổ sung" = mang
# thông tin mô hình KHÔNG có (tương quan riêng phần cao) — đây mới là thứ đáng dùng để lệch khỏi mức nền.
_W_STRONG, _W_EXTRA = "mạnh", "bổ sung"

#: Hướng tồn kho (floor_recommend.inventory_lean) → hướng tác động lên giá sàn. Cùng luật ±3% với màn
#: Gợi ý giá sàn — AI không tự áp ngưỡng riêng.
_SVR3L_DOM = "chỉ giá nội địa SVR 3L"
_LEAN_EFFECT = {"up": "hỗ trợ HẠ", "down": "hỗ trợ NÂNG", "flat": "trung tính (đi ngang)",
                "mixed": "trung tính (tổng và tự do trái chiều)"}
_CAUTION = {"shfe_opposite": "SHFE RU đi ngược hướng đề xuất",
            "inventory_opposite": "tồn kho đi ngược hướng đề xuất"}


def _lean_text(lean: dict | None) -> str:
    """Câu tham chiếu tồn kho cho LLM đọc nguyên văn — hướng đã quy sẵn, không để LLM tự nhân dấu."""
    if not lean:
        return "chưa đủ dữ liệu tồn kho để so với lần ban hành trước"
    pct_txt = lambda v: "—" if v is None else f"{v:+.1f}%".replace(".", ",")  # noqa: E731
    return (f"tồn kho tổng {pct_txt(lean['total_pct'])}, tự do {pct_txt(lean['free_pct'])} so với "
            f"{dmy(lean['base_day'])} (ngưỡng ±{lean['threshold_pct']:g}%) → {_LEAN_EFFECT[lean['direction']]}")


#: Dưới ngưỡng này coi như đi ngang — nhiễu, không đủ để lệch khỏi mức mô hình.
_FLAT_PCT = 0.5


def _signal(name: str, change_pct: float | None, weight: str, sign: int, note: str = "") -> dict:
    """1 dòng tín hiệu, ĐÃ QUY RA HƯỚNG cuối cùng.

    `sign` = +1 nếu tín hiệu thuận chiều giá sàn (tăng ⇒ hỗ trợ nâng), −1 nếu nghịch chiều.

    Vì sao phải tính sẵn: đo thực tế cho thấy để LLM tự nhân dấu là nó đọc nhầm — tồn kho GIẢM
    13,7% từng bị diễn giải thành "tồn kho cao nên nghiêng về giữ". Trả thẳng kết luận hướng thì
    không còn chỗ cho suy luận sai dấu.
    """
    if change_pct is None:
        huong = "chưa đủ dữ liệu"
    elif abs(change_pct) < _FLAT_PCT:
        huong = "trung tính (đi ngang)"
    else:
        up = (change_pct > 0) == (sign > 0)
        huong = "hỗ trợ NÂNG" if up else "hỗ trợ HẠ"
    chieu = "thuận chiều giá sàn" if sign > 0 else "nghịch chiều giá sàn"
    return {"tin_hieu": name, "thay_doi_pct": change_pct, "trong_so": weight,
            "huong_tac_dong": huong, "quan_he": chieu, "ghi_chu": note}


def _floor_context(args: dict) -> dict:
    """Gom TÍN HIỆU BÊN LỀ quanh một lần điều chỉnh: biến của mô hình, giá mủ chén, tồn kho.

    Mục đích: cho phép điều chỉnh khỏi mức đề xuất của engine một cách CÓ CĂN CỨ — mỗi tín hiệu
    kèm hướng tác động và trọng số đã đo, thay vì để người/AI ước lượng cảm tính.

    Không còn giá mủ chén (gỡ 24/09/2026): đo lại trên 83 lần ban hành, biến động giá mủ chén không
    mang thêm thông tin gì ngoài rổ futures (tương quan riêng phần −0,01, n=20; thô −0,31) — dùng nó
    để lệch khỏi mô hình là lệch theo nhiễu.
    """
    as_of = str(args.get("as_of") or today())
    try:
        s = floor_suggest.suggest(as_of)
    except Exception as exc:  # noqa: BLE001
        return err(f"Không lấy được bối cảnh: {exc}")
    if s.get("error"):
        return err(s["error"])

    signals: list[dict] = []
    # Biến của mô hình đa biến (4 futures + giá mủ nước) — đã nằm trong mức đề xuất.
    for row in _driver_rows(s.get("drivers", []), as_of):
        note = f"đã nằm trong mô hình · số ngày {row['ngay_so_moi']} so với {row['ngay_so_lan_truoc']}"
        signals.append(_signal(row["chi_so"], row["thay_doi_pct"], _W_STRONG, +1,
                               note + (f" · {row['ghi_chu']}" if row.get("ghi_chu") else "")))

    inv = s.get("inventory") or {}
    lean = s.get("inventory_lean")
    if inv.get("ton_kho") is not None:
        # % thay đổi so với lần ban hành trước, chỉ trên các đơn vị có số ở cả hai ngày; hướng lấy từ
        # luật chung `inventory_lean` (tổng + tự do, ngưỡng ±3%) để AI nói giống màn Gợi ý giá sàn.
        span = (f"{dmy(inv['base_day'])} → {dmy(inv['day'])}, {inv['units_compared']} đơn vị có số cả 2 ngày"
                if inv.get("base_day") else f"ngày {dmy(inv['day'])}, chưa có mốc so sánh")
        signals.append({
            "tin_hieu": f"Tồn kho Tập đoàn ({span})", "thay_doi_pct": inv.get("d_ton_kho_pct"),
            "trong_so": _W_EXTRA,
            "huong_tac_dong": _LEAN_EFFECT[lean["direction"]] if lean else "chưa đủ dữ liệu",
            "quan_he": "nghịch chiều giá sàn",  # tồn TĂNG ⇒ áp lực bán ⇒ hỗ trợ HẠ
            "ghi_chu": f"{_lean_text(lean)} · tồn {_vn_int(inv['ton_kho'])} tấn ({inv['units_counted']} đơn vị) "
                       f"· tự do (chưa có HĐ) {_vn_int(inv['ton_free'])} tấn"})

    # Giá sàn SVR 3L so với vùng hợp lý theo giá mủ tư nhân — hướng tính theo VỊ TRÍ giá sàn trong vùng
    # (không phải % thay đổi), nên dựng dòng tín hiệu trực tiếp thay vì qua `_signal`.
    fob_3l = next((it.get("suggested") for it in s.get("items", [])
                   if private_price_benchmark.is_svr3l(it.get("grade", ""))), None)
    try:
        bench = private_price_benchmark.benchmark(as_of, inv or None, fob_3l)
    except Exception:  # noqa: BLE001 - thiếu dữ liệu giá tư nhân không được làm hỏng cả bảng tín hiệu
        bench = None
    if bench:
        signals.append({
            "tin_hieu": f"Giá sàn SVR 3L so với vùng giá tư nhân (giá tới {dmy(bench['ngay_gia_moi_nhat'])})",
            "thay_doi_pct": bench["dieu_chinh_pct"], "trong_so": _W_EXTRA, "chi_ap_dung": _SVR3L_DOM,
            "huong_tac_dong": bench["huong_tac_dong"], "quan_he": "neo giá nội địa",
            "ghi_chu": f"{bench['gia_san_hien_hanh_so_voi_vung']}; vùng {bench['vung_gia_san_hop_ly']['tu']:,.0f}–"
                       f"{bench['vung_gia_san_hop_ly']['den']:,.0f} đồng/tấn".replace(",", ".")
                       + "; thay_doi_pct = mức cần chỉnh để vào vùng"
                       + (f"; {bench['canh_bao_do_tuoi']}" if bench.get("canh_bao_do_tuoi") else "")})

    # Cán cân CHỈ tính trên tín hiệu trọng số "bổ sung" — đó là phần duy nhất được phép làm lệch
    # mức mô hình (tín hiệu "mạnh" đã nằm trong mô hình) — và chỉ những tín hiệu áp cho giá FOB: vùng
    # giá tư nhân là của riêng SVR 3L nội địa và ĐÃ gộp tồn kho để chọn điểm trong vùng, đem nó bù trừ
    # với tồn kho là tính tồn kho hai lần (đo thực tế: ra "cân bằng" rồi LLM bỏ luôn mức của vùng).
    extra = [g for g in signals if g["trong_so"] == _W_EXTRA and not g.get("chi_ap_dung")]
    up = sum(1 for g in extra if g["huong_tac_dong"] == "hỗ trợ NÂNG")
    down = sum(1 for g in extra if g["huong_tac_dong"] == "hỗ trợ HẠ")
    balance = ("nghiêng NÂNG" if up > down else "nghiêng HẠ" if down > up
               else "cân bằng — giữ nguyên mức mô hình")
    return {"summary": {
        "as_of": as_of, "lan_truoc": dmy(s.get("prev_as_of")),
        "bien_dong_ro_chi_so_pct": s.get("basket_change_pct"),
        "can_can_tin_hieu_bo_sung": {"ap_dung": "giá sàn FOB các chủng loại", "ho_tro_nang": up,
                                     "ho_tro_ha": down, "ket_luan": balance},
        "tin_hieu": signals, "ton_kho_ngay": inv.get("day"),
        "huong_dan": "Mức của engine đã tính từ giá mủ nước + 4 futures (mô hình đa biến). Chỉ dùng tín "
                     "hiệu trọng số 'bổ sung' (tồn kho) và số liệu đơn vị thành viên để LỆCH khỏi mức đó; tín "
                     "hiệu 'mạnh' (kể cả giá mủ nước) đã nằm trong mô hình rồi, đừng cộng thêm lần nữa. Cán cân "
                     "dành cho giá FOB. Giá NỘI ĐỊA SVR 3L theo get_private_price_benchmark — tool đó đã gộp tồn "
                     "kho khi chọn điểm trong vùng, đừng trừ tồn kho thêm lần nữa."},
        "artifact": table(f"Tín hiệu bối cảnh điều chỉnh giá sàn ({dmy(as_of)})",
                          cols(("tin_hieu", "Tín hiệu"), ("thay_doi_pct", "Thay đổi %"),
                               ("huong_tac_dong", "Hướng tác động"), ("trong_so", "Trọng số"),
                               ("ghi_chu", "Ghi chú")), signals),
        "source": f"engine drivers · biểu Tồn kho đơn vị (ngày) · giá mủ tư nhân · {dmy(as_of)}"}


def context_for_model_mode(res: dict) -> dict:
    """Mức "Theo mô hình": dòng vùng giá tư nhân chỉ giữ VỊ TRÍ, bỏ % cần chỉnh để vào vùng.

    Cùng hàng rào với `private_price_tools.for_model_mode` — không có bản lọc này thì mức điều chỉnh
    SVR 3L nội địa đi đường vòng qua bảng tín hiệu bối cảnh.
    """
    summary = res.get("summary") or {}
    if "error" in summary or not summary.get("tin_hieu"):
        return res
    marker = "; thay_doi_pct = mức cần chỉnh để vào vùng"
    rows = [{**g, "thay_doi_pct": None, "ghi_chu": g["ghi_chu"].replace(marker, "")}
            if g.get("chi_ap_dung") else g for g in summary["tin_hieu"]]
    out = {**res, "summary": {**summary, "tin_hieu": rows}}
    if res.get("artifact"):
        out["artifact"] = {**res["artifact"], "rows": rows}
    return out


TOOLS: dict[str, dict[str, Any]] = {
    "get_floor_prices": {
        "run": _floor_prices,
        "schema": {"name": "get_floor_prices",
                   "description": "Giá sàn Tập đoàn của một lần ban hành (mặc định lần MỚI NHẤT đang hiện hành) theo từng chủng loại: FOB USD/tấn, giá nội địa VNĐ/tấn, kèm mức lần trước và % thay đổi.",
                   "parameters": {"type": "object", "properties": {
                       "as_of": {"type": "string", "description": "ngày áp dụng YYYY-MM-DD của lần ban hành muốn xem (bỏ trống = lần mới nhất)"}}}}},
    "get_floor_history": {
        "run": _floor_history,
        "schema": {"name": "get_floor_history",
                   "description": "LỊCH SỬ ban hành giá sàn: mức FOB (USD/tấn) của một chủng loại qua N lần gần nhất, % thay đổi từng lần và biên độ điều chỉnh trung bình. Dùng khi hỏi 'các lần trước chỉnh bao nhiêu', 'giá sàn đã đi thế nào'.",
                   "parameters": {"type": "object", "properties": {
                       "grade": {"type": "string", "description": "chủng loại, vd 'SVR 10 / CSR 10' (mặc định), 'SVR 3L', 'LATEX'"},
                       "limit": {"type": "integer", "description": "số lần ban hành gần nhất (mặc định 12)"}}}}},
    "suggest_floor_adjustment": {
        "run": _suggest_floor,
        "schema": {"name": "suggest_floor_adjustment",
                   "description": "TƯ VẤN nên NÂNG/GIỮ/HẠ giá sàn từng chủng loại: mức đề xuất (mỗi dòng có đơn vị riêng), Δ so lần ban hành trước, độ tin cậy, các chỉ số dẫn hướng (drivers, kèm ngày của số) và bối cảnh tồn kho. Gọi tool này khi người dùng hỏi về điều chỉnh/khuyến nghị giá sàn. Người dùng hỏi MỘT chủng loại (vd 'mủ 10' = SVR 10 / CSR 10) thì truyền grade để chỉ lấy dòng đó.",
                   "parameters": {"type": "object", "properties": {
                       "as_of": {"type": "string", "description": "ngày YYYY-MM-DD (mặc định hôm nay)"},
                       "grade": {"type": "string", "enum": list(VRG_FLOOR_GRADES),
                                 "description": "chỉ lấy 1 chủng loại (bỏ trống = mọi chủng loại)"}}}}},
    "simulate_floor_scenarios": {
        "run": _scenarios,
        "schema": {"name": "simulate_floor_scenarios",
                   "description": "KỊCH BẢN what-if giá sàn: nếu rổ chỉ số thị trường tăng/giảm X% thì mức giá sàn đề xuất là bao nhiêu (Bear/Base/Bull cho từng chủng loại). Dùng khi hỏi 'nếu thị trường giảm 5% thì sao'.",
                   "parameters": {"type": "object", "properties": {
                       "as_of": {"type": "string", "description": "ngày YYYY-MM-DD (mặc định hôm nay)"},
                       "shock_pct": {"type": "number", "description": "biên độ sốc % (số DƯƠNG, vd 5 cho cả 'giảm 5%' lẫn 'tăng 5%') áp lên rổ chỉ số; kịch bản giảm đọc cột bear_giam, tăng đọc bull_tang (bỏ trống = 1 độ lệch chuẩn lịch sử)"}}}}},
    "get_floor_context": {
        "run": _floor_context,
        "schema": {"name": "get_floor_context",
                   "description": "TÍN HIỆU BÊN LỀ quanh quyết định điều chỉnh giá sàn: biến động các biến của mô hình (4 futures + giá mủ nước, kèm ngày của số), tồn kho Tập đoàn theo ngày (tổng + tự do), vị trí giá sàn SVR 3L nội địa so với vùng giá mủ tư nhân — mỗi tín hiệu kèm hướng tác động (thuận/nghịch) và TRỌNG SỐ đã đo. Gọi tool này SAU suggest_floor_adjustment khi cần điều chỉnh khỏi mức đề xuất của mô hình, để việc điều chỉnh có căn cứ thay vì cảm tính.",
                   "parameters": {"type": "object", "properties": {
                       "as_of": {"type": "string", "description": "ngày YYYY-MM-DD (mặc định hôm nay)"}}}}},
}
