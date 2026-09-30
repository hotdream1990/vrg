#!/usr/bin/env bash
# Dựng SQL Server giả lập Historian: up container -> chờ sẵn sàng -> nạp init.sql -> tự kiểm bằng login scada_ro.
# CHỈ DÙNG DEV CỤC BỘ. Mật khẩu mặc định bên dưới là dev-only, ghi đè bằng biến môi trường nếu muốn.
set -euo pipefail
cd "$(dirname "$0")"

export SCADA_FAKE_SA_PASSWORD="${SCADA_FAKE_SA_PASSWORD:-VrgScada!Dev2026}"
export SCADA_FAKE_RO_PASSWORD="${SCADA_FAKE_RO_PASSWORD:-ScadaRo!Dev2026}"
C=vrg-scada-fake

docker compose up -d

echo "Chờ SQL Server sẵn sàng (lần đầu chạy qua Rosetta có thể mất ~1 phút)..."
status=none
for _ in $(seq 1 60); do
  status=$(docker inspect -f '{{.State.Health.Status}}' "$C" 2>/dev/null || echo none)
  [ "$status" = healthy ] && break
  sleep 3
done
if [ "$status" != healthy ]; then
  echo "SQL Server không lên (trạng thái: $status). Log cuối:" >&2
  docker logs --tail 40 "$C" >&2
  exit 1
fi

# sqlcmd nằm ở tools18 (image 2022) hoặc tools (image 2019)
SQLCMD=$(docker exec "$C" sh -c 'ls /opt/mssql-tools18/bin/sqlcmd /opt/mssql-tools/bin/sqlcmd 2>/dev/null | head -1')

echo "Nạp init.sql..."
docker exec -e SQLCMDPASSWORD="$SCADA_FAKE_SA_PASSWORD" "$C" "$SQLCMD" -C -S localhost -U sa -b \
  -i /init/init.sql -v SCADA_RO_PASSWORD="$SCADA_FAKE_RO_PASSWORD"

echo "Tự kiểm: truy vấn 'số mới nhất' bằng login scada_ro qua OPENQUERY(INSQL, ...)"
docker exec -e SQLCMDPASSWORD="$SCADA_FAKE_RO_PASSWORD" "$C" "$SQLCMD" -C -S localhost -U scada_ro -d Runtime -b -Q "
SELECT * FROM OPENQUERY(INSQL, 'SELECT DateTime, [PM_EnergyReal2], [PM_EnergyReal3], [Water_TotalVolume], [Packing_BaleCount]
 FROM WideHistory
 WHERE wwRetrievalMode = ''Cyclic'' AND wwResolution = 60000
 AND wwQualityRule = ''Extended'' AND wwVersion = ''Latest''
 AND DateTime >= DateAdd(mi,-10,GetDate()) AND DateTime <= GetDate()')"

echo "Xong. Host: localhost  Port: 14330  User: scada_ro  DB: Runtime  Linked server: INSQL"
echo "Kiểm đầy đủ: uv run --with pymssql python scripts/scada-fake-historian/smoke_query.py"
