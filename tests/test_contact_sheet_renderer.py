from __future__ import annotations

import unittest

from PIL import Image, ImageChops

from tools.contact_sheet_renderer import (
    CYAN,
    ContactSheetRecord,
    crop_and_resize,
    render_contact_card,
)


class ContactSheetRendererTests(unittest.TestCase):
    def test_left_panel_is_raw_crop_and_right_panel_is_marker_with_model_guide(self) -> None:
        raw = Image.new("RGB", (20, 20), (10, 20, 30))
        marker = Image.new("RGB", (20, 20), (30, 20, 10))
        for x in range(4, 12):
            for y in range(3, 15):
                raw.putpixel((x, y), (70, 110, 150))
                marker.putpixel((x, y), (150, 110, 70))
        marker.putpixel((5, 5), (255, 0, 0))

        raw_before = raw.copy()
        marker_before = marker.copy()
        record = ContactSheetRecord(
            card_id="SYN-000001",
            source_id="synthetic",
            score_display="0.9876",
            threshold_string="0.125",
            comparison_status="MODEL_ONLY_AT_BOTH",
            page_number=1,
            page_position=1,
            raw_image_path="raw.jpg",
            marker_image_path="marker.jpg",
            box=(8.0, 8.0, 12.0, 12.0),
            crop=(2, 2, 18, 18),
        )

        card = render_contact_card(record, raw, marker)
        left_panel = card.crop((18, 104, 378, 464))
        right_panel = card.crop((468, 104, 828, 464))
        expected_left = crop_and_resize(raw_before, record.crop, 360)

        diff = ImageChops.difference(left_panel, expected_left)
        self.assertIsNone(diff.getbbox(), "left panel must be the resized raw crop with no overlay")
        self.assertIsNone(ImageChops.difference(raw, raw_before).getbbox(), "raw input image was mutated")
        self.assertIsNone(ImageChops.difference(marker, marker_before).getbbox(), "marker input image was mutated")

        expected_marker = crop_and_resize(marker_before, record.crop, 360)
        self.assertIsNotNone(ImageChops.difference(right_panel, expected_marker).getbbox(), "right panel should include the cyan guide")

        marker_red_x = round((5 - record.crop[0]) * (360 / (record.crop[2] - record.crop[0])))
        marker_red_y = round((5 - record.crop[1]) * (360 / (record.crop[3] - record.crop[1])))
        red_neighborhood = [
            right_panel.getpixel((marker_red_x + dx, marker_red_y + dy))
            for dx in range(-1, 2)
            for dy in range(-1, 2)
        ]
        self.assertTrue(any(pixel[0] > 180 and pixel[1] < 80 and pixel[2] < 80 for pixel in red_neighborhood))

        right_pixels = right_panel.getdata()
        self.assertIn(CYAN, right_pixels)


if __name__ == "__main__":
    unittest.main()
