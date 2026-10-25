import unittest
from src.generate_meme import attach_source

class SourceResolutionTests(unittest.TestCase):
    def setUp(self):
        self.sources = {'news_1': 'https://news.google.com/rss/articles/original?oc=5'}

    def test_original_url_attached(self):
        self.assertEqual(attach_source({'source_id': 'news_1'}, self.sources)['source_url'], self.sources['news_1'])

    def test_model_url_cannot_override_original(self):
        result = attach_source({'source_id': ' news_1 ', 'source_url': 'https://invented.invalid'}, self.sources)
        self.assertEqual(result['source_url'], self.sources['news_1'])

    def test_unknown_missing_or_invalid_id_rejected(self):
        for idea in ({'source_id': 'unknown'}, {'source_id': None}, {'source_id': []}, []):
            with self.subTest(idea=idea):
                with self.assertRaises(ValueError):
                    attach_source(idea, self.sources)

if __name__ == '__main__':
    unittest.main()
