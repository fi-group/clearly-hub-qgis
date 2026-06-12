import unittest
from unittest.mock import patch

from backend.auth import AuthManager


class AuthManagerSessionStateTest(unittest.TestCase):
    def test_has_persisted_session_with_access_token(self):
        with patch.object(AuthManager, "get_current_oauth_config", return_value={"accessToken": "token"}):
            self.assertTrue(AuthManager().has_persisted_session())

    def test_has_persisted_session_with_refresh_token(self):
        with patch.object(AuthManager, "get_current_oauth_config", return_value={"refreshToken": "refresh"}):
            self.assertTrue(AuthManager().has_persisted_session())

    def test_has_persisted_session_without_tokens(self):
        with patch.object(AuthManager, "get_current_oauth_config", return_value={"clientId": "abc"}):
            self.assertFalse(AuthManager().has_persisted_session())


if __name__ == "__main__":
    unittest.main()
