"""Free Edge-TTS Voiceover Engine for Context Hook Narration & Fair Use Compliance."""
import asyncio
import logging
import re
import subprocess
from pathlib import Path

from . import config, media

_logger = logging.getLogger("studio.tts")

DEFAULT_VOICE = "en-US-ChristopherNeural"
# High-energy, fast narrative setup templates to transform third-party clips into commentary
HOOK_TEMPLATES = [
    "Wait till you see what happened when {streamer} tried this in {game}!",
    "You won't believe how {streamer} reacted to this {game} moment!",
    "Is {game} actually doing this right now?!",
    "Nobody expected {streamer} to pull this off in {game}!",
    "This might be the craziest {game} moment ever recorded by {streamer}!",
]


def make_hook_narrative(hook: str, streamer: str = "", game: str = "") -> str:
    """Generate a 1-sentence viral narrator hook setup."""
    streamer_clean = re.sub(r"[^\w\s]", "", streamer).strip() or "this streamer"
    game_clean = re.sub(r"[^\w\s]", "", game).strip() or "the game"

    if hook and len(hook.split()) >= 4:
        # If hook is already a question or punchline, frame it directly
        return f"Wait till you see this: {hook.rstrip('.!?')}!"

    import random
    tmpl = random.choice(HOOK_TEMPLATES)
    return tmpl.format(streamer=streamer_clean, game=game_clean)


async def _synthesize(text: str, out_file: Path, voice: str = DEFAULT_VOICE):
    import edge_tts
    comm = edge_tts.Communicate(text, voice, rate="+15%")  # +15% rate for rapid viral Shorts pacing
    await comm.save(str(out_file))


def generate_voiceover(text: str, out_path: Path, voice: str = DEFAULT_VOICE) -> Path | None:
    """Synchronously generate an MP3 voiceover file."""
    try:
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        asyncio.run(_synthesize(text, out_path, voice))
        if out_path.exists() and out_path.stat().st_size > 500:
            return out_path
    except Exception as e:
        _logger.warning("TTS voiceover generation failed: %s", e)
    return None


def overlay_voiceover_on_audio(base_audio_path: Path, voiceover_path: Path, out_audio_path: Path,
                               duck_db: float = -14.0) -> bool:
    """Overlay the voiceover onto the clip audio with background ducking during speech."""
    try:
        # Use ffmpeg sidechain ducking or amix with volume delay
        # 1. Probe voiceover duration
        probe = media.probe(voiceover_path)
        v_dur = float(probe.get("duration", 2.5))

        # FFmpeg filter: duck base audio by duck_db during voiceover duration, then return to normal
        # [0:a]volume='if(lt(t,{v_dur}),0.2,1.0)':eval=frame[ducked]; [ducked][1:a]amix=inputs=2:duration=first:dropout_transition=2[out]
        cmd = [
            "ffmpeg", "-y", "-v", "error",
            "-i", str(base_audio_path),
            "-i", str(voiceover_path),
            "-filter_complex",
            f"[0:a]volume=if(lt(t\\,{v_dur + 0.3:.2f})\\,0.22\\,1.0):eval=frame[ducked];"
            f"[ducked][1:a]amix=inputs=2:duration=first:dropout_transition=1[aout]",
            "-map", "[aout]",
            "-ac", "2", "-ar", "48000",
            str(out_audio_path)
        ]
        media.run(cmd, timeout=30)
        return out_audio_path.exists() and out_audio_path.stat().st_size > 1000
    except Exception as e:
        _logger.warning("Failed to overlay voiceover on audio: %s", e)
        return False
