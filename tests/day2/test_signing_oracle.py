"""Oracle self-checks only. These do not prove the backend implements Day 2."""
import unittest

from signing_oracle import sign, signed_payload


class OracleTests(unittest.TestCase):
    def test_rfc4231_hmac_vector_through_exact_message(self):
        # Independent implementation check using stdlib's published algorithm.
        import hashlib
        import hmac
        self.assertEqual(
            hmac.new(b"Jefe", b"what do ya want for nothing?", hashlib.sha256).hexdigest(),
            "5bdcc146bf60754e6a042426089575c75a003f089d2739839dec58b964ec3843",
        )

    def test_canonical_bytes(self):
        import hashlib
        import hmac
        payload = {"z": [True, None, 1], "a": "\u00e9"}
        expected = hmac.new(b" public ", 'entity|{"a":"\u00e9","z":[true,null,1]}'.encode("utf-8"), hashlib.sha256).hexdigest()
        self.assertEqual(sign(" public ", "entity", payload), expected)
        self.assertEqual(sign(" public ", "entity", dict(reversed(list(payload.items())))), expected)
        self.assertNotEqual(sign("public", "entity", payload), expected)

    def test_cart_excludes_unsigned_fields_and_uses_active_total(self):
        response = dict(cart_merged=True, guest_token="guest", registered_user_id="user",
                        total_items=999, active_cart={"total_items": 1, "user_id": "user"}, write_rejection_code=None,
                        signature="ignored")
        payload = signed_payload("guest/cart-merge", response)
        self.assertEqual(payload["total_items"], 1)
        self.assertNotIn("signature", payload)
        self.assertNotIn("active_cart", payload)

    def test_missing_signed_fields_fail(self):
        with self.assertRaises(KeyError):
            signed_payload("qr", {"entity_id": "match-m1"})
        with self.assertRaises(KeyError):
            signed_payload("moderation/test", {"chat_room_id": "room", "kicked_users": [], "dlq_status": {"queue_depth": 0}})

    def test_qr_target_changes_signature(self):
        payload = {"entity_id": "match-m1", "short_url": "/q/m1-live", "target_route": "/live"}
        before = sign("public-test-salt", "match-m1", payload)
        payload["target_route"] = "/vod"
        self.assertNotEqual(before, sign("public-test-salt", "match-m1", payload))


if __name__ == "__main__":
    unittest.main()
