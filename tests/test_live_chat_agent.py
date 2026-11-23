"""Test live YouTube stream monitoring and peak detection clipping."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from studio.peak_detector import MedianPeakDetector
from studio.yt_chat import extract_video_id, YouTubeChatReader
from studio import live, media

def test_full_live_peak_flow():
    # 1. Video ID extraction
    vid = extract_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    assert vid == "dQw4w9WgXcQ"
    print("PASS 1: extract_video_id")

    # 2. Peak detector simulation
    detector = MedianPeakDetector(window_sec=120, multiplier=2.4, min_rate=2.5, pre_roll_sec=20.0,
                                  min_clip_sec=30.0, max_clip_sec=60.0)

    # Establish baseline (1 msg per second)
    for t in range(40):
        detector.record_message(t, user=f"chatter_{t % 4}")
        detector.record_viewers(t, 1200)

    stats = detector.stats_at(40)
    assert stats["median_rate"] <= 1.5, f"Expected low median, got {stats['median_rate']}"
    assert detector.check_peak(40) is None
    print("PASS 2: baseline does not trigger peak")

    # Simulate spike at t=45..50: 8 msgs/sec from diverse users (hype moment)
    for t in range(45, 51):
        for i in range(8):
            detector.record_message(t, user=f"hype_fan_{i}")
        detector.record_viewers(t, 1500)

    peak = detector.check_peak(50)
    assert peak is not None, "Expected peak detection on surge"
    assert peak["start"] == 30.0, f"Expected start to be 50 - 20 = 30.0, got {peak['start']}"
    assert 30.0 <= peak["duration"] <= 60.0, f"Expected duration between 30 and 60, got {peak['duration']}"
    assert peak["end"] == peak["start"] + peak["duration"]
    print("PASS 3: peak triggered with dynamic duration", peak["duration"])

    # 3. Verify session integration
    class FakeSession:
        def __init__(self):
            self.samples = 16000 * 50
            self.lock = live.threading.RLock()
            self.chat = live.collections.Counter()
            self.chat_users = {}
            self.chat_total = 0
            self.chat_kept = 0
            self.viewers = 0
            self.peak_detector = detector

        def _on_yt_message(self, second, author, text, superchat):
            live.Session._on_yt_message(self, second, author, text, superchat)

        def _on_yt_viewers(self, count):
            live.Session._on_yt_viewers(self, count)

    s = FakeSession()
    s._on_yt_message(50, "test_user", "OMG WHAT A CLUTCH", False)
    s._on_yt_viewers(1500)
    assert s.chat[50] == 1
    assert s.viewers == 1500
    print("PASS 4: FakeSession chat callbacks integrated")

    print("\nALL LIVE CHAT AGENT TESTS PASSED")

if __name__ == "__main__":
    test_full_live_peak_flow()
