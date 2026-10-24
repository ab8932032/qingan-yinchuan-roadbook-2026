from pathlib import Path
from html.parser import HTMLParser
import json
import unittest

ROOT = Path(__file__).resolve().parents[1]

def read_data(file, prefix):
    return json.loads((ROOT / file).read_text(encoding='utf-8').removeprefix(prefix).rstrip(';\n'))

class ArchiveMarkup(HTMLParser):
    def handle_starttag(self, tag, attrs):
        assert tag not in {'script','style','iframe','form','input','button','img','video'}, tag
        for name, value in attrs:
            assert name in {'href','rel','target'}, name
            if name == 'href':
                assert value.startswith(('https://','http://')), value

class JourneyArchiveTests(unittest.TestCase):
    def test_all_original_entries_are_reachable_in_the_new_journey(self):
        archive = read_data('scripts/journey-archive.js','window.JOURNEY_ARCHIVE = ')
        atlas = read_data('scripts/atlas-data.js','window.ROADBOOK = ')
        places = {p['id'] for p in atlas['places']}
        self.assertEqual(set(archive['byPlace']),places)
        reachable = set(archive['shared'] + archive['unused'])
        for keys in archive['byPlace'].values():
            self.assertTrue(keys)
            reachable.update(keys)
        self.assertEqual(reachable,set(archive['entries']))
        self.assertEqual(len([k for k in reachable if k.startswith('spot-')]),23)
        self.assertEqual(len([k for k in reachable if k.startswith('city-')]),10)
        self.assertIn('city-yinchuan',archive['byPlace']['helan'])
        self.assertIn('budget',archive['shared'])
        self.assertIn('city-jiayuguan',archive['unused'])
        for entry in archive['entries'].values():
            self.assertTrue(entry['title'])
            self.assertTrue(entry['html'])
            ArchiveMarkup().feed(entry['html'])

    def test_portrait_layout_contains_every_place_within_its_page(self):
        config = read_data('scripts/theater-data.js','window.ROADBOOK_THEATER = ')
        portrait = config['portrait']
        self.assertEqual(set(config['layout']),set(portrait['layout']))
        for p in portrait['layout'].values():
            self.assertTrue(0 < p['x'] < portrait['size']['width'])
            self.assertTrue(0 < p['y'] < portrait['size']['height'])
        html = (ROOT / 'index.html').read_text(encoding='utf-8')
        self.assertNotIn('placePreview',html)
        self.assertIn('focus-reader" id="placePanel"',html)
        self.assertNotIn('<aside',html)
        self.assertNotIn('href="roadbook-original.html"',html)
