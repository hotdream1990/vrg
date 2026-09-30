-- =============================================================================
-- GIẢ LẬP AVEVA/Wonderware Historian cho VRG — CHỈ DÙNG PHÁT TRIỂN CỤC BỘ.
-- Chạy lại được nhiều lần (idempotent): dựng lại bảng/view/linked server từ đầu, số liệu sinh
-- xác định (cùng kết quả mỗi lần). Biến sqlcmd bắt buộc: SCADA_RO_PASSWORD (do run.sh truyền -v).
-- =============================================================================
:on error exit
SET NOCOUNT ON;
GO

USE master;
GO
IF DB_ID(N'Runtime') IS NULL CREATE DATABASE Runtime;
GO

-- ---------------------------------------------------------------------------
-- 1. Login chỉ-đọc scada_ro (mật khẩu dev-only từ biến môi trường, xem README)
-- ---------------------------------------------------------------------------
IF NOT EXISTS (SELECT 1 FROM sys.server_principals WHERE name = N'scada_ro')
    CREATE LOGIN scada_ro WITH PASSWORD = N'$(SCADA_RO_PASSWORD)', DEFAULT_DATABASE = Runtime;
ELSE
    ALTER LOGIN scada_ro WITH PASSWORD = N'$(SCADA_RO_PASSWORD)', DEFAULT_DATABASE = Runtime;
GO

USE Runtime;
GO

-- ---------------------------------------------------------------------------
-- 2. Dọn đối tượng cũ (thứ tự phụ thuộc: view -> hàm -> bảng)
-- ---------------------------------------------------------------------------
IF OBJECT_ID(N'dbo.WideHistory', N'V') IS NOT NULL DROP VIEW dbo.WideHistory;
IF OBJECT_ID(N'dbo.fn_WideHistoryMinute', N'IF') IS NOT NULL DROP FUNCTION dbo.fn_WideHistoryMinute;
IF OBJECT_ID(N'dbo.HistorianHourly', N'U') IS NOT NULL DROP TABLE dbo.HistorianHourly;
GO

-- ---------------------------------------------------------------------------
-- 3. Bảng nền theo GIỜ: mỗi dòng = số đọc của bộ đếm LŨY KẾ tại đúng mốc giờ
-- ---------------------------------------------------------------------------
CREATE TABLE dbo.HistorianHourly (
    [DateTime]         datetime2(3) NOT NULL PRIMARY KEY,
    PM_EnergyReal0     float NULL,   -- bit 48..63 của Wh
    PM_EnergyReal1     float NULL,   -- bit 32..47
    PM_EnergyReal2     float NULL,   -- bit 16..31
    PM_EnergyReal3     float NULL,   -- bit 0..15, lưu dạng int16 CÓ DẤU (PLC đọc thành số âm khi > 32767)
    Water_TotalVolume  float NULL,   -- m3 lũy kế
    Packing_BaleCount  float NULL    -- số bành lũy kế
);
GO

-- Sinh dữ liệu: 2026-06-01 00:00 .. 2027-06-01 00:00 (8761 mốc giờ)
-- Mỗi ngày có tổng tiêu thụ riêng (hash MD5 theo chỉ số ngày/giờ -> xác định, không phụ thuộc lần chạy); trong ngày chia theo trọng số giờ.
-- Neo lũy kế tại 2026-09-01 00:00: điện 180.000 kWh · nước 7.600 m3 · bành 8.600.
-- Trước 01/09 là mùa thấp điểm (x0,15) để bộ đếm ở 01/06 vẫn dương.
DECLARE @d0 date = '20260601', @anchor_day int = DATEDIFF(day, '20260601', '20260901');

;WITH nums AS (
    SELECT TOP (8761) CAST(ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) - 1 AS int) AS n
    FROM sys.all_objects a CROSS JOIN sys.all_objects b
),
day_raw AS (   -- 366 ngày, mỗi ngày 5 số ngẫu nhiên xác định trong [0,1)
    SELECT n AS d, DATEADD(day, n, @d0) AS dt,
        CONVERT(int, SUBSTRING(HASHBYTES('MD5', CONCAT(n, '-', 1)), 1, 3)) / 16777216.0 AS r1,
        CONVERT(int, SUBSTRING(HASHBYTES('MD5', CONCAT(n, '-', 2)), 1, 3)) / 16777216.0 AS r2,
        CONVERT(int, SUBSTRING(HASHBYTES('MD5', CONCAT(n, '-', 3)), 1, 3)) / 16777216.0 AS r3,
        CONVERT(int, SUBSTRING(HASHBYTES('MD5', CONCAT(n, '-', 4)), 1, 3)) / 16777216.0 AS r4,
        CONVERT(int, SUBSTRING(HASHBYTES('MD5', CONCAT(n, '-', 5)), 1, 3)) / 16777216.0 AS r5
    FROM nums WHERE n <= 365
),
day_tot AS (   -- tổng tiêu thụ của từng ngày
    SELECT r.d, x.rest, s.season,
        s.season * ROUND(1000 * CASE WHEN x.rest = 1 THEN 30 + 50 * r.r3 ELSE 2000 + 1100 * r.r3 END, 0) AS e_wh,
        s.season * CASE WHEN x.rest = 1 THEN 15 + 25 * r.r4 ELSE 150 + 80 * r.r4 END           AS w_m3,
        s.season * CASE WHEN x.rest = 1 THEN 0 ELSE 400 + FLOOR(191 * r.r5) END                AS bale
    FROM day_raw r
    CROSS APPLY (SELECT CASE WHEN r.dt < '20260901' THEN 0.15 ELSE 1.0 END AS season) s
    -- nghỉ: Chủ nhật (1900-01-07 là Chủ nhật) 50% hoặc ngẫu nhiên 2% ngày thường
    CROSS APPLY (SELECT CASE WHEN (DATEDIFF(day, '19000107', r.dt) % 7 = 0 AND r.r1 < 0.5) OR r.r2 < 0.02
                             THEN 1 ELSE 0 END AS rest) x
),
day_base AS (  -- bộ đếm lúc 00:00 mỗi ngày = tổng các ngày trước, dịch để khớp mốc neo
    SELECT d, e_wh, w_m3, bale,
        c.ce - MAX(CASE WHEN d = @anchor_day THEN c.ce END) OVER () + 180000000.0 AS be,
        c.cw - MAX(CASE WHEN d = @anchor_day THEN c.cw END) OVER () + 7600.0      AS bw,
        c.cb - MAX(CASE WHEN d = @anchor_day THEN c.cb END) OVER () + 8600.0      AS bb
    FROM (SELECT *,
            COALESCE(SUM(e_wh)  OVER (ORDER BY d ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING), 0) AS ce,
            COALESCE(SUM(w_m3)  OVER (ORDER BY d ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING), 0) AS cw,
            COALESCE(SUM(bale)  OVER (ORDER BY d ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING), 0) AS cb
          FROM day_tot) c
),
hr AS (        -- trọng số theo giờ: điện/nước chủ yếu 6-22h, bành chỉ 7-21h
    SELECT n, n / 24 AS d, n % 24 AS h,
        CASE WHEN n % 24 BETWEEN 6 AND 22 THEN 0.8 + 0.4 * re ELSE 0.06 + 0.04 * re END AS we,
        CASE WHEN n % 24 BETWEEN 6 AND 22 THEN 0.8 + 0.4 * rw ELSE 0.06 + 0.04 * rw END AS ww,
        CASE WHEN n % 24 BETWEEN 7 AND 21 THEN 0.8 + 0.4 * rb ELSE 0 END               AS wb
    FROM (SELECT n,
            CONVERT(int, SUBSTRING(HASHBYTES('MD5', CONCAT(n, '-', 11)), 1, 3)) / 16777216.0 AS re,
            CONVERT(int, SUBSTRING(HASHBYTES('MD5', CONCAT(n, '-', 12)), 1, 3)) / 16777216.0 AS rw,
            CONVERT(int, SUBSTRING(HASHBYTES('MD5', CONCAT(n, '-', 13)), 1, 3)) / 16777216.0 AS rb
          FROM nums) q
),
frac AS (      -- tỉ lệ đã tiêu thụ trong ngày tại đầu giờ (0 lúc 00:00, <1 lúc 23:00)
    SELECT n, d,
        COALESCE(SUM(we) OVER (PARTITION BY d ORDER BY h ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING), 0) / SUM(we) OVER (PARTITION BY d) AS fe,
        COALESCE(SUM(ww) OVER (PARTITION BY d ORDER BY h ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING), 0) / SUM(ww) OVER (PARTITION BY d) AS fw,
        COALESCE(SUM(wb) OVER (PARTITION BY d ORDER BY h ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING), 0) / NULLIF(SUM(wb) OVER (PARTITION BY d), 0) AS fb
    FROM hr
),
val AS (
    SELECT f.n,
        CAST(ROUND(b.be + b.e_wh * f.fe, 0) AS bigint)             AS wh,       -- Wh lũy kế (số nguyên)
        ROUND(b.bw + b.w_m3 * f.fw, 3)                             AS water,
        ROUND(b.bb + b.bale * COALESCE(f.fb, 0), 0)                AS bales
    FROM frac f JOIN day_base b ON b.d = f.d
)
INSERT dbo.HistorianHourly ([DateTime], PM_EnergyReal0, PM_EnergyReal1, PM_EnergyReal2, PM_EnergyReal3, Water_TotalVolume, Packing_BaleCount)
SELECT DATEADD(hour, v.n, CAST(@d0 AS datetime2(3))),
    v.wh / CAST(281474976710656 AS bigint),                                   -- R0 = Wh >> 48
    (v.wh / CAST(4294967296 AS bigint)) % 65536,                              -- R1 = (Wh >> 32) & 0xFFFF
    (v.wh / 65536) % 65536,                                   -- R2 = (Wh >> 16) & 0xFFFF
    CASE WHEN v.wh % 65536 > 32767 THEN v.wh % 65536 - 65536 ELSE v.wh % 65536 END,  -- R3 = int16 có dấu
    v.water, v.bales
FROM val v;

-- Bẫy dữ liệu để thử ứng dụng
UPDATE dbo.HistorianHourly SET Water_TotalVolume = NULL WHERE [DateTime] = '2026-09-12 00:00:00';                                 -- thiếu mốc 00:00 -> "partial"
UPDATE dbo.HistorianHourly SET Packing_BaleCount = NULL WHERE [DateTime] >= '2026-09-20' AND [DateTime] < '2026-09-21';          -- cả ngày -> "no_data"
GO

-- ---------------------------------------------------------------------------
-- 4. Hàm sinh mốc PHÚT cho ~20 phút gần nhất (nội suy giữa 2 mốc giờ kề, động theo GETDATE())
--    Nội suy trên Wh ghép lại rồi tách thanh ghi lại -> tránh sai khi R3 quay vòng.
-- ---------------------------------------------------------------------------
CREATE FUNCTION dbo.fn_WideHistoryMinute()
RETURNS TABLE
AS RETURN
(
    SELECT CAST(m.t AS datetime2(3)) AS [DateTime],
        CAST(w.wh / CAST(281474976710656 AS bigint) AS float)                                                        AS PM_EnergyReal0,
        CAST((w.wh / CAST(4294967296 AS bigint)) % 65536 AS float)                                                   AS PM_EnergyReal1,
        CAST((w.wh / 65536) % 65536 AS float)                                                        AS PM_EnergyReal2,
        CAST(CASE WHEN w.wh % 65536 > 32767 THEN w.wh % 65536 - 65536 ELSE w.wh % 65536 END AS float) AS PM_EnergyReal3,
        ROUND(a.Water_TotalVolume + (b.Water_TotalVolume - a.Water_TotalVolume) * m.f, 3)            AS Water_TotalVolume,
        ROUND(a.Packing_BaleCount + (b.Packing_BaleCount - a.Packing_BaleCount) * m.f, 0)            AS Packing_BaleCount
    FROM (SELECT t, DATEADD(hour, DATEDIFF(hour, 0, t), 0) AS lo, DATEDIFF(second, DATEADD(hour, DATEDIFF(hour, 0, t), 0), t) / 3600.0 AS f
          FROM (SELECT DATEADD(minute, DATEDIFF(minute, 0, GETDATE()) - v.n, 0) AS t
                FROM (VALUES (19),(18),(17),(16),(15),(14),(13),(12),(11),(10),(9),(8),(7),(6),(5),(4),(3),(2),(1),(0)) v(n)) q) m
    JOIN dbo.HistorianHourly a ON a.[DateTime] = m.lo
    JOIN dbo.HistorianHourly b ON b.[DateTime] = DATEADD(hour, 1, m.lo)
    CROSS APPLY (SELECT
        (CAST(a.PM_EnergyReal0 AS bigint) * CAST(281474976710656 AS bigint) + CAST(a.PM_EnergyReal1 AS bigint) * CAST(4294967296 AS bigint)
          + CAST(a.PM_EnergyReal2 AS bigint) * 65536 + CAST(a.PM_EnergyReal3 AS bigint) + CASE WHEN a.PM_EnergyReal3 < 0 THEN 65536 ELSE 0 END) AS wa,
        (CAST(b.PM_EnergyReal0 AS bigint) * CAST(281474976710656 AS bigint) + CAST(b.PM_EnergyReal1 AS bigint) * CAST(4294967296 AS bigint)
          + CAST(b.PM_EnergyReal2 AS bigint) * 65536 + CAST(b.PM_EnergyReal3 AS bigint) + CASE WHEN b.PM_EnergyReal3 < 0 THEN 65536 ELSE 0 END) AS wb) e
    CROSS APPLY (SELECT CAST(ROUND(e.wa + (e.wb - e.wa) * m.f, 0) AS bigint) AS wh) w
);
GO

-- ---------------------------------------------------------------------------
-- 5. View WideHistory: giống cấu trúc Historian thật. Chỉ trả dòng <= GETDATE().
--    Nhánh 1 (wwResolution = 3600000): mốc tròn giờ. Nhánh 2 (wwResolution = 60000): mốc phút gần nhất.
-- ---------------------------------------------------------------------------
CREATE VIEW dbo.WideHistory
AS
SELECT h.[DateTime], h.PM_EnergyReal0, h.PM_EnergyReal1, h.PM_EnergyReal2, h.PM_EnergyReal3,
    h.Water_TotalVolume, h.Packing_BaleCount,
    CAST(N'Cyclic' AS nvarchar(20)) AS wwRetrievalMode, CAST(3600000 AS int) AS wwResolution,
    CAST(NULL AS int) AS wwCycleCount, CAST(N'Extended' AS nvarchar(20)) AS wwQualityRule,
    CAST(N'Latest' AS nvarchar(20)) AS wwVersion
FROM dbo.HistorianHourly h
WHERE h.[DateTime] <= GETDATE()
UNION ALL
SELECT m.[DateTime], m.PM_EnergyReal0, m.PM_EnergyReal1, m.PM_EnergyReal2, m.PM_EnergyReal3,
    m.Water_TotalVolume, m.Packing_BaleCount,
    CAST(N'Cyclic' AS nvarchar(20)), CAST(60000 AS int), CAST(NULL AS int),
    CAST(N'Extended' AS nvarchar(20)), CAST(N'Latest' AS nvarchar(20))
FROM dbo.fn_WideHistoryMinute() m
WHERE m.[DateTime] <= GETDATE();
GO

-- ---------------------------------------------------------------------------
-- 6. Quyền: chỉ SELECT trên view (chuỗi sở hữu dbo -> bảng/hàm nền không cần cấp thêm)
-- ---------------------------------------------------------------------------
IF USER_ID(N'scada_ro') IS NULL CREATE USER scada_ro FOR LOGIN scada_ro WITH DEFAULT_SCHEMA = dbo;
ELSE ALTER USER scada_ro WITH LOGIN = scada_ro, DEFAULT_SCHEMA = dbo;
GRANT SELECT ON dbo.WideHistory TO scada_ro;
GO

-- ---------------------------------------------------------------------------
-- 7. Linked server loopback INSQL -> chính instance này
--    Trên SQL Server Linux CHỈ loại "SQL Server" dùng được cho login thường: kiểu OLE DB tường minh
--    (@provider = MSOLEDBSQL, có @catalog) chạy được với sysadmin nhưng login không-sysadmin
--    bị Msg 7416 "no login-mapping" dù đã ánh xạ. Kiểu "SQL Server" không cho khai @catalog, nên
--    CSDL đích do default database của login gọi quyết định (scada_ro -> Runtime).
-- ---------------------------------------------------------------------------
USE master;
GO
IF EXISTS (SELECT 1 FROM sys.servers WHERE name = N'INSQL')
    EXEC sp_dropserver @server = N'INSQL', @droplogins = 'droplogins';
EXEC sp_addlinkedserver @server = N'INSQL', @srvproduct = N'SQL Server';
EXEC sp_setnetname @server = N'INSQL', @netname = N'localhost';         -- trỏ về chính instance (cổng 1433 trong container)
EXEC sp_serveroption N'INSQL', N'data access', N'true';
-- Mọi login dùng CHÍNH quyền của mình ("self") -> OPENQUERY chạy với quyền của người gọi.
IF NOT EXISTS (SELECT 1 FROM sys.linked_logins l JOIN sys.servers s ON s.server_id = l.server_id
               WHERE s.name = N'INSQL' AND l.local_principal_id = 0 AND l.uses_self_credential = 1)
    EXEC sp_addlinkedsrvlogin @rmtsrvname = N'INSQL', @useself = N'TRUE', @locallogin = NULL;
GO
PRINT 'init.sql: xong (Runtime + WideHistory + INSQL + scada_ro).';
GO
