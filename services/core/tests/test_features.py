import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from features import FLAG_DEFINITIONS, PLAN_DEFAULTS


class TestFeatureFlagsAndPlans(unittest.TestCase):
    """Unit tests for B6 Feature Flags and subscription tier matrices."""

    def test_plan_tiers_defined(self):
        self.assertIn("free", PLAN_DEFAULTS)
        self.assertIn("premium", PLAN_DEFAULTS)
        self.assertIn("partner", PLAN_DEFAULTS)

    def test_flag_definitions_structure(self):
        self.assertGreater(len(FLAG_DEFINITIONS), 5)
        for flag_key, meta in FLAG_DEFINITIONS.items():
            self.assertIn("name", meta)
            self.assertIn("description", meta)
            self.assertIn("category", meta)
            self.assertIn("default_for", meta)
            self.assertIsInstance(meta["default_for"], list)

    def test_premium_lounge_flag_entitlement(self):
        premium_access = FLAG_DEFINITIONS.get("premium_page_access")
        self.assertIsNotNone(premium_access)
        # Free users should not have access by default
        self.assertNotIn("free", premium_access["default_for"])
        # Premium and Partner must have access
        self.assertIn("premium", premium_access["default_for"])
        self.assertIn("partner", premium_access["default_for"])

    def test_transcode_1080p60_entitlement(self):
        transcode_flag = FLAG_DEFINITIONS.get("1080p60_transcode")
        self.assertIsNotNone(transcode_flag)
        self.assertNotIn("free", transcode_flag["default_for"])
        self.assertIn("premium", transcode_flag["default_for"])


if __name__ == "__main__":
    unittest.main()
