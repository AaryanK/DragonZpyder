import os
import unittest
from unittest.mock import patch

from dragonzpyder.config import ConfigError, DragonZpyderConfig


class ConfigTests(unittest.TestCase):
    def test_missing_base_url_fails_clearly(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(
                ConfigError, "DRAGONZPYDER_OPERLY_BASE_URL is required"
            ):
                DragonZpyderConfig.from_env()

    def test_remote_http_is_rejected(self):
        with patch.dict(
            os.environ,
            {"DRAGONZPYDER_OPERLY_BASE_URL": "http://example.com"},
            clear=True,
        ):
            with self.assertRaisesRegex(ConfigError, "must use https"):
                DragonZpyderConfig.from_env()

    def test_valid_https_configuration(self):
        with patch.dict(
            os.environ,
            {
                "DRAGONZPYDER_OPERLY_BASE_URL": "https://operly.example.com/",
                "DRAGONZPYDER_REQUEST_TIMEOUT_SECONDS": "15",
            },
            clear=True,
        ):
            config = DragonZpyderConfig.from_env()

        self.assertEqual(config.operly_base_url, "https://operly.example.com")
        self.assertEqual(config.request_timeout_seconds, 15.0)


if __name__ == "__main__":
    unittest.main()
