# SCADA giả lập (AVEVA/Wonderware Historian) cho tính năng "Nhà máy thông minh"

SQL Server 2022 chạy trong Docker, giả lập đúng phần Historian mà ứng dụng VRG truy vấn:
linked server `INSQL` + view `WideHistory` (CSDL `Runtime`). **Chỉ dùng phát triển cục bộ** —
mật khẩu trong thư mục này là mật khẩu dev, không dùng cho hệ thống thật.

## Chạy

```bash
scripts/scada-fake-historian/run.sh      # up container -> chờ sẵn sàng -> nạp init.sql -> tự kiểm
uv run --with pymssql python scripts/scada-fake-historian/smoke_query.py   # kiểm đầy đủ 2 dạng truy vấn
```

Chạy lại `run.sh` bao nhiêu lần cũng được (dựng lại số liệu, kết quả y hệt). Image `linux/amd64`
chạy qua Rosetta trên Apple Silicon; lần đầu kéo image ~2,3 GB.

## Dừng / xoá

```bash
docker compose -f scripts/scada-fake-historian/docker-compose.yml stop   # dừng, giữ số liệu
docker compose -f scripts/scada-fake-historian/docker-compose.yml down   # xoá container (chạy run.sh để dựng lại)
```

## Khai vào màn "Cấu hình kết nối SCADA"

| Ô | Giá trị |
|---|---|
| Máy chủ | `localhost` (API chạy trong Docker: `host.docker.internal`) |
| Cổng | `14330` |
| Tài khoản | `scada_ro` |
| Mật khẩu | `ScadaRo!Dev2026` (mặc định dev; đổi bằng biến `SCADA_FAKE_RO_PASSWORD` trước khi chạy `run.sh`) |
| CSDL | `Runtime` |
| Linked server | `INSQL` |
| Tag điện | `PM_EnergyReal0`, `PM_EnergyReal1`, `PM_EnergyReal2`, `PM_EnergyReal3` |
| Tag nước | `Water_TotalVolume` |
| Tag số bành | `Packing_BaleCount` |

Tài khoản quản trị `sa`: mật khẩu `VrgScada!Dev2026` (biến `SCADA_FAKE_SA_PASSWORD`). Chỉ để dựng/sửa số liệu, ứng dụng không dùng.

## Số liệu

- Mốc theo giờ từ 2026-06-01 đến 2027-06-01; view chỉ trả dòng `DateTime <= GETDATE()` (giờ Việt Nam, container đặt `TZ=Asia/Ho_Chi_Minh`).
- Truy vấn `wwResolution = 3600000` trả mốc tròn giờ. Truy vấn `wwResolution = 60000` trả mốc phút của ~20 phút gần nhất (nội suy giữa 2 mốc giờ kề, tính theo `GETDATE()`), nên truy vấn "số mới nhất" luôn có số.
- Bộ đếm lũy kế, không giảm. Đầu 09/2026: điện 180.000 kWh (+2.000–3.100 kWh/ngày, chủ yếu 6–22 giờ), nước 7.600 m³ (+150–230 m³/ngày), bành 8.600 (+400–590/ngày). Vài ngày nghỉ gần 0 (bành = 0). Cuối 09/2026 điện ~247.000 kWh. Trước 01/09 là mùa thấp điểm (tiêu thụ ×0,15) để bộ đếm không âm.
- **Điện lưu 4 thanh ghi 16-bit** từ Wh = kWh × 1000: `R3 = Wh & 0xFFFF`, `R2 = (Wh>>16) & 0xFFFF`, `R1 = (Wh>>32) & 0xFFFF`, `R0 = Wh>>48`. `R3` cố ý lưu dạng số có dấu int16 (quá 32767 thì trừ 65536) nên hay ra **số âm** như PLC thật — ứng dụng phải `& 0xFFFF` trước khi ghép.

### Hai bẫy dữ liệu (để thử cờ cảnh báo)

1. `2026-09-12 00:00` → `Water_TotalVolume = NULL` (ứng dụng phải gắn cờ `partial`).
2. Cả ngày `2026-09-20` (24 mốc 00:00–23:00) → `Packing_BaleCount = NULL` (cờ `no_data`). Hệ quả: mốc cuối của ngày 09-19 (chính là 09-20 00:00) cũng trống.

## Giới hạn (đây là giả lập)

- Không mô phỏng thuật toán Cyclic của Historian: chỉ trả mốc có sẵn (giờ) hoặc nội suy tuyến tính (phút), bỏ qua `wwRetrievalMode`, `wwQualityRule`, `wwVersion` ngoài việc lộ đúng cột và giá trị `'Cyclic'`/`'Extended'`/`'Latest'`.
- Linked server `INSQL` là loại "SQL Server" loopback về chính instance (SQL Server trên Linux không cho login thường dùng kiểu OLE DB tường minh — lỗi 7416). Vì loại này không khai được `@catalog`, CSDL đích do CSDL mặc định của `scada_ro` (`Runtime`) quyết định; login `sa` (CSDL mặc định `master`) phải viết `FROM Runtime.dbo.WideHistory`.
- Cổng chỉ mở ở `127.0.0.1:14330`.
