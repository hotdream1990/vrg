# Chuẩn Code & Quy ước

> Áp dụng cho toàn repo. Bổ sung cho mục "Quy ước" trong [AGENTS.md](../../AGENTS.md).

## Đặt tên & tổ chức
- **File/thư mục**: kebab-case, tên mô tả rõ mục đích (đọc tên là hiểu).
- **File code < 200 dòng**; tách module khi vượt. Ưu tiên composition.
- **1 chủ đề / 1 file** với tài liệu & tri thức.

## Python (`apps/api`, `services/`, `packages/shared-py`)
- Quản lý bằng **uv**; format/lint bằng **ruff**; type bằng **mypy** (khuyến nghị).
- snake_case cho hàm/biến, PascalCase cho class. Type hints bắt buộc ở public API.
- Xử lý lỗi rõ ràng (try/except có ngữ cảnh), không nuốt exception.

## TypeScript (`apps/web`, `packages/shared-ts`)
- Quản lý bằng **pnpm** + **Vite**; lint **eslint**, format **prettier**.
- camelCase biến/hàm, PascalCase component/type. Ưu tiên bất biến (immutability).
- Boolean prefix `is/has/should/can`. Tránh magic number → đặt hằng số có tên.

## Bảo mật (bắt buộc)
- **Không hardcode secret** — dùng `.env` (xem `.env.example`).
- Validate & sanitize input; không log dữ liệu nhạy cảm (PII, token, giá nội bộ).
- Tham số hóa truy vấn DB; tuân thủ Nghị định 13/2023/NĐ-CP.

## Git
- **Conventional Commits**: `feat:`, `fix:`, `docs:`, `refactor:`, `chore:`… (tiếng Anh).
- Không commit dữ liệu mật / file build / secret. Branch theo `type/mô-tả-ngắn`.

## Ngôn ngữ
- Tài liệu, comment giải thích nghiệp vụ: **tiếng Việt**.
- Tên định danh trong code (biến, hàm, class): **tiếng Anh**.
