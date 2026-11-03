import json
import unittest

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from alphax_hr import push


class PushCrypto(unittest.TestCase):
    def test_round_trip(self):
        ua = ec.generate_private_key(ec.SECP256R1())
        p256dh = push.b64u(ua.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint))
        auth = push.b64u(b"0123456789abcdef")
        body = push.encrypt(json.dumps({"title": "Leave approved"}).encode(), p256dh, auth)
        self.assertEqual(json.loads(push.decrypt(body, ua, auth))["title"], "Leave approved")
        self.assertEqual(body[16:20], b"\x00\x00\x10\x00")  # record size 4096

    def test_vapid(self):
        pem, pub = push.new_vapid_keys()
        self.assertEqual(len(push.b64u_decode(pub)), 65)
        h = push.vapid_header("https://fcm.googleapis.com/fcm/send/abc", pem, pub, "mailto:hr@example.com")
        self.assertTrue(h.startswith("vapid t=") and f"k={pub}" in h)
        jwt = h.split("t=")[1].split(",")[0]
        claims = json.loads(push.b64u_decode(jwt.split(".")[1]))
        self.assertEqual(claims["aud"], "https://fcm.googleapis.com")
        self.assertEqual(len(push.b64u_decode(jwt.split(".")[2])), 64)


if __name__ == "__main__":
    unittest.main()
