import unittest
from src.full_width_layout import layout_plan

class FullWidthLayoutTests(unittest.TestCase):
    def test_square_template_uses_full_width(self):
        self.assertEqual(layout_plan((1200, 1200), 2), (1080, 1350, 135))

    def test_small_template_is_enlarged(self):
        self.assertEqual(layout_plan((500, 500), 2), (1080, 1350, 135))

    def test_landscape_template_keeps_proportions(self):
        self.assertEqual(layout_plan((1600, 900), 2), (608, 928, 160))

    def test_in_image_boxes_need_no_caption_bands(self):
        self.assertEqual(layout_plan((800, 1000), 2, True), (1350, 1350, 0))

    def test_overly_tall_template_is_not_cropped(self):
        with self.assertRaises(RuntimeError):
            layout_plan((500, 1500), 2)

if __name__ == '__main__':
    unittest.main()
