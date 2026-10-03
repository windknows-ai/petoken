"""Packaged QA dispatch precedes live startup and personal preference access."""
import unittest
from unittest.mock import patch

import widget


class PreviewEntrypointTests(unittest.TestCase):
    def test_dispatch_before_live_startup(self):
        arguments = ['--count', '2', '--language', 'zh_CN', '--expand', '1']
        with patch('widget.sys.argv', ['petoken', '--preview-v1-3', *arguments]), \
                patch('tools.preview_v1_3.main', return_value=7) as preview, \
                patch('widget.QApplication', side_effect=AssertionError('Live Qt startup')), \
                patch('widget.Panel', side_effect=AssertionError('Live provider startup')), \
                patch('widget.QLockFile', side_effect=AssertionError('Personal instance lock')), \
                patch('widget.PREF_DIR') as preferences:
            self.assertEqual(widget.main(), 7)
            preview.assert_called_once_with(arguments)
            preferences.mkdir.assert_not_called()


if __name__ == '__main__':
    unittest.main()
