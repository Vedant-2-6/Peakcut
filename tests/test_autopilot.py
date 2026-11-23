"""Unit tests for PeakCut Auto-Pilot Stream Discovery and Rotation."""
import os
import sys
import tempfile
import time
from unittest.mock import MagicMock, patch

os.environ["PEAKCUT_DATA"] = tempfile.mkdtemp(prefix="pc-autopilot-")
os.environ["DATABASE_URL"] = ""
sys.path.insert(0, ".")

from studio import autopilot

fails = []


def check(name, ok, extra=""):
    print(("PASS " if ok else "FAIL ") + name + (f"  {extra}" if extra and not ok else ""))
    if not ok:
        fails.append(name)


# 1. State and getters
st = autopilot.state()
check("initial state is not running", not st["running"])
check("default duration is 60 minutes", st["duration_min"] == 60)
check("initial history is a list", isinstance(st["history"], list))
check("is_running helper matches state", autopilot.is_running() == st["running"])

# 2. Discovery logic with mocked yt-dlp
mock_entries = [
    {"id": "vid01", "title": "Casual Minecraft Stream", "uploader": "GamerA", "concurrent_view_count": 450, "is_live": True},
    {"id": "vid02", "title": "Insane BGMI Tournament Grand Finals", "uploader": "Mortal", "concurrent_view_count": 28000, "is_live": True},
    {"id": "vid03", "title": "Valorant Ranked Radiant", "uploader": "ProShooter", "concurrent_view_count": 4200, "live_status": "is_live"},
    {"id": "vid04", "title": "Old VOD Not Live", "uploader": "OfflineGuy", "concurrent_view_count": 100, "is_live": False},
]

with patch("yt_dlp.YoutubeDL") as mock_ydl_cls:
    mock_instance = MagicMock()
    mock_ydl_cls.return_value.__enter__.return_value = mock_instance
    mock_instance.extract_info.return_value = {"entries": mock_entries}

    discovered = autopilot._discover_live_gaming_streams()

check("discovery finds only live streams", len(discovered) == 3, f"got {len(discovered)}")
check("discovery sorts by viewer count descending (#1 is Mortal with 28k)",
      discovered[0]["uploader"] == "Mortal" and discovered[0]["viewers"] == 28000,
      str(discovered[0] if discovered else None))
check("discovery correctly formats YouTube URLs",
      discovered[0]["url"] == "https://www.youtube.com/watch?v=vid02")

# 3. Creator helper
with patch("studio.creators.all_creators", return_value=[]), \
     patch("studio.creators.create", side_effect=lambda d: {"id": "c_auto", **d}):
    creator = autopilot._get_or_create_creator("Mortal Gaming", "https://youtube.com/live/123")
    check("creator created with cleaned name", "Mortal" in creator["name"])

# 4. Start and Stop controls
with patch("studio.autopilot._run_autopilot"):
    started_st = autopilot.start(duration_min=45)
    check("start sets running flag", started_st["running"] and autopilot.is_running())
    check("start sets configured duration", started_st["duration_min"] == 45)

    stopped_st = autopilot.stop()
    check("stop clears running flag", not stopped_st["running"] and not autopilot.is_running())

# 5. Topic and Trend Radar
st_topic = autopilot.set_topic("gta6")
check("set_topic sets topic to gta6", st_topic.get("topic") == "gta6")

# 6. SEO & Metadata Generation for Shorts
from studio import seo
meta = seo.generate_shorts_metadata("Insane car jump across military base", "TypicalGamer", "GTA 6")
check("SEO title contains GTA 6 and #Shorts", "GTA 6" in meta["title"] and "#Shorts" in meta["title"])
check("SEO description contains attribution and fair use notice", "Streamer: @TypicalGamer" in meta["description"] and "Fair Use" in meta["description"])
check("SEO tags include GTA 6 and gaming", any("GTA 6" in t for t in meta["tags"]))

print("ALL AUTOPILOT TESTS PASSED" if not fails else f"{len(fails)} test(s) failed")
import shutil

shutil.rmtree(os.environ["PEAKCUT_DATA"], ignore_errors=True)
sys.exit(1 if fails else 0)
