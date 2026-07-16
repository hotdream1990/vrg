# Font nhúng cho xuất PDF bản tin

Nhúng thẳng vào HTML (`@font-face` + data URI) để **PDF hiển thị giống nhau trên mọi máy**
— không phụ thuộc font cài sẵn của máy chạy Chromium (Mac dev vs Linux server).

| Font  | Thay cho          | Vì sao |
|-------|-------------------|--------|
| Tinos | Times New Roman   | Cùng metric (không lệch bố cục), phủ đủ tiếng Việt |
| Arimo | Arial             | Cùng metric, phủ đủ tiếng Việt (dùng cho header/footer) |

**Giấy phép:** Tinos & Arimo © Google — **Apache License 2.0** (được phép nhúng & phân phối lại).
Nguồn: https://github.com/google/fonts (thư mục `apache/tinos`, `apache/arimo`).
