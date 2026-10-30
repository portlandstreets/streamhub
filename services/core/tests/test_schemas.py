import sys
import unittest
from pathlib import Path
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from schemas import (
    MediaMTXAuthPayload,
    StreamCreate,
    StreamUpdate,
    UserLogin,
    UserRegister,
)


class TestSchemasValidation(unittest.TestCase):
    """Unit tests for Pydantic request/response payload validation."""

    def test_user_register_valid(self):
        user = UserRegister(
            username="streamer_pro",
            email="streamer@streamhub.app",
            password="StrongPassword2026!",
        )
        self.assertEqual(user.username, "streamer_pro")
        self.assertEqual(user.email, "streamer@streamhub.app")

    def test_user_register_invalid_email(self):
        with self.assertRaises(ValidationError):
            UserRegister(
                username="streamer_pro",
                email="not-an-email",
                password="StrongPassword2026!",
            )

    def test_user_register_short_password(self):
        with self.assertRaises(ValidationError):
            UserRegister(
                username="streamer_pro",
                email="streamer@streamhub.app",
                password="short",  # Min length is 8
            )

    def test_user_register_short_username(self):
        with self.assertRaises(ValidationError):
            UserRegister(
                username="a",  # Min length is 3
                email="streamer@streamhub.app",
                password="StrongPassword2026!",
            )

    def test_stream_create_valid(self):
        stream = StreamCreate(
            title="Late Night Cyberpunk 2077 Coding",
            description="Building microservices live on stream",
        )
        self.assertEqual(stream.title, "Late Night Cyberpunk 2077 Coding")
        self.assertTrue(len(stream.description) > 0)

    def test_stream_create_empty_title(self):
        with self.assertRaises(ValidationError):
            StreamCreate(title="")

    def test_mediamtx_auth_payload(self):
        payload = MediaMTXAuthPayload(
            action="publish",
            path="live_channel_01",
            ip="127.0.0.1",
            user="streamer1",
            password="secret_stream_key",
        )
        self.assertEqual(payload.action, "publish")
        self.assertEqual(payload.path, "live_channel_01")


if __name__ == "__main__":
    unittest.main()
