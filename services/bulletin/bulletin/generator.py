"""Core PPTX generator — fill BulletinData vào template, lưu file mới.

Approach: dùng file bản tin gốc làm template, tìm shape bằng name,
fill data vào đúng cell/paragraph. Giữ nguyên toàn bộ formatting.

Usage:
    data = BulletinData(report_date=..., prev_date=..., world_prices=[...])
    generate(template_path, output_path, data)
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from lxml import etree
from pptx import Presentation
from pptx.oxml.ns import qn

from .models import BulletinData


def generate(
    template_path: str | Path,
    output_path: str | Path,
    data: BulletinData,
    image_overrides: dict[str, str | Path] | None = None,
) -> Path:
    """Mở template, fill data, thay hình nếu có, lưu output. Trả về Path output.

    Args:
        image_overrides: mapping shape_name → file_path để thay hình.
            Supported keys: "Picture 2" (cover front), "Picture 1" (cover back),
            "Picture 18" (header banner), "Picture 21" (footer banner),
            "Picture 4" (logo VRG).
    """
    prs = Presentation(str(template_path))
    slides = list(prs.slides)

    _update_slide1_cover(slides[0], data)
    _update_slide2_prices(slides[1], data)
    _update_slide3_domestic(slides[2], data)
    _update_slides45_news(slides[3], slides[4], data)
    # Slide 6: giữ nguyên (trang cuối)

    # Replace images if custom overrides provided
    if image_overrides:
        _replace_images(prs, image_overrides)

    # Đồng bộ vị trí header/footer giữa các slide nội dung (template gốc đặt lệch)
    _normalize_header_footer(prs)

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(out))
    return out


# Header/footer dùng chung trên các slide nội dung (banner trên, logo, tiêu đề, banner dưới)
_HF_SHAPES = ("Picture 18", "Picture 4", "Content Placeholder 9", "Picture 21")


def _normalize_header_footer(prs: Presentation) -> None:
    """Ép các slide nội dung dùng CHUNG 1 header/footer theo slide 2.

    - Cùng vị trí + kích thước banner trên/dưới, logo, ô tiêu đề.
    - Cùng tiêu đề (text + định dạng) — copy txBody slide 2 sang (template gốc lỗi:
      slide 3 dư dòng trống & không set cỡ chữ).
    Bỏ qua slide bìa đầu (1) và bìa cuối (slide cuối).
    """
    import copy as _copy

    slides = list(prs.slides)
    if len(slides) < 3:
        return
    ref_geom: dict[str, tuple] = {}
    ref_title = None
    for sh in slides[1].shapes:  # slide 2 làm chuẩn
        if sh.name in _HF_SHAPES and sh.name not in ref_geom:
            ref_geom[sh.name] = (sh.left, sh.top, sh.width, sh.height)
        if sh.name == "Content Placeholder 9" and sh.has_text_frame:
            ref_title = sh.text_frame._txBody
    for s in slides[2:-1]:  # slide nội dung còn lại (trừ bìa cuối)
        for sh in s.shapes:
            geom = ref_geom.get(sh.name)
            if geom:
                sh.left, sh.top, sh.width, sh.height = geom
            if (sh.name == "Content Placeholder 9" and ref_title is not None
                    and sh.has_text_frame):
                cur = sh.text_frame._txBody
                cur.getparent().replace(cur, _copy.deepcopy(ref_title))


def _replace_images(prs: Presentation, overrides: dict[str, str | Path]) -> None:
    """Replace Picture shapes by name across all slides.

    Preserves position, size, and z-order. Works by removing old shape
    and inserting new image at exact same position/size.
    """
    from pptx.util import Emu

    for slide in prs.slides:
        for shape in list(slide.shapes):
            if shape.shape_type != 13:  # Not a picture
                continue
            img_path = overrides.get(shape.name)
            if not img_path:
                continue
            img_path = Path(img_path)
            if not img_path.exists():
                continue

            # Save geometry before removing
            left, top, width, height = shape.left, shape.top, shape.width, shape.height

            # Remove old picture element from slide XML
            sp_tree = slide.shapes._spTree
            sp_tree.remove(shape._element)

            # Add new picture at same position/size
            slide.shapes.add_picture(str(img_path), left, top, width, height)


# ---------------------------------------------------------------------------
# Slide 1 — Trang bìa
# ---------------------------------------------------------------------------

def _update_slide1_cover(slide, data: BulletinData) -> None:
    """Đổi ngày trên trang bìa (TextBox 9)."""
    for shape in slide.shapes:
        if shape.name == "TextBox 9" and shape.has_text_frame:
            _set_first_run_text(shape, data.report_date.strftime("%d/%m/%Y"))


# ---------------------------------------------------------------------------
# Slide 2 — Giá CSTN thế giới + Physical
# ---------------------------------------------------------------------------

# Vị trí cố định trong Table 1 (world prices): row_index → (exchange, grade)
_WORLD_TABLE_MAP = {
    2: ("OSE", "RSS3"),
    3: ("SHANGHAI", "RSS3"),
    4: ("SGX", "RSS3"),
    5: ("SGX", "TSR20"),
    6: ("MRE", "SMRCV"),
    7: ("MRE", "SMR20"),
    8: ("MRE", "LATEX"),
}

# Vị trí cố định trong Table 2 (physical): row_index → grade
_PHYSICAL_TABLE_MAP = {
    2: "RSS3",
    3: "STR20",
    4: "SMR20",
    5: "SIR20",
    6: "Thai Latex 60% (Bulk)",
    7: "Thai Latex 60% (Drums)",
}


def _update_slide2_prices(slide, data: BulletinData) -> None:
    """Fill 2 bảng giá + cập nhật ngày trong title/section headers."""
    _replace_dates_in_slide(slide, data)

    # Index world & physical prices by key for fast lookup
    world_map = {(r.exchange, r.grade): r for r in data.world_prices}
    physical_map = {r.grade: r for r in data.physical_prices}

    for shape in slide.shapes:
        if not shape.has_table:
            continue

        table = shape.table
        nrows, ncols = len(table.rows), len(table.columns)

        if nrows == 9 and ncols == 8:
            # Table 1: World prices
            _fill_table_headers_date(table, 0, data, col_prev=4, col_curr=5)
            for row_idx, key in _WORLD_TABLE_MAP.items():
                row_data = world_map.get(key)
                if row_data:
                    _set_cell(table, row_idx, 4, _fmt_price(row_data.price_prev))
                    _set_cell(table, row_idx, 5, _fmt_price(row_data.price_curr))
                    _set_cell(table, row_idx, 6, _fmt_change(row_data.change_abs))
                    _set_cell(table, row_idx, 7, _fmt_pct(row_data.change_pct))

        elif nrows == 8 and ncols == 5:
            # Table 2: Physical (ANRPC) — ngày cột = phiên vật chất thật (có thể cũ hơn ngày báo cáo)
            _fill_table_headers_date(table, 0, data, col_prev=1, col_curr=2,
                                     prev_date=data.physical_prev_date,
                                     curr_date=data.physical_curr_date)
            for row_idx, grade in _PHYSICAL_TABLE_MAP.items():
                row_data = physical_map.get(grade)
                if row_data:
                    _set_cell(table, row_idx, 1, _fmt_price(row_data.price_prev))
                    _set_cell(table, row_idx, 2, _fmt_price(row_data.price_curr))
                    _set_cell(table, row_idx, 3, _fmt_change(row_data.change_abs))
                    _set_cell(table, row_idx, 4, _fmt_pct(row_data.change_pct))


# ---------------------------------------------------------------------------
# Slide 3 — Giá trong nước (giá sàn VRG + mủ nguyên liệu)
# ---------------------------------------------------------------------------

# Vị trí cố định Table 3 (VRG floor): row_index → grade
_VRG_FLOOR_TABLE_MAP = {
    2: "SVR CV 50",
    3: "SVR CV60",
    4: "SVR L",
    5: "SVR 3L Mix",
    6: "SVR 3L",
    7: "SVR 5S",
    8: "SVR 5",
    9: "SVR 10 Mix",
    10: "SVR 10",
    11: "SVR 20",
    12: "RSS 3",
    13: "RSS 1",
    14: "LATEX",
}


def _update_slide3_domestic(slide, data: BulletinData) -> None:
    """Fill bảng giá sàn VRG + giá mủ nguyên liệu."""
    _replace_dates_in_slide(slide, data)

    if not data.vrg_floor_curr:
        return  # không có data giá sàn → giữ nguyên template

    prev_map = {r.grade: r for r in data.vrg_floor_prev}
    curr_map = {r.grade: r for r in data.vrg_floor_curr}

    for shape in slide.shapes:
        if shape.has_table:
            table = shape.table
            nrows = len(table.rows)
            if nrows == 15:  # Table 3: VRG floor prices
                # Update header labels
                if data.vrg_floor_prev_label:
                    _set_cell(table, 0, 1, data.vrg_floor_prev_label)
                if data.vrg_floor_curr_label:
                    _set_cell(table, 0, 3, data.vrg_floor_curr_label)
                # Fill data rows
                for row_idx, grade in _VRG_FLOOR_TABLE_MAP.items():
                    prev = prev_map.get(grade)
                    curr = curr_map.get(grade)
                    if prev:
                        _set_cell(table, row_idx, 1, _fmt_price(prev.fob_usd))
                        _set_cell(table, row_idx, 2, _fmt_price_vnd(prev.domestic_vnd))
                    if curr:
                        _set_cell(table, row_idx, 3, _fmt_price(curr.fob_usd))
                        _set_cell(table, row_idx, 4, _fmt_price_vnd(curr.domestic_vnd))

        # Fill giá mủ nguyên liệu — theo TỪNG ĐƠN VỊ thành viên (yêu cầu VRG, bỏ "khu vực").
        # Mỗi đơn vị 1 DÒNG (line-break <a:br/>) gom trong ô đầu; xoá các ô "Khu vực" còn lại.
        # KHÔNG có số liệu → '(chưa cập nhật)' (tránh để lọt giá khu vực giả của template).
        if shape.has_text_frame and shape.name == "Rectangle 10":
            unit_paras = [p for p in shape.text_frame.paragraphs
                          if p.text.strip().startswith("Khu vực")]
            if unit_paras:
                lines = [
                    f"Khu vực {region}: {txt} đồng/độ TSC"
                    for region, txt in (data.raw_material_regions or {}).items() if txt
                ]
                _set_para_multiline(unit_paras[0], "\n".join(lines) if lines else "(chưa cập nhật)")
                for para in unit_paras[1:]:
                    _set_first_run_text_para(para, "")


# ---------------------------------------------------------------------------
# Slide 4–5 — Thông tin thị trường
# ---------------------------------------------------------------------------

def _update_slides45_news(slide4, slide5, data: BulletinData) -> None:
    """Fill phân tích thị trường vào slide 4 và 5."""
    _replace_dates_in_slide(slide4, data)
    _replace_dates_in_slide(slide5, data)

    if not data.market_exchange_summary and not data.market_analysis:
        return  # không có input → giữ nguyên

    # Slide 4: Rectangle 14 chứa section IV
    for shape in slide4.shapes:
        if shape.has_text_frame and shape.name == "Rectangle 14":
            _fill_market_news_shape(shape, data)

    # Slide 5: Rectangle 14 chứa phần tiếp theo
    for shape in slide5.shapes:
        if shape.has_text_frame and shape.name == "Rectangle 14":
            _fill_market_continuation(shape, data)


def _fill_market_news_shape(shape, data: BulletinData) -> None:
    """Fill nội dung section IV vào shape Rectangle 14 (slide 4)."""
    paras = shape.text_frame.paragraphs
    if len(paras) < 2:
        return

    # P0 = "IV. Các thông tin thị trường liên quan:" — giữ nguyên
    # P1 = "1.  Giá cao su DD/MM trên các sàn giao dịch thế giới:" — đổi ngày
    dd_mm = data.report_date.strftime("%d/%m")
    if len(paras) > 1:
        _replace_date_in_para(paras[1], data)

    # P2-P5: exchange summary (từng sàn)
    for i, text in enumerate(data.market_exchange_summary):
        para_idx = 2 + i
        if para_idx < len(paras):
            _set_first_run_text_para(paras[para_idx], text)

    # P6: physical summary
    phys_para_idx = 2 + len(data.market_exchange_summary)
    if data.market_physical_summary and phys_para_idx < len(paras):
        _replace_date_in_para(paras[phys_para_idx], data)
        phys_para_idx += 1
        if phys_para_idx < len(paras) and data.market_physical_summary:
            _set_first_run_text_para(paras[phys_para_idx], data.market_physical_summary)

    # P8+: analysis paragraphs (admin/AI nhập tay)
    analysis_start = phys_para_idx + 1 if data.market_physical_summary else phys_para_idx
    for i, text in enumerate(data.market_analysis[:2]):  # max 2 trên slide 4
        para_idx = analysis_start + 1 + i  # +1 bỏ qua header "3. Các thông tin..."
        if para_idx < len(paras):
            _set_first_run_text_para(paras[para_idx], text)

    # Dọn các đoạn mẫu còn lại — tránh lọt nội dung mẫu của template (no fake data).
    # Không có phân tích → bỏ cả header "3."; có thì giữ header + các đoạn đã fill.
    clear_from = (analysis_start + 1 + len(data.market_analysis[:2])
                  if data.market_analysis else analysis_start)
    for j in range(clear_from, len(paras)):
        _set_first_run_text_para(paras[j], "")


def _fill_market_continuation(shape, data: BulletinData) -> None:
    """Fill phần tiếp theo vào slide 5 (phần cuối phân tích + nguồn tin)."""
    paras = shape.text_frame.paragraphs
    if len(paras) < 2:
        return

    # Dọn toàn bộ nội dung mẫu (giữ P0 = header "IV...") trước khi fill — tránh lọt text mẫu.
    for j in range(1, len(paras)):
        _set_first_run_text_para(paras[j], "")

    idx = 1
    for text in data.market_analysis[2:]:  # phần phân tích chưa fill ở slide 4
        if idx < len(paras):
            _set_first_run_text_para(paras[idx], text)
            idx += 1
    if data.source_urls and idx < len(paras):
        _set_first_run_text_para(paras[idx], "Nguồn tin: " + "  ".join(data.source_urls))


# ---------------------------------------------------------------------------
# Helpers: cell/text manipulation (preserve formatting)
# ---------------------------------------------------------------------------

def _set_para_multiline(para, value: str) -> None:
    """Set text 1 paragraph, giữ formatting run đầu. '\n' → line break OoXML <a:br/>."""
    if "\n" not in value:
        if para.runs:
            para.runs[0].text = value
            for run in para.runs[1:]:
                run.text = ""
        else:
            para.text = value
        return

    parts = value.split("\n")
    if not para.runs:
        para.text = parts[0]  # fallback (không có run để lấy format)
        return

    import copy

    rPr_src = para.runs[0]._r.find(qn("a:rPr"))
    p_elem = para._p
    for child in list(p_elem):  # xoá run/break cũ, giữ <a:pPr>
        if child.tag.endswith("}r") or child.tag.endswith("}br"):
            p_elem.remove(child)
    new_first = etree.SubElement(p_elem, qn("a:r"))
    if rPr_src is not None:
        new_first.insert(0, copy.deepcopy(rPr_src))
    etree.SubElement(new_first, qn("a:t")).text = parts[0]
    for part in parts[1:]:
        etree.SubElement(p_elem, qn("a:br"))
        new_r = etree.SubElement(p_elem, qn("a:r"))
        if rPr_src is not None:
            new_r.insert(0, copy.deepcopy(rPr_src))
        etree.SubElement(new_r, qn("a:t")).text = part


def _set_cell(table, row: int, col: int, value: str) -> None:
    """Set cell text, giữ formatting run đầu; hỗ trợ '\n' → line break."""
    _set_para_multiline(table.cell(row, col).text_frame.paragraphs[0], value)


def _set_first_run_text(shape, text: str) -> None:
    """Set text cho shape, giữ formatting của run đầu tiên."""
    para = shape.text_frame.paragraphs[0]
    if para.runs:
        para.runs[0].text = text
        for run in para.runs[1:]:
            run.text = ""
    else:
        para.text = text


def _set_first_run_text_para(para, text: str) -> None:
    """Set text cho paragraph, giữ formatting run đầu."""
    if para.runs:
        para.runs[0].text = text
        for run in para.runs[1:]:
            run.text = ""
    else:
        para.text = text


def _fill_table_headers_date(table, header_row: int, data: BulletinData,
                              col_prev: int, col_curr: int,
                              prev_date=None, curr_date=None) -> None:
    """Cập nhật ngày trong header bảng: 'Giá<br>(DD/MM/YY)'.

    prev_date/curr_date override (cho bảng physical dùng ngày phiên vật chất thật).
    """
    prev_str = (prev_date or data.prev_date).strftime("%d/%m/%y")
    curr_str = (curr_date or data.report_date).strftime("%d/%m/%y")
    _set_cell(table, header_row, col_prev, f"Giá\n({prev_str})")
    _set_cell(table, header_row, col_curr, f"Giá\n({curr_str})")


def _replace_dates_in_slide(slide, data: BulletinData) -> None:
    """Tìm và thay thế ngày trong title/section headers của slide."""
    dd_mm_yyyy = data.report_date.strftime("%d/%m/%Y")
    dd_mm = data.report_date.strftime("%d/%m")

    for shape in slide.shapes:
        if not shape.has_text_frame:
            continue
        for para in shape.text_frame.paragraphs:
            _replace_date_in_para(para, data)


def _replace_date_in_para(para, data: BulletinData) -> None:
    """Thay thế pattern ngày tháng trong paragraph text.

    Xử lý trường hợp date bị split qua nhiều runs:
    vd run1='ngày ' run2='09' run3='/06/2026'
    → gom text toàn bộ para, replace, rồi đặt lại vào run đầu.
    """
    date_pattern_full = re.compile(r"\d{2}/\d{2}/\d{4}")
    date_pattern_short = re.compile(r"(\d{2}/\d{2})(?!/\d)")

    new_full = data.report_date.strftime("%d/%m/%Y")
    new_short = data.report_date.strftime("%d/%m")

    # Thử replace trong từng run trước (simple case)
    for run in para.runs:
        if date_pattern_full.search(run.text):
            run.text = date_pattern_full.sub(new_full, run.text)
            return  # done

    # Nếu không tìm thấy trong run riêng lẻ → gom toàn bộ text
    full_text = "".join(run.text for run in para.runs)
    if date_pattern_full.search(full_text):
        new_text = date_pattern_full.sub(new_full, full_text)
        if para.runs:
            para.runs[0].text = new_text
            for run in para.runs[1:]:
                run.text = ""
        return

    # Short date (DD/MM) — chỉ trong context 'ngày' hoặc 'giá'
    if date_pattern_short.search(full_text):
        if "ngày" in full_text.lower() or "giá" in full_text.lower():
            new_text = date_pattern_short.sub(new_short, full_text)
            if para.runs:
                para.runs[0].text = new_text
                for run in para.runs[1:]:
                    run.text = ""


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _fmt_price(value: int | None) -> str:
    """Format giá: 2644 → '2,644'."""
    if value is None:
        return "N/A"
    return f"{value:,}"


def _fmt_price_vnd(value: int | None) -> str:
    """Format giá VND: 58500000 → '58,500,000'."""
    if value is None:
        return "N/A"
    return f"{value:,}"


def _fmt_change(value: int | None) -> str:
    """Format chênh lệch: +8 → '+8', -3 → '-3'."""
    if value is None:
        return ""
    return f"+{value}" if value > 0 else str(value)


def _fmt_pct(value: float | None) -> str:
    """Format phần trăm: 0.4 → '0.4', -0.3 → '-0.3'."""
    if value is None:
        return ""
    return f"{value:.1f}"
