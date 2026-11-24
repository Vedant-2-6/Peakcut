import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from studio import censor, seo, render

class TestCensorAndContentSafety(unittest.TestCase):

    def test_clean_user_flagged_title(self):
        """Specifically verify the exact title that got age restricted by YouTube."""
        raw_title = "NOT A FUCKING SINGLE SCRATCH in Grand Theft Auto VI! 🤯 #Shorts"
        cleaned = censor.clean_title_metadata(raw_title)
        self.assertNotIn("FUCKING", cleaned)
        self.assertNotIn("fuck", cleaned.lower())
        self.assertIn("NOT A SINGLE SCRATCH", cleaned)
        self.assertIn("#Shorts", cleaned)

    def test_clean_various_profanities_in_titles(self):
        cases = [
            ("WHAT THE FUCK IS THIS", "WHAT THE IS THIS"),
            ("HOLY SHIT THAT WAS INSANE", "HOLY moment THAT WAS INSANE"),
            ("THIS BITCH TRIED TO KILL ME", "THIS TRIED TO KILL ME"),
            ("BHENCHOD YE KYA THA", "YE KYA THA"),
            ("CARRYISLIVE CHUTIYA MOMENT", "CARRYISLIVE MOMENT"),
        ]
        for inp, expected in cases:
            out = censor.clean_title_metadata(inp)
            for bad in ["fuck", "shit", "bitch", "bhenchod", "chutiya"]:
                self.assertNotIn(bad, out.lower())

    def test_mask_caption_words_for_subtitles(self):
        """Subtitles on video must use asterisks (f***ing) so YouTube OCR doesn't flag them."""
        self.assertEqual(censor.mask_caption_word("fucking"), "f***ing")
        self.assertEqual(censor.mask_caption_word("FUCKING"), "F***ING")
        self.assertEqual(censor.mask_caption_word("shit"), "sh*t")
        self.assertEqual(censor.mask_caption_word("bitch"), "b***h")
        self.assertEqual(censor.mask_caption_word("chutiya"), "ch***ya")
        self.assertEqual(censor.mask_caption_word("madarchod"), "m****chod")
        # Regular words should not be touched
        self.assertEqual(censor.mask_caption_word("gaming"), "gaming")
        self.assertEqual(censor.mask_caption_word("Grand"), "Grand")

    def test_seo_metadata_generation_is_safe(self):
        meta = seo.generate_shorts_metadata(
            hook="NOT A FUCKING SINGLE SCRATCH",
            uploader="CarryisLive",
            game="GTA 6",
            transcript_snippet="The entire fucking air support"
        )
        self.assertNotIn("FUCKING", meta["title"])
        self.assertNotIn("fuck", meta["title"].lower())
        self.assertNotIn("fuck", meta["description"].lower())

    def test_render_ass_masks_subtitles(self):
        words = [
            {"w": "The", "s": 0.0, "e": 0.5},
            {"w": "fucking", "s": 0.5, "e": 1.0},
            {"w": "car", "s": 1.0, "e": 1.5},
        ]
        ass_script = render.build_ass(
            words=words,
            start=0.0,
            end=2.0,
            hook="WHAT THE FUCK",
            style_name="bounce",
            highlight=[],
            hook_y=300,
            cap_y=900
        )
        self.assertNotIn("fucking", ass_script.lower())
        self.assertIn("F***ING", ass_script)
        self.assertNotIn("WHAT THE FUCK", ass_script)


if __name__ == "__main__":
    unittest.main()
