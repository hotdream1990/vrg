-- Khởi tạo extension cho DB dự án (chạy tự động lần đầu tạo container).
-- TimescaleDB: dữ liệu chuỗi thời gian (giá, khối lượng theo thời gian).
-- pgvector:    embedding tài liệu cho RAG.
CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS vector;
