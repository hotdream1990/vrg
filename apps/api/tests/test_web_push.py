"""Test Web Push: mã hoá RFC 8291 (khớp từng byte Phụ lục A) · chữ ký VAPID · đường gửi · API đăng ký.

Dữ liệu tạo ra đều mang tiền tố `_zz_push_` và được dọn sau mỗi test. KHÔNG xoá/ghi đè khoá VAPID
đang có trong DB (DB dev là bản sao prod) — chưa có thì code tự sinh, đúng như chạy thật.
"""

from __future__ import annotations

import json
import time
import uuid

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.db import db_healthy, session_scope
from app.core.security import create_access_token, create_impersonation_token
from app.services import user_repo, web_push
from app.services import web_push_crypto as wpc

d = wpc.b64url_decode

# ── RFC 8291 §5 + Phụ lục A ──
RFC_PLAINTEXT = b"When I grow up, I want to be a watermelon"
RFC_AUTH = "BTBZMqHH6r4Tts7J_aSIgg"
RFC_UA_PUBLIC = "BCVxsr7N_eNgVRqvHtD0zTZsEc6-VV-JvLexhqUzORcxaOzi6-AYWXvTBHm4bjyPjs7Vd8pZGH6SRpkNtoIAiw4"
RFC_UA_PRIVATE = "q1dXpw3UpT5VOmu_cf_v6ih07Aems3njxI-JWgLcM94"
RFC_AS_PRIVATE = "yfWPiYE-n46HLnH0KqZOF1fJJU3MYrct3AELtAQ-oRw"
RFC_AS_PUBLIC = "BP4z9KsN6nGRTbVYI_c7VJSPQTBtkgcy27mlmlMoZIIgDll6e3vCYLocInmYWAmS6TlzAC8wEqKK6PBru3jl7A8"
RFC_SALT = "DGv6ra1nlYgDCS1FRnbzlw"
RFC_BODY = ("DGv6ra1nlYgDCS1FRnbzlwAAEABBBP4z9KsN6nGRTbVYI_c7VJSPQTBtkgcy27ml"
            "mlMoZIIgDll6e3vCYLocInmYWAmS6TlzAC8wEqKK6PBru3jl7A_yl95bQpu6cVPT"
            "pK4Mqgkf1CXztLVBSt2Ks3oZwbuwXPXLWyouBWLVWGNWQexSgSxsj_Qulcy4a-fN")


def _decrypt(body: bytes, ua_private: ec.EllipticCurvePrivateKey, auth: bytes) -> bytes:
    """Phía TRÌNH DUYỆT (độc lập với code gửi): bóc header → ECDH → HKDF → AES-GCM → bỏ 0x02."""
    salt, rs, idlen = body[:16], int.from_bytes(body[16:20], "big"), body[20]
    as_public, ciphertext = body[21:21 + idlen], body[21 + idlen:]
    assert rs == 4096 and idlen == 65
    ua_public = wpc.public_point(ua_private)
    shared = ua_private.exchange(
        ec.ECDH(), ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), as_public))

    def hkdf(salt_: bytes, ikm: bytes, info: bytes, n: int) -> bytes:
        return HKDF(algorithm=hashes.SHA256(), length=n, salt=salt_, info=info).derive(ikm)

    ikm = hkdf(auth, shared, b"WebPush: info\x00" + ua_public + as_public, 32)
    cek = hkdf(salt, ikm, b"Content-Encoding: aes128gcm\x00", 16)
    nonce = hkdf(salt, ikm, b"Content-Encoding: nonce\x00", 12)
    plain = AESGCM(cek).decrypt(nonce, ciphertext, None)
    assert plain.endswith(b"\x02")
    return plain[:-1]


def test_rfc8291_phu_luc_a_khop_tung_byte() -> None:
    as_private = wpc.load_private_key(RFC_AS_PRIVATE)
    assert wpc.b64url_encode(wpc.public_point(as_private)) == RFC_AS_PUBLIC
    out = wpc.encrypt(RFC_PLAINTEXT, d(RFC_UA_PUBLIC), d(RFC_AUTH),
                      as_private=as_private, salt=d(RFC_SALT))
    assert out == d(RFC_BODY)
    # Bộ giải mã của test cũng đúng chuẩn: mở được đúng ví dụ RFC bằng khoá riêng trình duyệt.
    assert _decrypt(d(RFC_BODY), wpc.load_private_key(RFC_UA_PRIVATE), d(RFC_AUTH)) == RFC_PLAINTEXT


def test_ma_hoa_roi_giai_ma_ra_dung_noi_dung() -> None:
    receiver = ec.generate_private_key(ec.SECP256R1())
    auth = bytes(range(16))
    payload = web_push.build_payload("Thông báo mới", "Nội dung tiếng Việt có dấu", "/ho-tro/1", "t1")
    body = wpc.encrypt(payload, wpc.public_point(receiver), auth)
    assert json.loads(_decrypt(body, receiver, auth)) == {
        "title": "Thông báo mới", "body": "Nội dung tiếng Việt có dấu", "url": "/ho-tro/1", "tag": "t1"}
    # Mỗi lần gửi một khoá tạm + salt mới → cùng nội dung ra hai thân khác nhau.
    assert wpc.encrypt(payload, wpc.public_point(receiver), auth) != body


def test_vapid_jwt_ky_dung_va_dung_aud_sub_exp() -> None:
    public, private = wpc.generate_vapid_keypair()
    assert len(d(public)) == 65 and len(d(private)) == 32
    now = int(time.time())
    header = wpc.vapid_authorization("https://fcm.googleapis.com/fcm/send/abc", private, public,
                                     "mailto:noreply@vrg.vn", now=now)
    assert header.startswith("vapid t=") and header.endswith(f", k={public}")
    token = header[len("vapid t="):header.index(", k=")]
    verify_key = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), d(public))
    claims = jwt.decode(token, verify_key, algorithms=["ES256"], audience="https://fcm.googleapis.com")
    assert claims["sub"] == "mailto:noreply@vrg.vn"
    assert claims["exp"] == now + 12 * 3600
    assert jwt.get_unverified_header(token)["alg"] == "ES256"


def test_payload_gon_va_url_chi_trong_web() -> None:
    raw = web_push.build_payload("T" * 500, "Ữ" * 5000, "https://evil.example/ho-tro/5?x=1")
    data = json.loads(raw)
    assert len(raw) < 3000 and data["body"].endswith("…")
    assert data["url"] == "/ho-tro/5?x=1"
    assert json.loads(web_push.build_payload("a", "b", "//evil.example"))["url"] == "/"
    assert json.loads(web_push.build_payload("a", "b", "javascript:alert(1)"))["url"] == "/"
    # "/\\evil" bị trình duyệt đọc thành "//evil" → cũng chặn (kể cả khi nằm trong URL tuyệt đối).
    for url in ("/\\evil.example", "https://vrg.vn/\\evil.example/x"):
        assert json.loads(web_push.build_payload("a", "b", url))["url"] == "/", url


def test_kiem_tra_dang_ky_trinh_duyet() -> None:
    p256dh = wpc.b64url_encode(wpc.public_point(ec.generate_private_key(ec.SECP256R1())))
    auth = wpc.b64url_encode(bytes(16))
    web_push.validate_subscription("https://fcm.googleapis.com/fcm/send/x", p256dh, auth)
    web_push.validate_subscription("https://web.push.apple.com/abc", p256dh, auth)
    for endpoint in ("http://fcm.googleapis.com/x", "https://evil.example/x",
                     "https://fcm.googleapis.com.evil.example/x"):
        with pytest.raises(ValueError):
            web_push.validate_subscription(endpoint, p256dh, auth)
    with pytest.raises(ValueError):
        web_push.validate_subscription("https://fcm.googleapis.com/x", p256dh[:-4] + "AAAA", auth)
    with pytest.raises(ValueError):
        web_push.validate_subscription("https://fcm.googleapis.com/x", p256dh, "a+b/")


# ── Phần cần DB ──
needs_db = pytest.mark.skipif(not db_healthy(), reason="DB không sẵn sàng")
USERS = ("_zz_push_a", "_zz_push_b")


def _endpoint() -> str:
    return f"https://fcm.googleapis.com/fcm/send/_zz_push_{uuid.uuid4().hex}"


def _row(endpoint: str) -> dict | None:
    with session_scope() as db:
        r = db.execute(text("SELECT * FROM push_subscription WHERE endpoint = :e"),
                       {"e": endpoint}).mappings().first()
    return dict(r) if r else None


@pytest.fixture
def users():
    for u in USERS:
        user_repo.delete_user(u)
        user_repo.create_user(u, "pass12345", None, "viewer")
    yield {u: {"Authorization": f"Bearer {create_access_token(u)}"} for u in USERS}
    with session_scope() as db:
        db.execute(text("DELETE FROM push_subscription WHERE username LIKE '\\_zz\\_push\\_%' "
                        "OR endpoint LIKE '%/\\_zz\\_push\\_%'"))
    for u in USERS:
        user_repo.delete_user(u)


def _receiver() -> tuple[ec.EllipticCurvePrivateKey, bytes, dict]:
    key, auth = ec.generate_private_key(ec.SECP256R1()), bytes(range(16, 32))
    keys = {"p256dh": wpc.b64url_encode(wpc.public_point(key)), "auth": wpc.b64url_encode(auth)}
    return key, auth, keys


class _Inline:  # chạy "luồng nền" ngay tại chỗ + đếm số luồng được mở
    started: list[str] = []

    def __init__(self, target, args, **_kw):
        self.target, self.args = target, args

    def start(self) -> None:
        _Inline.started.append(self.target.__name__)
        self.target(*self.args)


@needs_db
def test_gui_201_ghi_last_ok_va_410_xoa_dang_ky(users, monkeypatch) -> None:
    receiver, auth, keys = _receiver()
    ok_ep, gone_ep = _endpoint(), _endpoint()
    web_push.save_subscription(USERS[0], ok_ep, keys["p256dh"], keys["auth"])
    web_push.save_subscription(USERS[0], gone_ep, keys["p256dh"], keys["auth"])
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(201 if str(request.url) == ok_ep else 410)

    monkeypatch.setattr(web_push, "_transport", httpx.MockTransport(handler))
    monkeypatch.setattr(web_push.threading, "Thread", _Inline)
    web_push.send_async([USERS[0], USERS[0], " "], "Có thông báo", "Nội dung", "/ho-tro/9", "s-9")

    assert len(seen) == 2
    req = next(r for r in seen if str(r.url) == ok_ep)
    assert req.headers["content-encoding"] == "aes128gcm"
    assert req.headers["content-type"] == "application/octet-stream"
    assert req.headers["ttl"] == "86400" and req.headers["urgency"] == "normal"
    assert req.headers["authorization"].startswith("vapid t=")
    assert req.headers["authorization"].endswith(f"k={web_push.public_key()}")
    assert json.loads(_decrypt(req.content, receiver, auth))["url"] == "/ho-tro/9"
    assert _row(ok_ep)["last_ok_at"] is not None
    assert _row(gone_ep) is None


@needs_db
def test_gui_ca_dot_mot_luong_mot_ket_noi(users, monkeypatch) -> None:
    """Nhiều lượt (vd mỗi đơn vị một lượt) → 1 lần đọc đăng ký, 1 luồng nền, 1 httpx.Client."""
    recv = {u: _receiver() for u in USERS}
    eps = {u: _endpoint() for u in USERS}
    for u in USERS:
        web_push.save_subscription(u, eps[u], recv[u][2]["p256dh"], recv[u][2]["auth"])
    seen: list[httpx.Request] = []
    clients: list[int] = []
    lookups: list[list[str]] = []
    real_client, real_lookup = httpx.Client, web_push._subscriptions_for

    class _Client(real_client):
        def __init__(self, *a, **kw):
            clients.append(1)
            super().__init__(*a, **kw)

    monkeypatch.setattr(web_push, "_transport",
                        httpx.MockTransport(lambda r: seen.append(r) or httpx.Response(201)))
    monkeypatch.setattr(web_push.httpx, "Client", _Client)
    monkeypatch.setattr(web_push, "_subscriptions_for", lambda u: lookups.append(u) or real_lookup(u))
    monkeypatch.setattr(web_push.threading, "Thread", _Inline)
    _Inline.started.clear()
    web_push.send_batch_async([
        ([USERS[0]], "A", "a", "/ho-tro/1", "t1"),
        ([USERS[1]], "B", "b", "/ho-tro/2", "t2"),
        ([USERS[0], "_zz_push_khong_co"], "C", "c", "/ho-tro/3", None),
        ([" "], "rỗng", "", "/", None),
    ])
    assert _Inline.started == ["deliver"] and len(clients) == 1 and len(lookups) == 1
    got = sorted((str(r.url), json.loads(_decrypt(r.content, *recv[u][:2]))["title"])
                 for r in seen for u in USERS if str(r.url) == eps[u])
    assert got == sorted([(eps[USERS[0]], "A"), (eps[USERS[1]], "B"), (eps[USERS[0]], "C")])
    # send_async = vỏ mỏng của send_batch_async: một lượt cũng chỉ một luồng.
    web_push.send_async(USERS[1], "D", "d", "/")
    assert _Inline.started == ["deliver", "deliver"] and len(seen) == 4


@needs_db
def test_dang_ky_trung_endpoint_khac_khoa_khong_cuop_duoc(users) -> None:
    ep = _endpoint()
    _k, _a, mine = _receiver()
    _k2, _a2, other = _receiver()
    web_push.save_subscription(USERS[0], ep, mine["p256dh"], mine["auth"])
    # Chỉ biết endpoint (khoá khác, hoặc chỉ khác auth) → dòng giữ nguyên, không báo lỗi.
    for keys in (other, {**mine, "auth": wpc.b64url_encode(bytes(16))}):
        web_push.save_subscription(USERS[1], ep, keys["p256dh"], keys["auth"])
        row = _row(ep)
        assert (row["username"], row["p256dh"], row["auth"]) == (USERS[0], mine["p256dh"], mine["auth"])
    # Chính chủ đổi khoá → cập nhật như cũ.
    web_push.save_subscription(USERS[0], ep, other["p256dh"], other["auth"], "UA mới")
    assert (_row(ep)["p256dh"], _row(ep)["user_agent"]) == (other["p256dh"], "UA mới")
    # Đúng trình duyệt đó (khoá trùng hẳn), người khác đăng nhập → chuyển chủ.
    web_push.save_subscription(USERS[1], ep, other["p256dh"], other["auth"])
    assert _row(ep)["username"] == USERS[1]


@needs_db
def test_xoa_tai_khoan_don_dang_ky_push_va_da_doc(users) -> None:
    ep = _endpoint()
    _k, _a, keys = _receiver()
    web_push.save_subscription(USERS[0], ep, keys["p256dh"], keys["auth"])
    with session_scope() as db:
        db.execute(text("INSERT INTO support_read (thread_id, username) VALUES (-987654, :u) "
                        "ON CONFLICT DO NOTHING"), {"u": USERS[0]})
    assert user_repo.delete_user(USERS[0]) is True
    with session_scope() as db:
        left = db.execute(text("SELECT count(*) FROM support_read WHERE username = :u"),
                          {"u": USERS[0]}).scalar()
    assert _row(ep) is None and left == 0


@needs_db
def test_send_async_khong_bao_gio_nem_loi(monkeypatch) -> None:
    def boom(_users):
        raise RuntimeError("DB chết")

    monkeypatch.setattr(web_push, "_subscriptions_for", boom)
    web_push.send_async(["ai_do"], "t", "b", "/")  # không ném
    web_push.send_async([], "t", "b", "/")
    web_push.send_batch_async([(["ai_do"], "t", "b", "/", None)])
    web_push.send_batch_async([("thiếu cột",)])   # sai hình dạng → nuốt lỗi, không ném


@needs_db
def test_api_dang_ky_huy_chi_cua_minh(users) -> None:
    from app.main import app

    client = TestClient(app)
    a, b = users[USERS[0]], users[USERS[1]]
    _key, _auth, keys = _receiver()
    ep = _endpoint()

    key = client.get("/api/push/key", headers=a).json()["public_key"]
    assert len(d(key)) == 65
    assert client.post("/api/push/subscribe", json={"endpoint": ep, "keys": keys}, headers=a).status_code == 200
    assert _row(ep)["username"] == USERS[0]
    # Cùng trình duyệt, người khác đăng nhập rồi đăng ký → dòng chuyển sang người sau.
    assert client.post("/api/push/subscribe", json={"endpoint": ep, "keys": keys}, headers=b).status_code == 200
    assert _row(ep)["username"] == USERS[1]
    # A không gỡ được đăng ký đang thuộc B.
    r = client.post("/api/push/unsubscribe", json={"endpoint": ep}, headers=a)
    assert r.status_code == 200 and r.json()["removed"] is False and _row(ep)
    r = client.post("/api/push/unsubscribe", json={"endpoint": ep}, headers=b)
    assert r.json()["removed"] is True and _row(ep) is None

    bad = client.post("/api/push/subscribe", headers=a,
                      json={"endpoint": "https://evil.example/x" + "y" * 20, "keys": keys})
    assert bad.status_code == 400


@needs_db
def test_api_dang_nhap_ho_khong_duoc_dang_ky(users) -> None:
    from app.main import app

    client = TestClient(app)
    imp = {"Authorization": f"Bearer {create_impersonation_token(USERS[0], USERS[1])}"}
    ep = _endpoint()
    _key, _auth, keys = _receiver()
    r = client.post("/api/push/subscribe", json={"endpoint": ep, "keys": keys}, headers=imp)
    assert r.status_code == 403 and _row(ep) is None


def test_api_chua_dang_nhap_401() -> None:
    from app.main import app

    client = TestClient(app)
    assert client.get("/api/push/key").status_code == 401
    assert client.post("/api/push/subscribe", json={}).status_code == 401
    assert client.post("/api/push/unsubscribe", json={"endpoint": "x"}).status_code == 401


def test_sw_va_manifest_khong_luu_dem(tmp_path, monkeypatch) -> None:
    """sw.js + manifest tên cố định → `no-cache` như index.html; file thường giữ nguyên."""
    from fastapi import FastAPI

    from app.web_static import mount_spa

    for name, body in (("index.html", "<html></html>"), ("sw.js", "//"),
                       ("manifest.webmanifest", "{}"), ("logo-vrg.png", "x")):
        (tmp_path / name).write_text(body)
    monkeypatch.setenv("WEB_DIST_DIR", str(tmp_path))
    spa = FastAPI()
    assert mount_spa(spa, "test")
    client = TestClient(spa)
    for path in ("/sw.js", "/manifest.webmanifest"):
        r = client.get(path)
        assert r.status_code == 200 and r.headers["cache-control"] == "no-cache", path
    assert client.get("/manifest.webmanifest").headers["content-type"].startswith("application/manifest+json")
    assert "cache-control" not in client.get("/logo-vrg.png").headers
