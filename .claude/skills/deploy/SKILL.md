---
name: deploy
description: Build + deploy VRG lên production (Dokploy · docker-compose). Dùng khi user nói "deploy", "build và deploy", "đưa bản mới lên", "rollback về bản cũ", hoặc cần chạy SQL trên DB prod.
---

## Ba lớp ghi — đọc trước khi đụng prod

| Lớp | Ở đâu | Mất khi |
|---|---|---|
| **L1** DB Dokploy (`compose.env`, `compose.composeFile`) | container `dokploy-postgres` | không mất — **UI đọc lớp này** |
| **L2** `/etc/dokploy/compose/<appName>/code/{docker-compose.yml,.env}` | đĩa server | bị ghi đè từ L1 mỗi lần Deploy |
| **L3** runtime (`docker service update` / container) | swarm hoặc docker | bị ghi đè khi Dokploy Deploy |

Sửa thẳng L3 hoặc L2 mà không ghi L1 = **thay đổi biến mất** lần kế tiếp ai bấm Deploy, và UI Dokploy
không bao giờ thấy nó. Đầy đủ: `~/.claude/skills/dokploy-deploy/SKILL.md` mục 1.

```bash
./.claude/skills/deploy/dokploy-sync.local.sh check          # CHỈ ĐỌC — so 3 lớp. Chạy trước mọi đợt.
./.claude/skills/deploy/dokploy-sync.local.sh set-env K=V    # ghi env vào L1 + L2
./.claude/skills/deploy/dokploy-sync.local.sh push-compose f # ghi compose vào L1 (KHÔNG đụng đĩa)
./.claude/skills/deploy/dokploy-sync.local.sh deploy         # Dokploy tự dựng lại — không cần API key
```

`deploy` gọi webhook `refreshToken` → làm **đúng việc nút Deploy trên UI làm**
(`docker stack deploy --prune --with-registry-auth`). `--prune` xoá service không có trong compose.
Đây là thay đổi production → **hỏi chủ dự án trước khi chạy**.

> ⚠️ **Bảo mật — CÒN VIỆC CHO ANH:** `SSH_PASSWORD` cũ **trùng đúng chuỗi** với `composeId` của app
> trên Dokploy — ai vào được panel Dokploy đều đọc được (chuỗi cụ thể xem `docs/data/prod-accounts.md`, file đã gitignore). Đã **gỡ khỏi**
> `dokploy-target.local.env` và chuyển script sang SSH key (đã kiểm vào được), nên **đổi mật khẩu root
> của server không làm hỏng deploy**. Việc đổi mật khẩu là thao tác của anh, em không tự làm.
> Env đã đồng bộ 23/08/2026 (đĩa đang cũ: `VRG_TAG` 0.2.28 → 0.4.37 khớp container đang chạy).


# Deploy VRG lên production

**1 image gộp** (web Vite tĩnh + FastAPI phục vụ cả SPA lẫn `/api` cùng origin),
chạy trên **Dokploy · docker-compose** (KHÔNG phải Swarm stack → không dùng `docker service update`).

Thông tin server nằm trong `dokploy-target.local.env` (gitignored). Nguồn gốc: `docs/data/prod-accounts.md`.

## Quy trình 3 bước

```bash
# ① Bump version — PHẢI đồng thời 2 nơi rồi khoá lại lockfile
sed -i '' 's/^version = "0.2.71"/version = "0.2.72"/' apps/api/pyproject.toml
sed -i '' 's/"version": "0.2.71"/"version": "0.2.72"/' apps/web/package.json
(cd apps/api && uv lock -q)
git add -A apps/ && git commit -m "chore(release): bump version to 0.2.72"

# ② Build + push (~10–15 phút: image có Playwright Firefox [crawler] + Chromium [xuất PDF])
#    Chạy nền bằng nohup để không chết theo phiên; ĐỪNG pipe qua `tail` (che mất exit code của buildx).
#    ⚠ LUÔN kèm 2 cờ cache: bước `playwright install --with-deps firefox` tải >150 gói .deb — hôm
#    mạng chậm (27 kB/s, 06/09/2026) build mất 70 phút thay vì 17. Cache đẩy lên registry để lần
#    sau tái dùng; `--cache-to type=inline` nhúng luôn vào image, không tạo tag rác.
source .claude/skills/deploy/dokploy-target.local.env
nohup docker buildx build --platform linux/amd64 -f Dockerfile \
  -t "$IMAGE_BASE:0.2.72" \
  --cache-from "type=registry,ref=$IMAGE_BASE:buildcache" \
  --cache-to "type=inline" \
  --push . > /tmp/vrg-build.log 2>&1 &

# ③ Deploy (script tự kiểm image đã lên registry chưa)
./.claude/skills/deploy/dokploy-redeploy.local.sh 0.2.72
```

Rollback = deploy lại tag cũ: `./dokploy-redeploy.local.sh 0.2.70` (image cũ vẫn còn trong registry).

## Trước khi build — kiểm tra bắt buộc

```bash
cd apps/api && uv run pytest -q          # toàn bộ test phải xanh
cd apps/web && ./node_modules/.bin/tsc --noEmit && ./node_modules/.bin/vite build
```

**Đổi ý nghĩa dữ liệu (đơn vị tính, tên khoá payload, công thức) → đếm dòng trên prod TRƯỚC:**

```bash
source .claude/skills/deploy/dokploy-target.local.env; export SSHPASS="$SSH_PASSWORD"
sshpass -e ssh -p "$SSH_PORT" "$SSH_USER@$SSH_HOST" \
  "docker exec -i $DB_CONTAINER psql -U $DB_USER -d $DB_NAME -tAc 'SELECT count(*) FROM <bảng>'"
```
0 dòng → đổi thoải mái. Có dòng → phải viết migration, không được đổi ngầm.

## Script deploy làm gì (và vì sao theo thứ tự đó)

1. **Kiểm image có thật trên registry** — `buildx` từng báo thành công nhưng **fail ở bước push**
   (GitLab trả `400 Bad Request` giữa chừng). Không kiểm thì deploy sẽ chết với `manifest unknown`.
2. **Ghi `VRG_TAG` vào DB Dokploy TRƯỚC khi deploy** — deploy thủ công không báo cho Dokploy biết,
   nên env trong DB đứng im. Thực tế đã lệch tới **0.2.28 so với bản đang chạy**: ai bấm Deploy trên
   Dokploy UI là **tụt 42 version**. Script cập nhật env nên UI và thực tế luôn khớp.
3. **Giữ nguyên `ADMIN_USERNAME` / `ADMIN_PASSWORD`** — Dokploy tự tiêm lúc chạy, `.env` cạnh compose
   KHÔNG có. Deploy mà thiếu là **reset tài khoản admin**. Script lấy lại từ container đang chạy và
   **dừng hẳn nếu không lấy đủ 2 biến**.
4. **Chỉ recreate service `app`** — DB và volume dữ liệu không đụng tới.
5. **Đối chiếu version công khai** qua `/openapi.json` — không tin mỗi log deploy.

## Sau khi deploy

- **Migration tự chạy** trong `ensure_schema()` lúc app khởi động (`ALTER TABLE … ADD COLUMN IF NOT EXISTS`).
  Không cần SQL tay, trừ khi memory `production-deployment` ghi rõ có bước hậu-kỳ.
- **Web cache**: nhắc user **hard-refresh (Cmd+Shift+R)** — Ctrl+F5 nhiều lúc không đủ.
- Cập nhật memory `production-deployment` với version + nội dung thay đổi + bước hậu-kỳ (nếu có).

## Chạy SQL trên DB prod

DB không mở ra ngoài — phải đi qua SSH:

```bash
source .claude/skills/deploy/dokploy-target.local.env; export SSHPASS="$SSH_PASSWORD"
cat file.sql | sshpass -e ssh -p "$SSH_PORT" "$SSH_USER@$SSH_HOST" \
  "docker exec -i $DB_CONTAINER psql -U $DB_USER -d $DB_NAME -v ON_ERROR_STOP=1"
```
Sửa dữ liệu thì bọc `BEGIN; … COMMIT;` và `SELECT` lại để đối chiếu. Chỉ đọc thì thoải mái;
ghi/xoá phải hỏi user trước.

## Bẫy đã trả giá

- ⛔ **Build web NGOÀI Dockerfile (image vá) phải là `VITE_API_URL="" pnpm build`** — `http.ts` rơi về
  `http://localhost:8390` khi biến không được đặt. 0.4.93 (28/09/2026) quên ⇒ web prod gọi localhost, **không
  ai đăng nhập được ~2h40'**, `/health` vẫn `healthy` nên script deploy không bắt được. Trước khi push:
  `cat apps/web/dist/assets/*.js | grep -c localhost:8390` PHẢI = 0; sau deploy kiểm lại trên bundle công khai.
- **`DOCKER_CONFIG` trỏ vào volume của Dokploy** (`DOCKER_CONFIG_PATH` trong file env) — thiếu là `pull` bị **403** (auth registry
  nằm trong volume của Dokploy, không phải `~/.docker`).
- **Chỉ tag version, KHÔNG `latest`** — Dokploy pull theo tag, tag trùng thì không kéo bản mới.
- **`docker buildx` push fail rời rạc** — gặp `400 Bad Request` thì chạy lại, layer đã cache nên nhanh.
- **Đừng tin exit code khi chạy nền qua pipe** — `cmd | tail` trả exit code của `tail`, che mất lỗi buildx.
  Đọc thẳng file log.
- **Không thêm HEALTHCHECK vào Dockerfile** nếu entrypoint chạy migrate trước khi start.

## ⚠ Bảo mật — 2 việc nên xử lý

1. **Mật khẩu SSH root trùng đúng chuỗi `composeId` của Dokploy.** composeId xuất hiện trong URL
   của Dokploy UI và trong DB → ai xem được panel là biết mật khẩu root. **Nên đổi mật khẩu root và
   chuyển sang SSH key** (`ssh-copy-id`), rồi bỏ `SSH_PASSWORD` khỏi file env.
2. `dokploy-target.local.env` chứa thông tin server — đã chặn bằng `*.local.*` trong `.gitignore`.
   Kiểm lại bất cứ lúc nào: `git check-ignore -v .claude/skills/deploy/dokploy-target.local.env`.
