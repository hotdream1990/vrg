# knowledge/ — Tri thức dùng chung

Thư mục này chứa **tri thức nghiệp vụ** ở dạng **Markdown + YAML frontmatter** — đọc được bởi
**cả Claude Code, Google Antigravity, RAG engine và con người**. Đây là "bộ não" dùng chung của dự án.

## Nguyên tắc
- **1 chủ đề / 1 file**, tên **kebab-case** mô tả rõ nội dung.
- **Markdown thuần** — KHÔNG dùng cú pháp riêng của bất kỳ tool nào.
- Dữ liệu mật (Excel/PDF gốc) **không để ở đây** — chỉ trích xuất *fact* sang Markdown, ghi `source`.

## Frontmatter chuẩn
```yaml
---
title: Tiêu đề ngắn, rõ nghĩa
type: domain | data-source | process | reference
tags: [svr10, sgx, mua-vu]
source: bieu-mau/Tâm/...   # nguồn gốc (file/URL), để truy vết
updated: 2026-06-15
---
```

## Phân loại (`type`)
| type | Dùng cho | Thư mục |
|---|---|---|
| `domain` | Kiến thức ngành cao su (loại mủ, mùa vụ, thị trường) | `domain/` |
| `data-source` | Cách lấy dữ liệu (sàn, giá, vĩ mô) | `data-sources/` |
| `process` | Quy trình nghiệp vụ (báo cáo tuần/năm) | `business-process/` |
| `reference` | Phương pháp, định nghĩa kỹ thuật | `forecasting-method/` |

## Quy ước RAG
Mỗi file là một "tài liệu" có thể ingest. Giữ đoạn văn ngắn gọn, có heading rõ để chunk tốt.
Thuật ngữ chung tra ở [glossary.md](./glossary.md).
