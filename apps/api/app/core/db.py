"""Kết nối DB (SQLAlchemy 2 + psycopg3) cho persistence giá quét.

Engine khởi tạo lười (lazy) để API vẫn chạy khi DB tạm thời down — endpoint quét
sẽ degrade gracefully thay vì sập. `ensure_schema()` tạo bảng idempotent (phòng khi
init SQL chưa chạy do volume cũ).
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

_engine: Engine | None = None
_Session: sessionmaker[Session] | None = None
_schema_ready = False

# DDL idempotent — khớp infra/db/init/02-schema.sql. Nguồn ghi giá đã chuẩn hóa.
_DDL_TABLES = """
CREATE TABLE IF NOT EXISTS meta_crawl_run (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    started_at  timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz,
    sources     text,
    status      text NOT NULL DEFAULT 'running',
    rows        integer NOT NULL DEFAULT 0,
    error       text
);

CREATE TABLE IF NOT EXISTS fact_price (
    as_of       date NOT NULL,
    source      text NOT NULL,
    grade       text NOT NULL,
    contract    text NOT NULL DEFAULT '',
    price_type  text NOT NULL,
    price       double precision NOT NULL,
    currency    text NOT NULL,
    unit        text NOT NULL,
    source_ts   timestamptz,
    run_id      bigint,
    ingested_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (as_of, source, grade, price_type)  -- contract KHÔNG trong PK: mỗi (ngày,sàn,grade) 1 dòng, upsert ghi đè
);

CREATE INDEX IF NOT EXISTS ix_fact_price_latest
    ON fact_price (source, grade, as_of DESC);

CREATE TABLE IF NOT EXISTS vrg_floor_price (
    lan          integer NOT NULL,
    as_of        date NOT NULL,
    grade        text NOT NULL,
    fob_usd      double precision,
    domestic_vnd double precision,
    title        text,
    dispatch_no      text,                 -- số công văn (theo lần)
    dispatch_summary text,                 -- trích yếu nội dung công văn (theo lần)
    ingested_at  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (lan, grade)
);

CREATE INDEX IF NOT EXISTS ix_vrg_floor_asof ON vrg_floor_price (as_of DESC, lan DESC);

CREATE TABLE IF NOT EXISTS fact_inventory (
    as_of       date PRIMARY KEY,
    ton_kho     double precision,
    ton_kho_hd  double precision,
    note        text,
    source      text NOT NULL DEFAULT 'hanh_weekly',
    ingested_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS member_unit (
    name        text PRIMARY KEY,
    sort_order  integer NOT NULL DEFAULT 0,
    is_active   boolean NOT NULL DEFAULT true,
    note        text,
    created_at  timestamptz NOT NULL DEFAULT now()
);

-- Khu vực (nhóm các đơn vị thành viên) — dùng gom giá mủ nguyên liệu theo khu vực trong bản tin.
CREATE TABLE IF NOT EXISTS member_region (
    name        text PRIMARY KEY,
    sort_order  integer NOT NULL DEFAULT 0,
    is_active   boolean NOT NULL DEFAULT true,
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS app_user (
    username      text PRIMARY KEY,
    password_hash text NOT NULL,
    full_name     text,
    role          text NOT NULL DEFAULT 'admin',
    is_active     boolean NOT NULL DEFAULT true,
    permissions   jsonb NOT NULL DEFAULT '[]'::jsonb,  -- quyền theo mục (editor); admin=tất cả
    created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS app_config (
    key         text PRIMARY KEY,
    value       text,
    is_secret   boolean NOT NULL DEFAULT false,
    updated_at  timestamptz NOT NULL DEFAULT now(),
    updated_by  text
);

CREATE TABLE IF NOT EXISTS schedule_job (
    name        text PRIMARY KEY,
    hour        integer NOT NULL,
    minute      integer NOT NULL,
    enabled     boolean NOT NULL DEFAULT true,
    updated_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS bulletin_draft (
    report_date  date PRIMARY KEY,
    payload      jsonb NOT NULL,
    updated_at   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS market_quote (
    as_of       date PRIMARY KEY,
    payload     jsonb NOT NULL,
    updated_at  timestamptz NOT NULL DEFAULT now()
);

-- Danh mục "đơn vị tư nhân" cho Mục 6 Báo giá mủ (giá mủ tư nhân). Chuyên viên thêm, chỉ admin xoá.
-- Giá theo ngày nằm trong market_quote.payload.private_prices (khoá = tên), không nằm ở đây.
CREATE TABLE IF NOT EXISTS market_private_unit (
    id          serial PRIMARY KEY,
    name        text NOT NULL,
    created_by  text,
    created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_market_private_unit_name ON market_private_unit (lower(name));

CREATE TABLE IF NOT EXISTS weekly_report (
    week_key    text PRIMARY KEY,          -- ngày Thứ 2 ISO của tuần, 'YYYY-MM-DD'
    payload     jsonb NOT NULL,            -- narrative (các phần viết) + override bảng III.3
    updated_at  timestamptz NOT NULL DEFAULT now()
);

-- Danh mục nguồn tham khảo của Báo cáo tuần (cấu hình được; seed mặc định khi bảng rỗng).
-- mode quyết định cách hệ thống dùng nguồn: internal · market_feed (tự lấy theo feed_symbol) ·
-- vietnambiz (tự đọc bài trong kỳ) · attachment (chuyên viên tải file) · manual (chỉ là link).
CREATE TABLE IF NOT EXISTS weekly_source (
    id          serial PRIMARY KEY,
    category    text NOT NULL,             -- futures|physical|financial|news|macro
    name        text NOT NULL,
    role        text NOT NULL DEFAULT '',  -- vai trò trong phân tích
    url         text NOT NULL DEFAULT '',
    sections    jsonb NOT NULL DEFAULT '[]'::jsonb,  -- mục báo cáo dùng nguồn: ["III.1","IV.3"]
    guide       text NOT NULL DEFAULT '',  -- cách lấy/đọc số liệu (AI + chuyên viên đọc)
    mode        text NOT NULL DEFAULT 'manual',
    feed_symbol text,                      -- mã chỉ số khi mode=market_feed (kiểu Yahoo DX-Y.NYB hoặc CNBC @LCO.1)
    enabled     boolean NOT NULL DEFAULT true,
    sort_order  integer NOT NULL DEFAULT 0,
    updated_by  text,
    updated_at  timestamptz NOT NULL DEFAULT now()
);

-- Tài liệu đính kèm của từng báo cáo tuần (PDF/DOCX, vd báo cáo ANRPC) + chữ trích ra để AI đọc.
-- Không ràng FK với weekly_report: chuyên viên có thể tải file lên trước khi lưu báo cáo.
CREATE TABLE IF NOT EXISTS weekly_report_attachment (
    id           serial PRIMARY KEY,
    week_key     text NOT NULL,            -- Thứ 2 ISO của tuần đầu kỳ (khoá báo cáo tuần)
    file         text NOT NULL,            -- tên lưu (uuid) trong data_dir()/weekly-reports/attachments
    filename     text NOT NULL,            -- tên gốc
    size         bigint NOT NULL DEFAULT 0,
    kind         text NOT NULL DEFAULT 'other',  -- 'anrpc' | 'other'
    pages        integer,                  -- số trang PDF (DOCX: NULL)
    text_content text NOT NULL DEFAULT '', -- chữ trích (đã chuẩn hoá, cắt 200.000 ký tự)
    summary      text,                     -- AI/chuyên viên tóm tắt số liệu chính
    uploaded_by  text,
    created_at   timestamptz NOT NULL DEFAULT now(),
    updated_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_weekly_report_attachment_week ON weekly_report_attachment (week_key, id);

-- Nhu cầu thị trường: free text theo (đơn vị thành viên, ngày). Đơn vị tự nhập của mình;
-- chuyên viên có quyền market_demand xem/sửa mọi đơn vị. `company` khớp tên đơn vị (member_unit).
CREATE TABLE IF NOT EXISTS market_demand (
    as_of       date NOT NULL,
    company     text NOT NULL,
    content     text NOT NULL DEFAULT '',
    updated_at  timestamptz NOT NULL DEFAULT now(),
    updated_by  text,
    PRIMARY KEY (as_of, company)
);

-- Nhu cầu thị trường THEO TRƯỜNG (17/09/2026): mỗi dòng = MỘT nhu cầu của MỘT chủng loại, có tình
-- trạng cập nhật về sau. Thay cho ô chữ tự do `market_demand` (bảng cũ giữ lại để tra lịch sử).
CREATE TABLE IF NOT EXISTS market_demand_item (
    id                bigserial PRIMARY KEY,
    company           text NOT NULL,                 -- đơn vị thành viên ghi nhận
    as_of             date NOT NULL,                 -- ngày nhận nhu cầu
    customer          text NOT NULL,                 -- khách hỏi mua (gõ tự do)
    grade             text NOT NULL,                 -- chủng loại (UNIT_GRADES)
    qty               numeric,                       -- số lượng (không bắt buộc)
    qty_unit          text NOT NULL DEFAULT 'ton',   -- ton | container
    price             numeric,                       -- đơn giá (không bắt buộc)
    currency          text NOT NULL DEFAULT 'VND',   -- VND = triệu đồng/tấn · USD = USD/tấn
    delivery_place    text NOT NULL DEFAULT '',
    delivery_time     text NOT NULL DEFAULT '',      -- thời gian giao, gõ tự do
    result            text NOT NULL DEFAULT '',      -- kết quả, gõ tự do (trống = chưa có)
    note              text NOT NULL DEFAULT '',
    source_key        text,                          -- khoá chống nhập trùng khi chuyển dữ liệu cũ
    created_at        timestamptz NOT NULL DEFAULT now(),
    created_by        text,
    updated_at        timestamptz NOT NULL DEFAULT now(),
    updated_by        text
);
CREATE INDEX IF NOT EXISTS ix_mdi_company_date ON market_demand_item (company, as_of DESC);
CREATE INDEX IF NOT EXISTS ix_mdi_date ON market_demand_item (as_of DESC);
CREATE UNIQUE INDEX IF NOT EXISTS ux_mdi_source_key ON market_demand_item (source_key)
    WHERE source_key IS NOT NULL;

-- Báo cáo tiêu thụ – tồn kho của đơn vị thành viên (theo NGÀY) — 2 loại: thu mua ('purchase')
-- & tiêu thụ–tồn kho ('consumption'). Mỗi (ngày, đơn vị, loại) = 1 bản ghi, số liệu jsonb {field: number}.
-- Đơn vị tự nhập của mình; chuyên viên có quyền `unit_daily` xem/sửa mọi đơn vị (realtime).
CREATE TABLE IF NOT EXISTS unit_daily_report (
    as_of       date NOT NULL,         -- ngày báo cáo 'YYYY-MM-DD'
    company     text NOT NULL,         -- tên đơn vị (khớp member_unit)
    kind        text NOT NULL,         -- 'purchase' | 'consumption'
    payload     jsonb NOT NULL DEFAULT '{}'::jsonb,
    updated_at  timestamptz NOT NULL DEFAULT now(),
    updated_by  text,
    PRIMARY KEY (as_of, company, kind)
);
CREATE INDEX IF NOT EXISTS ix_unit_daily_date ON unit_daily_report (kind, as_of DESC);

-- Tồn kho ĐÃ KÝ HỢP ĐỒNG chưa giao — KHÔNG nhập lại mỗi ngày (hợp đồng có file scan, nhập lại
-- hằng ngày sẽ phình dữ liệu). Mỗi hợp đồng là 1 BẢN GHI có vòng đời: tính vào tồn kho từ
-- `start_date` đến HẾT ngày TRƯỚC `delivered_date`; chưa giao (`delivered_date` NULL) thì còn tồn.
CREATE TABLE IF NOT EXISTS unit_stock_contract (
    id          bigserial PRIMARY KEY,
    company     text NOT NULL,          -- đơn vị (khớp member_unit)
    code        text,                   -- số Hợp đồng / Phụ lục
    grade       text NOT NULL,          -- chủng loại
    qty         double precision,       -- số lượng (tấn)
    price       double precision,       -- đơn giá (theo `ccy`)
    ccy         text NOT NULL DEFAULT 'VND',
    fx          double precision,       -- tỷ giá USD→VND (khi ccy = USD)
    start_date  date NOT NULL,          -- ngày bắt đầu tồn kho
    delivery_date  date,                -- lịch giao (dự kiến)
    delivered_date date,                -- ngày giao THỰC TẾ (trống = chưa giao, vẫn đang tồn)
    file        text,                   -- HĐ đã ký scan: file ĐẦU trong `files` (giữ cho bản ghi cũ)
    filename    text,                   -- tên gốc để hiển thị (file đầu)
    files       jsonb NOT NULL DEFAULT '[]'::jsonb,  -- NHIỀU file: [{file, filename}]
    updated_at  timestamptz NOT NULL DEFAULT now(),
    updated_by  text
);
CREATE INDEX IF NOT EXISTS ix_stock_contract_company ON unit_stock_contract (company, start_date);

-- Chỉ tiêu KẾ HOẠCH thu mua theo năm cho từng đơn vị (dùng tính % thực hiện kế hoạch).
CREATE TABLE IF NOT EXISTS unit_purchase_plan (
    year        integer NOT NULL,
    company     text NOT NULL,
    plan_tonnes double precision,       -- kế hoạch thu mua năm (tấn)
    signed_lt_tonnes double precision,  -- tổng SL đã ký HĐ dài hạn năm (tấn)
    carry_lt_tonnes  double precision,  -- SL tiêu thụ HĐ dài hạn năm trước chuyển sang (tấn)
    carry_spot_tonnes double precision, -- SL tiêu thụ HĐ chuyến năm trước chuyển sang (tấn)
    updated_at  timestamptz NOT NULL DEFAULT now(),
    updated_by  text,
    PRIMARY KEY (year, company)
);

-- Nhật ký hoạt động (audit log): MỖI lần ghi/xoá số liệu = 1 DÒNG MỚI, không ghi đè.
-- Truy vết được ai · lúc nào · sửa ô nào · từ giá trị nào sang giá trị nào (data_before/data_after).
-- Bảng độc lập với bảng nghiệp vụ — xoá bản ghi nghiệp vụ vẫn còn nguyên vết ở đây.
CREATE TABLE IF NOT EXISTS audit_log (
    id          bigserial PRIMARY KEY,
    at          timestamptz NOT NULL DEFAULT now(),
    actor       text NOT NULL,              -- username; 'system' = job tự chạy; 'public:<đơn vị>' = link công khai
    actor_role  text,                       -- admin | editor | member (rỗng nếu không phải tài khoản)
    on_behalf   text,                       -- admin đang "đăng nhập hộ" (nếu có) — vẫn truy ra người thật
    entity      text NOT NULL,              -- nhóm số liệu: raw_material | physical | floor | inventory | ...
    action      text NOT NULL,              -- create | update | delete | scan | import
    entity_key  text NOT NULL DEFAULT '',   -- khoá bản ghi, vd '2026-07-23|sgx|TSR20|settle'
    as_of       date,                       -- ngày số liệu (để lọc "mọi thay đổi của ngày X")
    company     text,                       -- đơn vị thành viên (nếu có) — để lọc theo đơn vị
    data_before jsonb,                      -- giá trị TRƯỚC khi sửa (NULL khi thêm mới)
    data_after  jsonb,                      -- giá trị SAU khi sửa (NULL khi xoá)
    ip          text,
    note        text                        -- diễn giải ngắn (vd 'nhập từ file', 'xoá cả ngày')
);
CREATE INDEX IF NOT EXISTS ix_audit_at ON audit_log (at DESC);
CREATE INDEX IF NOT EXISTS ix_audit_entity ON audit_log (entity, at DESC);
CREATE INDEX IF NOT EXISTS ix_audit_actor ON audit_log (actor, at DESC);
CREATE INDEX IF NOT EXISTS ix_audit_key ON audit_log (entity, entity_key, at DESC);
CREATE INDEX IF NOT EXISTS ix_audit_asof ON audit_log (as_of);

-- Lịch sử truy cập (access log): ai ĐĂNG NHẬP lúc nào · VÀO TRANG nào. Tách riêng khỏi
-- `audit_log` (chỉ ghi THAY ĐỔI số liệu) để nhật ký thay đổi không bị loãng vì lượt xem.
-- `label` = tên trang tiếng Việt do server ánh xạ từ `path` (không tin nhãn client gửi lên).
CREATE TABLE IF NOT EXISTS access_log (
    id         bigserial PRIMARY KEY,
    at         timestamptz NOT NULL DEFAULT now(),
    username   text NOT NULL,
    role       text,                       -- vai trò lúc truy cập (leader | member | editor | ...)
    on_behalf  text,                       -- admin đang "đăng nhập hộ" (nếu có)
    event      text NOT NULL,              -- login | login_failed | page
    path       text NOT NULL DEFAULT '',   -- đường dẫn đã chuẩn hoá (đoạn động gom về dạng chung)
    label      text NOT NULL DEFAULT '',   -- tên trang tiếng Việt
    company    text,                       -- đơn vị được gán (tài khoản đơn vị/lãnh đạo đơn vị)
    ip         text,
    user_agent text
);
CREATE INDEX IF NOT EXISTS ix_access_at ON access_log (at DESC);
CREATE INDEX IF NOT EXISTS ix_access_user ON access_log (username, at DESC);
CREATE INDEX IF NOT EXISTS ix_access_event ON access_log (event, at DESC);

-- Danh mục KHÁCH HÀNG — quản lý RIÊNG cho từng đơn vị (chốt Q6 30/07/2026): mỗi đơn vị một
-- danh sách của mình, KHÔNG dùng chung ở cấp Tập đoàn. Hợp đồng gán khách của chính đơn vị đó.
CREATE TABLE IF NOT EXISTS unit_customer (
    id          bigserial PRIMARY KEY,
    company     text NOT NULL,          -- đơn vị SỞ HỮU danh mục (khớp member_unit)
    code        text,                   -- mã khách hàng (đơn vị tự đặt)
    name        text NOT NULL,
    tax_code    text,                   -- mã số thuế
    note        text,
    is_active   boolean NOT NULL DEFAULT true,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),
    updated_by  text
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_unit_customer_name ON unit_customer (company, lower(name));
CREATE INDEX IF NOT EXISTS ix_unit_customer_company ON unit_customer (company, is_active);

-- HỢP ĐỒNG BÁN HÀNG 2 CẤP (chốt 30/07/2026) — thay thế cách nhập tiêu thụ theo ngày:
--   `parent_id` NULL  = HỢP ĐỒNG. `delivery_type` = 'single' (giao trọn 1 lần)
--                       hoặc 'multi' (giao nhiều lần; hợp đồng giữ TỔNG SL cam kết ở `lines`).
--   `parent_id` khác  = ĐỢT GIAO (tên cũ: phụ lục). Mỗi đợt = 1 lần giao: hoá đơn · giấy xuất
--                       hàng · ngày giao · dòng chi tiết + 1 lần thanh toán.
--   `master_id` khác  = bản ghi là PHỤ LỤC của một HỢP ĐỒNG MẸ (`master_contract` — 21/08/2026):
--                       CHỈ là liên kết hồ sơ: hợp đồng vẫn giữ khách hàng và mọi số liệu của
--                       chính nó. NULL = hợp đồng không thuộc hồ sơ nào (mọi bản ghi cũ).
-- Tiêu thụ = tổng các ĐỢT ĐÃ GIAO; "đã ký HĐ chưa giao" (khối 3) = SL cam kết của HỢP ĐỒNG
-- − tổng đã giao, tính tới khi hợp đồng được đánh dấu HOÀN THÀNH (`completed_at`).
-- `lines` jsonb: [{grade, qty, qty_dry, price, ccy, fx, cost}] — nhiều chủng loại trên 1 hợp đồng.
--   Dòng của HỢP ĐỒNG có thể mang `from_date` (ngày hiệu lực, 30/09/2026) — trống = ngày ký; khối 3
--   tại ngày D chỉ cộng dòng hiệu lực ≤ D. Đợt giao không có khoá này.
CREATE TABLE IF NOT EXISTS sales_contract (
    id            bigserial PRIMARY KEY,
    company       text NOT NULL,        -- đơn vị bán (khớp member_unit)
    parent_id     bigint,               -- NULL = hợp đồng; khác NULL = ĐỢT GIAO của hợp đồng đó
    code          text NOT NULL,        -- số hợp đồng / số đợt giao
    customer_id   bigint,               -- khách hàng (unit_customer.id) — chỉ đặt ở hợp đồng mẹ
    delivery_type text NOT NULL DEFAULT 'single',  -- single | multi (chỉ có nghĩa ở hợp đồng mẹ)
    contract_type text,                 -- long_term | spot — loại HĐ, đặt ở hợp đồng (đợt thừa kế)
    sign_date     date,                 -- ngày ký
    expiry_date   date,                 -- thời hạn hợp đồng
    start_date    date,                 -- NGÀY BẮT ĐẦU của đợt giao (hàng gom vào kho cho đợt này)
    lines         jsonb NOT NULL DEFAULT '[]'::jsonb,
    delivered     boolean NOT NULL DEFAULT false,  -- suy từ delivered_at (có ngày giao = đã giao)
    delivered_at  date,                 -- NGÀY GIAO — mốc tính tiêu thụ vào kỳ báo cáo
    channel       text,                 -- export | domestic | internal (hình thức tiêu thụ)
    to_company    text,                 -- đơn vị NHẬN khi channel = 'internal' (tiêu thụ nội bộ)
    payment_date  date,                 -- 1 lần thanh toán / đợt giao (Q7) — KHÔNG theo dõi công nợ
    payment_qty   double precision,     -- sản lượng thanh toán (tấn)
    payment_cost  double precision,     -- (BỎ 03/08/2026) chi phí lần thanh toán — giữ cột cho dữ liệu cũ
    payment_docs  jsonb NOT NULL DEFAULT '[]'::jsonb,  -- chứng từ/hoá đơn: [{file, filename}]
    files         jsonb NOT NULL DEFAULT '[]'::jsonb,  -- hợp đồng scan: [{file, filename}]
    note          text,
    updated_at    timestamptz NOT NULL DEFAULT now(),
    updated_by    text
);
CREATE INDEX IF NOT EXISTS ix_sales_contract_company ON sales_contract (company, sign_date);
CREATE INDEX IF NOT EXISTS ix_sales_contract_parent ON sales_contract (parent_id);
CREATE INDEX IF NOT EXISTS ix_sales_contract_delivered ON sales_contract (delivered_at);

-- HỢP ĐỒNG MẸ — HĐ NGUYÊN TẮC (HĐNT) / HĐ DÀI HẠN (HĐDH) ký với khách hàng (chốt 21/08/2026).
-- Trước đây hệ thống KHÔNG quản lý cấp này: đơn vị nhập MỖI PHỤ LỤC như một hợp đồng. Nay hồ sơ
-- gốc được lưu riêng, `sales_contract.master_id` nối phụ lục về hợp đồng mẹ của nó.
-- Hợp đồng mẹ giữ THÔNG TIN KHÁCH HÀNG của hồ sơ + cam kết chủng loại / số lượng / đơn giá +
-- CÔNG THỨC GIÁ (HĐDH có công thức, HĐNT không có phần này) + bản scan.
-- ⚠ Nối hồ sơ CHỈ là liên kết (chốt 24/08/2026): hợp đồng vẫn tự khai khách hàng của chính nó,
-- gắn/gỡ hồ sơ KHÔNG đụng tới bất kỳ số liệu nào của hợp đồng.
-- ⚠ Bảng này KHÔNG vào tiêu thụ hay "đã ký HĐ chưa giao" (khối 3) — hai số đó vẫn tính trên
-- `sales_contract`; cộng cả hai cấp là đếm sản lượng hai lần. Cam kết của hồ sơ CHỈ dùng cho "còn
-- phải giao" (`contract_backlog`, 26/09/2026), nơi phụ lục của hồ sơ được tính ở cấp hồ sơ thay thế.
CREATE TABLE IF NOT EXISTS master_contract (
    id            bigserial PRIMARY KEY,
    company       text NOT NULL,        -- đơn vị ký (khớp member_unit)
    code          text NOT NULL,        -- SỐ HỢP ĐỒNG (mẹ) — duy nhất trong đơn vị
    master_type   text NOT NULL,        -- principle = HĐ nguyên tắc | long_term = HĐ dài hạn
    customer_id   bigint,               -- khách hàng CỦA HỒ SƠ (unit_customer.id)
    sign_date     date,
    expiry_date   date,
    lines         jsonb NOT NULL DEFAULT '[]'::jsonb,  -- [{grade, qty, price, ccy, fx}]
    price_formula text,                 -- công thức giá — TEXT tự do (HĐNT thường để trống)
    files         jsonb NOT NULL DEFAULT '[]'::jsonb,  -- hợp đồng scan: [{file, filename}]
    note          text,
    created_at    timestamptz NOT NULL DEFAULT now(),
    updated_at    timestamptz NOT NULL DEFAULT now(),
    updated_by    text
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_master_contract_code
    ON master_contract (company, lower(code));
CREATE INDEX IF NOT EXISTS ix_master_contract_company ON master_contract (company, sign_date);

-- CHỐT SỐ LIỆU ĐƠN VỊ (chốt 25/08/2026): Ban TTKD phát một ĐỢT CHỐT "chốt số liệu đến hết ngày X";
-- mỗi đơn vị tự rà rồi XÁC NHẬN, xác nhận xong là số liệu ≤ ngày X khoá lại với chính đơn vị đó
-- (chuyên viên/quản trị vẫn sửa được — đó là đường sửa duy nhất sau khi chốt).
-- Vì sao 2 bảng: đợt chốt là việc của Ban (1 dòng cho cả hệ thống), còn xác nhận là việc của từng
-- đơn vị (mỗi đơn vị 1 dòng) — nhờ vậy trang theo dõi lọc được "đơn vị chưa xác nhận" và giữ được
-- lịch sử các lần chốt trước.
CREATE TABLE IF NOT EXISTS data_lock_round (
    id           bigserial PRIMARY KEY,
    lock_date    date NOT NULL,          -- chốt số liệu đến HẾT ngày này
    note         text,                   -- lời nhắn của Ban hiện trong cảnh báo của đơn vị
    created_at   timestamptz NOT NULL DEFAULT now(),
    created_by   text,
    cancelled_at timestamptz             -- huỷ đợt: giữ vết chứ không xoá; đợt đã huỷ hết khoá
);
CREATE INDEX IF NOT EXISTS ix_data_lock_round_date ON data_lock_round (lock_date DESC);

-- Xác nhận chốt của TỪNG đơn vị. `snapshot` giữ CON SỐ tại lúc bấm xác nhận — để sau này còn đối
-- chiếu "số đã chốt" với "số hiện tại" (chuyên viên sửa hộ là số sẽ lệch, và phải nhìn ra được).
CREATE TABLE IF NOT EXISTS unit_data_lock (
    id        bigserial PRIMARY KEY,
    round_id  bigint NOT NULL,
    company   text NOT NULL,
    locked_at timestamptz NOT NULL DEFAULT now(),
    locked_by text,                      -- tài khoản bấm xác nhận (đơn vị) hoặc quản trị khoá hộ
    by_admin  boolean NOT NULL DEFAULT false,
    snapshot  jsonb
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_unit_data_lock ON unit_data_lock (round_id, company);
CREATE INDEX IF NOT EXISTS ix_unit_data_lock_company ON unit_data_lock (company);

-- HỖ TRỢ & THÔNG BÁO giữa Tập đoàn và đơn vị thành viên (chốt 29/08/2026).
-- ⚠ CÁCH LY: mỗi LUỒNG thuộc về ĐÚNG MỘT đơn vị. Tập đoàn gửi cho nhiều đơn vị = tạo NHIỀU luồng
-- (cùng `batch_id`), KHÔNG phải một luồng nhiều người nhận. Nhờ vậy "đơn vị này không thấy tin và
-- phản hồi của đơn vị kia" là tính chất của DỮ LIỆU, không phải của giao diện — không có truy vấn
-- nào lỡ tay là lộ chéo được.
CREATE TABLE IF NOT EXISTS support_thread (
    id          bigserial PRIMARY KEY,
    company     text NOT NULL,          -- đơn vị của luồng (khớp member_unit) — khoá cách ly
    kind        text NOT NULL,          -- request (đơn vị gửi lên) | announce (Tập đoàn gửi xuống) | reminder | alert (cảnh báo tự động)
    subject     text NOT NULL,
    status      text NOT NULL DEFAULT 'open',   -- open | closed
    batch_id    text,                   -- gom các luồng sinh ra từ CÙNG một lần gửi (thông báo nhiều đơn vị)
    reminder_id bigint,                 -- luồng do lịch nhắc nào sinh ra (NULL = người gửi tay)
    created_by  text,
    created_at  timestamptz NOT NULL DEFAULT now(),
    last_at     timestamptz NOT NULL DEFAULT now(),  -- mốc tin cuối (sắp xếp hộp thư)
    last_side   text NOT NULL DEFAULT 'hq',          -- hq | unit — bên nhắn cuối cùng
    hq_read_at   timestamptz,           -- Tập đoàn đã đọc tới lúc nào (NULL = chưa đọc)
    unit_read_at timestamptz            -- Đơn vị đã đọc tới lúc nào
);
CREATE INDEX IF NOT EXISTS ix_support_thread_company ON support_thread (company, last_at DESC);
CREATE INDEX IF NOT EXISTS ix_support_thread_last ON support_thread (kind, last_at DESC);
CREATE INDEX IF NOT EXISTS ix_support_thread_batch ON support_thread (batch_id);

-- Từng tin trong luồng: tin ĐẦU là nội dung gốc, các tin sau là phản hồi qua lại.
CREATE TABLE IF NOT EXISTS support_message (
    id          bigserial PRIMARY KEY,
    thread_id   bigint NOT NULL,
    side        text NOT NULL,          -- hq | unit — bên gửi
    author      text NOT NULL,          -- username ('system' = lịch nhắc tự phát)
    author_name text,
    body        text NOT NULL DEFAULT '',
    files       jsonb NOT NULL DEFAULT '[]'::jsonb,  -- đính kèm: [{file, filename, size}]
    created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_support_message_thread ON support_message (thread_id, id);

-- NHẮC LỊCH: đến giờ thì tự phát thông báo tới các đơn vị đã chọn (đi đúng đường thông báo ở trên,
-- nên cũng gửi email và cũng cách ly theo đơn vị). `next_at` là mốc phát KẾ TIẾP — job so mốc này
-- với hiện tại, phát xong mới dời sang chu kỳ sau; lưu mốc thay vì tính lại từ lịch để lỡ giờ
-- (máy chủ tắt/deploy) vẫn phát bù đúng một lần.
CREATE TABLE IF NOT EXISTS support_reminder (
    id           bigserial PRIMARY KEY,
    title        text NOT NULL,
    body         text NOT NULL DEFAULT '',
    files        jsonb NOT NULL DEFAULT '[]'::jsonb,
    scope        text NOT NULL DEFAULT 'all',   -- all | units | region
    units        jsonb NOT NULL DEFAULT '[]'::jsonb,
    region       text,
    repeat_rule  text NOT NULL DEFAULT 'once',  -- once | daily | weekly | monthly
    next_at      timestamptz NOT NULL,
    enabled      boolean NOT NULL DEFAULT true,
    last_sent_at timestamptz,
    created_by   text,
    created_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_support_reminder_next ON support_reminder (enabled, next_at);

-- ĐỀ NGHỊ SỬA SỐ LIỆU QUÁ KHỨ (chốt 15/09/2026): đơn vị bị cửa sổ sửa / chốt số liệu chặn thì gửi
-- nội dung muốn sửa kèm lý do; số liệu thật CHỈ đổi khi người có quyền `edit_request` duyệt.
-- `payload` = đúng body của API ghi gốc (đã chuẩn hoá) · `before` = ảnh chụp bản ghi LÚC GỬI để
-- người duyệt so trước/sau · `unlocked` = các đợt chốt đã gỡ khi duyệt (đơn vị phải chốt lại).
-- Mỗi (đơn vị, bản ghi) chỉ có MỘT đề nghị đang chờ — gửi lại là ghi đè (index UNIQUE một phần).
CREATE TABLE IF NOT EXISTS edit_request (
    id           bigserial PRIMARY KEY,
    company      text NOT NULL,
    op           text NOT NULL,          -- daily_report | daily_move | demand_save | demand_delete | contract_save | contract_delete | contract_delivery_type
    target_key   text NOT NULL,          -- khoá bản ghi bị sửa (chống trùng đề nghị đang chờ)
    title        text NOT NULL DEFAULT '',
    dates        jsonb NOT NULL DEFAULT '[]'::jsonb,   -- ngày số liệu bị ảnh hưởng
    payload      jsonb NOT NULL,
    before       jsonb,
    reason       text NOT NULL DEFAULT '',
    blocked      jsonb NOT NULL DEFAULT '[]'::jsonb,   -- câu báo chặn lúc gửi
    status       text NOT NULL DEFAULT 'pending',      -- pending | approved | rejected | cancelled
    requested_by text NOT NULL,
    requested_at timestamptz NOT NULL DEFAULT now(),
    updated_at   timestamptz NOT NULL DEFAULT now(),
    reviewed_by  text,
    reviewed_at  timestamptz,
    review_note  text,
    unlocked     jsonb
);
CREATE INDEX IF NOT EXISTS ix_edit_request_status ON edit_request (status, requested_at DESC);
CREATE INDEX IF NOT EXISTS ix_edit_request_company ON edit_request (company, requested_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS ux_edit_request_pending ON edit_request (company, target_key)
    WHERE status = 'pending';

-- SNAPSHOT SỐ LIỆU TUẦN (chốt 24/09/2026): bản lưu CỐ ĐỊNH thu mua · tiêu thụ · tồn kho của TỪNG
-- đơn vị, chụp tự động khi hết hạn nhập của ngày Chủ nhật. Mỗi tuần MỘT dòng, không bao giờ ghi đè
-- (INSERT … ON CONFLICT DO NOTHING) — sửa số liệu sau lúc chụp không làm đổi bản lưu.
-- `purchase`/`consumption` = NGUYÊN kết quả `unit_period_report.period_report` của tuần (đủ cột để
-- xuất lại Excel) · `totals` = dòng Tổng cộng của từng biểu · `deadline_at` = hạn nhập lúc chụp.
CREATE TABLE IF NOT EXISTS unit_week_snapshot (
    week_start  date PRIMARY KEY,          -- Thứ Hai (ISO) của tuần
    week_end    date NOT NULL,             -- Chủ nhật
    purchase    jsonb NOT NULL,
    consumption jsonb NOT NULL,
    totals      jsonb NOT NULL,
    deadline_at timestamptz NOT NULL,
    taken_at    timestamptz NOT NULL DEFAULT now(),
    taken_by    text NOT NULL              -- 'job' = tự động · username = admin bấm "Chụp ngay"
);

-- Migration idempotent cho DB đã tồn tại (CREATE IF NOT EXISTS không thêm cột mới).
-- Job chạy theo NGÀY TRONG TUẦN (rỗng/NULL = chạy hằng ngày như trước). Vd 'fri' = tối thứ Sáu
-- cho job chốt tồn kho Tập đoàn theo tuần.
ALTER TABLE schedule_job ADD COLUMN IF NOT EXISTS day_of_week text;
ALTER TABLE vrg_floor_price ADD COLUMN IF NOT EXISTS title text;
ALTER TABLE vrg_floor_price ADD COLUMN IF NOT EXISTS dispatch_no text;
ALTER TABLE vrg_floor_price ADD COLUMN IF NOT EXISTS dispatch_summary text;
ALTER TABLE member_unit ADD COLUMN IF NOT EXISTS region text;
-- Quốc gia + loại tiền của đơn vị (đơn vị nước ngoài Lào/Campuchia cần tỷ giá khi thu mua).
ALTER TABLE member_unit ADD COLUMN IF NOT EXISTS country text NOT NULL DEFAULT 'VN';
ALTER TABLE member_unit ADD COLUMN IF NOT EXISTS currency text NOT NULL DEFAULT 'VND';
-- Đơn vị có nhà máy chế biến không (đơn vị KHÔNG có nhà máy mới nhập tồn kho nguyên liệu).
ALTER TABLE member_unit ADD COLUMN IF NOT EXISTS has_factory boolean NOT NULL DEFAULT true;
-- Đơn vị có được giao KẾ HOẠCH thu mua năm không — chỉ đơn vị bật cờ này mới hiện ở "Kế hoạch năm".
ALTER TABLE member_unit ADD COLUMN IF NOT EXISTS has_purchase_plan boolean NOT NULL DEFAULT true;
-- TỰ ĐỘNG LẤY GIÁ MỦ NGUYÊN LIỆU TỪ ĐƠN VỊ (chốt 20/08/2026): đơn vị này được chuyên viên
-- chọn cho phép số tự khai (`fact_price` lớp `vrg_unit`) chảy thẳng sang lớp chuyên viên (`vrg`)
-- mỗi khi đơn vị thêm/sửa/xoá giá. Mặc định FALSE — bật từng đơn vị, không bật cả loạt.
ALTER TABLE member_unit ADD COLUMN IF NOT EXISTS auto_price_sync boolean NOT NULL DEFAULT false;
-- SÁP NHẬP ĐƠN VỊ (chốt 24/08/2026): đơn vị này đã sáp nhập vào đơn vị nào, kể từ ngày nào.
-- ⚠ CỐ Ý KHÔNG đụng tới một dòng số liệu nào — khác hẳn ĐỔI TÊN (`rename_unit` ghi đè `company`
-- ở mọi bảng). Đổi tên = một pháp nhân đổi tên; sáp nhập = HAI pháp nhân, lịch sử phải tách thì
-- mới trả lời được câu "đơn vị này lúc chưa sáp nhập làm được bao nhiêu". Số liệu cũ giữ nguyên
-- `company` = tên đơn vị cũ; báo cáo gộp bằng cách CỘNG theo dòng đời (xem `member_unit_repo`).
-- Nhờ vậy gỡ sáp nhập chỉ là xoá 2 cột này, không phải khôi phục dữ liệu.
ALTER TABLE member_unit ADD COLUMN IF NOT EXISTS merged_into text;
ALTER TABLE member_unit ADD COLUMN IF NOT EXISTS merged_at date;
-- Cây công ty MẸ – CON (chốt 30/07/2026): tên đơn vị mẹ của đơn vị này (rỗng = không thuộc cây nào).
-- Đơn vị con vẫn được chuyển TIÊU THỤ NỘI BỘ cho BẤT KỲ đơn vị thành viên nào (không giới hạn trong
-- cây); cột này để báo cáo cấp Tập đoàn biết quan hệ giữa các đơn vị.
ALTER TABLE member_unit ADD COLUMN IF NOT EXISTS parent_company text;
-- Số liệu năm nhập 1 lần (không theo ngày): tổng SL đã ký HĐ dài hạn của năm.
ALTER TABLE unit_purchase_plan ADD COLUMN IF NOT EXISTS signed_lt_tonnes double precision;
-- HÀNG CÓ CHỨNG CHỈ + PREMIUM (chốt 26/08/2026) — khai ở CẤP HỢP ĐỒNG cho cả hợp đồng gốc
-- (`master_contract`) lẫn hợp đồng bán (`sales_contract`):
--   `certs`       jsonb  danh sách chứng chỉ đã chọn (PEFC · EUDR · VRG GREEN) — chọn nhiều được
--   `premium`     số tiền cộng thêm cho hàng có chứng chỉ; NULL = hợp đồng không có premium
--   `premium_ccy` USD | VND (chỉ có nghĩa khi `premium` khác NULL)
-- ⚠ Premium KHÔNG tự cộng vào đơn giá/doanh thu — xem `services/contract_certs.py`.
ALTER TABLE master_contract ADD COLUMN IF NOT EXISTS certs jsonb NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE master_contract ADD COLUMN IF NOT EXISTS premium double precision;
ALTER TABLE master_contract ADD COLUMN IF NOT EXISTS premium_ccy text;
ALTER TABLE sales_contract ADD COLUMN IF NOT EXISTS certs jsonb NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE sales_contract ADD COLUMN IF NOT EXISTS premium double precision;
ALTER TABLE sales_contract ADD COLUMN IF NOT EXISTS premium_ccy text;
ALTER TABLE unit_purchase_plan ADD COLUMN IF NOT EXISTS carry_lt_tonnes double precision;
ALTER TABLE unit_purchase_plan ADD COLUMN IF NOT EXISTS carry_spot_tonnes double precision;
-- Kế hoạch TIÊU THỤ cho hợp đồng chuyến (chốt 03/08/2026) — chỉ để đối chiếu % thực hiện,
-- KHÔNG bật/tắt màn nào (khác kế hoạch thu mua: cái đó là công tắc của màn Thu mua).
ALTER TABLE unit_purchase_plan ADD COLUMN IF NOT EXISTS plan_sales_spot_tonnes double precision;
-- Kế hoạch DOANH THU năm (chốt 24/08/2026) — đơn vị **TỶ ĐỒNG**, cùng đơn vị với `revenue_ty` của
-- báo cáo kỳ nên "% thực hiện" là phép chia cùng đơn vị, không phải quy đổi (chỗ dễ sai nhất).
ALTER TABLE unit_purchase_plan ADD COLUMN IF NOT EXISTS plan_revenue_ty double precision;
-- Kế hoạch KHAI THÁC năm (chốt 24/09/2026) — TẤN, mủ từ vườn cây của CHÍNH đơn vị (khác thu mua =
-- mua của dân). NULL = chưa khai. Chưa có số thực hiện khai thác ⇒ chỉ lưu/hiện, không tính %.
ALTER TABLE unit_purchase_plan ADD COLUMN IF NOT EXISTS plan_exploit_tonnes double precision;
-- Kế hoạch HÀNG HÓA cao su năm (chốt 29/09/2026) — TẤN thành phẩm MUA NGOÀI để bán lại (Tân Biên:
-- khai thác 3.500 + thu mua 1.000 + hàng hóa 5.000). Không gộp vào `plan_tonnes`: chỉ tiêu thu mua
-- của Ban TTKD chỉ tính mủ nguyên liệu. NULL = chưa khai.
ALTER TABLE unit_purchase_plan ADD COLUMN IF NOT EXISTS plan_goods_tonnes double precision;
-- Hợp đồng tồn kho: đính kèm NHIỀU file. Cột file/filename cũ giữ nguyên = file ĐẦU danh sách.
ALTER TABLE unit_stock_contract ADD COLUMN IF NOT EXISTS files jsonb NOT NULL DEFAULT '[]'::jsonb;
-- Đã được script chuyển sang bảng hợp đồng 2 cấp `sales_contract` chưa. Bản ghi CŨ vẫn giữ nguyên
-- để tra cứu, nhưng khối 3 phải BỎ QUA nó — nếu không sản lượng chưa giao bị đếm hai lần.
ALTER TABLE unit_stock_contract ADD COLUMN IF NOT EXISTS migrated boolean NOT NULL DEFAULT false;
-- Ngày bắt đầu của đợt giao (chốt 02/08/2026): hàng của đợt nằm ở "đã ký HĐ chưa giao" từ ngày này
-- đến HẾT NGÀY TRƯỚC ngày giao. Không có ngày bắt đầu = đợt chưa mở, KHÔNG tính vào khối 3.
ALTER TABLE sales_contract ADD COLUMN IF NOT EXISTS start_date date;
-- Loại HỢP ĐỒNG (dài hạn / chuyến) — chỉ tiêu của mẫu báo cáo, KHÁC loại GIAO (1 lần / nhiều lần).
-- Để NULL, không đặt mặc định: đoán bừa một loại làm sai luôn chỉ tiêu "HĐ dài hạn / HĐ chuyến".
ALTER TABLE sales_contract ADD COLUMN IF NOT EXISTS contract_type text;
-- HOÁ ĐƠN của MỘT ĐỢT GIAO (chốt 05/08/2026): số hoá đơn + danh sách file scan. Trước đây hoá đơn
-- dồn chung vào `payment_docs` nên không tra cứu được theo số hoá đơn.
ALTER TABLE sales_contract ADD COLUMN IF NOT EXISTS invoice_no text;
ALTER TABLE sales_contract ADD COLUMN IF NOT EXISTS invoice_docs jsonb NOT NULL DEFAULT '[]'::jsonb;
-- HOÀN THÀNH HỢP ĐỒNG (chốt 05/08/2026): sản lượng thực giao được phép lệch so với hợp đồng ký,
-- nên phải có thao tác CHỐT để phần chênh còn lại rời khỏi "đã ký HĐ chưa giao". Đặt ở hợp đồng
-- mẹ; NULL = đang thực hiện.
ALTER TABLE sales_contract ADD COLUMN IF NOT EXISTS completed_at date;
-- HỢP ĐỒNG MẸ của phụ lục (chốt 21/08/2026): NULL = hợp đồng không thuộc hồ sơ nào (mọi bản ghi
-- cũ). Khác NULL = hợp đồng này nằm trong hồ sơ đó. ⚠ CHỈ là liên kết — hợp đồng vẫn giữ khách
-- hàng, loại hợp đồng và mọi số liệu của chính nó. Chỉ đặt ở hợp đồng, đợt giao luôn NULL.
ALTER TABLE sales_contract ADD COLUMN IF NOT EXISTS master_id bigint;
CREATE INDEX IF NOT EXISTS ix_sales_contract_master ON sales_contract (master_id);
-- Nâng bản ghi cũ (1 file ở cột phẳng) lên danh sách. Idempotent: chỉ chạm dòng chưa có danh sách.
UPDATE unit_stock_contract SET files = jsonb_build_array(
         jsonb_build_object('file', file, 'filename', COALESCE(filename, file)))
 WHERE files = '[]'::jsonb AND file IS NOT NULL AND file <> '';
ALTER TABLE app_user ADD COLUMN IF NOT EXISTS permissions jsonb NOT NULL DEFAULT '[]'::jsonb;
-- Email nhận thông báo (Hỗ trợ & Thông báo). Trống → lấy chính username nếu username là email.
ALTER TABLE app_user ADD COLUMN IF NOT EXISTS email text;
-- Các đơn vị gắn với tài khoản (chỉ dùng cho role=member) — 1 tài khoản có thể gán NHIỀU đơn vị.
ALTER TABLE app_user ADD COLUMN IF NOT EXISTS member_units jsonb NOT NULL DEFAULT '[]'::jsonb;
-- Migrate cột đơn cũ member_unit → mảng member_units rồi bỏ cột cũ (idempotent).
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.columns
             WHERE table_schema = current_schema() AND table_name = 'app_user'
               AND column_name = 'member_unit') THEN
    UPDATE app_user SET member_units = jsonb_build_array(member_unit)
      WHERE member_unit IS NOT NULL AND member_unit <> ''
        AND (member_units IS NULL OR member_units = '[]'::jsonb);
    ALTER TABLE app_user DROP COLUMN member_unit;
  END IF;
END $$;
-- Nhu cầu thị trường RÚT GỌN (chốt 17/09/2026): thời gian giao + kết quả thành Ô CHỮ; bỏ tình trạng,
-- số hợp đồng, ngày ký, giá tạm tính, cặp ngày giao. Gộp giá trị cũ thành chữ rồi bỏ cột (idempotent).
ALTER TABLE market_demand_item ADD COLUMN IF NOT EXISTS delivery_time text NOT NULL DEFAULT '';
ALTER TABLE market_demand_item ADD COLUMN IF NOT EXISTS result text NOT NULL DEFAULT '';
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.columns
             WHERE table_schema = current_schema() AND table_name = 'market_demand_item'
               AND column_name = 'status') THEN
    UPDATE market_demand_item SET
      delivery_time = CASE
        WHEN delivery_from IS NULL AND delivery_to IS NULL THEN delivery_time
        WHEN delivery_from IS NULL THEN 'Đến ' || to_char(delivery_to, 'DD/MM/YYYY')
        WHEN delivery_to IS NULL THEN 'Từ ' || to_char(delivery_from, 'DD/MM/YYYY')
        WHEN delivery_from = delivery_to THEN to_char(delivery_to, 'DD/MM/YYYY')
        ELSE to_char(delivery_from, 'DD/MM/YYYY') || ' – ' || to_char(delivery_to, 'DD/MM/YYYY')
      END,
      result = CASE status
        WHEN 'signed' THEN 'Đã ký hợp đồng số ' || contract_no
                           || COALESCE(' ngày ' || to_char(contract_date, 'DD/MM/YYYY'), '')
        WHEN 'failed' THEN 'Không thành'
        ELSE result
      END,
      note = CASE WHEN price_provisional
                  THEN 'Giá tạm tính' || CASE WHEN note <> '' THEN chr(10) || note ELSE '' END
                  ELSE note END;
    ALTER TABLE market_demand_item DROP COLUMN price_provisional, DROP COLUMN delivery_from,
      DROP COLUMN delivery_to, DROP COLUMN status, DROP COLUMN contract_no, DROP COLUMN contract_date;
  END IF;
END $$;
-- Đổi tên quyền cũ 'corridor_info' → 'market_demand' (Thông tin hành lang → Nhu cầu thị trường).
UPDATE app_user SET permissions = REPLACE(permissions::text, 'corridor_info', 'market_demand')::jsonb
    WHERE permissions::text LIKE '%corridor_info%';
-- Báo cáo tiêu thụ–tồn kho chuyển từ TUẦN → NGÀY: gỡ bảng tuần cũ (chưa có dữ liệu thật) + đổi tên quyền.
DROP TABLE IF EXISTS unit_weekly_report;
UPDATE app_user SET permissions = REPLACE(permissions::text, 'unit_weekly', 'unit_daily')::jsonb
    WHERE permissions::text LIKE '%unit_weekly%';
-- Đổi tên chủng loại giá sàn cho khớp báo cáo (idempotent).
UPDATE vrg_floor_price SET grade = 'SVR 10 / CSR 10' WHERE grade = 'SVR 10';
UPDATE vrg_floor_price SET grade = 'SVR 20 / CSR 20' WHERE grade = 'SVR 20';
UPDATE vrg_floor_price SET grade = 'Skim Block' WHERE grade = 'SkimBlock';
"""

# Hypertable tách riêng: cần extension timescaledb; nếu thiếu, bảng vẫn dùng được.
_DDL_HYPERTABLE = (
    "SELECT create_hypertable('fact_price', 'as_of', "
    "if_not_exists => TRUE, migrate_data => TRUE);"
)


def _normalized_url() -> str:
    """Ép driver psycopg3 cho SQLAlchemy."""
    url = settings.database_url
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def get_engine() -> Engine:
    global _engine, _Session
    if _engine is None:
        _engine = create_engine(
            _normalized_url(),
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=5,
            future=True,
        )
        _Session = sessionmaker(bind=_engine, future=True)
    return _engine


def ensure_schema() -> None:
    """Tạo bảng + hypertable nếu chưa có (idempotent). Gọi trước khi ghi."""
    global _schema_ready
    if _schema_ready:
        return
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text(_DDL_TABLES))
    # Hypertable phải ở TRANSACTION RIÊNG: thiếu extension timescaledb thì lệnh này lỗi, mà một
    # lệnh lỗi làm hỏng cả transaction đang mở — bắt exception rồi commit tiếp chỉ đổi commit thành
    # rollback, nuốt luôn phần CREATE TABLE ở trên. Triệu chứng: `ensure_schema()` chạy êm và báo
    # xong, nhưng DB không có bảng nào (đúng cảnh Postgres thường dùng để chạy test).
    try:
        with engine.begin() as conn:
            conn.execute(text(_DDL_HYPERTABLE))
    except Exception:  # noqa: BLE001 - thiếu timescaledb thì bỏ qua, bảng thường vẫn chạy
        pass
    _schema_ready = True


@contextmanager
def session_scope() -> Iterator[Session]:
    """Session có commit/rollback tự động."""
    get_engine()
    assert _Session is not None
    db = _Session()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def db_healthy() -> bool:
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:  # noqa: BLE001
        return False
