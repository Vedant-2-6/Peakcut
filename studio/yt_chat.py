"""Real-time YouTube live chat reader and viewer tracker."""
import logging
import re
import threading
import time

try:
    import pytchat
except ImportError:
    pytchat = None

from . import media

_logger = logging.getLogger("studio.yt_chat")
_YT_ID_PATTERN = re.compile(r"(?:v=|\/live\/|\/shorts\/|youtu\.be\/)([A-Za-z0-9_-]{11})")


def extract_video_id(url: str) -> str:
    """Extract 11-char YouTube video ID from URL or resolve live stream channel."""
    m = _YT_ID_PATTERN.search(url or "")
    if m:
        return m.group(1)
    if media.is_youtube(url):
        try:
            info = media.info(url)
            # If info contains an id or webpage_url with an id
            m2 = _YT_ID_PATTERN.search(info.get("webpage_url") or "")
            if m2:
                return m2.group(1)
        except Exception:
            pass
    return ""


class YouTubeChatReader:
    """Streams live chat messages and updates viewer counts in real-time."""

    def __init__(self, url: str, on_message=None, on_viewers=None, get_stream_time=None):
        self.url = url
        self.video_id = extract_video_id(url)
        self.on_message = on_message
        self.on_viewers = on_viewers
        self.get_stream_time = get_stream_time or (lambda: time.time())
        self.stop_flag = threading.Event()
        self.is_connected = False
        self.total_messages = 0
        self.thread = None

    def start(self):
        if not self.video_id:
            # Try to resolve in background thread
            self.thread = threading.Thread(target=self._resolve_and_run, daemon=True, name="yt_chat_reader")
        else:
            self.thread = threading.Thread(target=self._run, daemon=True, name="yt_chat_reader")
        self.thread.start()

    def stop(self):
        self.stop_flag.set()
        self.is_connected = False

    def _resolve_and_run(self):
        for _ in range(5):
            if self.stop_flag.is_set():
                return
            self.video_id = extract_video_id(self.url)
            if self.video_id:
                break
            time.sleep(3)
        if self.video_id:
            self._run()

    def _run(self):
        if not pytchat:
            _logger.warning("pytchat is not installed; YouTube chat reader disabled.")
            return

        fails = 0
        while not self.stop_flag.is_set():
            live_chat = None
            try:
                live_chat = pytchat.create(video_id=self.video_id)
                self.is_connected = True
                fails = 0
                while live_chat.is_alive() and not self.stop_flag.is_set():
                    data = live_chat.get()
                    if not data:
                        time.sleep(1)
                        continue
                    now_stream_sec = self.get_stream_time()
                    for item in data.sync_items():
                        self.total_messages += 1
                        author = getattr(item.author, "name", "") if hasattr(item, "author") else ""
                        msg = getattr(item, "message", "")
                        amount = getattr(item, "amountValue", 0.0)
                        if self.on_message:
                            try:
                                self.on_message(now_stream_sec, author, msg, bool(amount))
                            except Exception:
                                pass
                    time.sleep(1)
            except Exception as e:
                fails += 1
                self.is_connected = False
                if fails >= 5:
                    time.sleep(15)
                else:
                    time.sleep(3)
            finally:
                if live_chat:
                    try:
                        live_chat.terminate()
                    except Exception:
                        pass
                self.is_connected = False
