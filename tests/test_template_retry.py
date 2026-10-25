import unittest
from unittest.mock import Mock
from PIL import Image
from src.template_retry import select_fitting_concept


def idea(template_id):
    return {'template': {'id': template_id}, 'panel_text': ['Setup', 'Punchline'], 'topic': 'Example'}

class TemplateRetryTests(unittest.TestCase):
    def test_first_fitting_template_returns_without_retry(self):
        candidate = idea('wide')
        build = Mock(return_value=candidate)
        result = select_fitting_concept(build, lambda _: Image.new('RGB', (1600, 900)), [])
        self.assertIs(result, candidate)
        self.assertEqual(build.call_count, 1)

    def test_tall_then_wide_retries_and_excludes_tall_id(self):
        history = [{'topic': 'Previous rejection'}]
        seen = []
        candidates = iter([idea('tall'), idea('wide')])
        def build(rejected, excluded):
            seen.append((list(rejected), list(excluded)))
            return next(candidates)
        def picture(template):
            return Image.new('RGB', (500, 1500) if template['id'] == 'tall' else (1600, 900))
        result = select_fitting_concept(build, picture, history)
        self.assertEqual(result['template']['id'], 'wide')
        self.assertEqual(seen[1][1], ['tall'])
        self.assertEqual(seen[1][0][-1]['template_id'], 'tall')
        self.assertEqual(history, [{'topic': 'Previous rejection'}])

    def test_repeated_excluded_template_does_not_download_again(self):
        build = Mock(return_value=idea('tall'))
        picture = Mock(side_effect=lambda _: Image.new('RGB', (500, 1500)))
        with self.assertRaisesRegex(RuntimeError, 'after three selections'):
            select_fitting_concept(build, picture, [])
        self.assertEqual(build.call_count, 3)
        self.assertEqual(picture.call_count, 1)

    def test_three_distinct_tall_templates_stop_at_limit(self):
        build = Mock(side_effect=[idea('a'), idea('b'), idea('c')])
        with self.assertRaisesRegex(RuntimeError, 'after three selections'):
            select_fitting_concept(build, lambda _: Image.new('RGB', (500, 1500)), [])
        self.assertEqual(build.call_count, 3)

    def test_download_error_is_not_retried(self):
        build = Mock(return_value=idea('a'))
        with self.assertRaisesRegex(RuntimeError, 'Network failed'):
            select_fitting_concept(build, Mock(side_effect=RuntimeError('Network failed')), [])
        self.assertEqual(build.call_count, 1)

    def test_invalid_panel_count_is_not_treated_as_tall(self):
        candidate = idea('a')
        candidate['panel_text'] = []
        build = Mock(return_value=candidate)
        with self.assertRaisesRegex(RuntimeError, 'Invalid template dimensions or panel count'):
            select_fitting_concept(build, lambda _: Image.new('RGB', (100, 100)), [])
        self.assertEqual(build.call_count, 1)

    def test_concept_error_is_not_retried(self):
        build = Mock(side_effect=RuntimeError('Safety validation failed'))
        with self.assertRaisesRegex(RuntimeError, 'Safety validation failed'):
            select_fitting_concept(build, Mock(), [])
        self.assertEqual(build.call_count, 1)

if __name__ == '__main__':
    unittest.main()
