"""Authentication management for the ClearlyHub QGIS plugin.

Handles OAuth2 configuration, login/logout processes
and retrieval of authenticated user information.
"""
import json
from qgis.core import QgsApplication, QgsAuthMethodConfig
from qgis.PyQt.QtCore import QSettings

from .constants import (
    AUTHCFG_ENTRY,
    OAUTH_AUTH_URL,
    OAUTH_CLIENT_ID,
    OAUTH_TOKEN_URL,
    REDIRECT_URL,
)


class AuthManager:
    """Manage QGIS OAuth2 auth configuration for ClearlyHub."""

    AUTHCFG_ENTRY = AUTHCFG_ENTRY
    AUTH_URL = OAUTH_AUTH_URL
    TOKEN_URL = OAUTH_TOKEN_URL
    CLIENT_ID = OAUTH_CLIENT_ID
    REDIRECT_URL = REDIRECT_URL

    def __init__(self):
        """Initialize settings storage and QGIS auth manager handles."""
        self.settings = QSettings()
        self.auth_manager = QgsApplication.authManager()

    def get_authcfg_id(self):
        """ Return the stored auth config ID, if available."""
        return self.settings.value(self.AUTHCFG_ENTRY)

    def has_authcfg(self) -> bool:
        """Check if a valid auth config ID is stored."""
        return bool(self.get_authcfg_id())

    def has_persisted_session(self) -> bool:
        """Check whether the stored OAuth config already contains token state."""
        oauth_config = self.get_current_oauth_config() or {}
        token_fields = (
            "accessToken",
            "access_token",
            "refreshToken",
            "refresh_token",
        )
        return any(bool(oauth_config.get(field)) for field in token_fields)

    def setup_oauth2(self, communication=None) -> bool:
        """Create or reuse a compatible OAuth2 auth configuration.

        The method first attempts to reuse an existing ``clearlyhub`` auth config
        when all relevant OAuth values match the current constants. If the stored
        config is stale or incompatible, it is removed and recreated.

        Args:
            communication: Optional communication object reserved for future use.

        Returns:
            True when a valid auth config is available and stored, otherwise False.
        """
        # Reuse existing config only when it matches the active OAuth settings.
        for config_id, config in self.auth_manager.availableAuthMethodConfigs().items():
            if config.name() == "clearlyhub":
                oauth_config = config.configMap().get("oauth2config")
                if oauth_config:
                    try:
                        existing = json.loads(oauth_config)
                    except (TypeError, ValueError):
                        existing = {}

                    if (
                        existing.get("clientId") == self.CLIENT_ID
                        and existing.get("grantFlow") == 3
                        and existing.get("requestUrl") == self.AUTH_URL
                        and existing.get("tokenUrl") == self.TOKEN_URL
                        and existing.get("redirectUrl") == self.REDIRECT_URL
                        and existing.get("scope") == "email openid profile"
                    ):
                        self.settings.setValue(self.AUTHCFG_ENTRY, config_id)
                        return True

                # Existing config is stale/incompatible, recreate it.
                self.auth_manager.removeAuthenticationConfig(config_id)
                break

        authcfg = QgsAuthMethodConfig()
        authcfg.setMethod("OAuth2")
        authcfg.setName("clearlyhub")

        config_map = {
            "clientId": self.CLIENT_ID,
            "grantFlow": 3,
            "redirectHost": "localhost",
            "redirectPort": 7070,
            "redirectUrl": self.REDIRECT_URL,
            "requestUrl": self.AUTH_URL,
            "tokenUrl": self.TOKEN_URL,
            "refreshTokenUrl": self.TOKEN_URL,
            "scope": "email openid profile",
            "persistToken": True,
            "queryPairs": {}
        }

        authcfg.setConfigMap({"oauth2config": json.dumps(config_map)})
        self.auth_manager.storeAuthenticationConfig(authcfg)

        new_authcfg_id = authcfg.id()
        if not new_authcfg_id:
            return False

        self.settings.setValue(self.AUTHCFG_ENTRY, new_authcfg_id)
        return True

    def remove_authcfg(self):
        """Remove stored auth config."""
        authcfg_id = self.get_authcfg_id()
        if authcfg_id:
            self.auth_manager.removeAuthenticationConfig(authcfg_id)
        self.settings.remove(self.AUTHCFG_ENTRY)

    def expected_redirect_uri(self) -> str:
        """Return the redirect URI QGIS will build for localhost OAuth flows."""
        path = (self.REDIRECT_URL or "").lstrip("/")
        return f"http://127.0.0.1:7070/{path}" if path else "http://127.0.0.1:7070/"

    def get_current_oauth_config(self):
        """Return parsed oauth2config map for the active authcfg id, if available."""
        authcfg_id = self.get_authcfg_id()
        if not authcfg_id:
            return None

        config = QgsAuthMethodConfig()
        if not self.auth_manager.loadAuthenticationConfig(
                authcfg_id, config, True):
            return None

        oauth_config = config.configMap().get("oauth2config")
        if not oauth_config:
            return None

        try:
            return json.loads(oauth_config)
        except (TypeError, ValueError):
            return None
