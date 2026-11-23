"""Rolling median peak detection and dynamic clip sizing for live streams."""
import collections
import statistics
import time


class MedianPeakDetector:
    """Detects excitement peaks in chat and viewership using rolling medians,

    and calculates dynamic clip durations (30 to 60 seconds) based on hype duration."""

    def __init__(self, window_sec: int = 180, multiplier: float = 2.4, min_rate: float = 2.5,
                 cooldown_sec: int = 60, pre_roll_sec: float = 20.0, min_clip_sec: float = 40.0,
                 max_clip_sec: float = 60.0):
        self.window_sec = window_sec
        self.multiplier = multiplier
        self.min_rate = min_rate
        self.cooldown_sec = cooldown_sec
        self.pre_roll_sec = pre_roll_sec
        self.min_clip_sec = min_clip_sec
        self.max_clip_sec = max_clip_sec

        # second -> int count of messages
        self.history = collections.defaultdict(int)
        # second -> set of user identifiers
        self.user_history = collections.defaultdict(set)
        # second -> viewer count
        self.viewers_history = {}

        self.last_trigger_t = -999.0
        self.last_clip_end_t = -999.0
        self.total_peaks = 0

    def record_message(self, second: int, user: str = ""):
        self.history[second] += 1
        if user:
            # 32-bit integer hash to reduce Python string object allocations during long live chats
            self.user_history[second].add(hash(user.lower()) & 0xFFFFFFFF)

    def record_viewers(self, second: int, viewers: int):
        if viewers > 0:
            self.viewers_history[second] = viewers

    def prune(self, current_second: int, force: bool = False):
        # Throttle pruning to run every 30s instead of every message/second
        if not force and current_second % 30 != 0:
            return
        cutoff = current_second - self.window_sec - 60
        for s in list(self.history.keys()):
            if s < cutoff:
                del self.history[s]
        for s in list(self.user_history.keys()):
            if s < cutoff:
                del self.user_history[s]
        for s in list(self.viewers_history.keys()):
            if s < cutoff:
                del self.viewers_history[s]

    def stats_at(self, current_second: int) -> dict:
        """Calculate baseline median, current rate, and active user ratio."""
        window_start = max(0, current_second - self.window_sec)
        window_end = current_second - 8
        counts = [self.history.get(s, 0) for s in range(window_start, window_end)] if window_end > window_start else []
        median_rate = statistics.median(counts) if counts else 0.0

        burst_start = current_second - 6
        burst_seconds = range(burst_start, current_second)
        burst_count = sum(self.history.get(s, 0) for s in burst_seconds)
        current_rate = burst_count / 6.0

        burst_users = set()
        for s in burst_seconds:
            burst_users.update(self.user_history.get(s, ()))
        unique_users_ratio = (len(burst_users) / max(1, burst_count)) if burst_count > 0 else 1.0

        return {
            "median_rate": round(float(median_rate), 2),
            "current_rate": round(float(current_rate), 2),
            "burst_count": burst_count,
            "unique_users": len(burst_users),
            "user_ratio": round(float(unique_users_ratio), 2),
            "viewers": self.viewers_history.get(current_second) or self.viewers_history.get(current_second - 1)
        }

    def check_peak(self, current_second: int) -> dict | None:
        """Check if current_second marks a peak moment.

        Returns clip configuration dict if a peak is triggered, else None."""
        if current_second < 30:  # Need at least 30s warmup
            return None

        # Check cooldown against both trigger time and last clip end
        if (current_second - self.last_trigger_t < self.cooldown_sec or
                current_second < self.last_clip_end_t + 10):
            return None

        stats = self.stats_at(current_second)
        median = stats["median_rate"]
        cur = stats["current_rate"]

        # Peak condition:
        # 1. Rate is significantly above median (>= multiplier * max(median, 0.5))
        # 2. Rate meets min_rate threshold
        # 3. Not just 1 bot repeating messages (at least 2 distinct users or healthy ratio)
        is_spike = (
            cur >= max(self.min_rate, median * self.multiplier) and
            (stats["unique_users"] >= 2 or stats["burst_count"] <= 2)
        )

        if not is_spike:
            return None

        # Dynamic Clip Length (30s to 60s):
        # Clip starts 15-20s before the peak moment
        clip_start = max(0.0, float(current_second) - self.pre_roll_sec)

        # Baseline post-peak duration is calculated:
        # Higher intensity (rate / median ratio) and higher viewer engagement = longer post-peak coverage
        intensity = cur / max(median, 0.5)
        # For standard spike (2.5x), post_dur is ~15s (total 35s)
        # For huge viral spike (4x+), post_dur scales up to ~40s (total 60s)
        extra_hype = min(20.0, max(0.0, (intensity - self.multiplier) * 8.0))
        post_dur = 20.0 + extra_hype  # min post-peak: 20s -> total 40s min
        total_dur = min(self.max_clip_sec, max(self.min_clip_sec, self.pre_roll_sec + post_dur))
        clip_end = clip_start + total_dur

        self.last_trigger_t = float(current_second)
        self.last_clip_end_t = float(clip_end)
        self.total_peaks += 1
        self.prune(current_second)

        return {
            "peak_second": current_second,
            "start": round(clip_start, 2),
            "end": round(clip_end, 2),
            "duration": round(total_dur, 2),
            "intensity": round(intensity, 2),
            "current_rate": cur,
            "median_rate": median,
            "reason": f"Chat peak ({cur:.1f} msgs/s vs median {median:.1f})"
        }
