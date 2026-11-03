import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import jwt
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

core_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(core_dir))
if 'services' in sys.modules and not hasattr(sys.modules['services'], 'register_user'):
    del sys.modules['services']
os.environ['TESTING'] = '1'

_test_storage = tempfile.TemporaryDirectory(prefix="streamhub-auth-tests-")
_original_database_url = os.environ.get("DATABASE_URL")
_original_storage_dir = os.environ.get("STORAGE_DIR")
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["STORAGE_DIR"] = _test_storage.name

from database import get_db
from controllers import auth as auth_controller
from main import app
from models import Base
from security import ALGORITHM, SECRET_KEY, decode_access_token

if _original_database_url is None:
    os.environ.pop("DATABASE_URL", None)
else:
    os.environ["DATABASE_URL"] = _original_database_url

if _original_storage_dir is None:
    os.environ.pop("STORAGE_DIR", None)
else:
    os.environ["STORAGE_DIR"] = _original_storage_dir


class TestAuthenticationAndAuthorizationAPI(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False)

        async def override_get_db():
            async with self.session_factory() as session:
                yield session

        app.dependency_overrides[get_db] = override_get_db
        self.client = AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        )

    async def asyncTearDown(self):
        await self.client.aclose()
        app.dependency_overrides.clear()
        await self.engine.dispose()

    async def register_user(self, username="qa_streamer", email="qa@example.com"):
        return await self.client.post(
            "/api/v1/auth/register",
            json={
                "username": username,
                "email": email,
                "password": "SecurePass123!",
            },
        )

    async def test_registration_creates_user_and_returns_valid_bearer_token(self):
        response = await self.register_user()

        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(body["username"], "qa_streamer")
        self.assertEqual(body["email"], "qa@example.com")
        self.assertEqual(body["token_type"], "bearer")
        self.assertTrue(body["access_token"])
        self.assertNotIn("password", body)
        self.assertNotIn("hashed_password", body)
        self.assertEqual(decode_access_token(body["access_token"])["sub"], str(body["user_id"]))

    async def test_registration_rejects_duplicate_username_and_email(self):
        self.assertEqual((await self.register_user()).status_code, 201)

        duplicate_username = await self.register_user(
            username="qa_streamer",
            email="another@example.com",
        )
        duplicate_email = await self.register_user(
            username="another_streamer",
            email="qa@example.com",
        )

        self.assertEqual(duplicate_username.status_code, 400)
        self.assertEqual(duplicate_email.status_code, 400)

    async def test_registration_rejects_invalid_email_username_and_password(self):
        invalid_payloads = [
            {"username": "qa_streamer", "email": "not-an-email", "password": "SecurePass123!"},
            {"username": "ab", "email": "qa@example.com", "password": "SecurePass123!"},
            {"username": "qa_streamer", "email": "qa@example.com", "password": "short"},
        ]

        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                response = await self.client.post("/api/v1/auth/register", json=payload)
                self.assertEqual(response.status_code, 422)

    async def test_login_accepts_correct_credentials_and_rejects_invalid_credentials(self):
        await self.register_user()

        valid_login = await self.client.post(
            "/api/v1/auth/login",
            json={"username": "qa_streamer", "password": "SecurePass123!"},
        )
        wrong_password = await self.client.post(
            "/api/v1/auth/login",
            json={"username": "qa_streamer", "password": "WrongPassword123!"},
        )
        unknown_user = await self.client.post(
            "/api/v1/auth/login",
            json={"username": "missing_user", "password": "SecurePass123!"},
        )

        self.assertEqual(valid_login.status_code, 200)
        self.assertEqual(valid_login.json()["token_type"], "bearer")
        self.assertIsNotNone(decode_access_token(valid_login.json()["access_token"]))
        self.assertEqual(wrong_password.status_code, 401)
        self.assertEqual(unknown_user.status_code, 401)

    async def test_profile_requires_a_valid_token(self):
        for headers in (
            {},
            {"Authorization": "Bearer not-a-token"},
            {"Authorization": "Bearer "},
        ):
            with self.subTest(headers=headers):
                response = await self.client.get("/api/users/me", headers=headers)
                self.assertEqual(response.status_code, 401)

    async def test_profile_returns_authenticated_user_without_password_hash(self):
        registration = await self.register_user()
        token = registration.json()["access_token"]

        response = await self.client.get(
            "/api/users/me",
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["username"], "qa_streamer")
        self.assertNotIn("hashed_password", response.json())

    async def test_profile_rejects_expired_malformed_and_unknown_user_tokens(self):
        tokens = [
            jwt.encode(
                {"sub": "1", "exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
                SECRET_KEY,
                algorithm=ALGORITHM,
            ),
            jwt.encode(
                {"sub": "not-an-integer", "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
                SECRET_KEY,
                algorithm=ALGORITHM,
            ),
            jwt.encode(
                {"sub": "9999", "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
                SECRET_KEY,
                algorithm=ALGORITHM,
            ),
        ]

        for token in tokens:
            with self.subTest(token=token):
                response = await self.client.get(
                    "/api/users/me",
                    headers={"Authorization": f"Bearer {token}"},
                )
                self.assertEqual(response.status_code, 401)

    async def test_protected_stream_creation_requires_authentication(self):
        response = await self.client.post(
            "/api/streams",
            json={"title": "Private channel"},
        )

        self.assertEqual(response.status_code, 401)

    async def test_user_cannot_modify_another_users_stream(self):
        owner_registration = await self.register_user(
            username="stream_owner",
            email="owner@example.com",
        )
        other_registration = await self.register_user(
            username="other_user",
            email="other@example.com",
        )
        owner_token = owner_registration.json()["access_token"]
        other_token = other_registration.json()["access_token"]
        owner_streams = await self.client.get(
            "/api/users/me/streams",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        stream_id = owner_streams.json()["items"][0]["id"]

        response = await self.client.put(
            f"/api/streams/{stream_id}",
            headers={"Authorization": f"Bearer {other_token}"},
            json={"title": "Unauthorized edit"},
        )

        self.assertEqual(response.status_code, 403)

    async def test_oauth_provider_list_and_authorization_urls(self):
        providers_response = await self.client.get("/api/v1/auth/oauth/providers")
        self.assertEqual(providers_response.status_code, 200)
        self.assertEqual(
            {provider["id"] for provider in providers_response.json()["providers"]},
            {"google", "github", "microsoft"},
        )

        for provider in ("google", "github", "microsoft"):
            with self.subTest(provider=provider):
                response = await self.client.get(f"/api/v1/auth/oauth/{provider}/url")
                self.assertEqual(response.status_code, 200)
                body = response.json()
                self.assertEqual(body["provider"], provider)
                self.assertTrue(body["state"])
                self.assertEqual(
                    parse_qs(urlparse(body["authorization_url"]).query)["state"],
                    [body["state"]],
                )

    async def test_oauth_endpoints_reject_unsupported_providers(self):
        url_response = await self.client.get("/api/v1/auth/oauth/unknown/url")
        login_response = await self.client.post("/api/v1/auth/oauth/unknown/login")

        self.assertEqual(url_response.status_code, 400)
        self.assertEqual(login_response.status_code, 400)

    async def test_oauth_direct_login_issues_a_valid_token(self):
        response = await self.client.post(
            "/api/v1/auth/oauth/google/login",
            json={
                "email": "oauth@example.com",
                "username": "oauth_user",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["provider"], "google")
        self.assertTrue(response.json()["oauth_verified"])
        self.assertEqual(
            decode_access_token(response.json()["access_token"])["sub"],
            str(response.json()["user_id"]),
        )

    async def test_oauth_callback_returns_frontend_redirect_with_token(self):
        response = await self.client.get(
            "/api/v1/auth/oauth/github/callback",
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 302)
        redirect_query = parse_qs(urlparse(response.headers["location"]).query)
        self.assertEqual(redirect_query["provider"], ["github"])
        self.assertEqual(redirect_query["username"], ["github_broadcaster"])
        self.assertIsNotNone(decode_access_token(redirect_query["oauth_token"][0]))

    async def test_google_oauth_callback_uses_mocked_provider_profile(self):
        token_response = BytesIO(b'{"access_token":"mock-provider-token"}')
        profile_response = BytesIO(
            b'{"email":"verified@example.com","name":"OAuth Verified"}'
        )

        with (
            patch.object(auth_controller, "GOOGLE_CLIENT_ID", "test-client-id"),
            patch.object(auth_controller, "GOOGLE_CLIENT_SECRET", "test-client-secret"),
            patch.object(
                auth_controller.urllib.request,
                "urlopen",
                side_effect=[token_response, profile_response],
            ) as urlopen,
        ):
            response = await self.client.get(
                "/api/v1/auth/oauth/google/callback",
                params={"code": "mock-authorization-code", "state": "mock-state"},
                follow_redirects=False,
            )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(urlopen.call_count, 2)
        redirect_query = parse_qs(urlparse(response.headers["location"]).query)
        self.assertEqual(redirect_query["username"], ["oauthverified"])
        self.assertIsNotNone(decode_access_token(redirect_query["oauth_token"][0]))


if __name__ == "__main__":
    unittest.main()
