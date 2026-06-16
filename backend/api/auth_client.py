"""Authentication API client."""

import json

from .client import Client
from ..auth import AuthManager
from ..user import AuthenticatedUser
from ..constants import OAUTH_USERINFO_URL
from ..network_manager import NetworkManager


class AuthClient(Client):
    """HTTP client for authentication endpoints."""

    def get_authenticated_user(self, interactive=False):
        """Fetch authenticated user info from OAuth userinfo endpoint.

        Args:
            interactive: When True, allow OAuth setup to create or activate the
                login flow. When False, only reuse an already persisted session.

        Returns:
            AuthenticatedUser instance if authenticated, None otherwise.
        """
        auth_manager = AuthManager()
        if interactive:
            if not auth_manager.setup_oauth2():
                print("OAuth setup failed.")
                return None
        elif not auth_manager.has_authcfg():
            return None

        authcfg_id = auth_manager.get_authcfg_id()
        if not authcfg_id:
            print("No auth config ID available.")
            return None

        # Use NetworkManager with correct parameters: URL, auth_cfg
        network_manager = NetworkManager(
            OAUTH_USERINFO_URL, auth_cfg=authcfg_id)
        success, error, payload, token = network_manager.fetch()

        if not success or not payload:
            print(f"Failed to retrieve user info: {error}")
            return None

        try:
            user_info = json.loads(payload.decode("utf-8"))
            user = AuthenticatedUser.from_user_info(
                user_info,
                token=token,
                authcfg_id=authcfg_id,
            )
            return user
        except (json.JSONDecodeError, ValueError) as e:
            print(f"Failed to parse user info JSON: {e}")
            return None
