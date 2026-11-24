import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from studio import brain, config, creators, jobs, render, seo


class TestSplitLayoutQualityAndClickbait(unittest.TestCase):

    def test_defaults_prioritize_split_and_1080p(self):
        self.assertEqual(creators.DEFAULTS["layout"], "split")
        self.assertEqual(creators.DEFAULTS["min_score"], 75)
        self.assertEqual(creators.DEFAULTS["must_clip_min"], 0)
        self.assertEqual(jobs.DEFAULTS["layout"], "split")
        self.assertEqual(jobs.DEFAULTS["quality"], 1080)
        self.assertEqual(jobs.DEFAULTS["min_score"], 75)
        self.assertGreaterEqual(config.OUT_FPS, 60)

    def test_virality_calibration_boosts_hype_and_penalizes_boring_filler(self):
        import numpy as np
        # Simulated 60-second audio z-score: quiet monotone everywhere except spike at 35-42s
        z = np.zeros(60, dtype=np.float32)
        z[35:43] = 2.8
        words_hype = [{"w": f"w{i}", "s": float(i), "e": float(i) + 0.5} for i in range(10, 50)]
        hype_clip = {"score": 76, "hook": "INSANE CLUTCH", "title": "He Broke GTA 6!"}
        boring_clip = {"score": 76, "hook": "THANK YOU SO MUCH FOR THE SUPER CHAT", "title": "Thank you guys"}

        hype_score = brain.calibrate_score(hype_clip, z, words_hype, 10.0, 50.0)
        boring_score = brain.calibrate_score(boring_clip, z, words_hype, 0.0, 30.0)
        self.assertGreater(hype_score, 80)
        self.assertLess(boring_score, 55)

    def test_split_filter_includes_facecam_and_cropped_gameplay(self):
        # Source 1920x1080 with left-corner facecam [20, 40, 500, 320]
        f = render._filter("split", render.SPLIT_GAME_H, [20, 40, 500, 320], src_w=1920, src_h=1080)
        self.assertIn("[top][bot]vstack=inputs=2[v0]", f)
        self.assertIn("crop=500:320:20:40", f)
        self.assertIn(f"scale={render.W}:{render.SPLIT_FC_H}", f)
        self.assertIn(f"scale={render.W}:{render.SPLIT_GAME_H}", f)
        # Smart crop should shift x >= 520 (avoiding left facecam ending at x=520)
        self.assertIn("crop=888:1080:520:0", f)

    def test_smart_crop_avoids_right_facecam(self):
        # Right facecam starting at x=1320 (width 560 -> 1320..1880)
        expr = render._smart_gameplay_crop(1920, 1080, 1080, 1312, [1320, 40, 560, 320])
        # Center crop would be cx=516..1404 (overlapping 1320); should shift left to 1320 - 888 = 432
        self.assertIn("crop=888:1080:432:0", expr)

    def test_split_without_facecam_falls_back_to_crop(self):
        f = render._filter("split", 1920, None, src_w=1920, src_h=1080)
        self.assertIn("scale=1080:1920", f)
        self.assertNotIn("vstack", f)

    def test_clickbait_titles_keep_strong_ai_titles_and_drop_filler(self):
        # Strong AI title preserved and polished
        meta = seo.generate_shorts_metadata(
            hook="BYE NICOLO",
            uploader="CarryisLive",
            game="Grand Theft Auto VI",
            ai_title="CarryisLive Lost His Golden Lambo In 3 Seconds!",
        )
        self.assertIn("Golden Lambo", meta["title"])
        self.assertIn("#Shorts", meta["title"])
        self.assertNotIn("BYE NICOLO", meta["title"])

        # Boring filler hook falls back to clickbait template instead of "THANK YOU SO MUCH in ..."
        meta2 = seo.generate_shorts_metadata(
            hook="THANK YOU SO MUCH",
            uploader="CarryisLive",
            game="Grand Theft Auto VI",
            ai_title="",
        )
        self.assertNotIn("THANK YOU SO MUCH", meta2["title"])
        self.assertIn("#Shorts", meta2["title"])
        self.assertIn("Grand Theft Auto VI", meta2["title"])


if __name__ == "__main__":
    unittest.main()
