"""Web Push — gửi thông báo tới trình duyệt đã bấm "Nhận thông báo trên máy này" (chốt 01/10/2026).

Báo được cả khi đã đóng trang (iPhone cần "Thêm vào màn hình chính"). Nguyên tắc giống email:
**push KHÔNG BAO GIỜ làm hỏng nghiệp vụ** — `send_async` / `send_batch_async` không ném lỗi,
chạy ở luồng nền (cả đợt nhiều lượt: một luồng, một kết nối).

- Khoá VAPID tự sinh lần đầu cần, lưu `app_config` (`VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY` bí mật),
  KHÔNG hiện trên trang Cấu hình (không nằm trong CONFIG_SPEC) và KHÔNG ghi Nhật ký hoạt động.
- Mỗi trình duyệt một dòng `push_subscription` (khoá = endpoint). Dịch vụ push trả 404/410 = trình
  duyệt đã huỷ đăng ký → xoá dòng.
"""

from __future__ import annotations

import json
import logging
import threading
from collections.abc import Iterable
from urllib.parse import urlsplit

import httpx
from sqlalchemy import text

from app.core.db import ensure_schema, session_scope
from app.services import web_push_crypto as wpc

logger = logging.getLogger("vrg.web_push")

PUBLIC_KEY_KEY, PRIVATE_KEY_KEY = "VAPID_PUBLIC_KEY", "VAPID_PRIVATE_KEY"
_TIMEOUT = 10  # giây cho mỗi lần gọi dịch vụ push
_TTL = 86400  # dịch vụ push giữ tin tối đa 1 ngày khi máy đang tắt
_MAX_PAYLOAD_BYTES = 3000  # giới hạn thật ~4 KB/bản ghi; chừa xa cho an toàn
_TITLE_CHARS, _BODY_CHARS, _TAG_CHARS = 120, 400, 64
_MAX_PER_USER = 10  # mỗi tài khoản giữ tối đa 10 trình duyệt — chặn đăng ký rác làm phình bảng
_DEFAULT_SUBJECT = "mailto:noreply@vrg.vn"
# Chỉ gửi tới dịch vụ push thật của trình duyệt (Chrome & họ Chromium = FCM · Firefox = Mozilla ·
# Edge = WNS · Safari = Apple) — endpoint do trình duyệt gửi lên, không để máy chủ bị sai khiến POST
# tới địa chỉ tuỳ ý. Trình duyệt nào báo "chưa được hỗ trợ" thì bổ sung host vào đây.
_PUSH_HOST_SUFFIXES = ("fcm.googleapis.com", "push.services.mozilla.com",
                       "notify.windows.com", "push.apple.com")

_transport: httpx.BaseTransport | None = None  # test thay bằng httpx.MockTransport
_keys_lock = threading.Lock()
_keys: tuple[str, str] | None = None  # (public, private) đã nạp

#: Một lượt thông báo: (tài khoản nhận, tiêu đề, nội dung, đường dẫn trong web, tag).
PushItem = tuple[Iterable[str], str, str, str | None, str | None]


def _vapid_keys() -> tuple[str, str]:
    """(public, private) VAPID — chưa có thì sinh + ghi `INSERT … ON CONFLICT` (chỉ điền ô đang
    trống, KHÔNG đè khoá đã có) rồi đọc lại, nên hai tiến trình cùng sinh một lúc vẫn chỉ một cặp
    thắng. Khoá công khai luôn suy từ khoá riêng (lỡ hai dòng lệch nhau vẫn ký đúng)."""
    global _keys
    if _keys:
        return _keys
    with _keys_lock:
        if _keys:
            return _keys
        ensure_schema()
        pub, priv = wpc.generate_vapid_keypair()
        with session_scope() as db:
            db.execute(text("""
                INSERT INTO app_config (key, value, is_secret, updated_by)
                VALUES (:pk, :pub, false, 'system'), (:sk, :priv, true, 'system')
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = now()
                WHERE COALESCE(app_config.value, '') = ''
            """), {"pk": PUBLIC_KEY_KEY, "pub": pub, "sk": PRIVATE_KEY_KEY, "priv": priv})
            stored = dict(db.execute(
                text("SELECT key, value FROM app_config WHERE key IN (:pk, :sk)"),
                {"pk": PUBLIC_KEY_KEY, "sk": PRIVATE_KEY_KEY}).all())
        private = stored[PRIVATE_KEY_KEY]
        public = wpc.public_from_private(private)
        if stored.get(PUBLIC_KEY_KEY) != public:
            logger.warning("[push] VAPID_PUBLIC_KEY lưu không khớp khoá riêng — dùng khoá suy ra.")
        _keys = (public, private)
        return _keys


def public_key() -> str:
    """Khoá công khai VAPID (base64url) — trình duyệt cần để đăng ký nhận push."""
    return _vapid_keys()[0]


def validate_subscription(endpoint: str, p256dh: str, auth: str) -> None:
    """Đăng ký trình duyệt gửi lên có dùng được không — sai thì ValueError (câu tiếng Việt)."""
    parts = urlsplit(endpoint or "")
    host = (parts.hostname or "").lower()
    if parts.scheme != "https" or not host:
        raise ValueError("Địa chỉ nhận thông báo không hợp lệ.")
    if not any(host == s or host.endswith("." + s) for s in _PUSH_HOST_SUFFIXES):
        raise ValueError("Trình duyệt này dùng dịch vụ thông báo chưa được hỗ trợ.")
    try:
        wpc.check_receiver_keys(wpc.b64url_decode(p256dh), wpc.b64url_decode(auth))
    except ValueError as exc:
        raise ValueError("Khoá mã hoá của trình duyệt không hợp lệ.") from exc


def save_subscription(username: str, endpoint: str, p256dh: str, auth: str,
                      user_agent: str | None = None) -> None:
    """Ghi/cập nhật theo endpoint.

    - Cùng tài khoản → cập nhật khoá.
    - Tài khoản KHÁC → chỉ chuyển dòng sang khi khoá trùng hẳn (đúng trình duyệt đó, máy dùng chung:
      người đăng nhập sau cùng nhận). Chỉ biết endpoint mà không có khoá thì dòng giữ nguyên — không
      cướp được thông báo của người khác. Không báo lỗi (khỏi lộ endpoint đã có chủ).
    """
    ensure_schema()
    with session_scope() as db:
        db.execute(text("""
            INSERT INTO push_subscription (endpoint, username, p256dh, auth, user_agent)
            VALUES (:e, :u, :p, :a, :ua)
            ON CONFLICT (endpoint) DO UPDATE SET username = EXCLUDED.username,
                p256dh = EXCLUDED.p256dh, auth = EXCLUDED.auth, user_agent = EXCLUDED.user_agent
            WHERE push_subscription.username = EXCLUDED.username
               OR (push_subscription.p256dh = EXCLUDED.p256dh
                   AND push_subscription.auth = EXCLUDED.auth)
        """), {"e": endpoint, "u": username, "p": p256dh, "a": auth, "ua": user_agent})
        db.execute(text("""
            DELETE FROM push_subscription WHERE username = :u AND endpoint NOT IN (
                SELECT endpoint FROM push_subscription WHERE username = :u
                ORDER BY (endpoint = :e) DESC, COALESCE(last_ok_at, created_at) DESC LIMIT :n)
        """), {"u": username, "e": endpoint, "n": _MAX_PER_USER})


def delete_subscription(endpoint: str, username: str | None = None) -> bool:
    """Xoá một đăng ký; có `username` thì chỉ xoá khi dòng thuộc tài khoản đó."""
    ensure_schema()
    sql = "DELETE FROM push_subscription WHERE endpoint = :e"
    if username is not None:
        sql += " AND username = :u"
    with session_scope() as db:
        return bool(db.execute(text(sql), {"e": endpoint, "u": username}).rowcount)


def _subscriptions_for(usernames: list[str]) -> list[dict]:
    ensure_schema()
    with session_scope() as db:
        rows = db.execute(text("SELECT endpoint, username, p256dh, auth FROM push_subscription "
                               "WHERE username = ANY(:u)"),
            {"u": usernames}).mappings().all()
    return [dict(r) for r in rows]


def _local_url(url: str | None) -> str:
    """Chỉ nhận đường dẫn trong chính web (`/ho-tro/12`); URL tuyệt đối thì lấy phần đường dẫn."""
    u = (url or "").strip()
    if u.startswith(("http://", "https://")):
        parts = urlsplit(u)
        u = parts.path + (f"?{parts.query}" if parts.query else "")
    # "/\evil" cũng bị trình duyệt (WHATWG) đọc thành "//evil" → coi như URL ngoài.
    return u if u.startswith("/") and not u.startswith(("//", "/\\")) else "/"


def build_payload(title: str, body: str, url: str | None, tag: str | None = None) -> bytes:
    """JSON {title, body, url, tag} gọn dưới `_MAX_PAYLOAD_BYTES` — dài thì cắt bớt nội dung."""
    def clip(s: str | None, n: int) -> str:
        s = " ".join((s or "").split())
        return s if len(s) <= n else s[: n - 1].rstrip() + "…"

    data = {"title": clip(title, _TITLE_CHARS) or "VRG", "body": clip(body, _BODY_CHARS),
            "url": _local_url(url)[:500], "tag": clip(tag, _TAG_CHARS) or None}
    raw = json.dumps(data, ensure_ascii=False).encode()
    while len(raw) > _MAX_PAYLOAD_BYTES and data["body"]:
        data["body"] = clip(data["body"], len(data["body"]) * 3 // 4)
        raw = json.dumps(data, ensure_ascii=False).encode()
    return raw


def _subject() -> str:
    from app.services import config_repo, mailer

    sender = mailer.normalize(config_repo.get_value(mailer.FROM_KEY))
    return f"mailto:{sender}" if sender else _DEFAULT_SUBJECT


def _send_one(client: httpx.Client, sub: dict, payload: bytes, keys: tuple[str, str],
              subject: str) -> bool:
    """Gửi một trình duyệt → True nếu đăng ký đã hết hạn và vừa bị xoá."""
    endpoint = sub["endpoint"]
    host = urlsplit(endpoint).hostname  # chỉ log host — endpoint đầy đủ là "chìa khoá" gửi tin
    try:
        body = wpc.encrypt(payload, wpc.b64url_decode(sub["p256dh"]), wpc.b64url_decode(sub["auth"]))
        headers = {
            "Authorization": wpc.vapid_authorization(endpoint, keys[1], keys[0], subject),
            "Content-Encoding": "aes128gcm", "Content-Type": "application/octet-stream",
            "TTL": str(_TTL), "Urgency": "normal",
        }
        resp = client.post(endpoint, content=body, headers=headers)
    except Exception as exc:  # noqa: BLE001 - một trình duyệt lỗi không chặn các trình duyệt khác
        logger.warning("[push] Gửi tới %s thất bại: %s", host, type(exc).__name__)
        return False
    if resp.status_code in (404, 410):
        delete_subscription(endpoint)
        logger.info("[push] %s báo đăng ký đã hết hạn (%d) — đã xoá.", host, resp.status_code)
        return True
    if 200 <= resp.status_code < 300:
        with session_scope() as db:
            db.execute(text("UPDATE push_subscription SET last_ok_at = now() WHERE endpoint = :e"),
                       {"e": endpoint})
    else:
        logger.warning("[push] %s trả HTTP %d: %s", host, resp.status_code, resp.text[:200])
    return False


def deliver(jobs: list[tuple[list[dict], bytes]]) -> None:
    """Gửi tuần tự từng (trình duyệt, nội dung) qua MỘT httpx.Client (chạy ở luồng nền). Không ném lỗi."""
    try:
        keys, subject = _vapid_keys(), _subject()
        gone: set[str] = set()   # đã báo hết hạn ở lượt trước trong cùng đợt → khỏi gửi lại
        with httpx.Client(timeout=_TIMEOUT, transport=_transport) as client:
            for subs, payload in jobs:
                for sub in subs:
                    if sub["endpoint"] not in gone and _send_one(client, sub, payload, keys, subject):
                        gone.add(sub["endpoint"])
    except Exception as exc:  # noqa: BLE001 - push lỗi KHÔNG được làm hỏng nghiệp vụ
        logger.warning("[push] Bỏ qua lượt gửi: %s", type(exc).__name__)


def _names(usernames: Iterable[str] | str | None) -> list[str]:
    if isinstance(usernames, str):  # lỡ truyền một tên trần — đừng tách thành từng ký tự
        usernames = [usernames]
    return sorted({u.strip() for u in (usernames or ()) if u and u.strip()})


def send_batch_async(items: Iterable[PushItem]) -> None:
    """Gửi NHIỀU lượt thông báo (vd mỗi đơn vị một lượt khi Tập đoàn gửi "tất cả đơn vị") trong MỘT
    luồng nền, MỘT httpx.Client, đọc đăng ký một lần. Chạy nền, KHÔNG BAO GIỜ ném lỗi."""
    try:
        wanted = [(_names(users), title, body, url, tag) for users, title, body, url, tag in items]
        wanted = [w for w in wanted if w[0]]
        if not wanted:
            return
        by_user: dict[str, list[dict]] = {}
        for sub in _subscriptions_for(sorted({u for w in wanted for u in w[0]})):
            by_user.setdefault(sub["username"], []).append(sub)
        jobs = []
        for names, title, body, url, tag in wanted:
            subs = [sub for u in names for sub in by_user.get(u, [])]
            if subs:
                jobs.append((subs, build_payload(title, body, url, tag)))
        if jobs:
            threading.Thread(target=deliver, args=(jobs,), daemon=True, name="web-push").start()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[push] Bỏ qua gửi thông báo: %s", type(exc).__name__)


def send_async(usernames: Iterable[str], title: str, body: str, url: str,
               tag: str | None = None) -> None:
    """Gửi push tới MỌI trình duyệt đã đăng ký của các tài khoản này, chạy nền, KHÔNG BAO GIỜ ném lỗi."""
    send_batch_async([(usernames, title, body, url, tag)])
