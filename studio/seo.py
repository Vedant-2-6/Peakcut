"""High-CTR SEO & Metadata Engine for YouTube Shorts."""
import random
import re

from . import censor

TRENDING_HASHTAGS = {
    "gta 6": ["#GTA6", "#GTAVI", "#Gaming", "#Shorts", "#ViralGaming"],
    "bgmi": ["#BGMI", "#BGMILive", "#Gaming", "#Shorts", "#Clutch"],
    "valorant": ["#Valorant", "#ValorantClips", "#Gaming", "#Shorts"],
    "minecraft": ["#Minecraft", "#MinecraftMemes", "#Gaming", "#Shorts"],
    "default": ["#Gaming", "#Shorts", "#GamingClips", "#Viral", "#Trending"],
}

TITLE_TEMPLATES = [
    "{hook} in {game}! 🤯 #Shorts",
    "Nobody expected this in {game} 🔥 #{game_tag} #Shorts",
    "Watch what happens in {game} 💀 #{game_tag} #Shorts",
    "{streamer} couldn't believe this {game} moment 🚨 #Shorts",
    "Is this the craziest {game} glitch yet?! 🏎️ #Shorts",
]


def clean_name(val: str, max_len: int = 40) -> str:
    return re.sub(r"[^\w\s\-.]", "", str(val or "")).strip()[:max_len]


def generate_shorts_metadata(hook: str, uploader: str = "", game: str = "GTA 6", transcript_snippet: str = "") -> dict:
    """Generate high-retention title, description, and SEO tags for YouTube Shorts.

    Completely strips profanity so videos are never age-restricted by YouTube algorithms.
    """
    game_clean = clean_name(game) or "GTA 6"
    uploader_clean = clean_name(uploader) or "Streamer"
    # Ensure hook is completely clean of swear words
    hook_clean = censor.sanitize_hook(hook)
    hook_clean = clean_name(hook_clean, 50).rstrip(".!?")
    game_tag = re.sub(r"\s+", "", game_clean)

    # 1. High CTR Title (under 75 chars to avoid mobile truncation)
    if hook_clean and len(hook_clean) >= 12:
        title = f"{hook_clean} in {game_clean}! 🤯 #Shorts"
    else:
        tmpl = random.choice(TITLE_TEMPLATES)
        title = tmpl.format(hook=hook_clean or "Crazy Moment", game=game_clean, game_tag=game_tag, streamer=uploader_clean)

    title = censor.clean_title_metadata(title)
    if len(title) > 90:
        title = title[:86] + "... #Shorts"

    # 2. Tag Clusters
    g_low = game_clean.lower()
    hashtags = TRENDING_HASHTAGS.get(g_low, TRENDING_HASHTAGS["default"])
    tags = [game_clean, f"{game_clean} Gameplay", f"{game_clean} Shorts", "Gaming Shorts", "Trending Gaming", uploader_clean]

    # 3. High-SEO Description with Attribution & Fair Use Notice
    desc_lines = [
        f"{censor.clean_title_metadata(hook_clean if hook_clean else title)}",
        "",
        f"Streamer: @{uploader_clean}",
        f"Game: {game_clean}",
        "",
        "Fair Use Notice: This video is a transformative commentary and highlight compilation. Original creator credit is provided above. All rights belong to their respective owners.",
        "",
        " ".join(hashtags)
    ]
    description = "\n".join(desc_lines)

    return {
        "title": title,
        "description": description,
        "hashtags": hashtags,
        "tags": tags,
        "category_id": "20",  # YouTube Gaming Category ID
    }
