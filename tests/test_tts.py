"""Test for Edge-TTS Voiceover Engine."""
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, ".")

async def main():
    import edge_tts
    out = Path("data/tmp/test_voice.mp3")
    out.parent.mkdir(parents=True, exist_ok=True)
    c = edge_tts.Communicate("Wait till you see what happened in GTA 6!", "en-US-ChristopherNeural")
    await c.save(str(out))
    assert out.exists() and out.stat().st_size > 1000, "Audio file not created or too small"
    print(f"PASS test_tts: generated {out.stat().st_size} bytes")

if __name__ == "__main__":
    asyncio.run(main())
