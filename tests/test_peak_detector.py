"""Unit tests for MedianPeakDetector."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from studio.peak_detector import MedianPeakDetector

def test_peak_detector():
    detector = MedianPeakDetector(window_sec=60, multiplier=2.5, min_rate=3.0, cooldown_sec=40)

    # Simulate baseline traffic: 1 msg per second for 50 seconds
    for s in range(50):
        detector.record_message(s, user=f"user_{s % 5}")
        detector.record_viewers(s, 500)

    # Baseline check: should not trigger
    res = detector.check_peak(50)
    assert res is None, f"Expected no peak during baseline, got {res}"

    # Simulate sudden surge at s=51..56: 6 msgs per second with distinct users
    for s in range(51, 57):
        for m in range(6):
            detector.record_message(s, user=f"hyped_user_{m}")
        detector.record_viewers(s, 650)

    # Check at s=56
    peak = detector.check_peak(56)
    assert peak is not None, "Expected peak to trigger during surge"
    assert peak["peak_second"] == 56
    assert peak["start"] == 36.0, f"Expected start to be 56 - 20 = 36.0, got {peak['start']}"
    assert 30.0 <= peak["duration"] <= 60.0, f"Duration {peak['duration']} out of [30, 60] range"
    assert peak["end"] == peak["start"] + peak["duration"]

    # During cooldown (e.g. s=65), should not trigger again
    for s in range(57, 66):
        for m in range(6):
            detector.record_message(s, user=f"hyped_user_{m}")
    res2 = detector.check_peak(65)
    assert res2 is None, f"Expected cooldown to prevent immediate repeat trigger, got {res2}"

    print("PASS test_peak_detector")

if __name__ == "__main__":
    test_peak_detector()
