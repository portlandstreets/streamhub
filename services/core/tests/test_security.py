import os
import sys
import unittest
from pathlib import Path

# Add services/core to Python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from security import (
    create_access_token,
    decode_access_token,
    get_password_hash,
    verify_password,
)
from models import User


class TestSecurityAndAuth(unittest.TestCase):
    """Unit tests for password hashing, JWT tokens, and stream key generation."""

    def test_password_hashing_and_verification(self):
        raw_password = "SuperSecretPassword123!"
        hashed = get_password_hash(raw_password)

        self.assertNotEqual(raw_password, hashed)
        self.assertTrue(hashed.startswith("$2b$") or hashed.startswith("$2a$"))
        self.assertTrue(verify_password(raw_password, hashed))
        self.assertFalse(verify_password("WrongPassword999!", hashed))

    def test_jwt_token_generation_and_decode(self):
        payload = {"sub": "creator_alex", "user_id": 42, "role": "streamer"}
        token = create_access_token(payload)

        self.assertIsInstance(token, str)
        self.assertTrue(len(token) > 20)

        decoded = decode_access_token(token)
        self.assertIsNotNone(decoded)
        self.assertEqual(decoded.get("sub"), "creator_alex")
        self.assertEqual(decoded.get("user_id"), 42)
        self.assertEqual(decoded.get("role"), "streamer")
        self.assertIn("exp", decoded)

    def test_jwt_tampered_token(self):
        payload = {"sub": "creator_alex"}
        token = create_access_token(payload)
        tampered = token[:-4] + "fake"

        decoded = decode_access_token(tampered)
        self.assertIsNone(decoded)

    def test_jwt_empty_or_garbage_token(self):
        self.assertIsNone(decode_access_token("not-a-valid-jwt"))
        self.assertIsNone(decode_access_token(""))

    def test_stream_key_generation(self):
        key1 = User.generate_stream_key()
        key2 = User.generate_stream_key()

        self.assertTrue(key1.startswith("live_"))
        self.assertTrue(key2.startswith("live_"))
        self.assertNotEqual(key1, key2)
        self.assertGreater(len(key1), 20)


if __name__ == "__main__":
    unittest.main()
