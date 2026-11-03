"""Web Push (RFC 8030/8291/8292) with VAPID, using only `cryptography` and `requests` (already in Frappe).

Notifications reach installed AlphaX apps (Android, iPhone 16.4+ from the home screen, desktop browsers).
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import struct
import time
from urllib.parse import urlparse

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF


def b64u(data: bytes) -> str:
	return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def b64u_decode(text: str) -> bytes:
	return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def new_vapid_keys() -> tuple[str, str]:
	"""(private key PEM, public key base64url uncompressed point)."""
	key = ec.generate_private_key(ec.SECP256R1())
	pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()
	pub = key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
	return pem, b64u(pub)


def _hkdf(salt: bytes, ikm: bytes, info: bytes, length: int) -> bytes:
	return HKDF(algorithm=hashes.SHA256(), length=length, salt=salt, info=info).derive(ikm)


def encrypt(payload: bytes, p256dh: str, auth: str, salt: bytes | None = None, server_key=None) -> bytes:
	"""aes128gcm content coding (RFC 8188 + 8291): returns the request body."""
	ua_public = b64u_decode(p256dh)
	auth_secret = b64u_decode(auth)
	server_key = server_key or ec.generate_private_key(ec.SECP256R1())
	as_public = server_key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
	shared = server_key.exchange(ec.ECDH(), ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), ua_public))
	ikm = _hkdf(auth_secret, shared, b"WebPush: info\x00" + ua_public + as_public, 32)
	salt = salt or os.urandom(16)
	cek = _hkdf(salt, ikm, b"Content-Encoding: aes128gcm\x00", 16)
	nonce = _hkdf(salt, ikm, b"Content-Encoding: nonce\x00", 12)
	ciphertext = AESGCM(cek).encrypt(nonce, payload + b"\x02", None)
	return salt + struct.pack("!IB", 4096, len(as_public)) + as_public + ciphertext


def decrypt(body: bytes, ua_private, auth: str) -> bytes:
	"""Inverse of encrypt (used by tests)."""
	salt, idlen = body[:16], body[20]
	as_public = body[21:21 + idlen]
	ua_public = ua_private.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
	shared = ua_private.exchange(ec.ECDH(), ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), as_public))
	ikm = _hkdf(b64u_decode(auth), shared, b"WebPush: info\x00" + ua_public + as_public, 32)
	cek = _hkdf(salt, ikm, b"Content-Encoding: aes128gcm\x00", 16)
	nonce = _hkdf(salt, ikm, b"Content-Encoding: nonce\x00", 12)
	record = AESGCM(cek).decrypt(nonce, body[21 + idlen:], None)
	return record.rstrip(b"\x00")[:-1]


def vapid_header(endpoint: str, private_pem: str, public_b64: str, subject: str) -> str:
	url = urlparse(endpoint)
	header = b64u(json.dumps({"typ": "JWT", "alg": "ES256"}, separators=(",", ":")).encode())
	claims = b64u(json.dumps({"aud": f"{url.scheme}://{url.netloc}", "exp": int(time.time()) + 12 * 3600, "sub": subject},
							 separators=(",", ":")).encode())
	key = serialization.load_pem_private_key(private_pem.encode(), password=None)
	der = key.sign(f"{header}.{claims}".encode(), ec.ECDSA(hashes.SHA256()))
	r, s = decode_dss_signature(der)
	signature = b64u(r.to_bytes(32, "big") + s.to_bytes(32, "big"))
	return f"vapid t={header}.{claims}.{signature}, k={public_b64}"


def endpoint_hash(endpoint: str) -> str:
	return hashlib.sha256(endpoint.encode()).hexdigest()[:40]
