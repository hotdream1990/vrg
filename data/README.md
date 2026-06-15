# data/ — Dữ liệu

| Thư mục | Nội dung | Git |
|---|---|---|
| `raw/` | Excel/PDF gốc (giá, BCTM, physical, biểu mẫu thật) | **gitignored** (mật) |
| `templates/` | Biểu mẫu báo cáo (mẫu trống, có thể commit) | tracked |
| `samples/` | Mẫu ẩn danh để test/dev | tracked |

## Nguyên tắc
- **Không commit dữ liệu mật của VRG.** Nguồn gốc hiện ở `docs/data/` & `docs/bieu-mau/` (đều gitignored).
- Khi cần dùng cho RAG/model: trích xuất *fact* sang `knowledge/` (Markdown), giữ raw ở `raw/`.
- Ghi `source` trong frontmatter để truy vết về file gốc.
