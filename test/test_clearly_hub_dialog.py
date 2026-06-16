# coding=utf-8
"""Dialog test.

.. note:: This program is free software; you can redistribute it and/or modify
     it under the terms of the GNU General Public License as published by
     the Free Software Foundation; either version 2 of the License, or
     (at your option) any later version.

"""

__author__ = 'support@futureinsight.nl'
__date__ = '2026-02-19'
__copyright__ = 'Copyright 2026, Future Insight'

import unittest

from .utilities import get_qgis_app

try:
    from ..clearly_hub_dialog import ClearlyHubDialog
except ImportError:
    from clearly_hub_dialog import ClearlyHubDialog

QGIS_APP = get_qgis_app()


class ClearlyHubDialogTest(unittest.TestCase):
    """Test dialog behavior for the current main window UI."""

    def setUp(self):
        """Runs before each test."""
        self.dialog = ClearlyHubDialog(None)

    def tearDown(self):
        """Runs after each test."""
        self.dialog = None

    def test_dialog_has_expected_widgets(self):
        """Dialog exposes the key widgets from frontend/ui/main_window.ui."""
        self.assertIsNotNone(self.dialog.loginButton)
        self.assertIsNotNone(self.dialog.tabWidget)
        self.assertEqual(self.dialog.loginButton.text(), "Login")

    def test_login_button_emits_login_requested_when_logged_out(self):
        """Clicking login while logged out should emit login_requested only."""
        observed = {"login": 0, "logout": 0}

        self.dialog.login_requested.connect(
            lambda: observed.__setitem__(
                "login", observed["login"] + 1))
        self.dialog.logout_requested.connect(
            lambda: observed.__setitem__(
                "logout", observed["logout"] + 1))

        self.dialog.loginButton.click()

        self.assertEqual(observed["login"], 1)
        self.assertEqual(observed["logout"], 0)

    def test_login_button_emits_logout_requested_when_logged_in(self):
        """Clicking login while logged in should emit logout_requested only."""
        observed = {"login": 0, "logout": 0}

        self.dialog.login_requested.connect(
            lambda: observed.__setitem__(
                "login", observed["login"] + 1))
        self.dialog.logout_requested.connect(
            lambda: observed.__setitem__(
                "logout", observed["logout"] + 1))

        self.dialog.current_user = object()
        self.dialog.refresh_auth_button_text()

        self.assertEqual(self.dialog.loginButton.text(), "Logout")
        self.dialog.loginButton.click()

        self.assertEqual(observed["login"], 0)
        self.assertEqual(observed["logout"], 1)


if __name__ == "__main__":
    suite = unittest.makeSuite(ClearlyHubDialogTest)
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite)
