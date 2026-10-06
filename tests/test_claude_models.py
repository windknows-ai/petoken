import json
import tempfile
import unittest
from pathlib import Path

import claude_models


def entry(model_id, name, section='main', efforts=('low', 'high'), badge=None):
    data = dict(id=model_id, name=name, section=section,
                thinking=dict(type='effort', effort_options=[dict(id=e, name=e.title()) for e in efforts]))
    if badge:
        data['badge'] = dict(message=badge)
    return data


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name) / 'cache' / 'model-catalog'
        self.folder.mkdir(parents=True)

    def write(self, name, surface, fetched, models):
        (self.folder / name).write_text(json.dumps(dict(version=2, fetchedAt=fetched, catalog=dict(
            surface=surface, config=dict(id=surface, models=models)))), encoding='utf-8')

    def test_newest_cli_catalog_in_picker_order(self):
        self.write('a-cc.json', 'cc', 100, [entry('claude-old', 'Old')])
        self.write('b-cc.json', 'cc', 200, [entry('claude-more', 'More', section='overflow'),
                                           entry('claude-new', 'New 9', badge='Requires usage credits'),
                                           entry('claude-tiny', 'Tiny', efforts=())])
        self.write('c-ccd.json', 'ccd', 300, [entry('claude-desktop-only', 'Desktop')])
        models = claude_models.catalog(self.temp.name)
        self.assertEqual([m['id'] for m in models], ['claude-new', 'claude-tiny', 'claude-more'])
        self.assertEqual(models[0]['badge'], 'Requires usage credits')
        self.assertEqual(claude_models.efforts_for('claude-new', models), (('low', 'Low'), ('high', 'High')))
        self.assertEqual(claude_models.efforts_for('claude-tiny', models), ())
        self.assertEqual(claude_models.efforts_for('', models), claude_models.GENERIC_EFFORTS)
        self.assertIsNone(claude_models.find('claude-old', models))         # Retired: gone.

    def test_desktop_copy_then_built_in_fallback(self):
        self.write('x-ccd.json', 'ccd', 1, [entry('claude-desktop', 'Desktop')])
        self.assertEqual([m['id'] for m in claude_models.catalog(self.temp.name)], ['claude-desktop'])
        (self.folder / 'x-ccd.json').write_text('{broken', encoding='utf-8')
        self.assertEqual([m['id'] for m in claude_models.catalog(self.temp.name)],
                         [m['id'] for m in claude_models.FALLBACK])


if __name__ == '__main__':
    unittest.main()
