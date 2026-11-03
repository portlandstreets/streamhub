import hashlib
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from blob_storage import BlobStorageManager


class TestBlobStorageAndCDN(unittest.TestCase):
    """Unit tests for BlobStorageManager: buckets, ETags, CDN simulation, and presigned URLs."""

    def setUp(self):
        # Use a temporary directory for test storage
        self.temp_dir = tempfile.TemporaryDirectory()
        self.manager = BlobStorageManager(base_dir=Path(self.temp_dir.name))

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_buckets_provisioning(self):
        buckets = self.manager.list_buckets()
        names = [b["name"] for b in buckets]
        self.assertIn("streamhub-vods", names)
        self.assertIn("streamhub-thumbnails", names)
        self.assertIn("streamhub-assets", names)

    def test_put_and_get_blob(self):
        content = b"TEST-STREAM-REPLAY-CHUNK-PAYLOAD-2026"
        expected_etag = f'"{hashlib.md5(content).hexdigest()}"'

        meta = self.manager.put_blob(
            bucket="streamhub-vods",
            key="recordings/test_vod.mp4",
            data=content,
            content_type="video/mp4",
        )

        self.assertEqual(meta["key"], "recordings/test_vod.mp4")
        self.assertEqual(meta["size"], len(content))
        self.assertEqual(meta["content_type"], "video/mp4")
        self.assertEqual(meta["etag"], expected_etag)
        self.assertTrue(meta["cdn_url"].startswith("/api/v1/storage/cdn/streamhub-vods/"))

    def test_presigned_url_generation_and_verification(self):
        bucket = "streamhub-assets"
        key = "badges/vip-partner.svg"
        presigned = self.manager.generate_presigned_url(bucket, key, expires_in=3600)

        self.assertIn("token=", presigned)
        self.assertIn("expires=", presigned)

        # Extract token and expires
        parts = presigned.split("?")
        params = dict(p.split("=") for p in parts[1].split("&"))
        token = params["token"]
        expires_ts = int(params["expires"])

        # Valid token
        is_valid = self.manager.verify_presigned_token(bucket, key, expires_ts, token)
        self.assertTrue(is_valid)

        # Tampered token
        tampered = self.manager.verify_presigned_token(bucket, key, expires_ts, "tampered_token_xyz")
        self.assertFalse(tampered)

        # Expired token
        past_ts = int(time.time()) - 100
        expired = self.manager.verify_presigned_token(bucket, key, past_ts, token)
        self.assertFalse(expired)

    def test_delete_blob(self):
        content = b"temporary-thumbnail"
        self.manager.put_blob("streamhub-thumbnails", "temp.jpg", content, "image/jpeg")

        deleted = self.manager.delete_blob("streamhub-thumbnails", "temp.jpg")
        self.assertTrue(deleted)

        # Second deletion should return False
        deleted_again = self.manager.delete_blob("streamhub-thumbnails", "temp.jpg")
        self.assertFalse(deleted_again)

    def test_cdn_cache_hit_and_purge(self):
        bucket = "streamhub-thumbnails"
        key = "sample-cover.svg"

        # Record first request (MISS)
        info1 = self.manager.record_cdn_request(bucket, key, bytes_sent=1024)
        self.assertIn(info1["status"], ["HIT", "MISS"])

        # Record second request (HIT)
        info2 = self.manager.record_cdn_request(bucket, key, bytes_sent=1024)
        self.assertEqual(info2["status"], "HIT")

        # Purge cache
        purged = self.manager.purge_cdn_cache("*")
        self.assertGreaterEqual(purged, 0)
        self.assertEqual(len(self.manager.edge_cache_entries), 0)


if __name__ == "__main__":
    unittest.main()
