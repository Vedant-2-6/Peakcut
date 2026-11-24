"""High-CTR Viral Clickbait SEO & Metadata Engine for YouTube Shorts."""
import random
import re

from . import censor

TRENDING_HASHTAGS = {
    "gta 6": ["#GTA6", "#GTAVI", "#Gaming", "#Shorts", "#ViralGaming"],
    "grand theft auto vi": ["#GTA6", "#GTAVI", "#Gaming", "#Shorts", "#ViralGaming"],
    "bgmi": ["#BGMI", "#BGMILive", "#Gaming", "#Shorts", "#Clutch"],
    "valorant": ["#Valorant", "#ValorantClips", "#Gaming", "#Shorts"],
    "minecraft": ["#Minecraft", "#MinecraftMemes", "#Gaming", "#Shorts"],
    "default": ["#Gaming", "#Shorts", "#GamingClips", "#Viral", "#Trending"],
}

CLICKBAIT_TEMPLATES = [
    "{streamer} Did NOT Just Do That in {game}! 🤯 #{game_tag} #Shorts",
    "WAIT FOR THE ENDING... {streamer} Lost It in {game} 💀 #{game_tag} #Shorts",
    "He Actually Pulled This Off in {game}?! 🔥 #{game_tag} #Shorts",
    "Nobody Expected {streamer} To Survive This in {game} 🚨 #Shorts",
    "99% Of Players Miss This in {game}... 😱 #{game_tag} #Shorts",
    "How Did {streamer} Even Do This in {game}?! 🤯 #{game_tag} #Shorts",
    "This {game} Moment Broke The Whole Stream! 💀 #{game_tag} #Shorts",
]

_GENERIC_TITLES = {"clip", "loud moment", "viral moment", "wait for it", "untitled", ""}
_FILLER_HOOKS = re.compile(
    r"^(?:thank you(?: so much)?|love you(?: brother| guys)?|bye(?: bye)?|hello|hi guys|okay|ok|"
    r"good morning|what's up|i get that all the time|yes|no|yeah|wait|bro|bruh)[\s!?.]*$",
    re.I,
)
_HAS_EMOJI = re.compile(r"[\U0001F300-\U0001FAFF\u2600-\u27BF]")
_POWER_EMOJIS = ("🤯", "🔥", "💀", "🚨", "😱", "⚡")


def clean_name(val: str, max_len: int = 40) -> str:
    return re.sub(r"[^\w\s\-.]", "", str(val or "")).strip()[:max_len]


def _clean_emoji_title(val: str, max_len: int = 85) -> str:
    return re.sub(r"[<>]", "", str(val or "")).strip()[:max_len]


def _is_strong_title(title: str) -> bool:
    t = re.sub(r"#\w+", "", title or "").strip()
    if len(t) < 14:
        return False
    if t.lower() in _GENERIC_TITLES or _FILLER_HOOKS.match(t):
        return False
    return True


def _format_clickbait_title(raw_title: str, game_clean: str, uploader_clean: str) -> str:
    """Turn an AI title into an eye-catching YouTube Shorts clickbait title while staying under limits."""
    t = censor.clean_title_metadata(_clean_emoji_title(raw_title, 78))
    # Strip trailing #Shorts so we append tags cleanly once
    t = re.sub(r"\s*#shorts\b", "", t, flags=re.I).strip()
    # Add punchy emoji if none present
    if not _HAS_EMOJI.search(t):
        t = f"{t} {random.choice(_POWER_EMOJIS)}"
    # Ensure game name is searchable in the title if room permits
    if game_clean and game_clean.lower() not in t.lower() and not ("gta" in game_clean.lower() and "gta" in t.lower()):
        if len(t) + len(game_clean) + 12 <= 90:
            t = f"{t} ({game_clean})"
    if "#shorts" not in t.lower():
        t = f"{t} #Shorts"
    if len(t) > 95:
        t = re.sub(r"\s*#shorts\b", "", t, flags=re.I).strip()[:83].rstrip() + "... #Shorts"
    return t


def generate_shorts_metadata(
    hook: str,
    uploader: str = "",
    game: str = "GTA 6",
    transcript_snippet: str = "",
    ai_title: str = "",
) -> dict:
    """Generate high-CTR clickbait title, description, and SEO tags for YouTube Shorts.

    Prefers strong AI-generated clickbait titles over raw transcript hooks, strips profanity so
    videos are never age-restricted, and uses viral curiosity templates as fallback.
    """
    game_clean = clean_name(game) or "GTA 6"
    uploader_clean = clean_name(uploader) or "Streamer"
    hook_clean = censor.sanitize_hook(hook)
    hook_clean = clean_name(hook_clean, 50).rstrip(".!?")
    game_tag = re.sub(r"\s+", "", game_clean)

    ai_clean = censor.clean_title_metadata(ai_title)
    if _is_strong_title(ai_clean):
        title = _format_clickbait_title(ai_clean, game_clean, uploader_clean)
    elif hook_clean and len(hook_clean) >= 14 and not _FILLER_HOOKS.match(hook_clean):
        # Hook itself has real context: frame it with high-CTR curiosity framing
        if hook_clean.isupper():
            hook_display = hook_clean.title() if len(hook_clean.split()) > 3 else hook_clean
        else:
            hook_display = hook_clean
        title = _format_clickbait_title(f"{hook_display} in {game_clean}?!", game_clean, uploader_clean)
    else:
        tmpl = random.choice(CLICKBAIT_TEMPLATES)
        title = tmpl.format(
            hook=hook_clean or "Crazy Moment",
            game=game_clean,
            game_tag=game_tag,
            streamer=uploader_clean,
        )

    title = censor.clean_title_metadata(title)
    if len(title) > 95:
        title = title[:86].rstrip() + "... #Shorts"

    # 2. Tag Clusters
    g_low = game_clean.lower()
    hashtags = TRENDING_HASHTAGS.get(g_low, TRENDING_HASHTAGS["default"])
    tags = [game_clean, f"{game_clean} Gameplay", f"{game_clean} Shorts", "Gaming Shorts", "Trending Gaming", uploader_clean]

    # 3. High-SEO Description with Attribution & Fair Use Notice
    headline = censor.clean_title_metadata(ai_clean if _is_strong_title(ai_clean) else (hook_clean or title))
    desc_lines = [
        headline,
        "",
        f"Streamer: @{uploader_clean}",
        f"Game: {game_clean}",
        "",
        "Fair Use Notice: This video is a transformative commentary and highlight compilation. Original creator credit is provided above. All rights belong to their respective owners.",
        "",
        " ".join(hashtags),
    ]
    description = "\n".join(desc_lines)

    return {
        "title": title,
        "description": description,
        "hashtags": hashtags,
        "tags": tags,
        "category_id": "20",  # YouTube Gaming Category ID
    }
