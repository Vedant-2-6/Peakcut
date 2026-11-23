"""Pacing Engine & Silence Trimmer for YouTube Shorts Retention (APV > 100%)."""
import logging
import re
from pathlib import Path

from . import media

_logger = logging.getLogger("studio.pacing")


def detect_silence(video_or_audio_path: Path, noise_db: float = -32.0, min_duration: float = 0.35) -> list[tuple[float, float]]:
    """Detect silent intervals using ffmpeg silencedetect filter.

    Returns list of (start_sec, end_sec) tuples."""
    cmd = [
        "ffmpeg", "-y", "-v", "info",
        "-i", str(video_or_audio_path),
        "-af", f"silencedetect=noise={noise_db}dB:d={min_duration}",
        "-f", "null", "-"
    ]
    try:
        res = media.run(cmd, timeout=40)
    except RuntimeError as e:
        # silencedetect outputs logs to stderr
        res = str(e)

    silence_spans = []
    current_start = None
    for line in res.splitlines():
        m_start = re.search(r"silence_start:\s*([0-9.]+)", line)
        if m_start:
            current_start = float(m_start.group(1))
        m_end = re.search(r"silence_end:\s*([0-9.]+)", line)
        if m_end and current_start is not None:
            silence_spans.append((current_start, float(m_end.group(1))))
            current_start = None
    return silence_spans


def calculate_active_intervals(total_duration: float, silence_spans: list[tuple[float, float]],
                               pad_sec: float = 0.08) -> list[tuple[float, float]]:
    """Invert silence spans to get active speaking/action intervals with small padding."""
    if not silence_spans:
        return [(0.0, total_duration)]

    active = []
    cursor = 0.0
    for s_start, s_end in silence_spans:
        active_end = max(cursor, s_start + pad_sec)
        if active_end - cursor >= 0.2:
            active.append((cursor, active_end))
        cursor = min(total_duration, s_end - pad_sec)

    if total_duration - cursor >= 0.2:
        active.append((cursor, total_duration))
    return active


def adjust_word_timestamps_for_trimmed(words: list[dict], active_intervals: list[tuple[float, float]]) -> list[dict]:
    """Re-map caption word timestamps to match the silence-trimmed timeline."""
    new_words = []
    # Build cumulative time offset map
    # Each interval in active_intervals has an original start and maps to a new timeline start
    new_start_offset = 0.0
    for a_start, a_end in active_intervals:
        dur = a_end - a_start
        for w in words:
            if a_start <= w["s"] < a_end:
                offset = w["s"] - a_start
                w_dur = max(0.05, w["e"] - w["s"])
                new_words.append({
                    "w": w["w"],
                    "s": round(new_start_offset + offset, 2),
                    "e": round(new_start_offset + offset + w_dur, 2)
                })
        new_start_offset += dur

    return sorted(new_words, key=lambda x: x["s"])
