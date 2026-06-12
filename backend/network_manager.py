from typing import Optional

from qgis.core import QgsApplication, QgsBlockingNetworkRequest
from qgis.PyQt.QtCore import QUrl
from qgis.PyQt.QtNetwork import QNetworkRequest

# QgsBlockingNetworkRequest.NoError moved into ErrorCode enum in QGIS 4.
try:
    _BLOCK_NO_ERROR = QgsBlockingNetworkRequest.ErrorCode.NoError
except AttributeError:
    _BLOCK_NO_ERROR = QgsBlockingNetworkRequest.NoError


class NetworkManager:
    def __init__(self, url: str, auth_cfg: Optional[str] = None):
        self._url = url
        self._auth_cfg = auth_cfg
        self._auth_manager = QgsApplication.authManager()

    def fetch(self):
        request = QNetworkRequest(QUrl(self._url))
        request.setHeader(
            QNetworkRequest.KnownHeaders.ContentTypeHeader, "application/json"
        )

        access_token = None
        if self._auth_cfg:
            if not self._auth_manager.updateNetworkRequest(request, self._auth_cfg):
                return False, "Failed to apply authentication to request.", None, None

            auth_header = bytes(request.rawHeader(b"Authorization")).decode("utf-8")
            if auth_header.startswith("Bearer "):
                access_token = auth_header[len("Bearer "):]

        blocking = QgsBlockingNetworkRequest()
        error = blocking.get(request)

        if error != _BLOCK_NO_ERROR:
            return False, blocking.errorMessage(), None, access_token

        payload = bytes(blocking.reply().content())
        return True, None, payload, access_token