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

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(out))
    return out


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
            # Table 2: Physical (ANRPC)
            _fill_table_headers_date(table, 0, data, col_prev=1, col_curr=2)
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

        # Fill giá mủ nguyên liệu
        if (shape.has_text_frame and shape.name == "Rectangle 10"
                and data.raw_material_regions):
            paras = shape.text_frame.paragraphs
            # Tìm para bắt đầu "Khu vực" và replace
            region_idx = 0
            regions_list = list(data.raw_material_regions.items())
            for para in paras:
                if para.text.strip().startswith("Khu vực") and region_idx < len(regions_list):
                    region, price_text = regions_list[region_idx]
                    _set_first_run_text_para(para, f"Khu vực {region}: {price_text}")
                    region_idx += 1


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

    # P8+: analysis paragraphs
    analysis_start = phys_para_idx + 1 if data.market_physical_summary else phys_para_idx
    for i, text in enumerate(data.market_analysis[:2]):  # max 2 trên slide 4
        para_idx = analysis_start + 1 + i  # +1 bỏ qua header "3. Các thông tin..."
        if para_idx < len(paras):
            _set_first_run_text_para(paras[para_idx], text)


def _fill_market_continuation(shape, data: BulletinData) -> None:
    """Fill phần tiếp theo vào slide 5."""
    paras = shape.text_frame.paragraphs
    if len(paras) < 2:
        return

    # Slide 5 thường chứa phần cuối phân tích + nguồn tin
    remaining_analysis = data.market_analysis[2:]  # phần chưa fill ở slide 4
    for i, text in enumerate(remaining_analysis):
        para_idx = 1 + i
        if para_idx < len(paras):
            _set_first_run_text_para(paras[para_idx], text)

    # Source URLs ở cuối
    url_start = 1 + len(remaining_analysis) + 1
    for i, url in enumerate(data.source_urls):
        para_idx = url_start + i
        if para_idx < len(paras):
            _set_first_run_text_para(paras[para_idx], url)


# ---------------------------------------------------------------------------
# Helpers: cell/text manipulation (preserve formatting)
# ---------------------------------------------------------------------------

def _set_cell(table, row: int, col: int, value: str) -> None:
    """Set cell text, giữ nguyên formatting của run đầu tiên.

    Hỗ trợ '\n' → line break OoXML (thay vì \x0b bị escape).
    """
    cell = table.cell(row, col)
    para = cell.text_frame.paragraphs[0]
    if "\n" not in value:
        # Simple case: no line break
        if para.runs:
            para.runs[0].text = value
            for run in para.runs[1:]:
                run.text = ""
        else:
            para.text = value
    else:
        # Line break: cần tạo <a:br/> element
        parts = value.split("\n")
        if para.runs:
            # Lưu format từ run đầu
            first_run = para.runs[0]
            rPr_src = first_run._r.find(qn("a:rPr"))

            # Xóa toàn bộ run cũ + break cũ, chỉ giữ <a:pPr>
            p_elem = para._p
            for child in list(p_elem):
                tag = child.tag
                if tag.endswith("}r") or tag.endswith("}br"):
                    p_elem.remove(child)

            # Tạo run đầu tiên với text part[0]
            new_first = etree.SubElement(p_elem, qn("a:r"))
            if rPr_src is not None:
                import copy
                new_first.insert(0, copy.deepcopy(rPr_src))
            t0 = etree.SubElement(new_first, qn("a:t"))
            t0.text = parts[0]

            # Thêm line break + run mới cho phần sau
            for part in parts[1:]:
                etree.SubElement(p_elem, qn("a:br"))
                new_r = etree.SubElement(p_elem, qn("a:r"))
                if rPr_src is not None:
                    new_r.insert(0, copy.deepcopy(rPr_src))
                t = etree.SubElement(new_r, qn("a:t"))
                t.text = part
        else:
            para.text = parts[0]  # fallback


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
                              col_prev: int, col_curr: int) -> None:
    """Cập nhật ngày trong header bảng: 'Giá<br>(DD/MM/YY)'."""
    prev_str = data.prev_date.strftime("%d/%m/%y")
    curr_str = data.report_date.strftime("%d/%m/%y")
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
