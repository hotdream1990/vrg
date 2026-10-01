"""Mật mã Web Push THUẦN (không DB, không mạng) — tách khỏi `web_push.py` để test riêng từng byte.

- Mã hoá nội dung theo RFC 8291 (`Content-Encoding: aes128gcm`): ECDH P-256 với khoá của trình
  duyệt → HKDF-SHA256 → AES-128-GCM, một bản ghi duy nhất (nội dung < 4 KB).
- Chữ ký máy chủ theo RFC 8292 (VAPID): JWT ES256 ký bằng khoá riêng của hệ thống.

Chỉ dùng `cryptography` + `pyjwt` đã có sẵn trong image — KHÔNG thêm pywebpush/http-ece (image vá
lúc deploy gấp không cài lại gói).
"""

from __future__ import annotations

import base64
import os
import re
import time
from urllib.parse import urlsplit

import jwt
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

RECORD_SIZE = 4096  # rs trong header — nội dung gửi luôn nằm gọn trong MỘT bản ghi
VAPID_TTL_SECONDS = 12 * 3600  # RFC 8292: hạn JWT không quá 24 giờ
_CURVE = ec.SECP256R1()
_B64URL = re.compile(r"^[A-Za-z0-9_-]+={0,2}$")


def b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def b64url_decode(value: str) -> bytes:
    """base64url (có/không dấu `=`) → bytes. Ký tự lạ → ValueError (không lặng lẽ bỏ qua)."""
    s = (value or "").strip()
    if not _B64URL.match(s):
        raise ValueError("Không phải chuỗi base64url hợp lệ")
    s = s.rstrip("=")
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def public_point(key: ec.EllipticCurvePrivateKey) -> bytes:
    """Khoá công khai dạng điểm KHÔNG nén (65 byte, mở đầu 0x04) — dạng trình duyệt cần."""
    return key.public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint,
    )


def load_private_key(private_b64: str) -> ec.EllipticCurvePrivateKey:
    """Khoá riêng lưu dạng base64url của số bí mật 32 byte."""
    return ec.derive_private_key(int.from_bytes(b64url_decode(private_b64), "big"), _CURVE)


def generate_vapid_keypair() -> tuple[str, str]:
    """Cặp khoá VAPID mới → (public base64url 65 byte, private base64url 32 byte)."""
    key = ec.generate_private_key(_CURVE)
    secret = key.private_numbers().private_value.to_bytes(32, "big")
    return b64url_encode(public_point(key)), b64url_encode(secret)


def public_from_private(private_b64: str) -> str:
    return b64url_encode(public_point(load_private_key(private_b64)))


def check_receiver_keys(p256dh: bytes, auth: bytes) -> None:
    """Khoá trình duyệt gửi lên phải là điểm P-256 thật + auth 16 byte — sai thì ValueError."""
    if len(p256dh) != 65 or p256dh[0] != 0x04:
        raise ValueError("Khoá p256dh không đúng dạng điểm P-256 không nén")
    ec.EllipticCurvePublicKey.from_encoded_point(_CURVE, p256dh)  # điểm không nằm trên đường cong → lỗi
    if len(auth) != 16:
        raise ValueError("Khoá auth phải dài 16 byte")


def _hkdf(salt: bytes, ikm: bytes, info: bytes, length: int) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=length, salt=salt, info=info).derive(ikm)


def encrypt(plaintext: bytes, ua_public: bytes, auth_secret: bytes, *,
            as_private: ec.EllipticCurvePrivateKey | None = None,
            salt: bytes | None = None) -> bytes:
    """Mã hoá `plaintext` cho một trình duyệt (RFC 8291 §3–4) → thân request gửi dịch vụ push.

    `as_private`/`salt` chỉ truyền khi test (tái lập ví dụ Phụ lục A); bình thường mỗi lần gửi
    sinh khoá tạm + salt ngẫu nhiên mới.
    """
    as_private = as_private or ec.generate_private_key(_CURVE)
    salt = salt or os.urandom(16)
    as_public = public_point(as_private)
    ua_key = ec.EllipticCurvePublicKey.from_encoded_point(_CURVE, ua_public)
    ecdh_secret = as_private.exchange(ec.ECDH(), ua_key)
    ikm = _hkdf(auth_secret, ecdh_secret, b"WebPush: info\x00" + ua_public + as_public, 32)
    cek = _hkdf(salt, ikm, b"Content-Encoding: aes128gcm\x00", 16)
    nonce = _hkdf(salt, ikm, b"Content-Encoding: nonce\x00", 12)
    # 0x02 = dấu kết thúc bản ghi cuối (không đệm thêm).
    ciphertext = AESGCM(cek).encrypt(nonce, plaintext + b"\x02", None)
    header = salt + RECORD_SIZE.to_bytes(4, "big") + bytes([len(as_public)]) + as_public
    return header + ciphertext


def vapid_authorization(endpoint: str, private_b64: str, public_b64: str, subject: str,
                        now: int | None = None) -> str:
    """Header `Authorization` VAPID cho một endpoint: `vapid t=<JWT ES256>, k=<khoá công khai>`.

    `aud` = gốc (scheme://host[:port]) của dịch vụ push — mỗi dịch vụ một JWT.
    """
    parts = urlsplit(endpoint)
    host = parts.netloc.rsplit("@", 1)[-1]
    issued = int(now if now is not None else time.time())
    claims = {"aud": f"{parts.scheme}://{host}", "exp": issued + VAPID_TTL_SECONDS, "sub": subject}
    token = jwt.encode(claims, load_private_key(private_b64), algorithm="ES256")
    return f"vapid t={token}, k={public_b64}"
