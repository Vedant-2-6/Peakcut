"""Unit tests for YouTubeChatReader and video ID extraction."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from studio.yt_chat import extract_video_id, YouTubeChatReader

def test_extract_video_id():
    cases = [
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/live/dQw4w9WgXcQ?si=12345", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/shorts/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("http://youtube.com/watch?v=dQw4w9WgXcQ&t=10s", "dQw4w9WgXcQ"),
    ]
    for url, want in cases:
        got = extract_video_id(url)
        assert got == want, f"For {url}, expected {want}, got {got}"
    print("PASS test_extract_video_id")

def test_reader_init():
    received = []
    def on_msg(sec, author, text, superchat):
        received.append((sec, author, text, superchat))

    reader = YouTubeChatReader("https://www.youtube.com/watch?v=dQw4w9WgXcQ", on_message=on_msg)
    assert reader.video_id == "dQw4w9WgXcQ"
    assert not reader.is_connected
    print("PASS test_reader_init")

if __name__ == "__main__":
    test_extract_video_id()
    test_reader_init()
