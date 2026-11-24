"""Auto-pilot: discover top gaming live streams on YouTube, monitor each for ~1 hour, then rotate.

The autopilot runs as a daemon thread. It uses yt-dlp to search YouTube for currently live gaming streams
sorted by viewer count, picks the top one not already monitored, starts PeakCut's live session on it for
the configured duration (default 60 minutes), then moves to the next. No YouTube API key required."""
import logging
import re
import threading
import time

from . import accounts, auth, config, creators, ctx, jobs, live, media

_logger = logging.getLogger("studio.autopilot")

# ---------------------------------------------------------------- configuration
DURATION_MIN = int(config.env("PEAKCUT_AUTOPILOT_DURATION_MIN", "60"))   # how long to monitor each stream
PAUSE_BETWEEN = int(config.env("PEAKCUT_AUTOPILOT_PAUSE_SEC", "30"))    # cooldown between streams
MAX_STREAMS = int(config.env("PEAKCUT_AUTOPILOT_MAX_RESULTS", "20"))    # how many candidates to fetch

AUTOPILOT_TOPIC = config.env("PEAKCUT_AUTOPILOT_TOPIC", "gta6").lower()

# GTA 6 specific trend cluster
GTA6_QUERIES = [
    "GTA 6 live stream",
    "GTA 6 live",
    "GTA 6 gameplay live",
    "GTA 6 trailer reaction live",
    "GTA 6 leak discussion live",
    "GTA 6 RP live",
    "GTA 6 Vice City live",
]

# General gaming categories and search terms
GAMING_QUERIES = [
    "gaming live stream",
    "live gaming",
    "BGMI live stream",
    "GTA V live stream",
    "Valorant live stream",
    "Minecraft live stream",
    "Fortnite live stream",
    "Free Fire live stream",
    "PUBG live stream",
    "COD live stream",
]


def fetch_trending_queries(topic: str = "GTA 6") -> list[str]:
    """Fetch real-time trending YouTube gaming search suggestions without API keys."""
    try:
        import httpx
        url = f"https://suggestqueries.google.com/complete/search?client=firefox&ds=yt&q={topic}+live"
        r = httpx.get(url, timeout=5)
        if r.status_code == 200:
            suggestions = r.json()[1]
            return [s for s in suggestions if isinstance(s, str) and len(s) > 3][:8]
    except Exception:
        pass
    return []


_state = {
    "running": False,
    "topic": AUTOPILOT_TOPIC,
    "current_url": "",
    "current_title": "",
    "current_uploader": "",
    "current_viewers": 0,
    "started_at": 0.0,
    "duration_min": DURATION_MIN,
    "streams_done": 0,
    "clips_total": 0,
    "last_error": "",
    "history": [],         # [{url, title, uploader, viewers, clips, started, ended}]
}
_lock = threading.Lock()
_stop_event = threading.Event()
_thread = None


def state() -> dict:
    with _lock:
        s = dict(_state)
        if s["running"] and s["started_at"]:
            s["elapsed_min"] = round((time.time() - s["started_at"]) / 60, 1)
            s["remaining_min"] = max(0, s["duration_min"] - s["elapsed_min"])
        s["history"] = list(s["history"][-10:])   # last 10
        return s


def _discover_live_gaming_streams() -> list:
    """Use yt-dlp to search YouTube for live gaming streams, sorted by viewer count.

    Returns a list of dicts: [{url, title, uploader, viewers, video_id}]."""
    import yt_dlp

    results = []
    seen_ids = set()

    # Dynamic trend radar: prioritize current topic (GTA 6) + real-time YouTube suggestions
    topic = _state.get("topic", AUTOPILOT_TOPIC)
    if topic == "gta6":
        trending = fetch_trending_queries("GTA 6")
        topic_queries = trending + [q for q in GTA6_QUERIES if q not in trending]
        active_pool = topic_queries + GAMING_QUERIES
    else:
        active_pool = GAMING_QUERIES

    query_index = int(time.time() / 300) % len(active_pool)
    queries = active_pool[query_index:] + active_pool[:query_index]

    for query in queries[:3]:   # try up to 3 queries per round
        if len(results) >= MAX_STREAMS:
            break
        try:
            opts = {
                "extract_flat": True, "playlistend": MAX_STREAMS,
                "default_search": "ytsearch",
            }
            search_url = f"ytsearch{MAX_STREAMS}:{query}"
            with media._ydl(opts) as ydl:
                info = ydl.extract_info(search_url, download=False)
                entries = info.get("entries") or []
                for entry in entries:
                    vid = entry.get("id") or ""
                    if not vid or vid in seen_ids:
                        continue
                    if not entry.get("is_live") and not entry.get("live_status") == "is_live":
                        continue
                    seen_ids.add(vid)
                    results.append({
                        "url": f"https://www.youtube.com/watch?v={vid}",
                        "title": entry.get("title") or "",
                        "uploader": entry.get("uploader") or entry.get("channel") or "",
                        "viewers": int(entry.get("concurrent_view_count") or entry.get("view_count") or 0),
                        "video_id": vid,
                    })
        except Exception as e:
            _logger.debug("Search query %r failed: %s", query, e)
            continue

    # Sort by viewer count descending
    results.sort(key=lambda r: r["viewers"], reverse=True)
    return results


def _get_or_create_creator(name: str, url: str) -> dict:
    """Find or create a creator entry for the autopilot stream with optimal clipping settings."""
    name = re.sub(r"[^\w\s\-.]", "", name or "Auto-Pilot Stream")[:60].strip() or "Auto-Pilot Stream"
    existing = next((c for c in creators.all_creators() if c["name"].lower() == name.lower()), None)

    # Auto-detect connected accounts for zero-confirmation auto-upload
    try:
        connected = accounts.list_accounts()
    except Exception:
        connected = []
    yt_accs = [a["id"] for a in connected if a.get("platform") == "youtube"]
    acc_ids = yt_accs if yt_accs else [a["id"] for a in connected if "id" in a]

    patch = {
        "decide_mode": "either",
        "must_clip_min": 0,
        "min_score": 75,
        "layout": "split",
        "autopost": bool(acc_ids),
        "accounts": acc_ids,
        "ai_only_on_spike": False,
        "ai_every_min": 2,
    }
    if existing:
        return creators.update(existing["id"], patch)
    return creators.create({"name": name, "channel": url, **patch})


def _already_monitored(url: str) -> bool:
    """Is this URL already being monitored by any active live session?"""
    for s in live.active():
        if s.job.get("source", {}).get("url", "").rstrip("/") == url.rstrip("/"):
            return True
    return False


def _run_autopilot():
    """Main autopilot loop. Runs in a daemon thread."""
    _logger.info("Autopilot started (duration=%d min per stream)", DURATION_MIN)

    # Ensure we have a user context (use the local user)
    uid = None
    for _ in range(30):
        try:
            user = auth.local_user()
            uid = user.id if hasattr(user, "id") else str(user)
            break
        except Exception:
            time.sleep(2)
    if not uid:
        try:
            ids = auth.user_ids()
            uid = ids[0] if ids else None
        except Exception:
            pass
    if not uid:
        with _lock:
            _state["last_error"] = "No user account available for autopilot"
            _state["running"] = False
        _logger.error("Autopilot: no user account found")
        return

    prefetched_candidates = None
    while not _stop_event.is_set():
        with _lock:
            _state["current_url"] = ""
            _state["current_title"] = "Searching for top gaming streams..."
            _state["current_uploader"] = ""
            _state["current_viewers"] = 0

        # 1. Discover live gaming streams (or use pre-fetched from previous cycle)
        if prefetched_candidates:
            candidates = prefetched_candidates
            prefetched_candidates = None
            _logger.info("Autopilot: using pre-fetched stream candidates for instant rotation")
        else:
            try:
                candidates = _discover_live_gaming_streams()
            except Exception as e:
                _logger.warning("Stream discovery failed: %s", e)
                with _lock:
                    _state["last_error"] = f"Discovery failed: {str(e).strip()[:150]}"
                _stop_event.wait(60)
                continue

        if not candidates:
            _logger.info("No live gaming streams found, retrying in 2 minutes")
            with _lock:
                _state["last_error"] = "No live gaming streams found right now"
            _stop_event.wait(120)
            continue

        # 2. Pick the top stream not already monitored
        picked = None
        already_done = {h["url"] for h in _state.get("history", [])}
        for c in candidates:
            if c["url"] in already_done:
                continue
            if _already_monitored(c["url"]):
                continue
            picked = c
            break

        if not picked:
            # All candidates were already done; clear history and retry
            with _lock:
                _state["history"] = []
            _stop_event.wait(60)
            continue

        # 3. Start monitoring
        url = picked["url"]
        _logger.info("Autopilot: starting %s (%s, %d viewers)", picked["title"], picked["uploader"], picked["viewers"])
        with _lock:
            _state["current_url"] = url
            _state["current_title"] = picked["title"]
            _state["current_uploader"] = picked["uploader"]
            _state["current_viewers"] = picked["viewers"]
            _state["started_at"] = time.time()
            _state["last_error"] = ""

        session = None
        try:
            with ctx.as_user(uid):
                creator = _get_or_create_creator(picked["uploader"], url)
                # Stop any existing session for this creator
                existing = live.active_for(creator["id"])
                if existing:
                    existing.stop("Autopilot: rotating to next stream")
                    time.sleep(3)
                job = live.start_session(creator, url)
                session = live.SESSIONS.get(job["id"])
        except Exception as e:
            _logger.warning("Failed to start session for %s: %s", url, e)
            with _lock:
                _state["last_error"] = f"Start failed: {str(e).strip()[:150]}"
            _stop_event.wait(30)
            continue

        if not session:
            _logger.warning("Session object not found after start")
            _stop_event.wait(30)
            continue

        # 4. Monitor for DURATION_MIN minutes
        deadline = time.time() + DURATION_MIN * 60
        while not _stop_event.is_set() and time.time() < deadline:
            if session.ended or session.finished:
                _logger.info("Stream ended naturally before timeout")
                break
            # Update viewer count from session
            with _lock:
                _state["current_viewers"] = session.viewers or picked["viewers"]
            # Pre-fetch candidates 45s before handoff to eliminate transition gap
            if time.time() >= deadline - 45 and prefetched_candidates is None:
                try:
                    prefetched_candidates = _discover_live_gaming_streams()
                except Exception:
                    pass
            _stop_event.wait(15)

        # 5. Stop the session and record history
        clips_before = len([c for c in session.job.get("clips", []) if c.get("status") == "done"])
        try:
            session.stop("Autopilot: time limit reached, rotating to next stream")
        except Exception:
            pass

        with _lock:
            _state["streams_done"] += 1
            _state["clips_total"] += clips_before
            _state["history"].append({
                "url": url,
                "title": picked["title"],
                "uploader": picked["uploader"],
                "viewers": picked["viewers"],
                "clips": clips_before,
                "started": _state["started_at"],
                "ended": time.time(),
            })
            # Keep only last 50 entries
            if len(_state["history"]) > 50:
                _state["history"] = _state["history"][-50:]

        _logger.info("Autopilot: finished %s (%d clips), pausing %ds", picked["title"], clips_before, PAUSE_BETWEEN)

        # 6. Cooldown before next stream
        _stop_event.wait(PAUSE_BETWEEN)

    with _lock:
        _state["running"] = False
    _logger.info("Autopilot stopped")


def start(duration_min: int = None) -> dict:
    """Start the autopilot. Returns the current state."""
    global _thread, DURATION_MIN
    if duration_min:
        DURATION_MIN = max(10, min(480, duration_min))
    with _lock:
        if _state["running"]:
            return state()
        _state["running"] = True
        _state["duration_min"] = DURATION_MIN
        _state["last_error"] = ""
    _stop_event.clear()
    _thread = threading.Thread(target=_run_autopilot, daemon=True, name="autopilot")
    _thread.start()
    return state()


def stop() -> dict:
    """Stop the autopilot after the current stream finishes (or immediately)."""
    _stop_event.set()
    with _lock:
        _state["running"] = False
    return state()


def set_topic(topic: str) -> dict:
    """Set the target trend topic (e.g. 'gta6', 'gaming', 'bgmi')."""
    global AUTOPILOT_TOPIC
    topic = (topic or "gta6").strip().lower()
    with _lock:
        AUTOPILOT_TOPIC = topic
        _state["topic"] = topic
    return state()


def is_running() -> bool:
    return _state.get("running", False)
