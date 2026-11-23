"""Unit tests for Context Hook Voiceover Engine."""
import os
import sys
from pathlib import Path

sys.path.insert(0, ".")
from studio import tts

def test_tts_module():
    # 1. Narrative generation test
    narrative = tts.make_hook_narrative("Wait till you see this crazy stunt", "Shroud", "GTA 6")
    assert "Wait till you see" in narrative or "GTA 6" in narrative
    print("PASS make_hook_narrative:", narrative)

    # 2. Template fallback
    narrative2 = tts.make_hook_narrative("", "TypicalGamer", "GTA 6")
    assert "TypicalGamer" in narrative2 and "GTA 6" in narrative2
    print("PASS make_hook_narrative fallback:", narrative2)

    # 3. Audio synthesis test
    out_file = Path("data/tmp/narrative_test.mp3")
    res = tts.generate_voiceover(narrative, out_file)
    assert res is not None, "Expected valid audio path"
    assert out_file.exists() and out_file.stat().st_size > 1000
    print("PASS generate_voiceover:", out_file.stat().st_size, "bytes")

    print("ALL TTS TESTS PASSED")

if __name__ == "__main__":
    test_tts_module()
