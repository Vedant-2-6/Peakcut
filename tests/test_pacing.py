"""Unit tests for Pacing Engine & Silence Trimmer."""
import sys
from pathlib import Path

sys.path.insert(0, ".")
from studio import pacing

def test_pacing():
    # 1. Test active intervals calculation
    # 10s video with silence at 2.0-3.5 and 7.0-8.2
    silence = [(2.0, 3.5), (7.0, 8.2)]
    active = pacing.calculate_active_intervals(10.0, silence, pad_sec=0.05)
    assert len(active) == 3, f"Expected 3 active intervals, got {len(active)}"
    assert active[0][0] == 0.0
    print("PASS calculate_active_intervals:", active)

    # 2. Test word timestamp re-mapping
    words = [
        {"w": "Hello", "s": 0.5, "e": 0.9},
        {"w": "GTA", "s": 4.0, "e": 4.5},
        {"w": "World", "s": 9.0, "e": 9.4},
    ]
    trimmed_words = pacing.adjust_word_timestamps_for_trimmed(words, active)
    assert len(trimmed_words) == 3
    assert trimmed_words[0]["w"] == "Hello" and trimmed_words[0]["s"] == 0.5
    # Since 1.4s of silence was skipped, GTA should have shifted earlier
    assert trimmed_words[1]["s"] < words[1]["s"], f"Expected GTA timestamp to shift earlier, got {trimmed_words[1]['s']}"
    print("PASS adjust_word_timestamps_for_trimmed:", trimmed_words)

    print("ALL PACING TESTS PASSED")

if __name__ == "__main__":
    test_pacing()
