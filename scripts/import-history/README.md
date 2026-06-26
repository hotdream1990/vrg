# Import lịch sử giá vào `fact_price`

Scripts nạp dữ liệu lịch sử từ các file Excel của Ban TTKD vào DB (`fact_price`),
**chỉ từ năm 2024 trở đi**. Chia nhỏ theo nguồn để dễ chạy lại / bổ sung file mới.

## Cài & chạy
DB lấy từ `DATABASE_URL` (mặc định `postgresql://vrg:changeme@localhost:5433/vrg_caosu`).
Mỗi script idempotent (upsert theo khóa `as_of+source+grade+contract+price_type`) → chạy lại an toàn.

```bash
cd scripts/import-history
RUN='uv run --with openpyxl --with "psycopg[binary]" python'

# ► TRIỂN KHAI: nạp TẤT CẢ vào DB (idempotent, chỉ từ 2024). 1 lệnh duy nhất:
DATABASE_URL=postgresql://user:pass@host:5432/db $RUN run_all.py   # production
$RUN run_all.py                                                    # dev (DB mặc định)

# Hoặc chạy lẻ từng nguồn:
$RUN import_exchange.py        # giá sàn OSE/SHFE/SGX/MRB + FX  <- nguồn chính
$RUN import_latex.py           # giá mủ nước (thu mua theo cty + theo khu vực)
$RUN import_physical_staff.py  # giá physical USD/tấn từ sheet 'Lưu'
$RUN import_floor.py           # giá sàn Tập đoàn ban hành (FOB USD/T + nội địa VNĐ/T)
$RUN coverage_report.py        # báo cáo độ phủ -> Excel
# Xem trước (không ghi DB): thêm --dry-run vào từng import.
# ⛔ KHÔNG dùng import_physical.py (file Reuters tháng, baht/kg lẫn đơn vị — đã loại bỏ)
```

- `run_all.py` đọc **DATABASE_URL** (DB đích) + **BIEU_MAU_DOCS** (mặc định `<repo>/docs`), đường dẫn file tương đối nên chạy được trên production. Chỉ nạp `as_of >= 2024` (đổi `--from-year`).

## Nguồn & mapping (khớp `apps/api/.../market_meta.py`)
| Script | File nguồn | source | price_type | grade | đơn vị |
|---|---|---|---|---|---|
| `import_exchange` | `bieu-mau-bo-sung/Giá các sàn ...2021-2025.xlsx` sheet `'2025'` | tocom/shfe/sgx/lgm | settlement/physical | RSS3/RU/TSR20/SMRCV/SMR20/LATEX | theo market_meta |
| `import_exchange` (FX) | cùng file | fx | fx | USD/JPY, USD/CNY, USD/MYR | x per USD |
| `import_latex` | `bieu-mau/Tâm/Mẫu file lấy giá...xlsx` | vrg | purchase / region | tên công ty / khu vực | đồng/độ TSC |
| `import_physical_staff` | `bieu-mau-bo-sung/Giá các sàn ...2021-2025.xlsx` sheet `'Lưu'` (bảng phải) | reuters | physical | RSS3/STR20/SMR20/SIR20/Thai Latex 60% Bulk·Drums | **USD/tonne** (đã quy đổi sẵn) |
| `import_floor` | `bieu-mau-bo-sung/...2021-2025.xlsx` + master, sheet `'Bảng tính giá'` | (bảng `vrg_floor_price`) | — | SVR CV50/60, L, 3L Mix/3L, 5S/5, 10 Mix/10, 20, RSS3/1, LATEX | FOB **USD/T** + nội địa **VNĐ/T** |
| ~~`import_physical`~~ (loại bỏ) | ~~Tâm/Giá Physical file tháng~~ | — | — | baht/kg lẫn đơn vị, sai → **không dùng** | — |

## Lưu ý chất lượng dữ liệu
- **Ngày dd/mm + năm ngầm sai**: sheet giá mủ chỉ có dd/mm, năm Excel lưu loạn → `_lib.reconstruct_years`
  dựng lại năm (neo cột cuối = 2026, lùi khi Tháng12→Tháng1) và loại ô ngày lạc (đơn điệu tăng).
- **Giá khoảng** (`407-412`) → lấy trung điểm.
- **Physical**: lấy từ sheet `'Lưu'` (kho lưu hàng ngày của chuyên viên) — bảng phải đã là **USD/tấn**,
  không cần quy đổi. Phủ 14/05/2024 → 01/10/2025; ngày 'd/m' (không năm) tới 11/6/2025 → dựng năm đơn điệu.
  Phần 10/2025→giữa 2026 chưa có nguồn (chỉ `anrpc` live). File Reuters tháng (baht/kg) **đã loại bỏ vì sai**.
- Chỉ nạp `as_of >= 2024-01-01` (đổi qua `--from-year`).
