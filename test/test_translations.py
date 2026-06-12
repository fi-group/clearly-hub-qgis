# coding=utf-8
"""Safe Translations Test.

.. note:: This program is free software; you can redistribute it and/or modify
     it under the terms of the GNU General Public License as published by
     the Free Software Foundation; either version 2 of the License, or
     (at your option) any later version.

"""
from .utilities import get_qgis_app

__author__ = 'ismailsunni@yahoo.co.id'
__date__ = '12/10/2011'
__copyright__ = ('Copyright 2012, Australia Indonesia Facility for '
                 'Disaster Reduction')
import shutil
import subprocess
import unittest
import os

from qgis.PyQt.QtCore import QCoreApplication, QTranslator

QGIS_APP = get_qgis_app()

# Locate lrelease once at module level; None means the binary is absent.
_LRELEASE = (
    shutil.which('lrelease-qt6')
    or shutil.which('lrelease-qt5')
    or shutil.which('lrelease')
)


class SafeTranslationsTest(unittest.TestCase):
    """Test translations work."""

    def setUp(self):
        """Runs before each test."""
        if 'LANG' in iter(os.environ.keys()):
            os.environ.__delitem__('LANG')

    def tearDown(self):
        """Runs after each test."""
        if 'LANG' in iter(os.environ.keys()):
            os.environ.__delitem__('LANG')

    def test_qgis_translations(self):
        """Test that translations work.

        The repository ships af.ts (source) but not the compiled af.qm.
        This test compiles af.ts -> af.qm at runtime so the assertion is
        meaningful.  The test is skipped when lrelease is not installed.
        """
        if _LRELEASE is None:
            self.skipTest(
                'lrelease not found on PATH; install Qt tools to run '
                'translation tests (e.g. qttools5-dev-tools or qt6-tools).'
            )

        i18n_dir = os.path.abspath(
            os.path.join(__file__, os.path.pardir, os.path.pardir, 'i18n')
        )
        ts_path = os.path.join(i18n_dir, 'af.ts')
        qm_path = os.path.join(i18n_dir, 'af.qm')

        try:
            subprocess.run(
                [_LRELEASE, ts_path, '-qm', qm_path],
                check=True,
                capture_output=True,
            )

            translator = QTranslator()
            loaded = translator.load(qm_path)
            self.assertTrue(loaded, f'QTranslator failed to load {qm_path}')
            QCoreApplication.installTranslator(translator)

            expected_message = 'Goeie more'
            real_message = QCoreApplication.translate('@default', 'Good morning')
            self.assertEqual(real_message, expected_message)
        finally:
            if os.path.exists(qm_path):
                os.remove(qm_path)


if __name__ == "__main__":
    suite = unittest.makeSuite(SafeTranslationsTest)
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite)
