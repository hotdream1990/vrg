# Báo cáo: SCADA / Historian giả lập (nhánh C)

Ngày: 30/09/2026 · Thư mục: `/Volumes/Work/biz-project/VRG/scripts/scada-fake-historian/` (file mới, chưa commit)

## Kết quả
Container `vrg-scada-fake` **đang chạy** (healthy), cổng `127.0.0.1:14330`. `smoke_query.py` ĐẠT toàn bộ kiểm tra.

| Hạng mục | Giá trị |
|---|---|
| Image chạy được | `mcr.microsoft.com/mssql/server:2022-latest` (16.0.4295.3 CU27), `platform: linux/amd64` qua Rosetta. Không cần thử 2019 |
| Chạy | `scripts/scada-fake-historian/run.sh` (~15 giây khi đã có image; lần đầu kéo ~2,3 GB) |
| Kiểm | `uv run --with pymssql python scripts/scada-fake-historian/smoke_query.py` |
| Dừng / xoá | `docker compose -f .../docker-compose.yml stop` / `down` (chạy lại `run.sh` để dựng lại) |

## Kết quả smoke test (20:55 giờ VN)
- Truy vấn giờ `2026-09-01 -> GetDate()`: **717 dòng** (đúng số giờ), tăng dần, không lộ tương lai; chặn trên cố định `2026-10-01` cũng 717 dòng; tập con cột (Water, Bale) đủ dòng.
- Truy vấn "số mới nhất" (phút, 10 phút): **10 dòng** đủ điện/nước/bành, tăng dần. Đã mô phỏng qua ranh giới giờ/ngày (21:05, 23:59, 00:04) và mốc bẫy 09-12: bộ đếm vẫn không giảm.
- kWh ghép (có mask `& 0xFFFF`): **180.000,000** lúc 2026-09-01 00:00 -> **247.308,638** lúc 20:00 ngày 30/09 (mới nhất 247.418). Bộ đếm không giảm; R3 có mốc âm như thiết kế.
- Bẫy: 2026-09-12 00:00 nước = NULL; cả 24 mốc ngày 2026-09-20 bành = NULL.
- Đã thử: `down` rồi `run.sh` từ đầu, `docker restart`, chạy lại `run.sh` nhiều lần (idempotent), truy cập từ container khác qua `host.docker.internal:14330`.

## Mật khẩu dev (chỉ dev, đã ghi rõ trong compose/README)
- `sa`: `VrgScada!Dev2026` — ghi đè bằng `SCADA_FAKE_SA_PASSWORD`.
- `scada_ro`: `ScadaRo!Dev2026` — ghi đè bằng `SCADA_FAKE_RO_PASSWORD`.
- Mặc định nằm ở: `docker-compose.yml` (sa), `run.sh` (cả hai), `smoke_query.py` (scada_ro), README.

## Lệch so với yêu cầu / điều tích hợp cần biết
1. **Linked server `INSQL` là loại "SQL Server" loopback, không khai `@catalog`, không dùng MSOLEDBSQL tường minh.** Kiểu `@provider=MSOLEDBSQL` (có `@catalog='Runtime'`) chạy được với `sa` nhưng login không-sysadmin (kể cả `scada_ro` đã ánh xạ tường minh) luôn bị Msg 7416 "no login-mapping". Kiểu "SQL Server" + `sp_setnetname 'localhost'` chạy đúng với **`@useself='TRUE'`** (quyền của người gọi) như yêu cầu. Hệ quả: CSDL đích do default database của `scada_ro` (= `Runtime`) quyết định, nên `FROM WideHistory` (không tiền tố) chạy được với `scada_ro`; với `sa` phải viết `Runtime.dbo.WideHistory`. Ứng dụng dùng `scada_ro` nên không ảnh hưởng.
2. **Bẫy bành ngày 09-20 có tác dụng phụ**: mốc cuối của ngày 09-19 (09-20 00:00) cũng NULL — hệ quả tất yếu của "cả ngày 09-20 = NULL" khi ngày D dùng mốc D+1 00:00 làm chỉ số cuối. Đã ghi trong README; ứng dụng nên xử lý (ngày 09-19 sẽ thiếu chỉ số cuối).
3. Trước 01/09/2026 dùng hệ số mùa thấp điểm ×0,15 (điện/nước/bành) — vì để đầu 09 đạt 180.000 kWh / 7.600 m³ / 8.600 bành mà bộ đếm đầu 06/2026 vẫn dương thì tiêu thụ Jun–Aug không thể bằng mức 09. Từ 01/09 trở đi đúng dải yêu cầu. Tháng 09 có 4 ngày nghỉ (06, 13, 25, 27); ngày 20 là ngày làm việc (chỉ bành bị bẫy).
4. Số liệu sinh bằng hash MD5 theo chỉ số ngày/giờ (xác định, chạy lại cho kết quả y hệt). Ban đầu dùng `CHECKSUM` nhưng cho dãy tuyến tính trơn tru nên đã bỏ.
5. Mốc phút: chỉ nội suy tuyến tính giữa 2 mốc giờ kề (nội suy trên Wh ghép lại rồi tách thanh ghi, tránh sai khi R3 quay vòng); không mô phỏng Cyclic thật.

## Trở ngại đã gặp
- Msg 7416 với MSOLEDBSQL (xem mục 1) — mất nhiều thử nghiệm nhất.
- Literal > 2^31 trong T-SQL là numeric nên phép chia ra số thập phân (R0/R1 thành 6e-07…), đã ép `CAST(... AS bigint)`; smoke test có thêm kiểm tra "thanh ghi là số nguyên" để bắt lại lỗi này.
- Chưa có vấn đề Rosetta/crash với 2022-latest.

## File
`docker-compose.yml` · `init.sql` (idempotent, 208 dòng) · `run.sh` · `smoke_query.py` · `README.md` — không sửa file nào khác trong repo, không commit.
